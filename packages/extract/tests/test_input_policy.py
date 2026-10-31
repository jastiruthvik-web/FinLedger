from pathlib import Path

from extract.input_policy import minimize_invoice_markdown


def test_invoice_dates_are_kept_when_they_look_like_phone_numbers():
    markdown = "\n".join([
        "Vendor: Harbour Mills",
        "Invoice Date: 2026-10-05",
        "Dated 05-10-2026 for yarn",
        "Bill on 5/10/2026",
        "| Item | Date |",
        "| Yarn | 2026-10-05 |",
    ])
    kept = minimize_invoice_markdown(markdown)
    assert "2026-10-05" in kept
    assert "05-10-2026" in kept
    assert "5/10/2026" in kept
    assert "Invoice Date: 2026-10-05" in kept


def test_phone_numbers_are_still_dropped():
    markdown = "\n".join([
        "Vendor: Harbour Mills",
        "Date: 2026-10-05",
        "Call the mill on 9876543210 before dispatch",
        "WhatsApp +91 98765 43210",
        "GSTIN: 32AABCU9603R1ZM",
    ])
    kept = minimize_invoice_markdown(markdown)
    assert "2026-10-05" in kept
    assert "9876543210" not in kept
    assert "+91 98765 43210" not in kept
    assert "32AABCU9603R1ZM" in kept


def test_a_line_with_a_date_and_a_phone_still_drops():
    markdown = "Dispatch 2026-10-05 ring 022-12345678"
    assert minimize_invoice_markdown(markdown) == ""


def test_extract_prompt_keeps_a_charge_line_when_a_taxable_amount_is_printed():
    prompt = Path(__file__).parents[1].joinpath("prompts", "extract_digital.txt").read_text()
    assert "Do not return an empty line_items array" in prompt


def test_older_harbour_invoice_dates_are_not_stripped():
    markdown = "\n".join([
        "Vendor name: Shree Ganesh Metals",
        "Invoice number: HG-1041",
        "Invoice date: 2026-10-12",
        "Credit note date: 2026-10-18",
        "Invoice date: 2026-11-20",
        "This invoice date is after the books date of 2026-10-29.",
        "Call the mill on 9876543210 before dispatch",
    ])
    kept = minimize_invoice_markdown(markdown)
    assert "Invoice date: 2026-10-12" in kept
    assert "Credit note date: 2026-10-18" in kept
    assert "Invoice date: 2026-11-20" in kept
    assert "2026-10-29" in kept
    assert "9876543210" not in kept
