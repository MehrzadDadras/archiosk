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
    labels = ["New Project", "Your name", "Your role", "Company identity",
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
    assert body.index("Upload File") < body.index(">Composer</h2>")
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


def test_cleanup_keeps_required_position_and_minimal_upload_controls():
    body = _page()
    assert 'type="radio" name="entry_choice"' in body
    assert 'type="checkbox" required aria-label="Confirm project position"' not in body
    assert 'id="single-file-source-domain"' not in body
    assert '<input type="hidden" name="source_domain" value="UNKNOWN">' in body
    assert "Create project and parse document" not in body
    assert ">Upload Files</button>" in body
    assert "Connect Selected Folder" not in body
    # The submit says Upload Folder, matching its fieldset's own legend; the
    # three source-domain buttons above keep Connect/Add because they open a
    # picker rather than perform the upload.
    assert ">Upload Folder</button>" in body
    assert ">Connect Folder</button>" not in body
    assert 'id="folder-domain-summary"' in body


def test_identity_and_project_identity_are_framed_sections():
    body = _page()
    assert "<legend>Your identity</legend>" in body
    assert "<legend>Project identity</legend>" in body
    # Grouping only: the fields themselves are unchanged and still posted.
    identity = body[body.index('data-ui-ref="upload.identity"'):body.index('data-ui-ref="upload.entry-choice')]
    assert 'name="actor"' in identity and 'name="role"' in identity
    project_identity = body.index('data-ui-ref="upload.project-identity"')
    assert body.index("Company identity") < project_identity
    assert body.index('name="project_name"') > project_identity


def test_page_title_is_plain_and_standalone_not_a_hero():
    body = _page()
    assert 'class="np-page-title"' in body
    assert '<section class="hero new-project-hero">' not in body
    # No rule, border or divider attached to the title - the five bordered
    # section frames below carry the page's structure.
    assert 'np-rule' not in body
    title = body[body.index('class="np-page-title"'):]
    assert '</h1>' in title[:200]
    assert '<span' not in title[:title.index('</h1>')]


def test_upload_file_stages_multiple_files_without_a_domain_selector():
    body = _page()
    fieldset = body[body.index('class="single-file-establish-fieldset"'):]
    fieldset = fieldset[:fieldset.index("</fieldset>")]
    assert "multiple" in fieldset
    assert ">Choose File</button>" in fieldset
    assert 'id="upload-file-rows"' in fieldset
    # Action 9: no visible Source Domain dropdown, UNKNOWN fallback preserved.
    assert '<input type="hidden" name="source_domain" value="UNKNOWN">' in fieldset
    assert "<select" not in fieldset


def _help_page():
    import app as app_module
    from models import User, db

    application = app_module.create_app("testing")
    with application.app_context():
        db.session.add(User(username="np_help", password_hash=generate_password_hash("x"), role="admin"))
        db.session.commit()
    client = application.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username="np_help", role="admin")
    return client.get("/help/new-project").get_data(as_text=True)


def test_help_carries_the_explanations_the_working_screen_dropped():
    help_body = _help_page()
    # Each of these was removed from, or never stated on, the working screen.
    for topic in ("Choosing more than one file", "first file in the list establishes the project",
                  "Project name already exists.", "How the page is arranged",
                  "Your identity", "Project identity",
                  "Why there is no attachment control here"):
        assert topic in help_body, topic
    # And the roles / source-domain / folder guidance it already held is intact.
    for kept in ("Client Data Room", "TEAM_WORKSPACE", "EXTERNAL_REFERENCE",
                 "Upload Project Folder", "3 or 4 letters"):
        assert kept in help_body, kept


def test_help_does_not_contradict_the_working_screen():
    help_body = _help_page()
    # The page no longer presents a one-file-only control, so Help must not
    # describe one. "A single upload accepts" was the superseded wording.
    assert "A single upload accepts" not in help_body
    assert "Upload File accepts" in help_body
