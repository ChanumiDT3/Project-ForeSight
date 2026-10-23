import { useState } from 'react';
import { Alert, Box, Button, MenuItem, TextField } from '@mui/material';
import { listReadingTargets, logReading } from '../api/endpoints';
import { ErrorAlert, Loading } from '../components/LoadState';
import PageHeader from '../components/PageHeader';
import { useApi } from '../hooks/useApi';

// PUBLIC_INTERFACE
export default function LogReadingPage() {
  /** Log one reading for a configured machine parameter. */
  const targets = useApi(() => listReadingTargets(), []);
  const [parameter, setParameter] = useState(''); const [value, setValue] = useState(''); const [message, setMessage] = useState('');
  if (targets.loading) return <Loading />;
  return <Box><PageHeader title="Log reading" /><ErrorAlert error={targets.error} onRetry={targets.reload} />
    <TextField select fullWidth label="Parameter" value={parameter} onChange={(event) => setParameter(event.target.value)}>
      {(targets.data ?? []).flatMap((target: any) => target.parameters ?? []).map((item: any) => <MenuItem key={item.id} value={item.id}>{item.name} ({item.unit})</MenuItem>)}
    </TextField>
    <TextField fullWidth label="Value" value={value} onChange={(event) => setValue(event.target.value)} sx={{ mt: 2 }} />
    <Button variant="contained" sx={{ mt: 2 }} disabled={!parameter || !value} onClick={() => logReading(parameter, value).then(() => { setMessage('Reading saved.'); setValue(''); }).catch((error) => setMessage(String(error)))}>Save reading</Button>
    {message && <Alert sx={{ mt: 2 }} severity={message === 'Reading saved.' ? 'success' : 'error'}>{message}</Alert>}
  </Box>;
}
