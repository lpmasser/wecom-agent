"""Conversation-scoped transcript exports with relative local media references."""

import csv
import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

try:
    from .local_io import atomic_output
    from .local_query import public_message
    from .media_manifest import export_media
except ImportError:
    from local_io import atomic_output
    from local_query import public_message
    from media_manifest import export_media


def _markdown(value):
    result = str(value)
    for character in "\\`*_{}[]()<>#!|":
        result = result.replace(character, "\\" + character)
    return result


def render(rows, output_format, title, entries):
    media = {(e["message"]["table"], str(e["message"]["conversation_id"]), str(e["message"]["local_id"])): e
             for e in entries}
    if output_format == "html":
        yield ('<!doctype html><html lang="zh"><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width,initial-scale=1">'
               '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' data:; style-src \'unsafe-inline\'">'
               '<title>' + html.escape(title) + '</title><style>'
               'body{font:16px/1.6 system-ui;max-width:900px;margin:2rem auto;padding:0 1rem}'
               'article{border-bottom:1px solid #ddd;padding:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
               'img{max-width:100%;max-height:600px}small{color:#555}</style><h1>' + html.escape(title) + '</h1>\n')
    else:
        yield (_markdown(title) if output_format == "markdown" else title) + "\n\n"
    for row in rows:
        label = f"[{row['time']}] {row['sender']} [{row['type']}]"
        entry = media.get((row["table"], str(row["conv_id"]), str(row["local_id"])))
        if output_format == "html":
            yield "<article><small>" + html.escape(label) + "</small><pre>" + html.escape(row["content"]) + "</pre>\n"
        elif output_format == "markdown":
            yield "**" + _markdown(label) + "**\n\n" + _markdown(row["content"]) + "\n\n"
        else:
            yield label + "\n" + row["content"] + "\n"
        if entry:
            for path in entry["files"]:
                url = quote(path, safe="/")
                if output_format == "html":
                    if entry["kind"] == "image":
                        yield '<img alt="本地图片" loading="lazy" src="' + html.escape(url, quote=True) + '">\n'
                    else:
                        yield '<a download href="' + html.escape(url, quote=True) + '">' + html.escape(Path(path).name) + '</a>\n'
                elif output_format == "markdown":
                    yield ("![本地图片]" if entry["kind"] == "image" else "[本地附件]") + "(" + url + ")\n\n"
                else:
                    yield "本地附件: " + path + "\n"
            if entry["status"] != "resolved":
                status = f"[{entry['status']}: {entry['reason']}]"
                yield ("<p>" + html.escape(status) + "</p>\n") if output_format == "html" else status + "\n"
        yield "</article>\n" if output_format == "html" else "\n"
    if output_format == "html":
        yield "</html>\n"


def export_chat(store, database, conversation, output_path, *, days=None, output_format=None,
                with_media=False, cache_root=None):
    target = store.target(conversation)
    output_path = Path(output_path).expanduser().absolute()
    if output_path.resolve() == Path(database).resolve() or output_path.suffix.lower() == ".db":
        raise ValueError("导出文件不能覆盖消息数据库")
    output_format = output_format or {".md": "markdown", ".html": "html", ".htm": "html",
                                      ".json": "json", ".csv": "csv"}.get(output_path.suffix.lower(), "txt")
    if output_format not in ("txt", "markdown", "html", "json", "csv"):
        raise ValueError("不支持的导出格式")
    rows = list(store.iter_messages(conversation=target["id"], days=days))
    manifest = export_media(rows, database, cache_root, output_path) if with_media else None
    entries = manifest["entries"] if manifest else []
    with atomic_output(output_path, newline="" if output_format == "csv" else None) as stream:
        if output_format == "json":
            json.dump([public_message(r, redact=False) for r in rows], stream, ensure_ascii=False, indent=2)
        elif output_format == "csv":
            stream.write("\ufeff")
            columns = ["time", "conversation", "conv_id", "sender", "sender_id", "type", "type_code", "content", "table", "local_id", "server_id"]
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        else:
            stream.writelines(render(rows, output_format, target["name"], entries))
    manifest_path = output_path.with_suffix(".media.json") if manifest else None
    if manifest_path == output_path:
        manifest_path = output_path.with_name(output_path.name + ".media.json")
    if manifest:
        with atomic_output(manifest_path) as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return {"conversation": target, "messages": len(rows), "out": str(output_path),
            "format": output_format, "manifest": str(manifest_path) if manifest_path else None,
            "assets_directory": manifest["assets_directory"] if manifest else None,
            "media": dict(Counter(e["status"] for e in entries))}


def export_all(store, output, *, days=None, chinese_headers=False):
    """Stream both legacy exports without loading the entire history into RAM."""
    output = Path(output).expanduser()
    columns = ["time", "conversation", "conv_id", "sender", "sender_id", "type", "type_code", "content", "table", "local_id", "server_id"]
    headers = ["时间", "会话", "会话ID", "发送者", "发送者ID", "类型", "type码", "正文", "来源表", "本地消息ID", "服务端消息ID"] if chinese_headers else columns
    count = 0
    with atomic_output(output / "messages.json") as jf, atomic_output(output / "messages.csv", newline="") as cf:
        cf.write("\ufeff")
        writer = csv.writer(cf)
        writer.writerow(headers)
        jf.write("[\n")
        for row in store.iter_messages(days=days):
            writer.writerow([row.get(c) for c in columns])
            if count:
                jf.write(",\n")
            json.dump(public_message(row, redact=False), jf, ensure_ascii=False)
            count += 1
        jf.write("\n]\n")
    return {"messages": count, "out": str(output), "files": ["messages.json", "messages.csv"]}
