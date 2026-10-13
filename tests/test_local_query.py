import contextlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from local_fixtures import database, pb

from decrypt import export_wxwork as ex
from decrypt.local_io import connect_readonly
from decrypt.local_query import MessageStore, resolve_conversation, validate_window


class LocalQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.long = database(self.root)
        self.conn = connect_readonly(self.path)
        self.addCleanup(self.conn.close)
        self.store = MessageStore(self.conn, users={11: "发送者全名"})

    def test_readonly_and_missing_database_never_create_or_write(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.conn.execute("DELETE FROM MESSAGE")
        missing = self.root / "missing.db"
        with self.assertRaises(sqlite3.OperationalError):
            connect_readonly(missing)
        self.assertFalse(missing.exists())

    def test_search_preserves_entire_body_whitespace_newlines_and_identity(self):
        result = self.store.search("尾部关键字")
        self.assertEqual(result["messages"][0]["content"], self.long)
        self.assertEqual(result["messages"][0]["local_id"], 1)
        self.assertEqual(result["messages"][0]["conv_id"], "101")
        self.assertNotIn("_raw", json.dumps(result))

    def test_protobuf_text_has_no_field_cap_deduplication_or_reordering(self):
        text = pb(*[(1 if i % 2 == 0 else 2, "重复" if i % 3 else f"段{i}") for i in range(20)])
        expected = "\n".join("重复" if i % 3 else f"段{i}" for i in range(20))
        self.assertEqual(ex.decode_text(text), expected)
        self.assertEqual(ex.decode_text(pb((1, "单"))), "单")
        self.assertEqual(ex.decode_text(pb((1, " \n空白\r\n "))), " \n空白\r\n ")

    def test_conversation_pagination_and_ties_are_stable(self):
        first = self.store.conversation_page(1, 0)
        second = self.store.conversation_page(1, 1)
        self.assertEqual(first["total"], 3)
        self.assertEqual(first["next_offset"], 1)
        self.assertNotEqual(first["conversations"][0]["id"], second["conversations"][0]["id"])
        self.assertEqual(self.store.conversation_page(2, 20)["next_offset"], None)
        self.assertEqual(len(self.store.conversation_page()["conversations"]), 3)

    def test_search_pagination_reports_total_and_keeps_only_requested_page(self):
        result = self.store.search("消息", limit=1, offset=1)
        self.assertEqual((result["count"], result["total"], result["next_offset"]), (1, 2, None))
        self.assertEqual(self.store.search("消息", limit=1, offset=20)["messages"], [])

    def test_date_window_and_read_chat_latest_first(self):
        result = self.store.read_chat("101", limit=1, days=7)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["messages"][0]["local_id"], 2)
        self.assertEqual(self.store.read_chat("101", limit=1, offset=1, days=7)["messages"][0]["local_id"], 1)

    def test_duplicate_name_rejected_before_read_or_export(self):
        with self.assertRaisesRegex(ValueError, "102.*103"):
            self.store.read_chat("重名")
        self.assertEqual(self.store.target("102")["id"], "102")
        self.assertEqual(self.store.target("项目")["id"], "101")
        with self.assertRaisesRegex(ValueError, "没找到"):
            self.store.target("不存在")

    def test_invalid_parameters_and_empty_search_fail(self):
        for limit in (0, -1, 2001, True, 1.5, "50"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                validate_window(limit=limit)
        for days in (0, -1, True, 2.5, "7"):
            with self.subTest(days=days), self.assertRaises(ValueError):
                validate_window(days=days)
        for offset in (-1, True, 0.5, "1"):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                validate_window(offset=offset)
        with self.assertRaises(ValueError):
            self.store.search(" ")
        with self.assertRaises(ValueError):
            resolve_conversation("", [])

    def test_windows_schema_uses_the_same_full_text_query_contract(self):
        path, long = database(self.root / "win", windows=True)
        with contextlib.closing(connect_readonly(path)) as conn:
            store = MessageStore(conn, platform="windows", conversations={"101": "项目"})
            result = store.search("尾部关键字", limit=10)
            self.assertEqual(result["messages"][0]["content"], long)
            self.assertEqual(store.conversation_page()["total"], 3)

    def test_macos_cli_can_use_relocated_offline_database_without_live_profile(self):
        env = {**os.environ, "PYTHONUTF8": "0", "WECOM_DECRYPTED_DIR": str(self.root / "dec"), "WECOM_PROFILE": str(self.root / "missing-profile")}
        target = self.root / "dec" / "Messages1"
        target.mkdir(parents=True)
        (target / "Info.db").write_bytes(self.path.read_bytes())
        script = Path(__file__).parents[1] / "decrypt/macos/wecom_local.py"
        result = subprocess.run([sys.executable, str(script), "search", "尾部关键字", "--json", "--limit", "1"],
                                env=env, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["messages"][0]["content"], self.long)
        result = subprocess.run([sys.executable, str(script), "search", "尾部关键字"], env=env, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.long, result.stdout)

    def test_mcp_rejects_invalid_limits_before_local_data_access(self):
        import server
        with patch.object(server, "_local_module") as local:
            for call in (lambda: server.wecom_conversations(0), lambda: server.wecom_search("x", days=0),
                         lambda: server.wecom_read_chat("x", limit=True), lambda: server.wecom_search(" ")):
                self.assertIn("error", json.loads(call()))
            local.assert_not_called()

    def test_mcp_uses_structured_full_text_results(self):
        import server
        local = SimpleNamespace(CMDS={"search": lambda args, js=False: self.store.search(args[-1], limit=1)})
        with patch.object(server, "_PLAT", "macos"), patch.object(server, "_local_module", return_value=local):
            self.assertEqual(json.loads(server.wecom_search("尾部关键字"))["messages"][0]["content"], self.long)

    def test_profile_selection_is_explicit_and_bad_override_never_falls_back(self):
        from decrypt.macos import wecom_paths
        wecom_paths.profile_dir.cache_clear()
        self.addCleanup(wecom_paths.profile_dir.cache_clear)
        with patch.dict(os.environ, {"WECOM_PROFILE": str(self.root / "absent")}), self.assertRaisesRegex(SystemExit, "WECOM_PROFILE"):
            wecom_paths.profile_dir()
        wecom_paths.profile_dir.cache_clear()
        with patch.dict(os.environ, {}, clear=True), patch.object(wecom_paths.glob, "glob", return_value=["one", "two"]), patch.object(wecom_paths.os.path, "isdir", return_value=True), self.assertRaisesRegex(SystemExit, "多个"):
            wecom_paths.profile_dir()

    def test_importing_windows_does_not_mutate_macos_rendering(self):
        before = (dict(ex.MEDIA), dict(ex.TYPE_LABEL))
        with contextlib.redirect_stdout(io.StringIO()):
            import decrypt.windows.wecom_win  # noqa: F401
        self.assertEqual(before, (ex.MEDIA, ex.TYPE_LABEL))
        self.assertEqual(ex.type_name(14), "图片")
        self.assertEqual(ex.type_name(16), "语音")
