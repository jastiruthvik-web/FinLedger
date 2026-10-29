# FinLedger review desk

React, TypeScript, and Tailwind screens for the control service. The service still scores, maps, and approves. This app only calls `/api`.

## Open it locally

Start the control service on port 8770 (see `person3_control_ui/README.md`), then:

```text
cd desk
npm install
npm run dev
```

Open http://127.0.0.1:5173 .

The dev server proxies `/api` to http://127.0.0.1:8770 . Set `FINLEDGER_CONTROL_ORIGIN` if the API is on another origin.

Browser sign-in uses the same Supabase settings as the control service (`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `FINLEDGER_ENC_KEY`).

## Served by the control service

```text
cd desk
npm run build
```

Restart `finledger-control` and open http://127.0.0.1:8770 in a browser. The server uses `desk/dist` for browser page loads. Requests that do not ask for HTML still get the existing pages.
