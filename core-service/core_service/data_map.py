"""KARMO's data map: a catalog of where Kamara's files are (NAS and other
read-only sources), so "where are my 2024 BloomBoss invoices?" is answered
from the map in about a second, and a file's contents are opened only when
a question actually needs them.

The scan reads directory entries and file metadata only -- never file
contents -- so it scales to many terabytes; the cost is one stat() per
file. Rescans are incremental: unchanged rows only get last_seen_at
bumped, files that disappeared are marked missing (never deleted), and a
label Kamara set by hand is never overwritten by the rules.

Usage on AI01 (run by Kamara; no timer is installed):
    python3 -m core_service.data_map scan [--source nas]
    python3 -m core_service.data_map stats
    python3 -m core_service.data_map find 2024 bloomboss invoices
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

DEFAULT_CONFIG_FILE = "/etc/karmo/core/data_map.json"
DEFAULT_READER_DSN_FILE = "/etc/karmo/core/postgres.dsn"
DEFAULT_WRITER_DSN_FILE = "/etc/karmo/core/data-map-writer.dsn"
DEFAULT_UPLOAD_ROOT = "/var/lib/karmo/uploads"
UPLOAD_SOURCE = "uploads"
MAX_UPLOAD_BYTES = 14_000_000
_SNIFF_BYTES = 8192
BATCH_SIZE = 5000
MAX_FIND_RESULTS = 10

# Never catalogued: NAS/OS housekeeping folders, and anything that looks
# like employer data (standing rule: no SDCCD data in KARMO).
SKIP_DIR_NAMES = frozenset({
    "@eadir", "#recycle", "#snapshot", ".snapshot", ".snapshots", "@recycle", ".trash", ".trashes",
    ".spotlight-v100", ".fseventsd", ".documentrevisions-v100", "$recycle.bin", "system volume information",
    "lost+found", ".git", "node_modules", "__pycache__", ".venv", "venv",
})
EXCLUDED_PATH = re.compile(r"sdccd", re.IGNORECASE)

KINDS = {
    "document": {"pdf", "doc", "docx", "txt", "md", "rtf", "odt", "pages", "epub", "html", "htm"},
    "spreadsheet": {"csv", "tsv", "xls", "xlsx", "xlsm", "ods", "numbers"},
    "presentation": {"ppt", "pptx", "key", "odp"},
    "photo": {"jpg", "jpeg", "png", "heic", "heif", "gif", "webp", "tif", "tiff", "bmp", "raw", "cr2", "cr3",
              "nef", "arw", "dng", "orf", "rw2"},
    "video": {"mp4", "mov", "m4v", "mkv", "avi", "wmv", "webm", "mts", "m2ts", "3gp"},
    "audio": {"mp3", "m4a", "wav", "flac", "aac", "ogg", "opus", "aiff", "wma"},
    "email": {"eml", "msg", "mbox", "pst", "ost"},
    "archive": {"zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "rar", "iso", "dmg", "img", "vmdk", "qcow2", "ova"},
    "code": {"py", "js", "ts", "go", "rs", "java", "c", "cpp", "h", "sh", "ps1", "rb", "php", "sql", "ipynb"},
    "config": {"cfg", "conf", "ini", "yaml", "yml", "json", "toml", "xml", "env", "pcap", "pcapng"},
}
_KIND_BY_EXT = {ext: kind for kind, exts in KINDS.items() for ext in exts}

LABELS = ("BloomBoss", "Lab", "Personal", "Photos", "Media", "Archive", "Unsorted")
# First match wins; matched against the folder path (not the file name
# alone) so a whole folder lands under one label.
_LABEL_RULES = (
    ("BloomBoss", re.compile(r"bloom\s*boss|plant|nursery|garden|palmstreet|emgarden|succulent", re.I)),
    ("Lab", re.compile(r"karmo|homelab|\blab\b|network|router|switch|cisco|firewall|proxmox|vmware|server|"
                       r"devasc|ccna|ccnp|configs?\b|scripts?\b", re.I)),
    ("Personal", re.compile(r"personal|family|tax(es)?\b|medical|health|insurance|bank|finance|receipts?|"
                            r"resume|passport|legal|house|home\s*docs|car\b|school", re.I)),
    ("Photos", re.compile(r"photos?\b|pictures?|dcim|camera|iphone|screenshots?", re.I)),
    ("Media", re.compile(r"movies?|videos?|music|tv\s*shows?|podcasts?|media\b", re.I)),
    ("Archive", re.compile(r"backups?\b|archives?\b|\bold\b|time\s*machine", re.I)),
)
_LABEL_BY_KIND = {"photo": "Photos", "video": "Media", "audio": "Media", "archive": "Archive"}


class DataMapError(RuntimeError):
    pass


@dataclass(frozen=True)
class Source:
    name: str
    root: Path
    label: str | None = None  # forces every file in this source to one label


@dataclass(frozen=True)
class CatalogEntry:
    rel_path: str
    name: str
    ext: str
    kind: str
    label: str
    size_bytes: int
    modified_at: datetime


def classify(rel_path: str, forced_label: str | None = None) -> tuple[str, str, str]:
    """Returns (ext, kind, label) from the path alone -- no file contents."""
    name = rel_path.rsplit("/", 1)[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name.lstrip(".") else ""
    kind = _KIND_BY_EXT.get(ext, "other")
    if forced_label:
        return ext, kind, forced_label
    folder = rel_path.rsplit("/", 1)[0] if "/" in rel_path else ""
    for haystack in (folder, name):
        for label, pattern in _LABEL_RULES:
            if pattern.search(haystack):
                return ext, kind, label
    return ext, kind, _LABEL_BY_KIND.get(kind, "Unsorted")


def load_sources(config_file: str = DEFAULT_CONFIG_FILE) -> list[Source]:
    try:
        data = json.loads(Path(config_file).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataMapError(f"data map config not found: {config_file}") from exc
    except (OSError, ValueError) as exc:
        raise DataMapError(f"data map config unreadable: {type(exc).__name__}") from exc
    sources = []
    for item in data.get("sources") or []:
        name, root, label = item.get("name"), item.get("root"), item.get("label")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_-]{1,40}", name):
            raise DataMapError(f"invalid source name: {name!r}")
        if not isinstance(root, str) or not os.path.isabs(root):
            raise DataMapError(f"source {name}: root must be an absolute path")
        if label is not None and label not in LABELS:
            raise DataMapError(f"source {name}: label must be one of {', '.join(LABELS)}")
        sources.append(Source(name=name, root=Path(root), label=label))
    if not sources:
        raise DataMapError("data map config lists no sources")
    return sources


def walk(source: Source, stats: dict | None = None) -> Iterator[CatalogEntry]:
    """Yields one entry per regular file under source.root. Never follows
    symlinks and never opens a file. Unreadable folders are counted and
    skipped rather than stopping the scan."""
    stats = stats if stats is not None else {}
    root = str(source.root)
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                children = list(entries)
        except OSError:
            stats["unreadable_dirs"] = stats.get("unreadable_dirs", 0) + 1
            continue
        for entry in children:
            rel_path = os.path.relpath(entry.path, root).replace(os.sep, "/")
            if EXCLUDED_PATH.search(rel_path):
                stats["excluded"] = stats.get("excluded", 0) + 1
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() not in SKIP_DIR_NAMES:
                        pending.append(entry.path)
                    continue
                info = entry.stat(follow_symlinks=False)
            except OSError:
                stats["unreadable_files"] = stats.get("unreadable_files", 0) + 1
                continue
            if not stat.S_ISREG(info.st_mode) or entry.name.startswith("._") or entry.name == ".DS_Store":
                continue
            ext, kind, label = classify(rel_path, source.label)
            yield CatalogEntry(
                rel_path=rel_path, name=entry.name, ext=ext, kind=kind, label=label,
                size_bytes=info.st_size,
                modified_at=datetime.fromtimestamp(info.st_mtime, tz=timezone.utc),
            )


# File signatures, so a file is typed by what it is rather than only by
# its name (a phone may send "document" with no extension).
_MAGIC = (
    (b"%PDF-", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF8", "gif"),
    (b"PK\x03\x04", "zip"),
    (b"\xd0\xcf\x11\xe0", "doc"),
    (b"ID3", "mp3"),
    (b"RIFF", "wav"),
    (b"\x1f\x8b", "gz"),
)
_OOXML = {"word/": "docx", "xl/": "xlsx", "ppt/": "pptx"}
_TEXT_EXTS = KINDS["document"] | KINDS["spreadsheet"] | KINDS["config"] | {"txt", "md", "csv", "log"}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")
MAX_NOTE_CHARS = 60


def sniff_ext(head: bytes, name: str) -> str:
    """The file's real extension: its signature when recognised, else
    its name's extension. ISO-BMFF ('ftyp') files are photo or video by
    brand."""
    name = Path(str(name)).name
    named = name.rsplit(".", 1)[-1].lower() if "." in name.lstrip(".") else ""
    if not re.fullmatch(r"[a-z0-9]{1,10}", named):
        named = ""
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        return "heic" if brand in (b"heic", b"heix", b"mif1") else (named if named in KINDS["video"] else "mp4")
    for signature, ext in _MAGIC:
        if head.startswith(signature):
            if ext == "zip":
                for marker, office in _OOXML.items():
                    if marker.encode() in head:
                        return office
                return named if named in {"docx", "xlsx", "pptx", "odt", "ods", "epub", "numbers", "pages", "key"} else "zip"
            if ext == "jpg" and named in {"jpg", "jpeg"}:
                return named
            if ext == "wav" and head[8:12] != b"WAVE":
                return named or "bin"
            return ext
    return named


def safe_upload_name(name: str, ext: str, note: str = "") -> str:
    """Kamara's note, if any, leads the stored name ("begonia palmstreet
    live - IMG_7961.jpg"), so the data map's search and the label rules
    see it with no extra column."""
    base = _SAFE_NAME.sub("_", Path(str(name)).name).strip(" ._") or "upload"
    stem = base.rsplit(".", 1)[0] if "." in base else base
    note = " ".join(re.findall(r"[A-Za-z0-9]+", str(note or "")))[:MAX_NOTE_CHARS].strip()
    if note:
        stem = f"{note} - {stem[:120]}"
    return f"{stem[:185]}.{ext}" if ext else stem[:185]


def classify_upload(name: str, data: bytes, note: str = "") -> tuple[str, str, str]:
    """(file name to store, kind, label) for an uploaded file: type from
    its signature, label from its name, and -- for text files -- its
    first few KB, since a CSV named "export.csv" may be a BloomBoss
    order list."""
    ext = sniff_ext(data[:_SNIFF_BYTES], name)
    stored = safe_upload_name(name, ext, note)
    _ext, kind, label = classify(stored)
    if label in ("Unsorted", "Photos", "Media", "Archive") and ext in _TEXT_EXTS:
        text = data[:_SNIFF_BYTES].decode("utf-8", errors="ignore")
        for candidate, pattern in _LABEL_RULES:
            if candidate in ("BloomBoss", "Lab", "Personal") and pattern.search(text):
                label = candidate
                break
    return stored, kind, label


def _unique_path(folder: Path, name: str) -> Path:
    path = folder / name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    counter = 1
    while path.exists():
        counter += 1
        path = folder / (f"{stem}-{counter}.{ext}" if ext else f"{stem}-{counter}")
    return path


def store_upload(name: str, data: bytes, *, note: str = "", upload_root: str = DEFAULT_UPLOAD_ROOT,
                 store: "CatalogStore | None" = None, now: datetime | None = None) -> dict:
    """Saves an uploaded file under <upload_root>/<Label>/<YYYY-MM>/ and
    adds it to the catalog when a writer is available (otherwise the next
    scan of the "uploads" source picks it up, with the same label, since
    the label folder decides it)."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise DataMapError("the file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DataMapError(f"files over {MAX_UPLOAD_BYTES // 1_000_000} MB go on the NAS instead")
    now = now or datetime.now(timezone.utc)
    stored, kind, label = classify_upload(name, bytes(data), note)
    folder = Path(upload_root) / label / f"{now:%Y-%m}"
    folder.mkdir(parents=True, exist_ok=True)
    path = _unique_path(folder, stored)
    with open(path, "xb") as handle:
        handle.write(data)
    os.chmod(path, 0o640)
    rel_path = path.relative_to(upload_root).as_posix()
    entry_id = None
    if store is not None:
        ext, kind, _label = classify(rel_path)
        entry_id = store.upsert(UPLOAD_SOURCE, CatalogEntry(
            rel_path=rel_path, name=path.name, ext=ext, kind=kind, label=label,
            size_bytes=len(data), modified_at=now,
        ))
    return {"id": entry_id, "path": rel_path, "name": path.name, "kind": kind, "label": label,
            "size_bytes": len(data)}


