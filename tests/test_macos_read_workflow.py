"""Local workflow contracts, using synthetic databases and keys only."""
import contextlib
import ctypes
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_fixtures import database
from test_wal_snapshot import KEY, PAGE, encrypted

from decrypt.macos import wecom_paths
from decrypt.wxwork_crypto import load_valid_keys

REPO = Path(__file__).resolve().parents[1]
MAC = REPO / "decrypt/macos"


class MacReadWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / "profile"
        self.state = self.root / "state"
        self.info, self.long_text = database(self.profile / "Messages1")
        self.session = self.info.with_name("Session.db")
        with contextlib.closing(sqlite3.connect(self.session)) as conn, conn:
            conn.execute("CREATE TABLE USER(RID INTEGER, name TEXT)")
            conn.execute("INSERT INTO USER VALUES (11, '发送人')")
        self.source_bytes = {}
        for path in (self.info, self.session):
            plain = path.read_bytes()
            data = b"".join(encrypted(plain[i:i + PAGE], i // PAGE + 1)
                            for i in range(0, len(plain), PAGE))
            path.write_bytes(data)
            self.source_bytes[path] = data
        extra, _ = database(self.profile / "Unused")
        self.extra = extra
        self.keys = self.state / "profile/wxwork_keys.json"
        self.keys.parent.mkdir(parents=True)
        self.keys.write_text(json.dumps({"synthetic": KEY.hex()}))
        self.dec = self.state / "profile/decrypted"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("WECOM_")}
        self.env.update(WECOM_PROFILE=str(self.profile), WECOM_STATE_DIR=str(self.state),
                        PYTHONDONTWRITEBYTECODE="1")
        wecom_paths.profile_dir.cache_clear()
        self.addCleanup(wecom_paths.profile_dir.cache_clear)

    def run_script(self, name, *args, check=True, overrides=None):
        env = dict(self.env, **(overrides or {}))
        return subprocess.run([sys.executable, str(MAC / name), *args], env=env,
                              cwd=self.root, capture_output=True, text=True, check=check, timeout=15)

    def module(self, name):
        spec = importlib.util.spec_from_file_location("workflow_" + name, MAC / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, self.env, clear=True), patch.dict(sys.modules, {"wecom_paths": wecom_paths}):
            spec.loader.exec_module(module)
        return module

    def test_refresh_only_chat_preserves_source_and_full_message_body(self):
        self.run_script("read_wecom.py")
        self.assertTrue((self.dec / "Messages1/Info.db").exists())
        self.assertTrue((self.dec / "Messages1/Session.db").exists())
        self.assertFalse((self.dec / "Unused").exists())
        self.assertFalse((self.root / "export").exists())
        data = json.loads(self.run_script("wecom_local.py", "search", "尾部关键字", "--json").stdout)
        row = data["messages"][0]
        self.assertEqual((row["content"], row["sender"], row["local_id"]), (self.long_text, "发送人", 1))
        self.assertTrue(all(path.read_bytes() == data for path, data in self.source_bytes.items()))

    def test_missing_keys_stop_before_any_memory_capture(self):
        self.keys.unlink()
        reader = self.module("read_wecom")
        run = subprocess.run

        def only_decryption(argv, **kwargs):
            if Path(argv[1]).name != "decrypt_wxwork.py":
                self.fail("a refresh attempted an unauthorized subprocess")
            return run(argv, capture_output=True, **kwargs)

        with patch.dict(os.environ, self.env, clear=True), patch.object(sys, "argv", ["read_wecom.py"]), \
             patch.object(reader.subprocess, "run", side_effect=only_decryption), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            reader.main()
        self.assertFalse(self.dec.exists())

    def test_wrong_session_key_does_not_replace_either_snapshot(self):
        self.run_script("read_wecom.py")
        before = (self.dec / "Messages1/Info.db").read_bytes()
        self.session.write_bytes(b"invalid cipher page".ljust(PAGE, b"x"))
        result = self.run_script("read_wecom.py", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.dec / "Messages1/Info.db").read_bytes(), before)

    def test_export_is_explicit_and_clean_preserves_keys_sources_and_other_files(self):
        export = self.root / "wanted-export"
        self.run_script("read_wecom.py", "--export", str(export))
        self.assertTrue((export / "messages.json").is_file())
        keep = self.dec / "keep.txt"
        keep.write_text("user file")
        key_bytes = self.keys.read_bytes()
        self.run_script("read_wecom.py", "--clean")
        self.assertFalse((self.dec / "Messages1/Info.db").exists())
        self.assertEqual(self.keys.read_bytes(), key_bytes)
        self.assertEqual(keep.read_text(), "user file")
        self.assertTrue((export / "messages.json").exists())
        self.assertTrue(all(path.read_bytes() == data for path, data in self.source_bytes.items()))
        self.run_script("read_wecom.py")
        self.assertTrue((self.dec / "Messages1/Info.db").is_file())

    def test_cleanup_rejects_source_and_ancestor_directories(self):
        for target in (self.profile, self.profile.parent):
            result = self.run_script("read_wecom.py", "--clean", check=False,
                                     overrides={"WECOM_DECRYPTED_DIR": str(target)})
            self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all(path.read_bytes() == data for path, data in self.source_bytes.items()))

    @unittest.skipIf(os.name == "nt", "symlink creation requires extra Windows permissions")
    def test_cleanup_rejects_directory_symlinks_outside_cache(self):
        self.dec.mkdir()
        (self.dec / "Messages1").symlink_to(self.profile / "Messages1", target_is_directory=True)
        result = self.run_script("read_wecom.py", "--clean", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.info.read_bytes(), self.source_bytes[self.info])

    def test_key_capture_reuses_valid_keys_without_native_memory_access(self):
        result = self.run_script("find_key_fast.py")
        self.assertIn("未扫描", result.stdout)
        self.assertNotIn(KEY.hex(), result.stdout + result.stderr)
        self.assertEqual(load_valid_keys(self.keys), [KEY])

    def test_offline_capture_saves_private_keys_without_logging_them(self):
        capture = self.module("find_key_offline")
        self.keys.unlink()
        output = io.StringIO()
        with patch.object(capture, "iter_candidates", return_value=iter([(KEY, "synthetic fixture")])), \
             contextlib.redirect_stdout(output):
            capture.main()
        self.assertNotIn(KEY.hex(), output.getvalue())
        self.assertEqual(load_valid_keys(self.keys), [KEY])
        if os.name != "nt":
            self.assertEqual(self.keys.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(sys.platform == "darwin", "CommonCrypto validator is macOS only")
    def test_validator_works_after_its_temporary_library_is_removed(self):
        capture = self.module("find_key_fast")
        with patch.object(capture, "LIB", str(self.root / "nonexistent.dylib")):
            lib = capture.load_validator()
        page = self.info.read_bytes()[:PAGE]
        out = ctypes.create_string_buffer(16)
        found = ctypes.create_string_buffer(1)
        iv = capture.generate_initial_vector(1)
        data = b"prefix" + KEY + b"suffix"
        lib.scan_buf(data, len(data), 1, page[16:24], page[8:16] + page[24:32], iv, out, found)
        self.assertEqual(out.raw, KEY)
        self.assertEqual(found.raw, b"\x01")
        self.assertFalse((self.root / "nonexistent.dylib").exists())

    def test_legacy_and_explicit_paths_and_invalid_key_json(self):
        legacy = self.root / "legacy"
        legacy.mkdir()
        (legacy / "wxwork_keys.json").write_text(json.dumps({"old": KEY.hex()}))
        (legacy / "decrypted").mkdir()
        env = {k: v for k, v in self.env.items() if k != "WECOM_STATE_DIR"}
        with patch.dict(os.environ, env, clear=True), patch.object(wecom_paths, "_HERE", str(legacy)):
            self.assertEqual(wecom_paths.keys_file(), str(legacy / "wxwork_keys.json"))
            self.assertEqual(wecom_paths.decrypted(), str(legacy / "decrypted"))
            with patch.dict(os.environ, {"WECOM_KEYS_FILE": str(self.root / "missing.json")}):
                self.assertEqual(wecom_paths.keys_file(), str(self.root / "missing.json"))
        invalid = self.root / "invalid.json"
        invalid.write_text("[]")
        self.assertEqual(load_valid_keys(invalid), [])


if __name__ == "__main__":
    unittest.main()
