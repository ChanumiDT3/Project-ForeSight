import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { UserChoice } from '../api/types';
import WhoAreYouDialog, { NO_USERS_MESSAGE, USER_LIST_UNREACHABLE_MESSAGE, WHO_ARE_YOU_TITLE } from './WhoAreYouDialog';

const listActiveUsers = vi.fn<() => Promise<UserChoice[]>>();
const chooseUser = vi.fn();

vi.mock('../api/endpoints', () => ({ listActiveUsers: () => listActiveUsers() }));
vi.mock('./UserContext', () => ({
  useCurrentUser: () => ({
    user: null, chooserOpen: true, chooserNotice: null, closeChooser: vi.fn(), chooseUser,
  }),
}));

const USERS: UserChoice[] = [
  { id: 'u-ana', name: 'Ana Silva', role: 'Operator' },
  { id: 'u-raj', name: 'Raj Patel', role: 'Engineer' },
];

function renderDialog() {
  return render(<MemoryRouter><WhoAreYouDialog /></MemoryRouter>);
}

describe('WhoAreYouDialog', () => {
  beforeEach(() => {
    listActiveUsers.mockReset();
    chooseUser.mockReset();
  });

  it('shows the new heading and lets the user pick from a dropdown', async () => {
    listActiveUsers.mockResolvedValue(USERS);
    chooseUser.mockResolvedValue({ ...USERS[1], plant_id: 'plant-1' });
    renderDialog();

    expect(screen.getByText(WHO_ARE_YOU_TITLE)).toBeInTheDocument();
    const continueButton = screen.getByRole('button', { name: 'Continue' });
    expect(continueButton).toBeDisabled();

    await userEvent.click(await screen.findByRole('combobox'));
    expect(await screen.findByRole('option', { name: 'Ana Silva (Operator)' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('option', { name: 'Raj Patel (Engineer)' }));

    expect(continueButton).toBeEnabled();
    await userEvent.click(continueButton);
    expect(chooseUser).toHaveBeenCalledWith('u-raj');
  });

  it('explains a missing server instead of "record not found" when the user list returns 404', async () => {
    listActiveUsers.mockRejectedValue(new ApiError(404, 'http_404', 'Not Found'));
    renderDialog();

    expect(await screen.findByText(USER_LIST_UNREACHABLE_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByText('This record was not found.')).not.toBeInTheDocument();
  });

  it('tells the user when no users have been loaded yet', async () => {
    listActiveUsers.mockResolvedValue([]);
    renderDialog();

    expect(await screen.findByText(NO_USERS_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  });
});
