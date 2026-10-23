import { useState } from 'react';
import { Alert, Box, Button, Divider, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { registerMachine } from '../../api/endpoints';
import PageHeader from '../../components/PageHeader';
import ParameterFields, {
  newParameterDraft,
  toParameterPayload,
  validateParameterDraft,
  type ParameterDraft,
  type ParameterErrors,
} from '../../components/ParameterFields';
import { CRITICALITY_OPTIONS, RUNTIME_RULE } from '../../config/parameterRules';
import { errorMessage } from '../../utils/errors';
import { validateDecimal } from '../../utils/validation';

interface MachineForm {
  equipment_id: string;
  name: string;
  location: string;
  equipment_type: string;
  criticality: string;
}

// PUBLIC_INTERFACE
export default function MachineRegisterPage() {
  /** Register a machine with optional, validated monitoring parameters. */
  const navigate = useNavigate();
  const [form, setForm] = useState<MachineForm>({
    equipment_id: '',
    name: '',
    location: '',
    equipment_type: '',
    criticality: '1',
  });
  const [parameters, setParameters] = useState<ParameterDraft[]>([]);
  const [parameterErrors, setParameterErrors] = useState<Record<string, ParameterErrors>>({});
  const [baseline, setBaseline] = useState('');
  const [currentMeter, setCurrentMeter] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  const runtimeIncluded = parameters.some((parameter) => parameter.kind === 'runtime_hours');
  const setField = (field: keyof MachineForm, value: string) => setForm((current) => ({ ...current, [field]: value }));

  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = Object.fromEntries(parameters.map((parameter) => [parameter.key, validateParameterDraft(parameter)]));
    const baselineError = runtimeIncluded ? validateDecimal(baseline, RUNTIME_RULE) : null;
    const meterError = runtimeIncluded ? validateDecimal(currentMeter, RUNTIME_RULE) : null;
    setParameterErrors(nextErrors);
    if (
      Object.values(nextErrors).some((item) => Object.keys(item).length) ||
      baselineError ||
      meterError ||
      (runtimeIncluded && Number(baseline) > Number(currentMeter))
    ) {
      setError(runtimeIncluded && Number(baseline) > Number(currentMeter) ? new Error('Baseline cannot exceed the current meter.') : null);
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const machine = await registerMachine({
        equipment_id: form.equipment_id.trim(),
        name: form.name.trim(),
        location: form.location.trim(),
        equipment_type: form.equipment_type.trim(),
        criticality: Number(form.criticality),
        parameters: parameters.map(toParameterPayload),
        ...(runtimeIncluded ? { baseline: baseline.trim(), current_meter: currentMeter.trim() } : {}),
      });
      navigate(`/machines/${machine.id}`);
    } catch (reason) {
      setError(reason);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box>
      <PageHeader title="Register machine" subtitle="Parameters are optional; a machine without them is shown as Not monitored." />
      <Paper component="form" sx={{ p: 2.5 }} onSubmit={save}>
        <Stack spacing={2}>
          <TextField required label="Equipment ID" value={form.equipment_id} onChange={(event) => setField('equipment_id', event.target.value)} />
          <TextField required label="Name" value={form.name} onChange={(event) => setField('name', event.target.value)} />
          <TextField required label="Location" value={form.location} onChange={(event) => setField('location', event.target.value)} />
          <TextField required label="Equipment type" value={form.equipment_type} onChange={(event) => setField('equipment_type', event.target.value)} />
          <TextField select required label="Criticality" value={form.criticality} onChange={(event) => setField('criticality', event.target.value)}>
            {CRITICALITY_OPTIONS.map((option) => <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>)}
          </TextField>
        </Stack>

        <Divider sx={{ my: 3 }} />
        <Typography variant="h2" sx={{ mb: 2 }}>Health parameters</Typography>
        <Stack spacing={2}>
          {parameters.map((parameter, index) => (
            <Paper key={parameter.key} variant="outlined" sx={{ p: 2 }}>
              <Stack spacing={1.5}>
                <ParameterFields
                  draft={parameter}
                  errors={parameterErrors[parameter.key] ?? {}}
                  onChange={(next) => setParameters((current) => current.map((item, itemIndex) => itemIndex === index ? next : item))}
                  disabledKinds={parameters.filter((item) => item.key !== parameter.key).map((item) => item.kind)}
                />
                <Button color="error" onClick={() => setParameters((current) => current.filter((_, itemIndex) => itemIndex !== index))}>
                  Remove parameter
                </Button>
              </Stack>
            </Paper>
          ))}
          {runtimeIncluded && (
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              <TextField required label="Runtime baseline" value={baseline} onChange={(event) => setBaseline(event.target.value)} helperText="Hours at the last completed service." />
              <TextField required label="Current hour meter" value={currentMeter} onChange={(event) => setCurrentMeter(event.target.value)} helperText="Must be at least the baseline." />
            </Stack>
          )}
          <Box><Button onClick={() => setParameters((current) => [...current, newParameterDraft()])}>+ Add parameter</Button></Box>
        </Stack>
        {Boolean(error) && <Alert severity="error" sx={{ mt: 2 }}>{errorMessage(error)} Nothing was saved.</Alert>}
        <Box sx={{ mt: 3 }}><Button type="submit" variant="contained" disabled={submitting}>{submitting ? 'Saving…' : 'Register machine'}</Button></Box>
      </Paper>
    </Box>
  );
}
