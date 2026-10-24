import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * Vite configuration for the ForeSight frontend.
 *
 * Environment (see .env.example; values are requested from the user/orchestrator):
 * - PORT: dev/preview server port (defaults to 3000 for the hosted preview).
 * - VITE_API_BASE_URL: absolute backend origin used by the browser. Leave empty
 *   to call the API on the same origin (for example through the proxy below).
 * - VITE_BACKEND_PROXY_TARGET: optional backend origin the dev server proxies
 *   `/v1` and `/health` to, which avoids CORS during development. When blank it
 *   defaults to the local backend port from .project_manifest.yaml (3001).
 *   Without a proxy, Vite itself answers `/v1/...` JSON requests with 404, which
 *   the UI would otherwise report as "record not found".
 */
const DEFAULT_BACKEND_PROXY_TARGET = 'http://127.0.0.1:3001';

/**
 * Resolve the proxy target, pinning `localhost` to the IPv4 loopback address.
 *
 * The documented backend command (`uvicorn ... --host 127.0.0.1`, also uvicorn's
 * default host) listens on IPv4 only, while Node 17+ may resolve `localhost` to
 * the IPv6 address `::1` first (common on Windows). The proxy then cannot
 * connect and Vite answers every `/v1` call with a bare
 * "500 Internal Server Error". Other hosts are left unchanged.
 */
function resolveProxyTarget(value: string | undefined): string {
  const raw = value?.trim() || DEFAULT_BACKEND_PROXY_TARGET;
  try {
    const url = new URL(raw);
    if (url.hostname === 'localhost') url.hostname = '127.0.0.1';
    return `${url.protocol}//${url.host}${url.pathname.replace(/\/+$/, '')}`;
  } catch {
    // Leave unparseable values to Vite so its own error explains the problem.
    return raw;
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const port = Number(env.PORT || 3000);
  const proxyTarget = resolveProxyTarget(env.VITE_BACKEND_PROXY_TARGET);
  const proxy = {
    '/v1': { target: proxyTarget, changeOrigin: true },
    '/health': { target: proxyTarget, changeOrigin: true },
  };

  return {
    plugins: [react()],
    server: { host: '0.0.0.0', port, strictPort: true, allowedHosts: true, proxy },
    preview: { host: '0.0.0.0', port, strictPort: true, allowedHosts: true, proxy },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.ts',
      css: false,
    },
  };
});
