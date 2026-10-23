import { NavLink, Outlet } from 'react-router-dom';
import { Alert, AppBar, Box, Button, Container, Link, Toolbar, Typography } from '@mui/material';
import { useCurrentUser } from '../auth/UserContext';
import { menuFor } from '../navigation/roles';
import { ErrorAlert, Loading } from './LoadState';

// PUBLIC_INTERFACE
export default function AppLayout() {
  /** Render the persistent header, selected identity, and routed screen. */
  const { user, status, error, openChooser, retry } = useCurrentUser();
  return <Box sx={{ minHeight: '100vh' }}>
    <AppBar position="sticky"><Toolbar sx={{ gap: 2, flexWrap: 'wrap' }}>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>ForeSight</Typography>
      <Box component="nav" sx={{ display: 'flex', gap: 1, flexGrow: 1 }}>
        {(user ? menuFor(user.role) : []).map((item) => <Button key={item.path} component={NavLink} to={item.path} color="inherit">{item.label}</Button>)}
      </Box>
      {user && <Typography variant="body2">Signed in as <strong>{user.name}</strong> ({user.role}) <Link component="button" color="inherit" onClick={openChooser}>Switch user</Link></Typography>}
    </Toolbar></AppBar>
    <Container component="main" maxWidth="lg" sx={{ py: 3 }}>
      {status === 'resolving' && <Loading label="Checking selected user" />}
      {status === 'error' && <ErrorAlert error={error} onRetry={retry} />}
      {status === 'choosing' && <Alert severity="info">Choose who you are to continue.</Alert>}
      {status === 'ready' && user && <Outlet />}
    </Container>
  </Box>;
}
