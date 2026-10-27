import type { ReactNode } from "react";
import InfoTip from "./InfoTip";

export default function Panel({ title, info, grid, children }: {
  title: string;
  info?: string;
  grid?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>{title}{info && <InfoTip text={info} />}</h2>
      </header>
      <div className="panel-body">{grid ? <div className="field-grid">{children}</div> : children}</div>
    </section>
  );
}
