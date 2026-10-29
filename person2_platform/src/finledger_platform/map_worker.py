"""map_worker: claim `map` -> index this client's books -> Person 1 map -> submit_draft.

Outcomes per job:
    already past 'scored' (replay)      -> job done, nothing written ("skipped")
    payload names another tenant/doc    -> document 'exception' (map_payload_rejected)
    invoice or draft rejected           -> document 'exception' (map_draft_rejected)
    token cap spent                     -> document 'exception' (ai_budget_exceeded)
    store/DB/provider errors            -> job retries with backoff, then 'dead'
    ok                                  -> voucher draft submitted in the same tenant transaction

Extract never reads ledgers. This worker does, inside tenant(conn, client_id), then
ControlService.submit_draft before that transaction commits. The login must be a member of
finledger_app (RLS applies) and finledger_worker_map (claim_job allows the map queue).
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable

import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError
from usage.kill_switch import TokenCapExceededException

from .client_index import index_client_corpus
from .db import tenant
from .queue import claim, finish

log = logging.getLogger("finledger.map")

PAYLOAD_REJECTED = "map_payload_rejected"
DRAFT_REJECTED = "map_draft_rejected"
AI_BUDGET_EXCEEDED = "ai_budget_exceeded"

# mapper(*, client_id, document_id, invoice, policy) -> MapResult
MapFn = Callable[..., Any]


class MapRejected(ValueError):
    """The invoice or the draft can never be submitted; retrying cannot help."""


class LeaseLost(RuntimeError):
    """Another worker owns the job now; this worker's result must not be settled."""


def _retry_reason(error: Exception) -> str:
    if isinstance(error, psycopg.Error):
        return "map database operation failed"
    return "map processing failed"


def _payload_ok(job: dict) -> bool:
    payload = job["payload"] or {}
    return (str(payload.get("client_id")) == str(job["client_id"])
            and str(payload.get("document_id")) == str(job["document_id"]))


def _exception(conn, client_id, doc_id, maker, reason: str) -> None:
    conn.execute("""update documents set status = 'exception', status_reason = %s, updated_at = now()
                    where id = %s and status = 'scored'""", (reason, doc_id))
    conn.execute("""insert into workflow_events (client_id, document_id, from_status, to_status, action, actor_id, metadata)
                    values (%s, %s, 'scored', 'exception', 'map_exception', %s, %s)""",
                 (client_id, doc_id, maker, Jsonb({"reason": reason})))


def _invoice(conn, doc_id) -> dict:
    row = conn.execute("select payload from canonical_invoices where document_id = %s", (doc_id,)).fetchone()
    if not row or not isinstance(row["payload"], dict):
        raise MapRejected()
    return row["payload"]


def _policy(conn, client_id) -> str:
    row = conn.execute(
        """select auto_post_cap, po_required, po_required_above, maker_checker, tds_sections,
                  msme_clock, itc_180_warning, match_mode, gstins
           from clients where id = %s""",
        (client_id,),
    ).fetchone()
    if row is None:
        return "{}"
    return json.dumps({key: row[key] for key in row}, default=str)


def _submit(conn, client_id, doc_id, maker, result) -> None:
    from finledger_control.service import Conflict, ControlService

    draft = result.draft.model_dump(mode="json")
    try:
        ControlService(conn).submit_draft(client_id, doc_id, draft, maker)
    except Conflict:
        raise MapRejected() from None
    status = conn.execute("select status from documents where id = %s", (doc_id,)).fetchone()["status"]
    conn.execute(
        """insert into workflow_events (client_id, document_id, from_status, to_status, action, actor_id, metadata)
           values (%s, %s, %s, %s, 'map_trace', %s, %s)""",
        (client_id, doc_id, status, status, maker, Jsonb({
            "map_trace_id": result.trace.map_trace_id,
            "retrieved_chunk_ids": list(result.trace.retrieved_chunk_ids),
        })),
    )


