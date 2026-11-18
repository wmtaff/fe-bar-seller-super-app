/**
 * Lakebase (Postgres) SQL for the Seller Hub. Every read of a seller-owned serving table is scoped
 * by `owner_id = ANY($n)` with the persona's visible owner ids: the synced tables carry no UC row
 * filters (ruling R2), so this scoping IS the row-level security of the app.
 */

/** Self plus everyone whose manager or RVP is the persona (matches fn_can_see_owner in UC). */
export const VISIBLE_OWNERS = `
  SELECT user_id FROM serving.user_hierarchy
  WHERE user_id = $1 OR manager_id = $1 OR rvp_id = $1`;

export const PERSONA_USER = `
  SELECT user_id, name, role, title, demo_persona FROM serving.user_hierarchy WHERE user_id = $1`;

export const PERSONA_BY_TAG = `
  SELECT user_id, name, role, demo_persona FROM serving.user_hierarchy
  WHERE demo_persona = $1 ORDER BY user_id LIMIT 1`;

export const KPIS = `
  SELECT fiscal_quarter,
         quota::float8, closed_won_acv::float8, open_pipeline_acv::float8, commit_acv::float8,
         best_case_acv::float8, open_opportunities::int, won_opportunities::int
  FROM serving.seller_kpis
  WHERE owner_id = ANY($1) AND is_current_quarter`;

export const CURRENT_QUARTER = `
  SELECT fiscal_quarter FROM serving.seller_kpis WHERE is_current_quarter LIMIT 1`;

export const PRIORITY_DEALS = `
  SELECT opportunity_id, opportunity_name, account_name, owner_name, stage, acv::float8,
         close_date::text, fiscal_quarter, p_close_quarter::float8, close_label, next_action,
         competitive_risk::float8, churn_risk::float8, days_since_last_activity, competitor,
         (acv * coalesce(p_close_quarter, 0))::float8 AS expected_acv
  FROM serving.opportunity_pipeline
  WHERE owner_id = ANY($1) AND NOT is_closed
  ORDER BY expected_acv DESC NULLS LAST, opportunity_id
  LIMIT 15`;

/** Open NBAs with no seller decision yet: a decision hides the action instantly. */
export const OPEN_ACTIONS = `
  SELECT n.action_id, n.opportunity_id, n.account_id, n.action_type, n.title, n.why, n.source,
         n.due_date::text, n.priority_score::float8, o.opportunity_name, o.account_name
  FROM serving.next_best_actions n
  LEFT JOIN serving.opportunity_pipeline o ON o.opportunity_id = n.opportunity_id
  WHERE n.owner_id = ANY($1) AND n.status = 'open'
    AND NOT EXISTS (SELECT 1 FROM app.seller_actions s WHERE s.action_id = n.action_id)
  ORDER BY n.priority_score DESC NULLS LAST, n.action_id
  LIMIT 20`;

export const FRESHNESS = `SELECT max(last_modified_date) AS freshness_ts FROM serving.opportunity_pipeline`;

export const DEAL = `
  SELECT * FROM serving.opportunity_pipeline WHERE opportunity_id = $1 AND owner_id = ANY($2)`;

export const ACCOUNT = `SELECT * FROM serving.account_360 WHERE account_id = $1`;

export const INSIGHTS = `
  SELECT meeting_id, started_at, summary, next_steps, open_items, interests, competitors,
         objections, sentiment, stakeholders, extract_error
  FROM serving.call_insights WHERE opportunity_id = $1
  ORDER BY started_at DESC LIMIT 10`;

/** serving.contacts is synced from gold_contacts_masked: email/phone are already masked. */
export const CONTACTS = `
  SELECT contact_id, name, title, buyer_role, email, phone, mailing_state
  FROM serving.contacts WHERE account_id = $1
  ORDER BY buyer_role NULLS LAST, name LIMIT 25`;

export const DEAL_ACTIONS = `
  SELECT n.action_id, n.action_type, n.title, n.why, n.source, n.due_date::text,
         n.priority_score::float8, n.status, d.decision, d.created_at AS decided_at
  FROM serving.next_best_actions n
  LEFT JOIN LATERAL (
    SELECT decision, created_at FROM app.seller_actions s
    WHERE s.action_id = n.action_id ORDER BY created_at DESC, id DESC LIMIT 1) d ON true
  WHERE n.opportunity_id = $1
  ORDER BY n.priority_score DESC NULLS LAST, n.action_id`;

export const NOTES = `
  SELECT id::text, body, persona_user_id, created_at FROM app.notes
  WHERE opportunity_id = $1 ORDER BY created_at DESC, id DESC LIMIT 50`;

export const VISIBLE_ACTION = `
  SELECT action_id, opportunity_id FROM serving.next_best_actions
  WHERE action_id = $1 AND owner_id = ANY($2)`;

export const INSERT_ACTION = `
  INSERT INTO app.seller_actions (action_id, opportunity_id, persona_user_id, decision, reason)
  VALUES ($1, $2, $3, $4, $5)
  RETURNING id::text, action_id, opportunity_id, persona_user_id, decision, reason, created_at`;

export const INSERT_NOTE = `
  INSERT INTO app.notes (opportunity_id, persona_user_id, body) VALUES ($1, $2, $3)
  RETURNING id::text, body, persona_user_id, created_at`;
