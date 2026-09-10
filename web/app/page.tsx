"use client";

import { useEffect, useState } from "react";
import { dirtyState, loadMeta, type DirtyState, type Meta } from "@/lib/meta";

// Phase 1 proves the pipeline end to end: exporter -> web-data/ -> public/data/
// -> browser. Every value shown is a field of meta.json as exported.

const DIRTY: Record<DirtyState, { label: string; tone: string }> = {
  clean: { label: "Tracked files matched this commit", tone: "text-positive" },
  modified: {
    label: "Tracked files were modified: this commit does not describe the code that ran",
    tone: "text-negative",
  },
  unknown: { label: "Dirty state unknown: nothing verified the tree was clean", tone: "text-amber" },
};

export default function ProvenancePage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMeta().then(setMeta, (e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-16">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-amber">cricfield</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Data provenance</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        Read at runtime from <code className="font-mono text-text">/data/meta.json</code>, which the build copies
        from <code className="font-mono text-text">web-data/</code>. Nothing on this page is written into the code.
      </p>

      {error !== null ? (
        <div role="alert" className="mt-8 rounded-lg border border-negative bg-panel p-5 text-sm">
          <p className="font-semibold text-negative">Could not load meta.json</p>
          <p className="mt-1 font-mono text-muted">{error}</p>
        </div>
      ) : meta === null ? (
        <p className="mt-8 text-sm text-faint">Loading meta.json…</p>
      ) : (
        <Provenance meta={meta} />
      )}
    </main>
  );
}

function Provenance({ meta }: { meta: Meta }) {
  const dirty = DIRTY[dirtyState(meta)];
  return (
    <>
      <dl className="mt-8 grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-3">
        <Stat label="Matches" value={meta.matches.toLocaleString("en-GB")} />
        <Stat label="Deliveries" value={meta.deliveries.toLocaleString("en-GB")} />
        <Stat label="Seasons" value={`${meta.season_min}–${meta.season_max}`} />
      </dl>
      <dl className="mt-4 rounded-lg border border-border bg-panel p-5">
        <dt className="text-xs uppercase tracking-wider text-muted">Export commit</dt>
        <dd className="mt-2 break-all font-mono text-sm">{meta.git_commit}</dd>
        <dd className={`mt-2 text-sm ${dirty.tone}`}>{dirty.label}</dd>
        <dd className="mt-3 text-xs text-faint tabular-nums">
          Generated {meta.generated_at} · git read via {meta.git_source}
        </dd>
      </dl>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-panel p-5">
      <dt className="text-xs uppercase tracking-wider text-muted">{label}</dt>
      <dd className="mt-2 text-3xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}
