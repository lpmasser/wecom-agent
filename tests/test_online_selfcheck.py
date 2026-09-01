import unittest
from unittest import mock

from online import selfcheck


class OnlineSelfcheckTests(unittest.TestCase):
    def test_current_cli_reports_migrated_wrappers(self):
        with (
            mock.patch.object(selfcheck.wecom_cli, "version", return_value="wecom-cli 1.2.0"),
            mock.patch.object(selfcheck.wecom_cli, "auth_status", return_value="authorized"),
            mock.patch.object(selfcheck.wecom_cli, "service_available", return_value=True),
        ):
            report = selfcheck.collect()

        self.assertEqual(report["generation"], "current")
        self.assertFalse(report["upgrade_recommended"])
        self.assertEqual(report["python_wrappers"]["documents"]["read"], "supported")
        self.assertEqual(report["python_wrappers"]["smartsheets"]["read"], "supported")
        self.assertEqual(report["python_wrappers"]["smartpages"]["structured_pages"], "legacy-only")
        self.assertEqual(set(report["services"]), {"doc", "sheet", "smartsheet", "smartpage"})

    def test_legacy_cli_reports_read_gaps(self):
        with (
            mock.patch.object(selfcheck.wecom_cli, "version", return_value="wecom-cli 0.1.9"),
            mock.patch.object(selfcheck.wecom_cli, "auth_status", return_value="authorized"),
            mock.patch.object(selfcheck.wecom_cli, "service_available", return_value=True),
        ):
            report = selfcheck.collect()

        self.assertEqual(report["generation"], "legacy")
        self.assertTrue(report["upgrade_recommended"])
        self.assertEqual(report["python_wrappers"]["sheets"]["read"], "unsupported")
        self.assertEqual(report["services"], {"doc": "available"})

    def test_unknown_version_skips_auth_and_service_probes(self):
        with (
            mock.patch.object(selfcheck.wecom_cli, "version", return_value="development build"),
            mock.patch.object(selfcheck.wecom_cli, "auth_status") as auth,
            mock.patch.object(selfcheck.wecom_cli, "service_available") as service,
        ):
            report = selfcheck.collect()

        self.assertEqual(report["generation"], "unknown")
        self.assertEqual(report["auth_status"], "not_checked")
        self.assertEqual(report["services"], {})
        auth.assert_not_called()
        service.assert_not_called()


if __name__ == "__main__":
    unittest.main()
