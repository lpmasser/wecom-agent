#!/usr/bin/env python3
"""企业微信 Windows 版 · 全功能本地读取 —— 复用 Mac 解密核心 + 内容解析原语。

子命令(对齐 macOS wecom_local)：
  read           解密导出全部消息(含真名/会话名) → export/messages.json|csv
  contacts [词]  通讯录(姓名/手机/邮箱), 可按词过滤
  conversations  会话列表(名称/消息数/最后时间)
  search <词>    全文搜索消息
  stats          统计(发言排行/会话排行/类型/按小时/按天)
  todo           待办

用法: python wecom_win.py <key_hex> <子命令> [参数]
key 由 find_key.ps1 扫内存抓到。Windows 专属: CreateFileW 共享读(企微开着也能读)。
"""
import ctypes
import glob
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from ctypes import wintypes
from datetime import datetime

_H = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_H, os.path.dirname(_H)]
from wxwork_crypto import decrypt_database
import export_wxwork as ex
from media_export import export_cache
from local_files import open_files, print_files
from local_io import connect_readonly, configure_stdio
from local_query import MessageStore, parse_window, print_messages
from transcript_export import export_chat

OUT = os.path.join(_H, "export")
DEC = os.environ.get("WECOM_DECRYPTED_DIR") or os.path.join(OUT, "dec")

# Rendering profiles are passed explicitly; importing this module must not
# change the macOS decoder's global type maps.


def read_shared(path):
    GENERIC_READ = 0x80000000
    SHARE_ALL = 0x07
    k = ctypes.windll.kernel32
    k.CreateFileW.restype = wintypes.HANDLE
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    k.ReadFile.restype = wintypes.BOOL
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.GetLastError.restype = wintypes.DWORD
    h = k.CreateFileW(path, GENERIC_READ, SHARE_ALL, None, 3, 0x80, None)
    if h == wintypes.HANDLE(-1).value:
        error = k.GetLastError()
        if error in (2, 3):
            raise FileNotFoundError(path)
        raise OSError(error, "CreateFileW failed")
    try:
        size = 1024 * 1024
        buf = (ctypes.c_char * size)()
        rd = wintypes.DWORD(0)
        chunks = []
        while True:
            if not k.ReadFile(h, buf, size, ctypes.byref(rd), None):
                raise OSError(k.GetLastError(), "ReadFile failed")
            if not rd.value:
                return b"".join(chunks)
            chunks.append(bytes(buf[:rd.value]))
    finally:
        k.CloseHandle(h)


def _data_dir():
    configured = os.environ.get("WECOM_DATA_DIR")
    if configured:
        if os.path.isfile(os.path.join(configured, "message.db")):
            return configured
        sys.exit("WECOM_DATA_DIR 指定的目录缺少 message.db")
    m = glob.glob(os.path.join(os.path.expanduser("~"), "Documents", "WXWork", "*", "Data", "message.db"))
    if not m:
        sys.exit("没找到 message.db (企业微信装了吗/登录了吗?)")
    if len(m) > 1:
        sys.exit("发现多个企业微信账号；请用 WECOM_DATA_DIR 指定要读取的 Data 目录")
    return os.path.dirname(m[0])


def decrypt_db(name, key):
    src = os.path.join(_data_dir(), name)
    if not os.path.exists(src):
        return None
    os.makedirs(DEC, exist_ok=True)
    dec = os.path.join(DEC, name)
    decrypt_database(src, dec, key, reader=read_shared)
    con = connect_readonly(dec)
    con.text_factory = lambda b: b.decode("utf-8", "replace") if isinstance(b, bytes) else b
    return con


def load_names(key):
    """返回 (users{uid:名}, convs{cid:名}, self_uid)。"""
    users = {}
    u = decrypt_db("user.db", key)
    if u:
        for r in u.execute("SELECT id, name FROM user_table"):
            if r[1]:
                users[str(r[0])] = r[1]
        try:
            for r in u.execute("SELECT wxid, name FROM wechat_contactV1"):
                if r[1] and r[1] != "-":
                    users.setdefault(str(r[0]), r[1])
        except sqlite3.Error:
            pass
        u.close()
    convs, self_uid = {}, None
    s = decrypt_db("session.db", key)
    if s:
        srows = list(s.execute("SELECT id, name FROM conversation_table"))
        s.close()
        cnt = Counter()
        for cid, cname in srows:
            cid = str(cid)
            if cname:
                convs[cid] = cname
            if cid.startswith("S:"):
                for p in cid[2:].split("_"):
                    cnt[p] += 1
        if cnt:
            self_uid = cnt.most_common(1)[0][0]
    return users, convs, self_uid


