import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the FastAPI backend, so the browser only
// ever talks to one origin.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const target = env.VITE_API_PROXY_TARGET || "http://localhost:8000";
  // Hostnames allowed when the app is shared through an ngrok tunnel.
  const allowedHosts = [".ngrok-free.app", ".ngrok-free.dev", ".ngrok.app", ".ngrok.dev", ".ngrok.io"];
  return {
    plugins: [react()],
    build: {
      // Atlassian Design System packages go into their own long-cached chunk.
      rollupOptions: {
        output: {
          manualChunks: (id: string) => {
            if (!id.includes("node_modules")) return undefined;
            // Leave ADS theme files as separate lazy chunks (loaded per colour mode).
            if (id.includes("@atlaskit/tokens/dist/esm/artifacts/themes/")) return undefined;
            return id.includes("@atlaskit") ? "atlaskit" : "vendor";
          },
        },
      },
      chunkSizeWarningLimit: 700,
    },
    server: {
      port: 5173,
      host: true,
      allowedHosts,
      proxy: { "/api": { target, changeOrigin: true } },
    },
    preview: {
      port: 4173,
      allowedHosts,
      proxy: { "/api": { target, changeOrigin: true } },
    },
  };
});
