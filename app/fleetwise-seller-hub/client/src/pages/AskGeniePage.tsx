import { Badge, GenieChat } from '@databricks/appkit-ui/react';
import { usePersona } from '../lib/persona';

export function AskGeniePage() {
  const { me } = usePersona();
  return (
    <div className="space-y-4 w-full max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-foreground">Ask Genie</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Fleetwise Revenue Copilot answers questions about your pipeline, KPIs, accounts and next best actions.
        </p>
        <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-muted-foreground">
          <Badge variant="secondary">Runs as {me?.email ?? 'the signed-in user'}</Badge>
          <span>
            On behalf of the signed-in user (OBO): Genie reads the row-filtered views, so answers are scoped to
            the persona {me ? <strong>{me.persona_name}</strong> : 'you act as'}.
          </span>
        </div>
      </div>
      <div className="h-[min(640px,70vh)] border rounded-lg overflow-hidden">
        <GenieChat alias="default" placeholder="e.g. What is my open pipeline by stage this quarter?" />
      </div>
      <p className="text-xs text-muted-foreground">
        AI-generated from governed data via Genie. Review the generated SQL shown with each answer before relying on it.
      </p>
    </div>
  );
}
