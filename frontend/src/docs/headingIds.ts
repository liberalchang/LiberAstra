export type MdNode = {
  type?: string;
  value?: string;
  children?: MdNode[];
  data?: { hProperties?: { id?: string; [key: string]: unknown } };
};

const CUSTOM_ID_RE = /\s*\{#([^}]+)\}\s*$/;

/** Split a VitePress-style trailing `{#id}` from a heading's text. */
export function splitHeadingId(text: string): { text: string; id: string | null } {
  const match = CUSTOM_ID_RE.exec(text);
  if (!match) return { text, id: null };
  return { text: text.slice(0, match.index).trimEnd(), id: match[1] };
}

/** Move `{#id}` from the heading text onto the mdast heading's hProperties.id. */
export function applyHeadingIds(tree: MdNode): void {
  if (!tree || typeof tree !== "object") return;

  if (tree.type === "heading" && Array.isArray(tree.children)) {
    for (let i = tree.children.length - 1; i >= 0; i -= 1) {
      const child = tree.children[i];
      if (child.type !== "text" || typeof child.value !== "string") continue;
      const parsed = splitHeadingId(child.value);
      if (!parsed.id) break;
      child.value = parsed.text;
      const data = tree.data ?? {};
      const props = data.hProperties ?? {};
      props.id = parsed.id;
      data.hProperties = props;
      tree.data = data;
      break;
    }
  }

  if (Array.isArray(tree.children)) {
    for (const child of tree.children) applyHeadingIds(child);
  }
}

/** remark plugin: support VitePress `{#id}` headings in the bundled app docs. */
export function remarkHeadingIds() {
  return (tree: unknown) => {
    applyHeadingIds(tree as MdNode);
  };
}
