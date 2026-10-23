import { useState } from 'react';
import { Box, Button, Divider, Paper, Stack, Typography } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { getWorkOrder, startWorkOrder } from '../../api/endpoints';
import { useCurrentUser } from '../../auth/UserContext';
import { ErrorAlert, Loading } from '../../components/LoadState';
import PageHeader from '../../components/PageHeader';
import { useApi } from '../../hooks/useApi';
import { canManage } from '../../navigation/roles';
import type { ClosureResult, WorkOrder } from '../../api/types';
import AddendaSection from './AddendaSection';
import ChecklistSection from './ChecklistSection';
import ClosureSection from './ClosureSection';
import PlanningSection from './PlanningSection';

export interface ClosureOutcome {
  workOrderId: string;
  alertId: string;
  machineStatus: string;
  newBaseline: string | null;
  lastServiceAt: string;
}

// PUBLIC_INTERFACE
export default function WorkOrderDetailPage() {
  /** Display a work order and its role-gated planning, execution, closure, and addenda workflows. */
  const { workOrderId = '' } = useParams();
  const navigate = useNavigate();
  const { user } = useCurrentUser();
  const [planningDirty, setPlanningDirty] = useState(false);
  const order = useApi((signal) => getWorkOrder(workOrderId, signal), [workOrderId]);

  if (order.loading) return <Loading />;
  if (!order.data) return <ErrorAlert error={order.error} onRetry={order.reload} />;

  const workOrder = order.data;
  const editable = canManage(user?.role) && !['Closed', 'Cancelled'].includes(workOrder.status);
  const canClose = canManage(user?.role) && workOrder.status === 'In Progress';
  const canAddAddendum = canManage(user?.role) && workOrder.status === 'Closed';

  const start = async () => {
    order.setData(await startWorkOrder(workOrder.id, workOrder.version));
  };

  const closed = (result: ClosureResult) => {
    const closure: ClosureOutcome = {
      workOrderId: result.id,
      alertId: result.alert_id,
      machineStatus: result.machine_status,
      newBaseline: result.new_baseline,
      lastServiceAt: result.last_service_at,
    };
    navigate(`/machines/${result.machine_id}`, { state: { closure } });
  };

  return (
    <Box>
      <PageHeader
        back={{ to: '/work-orders', label: 'Work orders' }}
        title={`Work order ${workOrder.id}`}
        subtitle={workOrder.status}
        actions={
          canManage(user?.role) && workOrder.status === 'Open' ? (
            <Button variant="contained" onClick={start}>
              Start work
            </Button>
          ) : undefined
        }
      />
      <Paper sx={{ p: 2.5, mb: 2 }}>
        <Typography>Machine: {workOrder.snapshot.equipment_id} {workOrder.snapshot.machine_name}</Typography>
        <Typography>Priority: {workOrder.priority ?? '—'}</Typography>
        <Typography>Fault: {workOrder.snapshot.fault_description}</Typography>
        <Typography>Suggested action: {workOrder.snapshot.suggested_action || '—'}</Typography>
      </Paper>
      <Stack spacing={2}>
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="h2" sx={{ mb: 2 }}>Planning</Typography>
          <PlanningSection
            workOrder={workOrder}
            editable={editable}
            onSaved={(saved: WorkOrder) => order.setData(saved)}
            onDirtyChange={setPlanningDirty}
          />
        </Paper>
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="h2" sx={{ mb: 2 }}>Parts checklist</Typography>
          <ChecklistSection workOrder={workOrder} editable={editable} onSaved={order.setData} />
        </Paper>
        {canClose && (
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h2" sx={{ mb: 2 }}>Close work order</Typography>
            <ClosureSection
              workOrder={workOrder}
              planningDirty={planningDirty}
              onCancel={() => navigate('/work-orders')}
              onClosed={closed}
            />
          </Paper>
        )}
        {workOrder.status === 'Closed' && (
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h2" sx={{ mb: 2 }}>Addenda</Typography>
            <AddendaSection
              workOrderId={workOrder.id}
              addenda={workOrder.addenda}
              canAdd={canAddAddendum}
              onAdded={order.reload}
            />
          </Paper>
        )}
      </Stack>
      <Divider sx={{ mt: 2 }} />
    </Box>
  );
}
