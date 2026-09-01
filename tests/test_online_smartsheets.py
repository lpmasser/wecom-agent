import importlib
import importlib.util
import unittest


def load_module(name):
    if importlib.util.find_spec(name) is None:
        raise AssertionError(f"{name} module should exist")
    return importlib.import_module(name)


class FakeRunner:
    def __init__(self, result=None):
        self.calls = []
        self.result = result if result is not None else {"errcode": 0}

    def __call__(self, args, payload=None):
        self.calls.append((list(args), payload))
        return self.result


class OnlineSmartSheetsTests(unittest.TestCase):
    def test_get_fields_is_read_only(self):
        smartsheets = load_module("online.smartsheets")
        runner = FakeRunner({"fields": []})

        result = smartsheets.get_fields(docid="DOCID", sheet_id="SHEETID", runner=runner)

        self.assertEqual(result, {"fields": []})
        self.assertEqual(
            runner.calls,
            [(["doc", "smartsheet_get_fields"], {"docid": "DOCID", "sheet_id": "SHEETID"})],
        )

    def test_add_records_requires_confirmation_and_preserves_records(self):
        smartsheets = load_module("online.smartsheets")
        records = [{"values": {"标题": [{"type": "text", "text": "Task"}], "工时": 2}}]

        with self.assertRaises(PermissionError):
            smartsheets.add_records(docid="DOCID", sheet_id="SHEETID", records=records, runner=FakeRunner())

        runner = FakeRunner()
        smartsheets.add_records(
            docid="DOCID",
            sheet_id="SHEETID",
            records=records,
            confirmed=True,
            runner=runner,
        )
        self.assertEqual(
            runner.calls,
            [
                (
                    ["doc", "smartsheet_add_records"],
                    {"docid": "DOCID", "sheet_id": "SHEETID", "records": records},
                )
            ],
        )

    def test_current_cli_routes_sheet_and_field_operations(self):
        smartsheets = load_module("online.smartsheets")
        runner = FakeRunner()

        smartsheets.create_smartsheet(
            "Localization Tracker",
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.get_sheets(docid="DOCID", runner=runner, cli_version="1.2.0")
        smartsheets.add_sheet(
            docid="DOCID",
            title="Backlog",
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.update_sheet(
            docid="DOCID",
            sheet_id="SHEETID",
            title="Ready",
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.delete_sheet(
            docid="DOCID",
            sheet_id="SHEETID",
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.get_fields(
            docid="DOCID",
            sheet_id="SHEETID",
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.add_fields(
            docid="DOCID",
            sheet_id="SHEETID",
            fields=[{"field_title": "Status", "field_type": "text"}],
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.update_fields(
            docid="DOCID",
            sheet_id="SHEETID",
            fields=[{"field_id": "FIELDID", "new_field_title": "Workflow Status"}],
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.delete_fields(
            docid="DOCID",
            sheet_id="SHEETID",
            field_ids=["FIELDID"],
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )

        self.assertEqual(
            runner.calls,
            [
                (["smartsheet", "create"], {"name": "Localization Tracker"}),
                (["smartsheet", "sheets", "list"], {"docid": "DOCID"}),
                (
                    ["smartsheet", "sheets", "add"],
                    {"docid": "DOCID", "sheet_title": "Backlog"},
                ),
                (
                    ["smartsheet", "sheets", "update"],
                    {"docid": "DOCID", "sheet_id": "SHEETID", "new_sheet_title": "Ready"},
                ),
                (
                    ["smartsheet", "sheets", "delete"],
                    {"docid": "DOCID", "sheet_id": "SHEETID"},
                ),
                (
                    ["smartsheet", "fields", "list"],
                    {"docid": "DOCID", "sheet_id": "SHEETID"},
                ),
                (
                    ["smartsheet", "fields", "add"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "fields": [{"field_title": "Status", "field_type": "text"}],
                    },
                ),
                (
                    ["smartsheet", "fields", "update"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "fields": [{"field_id": "FIELDID", "new_field_title": "Workflow Status"}],
                    },
                ),
                (
                    ["smartsheet", "fields", "delete"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "fields": [{"field_id": "FIELDID"}],
                    },
                ),
            ],
        )

    def test_current_cli_reads_and_mutates_records_with_new_payloads(self):
        smartsheets = load_module("online.smartsheets")
        runner = FakeRunner()

        smartsheets.get_records(
            docid="DOCID",
            sheet_id="SHEETID",
            limit=50,
            start=10,
            key_type="FIELD_TITLE",
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.add_records(
            docid="DOCID",
            sheet_id="SHEETID",
            records=[{"values": {"Status": "Ready"}}],
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.update_records(
            docid="DOCID",
            sheet_id="SHEETID",
            records=[{"record_id": "RECORDID", "values": {"Status": "Done"}}],
            key_type="FIELD_TITLE",
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )
        smartsheets.delete_records(
            docid="DOCID",
            sheet_id="SHEETID",
            record_ids=["RECORDID"],
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )

        self.assertEqual(
            runner.calls,
            [
                (
                    ["smartsheet", "records", "list"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "limit": 50,
                        "start": 10,
                        "key_type": "field_title",
                    },
                ),
                (
                    ["smartsheet", "records", "add"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "records": [{"values": {"Status": "Ready"}}],
                    },
                ),
                (
                    ["smartsheet", "records", "update"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "records": [{"record_id": "RECORDID", "values": {"Status": "Done"}}],
                        "key_type": "field_title",
                    },
                ),
                (
                    ["smartsheet", "records", "delete"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "records": [{"record_id": "RECORDID"}],
                    },
                ),
            ],
        )

    def test_current_cli_rejects_legacy_auto_file_extension(self):
        smartsheets = load_module("online.smartsheets")
        runner = FakeRunner()

        with self.assertRaisesRegex(RuntimeError, "auto_file"):
            smartsheets.add_records(
                docid="DOCID",
                sheet_id="SHEETID",
                records=[{"values": {"Status": "Ready"}}],
                confirmed=True,
                auto_file=True,
                runner=runner,
                cli_version="1.2.0",
            )
        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