def res_sender(sid, users):
    sid = str(sid)
    if sid in users:
        return users[sid]
    if sid.isdigit() and len(sid) < 12:
        return f"[系统/应用 {sid}]"
    return sid


def res_conv(cid, convs, users, self_uid):
    cid = str(cid)
    if cid in convs:
        return convs[cid]
    if cid.startswith("S:"):
        other = [p for p in cid[2:].split("_") if p != self_uid] or cid[2:].split("_")
        return users.get(other[0], cid)
    return cid


def _content(ct, raw):
    return ex.render(ct, raw, "windows")


def _store(key):
    users, convs, self_uid = load_names(key)
    info = decrypt_db("message.db", key)
    if info is None:
        sys.exit("缺 message.db")
    try:
        names = {str(cid): res_conv(cid, convs, users, self_uid)
                 for (cid,) in info.execute("SELECT DISTINCT conversation_id FROM message_table")}
        return MessageStore(info, users=users, conversations=names, platform="windows",
                            sender=lambda sid: res_sender(sid, users))
    except Exception:
        info.close()
        raise


def cmd_read(key, args):
    from transcript_export import export_all
    store = _store(key)
    try:
        result = export_all(store, OUT)
    finally:
        store.conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))

def cmd_contacts(key, args, js=False):
    kw = args[0] if args else ""
    u = decrypt_db("user.db", key)
    contacts = []
    for r in u.execute("SELECT name, english_name, mobile, email, position FROM user_table ORDER BY name"):
        blob = " ".join(str(x or "") for x in r)
        if kw and kw not in blob:
            continue
        fields = [str(r[0] or ""), str(r[1] or ""), str(r[2] or ""), str(r[3] or ""), str(r[4] or "")]
        contacts.append(dict(zip(("name", "english_name", "mobile", "email", "position"), fields)))
        if not js:
            print("  " + " | ".join(x for x in fields if x))
    u.close()
    if js:
        return {"keyword": kw, "count": len(contacts), "contacts": contacts}
    print(f"\n{len(contacts)} 人" + (f'(含"{kw}")' if kw else ""))


def cmd_conversations(key, args, js=False):
    options = parse_window(args)
    store = _store(key)
    try:
        result = store.conversation_page(options.limit, options.offset)
    finally:
        store.conn.close()
    if js:
        return result
    for row in result["conversations"]:
        print(f"  {row['last_time']}  {row['messages']:>5}条  {row['name']} (ID={row['id']})")
    print(f"\n{result['count']}/{result['total']} 个会话；下一页 offset={result['next_offset']}")


def cmd_search(key, args, js=False):
    options = parse_window(args, positional="keyword")
    store = _store(key)
    try:
        result = store.search(options.keyword, limit=options.limit, offset=options.offset, days=options.days)
    finally:
        store.conn.close()
    if js:
        return result
    print_messages(result)


def cmd_chat(key, args, js=False):
    options = parse_window(args, positional="conversation")
    store = _store(key)
    try:
        result = store.read_chat(options.conversation, limit=options.limit or 50,
                                 offset=options.offset, days=options.days)
    finally:
        store.conn.close()
    if js:
        return result
    print_messages(result)


