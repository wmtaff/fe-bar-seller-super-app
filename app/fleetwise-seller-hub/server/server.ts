import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { Request, Response } from 'express';
import { createApp, analytics, genie, lakebase, server, sql } from '@databricks/appkit';
import {
  ActionBody,
  NoteBody,
  PERSONAS,
  PersonaBody,
  TtlCache,
  aggregateKpis,
  personaKeyFor,
  ucIdent,
  type KpiRow,
  type PersonaKey,
} from './lib/persona';
import * as Q from './lib/queries';

/** demo_identity_map (UC). Names come from app.yaml env, never from the request. */
const UC_PREFIX = `${ucIdent(process.env.UC_CATALOG, 'UC_CATALOG')}.${ucIdent(process.env.UC_SCHEMA, 'UC_SCHEMA')}`;
const IDENTITY_MAP = `${UC_PREFIX}.demo_identity_map`;
const PERSONA_TTL_MS = 30_000;

interface Persona {
  email: string;
  persona_user_id: string;
  persona_name: string;
  role: string;
  persona_key: PersonaKey | null;
  mapped: boolean;
  visible_owner_ids: string[];
}

type Row = Record<string, unknown>;

const text = (v: unknown): string | null =>
  typeof v === 'string' ? v : typeof v === 'number' || typeof v === 'bigint' ? String(v) : null;
const num = (v: unknown): number | null => (v === null || v === undefined ? null : Number(v));
const toKpiRow = (r: Row): KpiRow => ({
  fiscal_quarter: String(r.fiscal_quarter),
  quota: num(r.quota),
  closed_won_acv: num(r.closed_won_acv),
  open_pipeline_acv: num(r.open_pipeline_acv),
  commit_acv: num(r.commit_acv),
  best_case_acv: num(r.best_case_acv),
  open_opportunities: num(r.open_opportunities),
  won_opportunities: num(r.won_opportunities),
});

class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Errors worth one retry: the endpoint scaled to zero or the connection was recycled. */
function isTransientPgError(err: unknown): boolean {
  const e = err as { code?: string; message?: string };
  return (
    ['57P01', '57P03', '08000', '08003', '08006', 'ECONNRESET', 'ECONNREFUSED', 'ETIMEDOUT'].includes(e.code ?? '') ||
    /Connection terminated|connection timeout|server closed the connection/i.test(e.message ?? '')
  );
}

function callerEmail(req: Request): string {
  const email = req.header('x-forwarded-email') ?? req.header('x-forwarded-user');
  if (!email) throw new HttpError(401, 'no signed-in user (x-forwarded-email missing)');
  return email.toLowerCase();
}

