"""Synthetic native schemas. No user records, keys or cached media."""

import base64
import contextlib
import sqlite3
import time
from pathlib import Path

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9ZkAAAAASUVORK5CYII=")


def varint(number):
    out = bytearray()
    while number > 127:
        out.append((number & 127) | 128)
        number >>= 7
    return bytes(out + bytes([number]))


def pb(*items):
    out = b""
    for number, value in items:
        if isinstance(value, str):
            value = value.encode()
        if isinstance(value, int):
            out += varint(number << 3) + varint(value)
        else:
            out += varint((number << 3) | 2) + varint(len(value)) + value
    return out


def media_payload(identifier, name="image.png", *, emotion=False):
    if emotion:
        return pb((1, "https://invalid.example/private-cdn"), (6, identifier))
    return pb((1, "private-remote-key-must-not-appear"), (2, name), (8, "f" * 32), (10, identifier))


def database(root, *, windows=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / ("message.db" if windows else "Info.db")
    conn = sqlite3.connect(path)
    if windows:
        conn.execute("CREATE TABLE message_table(message_id INTEGER PRIMARY KEY, server_id INTEGER, conversation_id TEXT, sender_id INTEGER, content_type INTEGER, send_time INTEGER, content BLOB)")
    else:
        conn.execute("CREATE TABLE MESSAGE(LID INTEGER PRIMARY KEY, RID INTEGER, conv_id INTEGER, sender_id INTEGER, content_type INTEGER, send_time INTEGER, content BLOB)")
        conn.execute("CREATE TABLE CONVERSATION(LID INTEGER, RID INTEGER, name TEXT)")
        conn.executemany("INSERT INTO CONVERSATION VALUES (?,?,?)", [(1, 101, "项目"), (2, 102, "重名"), (3, 103, "重名")])
    now = int(time.time())
    long = "  第一行\n" + "完整正文" * 600 + "\n尾部关键字<script>alert(1)</script>  "
    rows = [(1, 1001, 101, 11, 0, now - 10, long), (2, 1002, 101, 2, 2, now - 9, "后续消息"),
            (3, 1003, 102, 11, 0, now - 8, "同名群甲"), (4, 1004, 103, 12, 0, now - 8, "同名群乙"),
            (5, 1005, 101, 0, 0, now - 86400 * 60, "旧消息")]
    table = "message_table" if windows else "MESSAGE"
    conn.executemany(f"INSERT INTO {table} VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return path, long


def add_message(path, local_id, kind, payload, *, conv=101):
    with contextlib.closing(sqlite3.connect(path)) as conn, conn:
        table = "message_table" if path.name == "message.db" else "MESSAGE"
        conn.execute(f"INSERT INTO {table} VALUES (?,?,?,?,?,?,?)",
                     (local_id, 10000 + local_id, conv, 11, kind, int(time.time()), payload))
