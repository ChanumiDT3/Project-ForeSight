/**
 * Optional parts checklist (replaced as a whole on save). Quantity must be a
 * whole number of at least 1 (Q2d).
 */
import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { replaceChecklist } from '../../api/endpoints';
import type { Availability, ChecklistItem, WorkOrder } from '../../api/types';
import { errorMessage } from '../../utils/errors';
import { validateQuantity } from '../../utils/validation';

interface Row {
  part_name: string;
  part_number: string;
  quantity: string;
  availability: Availability;
  notes: string;
}

const AVAILABILITY: Availability[] = ['yes', 'no', 'ordered'];

function toRows(items: ChecklistItem[] | null): Row[] {
  return (items ?? []).map((item) => ({
    part_name: item.part_name,
    part_number: item.part_number ?? '',
    quantity: String(item.quantity),
    availability: item.availability,
    notes: item.notes ?? '',
  }));
}

interface ChecklistSectionProps {
  workOrder: WorkOrder;
  editable: boolean;
  onSaved: (workOrder: WorkOrder) => void;
}

// PUBLIC_INTERFACE
export default function ChecklistSection({ workOrder, editable, onSaved }: ChecklistSectionProps) {
  /** Edit or display the parts checklist. */
  const [rows, setRows] = useState<Row[]>(toRows(workOrder.parts_checklist));
  const [errors, setErrors] = useState<Record<number, Partial<Record<keyof Row, string>>>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setRows(toRows(workOrder.parts_checklist));
    setDirty(false);
    setErrors({});
  }, [workOrder.version, workOrder.parts_checklist]);

  const update = (index: number, patch: Partial<Row>) => {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));
    setDirty(true);
  };

  const save = async () => {
    const found: Record<number, Partial<Record<keyof Row, string>>> = {};
    rows.forEach((row, index) => {
      const rowErrors: Partial<Record<keyof Row, string>> = {};
      if (!row.part_name.trim()) rowErrors.part_name = 'Required';
      const quantityError = validateQuantity(row.quantity);
      if (quantityError) rowErrors.quantity = quantityError;
      if (Object.keys(rowErrors).length) found[index] = rowErrors;
    });
    setErrors(found);
    if (Object.keys(found).length) return;

    setSaving(true);
    setError(null);
    try {
      const items: ChecklistItem[] = rows.map((row) => ({
        part_name: row.part_name.trim(),
        part_number: row.part_number.trim() || null,
        quantity: Number(row.quantity),
        availability: row.availability,
        notes: row.notes.trim() || null,
      }));
      onSaved(await replaceChecklist(workOrder.id, items, workOrder.version));
      setDirty(false);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  if (!editable) {
    if (!rows.length) return <Typography variant="body2">No parts planned.</Typography>;
    return (
      <Table size="small" aria-label="Parts checklist">
        <TableHead>
          <TableRow>
            <TableCell>Part</TableCell>
            <TableCell>Part no.</TableCell>
            <TableCell align="right">Qty</TableCell>
            <TableCell>Available</TableCell>
            <TableCell>Notes</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={`${row.part_name}-${index}`}>
              <TableCell>{row.part_name}</TableCell>
              <TableCell>{row.part_number || '—'}</TableCell>
              <TableCell align="right">{row.quantity}</TableCell>
              <TableCell>{row.availability}</TableCell>
              <TableCell>{row.notes || '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  return (
    <Stack spacing={2}>
      {rows.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No parts planned. The checklist is optional.
        </Typography>
      )}
      {rows.map((row, index) => (
        <Stack key={index} direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ md: 'flex-start' }}>
          <TextField
            label="Part name"
            required
            value={row.part_name}
            onChange={(event) => update(index, { part_name: event.target.value })}
            error={Boolean(errors[index]?.part_name)}
            helperText={errors[index]?.part_name ?? ' '}
          />
          <TextField
            label="Part no."
            value={row.part_number}
            onChange={(event) => update(index, { part_number: event.target.value })}
            helperText=" "
          />
          <TextField
            label="Qty"
            required
            value={row.quantity}
            inputProps={{ inputMode: 'numeric' }}
            onChange={(event) => update(index, { quantity: event.target.value })}
            error={Boolean(errors[index]?.quantity)}
            helperText={errors[index]?.quantity ?? ' '}
            sx={{ maxWidth: { md: 110 } }}
          />
          <TextField
            select
            label="Available"
            value={row.availability}
            onChange={(event) => update(index, { availability: event.target.value as Availability })}
            helperText=" "
            sx={{ minWidth: 120 }}
          >
            {AVAILABILITY.map((option) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Notes"
            value={row.notes}
            onChange={(event) => update(index, { notes: event.target.value })}
            helperText=" "
            sx={{ flexGrow: 1 }}
          />
          <IconButton
            aria-label={`Remove part ${index + 1}`}
            onClick={() => {
              setRows((current) => current.filter((_, i) => i !== index));
              setDirty(true);
            }}
          >
            <DeleteOutlineIcon />
          </IconButton>
        </Stack>
      ))}
      {Boolean(error) && <Alert severity="error">{errorMessage(error)} Nothing was saved.</Alert>}
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          onClick={() => {
            setRows((current) => [...current, { part_name: '', part_number: '', quantity: '1', availability: 'yes', notes: '' }]);
            setDirty(true);
          }}
        >
          + Add part
        </Button>
        <Button variant="contained" onClick={save} disabled={!dirty || saving}>
          {saving ? 'Saving…' : 'Save checklist'}
        </Button>
      </Box>
    </Stack>
  );
}
