import { useState } from 'react';
import { Link } from 'react-router';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@databricks/appkit-ui/react';
import { api, dateTime, pct, usd, useApi } from '../lib/api';
import { usePersona } from '../lib/persona';
import { EmptyState, ErrorState, LoadingRows, ProbBar } from '../components/States';

interface Kpis {
  fiscal_quarter: string;
  reps: number;
  quota: number;
  closed_won_acv: number;
  attainment_pct: number | null;
  open_pipeline_acv: number;
  commit_acv: number;
  best_case_acv: number;
  open_opportunities: number;
  coverage_ratio: number | null;
}

export interface Deal {
  opportunity_id: string;
  opportunity_name: string;
  account_name: string;
  owner_name: string;
  stage: string;
  acv: number;
  close_date: string;
  p_close_quarter: number | null;
  close_label: string | null;
  competitive_risk: number | null;
  churn_risk: number | null;
  days_since_last_activity: number | null;
  competitor: string | null;
  expected_acv: number;
}

export interface Action {
  action_id: string;
  opportunity_id: string;
  action_type: string;
  title: string;
  why: string | null;
  source: string | null;
  due_date: string | null;
  priority_score: number | null;
  opportunity_name?: string | null;
  account_name?: string | null;
}

interface Home {
  persona: { persona_name: string; role: string };
  fiscal_quarter: string | null;
  kpis: Kpis | null;
  priority_deals: Deal[];
  actions: Action[];
  freshness_ts: string | null;
}

function reasonChips(d: Deal): string[] {
  const chips: string[] = [];
  if ((d.competitive_risk ?? 0) >= 0.5) chips.push(d.competitor ? `vs ${d.competitor}` : 'Competitive');
  if ((d.churn_risk ?? 0) >= 0.5) chips.push('Churn risk');
  if ((d.days_since_last_activity ?? 0) > 14) chips.push(`Quiet ${d.days_since_last_activity}d`);
  if (d.close_label) chips.push(d.close_label);
  return chips.slice(0, 3);
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="py-3">
      <CardContent className="px-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
        {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  );
}

export function MyWeekPage() {
  const { version } = usePersona();
  const home = useApi<Home>('/api/home', [version]);
  const [pending, setPending] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const decide = async (a: Action, decision: 'accepted' | 'done' | 'dismissed') => {
    if (!home.data) return;
    setPending(a.action_id);
    setActionError(null);
    try {
      const res = await api<{ actions: Action[] }>(`/api/actions/${encodeURIComponent(a.action_id)}`, {
        method: 'POST',
        body: { decision },
      });
      home.setData({ ...home.data, actions: res.actions });
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setPending(null);
    }
  };

  const d = home.data;
  const k = d?.kpis;
  const quarter = d?.fiscal_quarter ?? k?.fiscal_quarter ?? 'current quarter';

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h2 className="text-2xl font-bold">My Week</h2>
          <p className="text-sm text-muted-foreground">
            {d ? `${d.persona.persona_name} · ${d.persona.role} · ${quarter}` : 'Loading your book…'}
          </p>
        </div>
        {d && (
          <Badge variant="outline" className="ml-auto" title="Latest LastModifiedDate in the served opportunity data">
            Data as of {dateTime(d.freshness_ts)}
          </Badge>
        )}
      </div>

      {home.error && <ErrorState message={home.error} onRetry={home.reload} />}

      <section aria-label="KPIs">
        {home.loading && !d ? (
          <LoadingRows rows={2} />
        ) : k ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Kpi label={`Attainment (${k.fiscal_quarter})`} value={pct(k.attainment_pct)} sub={`${usd(k.closed_won_acv)} of ${usd(k.quota)} quota`} />
            <Kpi label="Open pipeline" value={usd(k.open_pipeline_acv)} sub={`${k.open_opportunities} open opps`} />
            <Kpi label="Commit" value={usd(k.commit_acv)} sub={`Best case ${usd(k.best_case_acv)}`} />
            <Kpi label="Coverage" value={k.coverage_ratio === null ? '–' : `${k.coverage_ratio.toFixed(1)}x`} sub="Open pipeline / remaining quota" />
            <Kpi label="Reps in scope" value={String(k.reps)} sub="Self plus reports" />
          </div>
        ) : (
          d && <EmptyState title="No KPIs this quarter" description={`No seller_kpis rows for ${quarter} in your scope.`} />
        )}
      </section>

      <div className="grid lg:grid-cols-5 gap-6">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle><h3>Priority deals</h3></CardTitle>
            <CardDescription>Top 15 open deals by ACV × probability of closing this quarter</CardDescription>
          </CardHeader>
          <CardContent>
            {home.loading && !d ? (
              <LoadingRows rows={6} />
            ) : d && d.priority_deals.length === 0 ? (
              <EmptyState title="No open deals" description="Nothing open in your book right now." />
            ) : d ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Deal</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead className="text-right">ACV</TableHead>
                    <TableHead>P(close this qtr)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {d.priority_deals.map((deal) => (
                    <TableRow key={deal.opportunity_id} data-testid="deal-row">
                      <TableCell>
                        <Link to={`/deals/${deal.opportunity_id}`} className="font-medium hover:underline">
                          {deal.account_name}
                        </Link>
                        <div className="text-xs text-muted-foreground">
                          {deal.opportunity_name} · {deal.owner_name} · closes {deal.close_date}
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {reasonChips(deal).map((c) => (
                            <Badge key={c} variant="secondary" className="text-[10px]">{c}</Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">{deal.stage}</TableCell>
                      <TableCell className="text-right tabular-nums">{usd(deal.acv)}</TableCell>
                      <TableCell><ProbBar value={deal.p_close_quarter} label="Probability of closing this quarter" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : null}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle><h3>Next best actions</h3></CardTitle>
            <CardDescription>Your decision is saved to Lakebase and syncs back to the lakehouse</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {actionError && <ErrorState message={actionError} />}
            {home.loading && !d ? (
              <LoadingRows rows={5} />
            ) : d && d.actions.length === 0 ? (
              <EmptyState title="No open actions" description="You are all caught up." />
            ) : (
              d?.actions.map((a) => (
                <div key={a.action_id} className="border rounded-md p-3 space-y-2" data-testid="action-item" data-action-id={a.action_id}>
                  <div className="flex items-start gap-2">
                    <div className="flex-1">
                      <div className="text-sm font-medium">{a.title}</div>
                      <div className="text-xs text-muted-foreground">
                        <Link to={`/deals/${a.opportunity_id}`} className="hover:underline">{a.account_name ?? a.opportunity_id}</Link>
                        {a.due_date && ` · due ${a.due_date}`}
                      </div>
                    </div>
                    <Badge variant="outline" className="text-[10px]">{a.action_type}</Badge>
                  </div>
                  {a.why && <p className="text-xs text-muted-foreground">{a.why}</p>}
                  <div className="flex gap-2">
                    <Button size="sm" disabled={pending === a.action_id} onClick={() => void decide(a, 'accepted')}>Accept</Button>
                    <Button size="sm" variant="outline" disabled={pending === a.action_id} onClick={() => void decide(a, 'done')}>Done</Button>
                    <Button size="sm" variant="ghost" disabled={pending === a.action_id} onClick={() => void decide(a, 'dismissed')}>Dismiss</Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
