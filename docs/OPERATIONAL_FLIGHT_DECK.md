# Operational Convergence Flight Deck

Core read-only diagnostic surface: `/admin/operational-convergence`.
It uses the existing admin and Developer Mode gates. Customer and anonymous
sessions cannot read the feed. GET only; no training, provider, registry or
governance actions. Cognitive Gym remains the secondary `/admin/cognitive-gym`
surface and first-party plugin candidate. No plugin reorganization occurs.

The loader consumes the proven operational projection directly when the local
evaluator is available. On production it reads `instance/convergence/frontier.json`,
published manually with the existing exporter `--frontier` option. It verifies
schema and canonical integrity before displaying data. Missing, malformed,
ineligible or corrupt data produces an unavailable view and HTTP 503, not healthy
gauges. Page caching is private/no-store. Raw outputs are restricted to the same
authorized roles that can already inspect them in Cognitive Gym.

The top section distinguishes application activity, explicit stable handoffs,
GO developmental observations and accepted shared operations. The recorded gap
and target come from the retained frontier narrative, never a UI constant. Multiple
unrankable frontier narratives remain unresolved. The categorical matrix contains
no numeric readiness or intelligence axis. Badge state is distinct from component
position; stable does not imply trainable. The critical path is navigation among
mapped operations, not an assertion that the full workflow is implemented.

Each operation exposes the six application facets, positive and negative controls,
model/contract/instrument observations, application defects, source hashes, exact
responses and historical state transitions. Product Owner questions stay unresolved.
No rendered evidence image is inferred from region coordinates. When this projection
contains no thumbnails, the inspector says so. Stopped/GOtex history remains separately
available in the Gym; it is never pooled into operational GO readiness.

Desktop shows a categorical matrix and compact operation inspectors. Phone layout
shows the focus first, stacks summary cards and nonempty matrix groups, and opens
the inspector through ordinary hash navigation. All navigation and expansion is
read-only. Native details remain usable without JavaScript.

Publication must preserve its export receipt and source timestamp/hash. Refreshing
the page cannot refresh a manually published snapshot. Deployment changes static
version only through the established deployment workflow and must preserve all
persistent instance data and retained drawing assets.
