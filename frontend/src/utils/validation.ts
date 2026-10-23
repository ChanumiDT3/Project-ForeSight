/**
 * Client-side checks that mirror the backend's validation so errors appear
 * next to the field before a request is sent. The backend stays authoritative.
 */

export interface DecimalRule {
  minimum?: string | number | null;
  maximum?: string | number | null;
  precision?: number | null;
  unit?: string | null;
  /** Value must be strictly greater than this (e.g. thresholds > 0). */
  greaterThan?: number;
  /** Value must not be lower than this (cumulative / baseline floors). */
  notBelow?: { value: string | number; label: string } | null;
}

const DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/;

// PUBLIC_INTERFACE
export function decimalPlaces(value: string): number {
  /** Count significant decimal places, ignoring trailing zeros (as the backend does). */
  const fraction = value.split('.')[1] ?? '';
  return fraction.replace(/0+$/, '').length;
}

// PUBLIC_INTERFACE
export function validateDecimal(raw: string, rule: DecimalRule = {}): string | null {
  /** Return an error message for an invalid decimal entry, or null when valid. */
  const value = raw.trim();
  if (!value) return 'A value is required';
  if (!DECIMAL_PATTERN.test(value)) return 'Enter a number, for example 12.5';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 'Enter a finite number';
  const unit = rule.unit ? ` ${rule.unit}` : '';

  if (rule.greaterThan !== undefined && !(numeric > rule.greaterThan)) {
    return `Must be greater than ${rule.greaterThan}${unit}`;
  }
  const hasMin = rule.minimum !== undefined && rule.minimum !== null && rule.minimum !== '';
  const hasMax = rule.maximum !== undefined && rule.maximum !== null && rule.maximum !== '';
  if ((hasMin && numeric < Number(rule.minimum)) || (hasMax && numeric > Number(rule.maximum))) {
    return `Value must be between ${rule.minimum ?? '−∞'} and ${rule.maximum ?? '∞'}${unit}`;
  }
  if (rule.precision !== undefined && rule.precision !== null && decimalPlaces(value) > rule.precision) {
    return rule.precision === 0 ? 'Whole numbers only' : `At most ${rule.precision} decimal place(s)`;
  }
  if (rule.notBelow && numeric < Number(rule.notBelow.value)) {
    return `Cannot be lower than the ${rule.notBelow.label} (${rule.notBelow.value})`;
  }
  return null;
}

// PUBLIC_INTERFACE
export function validateQuantity(raw: string | number): string | null {
  /** Parts quantity must be a whole number of at least 1 (Q2d). */
  const value = String(raw).trim();
  if (!/^\d+$/.test(value) || Number(value) < 1) return 'Whole number, at least 1';
  return null;
}

// PUBLIC_INTERFACE
export function parseFieldErrors(detail: string): Record<string, string> {
  /**
   * Split backend "field: message; field: message" details into a map keyed by
   * the last path segment (e.g. "body.value: decimal_parsing" -> {value: ...}).
   */
  const result: Record<string, string> = {};
  detail
    .split(';')
    .map((part) => part.trim())
    .filter(Boolean)
    .forEach((part) => {
      const index = part.indexOf(':');
      if (index <= 0) return;
      const path = part.slice(0, index).trim();
      const message = part.slice(index + 1).trim();
      const key = path.split('.').filter((segment) => !/^\d+$/.test(segment)).pop() ?? path;
      result[key] = result[key] ? `${result[key]}; ${message}` : message;
    });
  return result;
}
