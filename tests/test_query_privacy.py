"""Synthetic regression coverage for credentials reaching query stdout."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from local_fixtures import add_message, database

from decrypt.local_io import connect_readonly
from decrypt.local_query import MessageStore, parse_window, print_messages
from decrypt.redaction import REDACTED, redact_text
from decrypt.transcript_export import export_all, export_chat


class QueryPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, _ = database(self.root / "Messages1")
        self.key = "zz-EXAMPLE-0123456789abcdefghij"
        self.password = "EXAMPLE-DB-PASS-0000"
        self.content = f"调用信息\napi_key：{self.key}\njdbc:demo://host/db?user=example&password={self.password}&mode=readonly\n新增筛选项"
        add_message(self.path, 10, 0, self.content)
        add_message(self.path, 11, 0, "新增筛选项，但属于其他会话", conv=102)
        self.conn = connect_readonly(self.path)
        self.addCleanup(self.conn.close)
        self.store = MessageStore(self.conn, users={11: "测试发送人"})

    def test_query_masks_known_credentials_before_json_and_text_outputs(self):
        for result in (self.store.read_chat("101"), self.store.search("调用信息", conversation="101")):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                print_messages(result)
            for rendered in (json.dumps(result, ensure_ascii=False), output.getvalue()):
                self.assertNotIn(self.key, rendered)
                self.assertNotIn(self.password, rendered)
                self.assertIn("新增筛选项", rendered)
                self.assertIn(REDACTED, rendered)
            row = next(m for m in result["messages"] if m["local_id"] == 10)
            self.assertEqual(row["sender"], "测试发送人")
            self.assertEqual(row["conv_id"], "101")
            self.assertTrue(row["time"] and row["server_id"] and row["content_redacted"])

    def test_cli_search_respects_scope_and_masks_both_output_formats(self):
        script = Path(__file__).resolve().parents[1] / "decrypt/macos/wecom_local.py"
        env = dict(os.environ, WECOM_DECRYPTED_DIR=str(self.root), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        for flags in ([], ["--json"]):
            result = subprocess.run([sys.executable, str(script), "search", "筛选项", "--conversation", "101", *flags],
                                    env=env, capture_output=True, text=True, encoding="utf-8", check=True)
            self.assertNotIn(self.key, result.stdout)
            self.assertNotIn(self.password, result.stdout)
            self.assertNotIn("但属于其他会话", result.stdout)
            self.assertIn("新增筛选项", result.stdout)
        options = parse_window(["筛选项", "--conversation", "101"], positional="keyword")
        self.assertEqual(self.store.search(options.keyword, conversation=options.conversation)["total"], 1)

    def test_empty_conversation_filter_cannot_silently_become_global(self):
        for conversation in ("", " "):
            with self.assertRaises(ValueError):
                self.store.search("筛选项", conversation=conversation)

    def test_explicit_exports_keep_original_text_and_queries_do_not_change_database(self):
        self.store.read_chat("101")
        out = self.root / "raw.json"
        export_chat(self.store, self.path, "101", out)
        rows = json.loads(out.read_text())
        raw = next(row for row in rows if row["local_id"] == 10)
        self.assertEqual(raw["content"], self.content)
        self.assertNotIn("content_redacted", raw)
        export_all(self.store, self.root / "bulk")
        rows = json.loads((self.root / "bulk/messages.json").read_text())
        self.assertEqual(next(row["content"] for row in rows if row["local_id"] == 10), self.content)
        self.assertEqual(self.conn.execute("SELECT content FROM MESSAGE WHERE LID=10").fetchone()[0], self.content)

    def test_mcp_search_uses_same_scope_and_redacted_query_results(self):
        import server

        def search(args, js=False):
            options = parse_window(args, positional="keyword")
            return self.store.search(options.keyword, limit=options.limit, offset=options.offset,
                                     days=options.days, conversation=options.conversation)

        local = SimpleNamespace(CMDS={"search": search})
        with patch.object(server, "_PLAT", "macos"), patch.object(server, "_local_module", return_value=local):
            result = json.loads(server.wecom_search("筛选项", conversation="101"))
        self.assertEqual(result["total"], 1)
        self.assertNotIn(self.key, json.dumps(result))
        self.assertNotIn(self.password, json.dumps(result))

    def test_missing_or_id_only_conversation_name_uses_exact_user_identity(self):
        for conversations in ({}, {101: "101"}, {101: " "}):
            store = MessageStore(self.conn, users={101: "对端姓名"}, conversations=conversations)
            target = store.target("101")
            self.assertEqual(target["name"], "对端姓名")
            self.assertEqual(store.read_chat("对端姓名")["conversation"]["id"], "101")
            self.assertTrue(all(m["conversation"] == "对端姓名" for m in store.read_chat("101")["messages"]))
        named = MessageStore(self.conn, users={101: "用户"}, conversations={101: "已有群名"})
        self.assertEqual(named.target("101")["name"], "已有群名")
        unknown = MessageStore(self.conn, users={11: "最后发言人"}, conversations={})
        self.assertEqual(unknown.target("101")["name"], "101")

    def test_windows_query_uses_shared_redaction_and_scope(self):
        path, _ = database(self.root / "windows", windows=True)
        add_message(path, 10, 0, self.content)
        with contextlib.closing(connect_readonly(path)) as conn:
            store = MessageStore(conn, platform="windows", conversations={"101": "项目"})
            data = store.search("调用信息", conversation="101")
        self.assertEqual(data["total"], 1)
        self.assertNotIn(self.key, json.dumps(data))
        self.assertNotIn(self.password, json.dumps(data))

    def test_common_credential_forms_and_ordinary_requirement_text(self):
        examples = [
            'api_key: "EXAMPLE secret with spaces"',
            r'{"OPENAI_API_KEY":"EXAMPLE\"escaped-value"}',
            "密码：EXAMPLE-PASS；请增加筛选项",
            "postgresql://user:EXAMPLE-PASS@localhost/db",
            "Authorization: Bearer EXAMPLE-BEARER-0000",
            "sk-EXAMPLE-NOT-A-REAL-CREDENTIAL-0000",
            "-----BEGIN PRIVATE KEY-----\nEXAMPLE-KEY-DATA\n-----END PRIVATE KEY-----",
        ]
        for example in examples:
            with self.subTest(example=example):
                redacted = redact_text(example)
                self.assertIn(REDACTED, redacted)
                self.assertNotIn("EXAMPLE", redacted)
        ordinary = 'API Key 写入后不可回读；max_tokens=100；api_key=""\n保留换行与原话'
        self.assertEqual(redact_text(ordinary), ordinary)


if __name__ == "__main__":
    unittest.main()
