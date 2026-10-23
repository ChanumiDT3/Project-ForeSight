import { useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Checkbox, Divider, FormControlLabel, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { useParams } from 'react-router-dom';
import {
  addParameter,
  editCriticality,
  editCumulative,
  editMachineDetails,
  editSuggestedAction,
  editThreshold,
  getMachine,
} from '../../api/endpoints';
import type { Parameter } from '../../api/types';
import ParameterFields, {
  newParameterDraft,
  toParameterPayload,
  validateParameterDraft,
  type ParameterDraft,
  type ParameterErrors,
} from '../../components/ParameterFields';
import { CRITICALITY_OPTIONS, RUNTIME_RULE } from '../../config/parameterRules';
import { ErrorAlert, Loading } from '../../components/LoadState';
import PageHeader from '../../components/PageHeader';
import { useApi } from '../../hooks/useApi';
import { errorMessage } from '../../utils/errors';
import { validateDecimal } from '../../utils/validation';

interface DetailsForm {
  name: string;
  location: string;
  equipmentType: string;
  criticality: string;
}

interface ParameterEdit {
  threshold: string;
  suggestedAction: string;
  cumulative: boolean;
}

const parameterEdit = (parameter: Parameter): ParameterEdit => ({
  threshold: parameter.threshold,
  suggestedAction: parameter.suggested_action,
  cumulative: Boolean(parameter.cumulative),
});

// PUBLIC_INTERFACE
export default function MachineEditPage() {
  /** Edit machine metadata and the parameter fields supported by the equipment API. */
  const { machineId = '' } = useParams();
  const machine = useApi((signal) => getMachine(machineId, signal), [machineId]);
  const [details, setDetails] = useState<DetailsForm>({ name: '', location: '', equipmentType: '', criticality: '1' });
  const [edits, setEdits] = useState<Record<string, ParameterEdit>>({});
  const [draft, setDraft] = useState<ParameterDraft>(newParameterDraft());
  const [draftErrors, setDraftErrors] = useState<ParameterErrors>({});
  const [baseline, setBaseline] = useState('');
  const [currentMeter, setCurrentMeter] = useState('');
  const [runtimeError, setRuntimeError] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!machine.data) return;
    setDetails({
      name: machine.data.name,
      location: machine.data.location,
      equipmentType: machine.data.equipment_type,
      criticality: String(machine.data.criticality),
    });
    setEdits(Object.fromEntries(machine.data.parameters.map((parameter) => [parameter.id, parameterEdit(parameter)])));
    setBaseline(machine.data.baseline ?? '');
    setCurrentMeter(machine.data.registration_meter ?? '');
  }, [machine.data]);

  const data = machine.data;
  const hasRuntime = Boolean(data?.parameters.some((parameter) => parameter.kind === 'runtime_hours'));
  const changed = useMemo(() => {
    if (!data) return false;
    return (
      details.name !== data.name ||
      details.location !== data.location ||
      details.equipmentType !== data.equipment_type ||
      Number(details.criticality) !== data.criticality ||
      data.parameters.some((parameter) => {
        const edit = edits[parameter.id];
        return Boolean(edit && (
          edit.threshold !== parameter.threshold ||
          edit.suggestedAction !== parameter.suggested_action ||
          (parameter.kind === 'custom' && parameter.latest_value == null && edit.cumulative !== Boolean(parameter.cumulative))
        ));
      })
    );
  }, [data, details, edits]);

  if (machine.loading && !data) return <Loading />;
  if (!data) return <ErrorAlert error={machine.error} onRetry={machine.reload} />;

  const setDetail = (field: keyof DetailsForm, value: string) => setDetails((current) => ({ ...current, [field]: value }));
  const setParameterEdit = (parameter: Parameter, patch: Partial<ParameterEdit>) => {
    setEdits((current) => ({ ...current, [parameter.id]: { ...(current[parameter.id] ?? parameterEdit(parameter)), ...patch } }));
  };

  const save = async () => {
    const commands: Array<Promise<unknown>> = [];
    if (details.name !== data.name || details.location !== data.location || details.equipmentType !== data.equipment_type) {
      commands.push(editMachineDetails(data.id, {
        name: details.name.trim(),
        location: details.location.trim(),
        equipment_type: details.equipmentType.trim(),
      }));
    }
    if (Number(details.criticality) !== data.criticality) commands.push(editCriticality(data.id, Number(details.criticality)));
    data.parameters.forEach((parameter) => {
      const edit = edits[parameter.id];
      if (!edit) return;
      if (edit.threshold !== parameter.threshold) commands.push(editThreshold(parameter.id, edit.threshold));
      if (edit.suggestedAction !== parameter.suggested_action) commands.push(editSuggestedAction(parameter.id, edit.suggestedAction));
      if (parameter.kind === 'custom' && parameter.latest_value == null && edit.cumulative !== Boolean(parameter.cumulative)) {
        commands.push(editCumulative(parameter.id, edit.cumulative));
      }
    });
    if (!commands.length) return;
    setSaving(true);
    setError(null);
    try {
      await Promise.all(commands);
      machine.setData(await getMachine(data.id));
    } catch (reason) {
      setError(reason);
    } finally {
      setSaving(false);
    }
  };

  const add = async () => {
    const errors = validateParameterDraft(draft);
    const addingRuntime = draft.kind === 'runtime_hours';
    const baselineError = addingRuntime ? validateDecimal(baseline, RUNTIME_RULE) : null;
    const meterError = addingRuntime ? validateDecimal(currentMeter, RUNTIME_RULE) : null;
    const baselineExceedsMeter = addingRuntime && Number(baseline) > Number(currentMeter);
    setDraftErrors(errors);
    setRuntimeError(baselineExceedsMeter ? 'Baseline cannot exceed the current meter.' : baselineError ?? meterError ?? '');
    if (Object.keys(errors).length || baselineError || meterError || baselineExceedsMeter) return;

    setAdding(true);
    setError(null);
    try {
      await addParameter(data.id, {
        ...toParameterPayload(draft),
        ...(addingRuntime ? { baseline: baseline.trim(), current_meter: currentMeter.trim() } : {}),
      });
      setDraft(newParameterDraft());
      machine.setData(await getMachine(data.id));
    } catch (reason) {
      setError(reason);
    } finally {
      setAdding(false);
    }
  };

  return (
    <Box>
      <PageHeader title={`Edit ${data.equipment_id}`} />
      <Paper sx={{ p: 2.5 }}>
        <Stack spacing={2}>
          <Typography variant="h2">Machine details</Typography>
          <TextField required label="Name" value={details.name} onChange={(event) => setDetail('name', event.target.value)} />
          <TextField required label="Location" value={details.location} onChange={(event) => setDetail('location', event.target.value)} />
          <TextField required label="Equipment type" value={details.equipmentType} onChange={(event) => setDetail('equipmentType', event.target.value)} />
          <TextField select required label="Criticality" value={details.criticality} onChange={(event) => setDetail('criticality', event.target.value)}>
            {CRITICALITY_OPTIONS.map((option) => <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>)}
          </TextField>
          <Box><Button variant="contained" onClick={save} disabled={!changed || saving}>{saving ? 'Saving…' : 'Save changes'}</Button></Box>
        </Stack>

        <Divider sx={{ my: 3 }} />
        <Typography variant="h2" sx={{ mb: 2 }}>Configured parameters</Typography>
        <Stack spacing={2}>
          {data.parameters.length === 0 && <Typography color="text.secondary">No parameters configured. Add one below to begin monitoring.</Typography>}
          {data.parameters.map((parameter) => {
            const edit = edits[parameter.id] ?? parameterEdit(parameter);
            const cumulativeEditable = parameter.kind === 'custom' && parameter.latest_value == null;
            return (
              <Paper key={parameter.id} variant="outlined" sx={{ p: 2 }}>
                <Stack spacing={1.5}>
                  <Typography variant="subtitle1">{parameter.name} ({parameter.kind.replace('_', ' ')})</Typography>
                  <TextField label="Maximum limit" value={edit.threshold} onChange={(event) => setParameterEdit(parameter, { threshold: event.target.value })} />
                  <TextField label="Suggested action" value={edit.suggestedAction} onChange={(event) => setParameterEdit(parameter, { suggestedAction: event.target.value })} />
                  {parameter.kind === 'custom' && (
                    <FormControlLabel
                      control={<Checkbox checked={edit.cumulative} disabled={!cumulativeEditable} onChange={(event) => setParameterEdit(parameter, { cumulative: event.target.checked })} />}
                      label={cumulativeEditable ? 'Cumulative (reading can never decrease)' : 'Cumulative (locked after the first reading)'}
                    />
                  )}
                </Stack>
              </Paper>
            );
          })}
        </Stack>

        <Divider sx={{ my: 3 }} />
        <Typography variant="h2" sx={{ mb: 2 }}>Add parameter</Typography>
        <Stack spacing={2}>
          <ParameterFields draft={draft} errors={draftErrors} onChange={setDraft} disabledKinds={hasRuntime ? ['runtime_hours'] : []} />
          {draft.kind === 'runtime_hours' && (
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              <TextField required label="Runtime baseline" value={baseline} onChange={(event) => setBaseline(event.target.value)} helperText={runtimeError || 'Hours at the last completed service.'} error={Boolean(runtimeError)} />
              <TextField required label="Current hour meter" value={currentMeter} onChange={(event) => setCurrentMeter(event.target.value)} helperText={runtimeError || 'Must be at least the baseline.'} error={Boolean(runtimeError)} />
            </Stack>
          )}
          <Box><Button variant="outlined" onClick={add} disabled={adding}>{adding ? 'Adding…' : 'Add parameter'}</Button></Box>
        </Stack>
        {Boolean(error) && <Alert severity="error" sx={{ mt: 2 }}>{errorMessage(error)} Nothing was saved.</Alert>}
      </Paper>
    </Box>
  );
}
