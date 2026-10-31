"use client";

import { useState } from "react";

export function Close() {
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") || "").trim();
    const name = String(data.get("name") || "").trim();
    const role = String(data.get("role") || "").trim();
    const city = String(data.get("city") || "").trim();
    if (!name || !role || !city) {
      setDone(false);
      setError("Name, role, and city are required.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setDone(false);
      setError("Enter an email address with a domain.");
      return;
    }
    setError("");
    setDone(true);
  }

  return (
    <section id="request" className="section section-alt close" aria-labelledby="request-title">
      <div className="wrap close-grid">
        <div>
          <p className="kicker">08 — A note</p>
          <h2 id="request-title" className="h-section">
            One client. One door.
          </h2>
          <p className="lede">
            Tell us the practice and the city. This preview checks the fields in the browser. It does not transmit them.
          </p>
        </div>
        <form className="request-form" onSubmit={onSubmit} noValidate>
          <p className="fine">Preview only. Submitting sends nothing to a server.</p>
          <label className="field">
            <span>Name</span>
            <input name="name" autoComplete="name" required aria-invalid={error && !done ? true : undefined} />
          </label>
          <label className="field">
            <span>Role</span>
            <input name="role" autoComplete="organization-title" placeholder="Partner, accounts manager" required />
          </label>
          <label className="field">
            <span>City</span>
            <input name="city" autoComplete="address-level2" required />
          </label>
          <label className="field">
            <span>Work email</span>
            <input name="email" type="email" autoComplete="email" inputMode="email" required />
          </label>
          <label className="field">
            <span>Note, if you want one</span>
            <textarea name="note" rows={3} placeholder="Which books are you trying to put on one desk?" />
          </label>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="btn btn-primary" type="submit" disabled={done}>
            {done ? "Not sent" : "Check this note"}
          </button>
          <p className="form-status" role="status">
            {done ? "Checked in this browser. Nothing was transmitted." : "The button does not file, pay, or post."}
          </p>
        </form>
      </div>
    </section>
  );
}
