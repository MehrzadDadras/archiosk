# Specified But Unbuilt — Project Security Policy

**Status:** Specified, not implemented. Not a new domain, not a new kernel concept.

A future owner-side Project Security Policy — personnel clearance, information classification, physical/remote access, view/copy/print/download/export rights, retention/destruction, procurement-stage restrictions, exceptions/approvals — is squarely **Domain 1, project-specific governed content**: ordinary `Requirement`s about a different `subject_domain` (information handling) than the usual physical/code-compliance subject matter, using the already-open-world `subject_domain` field, nothing new required for the object model itself.

**Governing principle preserved:** personnel authorization and information possession are not the same thing. Role/clearance is an authority-axis question; document-access-grant is a scope/visibility-axis question (the same private/shared boundary work already established) — conflating them into one field would repeat exactly the "two questions collapsed into one" error this model rejects everywhere else.

Detecting contradictions between security requirements and required proponent/team activities needs no new detection mechanism — it's the same contradiction-checking machinery already established for authoritative metamorphosis, applied to Security-Policy-shaped Requirements alongside physical/code Requirements.

**Explicitly not designed here, and not to be confused with this document:** infrastructure/tenant hosting isolation (separate encryption keys, separate physical/cloud tenancy, deployment-level separation) remains a distinct, unsolved, operational-security layer — see `deferred-reserved/reservations.md`. Everything resolved in this baseline is data-model and application-layer; infrastructure isolation is out of scope for this document and for the architecture review that produced it.
