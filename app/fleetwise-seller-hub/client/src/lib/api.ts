import { useCallback, useEffect, useState } from 'react';

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const res = await fetch(path, {
    method: init?.method ?? 'GET',
    headers: init?.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
  const text = await res.text();
  const json: unknown = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const msg = json && typeof json === 'object' && 'error' in json ? String((json as { error: unknown }).error) : res.statusText;
    throw new ApiError(res.status, msg);
  }
  return json as T;
}

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  setData: (d: T) => void;
}

/** GET a JSON route; re-fetches when `deps` change (e.g. after a persona switch). */
export function useApi<T>(path: string | null, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api<T>(path)
      .then((d) => !cancelled && setData(d))
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);

  return { data, error, loading, reload, setData };
}

export const usd = (v: unknown) =>
  v === null || v === undefined
    ? '–'
    : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(Number(v));

export const pct = (v: unknown, digits = 0) =>
  v === null || v === undefined ? '–' : `${(Number(v) * 100).toFixed(digits)}%`;

/** Render a scalar from a JSON row; objects are JSON-encoded instead of '[object Object]'. */
export const str = (v: unknown): string =>
  typeof v === 'string' ? v : typeof v === 'number' || typeof v === 'boolean' || typeof v === 'bigint' ? String(v) : v === null || v === undefined ? '' : JSON.stringify(v);

export const dateTime = (v: unknown) => (v ? new Date(str(v)).toLocaleString() : '–');

/** Insight fields are JSON arrays serialized as strings; fall back to plain text. */
export function asList(v: unknown): string[] {
  if (v === null || v === undefined || v === '') return [];
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'string' ? x : JSON.stringify(x)));
  if (typeof v === 'string') {
    try {
      const parsed: unknown = JSON.parse(v);
      if (Array.isArray(parsed)) return asList(parsed);
    } catch {
      /* plain text */
    }
    return [v];
  }
  return [JSON.stringify(v)];
}
