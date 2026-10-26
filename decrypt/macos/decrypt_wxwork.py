#!/usr/bin/env python3
"""用 wxwork_keys.json 的 16B raw key 解密企业微信(macOS)各加密库 → decrypt/macos/decrypted/。
自动按页1匹配可用 key(不同库可能不同 key); 明文库直接拷贝; 末尾打印消息库 schema。
用法: decrypt_wxwork.py [--profile DIR] [--out DIR] [--messages-only]
"""
import argparse
import os
import sqlite3
import sys

_H = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_H, os.path.dirname(_H)]
from wxwork_crypto import PAGE_SZ, SQLITE_HDR, decrypt_database, load_valid_keys, table_names, verify_key

HERE = os.path.dirname(os.path.abspath(__file__))
from wecom_paths import CHAT_DATABASES, profile_dir, decrypted, keys_file


def load_keys():
    path = keys_file()
    if not os.path.exists(path):
        sys.exit(f"缺 {path}；可配置 WECOM_KEYS_FILE。首次取钥须单独运行 find_key_fast.py")
    keys = load_valid_keys(path)
    if not keys:
        sys.exit("wxwork_keys.json 无有效 16B key")
    return keys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--out")
    parser.add_argument("--messages-only", action="store_true", help="只刷新 Info.db 和 Session.db")
    options = parser.parse_args()
    if options.profile:
        os.environ["WECOM_PROFILE"] = options.profile
        profile_dir.cache_clear()
    prof, out = profile_dir(), options.out or decrypted()
    keys = load_keys()
    print(f"{len(keys)} 个候选 key; profile={prof}")

    if options.messages_only:
        # Validate both databases before replacing either snapshot.
        for relative in CHAT_DATABASES:
            with open(os.path.join(prof, relative), "rb") as stream:
                page = stream.read(PAGE_SZ)
            if len(page) != PAGE_SZ or (page[:16] != SQLITE_HDR and not any(verify_key(k, page) for k in keys)):
                sys.exit(f"{relative}: 源库或已有密钥无效；未扫描内存")

    ok = copied = fail = 0
    msgdb = None
    for root, _, files in os.walk(prof):
        for name in sorted(files):
            if not name.endswith(".db") or name.endswith(("-wal", "-shm", "-journal")):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, prof)
            if options.messages_only and rel.replace(os.sep, "/") not in CHAT_DATABASES:
                continue
            if os.path.getsize(path) < PAGE_SZ:
                continue
            with open(path, "rb") as f:
                pg1 = f.read(PAGE_SZ)
            outp = os.path.join(out, rel)
            if pg1[:16] == SQLITE_HDR:
                decrypt_database(path, outp, None)
                copied += 1
                if rel.replace(os.sep, "/").endswith("Messages1/Info.db"):
                    msgdb = outp
                continue
            key = next((k for k in keys if verify_key(k, pg1)), None)
            if not key:
                print(f"SKIP {rel} (无匹配 key)")
                fail += 1
                continue
            try:
                decrypt_database(path, outp, key)
                tbls = table_names(outp)
                ok += 1
                print(f"OK   {rel}  表{len(tbls)}: {', '.join(tbls[:6])}")
                if rel.replace(os.sep, "/").endswith("Messages1/Info.db"):
                    msgdb = outp
            except Exception as e:
                print(f"FAIL {rel} ({e})")
                fail += 1

    print(f"\n解密 {ok}, 拷贝 {copied}, 跳过/失败 {fail} → {out}")
    if msgdb is None or (options.messages_only and fail):
        sys.exit("主消息库未成功更新；保留已有输出，请修复源库或 key 后重试")
    if msgdb and not options.messages_only:
        print(f"\n=== 消息库 schema: {os.path.relpath(msgdb, HERE)} ===")
        conn = sqlite3.connect(msgdb)
        for (sql,) in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND sql NOT NULL ORDER BY name"
        ):
            print((sql or "")[:400])
        conn.close()


if __name__ == "__main__":
    main()
