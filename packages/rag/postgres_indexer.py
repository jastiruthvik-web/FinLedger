from __future__ import annotations

import json
from typing import Any, Dict

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from rag.chunk_types import ChunkType
from rag.indexer import Indexer


def _chunk_type(chunk_type: ChunkType | str) -> str:
    return chunk_type.value if isinstance(chunk_type, ChunkType) else chunk_type


class PostgresIndexer(Indexer):
    def __init__(self, conn: psycopg.Connection):
        super().__init__()
        self._conn = conn
        self._conn.row_factory = dict_row

    def upsert(self, client_id: str, chunk_id: str, chunk_type: ChunkType, content: str, metadata: Dict[str, Any] | None = None):
        metadata = metadata or {}
        stored_type = _chunk_type(chunk_type)
        with self._conn.transaction():
            # Lexical search reads text. The embedding column stays null until a model id is configured.
            self._conn.execute(
                """insert into rag_chunks (client_id, chunk_type, ref, content, metadata)
                   values (%s::uuid, %s, %s, %s, %s)
                   on conflict (client_id, ref) do update
                     set chunk_type = excluded.chunk_type,
                         content = excluded.content,
                         metadata = excluded.metadata,
                         embedding = null""",
                (client_id, stored_type, chunk_id, content, Jsonb(metadata)),
            )
        chunk = {"chunk_id": chunk_id, "chunk_type": chunk_type, "content": content, "metadata": metadata}
        return chunk

    def get_namespace_chunks(self, client_id: str):
        rows = self._conn.execute(
            """select ref as chunk_id, chunk_type, content, metadata
               from rag_chunks where client_id = %s::uuid order by id""",
            (client_id,),
        ).fetchall()
        return [
            {
                "chunk_id": row["chunk_id"],
                "chunk_type": row["chunk_type"],
                "content": row["content"],
                "metadata": row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}"),
            }
            for row in rows
        ]
