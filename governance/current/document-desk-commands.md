# Typed document desk commands

The existing Action Registry exposes five bounded actions for the selected active
document cases: Archive, Delete, Re-analyze, Compare and Reload. The existing
conversational turn gateway resolves one typed proposal. It cannot select targets,
grant permissions, confirm deletion or report execution as successful.

The existing bulk Flask route validates ownership and disposable-case lifecycle
and every case's effective external-AI policy before sending display titles to
the provider, then reloads the same selection
after intent resolution. It invokes the ordinary bulk executors. Delete always
opens the existing seven-day recovery confirmation. Reload redirects to the
persisted list without writing records or queuing analysis. Unsupported,
ambiguous, malformed and unavailable-provider results do not execute an action.

View commands remain enabled only in their original single-source context.
Document-list commands cannot enter that executor. No separate dispatcher,
analysis engine, evidence store or lifecycle owner is introduced.

The selected-row action bar exposes the command input and concise privacy copy.
Existing action buttons and the separate Reload control remain usable.
Enter in the command field submits that command, never the first bulk button.
Runtime observation records actual intent resolution and existing executor invocation;
a typed proposal alone is not proof of execution.

Tests: tests/test_document_desk_commands.py covers owner isolation, lifecycle
changes during provider execution, confirmation, malformed proposals, outages,
source preservation and read-only Reload. Existing bulk and typed-view tests
cover the shared paths. tools/verify_document_shop_bulk.py --commands
--desk-commands exercises the real Flask UI and executors. Local intent-provider
responses are controlled and are explicitly not live natural-language proof.

This increment does not implement general canonical promotion commands,
investment matching or the remaining master-programme capabilities.
