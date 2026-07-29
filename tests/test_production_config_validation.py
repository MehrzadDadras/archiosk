"""
CLAUDE-P27-B: config.py's BaseConfig.validate() existed but was never
called anywhere -- a misconfigured "production" deploy (e.g.
FLASK_SECRET_KEY unset) previously booted and served traffic with
broken session integrity. app.py's _validate_production_config wires
the parts of it that must hard-fail (FLASK_SECRET_KEY, and DEBUG/
TESTING somehow true under ProductionConfig) into actual boot
behavior, while preserving the deliberate graceful degradation for a
missing ANTHROPIC_API_KEY (see tools/dependency_fit.py, README's
"Without an Anthropic API key" section) -- that one only warns.

Every test here patches SQLALCHEMY_DATABASE_URI to an in-memory
sqlite before calling create_app("production")/("development"), since
those two configs otherwise resolve to the real instance/bhive.db --
must never let this test suite touch that file.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import config


class ProductionConfigValidationTests(unittest.TestCase):
    def test_missing_secret_key_refuses_to_boot_under_production(self):
        import app as app_module

        with patch.object(config.ProductionConfig, "SECRET_KEY", ""), \
             patch.object(config.ProductionConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            with self.assertRaises(RuntimeError):
                app_module.create_app("production")

    def test_missing_anthropic_key_boots_with_warning_not_failure(self):
        import app as app_module

        with patch.object(config.ProductionConfig, "SECRET_KEY", "a-real-secret"), \
             patch.object(config.ProductionConfig, "ANTHROPIC_API_KEY", ""), \
             patch.object(config.ProductionConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            app = app_module.create_app("production")
        self.assertIsNotNone(app)

    def test_debug_true_under_production_refuses_to_boot(self):
        import app as app_module

        with patch.object(config.ProductionConfig, "SECRET_KEY", "a-real-secret"), \
             patch.object(config.ProductionConfig, "DEBUG", True), \
             patch.object(config.ProductionConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            with self.assertRaises(RuntimeError):
                app_module.create_app("production")

    def test_testing_true_under_production_refuses_to_boot(self):
        import app as app_module

        with patch.object(config.ProductionConfig, "SECRET_KEY", "a-real-secret"), \
             patch.object(config.ProductionConfig, "TESTING", True), \
             patch.object(config.ProductionConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            with self.assertRaises(RuntimeError):
                app_module.create_app("production")

    def test_development_config_is_unaffected_by_missing_secret_key(self):
        import app as app_module

        with patch.object(config.DevelopmentConfig, "SECRET_KEY", ""), \
             patch.object(config.DevelopmentConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            app = app_module.create_app("development")
        self.assertIsNotNone(app)

    def test_testing_config_is_unaffected_by_missing_secret_key(self):
        import app as app_module

        with patch.object(config.TestingConfig, "SECRET_KEY", ""):
            # TestingConfig already uses sqlite:///:memory: unconditionally.
            app = app_module.create_app("testing")
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
