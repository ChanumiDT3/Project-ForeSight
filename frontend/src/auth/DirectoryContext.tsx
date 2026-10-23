/**
 * User directory: audit fields store user IDs and screens show names (Q1a).
 * Assignable users are active Engineers only (Q2b).
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { listDirectory } from '../api/endpoints';
import type { DirectoryUser } from '../api/types';
import { useCurrentUser } from './UserContext';

export interface DirectoryContextValue {
  users: DirectoryUser[];
  loaded: boolean;
  /** Display name for a user ID; falls back to the ID itself. */
  nameOf: (id: string | null | undefined) => string;
  /** Active Engineers (the only assignable users). */
  engineers: DirectoryUser[];
  reload: () => void;
}

const DirectoryContext = createContext<DirectoryContextValue | null>(null);

// PUBLIC_INTERFACE
export function DirectoryProvider({ children }: { children: ReactNode }) {
  /** Load the user directory once a verified user is selected. */
  const { user } = useCurrentUser();
  const [users, setUsers] = useState<DirectoryUser[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!user) {
      setUsers([]);
      setLoaded(false);
      return undefined;
    }
    let cancelled = false;
    listDirectory()
      .then((rows) => {
        if (!cancelled) setUsers(rows);
      })
      .catch(() => {
        // Names fall back to IDs if the directory cannot be loaded.
        if (!cancelled) setUsers([]);
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [user, tick]);

  const byId = useMemo(() => new Map(users.map((entry) => [entry.id, entry])), [users]);
  const nameOf = useCallback(
    (id: string | null | undefined) => {
      if (!id) return '—';
      return byId.get(id)?.name ?? id;
    },
    [byId],
  );
  const engineers = useMemo(() => users.filter((entry) => entry.active && entry.role === 'Engineer'), [users]);

  const value = useMemo(
    () => ({ users, loaded, nameOf, engineers, reload: () => setTick((n) => n + 1) }),
    [users, loaded, nameOf, engineers],
  );
  return <DirectoryContext.Provider value={value}>{children}</DirectoryContext.Provider>;
}

// PUBLIC_INTERFACE
export function useDirectory(): DirectoryContextValue {
  /** Access the user directory. */
  const context = useContext(DirectoryContext);
  if (!context) throw new Error('useDirectory must be used inside DirectoryProvider');
  return context;
}
