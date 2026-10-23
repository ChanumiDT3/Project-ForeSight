/**
 * S9 Dashboard (read-only; Managers and Engineers, Q5b). "Open" means Open
 * plus In Progress for alerts and work orders (Q5a). Managers reach Machine
 * Detail from the at-risk list (Q7c).
 */
import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Grid,
  Link,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { getDashboard } from '../api/endpoints';
import type { PriorityLabel } from '../api/types';
import { useDirectory } from '../auth/DirectoryContext';
import { ErrorAlert, Loading } from '../components/LoadState';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { useApi } from '../hooks/useApi';
import { formatDate, shortId } from '../utils/format';

const PRIORITIES: Array<{ label: PriorityLabel; color: string }> = [
  { label: 'Critical', color: 'error.main' },
  { label: 'High', color: 'warning.main' },
  { label: 'Medium', color: 'info.main' },
];

// PUBLIC_INTERFACE
export default function DashboardPage() {
  /** Read-only overview with location and equipment-type filters. */
  const { nameOf } = useDirectory();
  const [location, setLocation] = useState('');
  const [equipmentType, setEquipmentType] = useState('');
  const dashboard = useApi(
    (signal) =>
      getDashboard({ location: location || undefined, equipment_type: equipmentType || undefined }, signal),
    [location, equipmentType],
  );
  const data = dashboard.data;

  return (
    <Box>
      <PageHeader title="Dashboard" subtitle="Read-only. “Open” includes Open and In Progress." />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField select label="Location" value={location} onChange={(event) => setLocation(event.target.value)} sx={{ minWidth: 200 }}>
            <MenuItem value="">All locations</MenuItem>
            {(data?.filters.locations ?? []).map((item) => (
              <MenuItem key={item} value={item}>
                {item}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Equipment type"
            value={equipmentType}
            onChange={(event) => setEquipmentType(event.target.value)}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="">All types</MenuItem>
            {(data?.filters.equipment_types ?? []).map((item) => (
              <MenuItem key={item} value={item}>
                {item}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      </Paper>

      <ErrorAlert error={dashboard.error} onRetry={dashboard.reload} />
      {dashboard.loading && !data && <Loading />}
      {data && (
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Paper sx={{ p: 2.5 }}>
              <Typography variant="h2" sx={{ mb: 2 }}>
                Open alerts by priority
              </Typography>
              <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                {PRIORITIES.map((priority) => (
                  <Box
                    key={priority.label}
                    sx={{ borderLeft: 4, borderColor: priority.color, pl: 2, pr: 4, py: 1, bgcolor: 'grey.50', borderRadius: 1 }}
                  >
                    <Typography variant="body2" color="text.secondary">
                      {priority.label}
                    </Typography>
                    <Typography variant="h4" component="p" sx={{ fontWeight: 600 }}>
                      {data.open_alerts_by_priority[priority.label] ?? 0}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </Paper>
          </Grid>
          <Grid item xs={12} md={5}>
            <Paper sx={{ height: '100%' }}>
              <Typography variant="h2" sx={{ p: 2, pb: 1 }}>
                At-risk machines ({data.at_risk_machines.total})
              </Typography>
              <TableContainer>
                <Table size="small" aria-label="At-risk machines">
                  <TableHead>
                    <TableRow>
                      <TableCell>ID</TableCell>
                      <TableCell>Name</TableCell>
                      <TableCell>Location</TableCell>
                      <TableCell align="right">Open alerts</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.at_risk_machines.items.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={4}>No machines at risk.</TableCell>
                      </TableRow>
                    )}
                    {data.at_risk_machines.items.map((machine) => (
                      <TableRow key={machine.id}>
                        <TableCell>
                          <Link component={RouterLink} to={`/machines/${machine.id}`}>
                            {machine.equipment_id}
                          </Link>
                        </TableCell>
                        <TableCell>{machine.name}</TableCell>
                        <TableCell>{machine.location}</TableCell>
                        <TableCell align="right">{machine.active_alert_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
          <Grid item xs={12} md={7}>
            <Paper sx={{ height: '100%' }}>
              <Typography variant="h2" sx={{ p: 2, pb: 1 }}>
                Open work orders ({data.open_work_orders.total})
              </Typography>
              <TableContainer>
                <Table size="small" aria-label="Open work orders">
                  <TableHead>
                    <TableRow>
                      <TableCell>Work order</TableCell>
                      <TableCell>Machine</TableCell>
                      <TableCell>Priority</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Assignee</TableCell>
                      <TableCell>Due</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.open_work_orders.items.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6}>No open work orders.</TableCell>
                      </TableRow>
                    )}
                    {data.open_work_orders.items.map((order) => (
                      <TableRow key={order.id}>
                        <TableCell>
                          <Link component={RouterLink} to={`/work-orders/${order.id}`}>
                            {shortId('WO', order.id)}
                          </Link>
                        </TableCell>
                        <TableCell>
                          {order.equipment_id} {order.machine_name}
                        </TableCell>
                        <TableCell>
                          <StatusChip label={order.priority} />
                        </TableCell>
                        <TableCell>
                          <StatusChip label={order.status} />
                        </TableCell>
                        <TableCell>{order.assignee ? nameOf(order.assignee) : 'Unassigned'}</TableCell>
                        <TableCell>{formatDate(order.due_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}
    </Box>
  );
}
