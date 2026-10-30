import { useMemo, useState } from "react";

import { selectClass } from "@/components/ui/field";
import { cn } from "@/lib/utils";

export interface SearchOption {
  value: string;
  label: string;
  /** 次要信息，例如工作流包 id */
  hint?: string;
  group?: string;
}

/** 选项很多时用可搜索列表；短列表仍用原生 select。 */
export function SearchSelect({
  value,
  onChange,
  options,
  ariaLabel,
  placeholder,
  emptyText,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  options: SearchOption[];
  ariaLabel: string;
  placeholder?: string;
  emptyText: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const selected = options.find((item) => item.value === value);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter((item) =>
      `${item.label} ${item.hint ?? ""} ${item.value} ${item.group ?? ""}`.toLowerCase().includes(needle),
    );
  }, [options, query]);

  if (options.length <= 8) {
    return (
      <select
        className={selectClass}
        aria-label={ariaLabel}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((item) => (
          <option key={`${item.group ?? ""}-${item.value}`} value={item.value}>
            {item.hint && item.hint !== item.label ? `${item.label} · ${item.hint}` : item.label}
          </option>
        ))}
      </select>
    );
  }

  let lastGroup = "";
  return (
    <div className="relative min-w-0">
      <input
        className={selectClass}
        aria-label={ariaLabel}
        role="combobox"
        aria-expanded={open}
        disabled={disabled}
        placeholder={placeholder}
        value={open ? query : (selected?.label ?? "")}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onBlur={() => {
          window.setTimeout(() => setOpen(false), 120);
        }}
      />
      {open && (
        <ul className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-xl border border-border bg-card p-1 shadow-lg">
          {filtered.map((item) => {
            const showGroup = Boolean(item.group) && item.group !== lastGroup;
            if (item.group) lastGroup = item.group;
            return (
              <li key={`${item.group ?? ""}-${item.value}`}>
                {showGroup && (
                  <div className="px-2 pb-1 pt-2 text-xs text-muted-foreground">{item.group}</div>
                )}
                <button
                  type="button"
                  className={cn(
                    "flex w-full flex-col rounded-lg px-2 py-1.5 text-left hover:bg-muted",
                    item.value === value && "bg-primary/10",
                  )}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    onChange(item.value);
                    setOpen(false);
                  }}
                >
                  <span className="truncate text-sm">{item.label}</span>
                  {item.hint && item.hint !== item.label && (
                    <span className="truncate text-xs text-muted-foreground">{item.hint}</span>
                  )}
                </button>
              </li>
            );
          })}
          {filtered.length === 0 && <li className="px-2 py-2 text-sm text-muted-foreground">{emptyText}</li>}
        </ul>
      )}
    </div>
  );
}
