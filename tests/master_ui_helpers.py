"""MASTERUI cutover: shared helpers for tests that used to read the retired
classic shell (the menu bar, customer top bar, Account menu).

- `master_command(body, id)` reads one rendered Master command's state and
  inner markup, so a test can assert "active with this route" or "grey with no
  route" (law 8: role greys, never removes).
- `expand_partials(text)` inlines `{% include "partials/_menu_*.html" %}` so a
  static check over a template reads exactly the markup it read before the
  working controls moved VERBATIM into partials - the protection is unchanged.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PARTIALS_DIR = REPO_ROOT / "templates" / "partials"


def master_command(body, command_id):
    """(state, inner_html) of one rendered Master command, or (None, None)."""
    m = re.search(r'<li class="master-item is-(active|grey|current)" data-command="%s">(.*?)</li>'
                  % re.escape(command_id), body, re.S)
    return (m.group(1), m.group(2)) if m else (None, None)


def expand_partials(text):
    return re.sub(r'\{% include "partials/(_menu_[a-z_]+\.html)" %\}',
                  lambda m: (PARTIALS_DIR / m.group(1)).read_text(encoding="utf-8"), text)


def read_expanded(path):
    return expand_partials(Path(path).read_text(encoding="utf-8"))
