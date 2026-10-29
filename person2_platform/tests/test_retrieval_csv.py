"""Staff retrieval CSV stays on the client the caller can already open."""
from __future__ import annotations

from conftest import auth

from finledger_platform.db import tenant
from finledger_platform.retrieval_import import HISTORY_MAX_BYTES, HISTORY_MAX_ROWS

GSTIN = "27AAPFU0939F1ZV"
LEDGERS = b"name,parent_group,gst_duty\nPurchase - Steel,Purchase Accounts,Purchase\n"
VENDORS = (
    b"name,gstin,default_ledger\n"
    b"Shree Ganesh Metals," + GSTIN.encode() + b",Purchase - Steel\n"
)
HISTORY = (
    b"doc_type,invoice_no,invoice_date,vendor_gstin,vendor_name,description,hsn_sac,amount,ledger\n"
    b"purchase_invoice,INV-1,2026-09-01," + GSTIN.encode()
    + b",Shree Ganesh Metals,HR coil,7208,118000,Purchase - Steel\n"
)


def _post(client, token, client_id, kind, payload, name):
    return client.post(
        f"/clients/{client_id}/retrieval-csv",
        headers=auth(token),
        data={"kind": kind},
        files={"file": (name, payload, "text/csv")},
    )


def _refs(conn, client_id, prefix):
    with tenant(conn, client_id):
        rows = conn.execute(
            "select ref, content, embedding from rag_chunks where ref like %s order by ref",
            (prefix + "%",),
        ).fetchall()
    return rows


def test_staff_upload_indexes_only_that_client(world, client, conn, store):
    uploaded = _post(client, world.clerk_token, world.a["id"], "ledgers", LEDGERS, "ledgers.csv")
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["imported"] == 1
    assert body["object_key"].startswith(f"{world.a['id']}/")
    assert store.get(body["object_key"]) == LEDGERS
    ledgers = _refs(conn, world.a["id"], "ledger:")
    assert [row["ref"] for row in ledgers] == ["ledger:Purchase - Steel"]
    assert ledgers[0]["embedding"] is None and "Purchase Accounts" in ledgers[0]["content"]
    assert _refs(conn, world.b["id"], "ledger:") == []
    assert _refs(conn, world.c["id"], "ledger:") == []

    replaced = b"name,parent_group\nPurchase - Steel,Direct Expenses\n"
    again = _post(client, world.token1, world.a["id"], "ledgers", replaced, "ledgers.csv")
    assert again.status_code == 201
    ledgers = _refs(conn, world.a["id"], "ledger:")
    assert len(ledgers) == 1 and "Direct Expenses" in ledgers[0]["content"]

    vendors = _post(client, world.clerk_token, world.a["id"], "vendors", VENDORS, "vendors.csv")
    assert vendors.status_code == 201, vendors.text
    with tenant(conn, world.a["id"]):
        vendor = conn.execute("select name from vendors where gstin = %s", (GSTIN,)).fetchone()
    assert vendor["name"] == "Shree Ganesh Metals"
    assert _refs(conn, world.a["id"], "vendor:")[0]["ref"] == f"vendor:{GSTIN}"
    assert _refs(conn, world.b["id"], "vendor:") == []

    other = _post(client, world.token2, world.b["id"], "ledgers", b"name,parent_group\nYarn,Purchases\n", "ledgers.csv")
    assert other.status_code == 201, other.text
    assert [row["ref"] for row in _refs(conn, world.b["id"], "ledger:")] == ["ledger:Yarn"]
    assert [row["ref"] for row in _refs(conn, world.a["id"], "ledger:")] == ["ledger:Purchase - Steel"]

    history = _post(client, world.clerk_token, world.a["id"], "posted_history", HISTORY, "history.csv")
    assert history.status_code == 201, history.text
    posted = _refs(conn, world.a["id"], "history:")
    assert posted[0]["ref"] == f"history:{GSTIN}:INV-1:7208"
    assert posted[0]["embedding"] is None
    assert _refs(conn, world.b["id"], "history:") == []


def test_retrieval_csv_is_staff_only_and_capped(world, client, conn):
    assert _post(client, world.token2, world.a["id"], "ledgers", LEDGERS, "ledgers.csv").status_code == 404
    assert _post(client, world.clerk_token, world.c["id"], "ledgers", LEDGERS, "ledgers.csv").status_code == 404
    assert client.post(
        f"/clients/{world.a['id']}/retrieval-csv",
        data={"kind": "ledgers"},
        files={"file": ("ledgers.csv", LEDGERS, "text/csv")},
    ).status_code == 401

    public = client.post(
        f"/i/{world.a['public_token']}",
        files=[("files", ("ledgers.csv", LEDGERS, "text/csv"))],
    )
    assert public.status_code == 422
    assert _refs(conn, world.a["id"], "ledger:") == []

    bills = b"vendor,invoice_no,total\nGanesh,INV-1,10\n"
    assert client.post(
        f"/clients/{world.a['id']}/csv",
        headers=auth(world.clerk_token),
        files={"file": ("bills.csv", bills, "text/csv")},
    ).status_code == 201
    assert _refs(conn, world.a["id"], "ledger:") == []

    too_big = b"x" * (HISTORY_MAX_BYTES + 1)
    assert _post(client, world.clerk_token, world.a["id"], "posted_history", too_big, "history.csv").status_code == 413
    header = b"doc_type,invoice_no,invoice_date,vendor_gstin,vendor_name,description,hsn_sac,amount,ledger\n"
    line = (
        b"purchase_invoice,INV-%d,2026-09-01," + GSTIN.encode()
        + b",Shree Ganesh Metals,HR coil,7208,10,Purchase\n"
    )
    fat = header + b"".join(line % n for n in range(HISTORY_MAX_ROWS + 1))
    capped = _post(client, world.clerk_token, world.a["id"], "posted_history", fat, "history.csv")
    assert capped.status_code == 422
    assert _refs(conn, world.a["id"], "history:") == []
    assert _post(client, world.clerk_token, world.a["id"], "vendors", b"name,gstin\nBad,NOTGSTIN\n", "vendors.csv").status_code == 422
