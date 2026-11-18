import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { ActionBody, NoteBody, PERSONAS, PersonaBody, TtlCache, aggregateKpis, personaKeyFor, ucIdent } from './persona';

describe('persona switcher validation (R4/R16)', () => {
  it('accepts only seller | manager | empty', () => {
    for (const p of ['seller', 'manager', 'empty']) expect(PersonaBody.safeParse({ persona: p }).success).toBe(true);
    for (const p of ['admin', 'ADMIN', '', 'empty-demo', null]) expect(PersonaBody.safeParse({ persona: p }).success).toBe(false);
  });
  it('rejects extra fields such as a client-chosen email or user id', () => {
    expect(PersonaBody.safeParse({ persona: 'seller', email: 'x@y' }).success).toBe(false);
    expect(PersonaBody.safeParse({ persona: 'seller', persona_user_id: '005' }).success).toBe(false);
  });
  it('never maps any option to the admin role', () => {
    expect(Object.values(PERSONAS).map((p) => p.role)).not.toContain('admin');
    expect(PERSONAS.empty.demoPersona).toBe('empty-demo');
    expect(personaKeyFor('empty-demo')).toBe('empty');
    expect(personaKeyFor('admin')).toBeNull();
  });
});

describe('request bodies', () => {
  it('validates action decisions', () => {
    expect(ActionBody.safeParse({ decision: 'accepted' }).success).toBe(true);
    expect(ActionBody.safeParse({ decision: 'maybe' }).success).toBe(false);
  });
  it('validates notes', () => {
    expect(NoteBody.safeParse({ body: '  ' }).success).toBe(false);
    expect(NoteBody.safeParse({ body: 'x'.repeat(4001) }).success).toBe(false);
    expect(NoteBody.safeParse({ body: 'call back Tuesday' }).success).toBe(true);
  });
});

describe('ucIdent', () => {
  it('quotes plain names and rejects injection', () => {
    expect(ucIdent('seller_superapp', 's')).toBe('`seller_superapp`');
    expect(() => ucIdent('a`; DROP', 's')).toThrow();
    expect(() => ucIdent(undefined, 's')).toThrow();
  });
});

describe('TtlCache', () => {
  it('expires entries after the ttl', () => {
    let now = 0;
    const c = new TtlCache<number>(30_000, () => now);
    c.set('a', 1);
    now = 29_999;
    expect(c.get('a')).toBe(1);
    now = 30_000;
    expect(c.get('a')).toBeUndefined();
  });
});

describe('aggregateKpis', () => {
  it('returns null for an empty scope and sums a team', () => {
    expect(aggregateKpis([])).toBeNull();
    const row = { fiscal_quarter: 'FY27Q4', quota: 100, closed_won_acv: 40, open_pipeline_acv: 120, commit_acv: 30, best_case_acv: 60, open_opportunities: 5, won_opportunities: 2 };
    const k = aggregateKpis([row, row])!;
    expect(k.reps).toBe(2);
    expect(k.quota).toBe(200);
    expect(k.attainment_pct).toBeCloseTo(0.4);
    expect(k.coverage_ratio).toBeCloseTo(2);
  });
});

describe('app schema DDL', () => {
  it('is a verbatim copy of src/lakebase/app_schema.sql', () => {
    const repo = path.resolve(__dirname, '../../../../src/lakebase/app_schema.sql');
    if (!existsSync(repo)) return; // only checkable inside the repo checkout
    expect(readFileSync(path.resolve(__dirname, '../sql/app_schema.sql'), 'utf8')).toBe(readFileSync(repo, 'utf8'));
  });
});