def relabel_upload(rel_path: str, label: str, *, upload_root: str = DEFAULT_UPLOAD_ROOT,
                   store: "CatalogStore | None" = None) -> dict:
    """Kamara's one-tap fix: moves an uploaded file to another label's
    folder and records the label as his, so no rescan changes it."""
    if label not in LABELS:
        raise DataMapError(f"label must be one of {', '.join(LABELS)}")
    root = Path(upload_root).resolve()
    current = (root / rel_path).resolve()
    if root not in current.parents or not current.is_file():
        raise DataMapError("no such uploaded file")
    folder = root / label / current.parent.name
    folder.mkdir(parents=True, exist_ok=True)
    target = _unique_path(folder, current.name)
    current.rename(target)
    new_rel = target.relative_to(root).as_posix()
    if store is not None:
        store.move(UPLOAD_SOURCE, rel_path, new_rel, label)
    return {"path": new_rel, "label": label}


class CatalogStore:
    """Postgres access for the catalog. The writer DSN (scan) needs
    INSERT/UPDATE; the reader DSN (chat) needs SELECT only."""

    def __init__(self, *, dsn: str = "", connection_factory: Callable[[], Any] | None = None) -> None:
        if not dsn and connection_factory is None:
            raise DataMapError("catalog DSN must be non-empty")
        self._dsn = dsn
        self._connection_factory = connection_factory

    def _connection(self):
        if self._connection_factory is not None:
            return self._connection_factory()
        import psycopg

        return psycopg.connect(self._dsn)

    def scan(self, source: Source, *, batch_size: int = BATCH_SIZE, progress: Callable[[int], None] | None = None) -> dict:
        stats: dict = {"files": 0, "bytes": 0}
        started = datetime.now(timezone.utc)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE TEMP TABLE IF NOT EXISTS karmo_file_catalog_stage "
                    "(rel_path TEXT, name TEXT, ext TEXT, kind TEXT, label TEXT, size_bytes BIGINT, modified_at TIMESTAMPTZ) "
                    "ON COMMIT DELETE ROWS"
                )
                batch: list[CatalogEntry] = []
                for entry in walk(source, stats):
                    batch.append(entry)
                    stats["files"] += 1
                    stats["bytes"] += entry.size_bytes
                    if len(batch) >= batch_size:
                        self._merge(cur, source.name, batch, started)
                        conn.commit()
                        batch = []
                        if progress:
                            progress(stats["files"])
                if batch:
                    self._merge(cur, source.name, batch, started)
                cur.execute(
                    """
                    UPDATE public.karmo_file_catalog SET missing_since = %s
                    WHERE source = %s AND last_seen_at < %s AND missing_since IS NULL
                    """,
                    (started, source.name, started),
                )
                stats["newly_missing"] = cur.rowcount
            conn.commit()
        return stats

    @staticmethod
    def _merge(cur, source_name: str, batch: list[CatalogEntry], seen_at: datetime) -> None:
        with cur.copy(
            "COPY karmo_file_catalog_stage (rel_path, name, ext, kind, label, size_bytes, modified_at) FROM STDIN"
        ) as copy:
            for e in batch:
                copy.write_row((e.rel_path, e.name, e.ext, e.kind, e.label, e.size_bytes, e.modified_at))
        cur.execute(
            """
            INSERT INTO public.karmo_file_catalog
                (source, rel_path, name, ext, kind, label, size_bytes, modified_at, first_seen_at, last_seen_at)
            SELECT DISTINCT ON (rel_path) %s, rel_path, name, ext, kind, label, size_bytes, modified_at, %s, %s
            FROM karmo_file_catalog_stage
            ON CONFLICT (source, rel_path) DO UPDATE SET
                size_bytes = EXCLUDED.size_bytes,
                modified_at = EXCLUDED.modified_at,
                kind = EXCLUDED.kind,
                label = CASE WHEN karmo_file_catalog.label_source = 'owner'
                             THEN karmo_file_catalog.label ELSE EXCLUDED.label END,
                last_seen_at = EXCLUDED.last_seen_at,
                missing_since = NULL
            """,
            (source_name, seen_at, seen_at),
        )
        cur.execute("DELETE FROM karmo_file_catalog_stage")

    def upsert(self, source_name: str, entry: CatalogEntry) -> int:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.karmo_file_catalog
                        (source, rel_path, name, ext, kind, label, size_bytes, modified_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source, rel_path) DO UPDATE SET
                        size_bytes = EXCLUDED.size_bytes, modified_at = EXCLUDED.modified_at,
                        label = EXCLUDED.label, last_seen_at = NOW(), missing_since = NULL
                    RETURNING id
                    """,
                    (source_name, entry.rel_path, entry.name, entry.ext, entry.kind, entry.label,
                     entry.size_bytes, entry.modified_at),
                )
                entry_id = cur.fetchone()[0]
            conn.commit()
        return entry_id

    def move(self, source_name: str, old_rel_path: str, new_rel_path: str, label: str) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.karmo_file_catalog
                    SET rel_path = %s, name = %s, label = %s, label_source = 'owner', last_seen_at = NOW()
                    WHERE source = %s AND rel_path = %s
                    """,
                    (new_rel_path, new_rel_path.rsplit("/", 1)[-1], label, source_name, old_rel_path),
                )
            conn.commit()

    def find(self, query: str, *, limit: int = MAX_FIND_RESULTS) -> tuple[int, list[dict]]:
        """Matches every word first; if nothing matches, any word, best
        first. Returns (total matches, top rows)."""
        words = re.findall(r"[A-Za-z0-9]+", query)
        if not words:
            return 0, []
        all_words = " & ".join(words)
        any_word = " | ".join(words)
        with self._connection() as conn:
            with conn.cursor() as cur:
                for expression in (all_words, any_word):
                    cur.execute(
                        """
                        SELECT count(*) OVER (), id, source, rel_path, kind, label, size_bytes, modified_at
                        FROM public.karmo_file_catalog, to_tsquery('english', %s) AS q
                        WHERE search @@ q AND missing_since IS NULL
                        ORDER BY ts_rank(search, q) DESC, modified_at DESC
                        LIMIT %s
                        """,
                        (expression, limit),
                    )
                    rows = cur.fetchall()
                    if rows:
                        return rows[0][0], [
                            {"id": r[1], "source": r[2], "path": r[3], "kind": r[4], "label": r[5],
                             "size_bytes": r[6], "modified_at": r[7]}
                            for r in rows
                        ]
        return 0, []

    def summary(self) -> list[tuple[str, int, int]]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT label, count(*), COALESCE(sum(size_bytes), 0)
                    FROM public.karmo_file_catalog WHERE missing_since IS NULL
                    GROUP BY label ORDER BY sum(size_bytes) DESC NULLS LAST
                    """
                )
                return [(label, int(count), int(size)) for label, count, size in cur.fetchall()]


def _read_dsn(path: str) -> str:
    dsn_path = Path(path)
    if not dsn_path.exists():
        raise DataMapError(f"DSN file not found: {path}")
    if dsn_path.stat().st_mode & 0o077:
        raise DataMapError("DSN file must not be accessible to other users")
    dsn = dsn_path.read_text(encoding="utf-8").strip()
    if not dsn:
        raise DataMapError("DSN file is empty")
    return dsn


def build_default_catalog_reader(dsn_file: str = DEFAULT_READER_DSN_FILE) -> CatalogStore:
    return CatalogStore(dsn=_read_dsn(dsn_file))


def build_default_catalog_writer(dsn_file: str = DEFAULT_WRITER_DSN_FILE) -> CatalogStore:
    return CatalogStore(dsn=_read_dsn(dsn_file))


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def format_find(query: str, total: int, rows: list[dict]) -> str:
    lines = [f"Found {total} file(s) for \"{query}\"" + (f"; the top {len(rows)}:" if total > len(rows) else ":")]
    for row in rows:
        modified = row["modified_at"]
        date = modified.strftime("%Y-%m-%d") if hasattr(modified, "strftime") else str(modified)[:10]
        lines.append(f"- {row['source']}:/{row['path']} ({row['label']}, {human_size(row['size_bytes'])}, {date})")
    return "\n".join(lines)


def format_summary(rows: list[tuple[str, int, int]]) -> str:
    if not rows:
        return "My data map is empty -- no storage has been scanned yet."
    total_files = sum(count for _l, count, _s in rows)
    total_bytes = sum(size for _l, _c, size in rows)
    lines = [f"Data map: {total_files:,} files, {human_size(total_bytes)}."]
    lines.extend(f"- {label}: {count:,} files, {human_size(size)}" for label, count, size in rows)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m core_service.data_map")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="catalog file metadata (never reads contents)")
    scan.add_argument("--source", help="scan only this source")
    scan.add_argument("--dsn-file", default=DEFAULT_WRITER_DSN_FILE)
    stats_cmd = sub.add_parser("stats")
    stats_cmd.add_argument("--dsn-file", default=DEFAULT_READER_DSN_FILE)
    find = sub.add_parser("find")
    find.add_argument("words", nargs="+")
    find.add_argument("--dsn-file", default=DEFAULT_READER_DSN_FILE)
    args = parser.parse_args(argv)
    try:
        store = CatalogStore(dsn=_read_dsn(args.dsn_file))
        if args.command == "scan":
            sources = [s for s in load_sources(args.config) if args.source in (None, s.name)]
            if not sources:
                raise DataMapError(f"no source named {args.source!r}")
            for source in sources:
                if not source.root.is_dir():
                    raise DataMapError(f"source {source.name}: {source.root} is not mounted or not a folder")
                began = time.monotonic()
                result = store.scan(source, progress=lambda n: print(f"  {n:,} files...", file=sys.stderr))
                print(f"{source.name}: {result['files']:,} files, {human_size(result['bytes'])} "
                      f"in {time.monotonic() - began:.0f}s; newly missing {result['newly_missing']:,}; "
                      f"excluded {result.get('excluded', 0):,}; unreadable "
                      f"{result.get('unreadable_dirs', 0) + result.get('unreadable_files', 0):,}")
        elif args.command == "stats":
            print(format_summary(store.summary()))
        else:
            query = " ".join(args.words)
            total, rows = store.find(query)
            print(format_find(query, total, rows) if rows else f"Nothing in the data map matches \"{query}\".")
    except DataMapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
