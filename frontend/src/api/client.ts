export const USER_ID_HEADER = 'X-User-Id';

export class ApiError extends Error {
  // PUBLIC_INTERFACE
  constructor(
    readonly status: number,
    readonly code: string,
    readonly detail: string,
    readonly correlationId?: string,
    readonly extra: Record<string, unknown> = {},
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

interface Config {
  baseUrl: string;
  getUserId: () => string | null;
  onUnknownUser: () => void;
  fetchImpl: typeof fetch;
}
const config: Config = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, ''),
  getUserId: () => null,
  onUnknownUser: () => undefined,
  fetchImpl: (...args) => fetch(...args),
};

// PUBLIC_INTERFACE
export function configureClient(partial: Partial<Config>): void {
  /** Configure identity callbacks and test transport overrides. */
  Object.assign(config, partial);
}

// PUBLIC_INTERFACE
export function newIdempotencyKey(): string {
  /** Create a UUID suitable for an Idempotency-Key header. */
  return globalThis.crypto?.randomUUID?.() ??
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (letter) => {
      const value = Math.floor(Math.random() * 16);
      return (letter === 'x' ? value : (value & 3) | 8).toString(16);
    });
}

export type QueryValue = string | number | boolean | null | undefined;
export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT';
  body?: unknown;
  version?: number;
  idempotencyKey?: string;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
  isPublic?: boolean;
  userId?: string;
}

function url(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  });
  return `${config.baseUrl}${path}${params.size ? `?${params}` : ''}`;
}

async function problem(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => ({})) as Record<string, unknown>;
  const { type: _type, title, status: _status, detail, instance: _instance, correlation_id, ...extra } = body;
  return new ApiError(
    response.status,
    typeof title === 'string' ? title : `http_${response.status}`,
    typeof detail === 'string' ? detail : response.statusText || 'Request failed',
    typeof correlation_id === 'string' ? correlation_id : response.headers.get('X-Correlation-ID') ?? undefined,
    extra,
  );
}

// PUBLIC_INTERFACE
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  /** Call the REST API, retrying one transient mutation with its original key. */
  const method = options.method ?? 'GET';
  const mutation = method !== 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  const userId = options.userId ?? config.getUserId();
  if (!options.isPublic && userId) headers[USER_ID_HEADER] = userId;
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.version !== undefined) headers['If-Match'] = `"${options.version}"`;
  if (mutation) headers['Idempotency-Key'] = options.idempotencyKey ?? newIdempotencyKey();

  let lastError: ApiError | undefined;
  for (let attempt = 0; attempt < (mutation ? 2 : 1); attempt += 1) {
    try {
      const response = await config.fetchImpl(url(path, options.query), {
        method, headers, signal: options.signal,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
      if (response.ok) return response.status === 204 ? undefined as T : await response.json() as T;
      const error = await problem(response);
      if (error.status === 401 && error.code === 'unknown_user' && !options.userId) config.onUnknownUser();
      if (!(error.status === 503 && attempt === 0 && mutation)) throw error;
      lastError = error;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error instanceof DOMException && error.name === 'AbortError') throw error;
      lastError = new ApiError(0, 'network_error', 'Cannot reach the ForeSight server. Check your connection and try again.');
    }
  }
  throw lastError ?? new ApiError(0, 'network_error', 'Request failed');
}
