"""Minimal, allow-listed reader for the public Ankama Cytrus CDN protocol.

This deliberately implements only the FlatBuffers fields required to fetch the
single WAKFU localization JAR. It never follows URLs embedded in a manifest.
"""
from __future__ import annotations

import hashlib
import json
import struct
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .errors import SchemaError, VerificationError

CDN_ORIGIN = "https://cytrus.cdn.ankama.com"
CDN_HOST = "cytrus.cdn.ankama.com"
GAME = "wakfu"
RELEASE = "main"
PLATFORM = "windows"
TARGET_PATH = "contents/i18n/i18n_en.jar"
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_CHUNK_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class Chunk:
    sha1: str
    size: int
    offset: int


@dataclass(frozen=True)
class FileEntry:
    name: str
    size: int
    sha1: str
    chunks: tuple[Chunk, ...]
    executable: bool
    symlink: str | None


@dataclass(frozen=True)
class Bundle:
    sha1: str
    chunks: tuple[Chunk, ...]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise VerificationError(f"redirect rejected for safety: HTTP {code} to {newurl}")


class _FlatBuffer:
    """Bounds-checked subset of FlatBuffers needed by Cytrus Manifest.fbs."""

    def __init__(self, data: bytes):
        if len(data) < 8:
            raise SchemaError("manifest is too small")
        self.data = data

    def _need(self, position: int, size: int) -> None:
        if position < 0 or size < 0 or position + size > len(self.data):
            raise SchemaError("manifest has an out-of-bounds FlatBuffers offset")

    def u16(self, position: int) -> int:
        self._need(position, 2)
        return struct.unpack_from("<H", self.data, position)[0]

    def u32(self, position: int) -> int:
        self._need(position, 4)
        return struct.unpack_from("<I", self.data, position)[0]

    def i32(self, position: int) -> int:
        self._need(position, 4)
        return struct.unpack_from("<i", self.data, position)[0]

    def i64(self, position: int) -> int:
        self._need(position, 8)
        return struct.unpack_from("<q", self.data, position)[0]

    def root_table(self) -> int:
        return self._indirect(0)

    def _indirect(self, position: int) -> int:
        target = position + self.u32(position)
        self._need(target, 4)
        return target

    def field(self, table: int, field_id: int) -> int | None:
        vtable = table - self.i32(table)
        self._need(vtable, 4)
        vtable_size = self.u16(vtable)
        slot = 4 + field_id * 2
        if slot + 2 > vtable_size:
            return None
        relative = self.u16(vtable + slot)
        if relative == 0:
            return None
        location = table + relative
        self._need(location, 1)
        return location

    def string(self, field_location: int | None) -> str | None:
        if field_location is None:
            return None
        start = self._indirect(field_location)
        length = self.u32(start)
        self._need(start + 4, length)
        try:
            return self.data[start + 4 : start + 4 + length].decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise SchemaError("manifest contains invalid UTF-8") from exc

    def byte_vector(self, field_location: int | None) -> bytes:
        if field_location is None:
            return b""
        start = self._indirect(field_location)
        length = self.u32(start)
        self._need(start + 4, length)
        return self.data[start + 4 : start + 4 + length]

    def table_vector(self, field_location: int | None) -> list[int]:
        if field_location is None:
            return []
        start = self._indirect(field_location)
        length = self.u32(start)
        if length > 2_000_000:
            raise SchemaError("manifest has an implausibly large table vector")
        first = start + 4
        self._need(first, length * 4)
        return [self._indirect(first + index * 4) for index in range(length)]


def _sha1(value: bytes) -> str:
    return hashlib.sha1(value).hexdigest()


def _parse_chunk(buffer: _FlatBuffer, table: int) -> Chunk:
    raw_hash = buffer.byte_vector(buffer.field(table, 0))
    size_location, offset_location = buffer.field(table, 1), buffer.field(table, 2)
    # FlatBuffers omits scalar fields equal to their default.  File-level
    # chunks only need hash/size; their bundle offset is normally omitted and
    # must therefore be read as the schema default of zero.
    if len(raw_hash) != 20 or size_location is None:
        raise SchemaError("manifest chunk does not match the expected schema")
    size, offset = buffer.i64(size_location), (buffer.i64(offset_location) if offset_location is not None else 0)
    if not 0 < size <= MAX_CHUNK_BYTES or offset < 0:
        raise SchemaError("manifest declares an invalid chunk range")
    return Chunk(raw_hash.hex(), size, offset)


def parse_manifest(data: bytes) -> tuple[tuple[FileEntry, ...], tuple[Bundle, ...]]:
    """Parse exactly the current Cytrus Manifest.fbs schema and fail closed."""
    if not data or len(data) > MAX_MANIFEST_BYTES:
        raise SchemaError("manifest length is invalid")
    buffer = _FlatBuffer(data)
    files: list[FileEntry] = []
    bundles: list[Bundle] = []
    root = buffer.root_table()
    for fragment in buffer.table_vector(buffer.field(root, 0)):
        for file_table in buffer.table_vector(buffer.field(fragment, 1)):
            name = buffer.string(buffer.field(file_table, 0))
            size_location = buffer.field(file_table, 1)
            raw_hash = buffer.byte_vector(buffer.field(file_table, 2))
            if name is None or size_location is None or len(raw_hash) != 20:
                raise SchemaError("manifest file does not match the expected schema")
            chunks = tuple(_parse_chunk(buffer, item) for item in buffer.table_vector(buffer.field(file_table, 3)))
            executable_location = buffer.field(file_table, 4)
            symlink = buffer.string(buffer.field(file_table, 5))
            size = buffer.i64(size_location)
            # Cytrus manifests also carry metadata-only entries (for example
            # directories/symlinks) that legitimately have a size but no
            # chunks.  The selected localization target is checked below as
            # a regular file and must have verified chunks before download.
            if size < 0:
                raise SchemaError("manifest file has an invalid size")
            files.append(FileEntry(name, size, raw_hash.hex(), chunks, bool(executable_location and buffer.data[executable_location]), symlink))
        for bundle_table in buffer.table_vector(buffer.field(fragment, 2)):
            raw_hash = buffer.byte_vector(buffer.field(bundle_table, 0))
            if len(raw_hash) != 20:
                raise SchemaError("manifest bundle lacks a SHA-1 hash")
            bundles.append(Bundle(raw_hash.hex(), tuple(_parse_chunk(buffer, item) for item in buffer.table_vector(buffer.field(bundle_table, 1)))))
    if not files or not bundles:
        raise SchemaError("manifest has no files or bundles")
    return tuple(files), tuple(bundles)


