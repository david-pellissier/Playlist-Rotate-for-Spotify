import { toggled } from "./MultiSelect";

export default function ChipFilter<T extends string>({ label, options, counts, selected, onChange }: {
  label: string;
  options: Record<T, string>;
  counts: Partial<Record<T, number>>;
  selected: Set<string>;
  onChange: (selected: Set<string>) => void;
}) {
  return (
    <div className="chips" role="group" aria-label={label}>
      {(Object.entries(options) as [T, string][]).map(([value, name]) => {
        const on = selected.has(value);
        return (
          <label key={value} className={on ? "chip filter on" : "chip filter"}>
            <input type="checkbox" checked={on} onChange={() => onChange(toggled(selected, value))} />
            {name}
            <span className="chip-count">{counts[value] ?? 0}</span>
          </label>
        );
      })}
    </div>
  );
}
