import { useState } from 'react';
import { Box, Button, List, ListItem, ListItemText, MenuItem, Paper, Stack, TextField } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { listWorkOrders } from '../api/endpoints';
import type { WorkOrderStatus } from '../api/types';
import { useDirectory } from '../auth/DirectoryContext';
import { useCurrentUser } from '../auth/UserContext';
import { ErrorAlert, Loading } from '../components/LoadState';
import PageHeader from '../components/PageHeader';
import { useApi } from '../hooks/useApi';

const STATUSES: WorkOrderStatus[] = ['Open', 'In Progress', 'Closed', 'Cancelled'];

// PUBLIC_INTERFACE
export default function WorkOrdersPage() {
  /** Show work orders with server-side status, assignee, and current-user filters. */
  const { user } = useCurrentUser();
  const { engineers, nameOf } = useDirectory();
  const [status, setStatus] = useState<WorkOrderStatus | ''>('');
  const [assignee, setAssignee] = useState('');
  const [mine, setMine] = useState(false);
  const selectedAssignee = mine ? (user?.id ?? '') : assignee;

  const orders = useApi(
    (signal) => listWorkOrders({ offset: 0, limit: 100, status, assignee: selectedAssignee || undefined }, signal),
    [status, selectedAssignee],
  );

  return (
    <Box>
      <PageHeader title="Work orders" />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
          <TextField select label="Status" value={status} onChange={(event) => setStatus(event.target.value as WorkOrderStatus | '')}>
            <MenuItem value="">All statuses</MenuItem>
            {STATUSES.map((option) => <MenuItem key={option} value={option}>{option}</MenuItem>)}
          </TextField>
          <TextField select label="Assignee" value={assignee} disabled={mine} onChange={(event) => setAssignee(event.target.value)}>
            <MenuItem value="">All assignees</MenuItem>
            {engineers.map((engineer) => <MenuItem key={engineer.id} value={engineer.id}>{engineer.name}</MenuItem>)}
          </TextField>
          <Button variant={mine ? 'contained' : 'outlined'} onClick={() => setMine((active) => !active)} disabled={!user}>
            Mine
          </Button>
        </Stack>
      </Paper>
      <ErrorAlert error={orders.error} onRetry={orders.reload} />
      {orders.loading ? (
        <Loading />
      ) : (
        <List>
          {(orders.data?.data ?? []).map((order) => (
            <ListItem key={order.id} component={RouterLink} to={`/work-orders/${order.id}`}>
              <ListItemText
                primary={`${order.snapshot.equipment_id} · ${order.status}`}
                secondary={`${order.assignee ? nameOf(order.assignee) : 'Unassigned'} · Due ${order.due_at ?? '—'}`}
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  );
}
