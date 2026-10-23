/**
 * S8 Machine Detail (journey step 5). Status is derived from open alerts.
 * After a closure the page shows the outcome (alert Resolved, work order
 * Closed, new baseline). Reading history is immutable; closure readings are
 * marked as such (Q3a).
 */
import { useEffect, useState } from 'react';
import { Link as RouterLink, useLocation, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
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
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { getMachine, listParameterReadings } from '../../api/endpoints';
import { useDirectory } from '../../auth/DirectoryContext';
import { useCurrentUser } from '../../auth/UserContext';
import DetailList from '../../components/DetailList';
import { ErrorAlert, Loading } from '../../components/LoadState';
import PageHeader from '../../components/PageHeader';
import StatusChip from '../../components/StatusChip';
import { useApi } from '../../hooks/useApi';
import { canManage } from '../../navigation/roles';
import { formatDateTime, kindLabel, shortId, withUnit } from '../../utils/format';
import type { ClosureOutcome } from '../work-order/WorkOrderDetailPage';

// PUBLIC_INTERFACE
export default function MachineDetailPage() {
  /** Machine detail with parameters, runtime baseline and reading history. */
  const { machineId = '' } = useParams();
  const location = useLocation();
  const closure = (location.state as { closure?: ClosureOutcome } | null)?.closure;
  const { user } = useCurrentUser();
  const { nameOf } = useDirectory();
  const machine = useApi((signal) => getMachine(machineId, signal), [machineId]);
  const [parameterId, setParameterId] = useState('');
  const [page, setPage] = useState(0);
  const rowsPerPage = 20;

  // Default the history to the runtime parameter, else the first parameter.
  useEffect(() => {
    const parameters = machine.data?.parameters ?? [];
    if (!parameters.length || parameters.some((parameter) => parameter.id === parameterId)) return;
    const runtime = parameters.find((parameter) => parameter.kind === 'runtime_hours');
    setParameterId((runtime ?? parameters[0]).id);
  }, [machine.data, parameterId]);

  const readings = useApi(
    (signal) =>
      parameterId ? listParameterReadings(parameterId, page * rowsPerPage, rowsPerPage, signal) : Promise.resolve(undefined),
    [parameterId, page],
  );

  if (machine.loading && !machine.data) return <Loading />;
  if (!machine.data) return <ErrorAlert error={machine.error} onRetry={machine.reload} />;

  const data = machine.data;
  const engineer = canManage(user?.role);
  const selectedParameter = data.parameters.find((parameter) => parameter.id === parameterId);
  const runtimeParameter = data.parameters.find((parameter) => parameter.kind === 'runtime_hours');

  return (
    <Box>
      <PageHeader
        back={{ to: '/machines', label: 'Machines' }}
        title={
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
            <span>
              {data.equipment_id} {data.name}
            </span>
            <StatusChip label={data.status} size="medium" />
          </Stack>
        }
        subtitle={engineer ? undefined : 'Read-only view.'}
        actions={
          engineer ? (
            <>
              <Button variant="outlined" component={RouterLink} to={`/machines/${data.id}/edit`}>
                Edit
              </Button>
              <Button variant="outlined" component={RouterLink} to="/log-reading">
                Log reading
              </Button>
            </>
          ) : undefined
        }
      />

      {closure && (
        <Alert severity="success" sx={{ mb: 2 }} role="status">
          Work order{' '}
          <Link component={RouterLink} to={`/work-orders/${closure.workOrderId}`}>
            {shortId('WO', closure.workOrderId)}
          </Link>{' '}
          is Closed (read-only; addenda can be added). Alert{' '}
          <Link component={RouterLink} to={`/alerts/${closure.alertId}`}>
            {shortId('A', closure.alertId)}
          </Link>{' '}
          is Resolved. Machine status: {closure.machineStatus}. Last service {formatDateTime(closure.lastServiceAt)}.
          {closure.newBaseline && ` New runtime baseline: ${closure.newBaseline} hours.`}
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2.5, height: '100%' }}>
            <Typography variant="h2" sx={{ mb: 2 }}>
              Machine
            </Typography>
            <DetailList
              items={[
                { label: 'Location', value: data.location },
                { label: 'Type', value: data.equipment_type },
                { label: 'Criticality', value: data.criticality },
                { label: 'Monitoring', value: <StatusChip label={data.monitoring_state} /> },
                { label: 'Active alerts', value: data.active_alert_count },
                { label: 'Last service', value: formatDateTime(data.last_service_at) },
                { label: 'Registered', value: `${nameOf(data.created_by)} · ${formatDateTime(data.created_at)}` },
                { label: 'Last updated', value: `${nameOf(data.updated_by)} · ${formatDateTime(data.updated_at)}` },
              ]}
            />
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2.5, height: '100%' }}>
            <Typography variant="h2" sx={{ mb: 2 }}>
              Runtime baseline
            </Typography>
            {!data.runtime_applicable ? (
              <Typography variant="body2" color="text.secondary">
                No runtime-hours parameter: closures do not affect runtime.
              </Typography>
            ) : (
              <>
                <DetailList
                  items={[
                    { label: 'State', value: <StatusChip label={data.runtime_state} /> },
                    { label: 'Current baseline', value: data.baseline ? `${data.baseline} hours` : 'Baseline missing' },
                    { label: 'Latest hour meter', value: withUnit(runtimeParameter?.latest_value, 'hours') },
                    {
                      label: 'Hours since service',
                      value:
                        data.runtime_state === 'Data error'
                          ? 'Data error'
                          : withUnit(data.hours_since_service, 'hours'),
                    },
                  ]}
                />
                {data.baseline_history.length > 0 && (
                  <Table size="small" aria-label="Baseline history" sx={{ mt: 2 }}>
                    <TableHead>
                      <TableRow>
                        <TableCell>When</TableCell>
                        <TableCell>Old → new</TableCell>
                        <TableCell>Work order</TableCell>
                        <TableCell>By</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {data.baseline_history.map((row) => (
                        <TableRow key={row.id}>
                          <TableCell>{formatDateTime(row.created_at)}</TableCell>
                          <TableCell>
                            {row.old_baseline} → {row.new_baseline}
                          </TableCell>
                          <TableCell>
                            <Link component={RouterLink} to={`/work-orders/${row.work_order_id}`}>
                              {shortId('WO', row.work_order_id)}
                            </Link>
                          </TableCell>
                          <TableCell>{nameOf(row.created_by)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Paper sx={{ mt: 2 }}>
        <Typography variant="h2" sx={{ p: 2, pb: 1 }}>
          Health parameters
        </Typography>
        {data.parameters.length === 0 ? (
          <Alert severity="info" sx={{ m: 2 }}>
            Not monitored: no parameters configured yet{engineer ? '. Use Edit to add one.' : '.'}
          </Alert>
        ) : (
          <TableContainer>
            <Table size="small" aria-label="Health parameters">
              <TableHead>
                <TableRow>
                  <TableCell>Parameter</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Max limit</TableCell>
                  <TableCell>Cumulative</TableCell>
                  <TableCell>Latest value</TableCell>
                  <TableCell>Latest reading</TableCell>
                  <TableCell>Suggested action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.parameters.map((parameter) => (
                  <TableRow key={parameter.id}>
                    <TableCell>{parameter.name}</TableCell>
                    <TableCell>{kindLabel(parameter.kind)}</TableCell>
                    <TableCell>{withUnit(parameter.threshold, parameter.unit)}</TableCell>
                    <TableCell>{parameter.cumulative ? 'Yes' : 'No'}</TableCell>
                    <TableCell>{withUnit(parameter.latest_value, parameter.unit)}</TableCell>
                    <TableCell>{formatDateTime(parameter.latest_reading_at)}</TableCell>
                    <TableCell>{parameter.suggested_action || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {data.parameters.length > 0 && (
        <Paper sx={{ mt: 2 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }} sx={{ p: 2, pb: 1 }}>
            <Typography variant="h2" sx={{ flexGrow: 1 }}>
              Reading history
            </Typography>
            <TextField
              select
              label="Parameter"
              value={parameterId}
              onChange={(event) => {
                setParameterId(event.target.value);
                setPage(0);
              }}
              sx={{ minWidth: 220 }}
            >
              {data.parameters.map((parameter) => (
                <MenuItem key={parameter.id} value={parameter.id}>
                  {parameter.name}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <ErrorAlert error={readings.error} onRetry={readings.reload} />
          <TableContainer>
            <Table size="small" aria-label="Reading history">
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Value</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>By</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {readings.data?.data.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4}>No readings logged yet.</TableCell>
                  </TableRow>
                )}
                {(readings.data?.data ?? []).map((reading) => (
                  <TableRow key={reading.id}>
                    <TableCell>{formatDateTime(reading.created_at)}</TableCell>
                    <TableCell>{withUnit(reading.value, selectedParameter?.unit)}</TableCell>
                    <TableCell>
                      {reading.source === 'closure' ? (
                        <>
                          Closure reading
                          {reading.work_order_id && (
                            <>
                              {' '}
                              (
                              <Link component={RouterLink} to={`/work-orders/${reading.work_order_id}`}>
                                {shortId('WO', reading.work_order_id)}
                              </Link>
                              )
                            </>
                          )}
                        </>
                      ) : (
                        'Manual'
                      )}
                    </TableCell>
                    <TableCell>{nameOf(reading.created_by)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {readings.data && (
            <TablePagination
              component="div"
              count={readings.data.total}
              page={page}
              rowsPerPage={rowsPerPage}
              rowsPerPageOptions={[rowsPerPage]}
              onPageChange={(_, next) => setPage(next)}
            />
          )}
        </Paper>
      )}
    </Box>
  );
}
