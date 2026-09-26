"""LIQUID SANDBOX - OBJECT FIELD v0 STORAGE HARDENING. Focused proof.

Two things only, no new capability:

1. PROVISIONAL MEDIA RETENTION - bytes live under SANDBOX_MEDIA_PATH, a root of
   their own outside the registry (so registry snapshots never carry them),
   outside PROJECT_ASSET_PATH and every project store; per-owner; deleted with
   the Sandbox; unreferenced files swept after every write.
2. TWO-TAB WRITE RACES - optimistic revision tokens. A write names the Sandbox
   token its page was drawn from; a stale one is REFUSED (never merged) and the
   person is told to refresh. The compare-and-swap runs under a short per-owner
   lock, so two in-flight requests cannot both pass.

Hermetic: every model call is a spy.
"""
from __future__ import annotations

import base64
import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

from config import BaseConfig as Config, TestingConfig
from services import llm_gateway
from services import sandbox as sb
from tests.test_liquid_sandbox_object_field_01 import MARKER_A, MARKER_B, _Field
from tests.test_sandbox_slice1_01 import MODEL_REPLY, _png_data_url

REFRESH = "This Sandbox changed in another tab or window. Refresh"


class _Tabs(_Field):
    def store(self):
        return sb.SandboxStore(str(self.tmp), str(self.media))

    def stale_turn(self, token, text, data_url=None, selected=()):
        """A tab whose page was drawn at `token` sends a message."""
        calls = []
        data = {"text": text, "object_id": list(selected), "sandbox_base": token}
        if data_url:
            data["image_data_url"] = data_url
        def spy(**kwargs):
            calls.append(kwargs)
            return MODEL_REPLY

        with patch("routes.portal._project_less_external_ai_allowed", return_value=True), \
                patch.object(llm_gateway, "call_llm_json", side_effect=spy):
            response = self.boss.post("/sandbox/turn", data=data)
        return response, calls

    def media_files(self):
        return sorted(p.name for p in self.media.rglob("*") if p.is_file())


class StaleTabIsRejected(_Tabs):
    def test_a_stale_tab_message_is_refused_before_anything_is_sent_or_kept(self):
        self.turn(MARKER_A, _png_data_url(24, 16))
        tab_a = self.token()                                  # tab A draws its page here
        self.turn(MARKER_B)                                   # tab B sends - the Sandbox moves on
        before, files = self.record(), self.media_files()

        response, calls = self.stale_turn(tab_a, "From the stale tab", _png_data_url(40, 40))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(calls, [])                           # nothing reached the model
        self.assertEqual(self.record(), before)               # nothing was kept
        self.assertEqual(self.media_files(), files)           # no new image, none lost
        self.assertIn(REFRESH, self.page())

    def test_a_message_without_any_token_is_refused(self):
        self.turn(MARKER_A)
        before = self.record()
        response, calls = self.stale_turn("", "No token")
        self.assertEqual(calls, [])
        self.assertEqual(self.record(), before)

    def test_a_stale_tab_cannot_choose_a_landing(self):
        self.turn("I want a permit for this townhouse renovation.")
        tab_a = self.token()
        self.turn("It is in Toronto.")
        before = self.record()["decisions"]
        self.boss.post("/sandbox/landing", data={"sandbox_id": self.record()["id"], "choice": "continue",
                                                 "sandbox_base": tab_a})
        self.assertEqual(self.record()["decisions"], before)
        self.assertIn(REFRESH, self.page())

    def test_a_stale_clean_tab_cannot_replace_a_newer_sandbox(self):
        """The dangerous case: a new Sandbox replaces the record and deletes its media."""
        self.turn(MARKER_A, _png_data_url(24, 16))
        self.boss.get("/sandbox?new=1")
        clean_tab = self.token()                              # two tabs showing the clean start
        self.turn("Tab B starts the new Sandbox", _png_data_url(30, 30))
        kept, files = self.record(), self.media_files()

        _, calls = self.stale_turn(clean_tab, "Tab A starts one too")
        self.assertEqual(calls, [])
        self.assertEqual(self.record(), kept)                 # tab B's Sandbox survives
        self.assertEqual(self.media_files(), files)           # and so do its images


class FreshTabSucceeds(_Tabs):
    def test_refreshing_and_sending_again_works(self):
        self.turn(MARKER_A)
        tab_a = self.token()
        self.turn(MARKER_B)
        self.stale_turn(tab_a, "stale")
        fresh = self.token()                                  # tab A refreshes
        response, calls = self.stale_turn(fresh, "After refresh")
        self.assertEqual(len(calls), 1)
        self.assertEqual([t["text"] for t in self.record()["turns"]], [MARKER_A, MARKER_B, "After refresh"])
        self.assertNotEqual(self.token(), fresh)              # every write moves the revision

    def test_the_page_carries_the_token_on_every_writing_form(self):
        self.turn("I want a permit for this townhouse renovation.")
        html = self.page()
        token = self.token()
        self.assertEqual(html.count('name="sandbox_base" value="%s"' % token), 3)   # Composer + 2 landing forms


