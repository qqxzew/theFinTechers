import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { getMeta } from './api';
import type { Meta } from './types';

export const ROLES = ['analyst_l1', 'analyst_l2', 'aml_officer', 'mlro'] as const;

/** Demo staff directory for the approver select (local only; the server validates). */
export const STAFF: { name: string; role: string }[] = [
  { name: 'Tomáš Svoboda', role: 'analyst_l1' },
  { name: 'Lucie Černá', role: 'analyst_l2' },
  { name: 'Eva Horáková', role: 'aml_officer' },
  { name: 'Karel Beneš', role: 'aml_officer' },
  { name: 'Petr Dvořák', role: 'mlro' },
  { name: 'Jana Nováková', role: 'mlro' },
];

interface Identity {
  name: string;
  role: string;
}

interface AppCtx {
  identity: Identity;
  setIdentity: (i: Identity) => void;
  meta: Meta | null;
  metaError: string | null;
  refreshMeta: () => void;
  dark: boolean;
  setDark: (d: boolean) => void;
}

const Ctx = createContext<AppCtx | null>(null);

function read<T>(k: string, d: T): T {
  try {
    const v = localStorage.getItem(k);
    return v ? (JSON.parse(v) as T) : d;
  } catch {
    return d;
  }
}
function save(k: string, v: unknown) {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch {
    /* ignore */
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentityState] = useState<Identity>(() => read('staj.identity', { name: 'Eva Horáková', role: 'aml_officer' }));
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [dark, setDarkState] = useState<boolean>(() => read('staj.dark', false));

  const refreshMeta = useCallback(() => {
    getMeta()
      .then((m) => {
        setMeta(m);
        setMetaError(null);
      })
      .catch((e: Error) => setMetaError(e.message));
  }, []);

  useEffect(refreshMeta, [refreshMeta]);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  const value = useMemo<AppCtx>(
    () => ({
      identity,
      setIdentity: (i) => {
        setIdentityState(i);
        save('staj.identity', i);
      },
      meta,
      metaError,
      refreshMeta,
      dark,
      setDark: (d) => {
        setDarkState(d);
        save('staj.dark', d);
      },
    }),
    [identity, meta, metaError, refreshMeta, dark],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useApp outside provider');
  return c;
}

/** Small async hook: re-runs when deps change, exposes reload. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((e: Error) => alive && setState({ data: null, error: e.message, loading: false }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1), setData: (d: T) => setState({ data: d, error: null, loading: false }) };
}
