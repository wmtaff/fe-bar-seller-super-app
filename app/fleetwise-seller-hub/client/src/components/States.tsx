import { Alert, AlertDescription, AlertTitle, Button, Empty, EmptyDescription, EmptyHeader, EmptyTitle, Skeleton } from '@databricks/appkit-ui/react';

export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>Could not load this panel</AlertTitle>
      <AlertDescription className="flex items-center gap-3">
        <span>{message}</span>
        {onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry}>
            Retry
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <Empty className="py-6">
      <EmptyHeader>
        <EmptyTitle>{title}</EmptyTitle>
        {description && <EmptyDescription>{description}</EmptyDescription>}
      </EmptyHeader>
    </Empty>
  );
}

/** Thin horizontal bar for a 0..1 probability. */
export function ProbBar({ value, label }: { value: number | null | undefined; label?: string }) {
  const v = value === null || value === undefined ? null : Math.max(0, Math.min(1, Number(value)));
  return (
    <div className="flex items-center gap-2 min-w-[120px]" title={label}>
      <div className="h-2 flex-1 rounded bg-muted overflow-hidden" role="meter" aria-valuemin={0} aria-valuemax={1} aria-valuenow={v ?? undefined} aria-label={label ?? 'probability'}>
        {v !== null && <div className="h-full bg-primary" style={{ width: `${v * 100}%` }} />}
      </div>
      <span className="text-xs tabular-nums w-9 text-right">{v === null ? '–' : `${Math.round(v * 100)}%`}</span>
    </div>
  );
}
