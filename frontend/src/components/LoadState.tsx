import { Alert, Box, Button, CircularProgress } from '@mui/material';
import { ApiError } from '../api/client';
import { errorMessage } from '../utils/errors';

// PUBLIC_INTERFACE
export function Loading({ label = 'Loading' }: { label?: string }) {
  /** Centered progress indicator. */
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
      <CircularProgress aria-label={label} />
    </Box>
  );
}

// PUBLIC_INTERFACE
export function ErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  /** Error banner with optional retry and the server correlation ID for support. */
  if (!error) return null;
  const correlation = error instanceof ApiError ? error.correlationId : undefined;
  return (
    <Alert
      severity="error"
      role="alert"
      sx={{ mb: 2 }}
      action={
        onRetry ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        ) : undefined
      }
    >
      {errorMessage(error)}
      {correlation && (
        <Box component="span" sx={{ display: 'block', fontSize: '0.75rem', opacity: 0.8 }}>
          Reference: {correlation}
        </Box>
      )}
    </Alert>
  );
}
