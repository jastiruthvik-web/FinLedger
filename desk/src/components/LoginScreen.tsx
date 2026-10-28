import { Eye, EyeOff, Moon, Sun } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { currentTheme, toggleTheme } from "@/theme";

export function LoginScreen({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [night, setNight] = useState(currentTheme() === "night");

  useEffect(() => {
    document.title = "Sign in · FinLedger";
    api.csrf().catch((reason: unknown) => {
      setError(reason instanceof ApiError && reason.status === 404
        ? "Sign-in is not configured on this control server."
        : errorMessage(reason, "The desk could not start sign-in."));
    });
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.login(email, password);
      onSignedIn();
    } catch (reason) {
      setBusy(false);
      setError(reason instanceof ApiError && reason.status === 404
        ? "Sign-in is not configured on this control server."
        : errorMessage(reason, "Sign-in failed."));
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-background px-4 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-border bg-card shadow-[var(--shadow)] md:grid-cols-2">
        <section className="relative hidden min-h-[560px] flex-col items-center justify-center bg-[#0B1C33] px-10 md:flex">
          <img src="/finledger-logo.png" alt="FinLedger" className="h-16 w-auto" />
          <p className="mt-8 max-w-xs text-center text-sm leading-6 text-[#8FB4D9]">Accounts payable for Indian CA firms. Review the bill, then post the voucher.</p>
        </section>
        <section className="relative flex flex-col items-center justify-center px-6 py-12 sm:px-12">
          <button
            type="button"
            className="absolute right-5 top-5 inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm text-foreground"
            aria-pressed={night}
            onClick={() => setNight(toggleTheme() === "night")}
          >
            {night ? <Sun className="size-4" /> : <Moon className="size-4" />}
            {night ? "Day" : "Night"}
          </button>
          <img src="/finledger-mark.png" alt="" className="size-12 rounded-xl" />
          <h1 className="mt-5 text-center text-3xl font-semibold tracking-tight text-foreground">Welcome back</h1>
          <p className="mt-2 text-center text-sm text-muted-foreground">Use the work email and password for your firm.</p>
          <form className="mt-8 w-full max-w-sm space-y-4" onSubmit={submit}>
            {error && <p role="alert" className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{error}</p>}
            <label className="block text-sm font-medium text-foreground">
              Email
              <Input className="mt-1.5" name="email" type="email" autoComplete="username" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label className="block text-sm font-medium text-foreground">
              Password
              <span className="relative mt-1.5 block">
                <Input name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} className="pr-10" />
                <button type="button" className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center text-muted-foreground" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((value) => !value)}>
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </span>
            </label>
            <Button type="submit" className="h-11 w-full" disabled={busy}>Sign in</Button>
          </form>
        </section>
      </div>
    </div>
  );
}
