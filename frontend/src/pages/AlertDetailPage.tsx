import { Box, Button, Paper, Typography } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { createWorkOrder, getAlert } from '../api/endpoints';
import { ErrorAlert, Loading } from '../components/LoadState';
import PageHeader from '../components/PageHeader';
import { useApi } from '../hooks/useApi';
import { canManage } from '../navigation/roles';
import { useCurrentUser } from '../auth/UserContext';

// PUBLIC_INTERFACE
export default function AlertDetailPage() {
  /** Display stored alert priority evidence and linked operational action. */
  const { alertId = '' } = useParams(); const navigate = useNavigate(); const { user } = useCurrentUser();
  const alert = useApi((signal) => getAlert(alertId, signal), [alertId]);
  if (alert.loading) return <Loading />; if (!alert.data) return <ErrorAlert error={alert.error} onRetry={alert.reload} />;
  const data: any = alert.data;
  return <Box><PageHeader title={`Alert ${data.id}`} subtitle={`${data.priority_label} · ${data.status}`} actions={canManage(user?.role) && data.status === 'Open' ? <Button variant="contained" onClick={() => createWorkOrder(data.id).then((workOrder) => navigate(`/work-orders/${workOrder.id}`))}>Create work order</Button> : undefined} />
    <Paper sx={{ p: 2 }}><Typography>Latest value: {data.latest_value}</Typography><Typography>Latest breach: {data.latest_breach_at}</Typography><Typography>Breach count: {data.breach_count}</Typography><Typography>Priority score: {data.breakdown?.priority_score ?? data.priority_score}</Typography></Paper>
  </Box>;
}
