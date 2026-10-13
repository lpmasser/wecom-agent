import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_fixtures import PNG, add_message, database, media_payload

from decrypt.local_files import open_files
from decrypt.local_io import connect_readonly
from decrypt.local_query import MessageStore
from decrypt.media_export import export_cache
from decrypt.media_manifest import CacheIndex, copy_cached
from decrypt.transcript_export import export_chat


class TranscriptExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.long = database(self.root)
        self.cache = self.root / "Caches"
        self.cache.mkdir()
        self.out = self.root / "out"
        self.out.mkdir()

    def add_media(self, lid, ct=14, *, identifier=None, name="image.png", body=PNG, month="2026-10", conv=101):
        identifier = identifier or f"{lid:032x}"
        sub = {14: "Images", 15: "Files", 16: "Voices", 29: "Emotions"}[ct]
        source = self.cache / sub / month / identifier / name
        source.parent.mkdir(parents=True, exist_ok=True)
        if body is not None:
            source.write_bytes(body)
        add_message(self.path, lid, ct, media_payload(identifier, name, emotion=ct == 29), conv=conv)
        return source

    def export(self, name="chat.html", **kwargs):
        with contextlib.closing(connect_readonly(self.path)) as conn:
            store = MessageStore(conn)
            return export_chat(store, self.path, "101", self.out / name, cache_root=self.cache, **kwargs)

    def manifest(self, result):
        return json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

    def test_html_links_only_selected_conversation_media_and_escapes_messages(self):
        self.add_media(10)
        self.add_media(11, conv=102)
        result = self.export(with_media=True)
        manifest = self.manifest(result)
        self.assertEqual(len(manifest["entries"]), 1)
        entry = manifest["entries"][0]
        self.assertEqual(entry["status"], "resolved")
        self.assertEqual(entry["message"]["local_id"], 10)
        self.assertEqual(entry["message"]["conversation_id"], "101")
        image = self.out / entry["files"][0]
        self.assertEqual(image.read_bytes(), PNG)
        content = Path(result["out"]).read_text(encoding="utf-8")
        self.assertIn("<img ", content)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", content)
        self.assertNotIn("<script>", content)
        serialized = json.dumps(manifest)
        for forbidden in (str(self.cache), "private-remote-key", "private-cdn", "https://", "_raw"):
            self.assertNotIn(forbidden, serialized)

    def test_all_export_formats_preserve_complete_text(self):
        self.add_media(10, name="空 格图.png")
        for suffix in ("txt", "md", "html", "json", "csv"):
            with self.subTest(format=suffix):
                result = self.export("chat." + suffix, with_media=True)
                text = Path(result["out"]).read_text(encoding="utf-8")
                self.assertIn("完整正文" * 600, text)
                self.assertIn("尾部关键字", text)
                self.assertNotIn("_raw", text)
                if suffix in ("md", "html"):
                    self.assertIn("%E7%A9%BA%20", text)
                if suffix == "json":
                    self.assertEqual(next(r["content"] for r in json.loads(text) if r["local_id"] == 1), self.long)

    def test_missing_encrypted_and_unsupported_have_explicit_statuses(self):
        self.add_media(10, body=None)
        self.add_media(11, body=b"encrypted_image_header")
        add_message(self.path, 12, 14, b"invalid protobuf")
        result = self.export(with_media=True)
        states = {e["message"]["local_id"]: e["status"] for e in self.manifest(result)["entries"]}
        self.assertEqual(states, {10: "not_found", 11: "encrypted_unsupported", 12: "unsupported"})
        self.assertIsNone(result["assets_directory"])

    def test_repeated_exports_have_distinct_asset_directories(self):
        self.add_media(10)
        first = self.export(with_media=True)
        first_paths = self.manifest(first)["entries"][0]["files"]
        second = self.export(with_media=True)
        self.assertNotEqual(first["assets_directory"], second["assets_directory"])
        self.assertTrue((self.out / first_paths[0]).exists())
        self.assertTrue((self.out / self.manifest(second)["entries"][0]["files"][0]).exists())

    def test_same_basename_uses_resource_ids_instead_of_largest_file(self):
        first = self.add_media(10, 15, name="report.txt", body=b"first")
        second = self.add_media(11, 15, name="report.txt", body=b"second larger contents")
        result = self.export(with_media=True)
        entries = self.manifest(result)["entries"]
        self.assertEqual([e["status"] for e in entries], ["resolved", "resolved"])
        self.assertNotEqual(entries[0]["files"], entries[1]["files"])
        with contextlib.closing(connect_readonly(self.path)) as conn:
            files = open_files(MessageStore(conn), self.cache, "report")
        self.assertEqual([f["local"] for f in files["files"]], [str(first.resolve()), str(second.resolve())])
        self.assertEqual([f["content"] for f in files["files"]], ["first", "second larger contents"])

    def test_different_same_resource_cache_copies_are_ambiguous(self):
        source = self.add_media(10, 15, name="report.txt", body=b"one")
        other = self.cache / "Files" / "2026-09" / source.parent.name / source.name
        other.parent.mkdir(parents=True)
        other.write_bytes(b"different")
        result = self.export(with_media=True)
        self.assertEqual(self.manifest(result)["entries"][0]["status"], "ambiguous")
        with contextlib.closing(connect_readonly(self.path)) as conn:
            files = open_files(MessageStore(conn), self.cache, "report")
        self.assertIsNone(files["files"][0]["content"])

    def test_identical_cache_copies_are_safe_to_resolve(self):
        source = self.add_media(10)
        other = self.cache / "Images" / "2026-09" / source.parent.name / source.name
        other.parent.mkdir(parents=True)
        other.write_bytes(PNG)
        self.assertEqual(self.manifest(self.export(with_media=True))["entries"][0]["status"], "resolved")

    def test_plain_dat_is_detected_by_signature_and_voice_is_linked(self):
        self.add_media(10, name="image.dat")
        self.add_media(11, 16, name="voice.silk", body=b"#!SILK_V3synthetic")
        entries = self.manifest(self.export(with_media=True))["entries"]
        self.assertTrue(entries[0]["files"][0].endswith(".dat.png"))
        self.assertEqual(entries[1]["kind"], "voice")
        self.assertEqual(entries[1]["status"], "resolved")

    def test_emotion_cache_is_linked_without_exporting_remote_cdn_credentials(self):
        self.add_media(10, 29, name="emotion.gif", body=b"GIF89a" + b"synthetic")
        result = self.export(with_media=True)
        self.assertEqual(self.manifest(result)["entries"][0]["status"], "resolved")
        self.assertNotIn("private-cdn", Path(result["out"]).read_text(encoding="utf-8"))

    def test_no_media_flag_creates_no_assets_or_manifest(self):
        self.add_media(10)
        result = self.export()
        self.assertIsNone(result["manifest"])
        self.assertEqual([p.name for p in self.out.iterdir()], ["chat.html"])

    def test_unknown_and_ambiguous_conversation_fail_before_creating_output(self):
        with contextlib.closing(connect_readonly(self.path)) as conn:
            for query in ("重名", "missing"):
                with self.subTest(query=query), self.assertRaises(ValueError):
                    export_chat(MessageStore(conn), self.path, query, self.out / "bad.html", with_media=True, cache_root=self.cache)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_source_database_cannot_be_overwritten(self):
        before = self.path.read_bytes()
        with contextlib.closing(connect_readonly(self.path)) as conn, self.assertRaises(ValueError):
            export_chat(MessageStore(conn), self.path, "101", self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_traversal_in_message_filename_is_rejected(self):
        add_message(self.path, 10, 15, media_payload("a" * 32, "../secret.txt"))
        result = self.export(with_media=True)
        self.assertEqual(self.manifest(result)["entries"][0]["status"], "unsupported")

    @unittest.skipIf(os.name == "nt", "symlink privilege is not available on every Windows runner")
    def test_source_and_output_symlinks_do_not_escape(self):
        source = self.add_media(10)
        outside = self.root / "outside"
        outside.mkdir()
        secret = outside / "secret.png"
        secret.write_bytes(PNG)
        source.unlink()
        source.symlink_to(secret)
        self.assertEqual(len(CacheIndex(self.cache).by_id), 0)
        source.unlink()
        source.write_bytes(PNG)
        destination = self.out / "assets"
        destination.mkdir()
        (destination / "Images").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            copy_cached(source, self.cache, destination, image=True)
        self.assertEqual(list(outside.iterdir()), [secret])

    def test_source_changes_during_copy_do_not_publish_partial_image(self):
        source = self.add_media(10)
        import decrypt.media_manifest as media
        original = media.shutil.copyfileobj

        def changing(stream, output):
            original(stream, output)
            source.write_bytes(PNG + b"changed")

        with patch.object(media.shutil, "copyfileobj", side_effect=changing), self.assertRaises(OSError):
            copy_cached(source, self.cache, self.out / "assets", image=True)
        self.assertFalse(any(p.is_file() for p in self.out.rglob("*")))

    def test_stable_image_voice_and_document_copy_succeed(self):
        for lid, ct, name, body in [(10, 14, "img.png", PNG), (11, 16, "voice.silk", b"#!SILK_V3synthetic"),
                                    (12, 15, "report.txt", b"synthetic document")]:
            with self.subTest(kind=ct):
                source = self.add_media(lid, ct, name=name, body=body)
                before = source.stat()
                try:
                    copied = copy_cached(source, self.cache, self.out / "assets", image=ct == 14)
                except OSError as error:
                    after = source.stat()
                    with source.open("rb") as stream:
                        handle = os.fstat(stream.fileno())
                    self.fail(f"{error}; path before={before}; path after={after}; file handle={handle}")
                self.assertEqual((self.out / "assets" / copied).read_bytes(), body)

    def test_changed_shared_resource_never_overwrites_an_already_exported_asset(self):
        source = self.add_media(10)
        destination = self.out / "assets"
        relative = copy_cached(source, self.cache, destination, image=True)
        source.write_bytes(PNG + b"changed resource")
        with self.assertRaises(OSError):
            copy_cached(source, self.cache, destination, image=True)
        self.assertEqual((destination / relative).read_bytes(), PNG)

    def test_stat_and_fstat_precision_difference_does_not_reject_stable_file(self):
        import decrypt.media_manifest as media
        source = self.add_media(10)
        original = media._fingerprint

        def lower_precision(path):
            dev, ino, size, mtime, ctime = original(path)
            return dev, ino, size, mtime - mtime % 1000000000, ctime - ctime % 1000000000

        with patch.object(media, "_fingerprint", side_effect=lower_precision):
            relative = copy_cached(source, self.cache, self.out / "assets", image=True)
        self.assertEqual((self.out / "assets" / relative).read_bytes(), PNG)

    def test_bulk_media_preserves_nested_paths_and_excludes_its_own_output(self):
        self.add_media(10, 15, name="report.txt", body=b"one")
        self.add_media(11, 15, name="report.txt", body=b"two")
        output = self.cache / "Files" / "exported"
        result = export_cache(self.cache, output, ("Files",))
        self.assertEqual(result["total"], 2)
        self.assertEqual(sorted(p.read_bytes() for p in output.rglob("report.txt")), [b"one", b"two"])
        again = export_cache(self.cache, output, ("Files",))
        self.assertEqual(again["total"], 2)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_transcript_manifest_and_assets_are_private(self):
        self.add_media(10)
        result = self.export(with_media=True)
        for path in [Path(result["out"]), Path(result["manifest"]), *[p for p in (self.out / result["assets_directory"]).rglob("*") if p.is_file()]]:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        for path in (self.out / result["assets_directory"]).rglob("*"):
            if path.is_dir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
