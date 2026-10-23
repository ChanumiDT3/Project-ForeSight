import { ApiError } from '../api/client';

// PUBLIC_INTERFACE
export function errorMessage(error: unknown): string {
  /** Translate an API or unexpected error into a user-facing sentence. */
  if (error instanceof ApiError) {
    switch (error.code) {
      case 'stale_version':
        return 'Someone else changed this record. Reload to see the latest version, then try again.';
      case 'unknown_user':
        return 'Your selected user is no longer available. Please choose who you are again.';
      case 'idempotency_conflict':
        return 'This request conflicted with an earlier attempt. Reload and try again.';
      case 'database_unconfigured':
      case 'plant_unconfigured':
        return 'The ForeSight server is not configured yet. Contact the development team.';
      default:
        break;
    }
    if (error.status === 403) return `You do not have permission to do this. ${error.detail}`;
    if (error.status === 404) return 'This record was not found.';
    return error.detail || 'The request failed.';
  }
  if (error instanceof Error) return error.message;
  return 'Something went wrong.';
}

// PUBLIC_INTERFACE
export function isAbort(error: unknown): boolean {
  /** True for fetch aborts caused by navigation/unmount. */
  return error instanceof DOMException && error.name === 'AbortError';
}
