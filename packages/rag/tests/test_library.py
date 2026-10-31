from rag.indexer import Indexer
from rag.library import STARTER_REFS, load_starter, seed_client_library
from rag.retriever import Retriever


def test_starter_is_eighteen_hard_rules_and_idempotent():
    rows = load_starter()
    assert [row["ref"] for row in rows] == list(STARTER_REFS)
    assert all(row["chunk_type"] == "hard_rule" and row["metadata"]["scope"] == "library" for row in rows)
    by_ref = {row["ref"]: row for row in rows}
    assert "CGST" in by_ref["library:gst:intra"]["content"]
    assert "IGST" in by_ref["library:gst:inter"]["content"]
    assert by_ref["library:sac:9983"]["metadata"]["ledger_hint"] == "Professional Fees"
    assert by_ref["library:sac:9983"]["metadata"]["tds_section"] == "194J"
    assert "Repairs and Maintenance" in by_ref["library:sac:9987"]["content"]
    assert by_ref["library:hsn:7208"]["metadata"]["ledger_hint"] == "Purchase — raw material"
    assert by_ref["library:hsn:8471"]["metadata"]["hsn"] == "8471"
    assert by_ref["library:hsn:8528"]["metadata"]["hsn"] == "8528"
    assert "194C" in by_ref["library:tds:194c"]["content"]
    assert "194I" in by_ref["library:tds:194i"]["content"]
    assert "invoice number" in by_ref["library:doc:purchase_invoice"]["content"]

    indexer = Indexer()
    assert seed_client_library(indexer, "client-a") == 18
    assert seed_client_library(indexer, "client-a") == 18
    assert len(indexer.get_namespace_chunks("client-a")) == 18
    assert indexer.get_namespace_chunks("client-b") == []


def test_unmatched_starter_does_not_fill_eight_slots():
    indexer = Indexer()
    seed_client_library(indexer, "client-a")
    assert Retriever(indexer).retrieve("client-a", "", "", [], "", "", "") == []
    matched = Retriever(indexer).retrieve("client-a", "", "", ["advisory"], "9982", "", "purchase_invoice")
    assert matched
    assert matched[0]["chunk_id"] == "library:sac:9982"
    assert all(row["score"] > 0 for row in matched)
    assert len(matched) <= 8
