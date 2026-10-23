/**
 * Insert-only addenda on a Closed work order (original record unchanged).
 */
import { useState } from 'react';
import { Alert, Box, Button, List, ListItem, ListItemText, Stack, TextField, Typography } from '@mui/material';
import { addAddendum } from '../../api/endpoints';
import type { Addendum } from '../../api/types';
import { useDirectory } from '../../auth/DirectoryContext';
import { errorMessage } from '../../utils/errors';
import { formatDateTime } from '../../utils/format';

interface AddendaSectionProps {
  workOrderId: string;
  addenda: Addendum[];
  canAdd: boolean;
  onAdded: () => void;
}

// PUBLIC_INTERFACE
export default function AddendaSection({ workOrderId, addenda, canAdd, onAdded }: AddendaSectionProps) {
  /** List addenda and, for Engineers, append a new note. */
  const { nameOf } = useDirectory();
  const [note, setNote] = useState('');
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async () => {
    setTouched(true);
    if (!note.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await addAddendum(workOrderId, note.trim());
      setNote('');
      setTouched(false);
      onAdded();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box>
      {addenda.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No addenda.
        </Typography>
      ) : (
        <List dense disablePadding>
          {addenda.map((entry) => (
            <ListItem key={entry.id} disableGutters divider>
              <ListItemText
                primary={entry.note}
                secondary={`${nameOf(entry.created_by)} · ${formatDateTime(entry.created_at)}`}
                primaryTypographyProps={{ sx: { whiteSpace: 'pre-wrap' } }}
              />
            </ListItem>
          ))}
        </List>
      )}
      {canAdd && (
        <Stack spacing={1.5} sx={{ mt: 2, maxWidth: 640 }}>
          <TextField
            label="Addendum note"
            multiline
            minRows={2}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            error={touched && !note.trim()}
            helperText={touched && !note.trim() ? 'A note is required' : 'Appended with your name and time; the closed record is unchanged.'}
          />
          {Boolean(error) && <Alert severity="error">{errorMessage(error)}</Alert>}
          <Box>
            <Button variant="outlined" onClick={submit} disabled={saving}>
              {saving ? 'Adding…' : 'Add addendum'}
            </Button>
          </Box>
        </Stack>
      )}
    </Box>
  );
}
