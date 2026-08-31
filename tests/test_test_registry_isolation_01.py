"""
CLAUDE-TEST-REGISTRY-ISOLATION-01 - the session reset cleans the test stores
and structurally cannot touch the real ones.

tests/conftest.py deletes directories. The whole risk of that file is one
character in a path putting `instance/registry` - real development data, not
recoverable from git - inside the blast radius. So the guard is asserted here
against the actual configured paths rather than trusted by reading.

The accumulation bug itself is asserted the only way it usefully can be: that
TestingConfig's stores are the ones being reset, and that a session start
actually empties them.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from config import BASE_DIR, BaseConfig, TestingConfig

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFTEST = _REPO_ROOT / "tests" / "conftest.py"


def _load_conftest():
    spec = importlib.util.spec_from_file_location("_archiosk_conftest", _CONFTEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheGuardRefusesTheRealStoresTests(unittest.TestCase):
    """The assertions that make conftest.py's rmtree safe to have written."""

    def setUp(self):
        self.conftest = _load_conftest()

    def test_the_real_development_registry_is_refused(self):
        # instance/registry holds actual dev Projects. It fails the `test_`
        # prefix, which is the whole point of the prefix.
        self.assertFalse(
            self.conftest._is_disposable_store(Path(BaseConfig.REGISTRY_STORE_PATH))
        )

    def test_the_real_project_assets_directory_is_refused(self):
        self.assertFalse(
            self.conftest._is_disposable_store(Path(BaseConfig.PROJECT_ASSET_PATH))
        )

    def test_the_instance_directory_itself_is_refused(self):
        # A path bug that resolved to the parent would take the database with it.
        self.assertFalse(self.conftest._is_disposable_store(BASE_DIR / "instance"))

    def test_the_repository_root_is_refused(self):
        self.assertFalse(self.conftest._is_disposable_store(BASE_DIR))

    def test_a_test_named_directory_outside_instance_is_refused(self):
        # The `test_` prefix alone is not sufficient - the parent must match too.
        self.assertFalse(self.conftest._is_disposable_store(BASE_DIR / "test_registry"))

    def test_the_configured_test_stores_are_accepted(self):
        for path in self.conftest.TEST_STORE_PATHS:
            self.assertTrue(self.conftest._is_disposable_store(path), path)

    def test_a_path_failing_the_guard_raises_rather_than_being_skipped(self):
        # A silent skip would restore the accumulation with nothing saying so.
        original = self.conftest.TEST_STORE_PATHS
        self.conftest.TEST_STORE_PATHS = (Path(BaseConfig.REGISTRY_STORE_PATH),)
        try:
            with self.assertRaises(RuntimeError):
                self.conftest._reset_test_stores()
        finally:
            self.conftest.TEST_STORE_PATHS = original


class TheResetTargetsTheStoresThatActuallyAccumulateTests(unittest.TestCase):
    """It must follow TestingConfig, not a restated literal."""

    def setUp(self):
        self.conftest = _load_conftest()

    def test_it_resets_exactly_the_testing_config_stores(self):
        configured = {
            Path(TestingConfig.REGISTRY_STORE_PATH).resolve(),
            Path(TestingConfig.PROJECT_ASSET_PATH).resolve(),
        }
        reset = {p.resolve() for p in self.conftest.TEST_STORE_PATHS}
        self.assertEqual(reset, configured)

    def test_the_test_stores_are_not_the_real_stores(self):
        # If TestingConfig ever inherited BaseConfig's paths again, the reset
        # would be aimed at real data and the guard would start raising - this
        # says so directly instead of leaving it to be discovered that way.
        self.assertNotEqual(
            Path(TestingConfig.REGISTRY_STORE_PATH).resolve(),
            Path(BaseConfig.REGISTRY_STORE_PATH).resolve(),
        )
        self.assertNotEqual(
            Path(TestingConfig.PROJECT_ASSET_PATH).resolve(),
            Path(BaseConfig.PROJECT_ASSET_PATH).resolve(),
        )


class TheResetActuallyEmptiesTheStoreTests(unittest.TestCase):
    """Behaviour, not just configuration."""

    def setUp(self):
        self.conftest = _load_conftest()

    def test_it_removes_a_populated_test_store(self):
        store = Path(TestingConfig.REGISTRY_STORE_PATH)
        store.mkdir(parents=True, exist_ok=True)
        marker = store / "conftest_reset_probe.json"
        marker.write_text("{}", encoding="utf-8")
        self.assertTrue(marker.exists())

        self.conftest._reset_test_stores()

        self.assertFalse(marker.exists())
        self.assertFalse(store.exists())

    def test_it_is_a_no_op_when_the_store_is_already_absent(self):
        # A fresh clone has no instance/test_registry at all; the first run
        # must not fail on that.
        for path in self.conftest.TEST_STORE_PATHS:
            if path.exists():
                self.conftest._reset_test_stores()
        self.assertEqual(self.conftest._reset_test_stores(), [])


class TheEscapeHatchIsRealTests(unittest.TestCase):
    """Preserving a failed run's artifacts has to be possible."""

    def setUp(self):
        self.conftest = _load_conftest()

    def test_the_opt_out_variable_is_named_and_honoured(self):
        self.assertEqual(self.conftest.KEEP_ENV_VAR, "ARCHIOSK_KEEP_TEST_REGISTRY")
        source = _CONFTEST.read_text(encoding="utf-8")
        hook = source.split("def pytest_sessionstart")[1]
        self.assertIn("KEEP_ENV_VAR", hook)
        self.assertIn("return", hook.split("KEEP_ENV_VAR")[1][:120])


if __name__ == "__main__":
    unittest.main()