await createApp({
  plugins: [
    analytics(),
    // Space id injected from the `genie-space` app resource (src/genie/space_id.txt via bundle var).
    genie({ spaces: { default: process.env.DATABRICKS_GENIE_SPACE_ID ?? '' } }),
    lakebase(),
    server(),
  ],
  async onPluginsReady(appkit) {
    const pg = async (text: string, params?: unknown[]): Promise<Row[]> => {
      try {
        return (await appkit.lakebase.query(text, params)).rows as Row[];
      } catch (err) {
        if (!isTransientPgError(err)) throw err;
        console.warn('[lakebase] transient error, retrying once:', (err as Error).message);
        return (await appkit.lakebase.query(text, params)).rows as Row[];
      }
    };
    const warehouseAsUser = async (req: Request, statement: string, params: Record<string, ReturnType<typeof sql.string>>): Promise<Row[]> => {
      const result = (await appkit.asUser(req).analytics.query(statement, params)) as { data?: Row[] } | undefined;
      return result?.data ?? [];
    };

    // 1. App-owned schema `app` (Task 8 DDL), as the service principal, idempotent on every start.
    const ddl = readFileSync(path.join(process.cwd(), 'server', 'sql', 'app_schema.sql'), 'utf8');
    try {
      await pg(ddl);
      console.log('[lakebase] app schema ready (app.seller_actions, app.notes, app.email_drafts)');
    } catch (err) {
      console.error('[lakebase] app schema setup failed:', (err as Error).message);
    }

    // 2. Persona per request: caller email -> demo_identity_map (OBO, warehouse) -> hierarchy (Lakebase).
    const personaCache = new TtlCache<Persona>(PERSONA_TTL_MS);

    async function defaultPersonaId(): Promise<string> {
      const [row] = await pg(Q.PERSONA_BY_TAG, [PERSONAS.seller.demoPersona]);
      if (!row) throw new HttpError(500, 'no seller demo persona in serving.user_hierarchy');
      return String(row.user_id);
    }

    async function resolvePersona(req: Request): Promise<Persona> {
      const email = callerEmail(req);
      const cached = personaCache.get(email);
      if (cached) return cached;
      const mapRows = await warehouseAsUser(
        req,
        `SELECT persona_user_id, persona_role FROM ${IDENTITY_MAP}
         WHERE lower(workspace_email) = :email ORDER BY updated_at DESC LIMIT 1`,
        { email: sql.string(email) },
      );
      // No row, or an admin row (null persona): the app never widens scope, it falls back to the seller.
      const mappedId = text(mapRows[0]?.persona_user_id) || null;
      const personaId = mappedId ?? (await defaultPersonaId());
      const [user] = await pg(Q.PERSONA_USER, [personaId]);
      if (!user) throw new HttpError(404, `persona ${personaId} not in serving.user_hierarchy`);
      const visible = (await pg(Q.VISIBLE_OWNERS, [personaId])).map((r) => String(r.user_id));
      const persona: Persona = {
        email,
        persona_user_id: personaId,
        persona_name: String(user.name),
        role: text(mapRows[0]?.persona_role) ?? 'seller',
        persona_key: personaKeyFor(user.demo_persona as string | null),
        mapped: mappedId !== null,
        visible_owner_ids: visible,
      };
      personaCache.set(email, persona);
      return persona;
    }

    const openActions = (p: Persona) => pg(Q.OPEN_ACTIONS, [p.visible_owner_ids]);

    const handle =
      (fn: (req: Request, res: Response) => Promise<unknown>) => async (req: Request, res: Response) => {
        try {
          const body = await fn(req, res);
          if (!res.headersSent) res.json(body);
        } catch (err) {
          const status = err instanceof HttpError ? err.status : 500;
          console.error(`[api] ${req.method} ${req.path} failed:`, (err as Error).message);
          if (!res.headersSent) res.status(status).json({ error: (err as Error).message });
        }
      };

    appkit.server.extend((app) => {
      app.get('/api/health/db', handle(async () => {
        const t0 = performance.now();
        await pg('SELECT 1');
        return { ok: true, latency_ms: Math.round((performance.now() - t0) * 10) / 10, at: new Date().toISOString() };
      }));

      // Second-principal governance check (R16): runs as the app SERVICE PRINCIPAL on the warehouse.
      // Expected: the unfiltered base gold table is denied, the row-filtered view is readable.
      app.get('/api/health/governance', handle(async () => {
        const probe = async (table: string) => {
          try {
            const r = (await appkit.analytics.query(`SELECT count(*) AS n FROM ${UC_PREFIX}.${table}`)) as { data?: Row[] } | undefined;
            return { table, ok: true, rows: num(r?.data?.[0]?.n) };
          } catch (err) {
            const m = (err as Error).message;
            return { table, ok: false, error: /PERMISSION_DENIED|INSUFFICIENT_PERMISSIONS|TABLE_OR_VIEW_NOT_FOUND/.exec(m)?.[0] ?? m.slice(0, 200) };
          }
        };
        const base = await probe('gold_opportunity_app');
        const view = await probe('v_opportunity_pipeline');
        return { principal: 'app service principal', base_table: base, view, pass: !base.ok && view.ok };
      }));

      app.get('/api/me', handle(async (req) => {
        const p = await resolvePersona(req);
        return {
          email: p.email,
          persona_user_id: p.persona_user_id,
          persona_name: p.persona_name,
          role: p.role,
          persona_key: p.persona_key,
          mapped: p.mapped,
          visible_owner_count: p.visible_owner_ids.length,
        };
      }));

      app.put('/api/persona', handle(async (req) => {
        const parsed = PersonaBody.safeParse(req.body);
        if (!parsed.success) throw new HttpError(400, 'persona must be one of seller | manager | empty');
        const email = callerEmail(req);
        const target = PERSONAS[parsed.data.persona];
        const [user] = await pg(Q.PERSONA_BY_TAG, [target.demoPersona]);
        if (!user) throw new HttpError(500, `no ${target.demoPersona} persona in serving.user_hierarchy`);
        // OBO: the signed-in user's own row, through the warehouse. The SP holds no MODIFY on the map.
        await warehouseAsUser(
          req,
          `MERGE INTO ${IDENTITY_MAP} AS t
           USING (SELECT :email AS workspace_email, :pid AS persona_user_id, :role AS persona_role) AS s
           ON lower(t.workspace_email) = s.workspace_email
           WHEN MATCHED THEN UPDATE SET persona_user_id = s.persona_user_id,
                                        persona_role = s.persona_role, updated_at = current_timestamp()
           WHEN NOT MATCHED THEN INSERT (workspace_email, persona_user_id, persona_role, updated_at)
                                 VALUES (s.workspace_email, s.persona_user_id, s.persona_role, current_timestamp())`,
          { email: sql.string(email), pid: sql.string(String(user.user_id)), role: sql.string(target.role) },
        );
        personaCache.delete(email);
        const p = await resolvePersona(req);
        return { email: p.email, persona_user_id: p.persona_user_id, persona_name: p.persona_name, role: p.role, persona_key: p.persona_key };
      }));

      app.get('/api/home', handle(async (req) => {
        const p = await resolvePersona(req);
        const [kpiRows, deals, actions, fresh, quarter] = await Promise.all([
          pg(Q.KPIS, [p.visible_owner_ids]),
          pg(Q.PRIORITY_DEALS, [p.visible_owner_ids]),
          openActions(p),
          pg(Q.FRESHNESS),
          pg(Q.CURRENT_QUARTER),
        ]);
        return {
          persona: { persona_user_id: p.persona_user_id, persona_name: p.persona_name, role: p.role },
          fiscal_quarter: quarter[0]?.fiscal_quarter ?? null,
          kpis: aggregateKpis(kpiRows.map(toKpiRow)),
          priority_deals: deals,
          actions,
          freshness_ts: fresh[0]?.freshness_ts ?? null,
        };
      }));

      app.get('/api/deals/:id', handle(async (req) => {
        const p = await resolvePersona(req);
        const id = String(req.params.id);
        const [opp] = await pg(Q.DEAL, [id, p.visible_owner_ids]);
        if (!opp) throw new HttpError(404, 'deal not found for this persona');
        const [account, insights, contacts, actions, notes] = await Promise.all([
          pg(Q.ACCOUNT, [opp.account_id]),
          pg(Q.INSIGHTS, [id]),
          pg(Q.CONTACTS, [opp.account_id]),
          pg(Q.DEAL_ACTIONS, [id]),
          pg(Q.NOTES, [id]),
        ]);
        return {
          opportunity: opp,
          scores: {
            p_close_quarter: opp.p_close_quarter,
            close_label: opp.close_label,
            close_confidence: opp.close_confidence,
            competitive_risk: opp.competitive_risk,
            churn_risk: opp.churn_risk,
            next_action: opp.next_action,
            next_action_conf: opp.next_action_conf,
            scored_at: opp.scored_at,
          },
          account: account[0] ?? null,
          insights,
          contacts,
          actions,
          notes,
        };
      }));

      app.post('/api/actions/:action_id', handle(async (req, res) => {
        const parsed = ActionBody.safeParse(req.body);
        if (!parsed.success) throw new HttpError(400, 'decision must be one of accepted | done | dismissed');
        const p = await resolvePersona(req);
        const [action] = await pg(Q.VISIBLE_ACTION, [String(req.params.action_id), p.visible_owner_ids]);
        if (!action) throw new HttpError(404, 'action not found for this persona');
        const [decision] = await pg(Q.INSERT_ACTION, [
          action.action_id, action.opportunity_id, p.persona_user_id, parsed.data.decision, parsed.data.reason ?? null,
        ]);
        res.status(201);
        return { decision, actions: await openActions(p) };
      }));

      app.post('/api/deals/:id/notes', handle(async (req, res) => {
        const parsed = NoteBody.safeParse(req.body);
        if (!parsed.success) throw new HttpError(400, 'body must be 1-4000 characters');
        const p = await resolvePersona(req);
        const id = String(req.params.id);
        const [opp] = await pg(Q.DEAL, [id, p.visible_owner_ids]);
        if (!opp) throw new HttpError(404, 'deal not found for this persona');
        const [note] = await pg(Q.INSERT_NOTE, [id, p.persona_user_id, parsed.data.body]);
        res.status(201);
        return { note, notes: await pg(Q.NOTES, [id]) };
      }));
    });
  },
});
