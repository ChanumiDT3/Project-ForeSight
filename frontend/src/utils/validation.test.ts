import { describe, expect, it } from 'vitest';
import { parseFieldErrors, validateDecimal, validateQuantity } from './validation';

describe('validateDecimal', () => {
  const temperature = { minimum: '0', maximum: '1000', precision: 1, unit: 'degrees C' };

  it('accepts inclusive range bounds and trailing zeros', () => {
    expect(validateDecimal('1000', temperature)).toBeNull();
    expect(validateDecimal('85.50', temperature)).toBeNull();
  });

  it('rejects out-of-range, over-precise and non-numeric values', () => {
    expect(validateDecimal('1000.1', temperature)).toBe('Value must be between 0 and 1000 degrees C');
    expect(validateDecimal('85.25', temperature)).toBe('At most 1 decimal place(s)');
    expect(validateDecimal('abc', temperature)).toMatch(/Enter a number/);
    expect(validateDecimal('', temperature)).toBe('A value is required');
  });

  it('enforces cumulative floors but accepts an equal value', () => {
    const rule = { ...temperature, notBelow: { value: '5100.0', label: 'latest reading' } };
    expect(validateDecimal('5099.9', rule)).toBe('Cannot be lower than the latest reading (5100.0)');
    expect(validateDecimal('5100', rule)).toBeNull();
  });

  it('requires thresholds greater than zero', () => {
    expect(validateDecimal('0', { greaterThan: 0 })).toBe('Must be greater than 0');
  });
});

describe('validateQuantity', () => {
  it('accepts whole numbers of at least 1 only', () => {
    expect(validateQuantity('2')).toBeNull();
    expect(validateQuantity('0')).not.toBeNull();
    expect(validateQuantity('1.5')).not.toBeNull();
  });
});

describe('parseFieldErrors', () => {
  it('maps closure and validation details by last field name', () => {
    expect(
      parseFieldErrors('resolution_note: A resolution note is required; hour_meter_value: Cannot be lower than the previous baseline (5000)'),
    ).toEqual({
      resolution_note: 'A resolution note is required',
      hour_meter_value: 'Cannot be lower than the previous baseline (5000)',
    });
    expect(parseFieldErrors('body.parameters.0.threshold: greater_than')).toEqual({ threshold: 'greater_than' });
  });
});
