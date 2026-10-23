import { Link as RouterLink } from 'react-router-dom';
import { Alert, Button } from '@mui/material';

// PUBLIC_INTERFACE
export default function NotFoundPage() {
  /** Shown for unknown routes. */
  return (
    <Alert
      severity="warning"
      action={
        <Button component={RouterLink} to="/" color="inherit" size="small">
          Go to my screen
        </Button>
      }
    >
      This page does not exist.
    </Alert>
  );
}
