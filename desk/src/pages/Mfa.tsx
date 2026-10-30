import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/pages/Placeholder";

export function MfaPage({ onVerified }: { onVerified: () => void }) {
  const [factorId, setFactorId] = useState("");
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    api.mfa()
      .then((page) => { if (live) setFactorId(page.factor_id); })
      .catch((reason: unknown) => {
        if (live) setError(errorMessage(reason, "Two-step verification is not available."));
      });
    return () => { live = false; };
  }, []);

  async function enroll() {
    setBusy(true);
    setError("");
    try {
      const next = await api.enroll();
      setFactorId(next.factor_id);
      setSecret(next.secret);
    } catch (reason) {
      setError(errorMessage(reason, "MFA setup is unavailable."));
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.verify(factorId, code);
      onVerified();
    } catch (reason) {
      setBusy(false);
      setError(errorMessage(reason, "Code could not be verified."));
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-4">
      <PageHeader title="Two-step verification" description="Enter the code from your authenticator app before you open a client." />
      {error ? <p role="alert" className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{error}</p> : null}
      {factorId ? (
        <form className="space-y-4 rounded-xl border border-border bg-card p-4" onSubmit={verify}>
          {secret ? <p className="text-sm text-muted-foreground">Add this setup key to your authenticator app: <code>{secret}</code></p> : <p className="text-sm text-muted-foreground">Enter the six-digit code from your authenticator app.</p>}
          <label className="block text-sm font-medium">
            Authenticator code
            <Input className="mt-1.5" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value)} />
          </label>
          <Button type="submit" disabled={busy}>Verify code</Button>
        </form>
      ) : (
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Set up two-step verification with an authenticator app.</p>
          <Button className="mt-4" disabled={busy} onClick={() => { void enroll(); }}>Start setup</Button>
        </div>
      )}
    </div>
  );
}
