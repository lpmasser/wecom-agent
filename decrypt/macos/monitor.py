#!/usr/bin/env python3
"""企业微信本地消息**增量监控** —— 用已存的 key 重解密 Info.db, 取上次以来的新消息。

特点: 无需重扫内存(key 已存 wxwork_keys.json), 无需重签; 纯读磁盘 DB + 已知 key。
(读取经过校验的已提交主库 + WAL 快照；本地 LID 水位包含同秒及晚到消息。)
解析复用 export_wxwork(发送者真名/类型/卡片/文件/文档)。
用法: monitor.py [--once] [--poll 30] [--all]
  --once  跑一次即退出   --poll N 轮询秒数(默认30)   --all 忽略水位,输出全部
"""
import json
import argparse
import hashlib
import math
import os
import sys
import time

_H = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_H, os.path.dirname(_H)]
from wxwork_crypto import PAGE_SZ, decrypt_database, load_valid_keys
import export_wxwork as ex
from local_io import atomic_output, connect_readonly, private_mkdir
from wal_snapshot import _metadata

HERE = os.path.dirname(os.path.abspath(__file__))
from wecom_paths import decrypted, info_db, session_db
SRC_INFO = info_db()
SRC_SESS = session_db()
DEC = decrypted("Messages1")
KEYS = os.path.join(HERE, "wxwork_keys.json")
STATE = os.path.join(HERE, "export", "monitor_state.json")
OUTLOG = os.path.join(HERE, "export", "monitor.jsonl")


def load_messages_key():
    if not os.path.exists(KEYS):
        sys.exit(f"缺 {KEYS}, 先跑 find_key_fast.py")
    with open(SRC_INFO, "rb") as f:
        pg1 = f.read(PAGE_SZ)
    keys = load_valid_keys(KEYS, pg1)
    if not keys:
        sys.exit("wxwork_keys.json 里没有能解 Info.db 的 key, 重跑 find_key_fast.py")
    return keys[0]


def decrypt_fresh(key):
    """把当前磁盘上的 Info.db / Session.db 用 key 重新解密到 decrypted/。"""
    os.makedirs(DEC, exist_ok=True)
    info_out = os.path.join(DEC, "Info.db")
    decrypt_database(SRC_INFO, info_out, key)
    if os.path.exists(SRC_SESS):
        try:
            decrypt_database(SRC_SESS, os.path.join(DEC, "Session.db"), key)
        except Exception:
            pass
    return info_out


def fetch_new(info_db, watermark, last_lid=None):
    users = ex._load_user_names(info_db)
    conn = connect_readonly(info_db)
    conv = ex._load_conv_names(conn)
    out = []
    hi = watermark
    condition, parameter = ("LID > ?", last_lid) if last_lid is not None else ("send_time >= ?", watermark)
    high_lid = last_lid or 0
    for r in conn.execute(
        "SELECT LID, conv_id, sender_id, content_type, send_time, content "
        "FROM MESSAGE WHERE " + condition + " ORDER BY LID", (parameter,)
    ):
        st = r["send_time"] or 0
        hi = max(hi, st)
        high_lid = max(high_lid, r["LID"])
        cv = r["conv_id"]
        out.append({
            "lid": r["LID"], "send_time": st,
            "time": ex.fmt_time(st),
            "conversation": conv.get(cv, cv),
            "sender": ex.resolve_sender(r["sender_id"], users),
            "type": ex.type_name(r["content_type"]),
            "content": ex.render(r["content_type"], r["content"]),
        })
    conn.close()
    return out, hi, high_lid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--poll", type=float, default=30.0)
    options = parser.parse_args()
    once, allmsg, poll = options.once, options.all, options.poll
    if not math.isfinite(poll) or poll <= 0:
        parser.error("--poll 必须是有限的正数")

    key = load_messages_key()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    profile_id = hashlib.sha256(os.path.realpath(SRC_INFO).encode()).hexdigest()
    if state.get("profile") not in (None, profile_id):
        state = {}
    watermark = 0 if allmsg else int(state.get("watermark", 0))
    last_lid = 0 if allmsg else state.get("last_lid")
    private_mkdir(os.path.dirname(OUTLOG))
    print(f"监控启动: LID 水位 {last_lid}; {'单次' if once else f'每{poll:.0f}s'}")

    last_snapshot = None

    def tick():
        nonlocal watermark, last_lid, last_snapshot
        stamp = (_metadata(SRC_INFO), _metadata(SRC_INFO + "-wal"))
        if stamp == last_snapshot:
            return 0                       # 源库未变 → 必无新消息, 跳过重解密
        info_path = decrypt_fresh(key)
        new, hi, high_lid = fetch_new(info_path, watermark, last_lid)
        if new:
            fd = os.open(OUTLOG, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                for m in new:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
            for m in new:
                print(f"  [{m['time']}] {m['conversation']} | {m['sender']} [{m['type']}]\n{m['content']}")
            watermark = hi
            last_lid = high_lid
            with atomic_output(STATE) as stream:
                json.dump({"watermark": watermark, "last_lid": last_lid, "profile": profile_id}, stream)
        last_snapshot = stamp
        return len(new)

    if once:
        print(f"新消息 {tick()} 条 → {OUTLOG}")
        return
    while True:
        n = tick()
        if n:
            print(f"[{ex.fmt_time(int(time.time()))}] +{n} 条")
        time.sleep(poll)


if __name__ == "__main__":
    main()
