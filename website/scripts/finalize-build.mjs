import { writeFile, rm, readFile, readdir } from "node:fs/promises";
import { join } from 'node:path';
import { gunzipSync, gzipSync } from 'node:zlib';
import { loadEnv } from "vite";
import { siteMetadata, locales, guideSlugs } from "../src/lib/site.ts";
import { strictPagefindChunks } from './strict-pagefind.mjs';
import { buildSearchSnapshot, embedSearchSnapshot } from '../src/lib/search-snapshot.ts';

const entry = JSON.parse(await readFile('dist/pagefind/pagefind-entry.json', 'utf8'));
if (entry.version !== '1.5.2') throw new Error('Review Pagefind strict chunk handling after upgrading.');
for (const file of ['pagefind.js', 'pagefind-worker.js']) {
  const path = `dist/pagefind/${file}`;
  await writeFile(path, strictPagefindChunks(await readFile(path, 'utf8')));
}

// Use the indexer's rendered article text, including code, but deliver the
// entire current-language corpus with the HTML instead of a network waterfall.
const fragmentFiles = await readdir('dist/pagefind/fragment');
const snapshots = {};
for (const locale of locales) {
  const prefix = locale === 'zh' ? 'zh-cn_' : 'en_';
  const fragments = await Promise.all(fragmentFiles.filter((file) => file.startsWith(prefix) && file.endsWith('.pf_fragment')).map(async (file) => {
    const bytes = gunzipSync(await readFile(join('dist/pagefind/fragment', file)));
    if (bytes.subarray(0, 12).toString() !== 'pagefind_dcd') throw new Error('Pagefind fragment format changed');
    return JSON.parse(bytes.subarray(12).toString());
  }));
  snapshots[locale] = buildSearchSnapshot(fragments, locale, guideSlugs);
  const serialized = JSON.stringify(snapshots[locale]);
  console.log(`Search snapshot ${locale}: ${fragments.length} documents, ${Buffer.byteLength(serialized)} bytes / ${gzipSync(serialized).length} gzip bytes`);
}
async function embedDirectory(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) await embedDirectory(path);
    else if (entry.name.endsWith('.html')) {
      const html = await readFile(path, 'utf8');
      if (!html.includes('id="search-catalog"')) continue;
      const locale = /<html[^>]*lang="zh-CN"/.test(html) ? 'zh' : 'en';
      await writeFile(path, embedSearchSnapshot(html, snapshots[locale]));
    }
  }
}
await embedDirectory('dist');

const env = loadEnv("production", process.cwd(), "PUBLIC_");
const meta = siteMetadata(
  process.env.PUBLIC_SITE_URL || env.PUBLIC_SITE_URL,
  "/zh/",
);
if (meta.indexable) {
  const paths = locales.flatMap((locale) => [
    `/${locale}/`,
    ...guideSlugs.map((slug) => `/${locale}/docs/${slug}/`),
  ]);
  const escape = (value) =>
    value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll('"', "&quot;");
  await writeFile(
    "dist/sitemap.xml",
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${paths.map((path) => `<url><loc>${escape(meta.origin + path)}</loc></url>`).join("")}</urlset>\n`,
  );
  await writeFile(
    "dist/robots.txt",
    `User-agent: *\nAllow: /\nDisallow: /pagefind/\nSitemap: ${meta.origin}/sitemap.xml\n`,
  );
} else {
  await rm("dist/sitemap.xml", { force: true });
  await writeFile("dist/robots.txt", "User-agent: *\nDisallow: /\n");
}
console.log(
  `Metadata: ${meta.indexable ? meta.origin : "private preview · noindex · no sitemap"}`,
);
