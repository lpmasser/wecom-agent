"""Associate a cached document with each file message's resource ID."""

try:
    from . import read_doc
    from .media_manifest import CacheIndex, resource
except ImportError:
    import read_doc
    from media_manifest import CacheIndex, resource


def open_files(store, cache_root, keyword, *, full=False):
    if not keyword.strip():
        raise ValueError("keyword 不能为空")
    index = CacheIndex(cache_root)
    result = []
    for row in store.iter_messages():
        if row["type_code"] != 15:
            continue
        reference = resource(row)
        if reference is None or keyword.casefold() not in reference[1].casefold():
            continue
        status, reason, path = index.resolve(row)
        entry = {"name": reference[1], "local_id": row["local_id"], "conv_id": row["conv_id"],
                 "sender": row["sender"], "time": row["time"], "conv": row["conversation"],
                 "status": status, "reason": reason, "local": str(path) if path else None,
                 "content": None, "visual": None}
        if path is not None:
            body = read_doc.read_file(str(path), limit=20000 if full else 8000)
            entry["visual" if body.startswith(read_doc.VISUAL_MARK) else "content"] = body
        result.append(entry)
    return {"keyword": keyword, "count": len(result), "files": result}


def print_files(result):
    for entry in result["files"]:
        print(f"《{entry['name']}》 {entry['sender']} {entry['time']} @ {entry['conv']} (ID={entry['local_id']})")
        print(entry["visual"] or entry["content"] or f"[{entry['status']}: {entry['reason']}]")
        print()
    print(f"匹配 {result['count']} 条文件消息")
