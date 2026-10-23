import { Navigate } from 'react-router-dom';
import { useCurrentUser } from '../auth/UserContext';
import { landingFor } from '../navigation/roles';

// PUBLIC_INTERFACE
export default function LandingRedirect() {
  /** Send the verified user to their role's landing screen (Q7b). */
  const { user } = useCurrentUser();
  return user ? <Navigate to={landingFor(user.role)} replace /> : null;
}
