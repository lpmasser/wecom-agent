#!/usr/bin/env python3
"""企业微信**本地数据**查询 —— 基于已解密的 53 库 + 明文缓存, 全本地、无需 API/网络/模型。

子命令(均支持 --json 输出结构化):
  contacts [关键词]      通讯录(姓名/部门/职位/手机/邮箱), 可按词过滤
  conversations          会话列表(名称/消息数/最后时间)
  members <会话名或ID>   某会话的参与者
  search <关键词>        全文搜索消息(时间/会话/发送者/正文)
  stats                  统计(总量/发言排行/会话排行/类型/按小时/按天)
  todo                   待办(内容/状态/创建者/提醒)
  calendar               日程
  media [--out 目录]     导出明文缓存的图片+文件(按原名)
  openfile <名/关键词>   找文档(谁/何时发)→定位本体→文本解析; 图片型/扫描PDF 输出🖼️VISUAL路径交多模态Read
前提: 先跑 read_wecom.py 解密。用法: wecom_local.py <子命令> [参数] [--json]
"""
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime

_H = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_H, os.path.dirname(_H)]
import export_wxwork as ex
from media_export import export_cache
from local_files import open_files, print_files
from local_io import connect_readonly, configure_stdio
from local_query import MessageStore, parse_window, print_messages
from transcript_export import export_chat

HERE = os.path.dirname(os.path.abspath(__file__))
from wecom_paths import caches, decrypted
DEC = decrypted()
INFO = decrypted("Messages1", "Info.db")
SESS = decrypted("Messages1", "Session.db")
CACHES = None


def _caches():
    return CACHES or caches()


def _conn(path):
    if not os.path.exists(path):
        sys.exit(f"缺 {path}, 先跑 read_wecom.py 解密")
    return connect_readonly(path)


def _store(info):
    return MessageStore(info, users=ex._load_user_names(INFO))


def cmd_contacts(args, js=False):
    kw = args[0] if args else ""
    c = _conn(SESS)
    people = []
    for r in c.execute("SELECT name, fullpath, job, mobile, email, alias FROM USER ORDER BY name"):
        blob = " ".join(str(r[k] or "") for k in ("name", "fullpath", "job", "mobile", "email", "alias"))
        if kw and kw not in blob:
            continue
        people.append({k: (r[k] or "") for k in ("name", "fullpath", "job", "mobile", "email", "alias")})
    c.close()
    if js:
        return {"keyword": kw, "count": len(people), "contacts": people}
    for p in people:
        fields = [p["name"], p["job"], p["mobile"], p["email"], p["fullpath"]]
        print("  " + " | ".join(x for x in fields if x))
    print(f"\n{len(people)} 人" + (f' (含"{kw}")' if kw else ""))


def cmd_conversations(args, js=False):
    options = parse_window(args)
    info = _conn(INFO)
    try:
        result = _store(info).conversation_page(options.limit, options.offset)
    finally:
        info.close()
    if js:
        return result
    for row in result["conversations"]:
        print(f"  {row['last_time']}  {row['messages']:>5}条  {row['name']} (ID={row['id']})")
    print(f"\n{result['count']}/{result['total']} 个会话；下一页 offset={result['next_offset']}")


def cmd_members(args, js=False):
    if not args:
        sys.exit("用法: members <会话名或ID>")
    q = args[0]
    info = _conn(INFO)
    users = ex._load_user_names(INFO)
    try:
        target = _store(info).target(q)
    except Exception:
        info.close()
        raise
    seen = Counter()
    for (sid,) in info.execute("SELECT sender_id FROM MESSAGE WHERE conv_id=?", (target["id"],)):
        seen[sid] += 1
    info.close()
    if js:
        return {"query": q, "conversation": target, "members": [
            {"id": str(sid), "name": ex.resolve_sender(sid, users), "messages": n} for sid, n in seen.most_common()]}
    print(f"会话 '{q}' 参与者(按发言数):")
    for sid, n in seen.most_common():
        print(f"  {n:>4}  {ex.resolve_sender(sid, users)} (ID={sid})")


def cmd_search(args, js=False):
    options = parse_window(args, positional="keyword")
    info = _conn(INFO)
    try:
        result = _store(info).search(options.keyword, limit=options.limit, offset=options.offset, days=options.days)
    finally:
        info.close()
    if js:
        return result
    print_messages(result)


def cmd_chat(args, js=False):
    options = parse_window(args, positional="conversation")
    info = _conn(INFO)
    try:
        result = _store(info).read_chat(options.conversation, limit=options.limit or 50,
                                       offset=options.offset, days=options.days)
    finally:
        info.close()
    if js:
        return result
    print_messages(result)


