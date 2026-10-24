import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField } from '@mui/material';
import { ApiError, SERVER_UNREACHABLE_CODE } from '../api/client';
import { listActiveUsers } from '../api/endpoints';
import type { UserChoice } from '../api/types';
import { landingFor } from '../navigation/roles';
import { errorMessage } from '../utils/errors';
import { useCurrentUser } from './UserContext';

/** Heading shown on the identity popup (there is no sign-in in the MVP, DL-10). */
export const WHO_ARE_YOU_TITLE = 'Let us know who you are!';

/** Message used when the public user list endpoint itself cannot be found. */
export const USER_LIST_UNREACHABLE_MESSAGE =
  'The user list could not be loaded because the ForeSight server could not be reached. ' +
  'Make sure the backend is running (port 3001) and that the frontend proxy (VITE_BACKEND_PROXY_TARGET) points to it.';

/** Message used when the server answered but has no active users yet. */
export const NO_USERS_MESSAGE =
  'No users are set up yet. Ask the development team to load the user list (python -m app.seed_users).';

function loadErrorMessage(error: unknown): string {
  // GET /v1/users is a public collection route, so a 404 never means "a user
  // record is missing". It means the request did not reach the ForeSight
  // backend (for example, the Vite dev proxy is not configured).
  if (error instanceof ApiError && error.status === 404) return USER_LIST_UNREACHABLE_MESSAGE;
  // A non-ForeSight 5xx means the dev proxy could not connect to the backend.
  if (error instanceof ApiError && error.code === SERVER_UNREACHABLE_CODE) return USER_LIST_UNREACHABLE_MESSAGE;
  return errorMessage(error);
}

// PUBLIC_INTERFACE
export default function WhoAreYouDialog() {
  /** Choose and validate an active user (from a dropdown) before accessing role-driven screens. */
  const { user, chooserOpen, chooserNotice, closeChooser, chooseUser } = useCurrentUser();
  const navigate = useNavigate();
  const [choices, setChoices] = useState<UserChoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState('');
  const [loadError, setLoadError] = useState<unknown>(null);
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!chooserOpen) return undefined;
    let cancelled = false;
    setSelected(user?.id ?? '');
    setLoadError(null);
    setSubmitError(null);
    setLoading(true);
    listActiveUsers()
      .then((rows) => { if (!cancelled) setChoices(rows); })
      .catch((reason) => { if (!cancelled) { setChoices([]); setLoadError(reason); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [chooserOpen, user?.id]);

  // MUI Select warns on values that are not among its options, so only pass a
  // selection that matches a loaded choice.
  const hasSelection = choices.some((choice) => choice.id === selected);
  const noUsers = !loading && !loadError && choices.length === 0;

  const submit = () => {
    setSubmitting(true);
    setSubmitError(null);
    chooseUser(selected)
      .then((current) => navigate(landingFor(current.role), { replace: true }))
      .catch(setSubmitError)
      .finally(() => setSubmitting(false));
  };

  return <Dialog open={chooserOpen} onClose={user ? closeChooser : undefined} fullWidth maxWidth="xs" aria-labelledby="who-are-you-title">
    <DialogTitle id="who-are-you-title">{WHO_ARE_YOU_TITLE}</DialogTitle>
    <DialogContent>
      <Stack spacing={2} sx={{ pt: 1 }}>
        {chooserNotice && <Alert severity="warning">{chooserNotice}</Alert>}
        {Boolean(loadError) && <Alert severity="error">{loadErrorMessage(loadError)}</Alert>}
        {noUsers && <Alert severity="info">{NO_USERS_MESSAGE}</Alert>}
        {Boolean(submitError) && <Alert severity="error">{errorMessage(submitError)}</Alert>}
        <TextField
          select
          fullWidth
          id="who-are-you-select"
          label="Select your name"
          value={hasSelection ? selected : ''}
          onChange={(event) => setSelected(event.target.value)}
          disabled={loading || choices.length === 0}
          helperText={loading ? 'Loading users…' : 'Your role decides which screens you see.'}
        >
          {choices.map((choice) => <MenuItem key={choice.id} value={choice.id}>{`${choice.name} (${choice.role})`}</MenuItem>)}
        </TextField>
      </Stack>
    </DialogContent>
    <DialogActions>
      {user && <Button onClick={closeChooser}>Cancel</Button>}
      <Button variant="contained" disabled={!hasSelection || submitting} onClick={submit}>Continue</Button>
    </DialogActions>
  </Dialog>;
}
