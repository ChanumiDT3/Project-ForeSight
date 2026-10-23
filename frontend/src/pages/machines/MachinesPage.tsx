import { Box, Button, List, ListItem, ListItemText } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { listMachines } from '../../api/endpoints';
import { ErrorAlert, Loading } from '../../components/LoadState';
import PageHeader from '../../components/PageHeader';
import { useApi } from '../../hooks/useApi';
import { canManage } from '../../navigation/roles';
import { useCurrentUser } from '../../auth/UserContext';

// PUBLIC_INTERFACE
export default function MachinesPage() {
  /** List machines and allow Engineers to register additional equipment. */
  const { user } = useCurrentUser(); const machines = useApi((signal) => listMachines(0, 100, signal), []);
  return <Box><PageHeader title="Machines" actions={canManage(user?.role) ? <Button component={RouterLink} to="/machines/new" variant="contained">Register machine</Button> : undefined} /><ErrorAlert error={machines.error} onRetry={machines.reload} />{machines.loading ? <Loading /> : <List>{(machines.data?.data ?? []).map((machine: any) => <ListItem key={machine.id} component={RouterLink} to={`/machines/${machine.id}`}><ListItemText primary={`${machine.equipment_id} ${machine.name}`} secondary={`${machine.location} · ${machine.status}`} /></ListItem>)}</List>}</Box>;
}
