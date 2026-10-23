export function NumberField(props: {
  label: string;
  value: number | null;
  min: number;
  optional?: boolean;
  onChange: (value: number | null) => void;
}) {
  return (
    <label>
      {props.label}
      <input
        type="number"
        min={props.min}
        required={!props.optional}
        value={props.value ?? ""}
        onChange={(e) => props.onChange(e.target.value === "" ? null : Number(e.target.value))}
      />
    </label>
  );
}

export function Checkbox(props: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="checkbox">
      <input type="checkbox" checked={props.checked} onChange={(e) => props.onChange(e.target.checked)} />
      {props.label}
    </label>
  );
}
