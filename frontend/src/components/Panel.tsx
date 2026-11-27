import type { ReactNode } from "react";
import InfoTip from "./InfoTip";

export default function Panel({ title, info, children }: {
  title: string;
  info?: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>{title}{info && <InfoTip text={info} />}</h2>
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}