def cmd_export(key, args, js=False):
    options = parse_window(args, positional="conversation", export=True)
    store = _store(key)
    try:
        result = export_chat(store, os.path.join(DEC, "message.db"), options.conversation,
                             options.out, days=options.days, output_format=options.format,
                             with_media=options.with_media, cache_root=_cache("") if options.with_media else None)
    finally:
        store.conn.close()
    if js:
        return result
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_stats(key, args, js=False):
    users, convs, self_uid = load_names(key)
    by_s, by_c, by_t, by_h, by_d = Counter(), Counter(), Counter(), Counter(), Counter()
    total = 0
    info = decrypt_db("message.db", key)
    for st, conv, sender, ct in info.execute("SELECT send_time, conversation_id, sender_id, content_type FROM message_table"):
        total += 1
        by_s[res_sender(sender, users)] += 1
        by_c[res_conv(conv, convs, users, self_uid)] += 1
        by_t[ex.type_name(ct, "windows")] += 1
        if st:
            dt = datetime.fromtimestamp(st)
            by_h[dt.hour] += 1
            by_d[dt.strftime("%Y-%m-%d")] += 1
    info.close()
    if js:
        return {"total": total, "by_sender": by_s.most_common(10), "by_conv": by_c.most_common(10),
                "by_type": by_t.most_common(), "by_hour": {h: by_h.get(h, 0) for h in range(24)},
                "by_day": sorted(by_d.items())}
    print(f"总消息 {total} 条")
    print("\n发言最多:")
    for s, c in by_s.most_common(10):
        print(f"  {c:>6}  {s}")
    print("\n最活跃会话:")
    for s, c in by_c.most_common(10):
        print(f"  {c:>6}  {s}")
    print("\n最近 7 活跃天:")
    for d, c in sorted(by_d.items())[-7:]:
        print(f"  {d}  {c}")


def cmd_todo(key, args, js=False):
    users, _, _ = load_names(key)
    f = decrypt_db("forever_store.db", key)
    if not f:
        sys.exit("无 forever_store.db")
    todos = []
    try:
        for r in f.execute("SELECT content, status, creator_id, from_info_name, create_time FROM todo_v4 ORDER BY create_time DESC"):
            content, status, creator, fromname, ctime = r
            st = "✓完成" if status == 1 else "○待办"
            who = users.get(str(creator), fromname or str(creator))
            todos.append({"content": str(content or ""), "status": status, "creator": who, "time": ex.fmt_time(ctime)})
            if not js:
                print(f"  {st}  {str(content or '')} {who} {ex.fmt_time(ctime) if ctime else ''}")
    except sqlite3.Error as e:
        sys.exit(f"读 todo_v4 失败: {e}")
    finally:
        f.close()
    if js:
        return {"count": len(todos), "todos": todos}
    print(f"\n{len(todos)} 条待办")


def cmd_members(key, args, js=False):
    if not args:
        sys.exit("用法: members <会话名或ID>")
    q = args[0]
    users, convs, self_uid = load_names(key)
    s = decrypt_db("session.db", key)
    from local_query import resolve_conversation
    seen = {}
    try:
        targets = [{"id": str(cid), "name": cname or res_conv(cid, convs, users, self_uid)}
                   for cid, cname in s.execute("SELECT id, name FROM conversation_table")]
        target = resolve_conversation(q, targets)
        for uid, nick in s.execute("SELECT user_id, nick_name FROM conversation_user_table WHERE conversation_id=?", (target["id"],)):
            uid = str(uid)
            seen[uid] = users.get(uid) or nick or uid
    finally:
        s.close()
    if js:
        return {"query": q, "conversation": target, "members": [{"id": uid, "name": nm} for uid, nm in seen.items()]}
    print(f"会话 '{q}' 成员({len(seen)}):")
    for uid, nm in sorted(seen.items(), key=lambda x: x[1]):
        print(f"  {nm}")


def _cache(sub):
    return os.path.join(os.environ.get("WECOM_CACHE_DIR") or os.path.join(os.path.dirname(_data_dir()), "Cache"), sub)


def cmd_calendar(key, args, js=False):
    c = decrypt_db("calendar_r7.db", key)
    if not c:
        sys.exit("无 calendar_r7.db")
    events = []
    for st, et, raw in c.execute("SELECT starttime, endtime, rawdata FROM calendar_main_table_v2 ORDER BY starttime DESC"):
        strs = ex._pb_strings(bytes(raw)) if raw else []
        cjk = [s for s in strs if re.search(r"[一-鿿]", s)]
        title = cjk[0] if cjk else (strs[0] if strs else "(无标题)")
        events.append({"start": ex.fmt_time(st), "end": ex.fmt_time(et), "title": title})
        if not js:
            print(f"  {ex.fmt_time(st)} ~ {ex.fmt_time(et)[11:]}  {title}")
    c.close()
    if js:
        return {"count": len(events), "events": events}
    print(f"\n{len(events)} 个日程")


def cmd_media(key, args, js=False):
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--out", default=os.path.join(OUT, "media"))
    options = parser.parse_args(args)
    result = export_cache(_cache(""), options.out, ("Image", "File", "Voice", "Emotion"))
    if js:
        return result
    print(json.dumps(result, ensure_ascii=False, indent=2))

