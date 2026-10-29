export function PageHeader({ title, description }: { title: string; description: string }) {
  return (
    <header>
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">FinLedger</p>
      <h1 className="mt-1 text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="mt-1 max-w-xl text-sm text-muted-foreground">{description}</p>
    </header>
  );
}
