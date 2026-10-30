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