def cmd_openfile(key, args, js=False):
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("keyword")
    parser.add_argument("--full", action="store_true")
    options = parser.parse_args(args)
    store = _store(key)
    try:
        result = open_files(store, _cache(""), options.keyword, full=options.full)
    finally:
        store.conn.close()
    if js:
        return result
    print_files(result)

def cmd_voice(key, args):
    root = _cache("Voice")
    files = sorted(f for f in glob.glob(os.path.join(root, "**", "*"), recursive=True) if os.path.isfile(f))
    print(f"缓存语音 {len(files)} 条 @ {root}")
    try:
        import pilk
        from faster_whisper import WhisperModel
    except ImportError:
        for f in files[:20]:
            print(f"  {os.path.getsize(f) // 1024}KB  {os.path.basename(f)}")
        print("\n转写: SILK→pilk→faster-whisper。x64 Windows 有 wheel 可直接装；")
        print("  本 ARM VM 无 win_arm64 wheel 且无 C++ 工具链, 转写不可用(定位/导出仍可)。")
        return
    import wave
    model = WhisperModel("base", device="cpu", compute_type="int8")
    res = {}
    for f in files:
        try:
            pcm = f + ".pcm"
            pilk.decode(f, pcm)
            wav = f + ".wav"
            with open(pcm, "rb") as p, wave.open(wav, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(p.read())
            seg, _ = model.transcribe(wav, language="zh")
            res[os.path.basename(f)] = "".join(s.text for s in seg).strip()
        except Exception as e:
            res[os.path.basename(f)] = f"[转写失败 {e}]"
    json.dump(res, open(os.path.join(OUT, "voice_transcripts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in res.items():
        print(f"  {k}: {v[:60]}")
    print(f"\n{len(res)} 条 → {OUT}\\voice_transcripts.json")


def cmd_monitor(key, args):
    sf = os.path.join(OUT, "monitor_state.json")
    os.makedirs(OUT, exist_ok=True)
    wm = json.load(open(sf)).get("watermark", 0) if os.path.exists(sf) else 0
    users, convs, self_uid = load_names(key)
    info = decrypt_db("message.db", key)
    new, hi = [], wm
    for st, conv, sender, ct, content in info.execute(
            "SELECT send_time, conversation_id, sender_id, content_type, content "
            "FROM message_table WHERE send_time > ? ORDER BY send_time", (wm,)):
        new.append((st, res_conv(conv, convs, users, self_uid), res_sender(sender, users), _content(ct, content)))
        hi = max(hi, st or 0)
    info.close()
    json.dump({"watermark": hi}, open(sf, "w"))
    if wm == 0:
        print(f"首次建立水位(send_time>{hi}); 共 {len(new)} 条历史. 之后再跑只出新消息。")
    else:
        print(f"新消息 {len(new)} 条:")
        for st, cv, s, c in new[:30]:
            print(f"  [{ex.fmt_time(st)}] 【{str(cv)[:12]}】{str(s)[:8]}: {str(c)[:40]}")


CMDS = {"read": cmd_read, "contacts": cmd_contacts, "conversations": cmd_conversations,
        "members": cmd_members, "search": cmd_search, "chat": cmd_chat, "export": cmd_export,
        "stats": cmd_stats, "todo": cmd_todo,
        "calendar": cmd_calendar, "media": cmd_media, "openfile": cmd_openfile,
        "voice": cmd_voice, "monitor": cmd_monitor}


def main():
    configure_stdio()
    if len(sys.argv) < 3 or sys.argv[2] not in CMDS:
        print(__doc__)
        print("子命令:", ", ".join(CMDS))
        sys.exit(1)
    key = bytes.fromhex(sys.argv[1].strip())
    if len(key) != 16:
        sys.exit("key 必须 16 字节(32 hex)")
    args = [a for a in sys.argv[3:] if a != "--json"]
    try:
        command = CMDS[sys.argv[2]]
        if "--json" in sys.argv[3:]:
            if sys.argv[2] not in ("contacts", "conversations", "members", "search", "chat", "export", "stats", "todo", "calendar", "media", "openfile"):
                sys.exit("此子命令暂不支持 --json")
            result = command(key, args, js=True)
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            command(key, args)
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
