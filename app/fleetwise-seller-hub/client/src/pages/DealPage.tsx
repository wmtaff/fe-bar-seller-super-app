import { useState } from 'react';
import { Link, useParams } from 'react-router';
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
  Textarea,
} from '@databricks/appkit-ui/react';
import { api, asList, dateTime, pct, str, usd, useApi } from '../lib/api';
import { usePersona } from '../lib/persona';
import { EmptyState, ErrorState, LoadingRows, ProbBar } from '../components/States';

type Row = Record<string, unknown>;

interface Note {
  id: string;
  body: string;
  persona_user_id: string;
  created_at: string;
}

interface Deal360 {
  opportunity: Row;
  scores: Row;
  account: Row | null;
  insights: Row[];
  contacts: Row[];
  actions: Row[];
  notes: Note[];
}

const PRODUCTS: [string, string][] = [
  ['Vehicle Telematics', 'adoption_vehicle_telematics_30d'],
  ['AI Dash Cams', 'adoption_ai_dash_cams_30d'],
  ['Driver Safety', 'adoption_driver_safety_30d'],
  ['Fuel & Maintenance', 'adoption_fuel_maintenance_30d'],
  ['Compliance/ELD', 'adoption_compliance_eld_30d'],
  ['Equipment Monitoring', 'adoption_equipment_monitoring_30d'],
];

const s = (v: unknown) => (v === null || v === undefined || v === '' ? '–' : str(v));

/** Prospects (no ARR, no telemetry) get a "prospect" panel instead of empty usage bars. */
const isProspect = (a: Row) => !Number(a.arr) && a.active_vehicles_30d == null && asList(a.products_owned).length === 0;

function ProductChips({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className="text-muted-foreground">{title}:</span>
      {items.length === 0 ? <span className="text-muted-foreground">none</span> : items.map((p) => (
        <Badge key={p} variant="secondary">{p}</Badge>
      ))}
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase text-muted-foreground">{title}</h4>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None captured</p>
      ) : (
        <ul className="list-disc pl-5 text-sm space-y-0.5">
          {items.map((i) => <li key={i}>{i}</li>)}
        </ul>
      )}
    </div>
  );
}

