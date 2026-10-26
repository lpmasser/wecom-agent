import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from local_fixtures import PNG, add_message, database, media_payload

from decrypt.local_io import connect_readonly
from decrypt.local_query import MessageStore
from decrypt.transcript_export import export_all
from decrypt.windows import wecom_win as win


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.long = database(self.root, windows=True)
        for name, statements in {
            "user.db": ["CREATE TABLE user_table(id INTEGER,name TEXT,english_name TEXT,mobile TEXT,email TEXT,position TEXT)",
                        "INSERT INTO user_table VALUES (11,'发送者全名','','','','')"],
            "session.db": ["CREATE TABLE conversation_table(id TEXT,name TEXT)", "CREATE TABLE conversation_user_table(conversation_id TEXT,user_id INTEGER,nick_name TEXT)",
                           "INSERT INTO conversation_table VALUES ('101','项目'),('102','重名'),('103','重名')",
                           "INSERT INTO conversation_user_table VALUES ('101',11,'昵称')"],
            "forever_store.db": ["CREATE TABLE todo_v4(content TEXT,status INTEGER,creator_id INTEGER,from_info_name TEXT,create_time INTEGER)",
                                 "INSERT INTO todo_v4 VALUES ('完整待办',0,11,'',1)"],
            "calendar_r7.db": ["CREATE TABLE calendar_main_table_v2(starttime INTEGER,endtime INTEGER,rawdata BLOB)"]
        }.items():
            with contextlib.closing(sqlite3.connect(self.root / name)) as conn, conn:
                for statement in statements:
                    conn.execute(statement)
        self.cache = self.root / "Cache"
        self.cache.mkdir()
        source = self.cache / "Image" / "2026-10" / ("a" * 32) / "image.png"
        source.parent.mkdir(parents=True)
        source.write_bytes(PNG)
        add_message(self.path, 10, 14, media_payload("a" * 32))

    def decrypt(self, name, key):
        path = self.root / name
        return connect_readonly(path) if path.exists() else None

    def test_windows_all_local_tools_return_structured_results(self):
        commands = [("contacts", []), ("conversations", ["--limit", "1"]), ("members", ["101"]),
                    ("search", ["尾部关键字"]), ("chat", ["101"]), ("stats", []), ("todo", []),
                    ("calendar", []), ("media", ["--out", str(self.root / "media")]), ("openfile", ["missing"]),
                    ("export", ["101", "--out", str(self.root / "chat.html"), "--with-media"])]
        with patch.object(win, "decrypt_db", side_effect=self.decrypt), patch.object(win, "DEC", str(self.root)), patch.dict(os.environ, {"WECOM_CACHE_DIR": str(self.cache)}):
            for command, args in commands:
                with self.subTest(command=command):
                    result = win.CMDS[command](b"synthetic-key", args, js=True)
                    self.assertIsInstance(result, dict)
                    self.assertNotIn("_raw", json.dumps(result))
            self.assertEqual(win.cmd_search(b"key", ["尾部关键字"], js=True)["messages"][0]["content"], self.long)
        self.assertTrue(list(self.root.glob("chat.assets-*")))

    def test_windows_mcp_search_uses_json_and_preserves_full_body(self):
        import server
        with patch.object(win, "decrypt_db", side_effect=self.decrypt), patch.object(server, "_PLAT", "windows"), patch.object(server, "_local_module", return_value=win), patch.object(server, "_win_key", return_value=b"key"):
            result = json.loads(server.wecom_search("尾部关键字"))
            literal = json.loads(server.wecom_search("--limit"))
        self.assertEqual(result["messages"][0]["content"], self.long)
        self.assertEqual(literal["keyword"], "--limit")

    def test_windows_decryption_includes_real_wal_through_shared_read(self):
        with contextlib.closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("INSERT INTO message_table VALUES (20,2000,'101',11,0,1,'WAL消息')")
            conn.commit()
            shared = win.read_shared if os.name == "nt" else lambda path: Path(path).read_bytes()
            with patch.object(win, "DEC", str(self.root / "dec")), patch.dict(os.environ, {"WECOM_DATA_DIR": str(self.root)}), patch.object(win, "read_shared", side_effect=shared), contextlib.closing(win.decrypt_db("message.db", b"key")) as snapshot:
                self.assertEqual(snapshot.execute("SELECT content FROM message_table WHERE message_id=20").fetchone()[0], "WAL消息")

    def test_bulk_exports_stream_complete_json_csv_with_stable_ids(self):
        with contextlib.closing(connect_readonly(self.path)) as conn:
            result = export_all(MessageStore(conn, platform="windows"), self.root / "bulk")
        rows = json.loads((self.root / "bulk/messages.json").read_text(encoding="utf-8"))
        self.assertEqual(result["messages"], 6)
        self.assertEqual(next(r["content"] for r in rows if r["local_id"] == 1), self.long)
        self.assertNotIn("_raw", str(rows))

    def monitor(self):
        path = Path(__file__).parents[1] / "decrypt/macos/monitor.py"
        spec = importlib.util.spec_from_file_location("test_mac_monitor", path)
        module = importlib.util.module_from_spec(spec)
        fake_paths = SimpleNamespace(decrypted=lambda *parts: str(self.root.joinpath(*parts)),
                                     info_db=lambda: str(self.path), session_db=lambda: str(self.root / "Session.db"),
                                     keys_file=lambda: str(self.root / "wxwork_keys.json"))
        with patch.dict(sys.modules, {"wecom_paths": fake_paths}):
            spec.loader.exec_module(module)
        return module

    def test_monitor_local_id_cursor_includes_late_and_same_second_messages(self):
        mac_path, _ = database(self.root / "mac")
        monitor = self.monitor()
        _rows, watermark, lid = monitor.fetch_new(mac_path, 0)
        self.assertEqual(lid, 5)
        with contextlib.closing(sqlite3.connect(mac_path)) as conn, conn:
            conn.execute("INSERT INTO MESSAGE VALUES (6,1006,101,11,0,?,'同秒消息')", (watermark,))
            conn.execute("INSERT INTO MESSAGE VALUES (7,1007,101,11,0,?,'晚到消息')", (watermark - 100,))
        fresh, _, next_lid = monitor.fetch_new(mac_path, watermark, lid)
        self.assertEqual([r["lid"] for r in fresh], [6, 7])
        self.assertEqual(next_lid, 7)
        self.assertEqual(monitor.fetch_new(mac_path, watermark, next_lid)[0], [])

    def test_monitor_wal_only_change_triggers_refresh(self):
        mac_path, _ = database(self.root / "mac")
        monitor = self.monitor()
        source = self.root / "source.db"
        source.write_bytes(b"unchanged main database")
        monitor.SRC_INFO = str(source)
        monitor.STATE = str(self.root / "monitor-state.json")
        monitor.OUTLOG = str(self.root / "monitor.jsonl")
        ticks = 0

        def after_tick(_):
            nonlocal ticks
            ticks += 1
            if ticks == 1:
                with contextlib.closing(sqlite3.connect(mac_path)) as conn, conn:
                    conn.execute("INSERT INTO MESSAGE VALUES (6,1006,101,11,0,1,'late WAL message')")
                Path(str(source) + "-wal").write_bytes(b"changed WAL only")
            else:
                raise RuntimeError("test stop")

        with patch.object(sys, "argv", ["monitor.py", "--poll", "0.01"]), patch.object(monitor, "load_messages_key", return_value=b"key"), patch.object(monitor, "decrypt_fresh", return_value=str(mac_path)) as refresh, patch.object(monitor.time, "sleep", side_effect=after_tick), contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "test stop"):
            monitor.main()
        self.assertEqual(refresh.call_count, 2)
        messages = [json.loads(line) for line in Path(monitor.OUTLOG).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([m["lid"] for m in messages], [1, 2, 3, 4, 5, 6])
