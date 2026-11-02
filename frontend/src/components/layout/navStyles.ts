import { cn } from "@/lib/utils";

export function navRowClass({
  active,
  open = false,
  direct = false,
  mini = false,
}: {
  active: boolean;
  open?: boolean;
  direct?: boolean;
  mini?: boolean;
}) {
  return cn(
    "flex h-10 items-center gap-2.5 rounded-lg px-3 text-sm text-foreground/85 transition-colors hover:bg-foreground/6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    active && "text-primary dark:text-[#c4b5fd]",
    active && (direct || open) && "bg-primary/15 font-medium hover:bg-primary/20",
    active && !direct && !open && "bg-primary/10 hover:bg-primary/15",
    !active && open && "bg-foreground/6",
    mini && "justify-center px-0",
  );
}

export function navSubItemClass({ active }: { active: boolean }) {
  return cn(
    "flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm text-foreground/85 transition-colors hover:bg-foreground/6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    active && "bg-primary/15 font-medium text-primary hover:bg-primary/20 dark:text-[#c4b5fd]",
  );
}
