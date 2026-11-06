"""Suggest an expense ledger from this company's saved corrections.

Party-ledger corrections are not expense accounts. Nothing here writes an
invoice, a voucher, or a retrieval index. Extraction is left untouched.
"""
from __future__ import annotations

import re
from typing import Any


def suggest_expense_ledgers(lines: list[dict], corrections: list[dict], *, vendor_gstin: str) -> list[dict]:
    expense = [row for row in corrections if (row.get("field") or "") == "expense_ledger"]
    suggestions = []
    for index, line in enumerate(lines):
        suggestions.append(_one(index, line, expense, vendor_gstin))
    return suggestions


def _one(index: int, line: dict, corrections: list[dict], vendor_gstin: str) -> dict:
    description = str(line.get("description") or "")
    hsn = str(line.get("hsn") or "")
    specific = []
    vendor_wide = []
    for row in corrections:
        if not _gstin_ok(row.get("vendor_gstin"), vendor_gstin):
            continue
        ledger = _ledger(row)
        if not ledger:
            continue
        score, scope = _score(row, description, hsn)
        item = {"id": row.get("id"), "ledger": ledger, "score": score, "created_at": row.get("created_at")}
        if scope == "line" and score >= 4:
            specific.append(item)
        elif scope == "vendor":
            vendor_wide.append(item)
    if specific:
        return _from_group(index, specific, "line")
    if vendor_wide:
        latest = max(vendor_wide, key=lambda item: (str(item.get("created_at") or ""), item.get("id") or 0))
        return {
            "line": index,
            "ledger": latest["ledger"],
            "confidence": "low",
            "scope": "vendor",
            "abstained": False,
            "explanation": "Vendor-level expense hint only. It does not replace a line rule and it is not applied automatically.",
            "evidence": [{"id": item["id"], "ledger": item["ledger"]} for item in vendor_wide],
        }
    return {
        "line": index,
        "ledger": None,
        "confidence": "abstain",
        "scope": "none",
        "abstained": True,
        "explanation": "No expense-ledger correction for this line. The party ledger was not used as an expense account.",
        "evidence": [],
    }


def _from_group(index: int, rows: list[dict], scope: str) -> dict:
    ledgers = {row["ledger"] for row in rows}
    evidence = [{"id": row["id"], "ledger": row["ledger"]} for row in rows]
    if len(ledgers) == 1:
        ledger = next(iter(ledgers))
        confidence = "high" if max(row["score"] for row in rows) >= 6 else "medium"
        return {
            "line": index,
            "ledger": ledger,
            "confidence": confidence,
            "scope": scope,
            "abstained": False,
            "explanation": f"Saved expense correction {ledger}. Not applied until someone saves it on this line.",
            "evidence": evidence,
        }
    names = ", ".join(sorted(ledgers))
    return {
        "line": index,
        "ledger": None,
        "confidence": "abstain",
        "scope": scope,
        "abstained": True,
        "explanation": f"Expense history disagrees ({names}). Nothing was chosen.",
        "evidence": evidence,
    }


def _gstin_ok(correction_gstin, vendor_gstin: str) -> bool:
    left = str(correction_gstin or "").strip().upper()
    right = str(vendor_gstin or "").strip().upper()
    if not left or not right:
        return False
    return left == right


def _ledger(row: dict) -> str:
    value = row.get("new_value")
    if isinstance(value, dict):
        text = value.get("ledger") or ""
    else:
        text = value or ""
    return " ".join(str(text).split())


def _score(row: dict, description: str, hsn: str) -> tuple[int, str]:
    value = row.get("new_value") if isinstance(row.get("new_value"), dict) else {}
    corr_desc = " ".join(filter(None, [str(row.get("description") or ""), str(value.get("description") or "")]))
    corr_hsn = str(row.get("hsn") or value.get("hsn") or "")
    if not corr_desc.strip() and not corr_hsn.strip():
        return 1, "vendor"
    score = 0
    terms = set(re.findall(r"[a-z0-9]+", description.casefold()))
    corr_terms = set(re.findall(r"[a-z0-9]+", corr_desc.casefold()))
    shared = {term for term in terms & corr_terms if len(term) > 2}
    if shared:
        score += min(4, len(shared))
    if hsn and corr_hsn and (hsn == corr_hsn or corr_hsn.startswith(hsn) or hsn.startswith(corr_hsn)):
        score += 4
    return score, "line"


def suggestion_touches_invoice(before: Any, after: Any) -> bool:
    return before != after
