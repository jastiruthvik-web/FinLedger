import json
import socket
from pathlib import Path

from usage.providers.transport import FakeGeminiTransport, TransportResponse

from run_evals import main


def test_non_mock_provider_requires_live_flag():
    assert main(["--provider-mode", "gemini", "--report", "/tmp/eval-gate.md"]) == 1


def test_live_flag_refuses_mock_and_ci_stays_mock_only(tmp_path):
    assert main([
        "--provider-mode", "mock", "--live-synthetic-eval",
        "--fixtures-dir", str(tmp_path), "--report", str(tmp_path / "live.md"),
    ]) == 1
    workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "--provider-mode mock" in text
    assert "--live-synthetic-eval" not in text


def test_live_flag_without_explicit_settings_does_not_open_a_socket(tmp_path, monkeypatch):
    monkeypatch.setenv("FINLEDGER_LLM_PROVIDER", "gemini")
    monkeypatch.delenv("FINLEDGER_GEMINI_LOCATION", raising=False)
    monkeypatch.delenv("FINLEDGER_MODEL_EXTRACT", raising=False)
    monkeypatch.delenv("FINLEDGER_GEMINI_PROJECT", raising=False)
    monkeypatch.delenv("FINLEDGER_GEMINI_CREDENTIAL", raising=False)
    monkeypatch.delenv("FINLEDGER_ENV", raising=False)
    monkeypatch.setenv("FINLEDGER_GEMINI_FALLBACK_LOCATION", "us-central1")

    def exploded(*_args, **_kwargs):
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "create_connection", exploded)
    report = tmp_path / "live.md"
    code = main([
        "--provider-mode", "gemini", "--live-synthetic-eval",
        "--fixtures-dir", str(tmp_path), "--report", str(report),
    ])
    assert code == 1
    assert not report.exists()


def test_live_eval_records_model_location_tokens_and_unpriced_cost(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FINLEDGER_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("FINLEDGER_GEMINI_LOCATION", "asia-south1")
    monkeypatch.setenv("FINLEDGER_MODEL_EXTRACT", "gemini-2.5-flash")
    monkeypatch.setenv("FINLEDGER_GEMINI_PROJECT", "finledger-local")
    monkeypatch.setenv("FINLEDGER_GEMINI_CREDENTIAL", "CANARYSECRET")
    monkeypatch.delenv("FINLEDGER_ENV", raising=False)
    invoice = {
        "document_id": "doc-live", "document_type": "purchase_invoice",
        "vendor": {"name": "Local Tech"}, "invoice_no": "INV-01", "invoice_date": "2026-09-01", "total": 10,
    }
    transport = FakeGeminiTransport([
        TransportResponse(json.dumps(invoice), 17, 4, 3),
    ])
    monkeypatch.setattr("usage.live_gemini.build_explicit_transport", lambda _settings: transport)

    def exploded(*_args, **_kwargs):
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "create_connection", exploded)
    (tmp_path / "sample.md").write_text("Vendor: Local Tech\nInv No: INV-01\nTotal: 10\n", encoding="utf-8")
    report_path = tmp_path / "live.md"
    assert main([
        "--provider-mode", "gemini", "--live-synthetic-eval",
        "--fixtures-dir", str(tmp_path), "--report", str(report_path),
    ]) == 0
    report = report_path.read_text(encoding="utf-8")
    captured = capsys.readouterr()
    for text in (report, captured.out, captured.err):
        assert "CANARYSECRET" not in text
        assert "us-central1" not in text
        assert "gemini-1.5-flash" not in text
    assert "gemini-2.5-flash" in report
    assert "asia-south1" in report
    assert "**Tokens in:** 17" in report
    assert "**Tokens out:** 4" in report
    assert "**Cost USD:** unpriced" in report
    assert "sample.md" not in report
    assert transport.calls[0]["model"] == "gemini-2.5-flash"
    assert transport.calls[0]["location"] == "asia-south1"
