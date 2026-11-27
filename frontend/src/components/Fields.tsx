import InfoTip from "./InfoTip";

export function NumberField(props: {
  label: string;
  info?: string;
  value: number | null;
  min: number;
  optional?: boolean;
  placeholder?: string;
  onChange: (value: number | null) => void;
}) {
  return (
    <label>
      <span>{props.label}{props.info && <InfoTip text={props.info} />}</span>
      <input
        type="number"
        min={props.min}
        required={!props.optional}
        placeholder={props.placeholder}
        value={props.value ?? ""}
        onChange={(e) => props.onChange(e.target.value === "" ? null : Number(e.target.value))}
      />
    </label>
  );
}

export function Checkbox(props: {
  label: string;
  info?: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className={props.disabled ? "checkbox disabled" : "checkbox"}>
      <input
        type="checkbox"
        checked={props.checked}
        disabled={props.disabled}
        onChange={(e) => props.onChange(e.target.checked)}
      />
      <span>{props.label}{props.info && <InfoTip text={props.info} />}</span>
    </label>
  );
}
