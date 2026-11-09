import type { SearchData, SearchIndex } from './search-bootstrap';

type Locale = 'zh' | 'en';
interface SearchDocument { url: string; title: string; content: string }
interface SearchSnapshot { version: 1; locale: Locale; documents: SearchDocument[] }

const clean = (text: string) => text.replaceAll('\u200b', '').replace(/\s+/g, ' ').trim();
const folded = (text: string) => clean(text).normalize('NFKC').toLowerCase();

function readSnapshot(serialized: string, locale: Locale): SearchSnapshot {
  // Keep the small-corpus tradeoff explicit; review the transport before it grows.
  if (new TextEncoder().encode(serialized).length > 300_000) throw new Error('Search snapshot exceeds size budget');
  const snapshot = JSON.parse(serialized) as SearchSnapshot;
  if (!snapshot || snapshot.version !== 1 || snapshot.locale !== locale ||
      !Array.isArray(snapshot.documents) || !snapshot.documents.length || snapshot.documents.length > 100)
    throw new Error('Invalid search snapshot');
  const urls = new Set<string>();
  const path = new RegExp(`^/${locale}/docs/[a-z0-9-]+/$`);
  for (const document of snapshot.documents) {
    if (!document || typeof document.url !== 'string' || !path.test(document.url) || urls.has(document.url) ||
        typeof document.title !== 'string' || !document.title.trim() ||
        typeof document.content !== 'string' || !document.content.trim())
      throw new Error('Invalid search document');
    urls.add(document.url);
  }
  return snapshot;
}

/** Search the complete locale text already delivered in the page, including code. */
export function createSnapshotIndex(serialized: string, locale: Locale): SearchIndex {
  const snapshot = readSnapshot(serialized, locale);
  const documents = snapshot.documents.map((document) => {
    const content = clean(document.content);
    const title = folded(document.title);
    return { ...document, content, titleKey: title, textKey: folded(content), all: `${title} ${folded(content)}` };
  });
  let disposed = false;
  return {
    async search(query) {
      if (disposed) throw new Error('Search snapshot disposed');
      const terms = [...new Set(folded(query).split(/\s+/).filter(Boolean))];
      if (!terms.length) return { results: [] };
      const matches = documents.filter((document) => terms.every((term) => document.all.includes(term)));
      const score = (document: typeof documents[number]) =>
        (document.titleKey === terms.join(' ') ? 100 : 0) +
        terms.reduce((sum, term) => sum + (document.titleKey.includes(term) ? 20 : 0), 0);
      matches.sort((a, b) => score(b) - score(a) || a.url.localeCompare(b.url));
      return { results: matches.map((document) => ({ async data(): Promise<SearchData> {
        const location = terms.map((term) => document.textKey.indexOf(term)).find((index) => index >= 0) ?? 0;
        const start = Math.max(0, location - 55);
        const end = Math.min(document.content.length, start + 190);
        return {
          url: document.url, meta: { title: document.title }, excerptFormat: 'text',
          excerpt: `${start ? '…' : ''}${document.content.slice(start, end)}${end < document.content.length ? '…' : ''}`,
        };
      } })) };
    },
    async destroy() { disposed = true; },
  };
}

/** Pagefind extracts rendered article text at build time; no browser runtime is required. */
export function buildSearchSnapshot(
  fragments: { url: string; meta: { title: string }; content: string }[],
  locale: Locale,
  slugs: readonly string[],
): SearchSnapshot {
  const documents = fragments.map((fragment) => ({
    url: fragment.url, title: fragment.meta.title, content: clean(fragment.content),
  })).sort((a, b) => a.url.localeCompare(b.url));
  const expected = new Set(slugs.map((slug) => `/${locale}/docs/${slug}/`));
  if (documents.length !== expected.size || documents.some((document) => !expected.delete(document.url)) || expected.size)
    throw new Error(`Search snapshot coverage mismatch for ${locale}`);
  const snapshot: SearchSnapshot = { version: 1, locale, documents };
  readSnapshot(JSON.stringify(snapshot), locale);
  return snapshot;
}

export function embedSearchSnapshot(html: string, snapshot: SearchSnapshot): string {
  const placeholder = /<script\b(?=[^>]*\bid="search-catalog")(?=[^>]*\btype="application\/json")[^>]*>[\s\S]*?<\/script>/g;
  if ([...html.matchAll(placeholder)].length !== 1) throw new Error('Expected one search snapshot placeholder');
  // JSON is data, never executable markup (including literal </script> in code).
  const serialized = JSON.stringify(snapshot).replace(/[<>&\u2028\u2029]/g, (character) =>
    `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`);
  return html.replace(placeholder, () => `<script id="search-catalog" type="application/json">${serialized}</script>`);
}
