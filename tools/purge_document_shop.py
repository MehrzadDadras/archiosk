"""Scheduled disposal of expired Document Shop Trash through the workspace owner."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from services.case_workspace import CaseWorkspaceStore

if __name__ == '__main__':
    app = create_app('production')
    with app.app_context():
        print(json.dumps({'purged': CaseWorkspaceStore(app.config['REGISTRY_STORE_PATH']).purge_document_shop_trash()}))
