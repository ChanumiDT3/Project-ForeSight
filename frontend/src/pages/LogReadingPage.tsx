import { useState } from 'react';
import { Alert, Box, Button, MenuItem, TextField } from '@mui/material';
import { listReadingTargets, logReading } from '../api/endpoints';
import type { Parameter, ReadingTarget } from '../api/types';
import { ErrorAlert, Loading } from '../components/LoadState';
import PageHeader from '../components/PageHeader';
import { useApi } from '../hooks/useApi';

/** Shown inside the dropdown when no machine has a configured parameter yet. */
export const NO_PARAMETERS_MESSAGE = 'No parameters are configured yet. An Engineer must register equipment with health parameters first.';

interface ParameterOption { id: string; label: string }

// PUBLIC_INTERFACE
export function parameterOptions(targets: ReadingTarget[]): ParameterOption[] {
  /** Flatten machines into selectable options; only configured parameters are offered (UI Wireframes S3). */
  return targets.flatMap((target) => (target.parameters ?? []).map((item: Parameter) => ({
    id: item.id,
    // The machine prefix keeps options distinct when machines share parameter names.
    label: `${target.equipment_id} ${target.name} – ${item.name} (${item.unit})`,
  })));
}

// PUBLIC_INTERFACE
export default function LogReadingPage() {
  /** Log one reading for a configured machine parameter. */
  const targets = useApi(() => listReadingTargets(), []);
  const [parameter, setParameter] = useState(''); const [value, setValue] = useState(''); const [message, setMessage] = useState('');
  if (targets.loading) return <Loading />;
  const options = parameterOptions(targets.data ?? []);
  return <Box><PageHeader title="Log reading" /><ErrorAlert error={targets.error} onRetry={targets.reload} />
    <TextField select fullWidth label="Parameter" value={parameter} onChange={(event) => setParameter(event.target.value)}>
      {options.length
        ? options.map((option) => <MenuItem key={option.id} value={option.id}>{option.label}</MenuItem>)
        : <MenuItem value="" disabled>{NO_PARAMETERS_MESSAGE}</MenuItem>}
    </TextField>
    <TextField fullWidth label="Value" value={value} onChange={(event) => setValue(event.target.value)} sx={{ mt: 2 }} />
    <Button variant="contained" sx={{ mt: 2 }} disabled={!parameter || !value} onClick={() => logReading(parameter, value).then(() => { setMessage('Reading saved.'); setValue(''); }).catch((error) => setMessage(String(error)))}>Save reading</Button>
    {message && <Alert sx={{ mt: 2 }} severity={message === 'Reading saved.' ? 'success' : 'error'}>{message}</Alert>}
  </Box>;
}
