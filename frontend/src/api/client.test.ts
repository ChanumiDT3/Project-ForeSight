import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiRequest, configureClient } from './client';

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

describe('apiRequest', () => {
  const onUnknownUser = vi.fn();
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onUnknownUser.mockReset();
    fetchMock = vi.fn();
    configureClient({
      baseUrl: 'http://api.test',
      getUserId: () => 'u-priya',
      onUnknownUser,
      fetchImpl: fetchMock as unknown as typeof fetch,
    });
  });

  it('sends X-User-Id on business reads and drops empty query values', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { data: [], total: 0, offset: 0, limit: 25 }));
    await apiRequest('/v1/work-orders', { query: { offset: 0, limit: 25, status: '', assignee: undefined } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://api.test/v1/work-orders?offset=0&limit=25');
    expect(init.headers['X-User-Id']).toBe('u-priya');
    expect(init.headers['Idempotency-Key']).toBeUndefined();
  });

  it('omits X-User-Id on public endpoints', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { data: [] }));
    await apiRequest('/v1/users', { isPublic: true });
    expect(fetchMock.mock.calls[0][1].headers['X-User-Id']).toBeUndefined();
  });

  it('adds an Idempotency-Key and a quoted If-Match to versioned mutations', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { data: { id: 'wo' } }));
    await apiRequest('/v1/work-orders/wo/start', { method: 'POST', version: 3 });
    const { headers } = fetchMock.mock.calls[0][1];
    expect(headers['If-Match']).toBe('"3"');
    expect(headers['Idempotency-Key']).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('retries a transient failure once with the same Idempotency-Key', async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError('network down'))
      .mockResolvedValueOnce(jsonResponse(201, { data: { reading: {} } }));
    await apiRequest('/v1/readings', { method: 'POST', body: { parameter_id: 'p', value: '1' } });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const first = fetchMock.mock.calls[0][1].headers['Idempotency-Key'];
    const second = fetchMock.mock.calls[1][1].headers['Idempotency-Key'];
    expect(first).toBe(second);
  });

  it('parses problem bodies into ApiError including extra fields', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(409, {
        type: 'urn:foresight:problem:active_work_order_exists',
        title: 'active_work_order_exists',
        status: 409,
        detail: 'This alert already has an active work order',
        instance: '/v1/alerts/a/work-orders',
        correlation_id: 'c-1',
        work_order_id: 'wo-9',
      }),
    );
    const error = await apiRequest('/v1/alerts/a/work-orders', { method: 'POST' }).catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw error;
    expect(error.code).toBe('active_work_order_exists');
    expect(error.correlationId).toBe('c-1');
    expect(error.extra.work_order_id).toBe('wo-9');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('notifies identity handling on 401 unknown_user', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(401, { title: 'unknown_user', status: 401, detail: 'Unknown or deactivated user' }),
    );
    await expect(apiRequest('/v1/alerts')).rejects.toBeInstanceOf(ApiError);
    expect(onUnknownUser).toHaveBeenCalledTimes(1);
  });

  it('does not treat 403 as an identity problem', async () => {
    fetchMock.mockResolvedValue(jsonResponse(403, { title: 'forbidden', status: 403, detail: 'Engineer role required' }));
    const error = await apiRequest('/v1/machines', { method: 'POST', body: {} }).catch((reason: unknown) => reason);
    if (!(error instanceof ApiError)) throw error;
    expect(error.status).toBe(403);
    expect(onUnknownUser).not.toHaveBeenCalled();
  });
});
