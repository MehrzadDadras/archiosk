"""Focused contract for the approved New Project operational surface."""
from __future__ import annotations

from werkzeug.security import generate_password_hash


def _page():
    import app as app_module
    from models import User, db

    application = app_module.create_app("testing")
    with application.app_context():
        db.session.add(User(username="new_project_ui", password_hash=generate_password_hash("x"), role="admin"))
        db.session.commit()
    client = application.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username="new_project_ui", role="admin")
    return client.get("/upload").get_data(as_text=True)


def test_visible_order_and_minimal_labels():
    body = _page()
    labels = ["New Project", "Your name", "Your role", "Your project position",
              "Project name", "Acronym", "Upload Project Folder", "Upload File", "Composer"]
    positions = [body.index(label) for label in labels]
    assert positions == sorted(positions)
    for label in ("Client", "Lead Design Consultant", "Subconsultant", "Design-Builder / GC", "Subcontractor"):
        assert label in body
    for removed in ("Establish a Project", "Choose how this Project's documents connect",
                    "Accepted formats:", "Ask Archiosk about this form",
                    "Show GO the document I selected below", "e.g. what does"):
        assert removed not in body


def test_composer_is_last_open_surface_and_has_no_fake_suggestions():
    body = _page()
    assert body.index("Upload File") < body.index("<h2>Composer</h2>")
    assert '<section class="upload-composer"' in body
    composer = body[body.index('<section class="upload-composer"'):body.index('</section>', body.index('<section class="upload-composer"'))]
    assert '<details' not in composer
    assert "upload-help-candidate-toggle" not in body
    assert "suggestion" not in composer.lower()


def test_folder_buttons_keep_distinct_domains():
    body = _page()
    expected = {
        "Connect Client Data Room": "CLIENT_ISSUED",
        "Connect Your Workspace": "TEAM_WORKSPACE",
        "Add External References": "EXTERNAL_REFERENCE",
    }
    for label, domain in expected.items():
        start = body.index(label)
        tag = body[body.rfind("<button", 0, start):body.index(">", start) + 1]
        assert f'data-source-domain="{domain}"' in tag
