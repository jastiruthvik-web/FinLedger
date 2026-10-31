"""Each new client gets the starter file. Nothing is inserted with a null client."""
from __future__ import annotations

from finledger_platform.db import tenant
from rag.library import STARTER_REFS, seed_client_library
from rag.postgres_indexer import PostgresIndexer


def test_create_client_copies_the_starter_under_that_client_only(world, conn, owner):
    for client_id in (world.a["id"], world.b["id"], world.c["id"]):
        with tenant(conn, client_id):
            rows = conn.execute(
                "select ref, chunk_type, metadata, embedding from rag_chunks order by ref"
            ).fetchall()
        library = [row for row in rows if row["ref"].startswith("library:")]
        assert [row["ref"] for row in library] == sorted(STARTER_REFS)
        assert all(row["chunk_type"] == "hard_rule" for row in library)
        assert all(row["metadata"]["scope"] == "library" for row in library)
        assert all(row["embedding"] is None for row in library)
    with tenant(conn, world.a["id"]):
        seed_client_library(PostgresIndexer(conn), str(world.a["id"]))
        again = conn.execute("select count(*) as n from rag_chunks where ref like 'library:%'").fetchone()["n"]
    assert again == 18
    assert owner.execute("select count(*) from rag_chunks where client_id is null").fetchone()[0] == 0
    counts = owner.execute(
        "select count(*) from rag_chunks where ref like 'library:%' group by client_id"
    ).fetchall()
    assert sorted(row[0] for row in counts) == [18, 18, 18]
