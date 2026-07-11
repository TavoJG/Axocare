function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value: string): string {
  return escapeHtml(value).replaceAll("`", "&#96;");
}

function sanitizeUrl(value: string): string | null {
  const trimmed = value.trim();
  if (/^(https?:|mailto:)/i.test(trimmed)) return trimmed;
  return null;
}

function renderInline(text: string): string {
  let html = escapeHtml(text);
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_match, label: string, url: string) => {
    const safeUrl = sanitizeUrl(url);
    if (!safeUrl) return label;
    return `<a href="${escapeAttribute(safeUrl)}" target="_blank" rel="noreferrer">${label}</a>`;
  });
  return html;
}

function flushParagraph(paragraph: string[], blocks: string[]): void {
  if (!paragraph.length) return;
  blocks.push(`<p>${paragraph.map((line) => renderInline(line)).join("<br>")}</p>`);
  paragraph.length = 0;
}

function flushList(items: string[], ordered: boolean, blocks: string[]): void {
  if (!items.length) return;
  const tag = ordered ? "ol" : "ul";
  blocks.push(`<${tag}>${items.map((item) => `<li>${renderInline(item)}</li>`).join("")}</${tag}>`);
  items.length = 0;
}

export function renderMarkdown(markdown: string): string {
  const normalized = markdown.replace(/\r\n/g, "\n").trim();
  if (!normalized) return "";

  const blocks: string[] = [];
  const paragraph: string[] = [];
  let listItems: string[] = [];
  let orderedList = false;
  let codeFence: string[] | null = null;

  for (const line of normalized.split("\n")) {
    if (line.startsWith("```")) {
      flushParagraph(paragraph, blocks);
      flushList(listItems, orderedList, blocks);
      if (codeFence === null) {
        codeFence = [];
      } else {
        blocks.push(`<pre><code>${escapeHtml(codeFence.join("\n"))}</code></pre>`);
        codeFence = null;
      }
      continue;
    }

    if (codeFence !== null) {
      codeFence.push(line);
      continue;
    }

    if (!line.trim()) {
      flushParagraph(paragraph, blocks);
      flushList(listItems, orderedList, blocks);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushParagraph(paragraph, blocks);
      flushList(listItems, orderedList, blocks);
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    const unordered = line.match(/^[-*]\s+(.+)$/);
    if (unordered) {
      flushParagraph(paragraph, blocks);
      if (listItems.length && orderedList) flushList(listItems, orderedList, blocks);
      orderedList = false;
      listItems.push(unordered[1]);
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (ordered) {
      flushParagraph(paragraph, blocks);
      if (listItems.length && !orderedList) flushList(listItems, orderedList, blocks);
      orderedList = true;
      listItems.push(ordered[1]);
      continue;
    }

    flushList(listItems, orderedList, blocks);
    paragraph.push(line);
  }

  if (codeFence !== null) blocks.push(`<pre><code>${escapeHtml(codeFence.join("\n"))}</code></pre>`);
  flushParagraph(paragraph, blocks);
  flushList(listItems, orderedList, blocks);
  return blocks.join("");
}
