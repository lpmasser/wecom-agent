"""Exercise installer side effects with local stub executables, never real clients."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "POSIX shell installer")
class SetupTests(unittest.TestCase):
    def test_mcp_is_installed_and_registered_only_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binaries = root / "bin"
            binaries.mkdir()
            events = root / "events.jsonl"
            python = binaries / "python"
            # Use the test interpreter, not any tool on the operator's PATH.
            import sys
            python.write_text(f"#!{sys.executable}\n" + r'''
import json, os, pathlib, shutil, sys
args = sys.argv[1:]
with open(os.environ["SETUP_TEST_EVENTS"], "a") as stream:
    stream.write(json.dumps(["python", *args]) + "\n")
if args[:2] == ["-m", "venv"]:
    dest = pathlib.Path(args[2]) / "bin/python"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, dest)
    dest.chmod(0o700)
''')
            claude = binaries / "claude"
            claude.write_text(f"#!{sys.executable}\n" + r'''
import json, os, sys
with open(os.environ["SETUP_TEST_EVENTS"], "a") as stream:
    stream.write(json.dumps(["claude", *sys.argv[1:]]) + "\n")
''')
            uname = binaries / "uname"
            uname.write_text("#!/bin/sh\necho Darwin\n")
            for path in (python, claude, uname):
                path.chmod(0o700)
            env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ.get("PATH", ""),
                       WECOM_PYTHON=str(python), WECOM_VENV_DIR=str(root / "venv"),
                       SETUP_TEST_EVENTS=str(events))

            def install(*args):
                events.unlink(missing_ok=True)
                subprocess.run(["bash", str(REPO / "setup.sh"), *args], env=env,
                               capture_output=True, text=True, check=True)
                return [json.loads(line) for line in events.read_text().splitlines()]

            default = install()
            self.assertFalse(any(row[0] == "claude" for row in default))
            packages = [row[-1] for row in default if row[1:4] == ["-m", "pip", "install"]]
            self.assertEqual(packages, [str(REPO / "requirements-core.txt")])
            explicit = install("--mcp")
            packages = [row[-1] for row in explicit if row[1:4] == ["-m", "pip", "install"]]
            self.assertEqual(packages, [str(REPO / "requirements.txt")])
            self.assertTrue(any(row[:3] == ["claude", "mcp", "add"] for row in explicit))
            later_default = install()
            self.assertFalse(any(row[0] == "claude" for row in later_default))


if __name__ == "__main__":
    unittest.main()
