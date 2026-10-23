import { Box, List, ListItem, ListItemText } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { listAlerts } from '../api/endpoints';
import { ErrorAlert, Loading } from '../components/LoadState';
import PageHeader from '../components/PageHeader';
import { useApi } from '../hooks/useApi';

// PUBLIC_INTERFACE
export default function AlertQueuePage() {
  /** Show the backend-prioritized alert queue. */
  const alerts = useApi((signal) => listAlerts(0, 100, signal), []);
  return <Box><PageHeader title="Alerts" /><ErrorAlert error={alerts.error} onRetry={alerts.reload} />{alerts.loading ? <Loading /> : <List>{(alerts.data?.data ?? []).map((alert: any) => <ListItem key={alert.id} component={RouterLink} to={`/alerts/${alert.id}`}><ListItemText primary={`${alert.priority_label}: ${alert.machine?.equipment_id ?? ''} ${alert.parameter?.name ?? ''}`} secondary={alert.status} /></ListItem>)}</List>}</Box>;
}
