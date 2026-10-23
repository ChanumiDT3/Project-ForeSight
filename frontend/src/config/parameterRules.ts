import type { ParameterKind } from '../api/types';
export const NAMED_PARAMETER_RULES: Record<Exclude<ParameterKind, 'custom'>, any> = {
  temperature: { label: 'Temperature', unit: 'degrees C', minimum: '0', maximum: '1000', precision: 1, cumulative: false },
  vibration: { label: 'Vibration', unit: 'mm/s', minimum: '0', maximum: '200', precision: 2, cumulative: false },
  cycle_count: { label: 'Cycle count', unit: 'cycles', minimum: '0', maximum: '999999999', precision: 0, cumulative: true },
  runtime_hours: { label: 'Runtime hours', unit: 'hours', minimum: '0', maximum: '200000', precision: 1, cumulative: true },
};
export const PARAMETER_KINDS: ParameterKind[] = ['temperature', 'vibration', 'cycle_count', 'runtime_hours', 'custom'];
export const RUNTIME_RULE = NAMED_PARAMETER_RULES.runtime_hours;
export const CRITICALITY_OPTIONS = [
  { value: 3, label: '3 — Line-stopping or safety-related, no backup' },
  { value: 2, label: '2 — Reduced output or costly workaround' },
  { value: 1, label: '1 — Minor impact, backup available' },
];
