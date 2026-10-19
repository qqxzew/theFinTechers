import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { getMeta } from './api';
import type { Meta } from './types';

export const ROLES = ['analyst_l1', 'analyst_l2', 'aml_officer', 'mlro'] as const;

/** Fallback staff list for the decider/approver selects when the server sends no `meta.staff`. */
export const STAFF: { name: string; role: string }[] = [
  { name: 'ann', role: 'analyst_l1' },
  { name: 'tom', role: 'analyst_l2' },
  { name: 'eva', role: 'aml_officer' },
  { name: 'rob', role: 'aml_officer' },
  { name: 'zoe', role: 'mlro' },
  { name: 'max', role: 'mlro' },
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
}

const Ctx = createContext<AppCtx | null>(null);

function readIdentity(): Identity {
  try {
    const v = localStorage.getItem('staj.identity');
    if (v) return JSON.parse(v) as Identity;
  } catch {
    /* ignore */
  }
  return { name: 'eva', role: 'aml_officer' };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentityState] = useState<Identity>(readIdentity);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);

  const refreshMeta = useCallback(() => {
    getMeta()
      .then((m) => {
        setMeta(m);
        setMetaError(null);
      })
      .catch((e: Error) => setMetaError(e.message));
  }, []);
  useEffect(refreshMeta, [refreshMeta]);

  const value = useMemo<AppCtx>(
    () => ({
      identity,
      setIdentity: (i) => {
        setIdentityState(i);
        try {
          localStorage.setItem('staj.identity', JSON.stringify(i));
        } catch {
          /* ignore */
        }
      },
      meta,
      metaError,
      refreshMeta,
    }),
    [identity, meta, metaError, refreshMeta],
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
