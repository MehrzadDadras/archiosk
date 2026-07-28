"""
CLAUDE-P13R self-test laboratory: Golden Corpus -> Controlled Mutation ->
Blind Archiosk Run -> Hidden Answer-Key Evaluation.

This is genuinely separate from the existing NREOCRC lab
(tests/fixtures/nreocrc/) - that lineage audits FAITHFULNESS: does
Archiosk's extraction of a real, complex synthetic document correctly
represent what the document actually says, judged by an independent
prose review written AFTER the run. This package tests DETECTION
CAPABILITY instead: does Archiosk catch a specific, deliberately-planted
defect with a correct answer written BEFORE the run - a blind exam, not
an audit.

Module boundaries are deliberate, not decorative - see mutation_schema.py,
golden_corpus.py, mutations.py, and evaluator.py's own docstrings for
which one is allowed to know what. The investigator (services/
bhive_parser.py's real consistency-check, called from tools/
self_test_lab.py, never from here) only ever receives requirement id/
category/text - never a PlantedMutation, never this package's own
imports - so it structurally cannot "remember the exam answers."
"""
