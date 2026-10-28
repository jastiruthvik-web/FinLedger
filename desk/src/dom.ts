type Child = Node | string | null | false | undefined;
type Props = Record<string, string | undefined>;

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Props = {},
  children: Child[] = [],
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined) continue;
    if (key === "class") node.className = value;
    else if (key === "value" && (node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement)) node.value = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false || child === "") continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

export function setTitle(title: string) {
  document.title = title === "FinLedger" ? title : `${title} · FinLedger`;
}

export function followLink(event: MouseEvent, go: (url: string) => void, url: string) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  go(url);
}
