"""
CLAUDE-CA1D-COMPOSER-SPINE-01 - the Composer's real conversational
orchestration: bounded multi-turn history (Stage 0, this file's first
addition) and, in later stages of the same tranche, the Context
Envelope and the closed intent_class dispatch table that let the
Composer genuinely understand a turn rather than only pattern-match it
(see services/conversation_interpreter.py's own module docstring on
why THAT file stays deterministic keyword matching for the fast path,
and this file's own governance record, once written, for the
architecture this module implements).

Stage 0 responsibility only, for now: `build_bounded_history`, promoted
verbatim from services/project_qa.py's own `_select_bounded_history` (the
only precedent for turn-windowing this app had) so every conversational
turn - not only a project-question turn - windows its history the same
one way, rather than each new call site inventing its own copy.
"""
from __future__ import annotations

# CLAUDE-POSTCAMEL-CA1A (Section 5, token-aware continuity, originally
# services/project_qa.py): a fixed message-count cap alone lets one long
# single message consume the whole window - this instead bounds total
# transmitted continuity by size, not by count, while still capping the
# message COUNT too so a long run of very short messages can't produce
# an unbounded list. No tokenizer dependency - a deterministic character
# budget, per that stage's own "approximate character/token budget
# rather than a large dependency" instruction.
_RECENT_HISTORY_CHAR_BUDGET = 2000
_MAX_RECENT_HISTORY_MESSAGES = 20
_MAX_HISTORY_MESSAGE_CHARS = 300


def build_bounded_history(
    recent_history: list[dict],
    char_budget: int = _RECENT_HISTORY_CHAR_BUDGET,
    max_messages: int = _MAX_RECENT_HISTORY_MESSAGES,
    max_message_chars: int = _MAX_HISTORY_MESSAGE_CHARS,
) -> list[dict]:
    """
    Walk backwards from the most recent message, keeping whole messages
    (never truncating a message mid-sentence just to hit the budget
    exactly) until either the character budget or the message-count cap
    is reached, then restore chronological order. Recent turns are
    always favored - the OLDEST messages are the ones dropped first when
    the budget is exceeded. Callers pass raw {"role", "text"} dicts (the
    same shape services/case_workspace.py's ConversationMessage already
    exposes) - this function has no model/persistence knowledge of its
    own.
    """
    selected: list[dict] = []
    total_chars = 0
    for message in reversed(recent_history):
        text = (message.get("text") or "").strip()[:max_message_chars]
        if not text:
            continue
        if selected and (
            total_chars + len(text) > char_budget
            or len(selected) >= max_messages
        ):
            break
        selected.append({"role": message.get("role"), "text": text})
        total_chars += len(text)
    selected.reverse()
    return selected
