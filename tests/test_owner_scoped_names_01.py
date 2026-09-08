"""CLAUDE-BLACK-BOX-OWNER-NAMES-01: a display name is a label, not an identifier.

DISPLAY NAME UNIQUENESS IS OWNER-SCOPED, NOT DEPLOYMENT-SCOPED.

The old rule did two wrong things with one check. It stopped two unrelated
customers using the same ordinary words, and its refusal disclosed that SOMEBODY
ELSE held that name - a cross-customer existence oracle inside a validation
message, in an application that returns a generic 404 everywhere else precisely
so existence is never confirmed.

Two tests carry the weight:

`test_a_refusal_can_only_be_caused_by_your_own_container` - the disclosure,
asserted directly. This is the regression the whole tranche exists to prevent.

`test_one_owner_still_cannot_have_two_containers_of_the_same_name` - the
protection that must survive the narrowing.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore, SOURCE_KIND_UNCLASSIFIED,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import (
    UploadError, _names_owned_by, ingest_upload, reject_if_display_name_taken,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class OwnerScopedNameTests(unittest.TestCase):

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_names_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _project(self, owner, name, filename="rfp.pdf"):
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename=filename),
                    self.app, operating_environment=CLIENT_OWNER, owner=owner,
                    project_name=name)

    def _job(self, owner, name, filename="notes.txt"):
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename=filename),
                    self.app, operating_environment=None, owner=owner,
                    container_state=CONTAINER_STATE_BLACK_BOX, project_name=name)

    # -- the disclosure this exists to remove --------------------------------

    def test_a_refusal_can_only_be_caused_by_your_own_container(self):
        """The regression. Ana's container must be invisible to Ben, including
        through the shape of an error message he can provoke at will."""
        self._project("ana", "Warehouse Conversion")
        ben = self._project("ben", "Warehouse Conversion", filename="ben.pdf")
        self.assertTrue(ben.project_id)
        self.assertEqual(
            self.store.get(ben.project_id).owner, "ben")

    def test_different_owners_may_share_a_project_name(self):
        a = self._project("ana", "Community Centre")
        b = self._project("ben", "Community Centre", filename="b.pdf")
        self.assertNotEqual(a.project_id, b.project_id)

    def test_different_owners_may_share_a_document_shop_name(self):
        a = self._job("ana", "Electrical Review")
        b = self._job("ben", "Electrical Review", filename="b.txt")
        self.assertNotEqual(a.project_id, b.project_id)

    def test_another_owners_name_is_never_in_your_namespace(self):
        self._project("ana", "Private Thing")
        self.assertEqual(_names_owned_by(self.app, "ben"), set())
        self.assertIn("Private Thing", _names_owned_by(self.app, "ana"))

    # -- the protection that must survive ------------------------------------

    def test_one_owner_still_cannot_have_two_containers_of_the_same_name(self):
        self._project("ana", "Community Centre")
        with self.assertRaises(UploadError) as caught:
            self._project("ana", "Community Centre", filename="second.pdf")
        self.assertIn("already in use", str(caught.exception))

    def test_one_owner_cannot_have_two_document_shop_jobs_of_the_same_name(self):
        self._job("ana", "Electrical Review")
        with self.assertRaises(UploadError):
            self._job("ana", "Electrical Review", filename="second.txt")

    def test_one_owner_has_one_namespace_across_operating_lines(self):
        """Pre-existing behaviour narrowed by owner, not a new namespace rule.

        Two identically-named things in one person's own list are confusing
        whatever operating line each belongs to.
        """
        self._project("ana", "Riverside")
        with self.assertRaises(UploadError):
            self._job("ana", "Riverside", filename="job.txt")

    def test_the_reverse_direction_holds_too(self):
        self._job("ana", "Northgate")
        with self.assertRaises(UploadError):
            self._project("ana", "Northgate", filename="p.pdf")

    # -- rename is the same oracle through a different door ------------------

    def test_rename_is_owner_scoped(self):
        self._project("ana", "Ana Thing")
        ben = self._project("ben", "Ben Thing", filename="b.pdf")
        with self.app.app_context():
            # Ben renaming to Ana's name is allowed - he must not learn it exists.
            reject_if_display_name_taken(
                self.app, "Ana Thing", exclude_project_id=ben.project_id,
                owner="ben")

    def test_rename_still_refuses_your_own_duplicate(self):
        self._project("ana", "First")
        second = self._project("ana", "Second", filename="s.pdf")
        with self.app.app_context():
            with self.assertRaises(UploadError):
                reject_if_display_name_taken(
                    self.app, "First", exclude_project_id=second.project_id,
                    owner="ana")

    def test_renaming_to_its_own_name_is_never_a_collision(self):
        only = self._project("ana", "Unchanged")
        with self.app.app_context():
            reject_if_display_name_taken(
                self.app, "Unchanged", exclude_project_id=only.project_id,
                owner="ana")

    # -- audited behaviour, deliberately preserved ---------------------------

    def test_a_removed_container_still_holds_its_owners_name(self):
        """PRE-EXISTING and unchanged: removal does not free the name.

        The uniqueness scan has never filtered on removed_at, so a removed
        container keeps its name reserved for its owner. Owner-scoping did not
        require changing that, so it was not changed - the rule is recorded
        here rather than quietly redefined.
        """
        first = self._project("ana", "Recycled Name")
        workspace = self.store.get(first.project_id)
        self.store.remove_project(workspace, actor="ana", actor_role="admin",
                                  reason="test")
        with self.assertRaises(UploadError):
            self._project("ana", "Recycled Name", filename="again.pdf")

    def test_an_ownerless_container_belongs_to_nobodys_namespace(self):
        """A legacy record with no established owner matches no one.

        Folding unattributed containers into an asking owner's namespace would
        reintroduce the disclosure this tranche removes. Recorded as a real
        consequence rather than left implicit.
        """
        document = self._project("ana", "Legacy Shaped")
        workspace = self.store.get(document.project_id)
        workspace.owner = None
        self.store.save(workspace)
        self.assertEqual(_names_owned_by(self.app, "ana"), set())
        self.assertEqual(_names_owned_by(self.app, None), set())
        self.assertEqual(_names_owned_by(self.app, ""), set())

    def test_normalization_semantics_are_unchanged(self):
        """Comparison is still exact-after-strip, case-sensitive as before.

        Asserted to PIN current behaviour, not to bless it. Case-folding,
        Unicode and whitespace policy were explicitly out of scope; this test
        exists so a future normalization change is a deliberate act.
        """
        self._project("ana", "Riverside Centre")
        allowed = self._project("ana", "riverside centre", filename="lower.pdf")
        self.assertTrue(allowed.project_id)
        with self.assertRaises(UploadError):
            self._project("ana", "  Riverside Centre  ", filename="spaces.pdf")

    # -- nothing else moved ---------------------------------------------------

    def test_internal_identifiers_remain_globally_unique(self):
        a = self._project("ana", "Same Name")
        b = self._project("ben", "Same Name", filename="b.pdf")
        self.assertNotEqual(a.project_id, b.project_id)
        codes = {self.store.get(a.project_id).project_code,
                 self.store.get(b.project_id).project_code}
        self.assertEqual(len(codes), 2,
                         "project codes stay deployment-wide and distinct")

    def test_container_state_and_source_kind_are_unaffected(self):
        job = self._job("ana", "A Job")
        workspace = self.store.get(job.project_id)
        self.assertEqual(workspace.container_state, CONTAINER_STATE_BLACK_BOX)
        self.assertEqual(workspace.sources[0]["kind"], SOURCE_KIND_UNCLASSIFIED)

    def test_owner_is_required_with_no_default(self):
        """A default would silently restore deployment-wide behaviour."""
        import inspect
        from services.ingestion import _reject_if_name_taken

        signature = inspect.signature(_reject_if_name_taken)
        self.assertIs(signature.parameters["owner"].default,
                      inspect.Parameter.empty)

    def test_access_isolation_is_unchanged(self):
        ana = self._project("ana", "Ana Only")
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 2
            session["username"] = "ben"
            session["role"] = "read_only"
        self.assertEqual(
            client.get("/projects/%s/workspace" % ana.project_id).status_code,
            404, "a generic 404, never a distinguishable refusal")
