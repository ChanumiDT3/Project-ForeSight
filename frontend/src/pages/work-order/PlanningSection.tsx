import { useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Checkbox, FormControlLabel, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { editWorkOrder } from '../../api/endpoints';
import type { WorkOrder, WorkOrderEditPayload } from '../../api/types';
import { useDirectory } from '../../auth/DirectoryContext';
import { errorMessage } from '../../utils/errors';
import { fromLocalInputValue, toLocalInputValue } from '../../utils/format';

interface PlanningSectionProps {
  workOrder: WorkOrder;
  editable: boolean;
  onSaved: (workOrder: WorkOrder) => void;
  onDirtyChange: (dirty: boolean) => void;
}

// PUBLIC_INTERFACE
export default function PlanningSection({ workOrder, editable, onSaved, onDirtyChange }: PlanningSectionProps) {
  /** Edit the backend-supported assignment, due-date, and runtime-service fields. */
  const { engineers } = useDirectory();
  const [assignee, setAssignee] = useState(workOrder.assignee ?? '');
  const [dueAt, setDueAt] = useState(toLocalInputValue(workOrder.due_at));
  const [scheduledService, setScheduledService] = useState(workOrder.scheduled_service);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setAssignee(workOrder.assignee ?? '');
    setDueAt(toLocalInputValue(workOrder.due_at));
    setScheduledService(workOrder.scheduled_service);
    setError(null);
  }, [workOrder.assignee, workOrder.due_at, workOrder.scheduled_service, workOrder.version]);

  const changes = useMemo<WorkOrderEditPayload>(() => {
    const next: WorkOrderEditPayload = {};
    if (assignee !== (workOrder.assignee ?? '')) next.assignee = assignee || null;

    const initialDueAt = toLocalInputValue(workOrder.due_at);
    if (dueAt !== initialDueAt) {
      const converted = fromLocalInputValue(dueAt);
      if (converted) next.due_at = converted;
    }

    if (workOrder.runtime_applicable && scheduledService !== workOrder.scheduled_service) {
      next.scheduled_service = scheduledService;
    }
    return next;
  }, [assignee, dueAt, scheduledService, workOrder]);

  const invalidDueDate = dueAt !== toLocalInputValue(workOrder.due_at) && !fromLocalInputValue(dueAt);
  const dirty = Object.keys(changes).length > 0 || invalidDueDate;

  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);

  if (!editable) {
    return (
      <Stack spacing={0.5}>
        <Typography>Assignee: {workOrder.assignee ?? 'Unassigned'}</Typography>
        <Typography>Due: {workOrder.due_at ?? 'No due date'}</Typography>
        {workOrder.runtime_applicable && (
          <Typography>Scheduled service performed: {workOrder.scheduled_service ? 'Yes' : 'No'}</Typography>
        )}
      </Stack>
    );
  }

  const save = async () => {
    if (!Object.keys(changes).length || invalidDueDate) return;
    setSaving(true);
    setError(null);
    try {
      onSaved(await editWorkOrder(workOrder.id, changes, workOrder.version));
    } catch (reason) {
      setError(reason);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack spacing={2} sx={{ maxWidth: 560 }}>
      <TextField select label="Assignee" value={assignee} onChange={(event) => setAssignee(event.target.value)}>
        <MenuItem value="">Unassigned</MenuItem>
        {engineers.map((engineer) => (
          <MenuItem key={engineer.id} value={engineer.id}>
            {engineer.name}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        type="datetime-local"
        label="Due date"
        value={dueAt}
        onChange={(event) => setDueAt(event.target.value)}
        InputLabelProps={{ shrink: true }}
        error={invalidDueDate}
        helperText={invalidDueDate ? 'Enter a valid due date.' : 'The server rejects past due dates.'}
      />
      {workOrder.runtime_applicable && (
        <FormControlLabel
          control={
            <Checkbox
              checked={scheduledService}
              disabled={workOrder.raised_from_runtime_alert}
              onChange={(event) => setScheduledService(event.target.checked)}
            />
          }
          label={
            workOrder.raised_from_runtime_alert
              ? 'Scheduled service performed (required for runtime-alert work)'
              : 'Scheduled service performed'
          }
        />
      )}
      {Boolean(error) && <Alert severity="error">{errorMessage(error)} Nothing was saved.</Alert>}
      <Box>
        <Button variant="contained" onClick={save} disabled={!dirty || invalidDueDate || saving}>
          {saving ? 'Saving…' : 'Save planning'}
        </Button>
      </Box>
    </Stack>
  );
}
