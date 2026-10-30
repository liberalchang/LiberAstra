import { useId, useLayoutEffect, useMemo, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";

import { selectClass } from "@/components/ui/field";
import { cn } from "@/lib/utils";

export interface SearchOption {
  value: string;
  label: string;
  /** 次要信息，例如工作流包 id */
  hint?: string;
  group?: string;
}

const menuFieldClass =
  "min-h-11 w-full rounded-[10px] border border-border bg-field px-3 py-1.5 text-left text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** 选项带次行，或列表很长时，用可搜索菜单；短列表仍用原生 select。 */
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
  const hinted = options.some((item) => item.hint && item.hint !== item.label);
  if (options.length <= 8 && !hinted) {
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
  return (
    <SearchMenu
      value={value}
      onChange={onChange}
      options={options}
      ariaLabel={ariaLabel}
      placeholder={placeholder}
      emptyText={emptyText}
      disabled={disabled}
    />
  );
}

function SearchMenu({
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
  const listId = useId();
  const anchorRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(false);
  const selected = options.find((item) => item.value === value);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle || !editing) return options;
    return options.filter((item) =>
      `${item.label} ${item.hint ?? ""} ${item.value} ${item.group ?? ""}`.toLowerCase().includes(needle),
    );
  }, [editing, options, query]);
  const box = useMenuBox(open, anchorRef);

  useLayoutEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const close = () => {
    setOpen(false);
    setEditing(false);
    setQuery("");
  };

  let lastGroup = "";
  const menu =
    open && box
      ? createPortal(
          <ul
            id={listId}
            role="listbox"
            className="overflow-auto rounded-xl border border-border bg-card p-1 shadow-lg"
            style={{
              position: "fixed",
              top: box.top,
              left: box.left,
              width: box.width,
              maxHeight: box.maxHeight,
              zIndex: 80,
            }}
          >
            {filtered.map((item) => {
              const showGroup = Boolean(item.group) && item.group !== lastGroup;
              if (item.group) lastGroup = item.group;
              return (
                <li key={`${item.group ?? ""}-${item.value}`} role="presentation">
                  {showGroup && (
                    <div className="px-2 pb-1 pt-2 text-xs text-muted-foreground">{item.group}</div>
                  )}
                  <button
                    type="button"
                    role="option"
                    aria-selected={item.value === value}
                    className={cn(
                      "flex w-full flex-col rounded-lg px-2 py-1.5 text-left hover:bg-muted",
                      item.value === value && "bg-primary/10",
                    )}
                    onMouseDown={(event) => {
                      event.preventDefault();
                      onChange(item.value);
                      close();
                    }}
                  >
                    <span className="whitespace-normal text-sm leading-5">{item.label}</span>
                    {item.hint && item.hint !== item.label && (
                      <span className="truncate text-xs text-muted-foreground">{item.hint}</span>
                    )}
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 && <li className="px-2 py-2 text-sm text-muted-foreground">{emptyText}</li>}
          </ul>,
          document.body,
        )
      : null;

  return (
    <div ref={anchorRef} className="relative min-w-0 w-full flex-1">
      {open ? (
        <input
          ref={inputRef}
          className={cn(menuFieldClass, "h-11")}
          aria-label={ariaLabel}
          role="combobox"
          aria-expanded
          aria-controls={listId}
          disabled={disabled}
          placeholder={selected?.label || placeholder}
          value={editing ? query : (selected?.label ?? "")}
          onChange={(event) => {
            const next = event.target.value;
            const base = selected?.label ?? "";
            if (!editing) {
              const typed = next.startsWith(base) ? next.slice(base.length) : next;
              setEditing(true);
              setQuery(typed);
              return;
            }
            setQuery(next);
          }}
          onBlur={() => {
            window.setTimeout(close, 120);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") close();
          }}
        />
      ) : (
        <button
          type="button"
          className={cn(menuFieldClass, "flex flex-col items-start justify-center")}
          aria-label={ariaLabel}
          aria-expanded={false}
          aria-controls={listId}
          disabled={disabled}
          onClick={() => setOpen(true)}
        >
          <span className="w-full whitespace-normal leading-5">{selected?.label || placeholder}</span>
          {selected?.hint && selected.hint !== selected.label && (
            <span className="w-full truncate text-xs text-muted-foreground">{selected.hint}</span>
          )}
        </button>
      )}
      {menu}
    </div>
  );
}

function useMenuBox(open: boolean, anchor: RefObject<HTMLDivElement | null>) {
  const [box, setBox] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null);
  useLayoutEffect(() => {
    if (!open) return;
    const update = () => {
      const el = anchor.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const below = window.innerHeight - rect.bottom - 8;
      const above = rect.top - 8;
      const maxHeight = Math.max(120, Math.min(256, Math.max(below, above)));
      const openUp = below < 160 && above > below;
      setBox({
        top: openUp ? Math.max(8, rect.top - maxHeight - 4) : rect.bottom + 4,
        left: rect.left,
        width: rect.width,
        maxHeight,
      });
    };
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [anchor, open]);
  return box;
}
