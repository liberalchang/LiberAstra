from __future__ import annotations

import hashlib
import io
import json

import files
import pytest


def test_save_resolve_delete(tmp_path) -> None:
    store = files.FileStore(root=tmp_path, max_bytes=0, ttl_seconds=3600)
    data = b"hello" * 1000
    record = store.save(io.BytesIO(data), "../../evil.wav")
    assert record.filename == "evil.wav"
    assert record.size == len(data)
    assert record.sha256 == hashlib.sha256(data).hexdigest()
    assert store.resolve(record.file_id).read_bytes() == data

    public = record.public()
    assert public["file_id"] == record.file_id
    assert public["filename"] == "evil.wav"
    assert public["size"] == len(data)
    assert public["sha256"] == record.sha256
    assert public["expires_at"]

    assert store.delete(record.file_id) is True
    with pytest.raises(files.FileStoreError) as info:
        store.record(record.file_id)
    assert info.value.code == "file_not_found"


def test_streaming_reads_in_chunks(tmp_path) -> None:
    class Chunked:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self._pos = 0
            self.read_sizes: list[int] = []

        def read(self, size: int = -1) -> bytes:
            self.read_sizes.append(size)
            end = self._pos + size if size >= 0 else len(self._data)
            chunk = self._data[self._pos : end]
            self._pos += len(chunk)
            return chunk

    data = b"x" * 5000
    reader = Chunked(data)
    store = files.FileStore(root=tmp_path, max_bytes=0, ttl_seconds=3600, chunk_size=1024)
    record = store.save(reader, "a.wav")
    assert record.size == len(data)
    assert reader.read_sizes
    assert max(reader.read_sizes) <= 1024


def test_empty_file_and_optional_limit(tmp_path) -> None:
    store = files.FileStore(root=tmp_path, max_bytes=0, ttl_seconds=3600)
    with pytest.raises(files.FileStoreError) as info:
        store.save(io.BytesIO(b""), "empty.wav")
    assert info.value.code == "empty_file"

    limited = files.FileStore(root=tmp_path, max_bytes=10, ttl_seconds=3600)
    with pytest.raises(files.FileStoreError) as info:
        limited.save(io.BytesIO(b"x" * 11), "a.wav")
    assert info.value.code == "upload_limit_exceeded"


def test_ttl_expiry_deletes_file(tmp_path) -> None:
    store = files.FileStore(root=tmp_path, max_bytes=0, ttl_seconds=60)
    record = store.save(io.BytesIO(b"data"), "a.wav")
    meta_path = tmp_path / f"{record.file_id}.json"
    meta = json.loads(meta_path.read_text())
    meta["expires_at"] = "2000-01-01T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(files.FileStoreError) as info:
        store.record(record.file_id)
    assert info.value.code == "file_expired"
    assert not (tmp_path / f"{record.file_id}.wav").exists()


def test_cleanup_expired(tmp_path) -> None:
    store = files.FileStore(root=tmp_path, max_bytes=0, ttl_seconds=60)
    old = store.save(io.BytesIO(b"old"), "old.wav")
    keep = store.save(io.BytesIO(b"keep"), "keep.wav")
    meta_path = tmp_path / f"{old.file_id}.json"
    meta = json.loads(meta_path.read_text())
    meta["expires_at"] = "2000-01-01T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    assert store.cleanup_expired() == 1
    with pytest.raises(files.FileStoreError):
        store.record(old.file_id)
    assert store.record(keep.file_id).size == 4


def test_invalid_file_id(tmp_path) -> None:
    store = files.FileStore(root=tmp_path, max_bytes=0, ttl_seconds=3600)
    with pytest.raises(files.FileStoreError) as info:
        store.record("../etc/passwd")
    assert info.value.code == "invalid_file_id"
