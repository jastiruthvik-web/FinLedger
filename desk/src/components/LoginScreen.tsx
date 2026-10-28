import { Eye, EyeOff, Moon, Sun } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, errorMessage } from "../api";
import { currentTheme, toggleTheme } from "../theme";
import { Button, Input } from "./ui";

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
    <div className="grid min-h-screen place-items-center bg-bg px-4 py-8">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-line bg-surface shadow-[var(--fl-shadow)] md:grid-cols-[minmax(0,0.92fr)_minmax(0,1fr)]">
        <section className="relative hidden min-h-[560px] flex-col justify-between overflow-hidden bg-[#0B3A66] p-10 text-white md:flex night:bg-[#121820]">
          <div
            className="pointer-events-none absolute inset-0 opacity-40"
            style={{
              backgroundImage: "linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)",
              backgroundSize: "28px 28px",
            }}
          />
          <div className="relative text-sm font-medium tracking-wide text-white/80">FinLedger</div>
          <div className="relative max-w-sm">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-[#8FB4D9]">Accounts payable</p>
            <h2 className="mt-3 text-4xl font-semibold leading-tight tracking-tight">Review the bill. Then post the voucher.</h2>
            <p className="mt-4 text-sm leading-6 text-white/75">A quiet desk for Indian firms. The source, what we read, and the voucher stay on one screen.</p>
          </div>
          <div className="relative grid grid-cols-3 gap-3 text-xs text-white/80">
            <div className="rounded-2xl border border-white/15 bg-white/8 p-3">Clients</div>
            <div className="rounded-2xl border border-white/15 bg-white/8 p-3">Queues</div>
            <div className="rounded-2xl border border-white/15 bg-white/8 p-3">Vouchers</div>
          </div>
        </section>
        <section className="relative flex flex-col justify-center px-6 py-10 sm:px-12">
          <button
            type="button"
            className="absolute right-5 top-5 inline-flex h-9 items-center gap-2 rounded-lg border border-line px-3 text-sm"
            aria-pressed={night}
            onClick={() => setNight(toggleTheme() === "night")}
          >
            {night ? <Sun size={15} /> : <Moon size={15} />}
            {night ? "Day" : "Night"}
          </button>
          <p className="text-sm font-medium text-muted">FinLedger</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">Welcome back</h1>
          <p className="mt-2 text-sm text-muted">Use the work email and password for your firm.</p>
          <form className="mt-8 space-y-4" onSubmit={submit}>
            {error && <p role="alert" className="rounded-lg border border-line bg-bg px-3 py-2 text-sm">{error}</p>}
            <label className="block text-sm font-medium">
              Email
              <Input className="mt-1.5" name="email" type="email" autoComplete="username" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label className="block text-sm font-medium">
              Password
              <span className="relative mt-1.5 block">
                <Input name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} className="pr-10" />
                <button type="button" className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center text-muted" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((value) => !value)}>
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
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
