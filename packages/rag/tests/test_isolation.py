import pytest
from rag.indexer import Indexer
from rag.retriever import Retriever
from rag.chunk_types import ChunkType

def test_hard_isolation():
    indexer = Indexer()
    # Client A data
    indexer.upsert("clientA", "chunk1", ChunkType.LEDGER, "Client A Ledger")
    
    # Client B data
    indexer.upsert("clientB", "chunk2", ChunkType.VENDOR, "Client B Vendor")
    
    retriever = Retriever(indexer)
    
    # Unmatched rows score 0 and are not returned. A positive query still cannot cross clients.
    assert retriever.retrieve("clientA", "", "", [], "", "", "") == []
    results_a = retriever.retrieve("clientA", "", "Client A", [], "", "", "")
    assert len(results_a) == 1
    assert results_a[0]["content"] == "Client A Ledger"

    results_b = retriever.retrieve("clientB", "", "Client B", [], "", "", "")
    assert len(results_b) == 1
    assert results_b[0]["content"] == "Client B Vendor"
    
    # Client A chunks NEVER appear in Client B queries
    assert not any("Client A" in r["content"] for r in results_b)
    # Client B chunks NEVER appear in Client A queries
    assert not any("Client B" in r["content"] for r in results_a)
