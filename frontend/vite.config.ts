import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");

  const devHost = env.LISTEN_HOST ?? "localhost";
  const proxyHost = env.PROXY_HOST ?? "localhost";
  const proxyPort = env.API_PORT ?? "8000";
  console.log({
    plugins: [react()],
    server: {
      port: 5174,
      host: devHost,
      proxy: {
        "/api": `http://${proxyHost}:${proxyPort}`,
        "/ws": { target: `ws://${proxyHost}:${proxyPort}`, ws: true },
      },
    },
  });

  return {
    plugins: [react()],
    server: {
      port: 5174,
      host: devHost,
      proxy: {
        "/api": `http://${proxyHost}:${proxyPort}`,
        "/ws": { target: `ws://${proxyHost}:${proxyPort}`, ws: true },
      },
    },
  };
});
