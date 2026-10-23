/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute backend origin; empty means same origin. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
