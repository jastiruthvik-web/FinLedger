import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function AcceptInvite({ onDone }: { onDone: () => void }) {
  const params = new URLSearchParams(window.location.search);
  const tokenHash = params.get("token_hash") || "";
  const kind = params.get("type") || "";
  const incomplete = kind !== "invite" || !tokenHash;
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Set your password · FinLedger";
    api.csrf().catch((reason: unknown) => {
      setError(errorMessage(reason, "The desk could not start this invitation."));
    });
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.acceptInvite(tokenHash, password, confirm);
      onDone();
    } catch (reason) {
      setBusy(false);
      setError(errorMessage(reason, "This invitation could not be accepted."));
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-background px-4 py-10">
      <section className="w-full max-w-md rounded-[28px] border border-border bg-card px-6 py-10 shadow-[var(--shadow)] sm:px-10">
        <img src="/finledger-mark.png" alt="" className="size-12 rounded-xl" />
        <h1 className="mt-5 text-3xl font-semibold tracking-tight">Set your password</h1>
        <p className="mt-2 text-sm text-muted-foreground">Choose a password of at least 12 characters. Then sign in on this desk.</p>
        {incomplete ? (
          <p role="alert" className="mt-6 text-sm">This invitation link is incomplete.</p>
        ) : (
          <form className="mt-8 space-y-4" onSubmit={submit}>
            {error ? <p role="alert" className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{error}</p> : null}
            <label className="block text-sm font-medium">
              Password
              <Input className="mt-1.5" type="password" required minLength={12} maxLength={1024} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            <label className="block text-sm font-medium">
              Confirm password
              <Input className="mt-1.5" type="password" required minLength={12} maxLength={1024} autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} />
            </label>
            <Button type="submit" className="h-11 w-full" disabled={busy}>Save password</Button>
          </form>
        )}
      </section>
    </div>
  );
}
