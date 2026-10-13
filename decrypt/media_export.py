#!/usr/bin/env python3
"""Shared media export helpers."""
import hashlib
import os
import shutil
from pathlib import Path


def copy_unique(src, dst_dir):
    """Copy src into dst_dir without overwriting an existing same-name file."""
    src = Path(src)
    dst_dir = Path(dst_dir)
    if src.is_symlink():
        raise ValueError("refusing to export a symlink")
    dst_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = dst_dir / src.name
    if target.exists():
        digest = hashlib.blake2s(str(src).encode("utf-8", "surrogateescape"), digest_size=4).hexdigest()
        stem, suffix = src.stem, src.suffix
        target = dst_dir / f"{stem}_{digest}{suffix}"
        i = 2
        while target.exists():
            target = dst_dir / f"{stem}_{digest}_{i}{suffix}"
            i += 1
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output, src.open("rb") as source:
            shutil.copyfileobj(source, output)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def export_cache(cache_root, output, subdirectories):
    """Keep the cache-relative hierarchy and exclude symlinks / nested output."""
    cache_root, output = Path(cache_root).resolve(), Path(output).expanduser().resolve()
    if cache_root == output:
        raise ValueError("媒体输出目录不能是原缓存目录")
    counts = {}
    for sub in subdirectories:
        root = cache_root / sub
        count = 0
        if not root.is_dir() or root.is_symlink():
            continue
        for parent, directories, files in os.walk(root, followlinks=False):
            directories[:] = [d for d in directories if not (Path(parent) / d).is_symlink()
                              and not (Path(parent) / d).resolve().is_relative_to(output)]
            for name in files:
                source = Path(parent) / name
                if (name == ".DS_Store" or source.is_symlink() or not source.is_file()
                        or source.resolve().is_relative_to(output)):
                    continue
                destination = output / source.relative_to(cache_root).parent
                if not destination.resolve().is_relative_to(output):
                    raise ValueError("媒体输出路径越界")
                copy_unique(source, destination)
                count += 1
        counts[sub] = count
    return {"out": str(output), "total": sum(counts.values()), **counts}
