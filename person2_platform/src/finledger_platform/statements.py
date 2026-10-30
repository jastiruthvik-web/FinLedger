"""Bank-statement rows and payment matching.

A payment matches an open bill only when the invoice number and the amount both agree.
Anything else stays unmatched. This module does not invent clients or post to an ERP.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element, ParseError

_CENT = Decimal("0.01")
_HEADER = {
    "date": "date",
    "txn date": "date",
    "transaction date": "date",
    "value date": "date",
    "narration": "narration",
    "description": "narration",
    "particulars": "narration",
    "details": "narration",
    "invoice": "reference",
    "invoice no": "reference",
    "invoice number": "reference",
    "reference": "reference",
    "ref": "reference",
    "ref no": "reference",
    "cheque": "reference",
    "chq no": "reference",
    "debit": "debit",
    "withdrawal": "debit",
    "dr": "debit",
    "credit": "credit",
    "deposit": "credit",
    "cr": "credit",
}


def read_table(data: bytes, mime: str) -> list[list[str]]:
    """First sheet of an xlsx, or every row of a csv. Empty when the bytes are not a table."""
    if mime == "text/csv" or data[:3] != b"PK\x03":
        if mime == "text/csv" or _looks_like_csv(data):
            return _csv_rows(data)
    if data[:2] == b"PK":
        return _xlsx_rows(data)
    return []


def lines_from_statement(data: bytes, mime: str) -> list[dict]:
    try:
        rows = read_table(data, mime)
    except (ValueError, zipfile.BadZipFile, OSError, ParseError):
        return []
    return lines_from_table(rows)


def lines_from_table(rows: list[list[str]]) -> list[dict]:
    if not rows:
        return []
    indexes: dict[str, int] = {}
    for index, cell in enumerate(rows[0]):
        kind = _HEADER.get(_header(cell))
        if kind and kind not in indexes:
            indexes[kind] = index
    if not {"date", "debit", "credit", "reference", "narration"} & set(indexes):
        return []
    lines: list[dict] = []
    for raw in rows[1:]:
        def cell(kind: str) -> str:
            index = indexes.get(kind)
            if index is None or index >= len(raw):
                return ""
            return str(raw[index]).strip()

        debit = _plain(_money(cell("debit")))
        credit = _plain(_money(cell("credit")))
        line = {
            "date": cell("date"),
            "narration": cell("narration"),
            "reference": cell("reference"),
            "debit": debit,
            "credit": credit,
        }
        if any(line.values()):
            lines.append(line)
    return lines


def table_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)

    def cells(row: list[str]) -> list[str]:
        padded = [str(value).replace("|", "/").replace("\n", " ") for value in row]
        return padded + [""] * (width - len(padded))

    header = cells(rows[0])
    body = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    body.extend("| " + " | ".join(cells(row)) + " |" for row in rows[1:])
    return "\n".join(body)


def match_payments(lines: list[dict], bills: list[dict]) -> dict:
    """Match each payment to at most one open bill. Invoice number and amount must both agree."""
    pending = []
    for bill in bills:
        invoice_no = str(bill.get("invoice_no") or "").strip()
        amount = _money(bill.get("amount"))
        if not invoice_no or amount is None:
            continue
        pending.append({
            "document_id": str(bill.get("document_id") or ""),
            "invoice_no": invoice_no,
            "amount": amount,
            "vendor_name": str(bill.get("vendor_name") or ""),
            "workflow_status": str(bill.get("status") or bill.get("workflow_status") or ""),
        })
    used: set[str] = set()
    matched_lines = []
    for line in lines:
        amount = _payment_amount(line)
        hit = None
        if amount is not None:
            text = (str(line.get("narration") or ""), str(line.get("reference") or ""))
            for bill in pending:
                if bill["document_id"] in used:
                    continue
                if bill["amount"] == amount and _contains_invoice(bill["invoice_no"], *text):
                    hit = bill
                    break
        if hit is not None:
            used.add(hit["document_id"])
        matched_lines.append({
            "date": str(line.get("date") or ""),
            "narration": str(line.get("narration") or ""),
            "reference": str(line.get("reference") or ""),
            "debit": _plain(_money(line.get("debit"))),
            "credit": _plain(_money(line.get("credit"))),
            "status": "matched" if hit else "unmatched",
            "invoice_no": hit["invoice_no"] if hit else None,
            "document_id": hit["document_id"] if hit else None,
        })
    return {
        "lines": matched_lines,
        "bills": [{
            "document_id": bill["document_id"],
            "invoice_no": bill["invoice_no"],
            "amount": _plain(bill["amount"]),
            "vendor_name": bill["vendor_name"],
            "workflow_status": bill["workflow_status"],
            "status": "matched" if bill["document_id"] in used else "unmatched",
        } for bill in pending],
    }


def _looks_like_csv(data: bytes) -> bool:
    sample = data[:200].decode("utf-8", errors="ignore").lower()
    return "date" in sample and ("," in sample or ";" in sample)


def _csv_rows(data: bytes) -> list[list[str]]:
    text = data.decode("utf-8-sig", errors="replace")
    return [row for row in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in row)]


def _xlsx_rows(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        names = set(book.namelist())
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in names:
            sheets = sorted(name for name in names if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
            if not sheets:
                return []
            sheet_name = sheets[0]
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared = _shared_strings(book.read("xl/sharedStrings.xml"))
        root = _xml(book.read(sheet_name))
    grid: dict[int, dict[int, str]] = {}
    for row in root.iter():
        if _local(row.tag) != "row":
            continue
        number = int(row.attrib.get("r") or 0)
        if number < 1:
            continue
        for cell in list(row):
            if _local(cell.tag) != "c":
                continue
            ref = cell.attrib.get("r") or ""
            column = _column_index(ref)
            if column < 0:
                continue
            grid.setdefault(number, {})[column] = _cell_text(cell, shared)
    if not grid:
        return []
    last_row = max(grid)
    width = max((max(columns) for columns in grid.values() if columns), default=-1) + 1
    table = []
    for number in range(1, last_row + 1):
        values = grid.get(number, {})
        table.append([values.get(index, "") for index in range(width)])
    while table and not any(cell.strip() for cell in table[-1]):
        table.pop()
    return table


def _shared_strings(data: bytes) -> list[str]:
    root = _xml(data)
    strings = []
    for item in root:
        if _local(item.tag) != "si":
            continue
        strings.append("".join(node.text or "" for node in item.iter() if _local(node.tag) == "t"))
    return strings


def _cell_text(cell: Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter() if _local(node.tag) == "t")
    value = ""
    for node in list(cell):
        if _local(node.tag) == "v":
            value = node.text or ""
            break
    if kind == "s":
        try:
            return shared[int(value)]
        except (ValueError, IndexError):
            return ""
    return value


def _xml(data: bytes) -> Element:
    from xml.etree import ElementTree as ET

    return ET.fromstring(data)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _column_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    if not letters:
        return -1
    number = 0
    for ch in letters:
        number = number * 26 + (ord(ch.upper()) - 64)
    return number - 1


def _header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower()).rstrip(":")


def _money(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", "")
    text = text.strip()
    if text in {"", "-", "—", "–"}:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount == 0:
        return None
    return amount.quantize(_CENT)


def _plain(amount: Decimal | None) -> str | None:
    if amount is None:
        return None
    return f"{amount:.2f}"


def _payment_amount(line: dict) -> Decimal | None:
    debit = _money(line.get("debit"))
    credit = _money(line.get("credit"))
    if debit is not None:
        return debit
    return credit


def _contains_invoice(invoice_no: str, *parts: str) -> bool:
    token = invoice_no.strip()
    if not token:
        return False
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", re.IGNORECASE)
    return any(pattern.search(part or "") for part in parts)
