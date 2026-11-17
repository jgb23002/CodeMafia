import type { ReactNode } from 'react';

/** Temporary screen for routes whose real UI lands in a later week. */
export function PlaceholderPage({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section className="placeholder">
      <h1>{title}</h1>
      {children ?? <p>This screen is coming in a later week.</p>}
    </section>
  );
}
