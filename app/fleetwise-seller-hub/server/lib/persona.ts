import { z } from 'zod';

/**
 * Demo personas the switcher may select (rulings R4/R16). `admin` is deliberately absent: the app
 * can never widen a viewer to "sees all rows". `empty` is a hidden test option (Taylor Empty, a
 * seller with no open deals) used by the empty-state smoke test.
 */
export const PersonaKey = z.enum(['seller', 'manager', 'empty']);
export type PersonaKey = z.infer<typeof PersonaKey>;

export const PersonaBody = z.object({ persona: PersonaKey }).strict();

/** user_hierarchy.demo_persona tag and demo_identity_map.persona_role for each switcher option. */
export const PERSONAS: Record<PersonaKey, { demoPersona: string; role: 'seller' | 'manager' }> = {
  seller: { demoPersona: 'seller', role: 'seller' },
  manager: { demoPersona: 'manager', role: 'manager' },
  empty: { demoPersona: 'empty-demo', role: 'seller' },
};

export function personaKeyFor(demoPersona: string | null | undefined): PersonaKey | null {
  const hit = (Object.keys(PERSONAS) as PersonaKey[]).find((k) => PERSONAS[k].demoPersona === demoPersona);
  return hit ?? null;
}

export const Decision = z.enum(['accepted', 'done', 'dismissed']);
export const ActionBody = z.object({ decision: Decision, reason: z.string().trim().max(500).optional() }).strict();
export const NoteBody = z.object({ body: z.string().trim().min(1).max(4000) }).strict();

/** Unity Catalog identifiers come from app.yaml env; refuse anything that is not a plain name. */
export function ucIdent(name: string | undefined, what: string): string {
  if (!name || !/^[A-Za-z0-9_]+$/.test(name)) throw new Error(`invalid ${what}: ${String(name)}`);
  return '`' + name + '`';
}

/** Small TTL cache (persona per caller email, 30 s by default). */
export class TtlCache<V> {
  private readonly entries = new Map<string, { value: V; expires: number }>();
  constructor(private readonly ttlMs: number, private readonly now: () => number = Date.now) {}

  get(key: string): V | undefined {
    const hit = this.entries.get(key);
    if (!hit) return undefined;
    if (hit.expires <= this.now()) {
      this.entries.delete(key);
      return undefined;
    }
    return hit.value;
  }

  set(key: string, value: V): void {
    this.entries.set(key, { value, expires: this.now() + this.ttlMs });
  }

  delete(key: string): void {
    this.entries.delete(key);
  }
}

/** Aggregate per-owner KPI rows (one per visible owner) into the persona's KPI strip. */
export interface KpiRow {
  fiscal_quarter: string;
  quota: number | null;
  closed_won_acv: number | null;
  open_pipeline_acv: number | null;
  commit_acv: number | null;
  best_case_acv: number | null;
  open_opportunities: number | null;
  won_opportunities: number | null;
}

export function aggregateKpis(rows: KpiRow[]) {
  if (rows.length === 0) return null;
  const sum = (k: keyof Omit<KpiRow, 'fiscal_quarter'>) => rows.reduce((a, r) => a + Number(r[k] ?? 0), 0);
  const quota = sum('quota');
  const won = sum('closed_won_acv');
  const open = sum('open_pipeline_acv');
  const remaining = Math.max(quota - won, 0);
  return {
    fiscal_quarter: rows[0].fiscal_quarter,
    reps: rows.length,
    quota,
    closed_won_acv: won,
    attainment_pct: quota > 0 ? won / quota : null,
    open_pipeline_acv: open,
    commit_acv: sum('commit_acv'),
    best_case_acv: sum('best_case_acv'),
    open_opportunities: sum('open_opportunities'),
    won_opportunities: sum('won_opportunities'),
    coverage_ratio: remaining > 0 ? open / remaining : null,
  };
}
