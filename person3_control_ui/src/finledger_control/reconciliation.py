"""Bank lines already stored for one client, matched to that client's open bills."""
from __future__ import annotations

from finledger_platform.statements import match_payments


def load_reconciliation(conn, client_id) -> dict:
    with conn.transaction():
        conn.execute("select set_config('app.client_id', %s, true)", (str(client_id),))
        statements = conn.execute(
            """select source_meta->'bank_lines' as bank_lines
               from documents
               where document_class = 'statement'
               order by received_at""",
        ).fetchall()
        bills = conn.execute(
            """select d.id as document_id, d.status,
                      c.payload->>'invoice_no' as invoice_no,
                      c.payload->>'total' as amount,
                      c.payload->'vendor'->>'name' as vendor_name
               from documents d
               join canonical_invoices c on c.document_id = d.id
               where coalesce(c.payload->>'invoice_no', '') <> ''
                 and d.status not in ('paid', 'posted', 'reconciled', 'closed', 'rejected')
               order by c.payload->>'invoice_no', d.id""",
        ).fetchall()
    lines = []
    for row in statements:
        stored = row["bank_lines"]
        if isinstance(stored, list):
            lines.extend(item for item in stored if isinstance(item, dict))
    return match_payments(lines, [dict(row) for row in bills])