export function DealPage() {
  const { id } = useParams();
  const { version } = usePersona();
  const deal = useApi<Deal360>(id ? `/api/deals/${encodeURIComponent(id)}` : null, [version]);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  const addNote = async () => {
    if (!deal.data || !draft.trim()) return;
    setSaving(true);
    setNoteError(null);
    try {
      const res = await api<{ notes: Note[] }>(`/api/deals/${encodeURIComponent(id ?? '')}/notes`, { method: 'POST', body: { body: draft } });
      deal.setData({ ...deal.data, notes: res.notes });
      setDraft('');
    } catch (e) {
      setNoteError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (deal.loading && !deal.data) return <LoadingRows rows={8} />;
  if (deal.error) return <ErrorState message={deal.error} onRetry={deal.reload} />;
  if (!deal.data) return <EmptyState title="Deal not found" />;

  const { opportunity: o, scores, account: a, insights, contacts, actions, notes } = deal.data;
  const latest = insights.find((i) => !i.extract_error) ?? insights[0];

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-muted-foreground hover:underline">← My Week</Link>
        <h2 className="text-2xl font-bold mt-1">{s(o.account_name)}</h2>
        <p className="text-sm text-muted-foreground">
          {s(o.opportunity_name)} · {s(o.stage)} · {usd(o.acv)} ACV · closes {s(o.close_date).slice(0, 10)} ({s(o.fiscal_quarter)}) · owner {s(o.owner_name)}
        </p>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="outline">{s(o.forecast_category)}</Badge>
          <Badge variant="outline">{s(o.primary_product)}</Badge>
          {o.competitor ? <Badge variant="secondary">Competitor: {s(o.competitor)}</Badge> : null}
          <Badge variant="outline">Stage age {s(o.stage_age_days)}d</Badge>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle><h3>Deal scores</h3></CardTitle>
            <CardDescription>OpenJev classifier · scored {dateTime(scores.scored_at)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>P(close this quarter) <ProbBar value={scores.p_close_quarter as number | null} label="P(close this quarter)" /></div>
            <div>Competitive risk <ProbBar value={scores.competitive_risk as number | null} label="Competitive risk" /></div>
            <div>Churn risk <ProbBar value={scores.churn_risk as number | null} label="Churn risk" /></div>
            <div className="text-xs text-muted-foreground">
              Label {s(scores.close_label)} ({pct(scores.close_confidence)} confidence) · next action {s(scores.next_action)} ({pct(scores.next_action_conf)})
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle><h3>Call insights</h3></CardTitle>
            <CardDescription>
              {latest ? `Latest call ${dateTime(latest.started_at)} · sentiment ${s(latest.sentiment)} · ${insights.length} call(s)` : 'Extracted from call transcripts with ai_query'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!latest ? (
              <>
                <h4 className="text-xs font-semibold uppercase text-muted-foreground">Next steps</h4>
                <EmptyState title="No call insights yet" description="No recorded calls for this deal." />
              </>
            ) : (
              <>
                {latest.summary ? <p className="text-sm">{s(latest.summary)}</p> : null}
                <div className="grid md:grid-cols-2 gap-4">
                  <ListBlock title="Next steps" items={asList(latest.next_steps)} />
                  <ListBlock title="Open items" items={asList(latest.open_items)} />
                  <ListBlock title="Competitors" items={asList(latest.competitors)} />
                  <ListBlock title="Objections" items={asList(latest.objections)} />
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle><h3>Account usage and products</h3></CardTitle>
            <CardDescription>
              {!a
                ? 'Account 360'
                : isProspect(a)
                  ? `${s(a.industry)} · ${s(a.fleet_size)} vehicles · Prospect (no ARR yet)`
                  : `${s(a.industry)} · ${s(a.fleet_size)} vehicles · ARR ${usd(a.arr)} · usage as of ${s(a.usage_as_of)}`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {!a ? (
              <EmptyState title="No account data" />
            ) : isProspect(a) ? (
              <>
                <p className="text-muted-foreground">
                  Prospect: not a customer yet, so there is no product telemetry. The whole product line is
                  whitespace for this deal.
                </p>
                <ProductChips title="Whitespace" items={asList(a.whitespace_products)} />
              </>
            ) : (
              <>
                <div className="flex flex-wrap gap-4 text-xs">
                  <span>Active vehicles (30d): <strong>{s(a.active_vehicles_30d)}</strong></span>
                  <span>Usage trend (30d): <strong>{pct(a.usage_trend_pct_30d, 1)}</strong></span>
                  <span>Open tickets: <strong>{s(a.open_tickets)}</strong> (P1 30d: {s(a.p1_tickets_30d)})</span>
                </div>
                {PRODUCTS.map(([name, col]) => (
                  <div key={col} className="grid grid-cols-[160px_1fr] items-center gap-2">
                    <span className="text-xs">{name}</span>
                    <ProbBar value={a[col] as number | null} label={`${name} adoption (30d)`} />
                  </div>
                ))}
                <ProductChips title="Owned" items={asList(a.products_owned)} />
                <ProductChips title="Whitespace" items={asList(a.whitespace_products)} />
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle><h3>Contacts</h3></CardTitle>
            <CardDescription>Email and phone are masked in Unity Catalog before they reach the app</CardDescription>
          </CardHeader>
          <CardContent>
            {contacts.length === 0 ? (
              <EmptyState title="No contacts" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Phone</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contacts.map((c) => (
                    <TableRow key={String(c.contact_id)}>
                      <TableCell>{s(c.name)}<div className="text-xs text-muted-foreground">{s(c.title)}</div></TableCell>
                      <TableCell className="text-xs">{s(c.buyer_role)}</TableCell>
                      <TableCell className="text-xs">{s(c.email)}</TableCell>
                      <TableCell className="text-xs">{s(c.phone)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle><h3>Actions on this deal</h3></CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {actions.length === 0 ? (
              <EmptyState title="No next best actions" />
            ) : (
              actions.map((x) => (
                <div key={String(x.action_id)} className="flex items-start gap-2 text-sm border-b pb-2">
                  <div className="flex-1">
                    <div>{s(x.title)}</div>
                    <div className="text-xs text-muted-foreground">{s(x.why)}</div>
                  </div>
                  <Badge variant={x.decision ? 'secondary' : 'outline'}>{x.decision ? s(x.decision) : 'open'}</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle><h3>Notes</h3></CardTitle>
            <CardDescription>Saved to Lakebase (app.notes)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Add a note about this deal" maxLength={4000} aria-label="New note" />
            <Button size="sm" onClick={() => void addNote()} disabled={saving || !draft.trim()}>{saving ? 'Saving…' : 'Add note'}</Button>
            {noteError && <ErrorState message={noteError} />}
            {notes.length === 0 ? (
              <EmptyState title="No notes yet" />
            ) : (
              notes.map((n) => (
                <div key={n.id} className="text-sm border-b pb-2">
                  <div className="whitespace-pre-wrap">{n.body}</div>
                  <div className="text-xs text-muted-foreground">{dateTime(n.created_at)}</div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
