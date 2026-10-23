import { Checkbox, FormControlLabel, MenuItem, TextField } from '@mui/material';
import type { ParameterKind, ParameterPayload } from '../api/types';
import { NAMED_PARAMETER_RULES, PARAMETER_KINDS } from '../config/parameterRules';

export interface ParameterDraft {
  key: string; kind: ParameterKind; name: string; threshold: string; suggested_action: string;
  unit: string; minimum: string; maximum: string; precision: string; cumulative: boolean;
}
export type ParameterErrors = Partial<Record<keyof ParameterDraft, string>>;
let count = 0;

// PUBLIC_INTERFACE
export function newParameterDraft(kind: ParameterKind = 'temperature'): ParameterDraft {
  /** Create an editable health-parameter draft. */
  const rule = kind === 'custom' ? undefined : NAMED_PARAMETER_RULES[kind];
  return { key: `draft-${++count}`, kind, name: rule?.label ?? '', threshold: '', suggested_action: '', unit: '', minimum: '', maximum: '', precision: '', cumulative: rule?.cumulative ?? false };
}
// PUBLIC_INTERFACE
export function validateParameterDraft(draft: ParameterDraft): ParameterErrors {
  /** Perform basic client validation; backend validation remains authoritative. */
  const errors: ParameterErrors = {};
  if (!draft.name.trim()) errors.name = 'Name is required';
  if (!draft.threshold.trim() || Number(draft.threshold) <= 0) errors.threshold = 'Maximum limit must be greater than 0';
  if (draft.kind === 'custom') {
    if (!draft.unit.trim()) errors.unit = 'Unit is required';
    if (!draft.minimum.trim() || !Number.isFinite(Number(draft.minimum))) errors.minimum = 'A numeric minimum is required';
    if (!draft.maximum.trim() || !Number.isFinite(Number(draft.maximum))) errors.maximum = 'A numeric maximum is required';
    if (!/^\d+$/.test(draft.precision)) errors.precision = 'Use a whole number of decimal places';
    if (!errors.minimum && !errors.maximum && Number(draft.minimum) > Number(draft.maximum)) {
      errors.maximum = 'Maximum must be at least the minimum';
    }
  }
  return errors;
}
// PUBLIC_INTERFACE
export function toParameterPayload(draft: ParameterDraft): ParameterPayload {
  /** Convert a validated draft to the backend request contract. */
  return draft.kind === 'custom'
    ? { kind: draft.kind, name: draft.name.trim(), threshold: draft.threshold.trim(), suggested_action: draft.suggested_action, unit: draft.unit.trim(), minimum: draft.minimum.trim(), maximum: draft.maximum.trim(), precision: Number(draft.precision), cumulative: draft.cumulative }
    : { kind: draft.kind, name: draft.name.trim(), threshold: draft.threshold.trim(), suggested_action: draft.suggested_action };
}

// PUBLIC_INTERFACE
export default function ParameterFields({ draft, errors, onChange, disabledKinds = [] }: { draft: ParameterDraft; errors: ParameterErrors; onChange: (draft: ParameterDraft) => void; disabledKinds?: ParameterKind[] }) {
  /** Render the editable fields for a health parameter. */
  const set = (patch: Partial<ParameterDraft>) => onChange({ ...draft, ...patch });
  return <>
    <TextField select fullWidth label="Parameter type" value={draft.kind} onChange={(event) => onChange({ ...newParameterDraft(event.target.value as ParameterKind), key: draft.key })}>
      {PARAMETER_KINDS.map((kind) => <MenuItem key={kind} value={kind} disabled={disabledKinds.includes(kind)}>{kind.replace('_', ' ')}</MenuItem>)}
    </TextField>
    <TextField fullWidth required label="Name" value={draft.name} onChange={(event) => set({ name: event.target.value })} error={Boolean(errors.name)} helperText={errors.name} />
    <TextField fullWidth required label="Maximum limit" value={draft.threshold} onChange={(event) => set({ threshold: event.target.value })} error={Boolean(errors.threshold)} helperText={errors.threshold} />
    {draft.kind === 'custom' && <><TextField fullWidth required label="Unit" value={draft.unit} onChange={(event) => set({ unit: event.target.value })} error={Boolean(errors.unit)} helperText={errors.unit} /><TextField fullWidth required label="Minimum valid reading" value={draft.minimum} onChange={(event) => set({ minimum: event.target.value })} error={Boolean(errors.minimum)} helperText={errors.minimum} /><TextField fullWidth required label="Maximum valid reading" value={draft.maximum} onChange={(event) => set({ maximum: event.target.value })} error={Boolean(errors.maximum)} helperText={errors.maximum} /><TextField fullWidth required label="Decimal places" value={draft.precision} inputProps={{ inputMode: 'numeric' }} onChange={(event) => set({ precision: event.target.value })} error={Boolean(errors.precision)} helperText={errors.precision} /></>}
    <TextField fullWidth label="Suggested action" value={draft.suggested_action} onChange={(event) => set({ suggested_action: event.target.value })} />
    <FormControlLabel control={<Checkbox checked={draft.cumulative} disabled={draft.kind !== 'custom'} onChange={(event) => set({ cumulative: event.target.checked })} />} label="Cumulative (reading can never decrease)" />
  </>;
}
