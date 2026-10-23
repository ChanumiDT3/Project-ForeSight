import { Chip, type ChipProps } from '@mui/material';

type Tone = ChipProps['color'];

const TONES: Record<string, Tone> = {
  Critical: 'error',
  High: 'warning',
  Medium: 'info',
  Open: 'warning',
  'In Progress': 'info',
  Resolved: 'success',
  Dismissed: 'default',
  Closed: 'success',
  Cancelled: 'default',
  Healthy: 'success',
  'At Risk': 'error',
  Monitored: 'primary',
  'Not monitored': 'default',
  'Baseline missing': 'warning',
  'Data error': 'error',
  Ready: 'success',
};

// PUBLIC_INTERFACE
export default function StatusChip({ label, size = 'small' }: { label: string | null | undefined; size?: ChipProps['size'] }) {
  /** Text status badge; colour is an addition, never the only signal. */
  if (!label) return <>—</>;
  const tone = TONES[label] ?? 'default';
  return <Chip label={label} color={tone} size={size} variant={tone === 'default' ? 'outlined' : 'filled'} />;
}