def process_map(conn: psycopg.Connection, mapper: MapFn, job: dict) -> str:
    client_id, doc_id = str(job["client_id"]), str(job["document_id"])
    with tenant(conn, client_id):
        doc = conn.execute("select status from documents where id = %s for update", (doc_id,)).fetchone()
        if doc is None:
            outcome = "dead"
        elif doc["status"] != "scored":
            outcome = "skipped"
        else:
            maker = conn.execute("select automation_maker_id(%s) as id", (client_id,)).fetchone()["id"]
            if not _payload_ok(job):
                _exception(conn, client_id, doc_id, maker, PAYLOAD_REJECTED)
                outcome = "exception"
            else:
                try:
                    index_client_corpus(conn, client_id)
                    with conn.transaction():
                        result = mapper(
                            client_id=client_id,
                            document_id=doc_id,
                            invoice=_invoice(conn, doc_id),
                            policy=_policy(conn, client_id),
                        )
                        _submit(conn, client_id, doc_id, maker, result)
                    outcome = "mapped"
                except TokenCapExceededException:
                    _exception(conn, client_id, doc_id, maker, AI_BUDGET_EXCEEDED)
                    outcome = "exception"
                except (MapRejected, ValidationError, json.JSONDecodeError):
                    _exception(conn, client_id, doc_id, maker, DRAFT_REJECTED)
                    outcome = "exception"
        if outcome == "dead":
            state = finish(conn, job["id"], job["claim_token"], ok=False, error="document row missing", permanent=True)
        else:
            state = finish(conn, job["id"], job["claim_token"], ok=True)
        if state is None:
            raise LeaseLost()
    return outcome


def run_once(conn: psycopg.Connection, mapper: MapFn, lease_seconds: int = 300) -> str | None:
    try:
        return _run_once(conn, mapper, lease_seconds)
    except Exception:
        raise RuntimeError("map worker operation failed") from None


def _run_once(conn: psycopg.Connection, mapper: MapFn, lease_seconds: int) -> str | None:
    job = claim(conn, "map", lease_seconds)
    if job is None:
        return None
    try:
        return process_map(conn, mapper, job)
    except LeaseLost:
        log.warning("map job %s lost its lease; result discarded", job["id"])
        return "lease_lost"
    except Exception as error:
        reason = _retry_reason(error)
        log.error("map job %s failed: %s", job["id"], reason)
        return finish(conn, job["id"], job["claim_token"], ok=False, error=reason) or "lease_lost"


def _explicit_live_transport(settings):
    if os.getenv("FINLEDGER_GEMINI_LIVE", "").strip() != "1":
        return None
    from usage.live_gemini import build_explicit_transport

    return build_explicit_transport(settings)


def _canonical_invoice(invoice: dict):
    """Person 3 stores nulls for optional vendor and line fields. The map model wants strings."""
    from contracts.schemas import CanonicalInvoice

    data = json.loads(json.dumps(invoice, default=str))
    vendor = dict(data.get("vendor") or {})
    for key in ("name", "gstin", "pan", "state"):
        if vendor.get(key) is None:
            vendor[key] = ""
    data["vendor"] = vendor
    if data.get("buyer_gstin") is None:
        data["buyer_gstin"] = ""
    if data.get("raw_markdown_path") is None:
        data["raw_markdown_path"] = ""
    if isinstance(data.get("bank_upi"), dict):
        data["bank_upi"] = json.dumps(data["bank_upi"], sort_keys=True)
    for item in data.get("line_items") or []:
        if not isinstance(item, dict):
            continue
        for key in ("desc", "hsn_sac"):
            if item.get(key) is None:
                item[key] = ""
        for key in ("qty", "rate", "taxable", "tax_rate", "tax_amount"):
            if item.get(key) is None:
                item[key] = 0
    return CanonicalInvoice.model_validate(data)


def default_map(conn: psycopg.Connection) -> MapFn:
    """Person 1 MapWorker over this connection's chunks, then the caller submits the draft."""
    from contracts.schemas import CanonicalInvoice
    from mapper.map_worker import MapWorker
    from rag.postgres_indexer import PostgresIndexer
    from rag.retriever import Retriever
    from usage.model_router import ModelRouter, Settings
    from usage.postgres_kill_switch import PostgresKillSwitch
    from usage.postgres_usage_writer import PostgresUsageWriter

    settings = Settings.from_env()
    transport = _explicit_live_transport(settings)
    switch = PostgresKillSwitch(conn, limit=settings.per_bill_token_cap, enabled=settings.kill_switch_enabled)
    worker = MapWorker(
        PostgresUsageWriter(conn),
        Retriever(PostgresIndexer(conn)),
        ModelRouter(settings, gemini_transport=transport, kill_switch=switch),
    )

    def map_invoice(*, client_id, document_id, invoice, policy):
        canonical = invoice if isinstance(invoice, CanonicalInvoice) else _canonical_invoice(invoice)
        if str(canonical.document_id) != str(document_id):
            raise MapRejected()
        return worker.map_invoice_result(str(client_id), canonical, policy)

    return map_invoice


def run_forever(pool, make_map: Callable[[psycopg.Connection], MapFn], idle_sleep: float = 1.0) -> None:
    log.info("map worker started")
    while True:
        with pool.connection() as conn:
            did = run_once(conn, make_map(conn))
        if did is None:
            time.sleep(idle_sleep)