class AnkamaCdnClient:
    def __init__(self, *, timeout_seconds: int = 45):
        self.timeout_seconds = timeout_seconds
        self.opener = urllib.request.build_opener(_NoRedirect())

    @staticmethod
    def _url(path: str) -> str:
        if not path or path.startswith("/") or ".." in path.split("/"):
            raise VerificationError("unsafe CDN path")
        url = CDN_ORIGIN + "/" + path
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != CDN_HOST:
            raise VerificationError("CDN allow-list rejected URL")
        return url

    def _request(self, path: str, *, byte_range: tuple[int, int] | None = None) -> tuple[bytes, Any]:
        headers = {"User-Agent": "wakfu-translation-automation/1"}
        if byte_range is not None:
            headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
        request = urllib.request.Request(self._url(path), headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                final = urllib.parse.urlparse(response.geturl())
                if final.scheme != "https" or final.hostname != CDN_HOST:
                    raise VerificationError("redirect escaped CDN allow-list")
                payload = response.read(MAX_MANIFEST_BYTES if byte_range is None else MAX_CHUNK_BYTES + 1)
                return payload, response
        except urllib.error.HTTPError as exc:
            raise VerificationError(f"CDN request failed: HTTP {exc.code} for {path}") from exc

    def latest_version(self) -> str:
        payload, _ = self._request("cytrus.json")
        try:
            index = json.loads(payload.decode("utf-8"))
            version = index["games"][GAME]["platforms"][PLATFORM][RELEASE]
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SchemaError("cytrus.json does not have the expected WAKFU main/windows structure") from exc
        if not isinstance(version, str) or not version or "/" in version or ".." in version:
            raise SchemaError("CDN returned an unsafe WAKFU version")
        return version

    def manifest(self, version: str) -> tuple[tuple[FileEntry, ...], tuple[Bundle, ...]]:
        return parse_manifest(self._request(f"{GAME}/releases/{RELEASE}/{PLATFORM}/{version}.manifest")[0])

    def target_entry(self, version: str) -> tuple[FileEntry, dict[str, tuple[str, Chunk]]]:
        files, bundles = self.manifest(version)
        selected = [entry for entry in files if entry.name == TARGET_PATH]
        if len(selected) != 1:
            raise SchemaError(f"manifest did not contain exactly one {TARGET_PATH}")
        entry = selected[0]
        if entry.executable or entry.symlink:
            raise SchemaError("localization target must be a regular data file")
        if entry.size <= 0 or not entry.chunks:
            raise SchemaError("localization target has no verified content chunks")
        chunk_index: dict[str, tuple[str, Chunk]] = {}
        for bundle in bundles:
            for chunk in bundle.chunks:
                # A content-addressed chunk can be referenced by more than
                # one bundle/fragment. Any matching copy is acceptable: the
                # selected file chunk and the downloaded bytes are both SHA-1
                # verified before use. Keep the first deterministic entry.
                if chunk.sha1 not in chunk_index:
                    chunk_index[chunk.sha1] = (bundle.sha1, chunk)
        for chunk in entry.chunks:
            if chunk.sha1 not in chunk_index:
                raise SchemaError("localization file references a chunk absent from all bundles")
        return entry, chunk_index

    def download_localization(self, version: str, destination: Path) -> FileEntry:
        entry, chunk_index = self.target_entry(version)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            with temporary.open("wb") as output:
                for file_chunk in entry.chunks:
                    bundle_sha1, bundle_chunk = chunk_index[file_chunk.sha1]
                    if bundle_chunk.size != file_chunk.size:
                        raise SchemaError("file and bundle disagree on chunk size")
                    payload, response = self._request(
                        f"{GAME}/bundles/{bundle_sha1[:2]}/{bundle_sha1}",
                        byte_range=(bundle_chunk.offset, bundle_chunk.offset + bundle_chunk.size - 1),
                    )
                    content_range = response.headers.get("Content-Range", "")
                    expected_range = f"bytes {bundle_chunk.offset}-{bundle_chunk.offset + bundle_chunk.size - 1}/"
                    if response.status != 206 or not content_range.startswith(expected_range) or len(payload) != bundle_chunk.size:
                        raise VerificationError("CDN returned an incomplete or incorrect HTTP range")
                    if _sha1(payload) != file_chunk.sha1:
                        raise VerificationError("downloaded localization chunk SHA-1 mismatch")
                    output.write(payload)
                output.flush()
            if temporary.stat().st_size != entry.size or _sha1(temporary.read_bytes()) != entry.sha1:
                raise VerificationError("assembled i18n_en.jar SHA-1 mismatch")
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return entry
