import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReadingTarget } from '../api/types';
import LogReadingPage, { NO_PARAMETERS_MESSAGE } from './LogReadingPage';

const listReadingTargets = vi.fn<() => Promise<ReadingTarget[]>>();
const logReading = vi.fn();

vi.mock('../api/endpoints', () => ({
  listReadingTargets: () => listReadingTargets(),
  logReading: (...args: unknown[]) => logReading(...args),
}));

const parameter = (id: string, name: string, unit: string) => ({ id, name, unit } as ReadingTarget['parameters'][number]);

// Mirrors backend/seed/equipment.json (UI Wireframes M-100 Press 1).
const TARGETS: ReadingTarget[] = [{
  id: 'm-1', equipment_id: 'M-100', name: 'Press 1', location: 'Line A', baseline: '5000.0',
  parameters: [
    parameter('p-temp', 'Temperature', 'degrees C'),
    parameter('p-vib', 'Vibration', 'mm/s'),
    parameter('p-run', 'Runtime hours', 'hours'),
  ],
}];

describe('LogReadingPage parameter dropdown', () => {
  beforeEach(() => {
    listReadingTargets.mockReset();
    logReading.mockReset();
  });

  it('lists configured parameters and lets the user select one and save', async () => {
    listReadingTargets.mockResolvedValue(TARGETS);
    logReading.mockResolvedValue({ reading: { id: 'r-1' } });
    render(<LogReadingPage />);

    await userEvent.click(await screen.findByRole('combobox'));
    const listbox = await screen.findByRole('listbox');
    expect(within(listbox).getAllByRole('option').map((item) => item.textContent)).toEqual([
      'M-100 Press 1 – Temperature (degrees C)',
      'M-100 Press 1 – Vibration (mm/s)',
      'M-100 Press 1 – Runtime hours (hours)',
    ]);

    await userEvent.click(within(listbox).getByRole('option', { name: /Vibration/ }));
    expect(screen.getByRole('combobox')).toHaveTextContent('M-100 Press 1 – Vibration (mm/s)');

    await userEvent.type(screen.getByLabelText('Value'), '7.5');
    await userEvent.click(screen.getByRole('button', { name: 'Save reading' }));
    expect(logReading).toHaveBeenCalledWith('p-vib', '7.5');
  });

  it('explains an empty configuration instead of showing a blank list', async () => {
    listReadingTargets.mockResolvedValue([]);
    render(<LogReadingPage />);

    // Checked before opening the menu: MUI hides the page behind an open menu.
    expect(await screen.findByRole('button', { name: 'Save reading' })).toBeDisabled();
    await userEvent.click(await screen.findByRole('combobox'));
    const option = await screen.findByRole('option', { name: NO_PARAMETERS_MESSAGE });
    expect(option).toHaveAttribute('aria-disabled', 'true');
  });
});
