/**
 * S7 Close Work Order (journey step 4). Only In Progress orders close, and the
 * backend saves everything or nothing (DL-08).
 *
 * When the runtime reset applies, the hour-meter field is prefilled with the
 * latest saved reading; it must not be lower than the latest reading or the
 * current baseline. The closure reading is not evaluated for a breach (Q3a).
 * A missing baseline rejects the closure (Q3c).
 */
import { useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Checkbox, FormControlLabel, IconButton, Stack, TextField, Typography } from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { ApiError } from '../../api/client';
import { closeWorkOrder, getMachine } from '../../api/endpoints';
import type { ClosureResult, WorkOrder } from '../../api/types';
import { useApi } from '../../hooks/useApi';
import { RUNTIME_RULE } from '../../config/parameterRules';
import { errorMessage } from '../../utils/errors';
import { parseFieldErrors, validateDecimal, validateQuantity } from '../../utils/validation';

interface PartRow {
  part_name: string;
  part_number: string;
  quantity: string;
  notes: string;
}

interface ClosureSectionProps {
  workOrder: WorkOrder;
  /** True while the planning form has unsaved changes. */
  planningDirty: boolean;
  onCancel: () => void;
  onClosed: (result: ClosureResult) => void;
}

// PUBLIC_INTERFACE
export default function ClosureSection({ workOrder, planningDirty, onCancel, onClosed }: ClosureSectionProps) {
  /** Collect closure data and submit it atomically. */
  const resetApplies = workOrder.reset_applies;
  const machine = useApi(
    (signal) => (resetApplies ? getMachine(workOrder.machine_id, signal) : Promise.resolve(undefined)),
    [resetApplies, workOrder.machine_id],
  );
  const runtimeParameter = machine.data?.parameters.find((parameter) => parameter.kind === 'runtime_hours');
  const latest = runtimeParameter?.latest_value ?? null;
  const baseline = machine.data?.baseline ?? null;

  const [note, setNote] = useState('');
  const [parts, setParts] = useState<PartRow[]>(() =>
    (workOrder.parts_checklist ?? []).map((item) => ({
      part_name: item.part_name,
      part_number: item.part_number ?? '',
      quantity: String(item.quantity),
      notes: item.notes ?? '',
    })),
  );
  const [noParts, setNoParts] = useState(false);
  const [hourMeter, setHourMeter] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // Prefill the hour meter with the latest saved reading once known.
  useEffect(() => {
    if (resetApplies && latest && !hourMeter) setHourMeter(latest);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetApplies, latest]);

  const floor = useMemo(() => {
    const candidates = [
      latest ? { value: latest, label: 'latest saved reading' } : null,
      baseline ? { value: baseline, label: 'current baseline' } : null,
    ].filter(Boolean) as Array<{ value: string; label: string }>;
    return candidates.sort((a, b) => Number(b.value) - Number(a.value))[0] ?? null;
  }, [latest, baseline]);

  const validate = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    if (!note.trim()) errors.resolution_note = 'A resolution note is required';
    if (noParts && parts.length) errors.parts_used = 'Remove the listed parts or untick “No parts used”';
    if (!noParts && !parts.length) errors.parts_used = 'List the parts used or tick “No parts used”';
    parts.forEach((part, index) => {
      if (!part.part_name.trim()) errors[`part_name_${index}`] = 'Required';
      const quantityError = validateQuantity(part.quantity);
      if (quantityError) errors[`quantity_${index}`] = quantityError;
    });
    if (resetApplies) {
      const meterError = validateDecimal(hourMeter, {
        minimum: RUNTIME_RULE.minimum,
        maximum: RUNTIME_RULE.maximum,
        precision: RUNTIME_RULE.precision,
        unit: RUNTIME_RULE.unit,
        notBelow: floor,
      });
      if (meterError) errors.hour_meter_value = meterError;
    }
    return errors;
  };

  const submit = async () => {
    setError(null);
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;

    setSubmitting(true);
    try {
      const result = await closeWorkOrder(
        workOrder.id,
        {
          resolution_note: note.trim(),
          parts_used: noParts
            ? []
            : parts.map((part) => ({
                part_name: part.part_name.trim(),
                part_number: part.part_number.trim() || null,
                quantity: Number(part.quantity),
                notes: part.notes.trim() || null,
              })),
          no_parts_used: noParts,
          ...(resetApplies ? { hour_meter_value: hourMeter.trim() } : {}),
        },
        workOrder.version,
      );
      onClosed(result);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'closure_validation') {
        setFieldErrors(parseFieldErrors(err.detail));
      }
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      {planningDirty && (
        <Alert severity="warning">
          You have unsaved planning changes. Closing uses the saved work order, including the saved scheduled-service
          setting.
        </Alert>
      )}
      <TextField
        label="Resolution note"
        required
        multiline
        minRows={3}
        value={note}
        onChange={(event) => setNote(event.target.value)}
        error={Boolean(fieldErrors.resolution_note)}
        helperText={fieldErrors.resolution_note ?? ' '}
      />

      <Box>
        <Typography variant="h3" sx={{ mb: 1 }}>
          Parts used *
        </Typography>
        {parts.map((part, index) => (
          <Stack key={index} direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mb: 1 }}>
            <TextField
              label="Part name"
              required
              disabled={noParts}
              value={part.part_name}
              onChange={(event) =>
                setParts((current) => current.map((row, i) => (i === index ? { ...row, part_name: event.target.value } : row)))
              }
              error={Boolean(fieldErrors[`part_name_${index}`])}
              helperText={fieldErrors[`part_name_${index}`] ?? ' '}
            />
            <TextField
              label="Part no."
              disabled={noParts}
              value={part.part_number}
              onChange={(event) =>
                setParts((current) => current.map((row, i) => (i === index ? { ...row, part_number: event.target.value } : row)))
              }
              helperText=" "
            />
            <TextField
              label="Qty"
              required
              disabled={noParts}
              value={part.quantity}
              inputProps={{ inputMode: 'numeric' }}
              onChange={(event) =>
                setParts((current) => current.map((row, i) => (i === index ? { ...row, quantity: event.target.value } : row)))
              }
              error={Boolean(fieldErrors[`quantity_${index}`])}
              helperText={fieldErrors[`quantity_${index}`] ?? ' '}
              sx={{ maxWidth: { md: 110 } }}
            />
            <TextField
              label="Notes"
              disabled={noParts}
              value={part.notes}
              onChange={(event) =>
                setParts((current) => current.map((row, i) => (i === index ? { ...row, notes: event.target.value } : row)))
              }
              helperText=" "
              sx={{ flexGrow: 1 }}
            />
            <IconButton
              aria-label={`Remove used part ${index + 1}`}
              disabled={noParts}
              onClick={() => setParts((current) => current.filter((_, i) => i !== index))}
            >
              <DeleteOutlineIcon />
            </IconButton>
          </Stack>
        ))}
        <Stack direction="row" spacing={2} alignItems="center">
          <Button
            disabled={noParts}
            onClick={() => setParts((current) => [...current, { part_name: '', part_number: '', quantity: '1', notes: '' }])}
          >
            + Add part used
          </Button>
          <FormControlLabel
            control={<Checkbox checked={noParts} onChange={(event) => setNoParts(event.target.checked)} />}
            label="No parts used"
          />
        </Stack>
        {fieldErrors.parts_used && (
          <Typography variant="caption" color="error" role="alert">
            {fieldErrors.parts_used}
          </Typography>
        )}
      </Box>

      {resetApplies && (
        <Box>
          {machine.error ? <Alert severity="error">{errorMessage(machine.error)}</Alert> : null}
          {machine.data && baseline === null && (
            <Alert severity="error" sx={{ mb: 1 }}>
              Baseline missing for this machine. Closure will be rejected until the development team corrects it.
            </Alert>
          )}
          <TextField
            label="Hour-meter reading at service"
            required
            value={hourMeter}
            inputProps={{ inputMode: 'decimal' }}
            onChange={(event) => setHourMeter(event.target.value)}
            error={Boolean(fieldErrors.hour_meter_value)}
            helperText={
              fieldErrors.hour_meter_value ??
              `Prefilled with the latest saved reading — confirm or change. ${RUNTIME_RULE.minimum} – ${RUNTIME_RULE.maximum} hours, 1 decimal; not lower than ${
                latest ?? '—'
              } (latest reading) or ${baseline ?? '—'} (current baseline). Becomes the new baseline.`
            }
            sx={{ maxWidth: 520 }}
            fullWidth
          />
        </Box>
      )}

      {Boolean(error) && (
        <Alert severity="error" role="alert">
          {error instanceof ApiError && error.code === 'baseline_missing'
            ? 'Baseline missing for this machine.'
            : errorMessage(error)}{' '}
          Nothing was saved; the work order stays open.
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button variant="contained" color="success" onClick={submit} disabled={submitting}>
          {submitting ? 'Closing…' : 'Close work order'}
        </Button>
        <Button onClick={onCancel} disabled={submitting}>
          Back
        </Button>
      </Box>
    </Stack>
  );
}
