import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError, configureClient } from '../api/client';
import { getMe } from '../api/endpoints';
import type { CurrentUser } from '../api/types';

export const SELECTED_USER_STORAGE_KEY = 'foresight.selectedUserId';
export interface UserContextValue {
  user: CurrentUser | null; status: 'resolving' | 'choosing' | 'ready' | 'error'; error: unknown;
  chooserOpen: boolean; chooserNotice: string | null; openChooser: () => void; closeChooser: () => void;
  chooseUser: (id: string) => Promise<CurrentUser>; retry: () => void;
}
const Context = createContext<UserContextValue | null>(null);
const stored = () => window.localStorage.getItem(SELECTED_USER_STORAGE_KEY);

// PUBLIC_INTERFACE
export function UserProvider({ children }: { children: ReactNode }) {
  /** Persist and server-verify the selected identity for every request. */
  const id = useRef<string | null>(stored());
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<UserContextValue['status']>(id.current ? 'resolving' : 'choosing');
  const [error, setError] = useState<unknown>(null);
  const [chooserOpen, setChooserOpen] = useState(!id.current);
  const [chooserNotice, setChooserNotice] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const forget = useCallback((notice: string | null) => {
    id.current = null; window.localStorage.removeItem(SELECTED_USER_STORAGE_KEY);
    setUser(null); setStatus('choosing'); setChooserNotice(notice); setChooserOpen(true);
  }, []);
  configureClient({ getUserId: () => id.current, onUnknownUser: () => forget('Your saved user is no longer available. Please choose who you are again.') });
  useEffect(() => {
    if (!id.current) return;
    getMe(id.current).then((current) => { setUser(current); setStatus('ready'); })
      .catch((reason) => reason instanceof ApiError && reason.status === 401 ? forget('Your saved user is no longer available. Please choose who you are again.') : (setError(reason), setStatus('error')));
  }, [forget, tick]);
  const chooseUser = useCallback(async (next: string) => {
    const current = await getMe(next); id.current = current.id; window.localStorage.setItem(SELECTED_USER_STORAGE_KEY, current.id);
    setUser(current); setStatus('ready'); setChooserOpen(false); setChooserNotice(null); return current;
  }, []);
  const value = useMemo<UserContextValue>(() => ({
    user, status, error, chooserOpen, chooserNotice, chooseUser,
    openChooser: () => setChooserOpen(true), closeChooser: () => user && setChooserOpen(false),
    retry: () => setTick((current) => current + 1),
  }), [user, status, error, chooserOpen, chooserNotice, chooseUser]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

// PUBLIC_INTERFACE
export function useCurrentUser(): UserContextValue {
  /** Access the selected, backend-resolved current user. */
  const value = useContext(Context);
  if (!value) throw new Error('useCurrentUser must be used inside UserProvider');
  return value;
}
