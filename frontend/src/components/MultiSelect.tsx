import { useEffect, useRef, useState } from "react";

export interface Option {
  value: string;
  label: string;
  hint?: string;
}

export function toggled(set: Set<string>, value: string): Set<string> {
  const next = new Set(set);
  if (!next.delete(value)) next.add(value);
  return next;
}

export default function MultiSelect({ noun, options, hidden, onChange }: {
  noun: string;
  options: Option[];
  hidden: Set<string>;
  onChange: (hidden: Set<string>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function closeOnOutsideClick(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const shown = options.filter((option) => !hidden.has(option.value));
  const term = search.trim().toLocaleLowerCase();
  const visible = term ? options.filter((option) => option.label.toLocaleLowerCase().includes(term)) : options;
  const summary = shown.length === options.length
    ? `All ${noun}`
    : shown.length === 0
      ? `No ${noun}`
      : shown.length === 1 ? shown[0].label : `${shown.length} of ${options.length} ${noun}`;

  function showVisible(show: boolean) {
    const next = new Set(hidden);
    for (const option of visible) {
      if (show) next.delete(option.value);
      else next.add(option.value);
    }
    onChange(next);
  }

  return (
    <div className="multi-select" ref={root}>
      <button
        type="button"
        className={shown.length < options.length ? "multi-select-trigger filtered" : "multi-select-trigger"}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span>{summary}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div className="multi-select-panel">
          {options.length > 8 && (
            <input
              type="search"
              aria-label={`Search ${noun}`}
              placeholder={`Search ${noun}`}
              value={search}
              autoFocus
              onChange={(e) => setSearch(e.target.value)}
            />
          )}
          <div className="multi-select-actions">
            <button type="button" className="small ghost" onClick={() => showVisible(true)}>Select all</button>
            <button type="button" className="small ghost" onClick={() => showVisible(false)}>Clear</button>
          </div>
          <ul className="multi-select-options">
            {visible.map((option) => (
              <li key={option.value}>
                <label>
                  <input
                    type="checkbox"
                    checked={!hidden.has(option.value)}
                    onChange={() => onChange(toggled(hidden, option.value))}
                  />
                  <span className="multi-select-label">{option.label}</span>
                  {option.hint && <small>{option.hint}</small>}
                </label>
                <button
                  type="button"
                  className="small ghost"
                  onClick={() => onChange(new Set(options.map((o) => o.value).filter((v) => v !== option.value)))}
                >
                  Only
                </button>
              </li>
            ))}
            {!visible.length && <li className="muted">No match</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
