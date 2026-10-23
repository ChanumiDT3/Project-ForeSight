/**
 * Display formatting. Timestamps are stored in UTC and shown in local time.
 */

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});

const dateFormat = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: '2-digit' });

// PUBLIC_INTERFACE
export function formatDateTime(value: string | null | undefined): string {
  /** Format a UTC ISO timestamp in the viewer's local time, or an em dash. */
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateTimeFormat.format(date);
}

// PUBLIC_INTERFACE
export function formatDate(value: string | null | undefined): string {
  /** Format a UTC ISO timestamp as a local date, or an em dash. */
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date);
}

// PUBLIC_INTERFACE
export function shortId(prefix: string, id: string | null | undefined): string {
  /** Render a readable reference for a UUID record, e.g. WO-1A2B3C4D. */
  if (!id) return '—';
  return `${prefix}-${id.replace(/-/g, '').slice(0, 8).toUpperCase()}`;
}

// PUBLIC_INTERFACE
export function withUnit(value: string | number | null | undefined, unit?: string | null): string {
  /** Join a value and its unit, or return an em dash when there is no value. */
  if (value === null || value === undefined || value === '') return '—';
  return unit ? `${value} ${unit}` : String(value);
}

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

// PUBLIC_INTERFACE
export function toLocalInputValue(value: string | Date | null | undefined): string {
  /** Convert an ISO timestamp/Date into a `datetime-local` input value. */
  if (!value) return '';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(
    date.getMinutes(),
  )}`;
}

// PUBLIC_INTERFACE
export function fromLocalInputValue(value: string): string | null {
  /** Convert a `datetime-local` value into an aware UTC ISO timestamp. */
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

// PUBLIC_INTERFACE
export function kindLabel(kind: string): string {
  /** Human label for a parameter kind. */
  switch (kind) {
    case 'temperature':
      return 'Temperature';
    case 'vibration':
      return 'Vibration';
    case 'cycle_count':
      return 'Cycle count';
    case 'runtime_hours':
      return 'Runtime hours';
    default:
      return 'Custom';
  }
}