def cmd_export(args, js=False):
    options = parse_window(args, positional="conversation", export=True)
    info = _conn(INFO)
    try:
        result = export_chat(_store(info), INFO, options.conversation, options.out, days=options.days,
                             output_format=options.format, with_media=options.with_media,
                             cache_root=_caches() if options.with_media else None)
    finally:
        info.close()
    if js:
        return result
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_stats(args, js=False):
    info = _conn(INFO)
    users = ex._load_user_names(INFO)
    convn = ex._load_conv_names(info)
    by_s, by_c, by_t, by_h, by_d = Counter(), Counter(), Counter(), Counter(), Counter()
    total = 0
    for r in info.execute("SELECT conv_id, sender_id, content_type, send_time FROM MESSAGE"):
        total += 1
        by_s[ex.resolve_sender(r["sender_id"], users)] += 1
        by_c[convn.get(r["conv_id"], r["conv_id"])] += 1
        by_t[ex.type_name(r["content_type"])] += 1
        if r["send_time"]:
            dt = datetime.fromtimestamp(r["send_time"])
            by_h[dt.hour] += 1
            by_d[dt.strftime("%Y-%m-%d")] += 1
    info.close()
    if js:
        return {"total": total, "by_sender": by_s.most_common(10), "by_conv": by_c.most_common(10),
                "by_type": by_t.most_common(12), "by_hour": {h: by_h.get(h, 0) for h in range(24)},
                "by_day": sorted(by_d.items())}
    print(f"总消息 {total} 条")
    print("\n发言最多:")
    for s, n in by_s.most_common(10):
        print(f"  {n:>5}  {s}")
    print("\n最活跃会话:")
    for c, n in by_c.most_common(10):
        print(f"  {n:>5}  {c}")
    print("\n类型分布:")
    for t, n in by_t.most_common(12):
        print(f"  {n:>5}  {t}")
    print("\n按小时:")
    mx = max(by_h.values()) if by_h else 1
    for h in range(24):
        bar = "█" * int(by_h.get(h, 0) / mx * 30)
        print(f"  {h:02d}时 {by_h.get(h,0):>4} {bar}")
    print("\n最近 7 活跃天:")
    for d, n in sorted(by_d.items())[-7:]:
        print(f"  {d}  {n}")


def cmd_todo(args, js=False):
    p = os.path.join(DEC, "Todo", "Todo.db")
    users = ex._load_user_names(INFO)
    c = _conn(p)
    items = []
    for r in c.execute("SELECT content, completed, creator, remindtime FROM TODOTABLE3 WHERE deleted=0 "
                       "ORDER BY remindtime DESC"):
        items.append({"content": str(r["content"] or ""), "completed": bool(r["completed"]),
                      "creator": users.get(r["creator"], str(r["creator"])),
                      "remind": ex.fmt_time(r["remindtime"]) if r["remindtime"] else ""})
    c.close()
    if js:
        return {"count": len(items), "todos": items}
    for it in items:
        st = "✓完成" if it["completed"] else "○待办"
        print(f"  {st}  {it['content'][:54]:<54} {it['creator']} {it['remind']}")
    print(f"\n{len(items)} 条待办")


def cmd_calendar(args, js=False):
    p = os.path.join(DEC, "Calendar", "Calendar_tmp19.db")
    c = _conn(p)
    events = []
    for r in c.execute("SELECT starttime, endtime, blob FROM calevent2 ORDER BY starttime DESC"):
        title = ex.decode_text(r["blob"]) if r["blob"] else ""
        title = title.split("\n")[0][:50] if title else "(无标题)"
        events.append({"start": ex.fmt_time(r["starttime"]), "end": ex.fmt_time(r["endtime"]), "title": title})
    c.close()
    if js:
        return {"count": len(events), "events": events}
    for e in events:
        print(f"  {e['start']} ~ {e['end'][11:]}  {e['title']}")
    print(f"\n{len(events)} 个日程")


def cmd_media(args, js=False):
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--out", default=os.path.join(HERE, "export", "media"))
    options = parser.parse_args(args)
    result = export_cache(_caches(), options.out, ("Images", "Files", "Voices", "Emotions"))
    if js:
        return result
    print(json.dumps(result, ensure_ascii=False, indent=2))

def cmd_openfile(args, js=False):
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("keyword")
    parser.add_argument("--full", action="store_true")
    options = parser.parse_args(args)
    info = _conn(INFO)
    try:
        result = open_files(_store(info), _caches(), options.keyword, full=options.full)
    finally:
        info.close()
    if js:
        return result
    print_files(result)

CMDS = {"contacts": cmd_contacts, "conversations": cmd_conversations, "members": cmd_members,
        "search": cmd_search, "chat": cmd_chat, "export": cmd_export,
        "stats": cmd_stats, "todo": cmd_todo, "calendar": cmd_calendar,
        "media": cmd_media, "openfile": cmd_openfile}


def main():
    configure_stdio()
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        print("子命令:", ", ".join(CMDS))
        sys.exit(1)
    js = "--json" in sys.argv
    args = [a for a in sys.argv[2:] if a != "--json"]
    try:
        r = CMDS[sys.argv[1]](args, js)
    except ValueError as e:
        sys.exit(str(e))
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            sys.exit("解密 OK，但核心表缺失 → 数据未同步(可能是新登录)。先打开企业微信浏览消息，等同步后重试。")
        raise
    if js:
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
