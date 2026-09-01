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


class OnlineSheetsTests(unittest.TestCase):
    def test_append_row_converts_python_values_to_sheet_cells(self):
        sheets = load_module("online.sheets")
        runner = FakeRunner()

        sheets.append_row(
            docid="DOCID",
            sheet_id="SHEETID",
            values=["Name", 12, {"type": "link", "text": "Open", "url": "https://example.com"}],
            confirmed=True,
            runner=runner,
        )

        self.assertEqual(
            runner.calls,
            [
                (
                    ["doc", "sheet_append_data"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "row": {
                            "values": [
                                {"data_type": "TEXT", "cell_value": {"text": "Name"}},
                                {"data_type": "NUMBER", "cell_value": {"number": 12}},
                                {
                                    "data_type": "LINK",
                                    "cell_value": {
                                        "link": {"text": "Open", "url": "https://example.com", "overwrite": True}
                                    },
                                },
                            ]
                        },
                    },
                )
            ],
        )

    def test_update_range_uses_zero_based_start_position(self):
        sheets = load_module("online.sheets")
        runner = FakeRunner()

        sheets.update_range(
            url="https://doc",
            sheet_id="SHEETID",
            start_row=0,
            start_column=1,
            rows=[["A", "B"], ["C", "D"]],
            confirmed=True,
            runner=runner,
        )

        self.assertEqual(runner.calls[0][0], ["doc", "sheet_update_range_data"])
        self.assertEqual(runner.calls[0][1]["url"], "https://doc")
        self.assertEqual(runner.calls[0][1]["grid_data"]["start_column"], 1)
        self.assertEqual(len(runner.calls[0][1]["grid_data"]["rows"]), 2)

    def test_current_cli_uses_sheet_service_and_current_formula_enum(self):
        sheets = load_module("online.sheets")
        runner = FakeRunner()

        sheets.append_row(
            url="https://doc.weixin.qq.com/sheet/DOCID?scode=share",
            sheet_id="SHEETID",
            values=[{"type": "formula", "formula": "=SUM(A1:A2)"}],
            confirmed=True,
            runner=runner,
            cli_version="1.2.0",
        )

        self.assertEqual(
            runner.calls,
            [
                (
                    ["sheet", "rows", "append"],
                    {
                        "docid": "DOCID",
                        "sheet_id": "SHEETID",
                        "row": {
                            "values": [
                                {
                                    "data_type": "FORMULA",
                                    "cell_value": {"formula": "=SUM(A1:A2)"},
                                }
                            ]
                        },
                    },
                )
            ],
        )

    def test_legacy_formula_keeps_historical_cli_enum(self):
        sheets = load_module("online.sheets")

        result = sheets.cell_data({"type": "formula", "formula": "=A1"})

        self.assertEqual(result["data_type"], "FORMUAL")

    def test_current_cli_reads_sheet_range(self):
        sheets = load_module("online.sheets")
        runner = FakeRunner({"grid_data": {}})

        result = sheets.get_range(
            docid="DOCID",
            sheet_id="SHEETID",
            cell_range="A1:B10",
            runner=runner,
            cli_version="1.2.0",
        )

        self.assertEqual(result, {"grid_data": {}})
        self.assertEqual(
            runner.calls,
            [
                (
                    ["sheet", "ranges", "get"],
                    {"docid": "DOCID", "sheet_id": "SHEETID", "mode": "default", "range": "A1:B10"},
                )
            ],
        )

    def test_current_cli_maps_standard_sheet_operations(self):
        sheets = load_module("online.sheets")
        runner = FakeRunner()
        common = {"docid": "DOCID", "runner": runner, "cli_version": "1.2.0"}

        sheets.create_sheet("Metrics", confirmed=True, runner=runner, cli_version="1.2.0")
        sheets.get_info(**common)
        sheets.add_subsheet(title="Week 1", confirmed=True, **common)
        sheets.delete_subsheet(sheet_id="SHEETID", confirmed=True, **common)
        sheets.update_range(
            sheet_id="SHEETID",
            rows=[["A"]],
            confirmed=True,
            **common,
        )

        self.assertEqual(
            [call[0] for call in runner.calls],
            [
                ["sheet", "create"],
                ["sheet", "get"],
                ["sheet", "subsheets", "add"],
                ["sheet", "subsheets", "delete"],
                ["sheet", "contents", "update"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
