import { useEffect, useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField } from '@mui/material';
import { errorMessage } from '../utils/errors';

interface ReasonDialogProps {
  open: boolean;
  title: string;
  confirmLabel: string;
  description?: string;
  onClose: () => void;
  /** Perform the command; a thrown error is shown and nothing is closed. */
  onConfirm: (reason: string) => Promise<void>;
}

// PUBLIC_INTERFACE
export default function ReasonDialog({ open, title, confirmLabel, description, onClose, onConfirm }: ReasonDialogProps) {
  /** Collect a required free-text reason and run a command with it. */
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (open) {
      setReason('');
      setTouched(false);
      setError(null);
    }
  }, [open]);

  const blank = !reason.trim();
  const submit = async () => {
    setTouched(true);
    if (blank) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="sm" aria-labelledby="reason-dialog-title">
      <DialogTitle id="reason-dialog-title">{title}</DialogTitle>
      <DialogContent>
        {description && <Alert severity="info" sx={{ mb: 2 }}>{description}</Alert>}
        <TextField
          autoFocus
          label="Reason"
          required
          fullWidth
          multiline
          minRows={3}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          onBlur={() => setTouched(true)}
          error={touched && blank}
          helperText={touched && blank ? 'A reason is required' : ' '}
        />
        {Boolean(error) && <Alert severity="error">{errorMessage(error)} Nothing was saved.</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          Back
        </Button>
        <Button variant="contained" color="error" onClick={submit} disabled={busy}>
          {busy ? 'Saving…' : confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
