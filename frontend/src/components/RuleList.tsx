import { SyntheticEvent, useState } from "react";
import { useAction } from "../hooks";
import type { Rule, RuleKind } from "../types";

export default function RuleList(props: {
  rules: Rule[];
  onCreate: (kind: RuleKind, pattern: string) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}) {
  const [kind, setKind] = useState<RuleKind>("keyword");
  const [pattern, setPattern] = useState("");
  const action = useAction();

  const canAdd = pattern.trim() !== "" && !action.busy;

  async function add(event: SyntheticEvent) {
    event.preventDefault();
    event.stopPropagation();
    if (!canAdd) return;
    await action.run(async () => {
      await props.onCreate(kind, pattern);
      setPattern("");
    });
  }

  return (
    <div className="stack">
      {action.error && <p className="error">{action.error}</p>}
      <div className="chips">
        {props.rules.map((rule) => (
          <span key={rule.id} className="chip">
            {rule.kind === "regex" && <span className="muted">regex</span>} {rule.pattern}
            <button type="button" className="link" title="Remove" onClick={() => action.run(() => props.onDelete(rule.id))}>
              ×
            </button>
          </span>
        ))}
        {props.rules.length === 0 && <span className="muted">No rules.</span>}
      </div>
      <div className="inline">
        <select value={kind} onChange={(e) => setKind(e.target.value as RuleKind)}>
          <option value="keyword">Keyword</option>
          <option value="regex">Regex</option>
        </select>
        <input
          placeholder={kind === "keyword" ? "e.g. karaoke" : "e.g. pt\\.? ?\\d+"}
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add(e)}
        />
        <button type="button" disabled={!canAdd} onClick={add}>Add rule</button>
      </div>
    </div>
  );
}
