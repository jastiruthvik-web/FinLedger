import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type ProxyOptions } from "vite";

function apiProxy(target: string): ProxyOptions {
  return {
    target,
    changeOrigin: true,
    configure(proxy) {
      // The control service checks Origin against the host it received.
      proxy.on("proxyReq", (proxyReq) => {
        proxyReq.setHeader("origin", target);
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = (env.FINLEDGER_CONTROL_ORIGIN || "http://127.0.0.1:8770").replace(/\/$/, "");
  const proxy = { "/api": apiProxy(target) };
  return {
    plugins: [react(), tailwindcss()],
    server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy },
    preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
  };
});
