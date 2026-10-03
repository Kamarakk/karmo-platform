"""Data map: path-only classification, the metadata walk, and the
real-PostgreSQL catalog (migration 014)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core_service.data_map import (
    CatalogStore,
    DataMapError,
    Source,
    classify,
    format_find,
    format_summary,
    load_sources,
    walk,
)


def test_classify_uses_folder_then_kind():
    assert classify("Business/BloomBoss/2024/emgarden_invoice.pdf") == ("pdf", "document", "BloomBoss")
    assert classify("homelab/router-configs/core-sw1.cfg") == ("cfg", "config", "Lab")
    assert classify("Taxes/2023/w2.pdf")[2] == "Personal"
    assert classify("DCIM/100APPLE/IMG_0001.HEIC") == ("heic", "photo", "Photos")
    assert classify("random/IMG_0002.jpg")[2] == "Photos"
    assert classify("random/clip.mkv")[2] == "Media"
    assert classify("random/notes")[1:] == ("other", "Unsorted")
    assert classify("anything/x.pdf", forced_label="Archive")[2] == "Archive"


def _make(root: Path, files: dict[str, str]):
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def test_walk_reads_metadata_only_and_skips_housekeeping_symlinks_and_employer_data(tmp_path):
    _make(tmp_path, {
        "BloomBoss/inv.csv": "a,b\n",
        "@eaDir/thumb.jpg": "x",
        "#recycle/old.pdf": "x",
        "Work/SDCCD/roster.xlsx": "x",
        "Photos/.DS_Store": "x",
        "Photos/a.jpg": "xyz",
    })
    os.symlink(tmp_path / "BloomBoss", tmp_path / "loop")
    stats = {}

    entries = {e.rel_path: e for e in walk(Source(name="nas", root=tmp_path), stats)}

    assert set(entries) == {"BloomBoss/inv.csv", "Photos/a.jpg"}
    assert entries["Photos/a.jpg"].size_bytes == 3
    assert entries["BloomBoss/inv.csv"].label == "BloomBoss"
    assert stats["excluded"] == 1


def test_load_sources_validates_config(tmp_path):
    config = tmp_path / "data_map.json"
    config.write_text(json.dumps({"sources": [{"name": "nas", "root": "/mnt/karmo-nas"}]}))
    assert load_sources(str(config)) == [Source(name="nas", root=Path("/mnt/karmo-nas"))]
    for bad in ({"sources": []}, {"sources": [{"name": "NAS!", "root": "/x"}]},
                {"sources": [{"name": "nas", "root": "relative"}]},
                {"sources": [{"name": "nas", "root": "/x", "label": "Work"}]}):
        config.write_text(json.dumps(bad))
        with pytest.raises(DataMapError):
            load_sources(str(config))


def test_format_helpers():
    assert format_summary([]).startswith("My data map is empty")
    assert "1.0 TB" in format_summary([("Photos", 10, 1024 ** 4)])
    from datetime import datetime, timezone
    text = format_find("invoice", 25, [{"source": "nas", "path": "BloomBoss/inv.pdf", "label": "BloomBoss",
                                        "size_bytes": 2048, "modified_at": datetime(2024, 5, 1, tzinfo=timezone.utc)}])
    assert "Found 25 file(s)" in text and "nas:/BloomBoss/inv.pdf (BloomBoss, 2.0 KB, 2024-05-01)" in text


# --- real PostgreSQL --------------------------------------------------------

psycopg = pytest.importorskip("psycopg")

PG = dict(
    host=os.environ.get("KARMO_CORE_TEST_PG_HOST", "127.0.0.1"),
    port=os.environ.get("KARMO_CORE_TEST_PG_PORT", "55434"),
    dbname=os.environ.get("KARMO_CORE_TEST_PG_DB", "karmo_core_test"),
    user=os.environ.get("KARMO_CORE_TEST_PG_USER", "karmo_core_test"),
    password=os.environ.get("KARMO_CORE_TEST_PG_PASSWORD", "karmo_core_test_synthetic_local_only"),
)
CONNINFO = " ".join(f"{k}={v}" for k, v in PG.items())
MIGRATION = Path(__file__).resolve().parents[1] / "core_service" / "migrations" / "014_file_catalog.sql"


def _reachable():
    try:
        with psycopg.connect(CONNINFO, connect_timeout=2):
            return True
    except Exception:
        return False


postgres = pytest.mark.skipif(not _reachable(), reason="no reachable PostgreSQL for data map tests")


@pytest.fixture
def store():
    with psycopg.connect(CONNINFO, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS public.karmo_file_catalog")
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
        cur.execute(MIGRATION.read_text(encoding="utf-8"))  # idempotent
    return CatalogStore(dsn=CONNINFO)


@postgres
def test_scan_find_rescan_and_missing(store, tmp_path):
    _make(tmp_path, {
        "Business/BloomBoss/2024/emgarden_invoice_0401.pdf": "x",
        "Business/BloomBoss/2024/palmstreet_orders.csv": "x",
        "homelab/configs/core-switch.cfg": "x",
        "Photos/2024/IMG_1.jpg": "x",
    })
    source = Source(name="nas", root=tmp_path)

    first = store.scan(source, batch_size=2)
    assert first["files"] == 4 and first["newly_missing"] == 0

    total, rows = store.find("2024 bloomboss invoices")
    assert total == 1 and rows[0]["path"] == "Business/BloomBoss/2024/emgarden_invoice_0401.pdf"
    total, rows = store.find("switch config")
    assert rows[0]["label"] == "Lab"

    # An owner-set label survives a rescan; a deleted file is marked missing, not removed.
    with psycopg.connect(CONNINFO, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("UPDATE karmo_file_catalog SET label = 'Personal', label_source = 'owner' "
                    "WHERE rel_path LIKE 'Photos/%'")
    (tmp_path / "homelab/configs/core-switch.cfg").unlink()
    second = store.scan(source)
    assert second["files"] == 3 and second["newly_missing"] == 1
    assert store.find("switch")[0] == 0
    assert dict((label, count) for label, count, _ in store.summary()) == {"BloomBoss": 2, "Personal": 1}


# --- chat routing -----------------------------------------------------------

class FakeCatalog:
    def __init__(self, rows=None, fail=False):
        self.rows = rows or []
        self.fail = fail
        self.queries = []

    def find(self, query):
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("catalog down")
        return len(self.rows), self.rows

    def summary(self):
        return [("BloomBoss", 2, 4096)]


class NoChatModel:
    def chat(self, *args, **kwargs):
        raise AssertionError("the model must not be called")


def _row():
    from datetime import datetime, timezone
    return {"source": "nas", "path": "BloomBoss/2024/inv.pdf", "label": "BloomBoss", "size_bytes": 10,
            "modified_at": datetime(2024, 4, 1, tzinfo=timezone.utc)}


def _operator(catalog):
    from core_service.operator import KarmoOperator
    return KarmoOperator(model_client=NoChatModel(), catalog_reader=catalog)


def test_where_question_is_answered_from_the_catalog_without_a_model():
    catalog = FakeCatalog([_row()])
    response = _operator(catalog)._handle("Where are my 2024 BloomBoss invoices?")
    assert catalog.queries == ["2024 BloomBoss invoices"]
    assert response["model"] is None and "nas:/BloomBoss/2024/inv.pdf" in response["message"]


def test_data_map_summary():
    response = _operator(FakeCatalog())._handle("what's on my NAS?")
    assert response["message"].startswith("Data map: 2 files")


def test_no_match_or_broken_catalog_falls_through_to_chat():
    from core_service.operator import KarmoOperator
    for catalog in (FakeCatalog([]), FakeCatalog(fail=True)):
        operator = KarmoOperator(catalog_reader=catalog)
        assert operator._data_map_answer("where is my phone") is None
    assert _operator(FakeCatalog([_row()]))._data_map_answer("how do I kill weeds") is None


# --- uploads ----------------------------------------------------------------

def test_sniff_uses_the_file_signature_over_the_name():
    from core_service.data_map import sniff_ext
    assert sniff_ext(b"%PDF-1.7 ...", "scan") == "pdf"
    assert sniff_ext(b"\x89PNG\r\n\x1a\nxxxx", "photo.jpg") == "png"
    assert sniff_ext(b"PK\x03\x04....word/document.xml", "report") == "docx"
    assert sniff_ext(b"\x00\x00\x00\x18ftypheic", "IMG_1") == "heic"
    assert sniff_ext(b"date,cultivar,price", "export.csv") == "csv"


def test_classify_upload_reads_text_files_for_the_label():
    from core_service.data_map import classify_upload
    assert classify_upload("export.csv", b"order,cultivar,plant,price\n1,Monstera,x,10")[2] == "BloomBoss"
    assert classify_upload("notes.txt", b"core switch vlan config for the homelab")[2] == "Lab"
    assert classify_upload("IMG_1", b"\xff\xd8\xff\xe0rest")[:2] == ("IMG_1.jpg", "photo")
    assert classify_upload("../../etc/passwd", b"root:x:0:0")[0] == "passwd"


def test_store_and_relabel_upload_on_disk(tmp_path):
    from datetime import datetime, timezone
    from core_service.data_map import relabel_upload, store_upload
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    saved = store_upload("tax return 2025.pdf", b"%PDF-1.7", upload_root=str(tmp_path), now=now)
    assert saved["label"] == "Personal" and saved["path"] == "Personal/2026-10/tax return 2025.pdf"
    again = store_upload("tax return 2025.pdf", b"%PDF-1.7", upload_root=str(tmp_path), now=now)
    assert again["path"] == "Personal/2026-10/tax return 2025-2.pdf"

    moved = relabel_upload(saved["path"], "Archive", upload_root=str(tmp_path))
    assert moved == {"path": "Archive/2026-10/tax return 2025.pdf", "label": "Archive"}
    assert (tmp_path / moved["path"]).read_bytes() == b"%PDF-1.7"
    for bad_path, label in (("../outside.txt", "Lab"), (moved["path"], "Work")):
        with pytest.raises(DataMapError):
            relabel_upload(bad_path, label, upload_root=str(tmp_path))
    with pytest.raises(DataMapError):
        store_upload("big.bin", b"x" * 14_000_001, upload_root=str(tmp_path))


@postgres
def test_upload_is_catalogued_and_an_owner_relabel_survives_a_rescan(store, tmp_path):
    from core_service.data_map import relabel_upload, store_upload
    saved = store_upload("palmstreet export.csv", b"cultivar,plant,price", upload_root=str(tmp_path), store=store)
    assert saved["label"] == "BloomBoss" and store.find("palmstreet")[0] == 1

    moved = relabel_upload(saved["path"], "Personal", upload_root=str(tmp_path), store=store)
    store.scan(Source(name="uploads", root=tmp_path))
    total, rows = store.find("palmstreet")
    assert total == 1 and rows[0]["label"] == "Personal" and rows[0]["path"] == moved["path"]


def test_operator_upload_never_raises(tmp_path):
    from core_service.operator import KarmoOperator
    operator = KarmoOperator(catalog_reader=FakeCatalog(), upload_root=str(tmp_path))
    operator.catalog_writer = None
    assert operator.store_upload(name="a.txt", data_base64="not base64!")["error"]
    assert operator.store_upload(name="a.txt", data_base64="aGVsbG8=")["path"].endswith("a.txt")
    assert "error" in operator.relabel_upload(path="nope.txt", label="Lab")
