"""GOPILOT NERVOUS SYSTEM - the ONE governed intake for a Composer image.

Every server path that accepts an image from the canonical Composer (a pasted
screenshot, a picked file, a phone photo, or Image Search's "send to Composer")
reads it here. There were two validators with different rules - the workspace
photo path had the 5MB ceiling but took ANY data:image/* (SVG included), and the
Developer path had a type allowlist but no ceiling. This keeps the union of both.

    shape      a data: URL of the form  data:image/<type>;base64,<payload>
    type       PNG, JPEG, GIF or WebP only - the raster formats a vision model
               reads; SVG (markup that can carry script) and anything else refused
    size       5MB decoded, checked on the payload length BEFORE decoding, so an
               oversized upload costs nothing
    encoding   the payload must actually be base64

It is a validator, not an upload subsystem: nothing is written to disk,
registered or retained here. The external-AI policy is the CALLER's context:
a project-less surface passes its gate in `policy_allowed`; a project surface
resolves its project's own policy at its own point in the turn (where it tells
the person, in the conversation, that a photo was not sent).

A refusal is never an exception: a turn with an unusable image still carries
its text, and the caller can say why the image was not used.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Callable, Optional

ALLOWED_MEDIA_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")
MAX_IMAGE_BYTES = 5 * 1024 * 1024   # the vision provider's own base64-image ceiling

STATUS_ABSENT = "absent"                    # no image was sent
STATUS_ACCEPTED = "accepted"
STATUS_MALFORMED = "malformed"              # not a well-formed base64 image data URL
STATUS_UNSUPPORTED = "unsupported_type"     # an image, but not PNG/JPEG/GIF/WebP
STATUS_TOO_LARGE = "too_large"
STATUS_POLICY_DENIED = "policy_denied"      # valid, but this context may not send it out

REASONS = {
    STATUS_MALFORMED: "The attachment could not be read as an image.",
    STATUS_UNSUPPORTED: "That image type is not supported - use PNG, JPEG, GIF or WebP.",
    STATUS_TOO_LARGE: "That image is too large to send (5MB limit).",
    STATUS_POLICY_DENIED: "Images cannot be sent to GO here under the current security policy.",
}


@dataclass(frozen=True)
class ComposerImage:
    status: str
    media_type: Optional[str] = None
    base64: Optional[str] = None

    @property
    def accepted(self) -> bool:
        return self.status == STATUS_ACCEPTED

    @property
    def sent(self) -> bool:
        """Something that looked like an image arrived, whatever became of it."""
        return self.status != STATUS_ABSENT

    @property
    def reason(self) -> str:
        return REASONS.get(self.status, "")

    @property
    def decoded_size(self) -> int:
        return len(self.base64) * 3 // 4 if self.base64 else 0


def validate(data_url: Optional[str]) -> ComposerImage:
    """Shape, type, size and encoding - pure, no request, no policy."""
    raw = (data_url or "").strip()
    if not raw:
        return ComposerImage(STATUS_ABSENT)
    if not raw.startswith("data:image/"):
        return ComposerImage(STATUS_MALFORMED)
    header, _, payload = raw.partition(",")
    if not header.endswith(";base64") or not payload.strip():
        return ComposerImage(STATUS_MALFORMED)
    media_type = header[len("data:"):-len(";base64")].split(";", 1)[0].strip().lower()
    if media_type not in ALLOWED_MEDIA_TYPES:
        return ComposerImage(STATUS_UNSUPPORTED, media_type=media_type)
    payload = payload.strip()
    if len(payload) * 3 / 4 > MAX_IMAGE_BYTES:   # before decoding: an oversized payload costs nothing
        return ComposerImage(STATUS_TOO_LARGE, media_type=media_type)
    try:
        base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return ComposerImage(STATUS_MALFORMED, media_type=media_type)
    return ComposerImage(STATUS_ACCEPTED, media_type=media_type, base64=payload)


def from_request(form, *, policy_allowed: Optional[Callable[[], bool]] = None,
                 field: str = "image_data_url") -> ComposerImage:
    """The Composer's image field, validated, then - when the caller's context
    supplies one - checked against that context's external-AI policy. A denied
    image is dropped here, so it cannot reach the model by any later path."""
    image = validate(form.get(field))
    if image.accepted and policy_allowed is not None and not policy_allowed():
        return ComposerImage(STATUS_POLICY_DENIED, media_type=image.media_type)
    return image
