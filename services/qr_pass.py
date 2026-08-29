"""CLAUDE-QR-PASS-01 — a pass you can hold up and someone can scan.

WHY THIS EXISTS. A superintendent standing on a deck with a phone in one hand
cannot type a 43-character bearer token, and dictating one across a site is how
it ends up written on a drywall offcut. The QR is the token, rendered.

RENDERED LOCALLY, ALWAYS. `segno` is pure Python with zero dependencies of its
own and makes no network call - no Google Chart API, no third-party image
service. That matters more here than convenience: the payload IS A LIVE
CREDENTIAL, and handing it to an external image service would mail every
stakeholder pass to a company nobody chose.

THE HARD CONSTRAINT THIS MODULE IS SHAPED BY

`services/project_rbac.py` stores ONLY `sha256(token)`. The raw value exists
once, in the response to the request that minted it, and nowhere afterwards -
the same "never store the real secret" property PasswordResetToken,
VerificationAccessToken and StorageAgentEnrolment all share.

So there is no function here that takes a token id and returns its QR. There
cannot be: the raw token is gone. A `token_hash` in the URL would not work
either (the server hashes what is presented, so it would compare
sha256(sha256(token))) and if it ever did work, the stored digest would itself
become a usable credential - destroying the exact property hash-only storage
exists to provide.

That is why there are two flows and no third:

  A  ONE-TIME REVEAL. The QR is rendered beside the link, in the response that
     created the pass. Costs nothing, stores nothing.

  B  ROTATION. For a pass already in the table, the old credential is REVOKED
     and a fresh one minted. The QR shows the new token. The previous link
     stops working immediately - which is the correct behaviour for a field
     pass being handed to somebody, not a side effect to apologise for.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# Rendered at a size that scans from three or four feet - a phone camera needs
# roughly 2-3 pixels per module, and a job-site scan is never at arm's length.
DEFAULT_SCALE = 8
DEFAULT_BORDER = 2

# Deliberately high, and deliberately not configurable per call. A QR held up
# on a cracked phone screen, in daylight, at an angle, with dust on it, is the
# ordinary case rather than the bad one. M recovers ~15% of the symbol; L would
# render slightly smaller and fail more often in exactly the conditions this
# is for.
ERROR_CORRECTION = "m"


def render_token_qr_svg(target_url: str, *, scale: int = DEFAULT_SCALE,
                        border: int = DEFAULT_BORDER,
                        dark: str = "#000000", light: str = "#FFFFFF") -> str:
    """An inline SVG QR for a full access URL.

    Returns markup for embedding directly in a page - no file is written and
    nothing is cached. A credential written to disk as an image is a
    credential that outlives the page it was shown on.

    Colours default to pure black on pure white and SHOULD NOT be themed. A
    scanner needs contrast, not brand: a dark-mode QR in muted greys is the
    classic way to make a code that looks correct and reads unreliably in
    daylight. The page around it may be any colour; the symbol itself is not
    negotiable, and the template gives it its own white plate for that reason.
    """
    import segno

    if not target_url or not str(target_url).strip():
        raise ValueError("a QR pass needs a target URL")

    code = segno.make(str(target_url).strip(), error=ERROR_CORRECTION)
    import io

    # BytesIO, not StringIO: segno's SVG serialiser writes encoded bytes.
    buffer = io.BytesIO()
    code.save(
        buffer,
        kind="svg",
        scale=scale,
        border=border,
        dark=dark,
        light=light,
        # No XML declaration: this is embedded INSIDE an HTML document, and a
        # second <?xml ...?> mid-document is invalid.
        xmldecl=False,
        svgns=True,
        # Its own title would be read aloud before the surrounding context;
        # the template labels it instead, where the label can say what the
        # pass is FOR rather than that it is a QR code.
        omitsize=False,
    )
    return buffer.getvalue().decode("utf-8")


def pass_target_url(base_url: str, project_id: str, raw_token: str) -> str:
    """The canonical URL a scan should land on.

    Built here rather than in a template so the two flows cannot drift into
    producing different shapes, and so the token appears in exactly one
    place that can be reviewed.
    """
    root = (base_url or "").rstrip("/")
    return f"{root}/project/{project_id}?token={raw_token}"


def remaining_duration(expires_at: datetime, *, now: Optional[datetime] = None) -> str:
    """How long is left, in words a person reads at a glance.

    Rounded DOWN and never optimistic: "1 day" for anything from 24 to 47
    hours. A pass that says 2 days and dies in 25 hours strands somebody on a
    deck, so the error is always in the safe direction.
    """
    moment = now or datetime.now(timezone.utc)
    deadline = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    seconds = int((deadline - moment).total_seconds())

    if seconds <= 0:
        return "expired"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    days = seconds // 86400
    return f"{days} day{'s' if days != 1 else ''}"


def rotate_pass(token_id: int, *, actor: Optional[str] = None):
    """Flow B. Revoke a pass and mint its replacement, atomically enough.

    Returns `(new_row, raw_token)`.

    ORDER MATTERS AND IS DELIBERATE: the new pass is minted FIRST, then the old
    one is revoked. The reverse order has a window in which the stakeholder has
    no working credential at all, and if minting then failed they would be left
    with nothing while the superintendent believed they had just been handed a
    pass. Overlap for a few milliseconds is the safer failure.

    The replacement inherits role, disciplines and remaining lifetime exactly.
    Rotation is a new CREDENTIAL, never a new GRANT - anything else would make
    "re-issue" a quiet way to widen access.
    """
    from models import ProjectAccessToken, db

    from services.project_rbac import ProjectAccessRefused, issue_token, revoke_token

    old = db.session.get(ProjectAccessToken, token_id)
    if old is None or old.revoked_at is not None:
        raise ProjectAccessRefused("This project token is not authorised for that.")

    expires_at = old.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        # Rotating an expired pass would silently extend it, because
        # issue_token refuses a deadline in the past and would otherwise need
        # a new one invented here. Reissuing is the architect's decision to
        # make on the form, not something rotation does on their behalf.
        raise ProjectAccessRefused("This project token is not authorised for that.")

    disciplines = [d for d in (old.disciplines or "").split(",") if d]
    new_row, raw_token = issue_token(
        old.project_id,
        old.role,
        label=old.label,
        actor=actor,
        disciplines=disciplines or None,
        expires_at=expires_at,
    )
    revoke_token(token_id, actor=actor)
    return new_row, raw_token
