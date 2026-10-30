from pathlib import Path

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "map_prompt.txt"

REQUIRED = (
    "document_id",
    "date",
    "voucher_type",
    "party_ledger",
    "party_create_proposal",
    "lines",
    "gst",
    "tds",
    "bill_wise",
    "narration",
    "attachment_document_id",
    "reasons",
    "map_trace_id",
    "is_debit",
    "cost_centre",
    "input_ledgers",
    "tax_breakup",
    "ref_type",
)


def test_map_prompt_lists_voucher_draft_fields():
    text = PROMPT.read_text(encoding="utf-8")
    for field in REQUIRED:
        assert field in text
    assert "purchase" in text and "debit_note" in text and "credit_note" in text
