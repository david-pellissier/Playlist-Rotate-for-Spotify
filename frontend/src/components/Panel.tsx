import type { ReactNode } from "react";

export default function Panel({ title, description, grid, children }: {
  title: string;
  description?: ReactNode;
  grid?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </header>
      <div className="panel-body">{grid ? <div className="field-grid">{children}</div> : children}</div>
    </section>
  );
}
