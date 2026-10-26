#!/usr/bin/env python3
"""Refresh macOS chat snapshots with existing keys; export and cleanup are explicit."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

_H = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_H, os.path.dirname(_H)]
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
from wecom_paths import CHAT_DATABASES, decrypted, keys_file, profile_dir


def clean_chat():
    """Unlink only chat snapshots/sidecars, never keys, exports or a source tree."""
    source = Path(profile_dir()).resolve()
    root = Path(decrypted()).resolve()
    key_path = Path(keys_file()).resolve()
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("解密目录与原始 profile 重叠，拒绝清理")
    targets = [root / (name + suffix) for name in CHAT_DATABASES
               for suffix in ("", "-wal", "-shm", "-journal")]
    for path in targets:
        resolved = path.resolve()
        if root not in resolved.parents or source in resolved.parents or resolved == key_path:
            raise ValueError("清理目标指向源库、密钥或解密目录以外，拒绝清理")
    for path in targets:
        path.unlink(missing_ok=True)
    for directory in (root / "Messages1", root):
        try:
            directory.rmdir()  # Preserve unrelated files and nonempty directories.
        except (FileNotFoundError, OSError):
            pass
    print("已清理聊天快照；密钥、原始数据和导出保留")


def run(script, *args):
    print(f"\n▶ {script} {' '.join(args)}".rstrip())
    if subprocess.run([PY, os.path.join(HERE, script), *args]).returncode != 0:
        sys.exit(f"✗ {script} 失败")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--clean", action="store_true", help="只删除可重建的聊天快照")
    mode.add_argument("--export", metavar="DIR", help="刷新后显式导出全部聊天为 JSON/CSV")
    options = parser.parse_args()
    os.umask(0o077)
    if options.clean:
        clean_chat()
        return
    # Missing/invalid keys fail here. Capturing keys is a separate, explicit command.
    run("decrypt_wxwork.py", "--messages-only")
    if options.export:
        result = subprocess.run([PY, os.path.join(os.path.dirname(HERE), "export_wxwork.py"),
                                 "--db", decrypted("Messages1", "Info.db"), "--out", options.export])
        if result.returncode:
            sys.exit("export_wxwork 失败")
    print("聊天快照已刷新；可用 wecom_local.py 查询")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(str(error))
