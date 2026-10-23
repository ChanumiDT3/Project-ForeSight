import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Alert, Button } from '@mui/material';
import type { Role } from '../api/types';
import { useCurrentUser } from '../auth/UserContext';
import { landingFor } from '../navigation/roles';

// PUBLIC_INTERFACE
export default function RequireRole({ roles, children }: { roles: readonly Role[]; children: ReactNode }) {
  /** Render children only for allowed roles; the backend still enforces 403. */
  const { user } = useCurrentUser();
  if (!user) return null;
  if (!roles.includes(user.role)) {
    return (
      <Alert
        severity="warning"
        action={
          <Button component={RouterLink} to={landingFor(user.role)} color="inherit" size="small">
            Go to my screen
          </Button>
        }
      >
        This screen is not available for the {user.role} role.
      </Alert>
    );
  }
  return <>{children}</>;
}