class TheCompareAndSwapHoldsUnderConcurrency(_Tabs):
    def test_only_one_of_many_simultaneous_writers_with_the_same_token_wins(self):
        self.turn(MARKER_A)
        store, record, token = self.store(), self.record(), self.token()
        results = []

        def writer(n):
            try:
                store.add_turn("cover_boss", record["id"], "writer %d" % n, {"canonical": False}, expected=token)
                results.append("ok")
            except sb.SandboxConflict:
                results.append("conflict")

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(results), ["conflict"] * 7 + ["ok"])
        self.assertEqual(len(self.record()["turns"]), 2)

    def test_server_internal_writes_never_lose_an_update(self):
        self.turn(MARKER_A)
        store, record = self.store(), self.record()
        threads = [threading.Thread(target=store.add_turn,
                                    args=("cover_boss", record["id"], "internal %d" % n, {"canonical": False}))
                   for n in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        texts = [t["text"] for t in self.record()["turns"]]
        self.assertEqual(len(texts), 9)
        self.assertEqual(sorted(texts[1:]), sorted("internal %d" % n for n in range(8)))

    def test_a_refused_write_leaves_no_media_behind(self):
        self.turn(MARKER_A)
        store, record, stale = self.store(), self.record(), self.token()
        self.turn(MARKER_B)
        files = self.media_files()
        data = _png_data_url(50, 50).split(",", 1)[1]
        with self.assertRaises(sb.SandboxConflict):
            store.add_turn("cover_boss", record["id"], "late", {}, image=(data, "image/png"), expected=stale)
        self.assertEqual(self.media_files(), files)

    def test_an_abandoned_lock_does_not_block_the_owner_forever(self):
        self.turn(MARKER_A)
        store = self.store()
        lock = store.root / (store._digest("cover_boss") + ".lock")
        lock.write_text("")
        old = time.time() - 120
        os.utime(lock, (old, old))
        store.add_turn("cover_boss", self.record()["id"], "after a crash", {})
        self.assertEqual(self.record()["turns"][-1]["text"], "after a crash")
        self.assertFalse(lock.exists())


class MediaRetentionAndIsolation(_Tabs):
    def test_media_lives_outside_the_registry_and_project_assets(self):
        for cfg in (Config, TestingConfig):
            media = Path(cfg.SANDBOX_MEDIA_PATH).resolve()
            for other in (cfg.REGISTRY_STORE_PATH, cfg.PROJECT_ASSET_PATH):
                other = Path(other).resolve()
                with self.subTest(cfg=cfg.__name__, other=str(other)):
                    self.assertNotEqual(media, other)
                    self.assertNotIn(other, media.parents)          # never inside a snapshot root
                    self.assertNotIn(media, other.parents)
        self.turn("photo", _png_data_url())
        self.assertEqual([p for p in self.tmp.rglob("*.png")], [])  # nothing in the test registry
        self.assertEqual(len(self.media_files()), 1)

    def test_owners_are_isolated_on_disk_and_in_deletion(self):
        store = self.store()
        data = _png_data_url(12, 12).split(",", 1)[1]
        for owner in ("owner_one", "owner_two"):
            record = store.start(owner)
            store.add_turn(owner, record["id"], "same photo", {}, image=(data, "image/png"))
        dirs = sorted(p.name for p in self.media.iterdir())
        self.assertEqual(len(dirs), 2)                               # one directory per owner
        one = store.get("owner_one")["objects"][-1]
        store.start("owner_one")                                     # owner one's new Sandbox
        self.assertIsNone(store.read_media("owner_one", one))
        self.assertIsNotNone(store.read_media("owner_two", store.get("owner_two")["objects"][-1]))

    def test_unreferenced_files_are_swept_after_a_write(self):
        self.turn("photo", _png_data_url())
        store = self.store()
        orphan = store._owner_media("cover_boss") / ("f" * 64 + ".png")
        orphan.write_bytes(b"left behind")
        self.turn(MARKER_B)
        self.assertFalse(orphan.exists())
        self.assertEqual(len(self.media_files()), 1)                 # the referenced image stays

    def test_the_media_route_keeps_its_protections(self):
        self.turn("photo", _png_data_url(24, 16))
        image = self.objects("image")[0]
        served = self.boss.get("/sandbox/media/%s" % image["id"])
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", served.headers["Cache-Control"])
        # a tampered file fails its checksum and is not served
        path = next(self.media.rglob("*.png"))
        path.write_bytes(b"not the image")
        self.assertEqual(self.boss.get("/sandbox/media/%s" % image["id"]).status_code, 404)

    def test_a_store_opened_without_a_media_root_cannot_touch_bytes(self):
        self.turn("photo", _png_data_url())
        reader = sb.SandboxStore(str(self.tmp))                      # the planning owner's view
        self.assertIsNone(reader.read_media("cover_boss", self.objects("image")[0]))
        reader.mark_promoted("cover_boss", self.record()["id"], {"landing": "planning_study"})
        self.assertEqual(len(self.media_files()), 1)                 # promotion marking leaves media alone
