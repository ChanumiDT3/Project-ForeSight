import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Radio, RadioGroup } from '@mui/material';
import { listActiveUsers } from '../api/endpoints';
import type { UserChoice } from '../api/types';
import { landingFor } from '../navigation/roles';
import { errorMessage } from '../utils/errors';
import { useCurrentUser } from './UserContext';

// PUBLIC_INTERFACE
export default function WhoAreYouDialog() {
  /** Choose and validate an active user before accessing role-driven screens. */
  const { user, chooserOpen, chooserNotice, closeChooser, chooseUser } = useCurrentUser();
  const navigate = useNavigate();
  const [choices, setChoices] = useState<UserChoice[]>([]);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (chooserOpen) {
      setSelected(user?.id ?? ''); setError(null);
      listActiveUsers().then(setChoices).catch(setError);
    }
  }, [chooserOpen, user?.id]);
  return <Dialog open={chooserOpen} onClose={user ? closeChooser : undefined} fullWidth maxWidth="xs">
    <DialogTitle>Who are you?</DialogTitle>
    <DialogContent>
      {chooserNotice && <Alert severity="warning">{chooserNotice}</Alert>}
      {Boolean(error) && <Alert severity="error">{errorMessage(error)}</Alert>}
      <RadioGroup value={selected} onChange={(event) => setSelected(event.target.value)}>
        {choices.map((choice) => <FormControlLabel key={choice.id} value={choice.id} control={<Radio />} label={`${choice.name}, ${choice.role}`} />)}
      </RadioGroup>
    </DialogContent>
    <DialogActions>
      {user && <Button onClick={closeChooser}>Cancel</Button>}
      <Button variant="contained" disabled={!selected} onClick={() => chooseUser(selected).then((current) => navigate(landingFor(current.role), { replace: true })).catch(setError)}>Continue</Button>
    </DialogActions>
  </Dialog>;
}
