import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { markdownToHtml } from 'satteri';
import { repositoryUrl, repositoryLinks } from '../src/lib/repository.mjs';
import { checkBuiltRepositoryLinks, checkRepositoryTargets } from '../scripts/check-repository-links.mjs';

test('repository links pin the published commit and retain section fragments', () => {
  assert.equal(repositoryUrl('docs/user-input.md#receipts-restart-and-session-occupancy'),
    'https://github.com/RalfNick/relf-agent/blob/300c62ce8dd417df6b471ce1c10a1b7a562d2c46/docs/user-input.md#receipts-restart-and-session-occupancy');
  assert.match(repositoryUrl('docs', 'tree'), /\/tree\/[a-f0-9]{40}\/docs$/);
});

test('repository links refuse traversal, external targets and unsupported kinds', () => {
  for (const path of ['../secret', '/docs/x.md', 'docs/../x.md', 'https://example.com', 'docs/x.md?raw=1'])
    assert.throws(() => repositoryUrl(path));
  assert.throws(() => repositoryUrl('docs/x.md', 'edit'));
});

test('rendered Markdown uses the pinned ref for inline and reference-style links', () => {
  const result = markdownToHtml('[Input](repo:docs/user-input.md) [README][readme] [External](https://example.com)\n\n[readme]: repo:README.md#installation',
    { mdastPlugins: [repositoryLinks] });
  assert.ok(result.html.includes(`href="${repositoryUrl('docs/user-input.md')}"`));
  assert.ok(result.html.includes(`href="${repositoryUrl('README.md#installation')}"`));
  assert.ok(result.html.includes('href="https://example.com"'));
  assert.ok(!result.html.includes('href="repo:'));
});

test('current delivery links reach main while ordinary repository links remain pinned', () => {
  const result = markdownToHtml('[Current](current-delivery:docs/current-delivery.md) [Record][delivery] [Snapshot](repo:docs/current-delivery.md)\n\n[delivery]: current-delivery:docs/current-delivery.md',
    { mdastPlugins: [repositoryLinks] });
  assert.equal((result.html.match(/href="https:\/\/github.com\/RalfNick\/relf-agent\/blob\/main\/docs\/current-delivery.md"/g) ?? []).length, 2);
  assert.ok(result.html.includes('href="https://github.com/RalfNick/relf-agent/blob/300c62ce8dd417df6b471ce1c10a1b7a562d2c46/docs/current-delivery.md"'));
  assert.ok(!result.html.includes('href="current-delivery:'));
});

test('current delivery alias refuses any other path, fragment or query', () => {
  for (const path of [
    'README.md', 'docs/other.md', '../docs/current-delivery.md',
    '/docs/current-delivery.md', 'docs/../docs/current-delivery.md',
    'docs/current-delivery.md#status', 'docs/current-delivery.md?raw=1',
    'docs/%63urrent-delivery.md', 'https://example.com', '',
  ]) {
    assert.throws(() => markdownToHtml(`[Current](current-delivery:${path})`,
      { mdastPlugins: [repositoryLinks] }), /Invalid current delivery target/);
  }
});

test('build validation allows only the exact current delivery URL on main', () => {
  const problems = checkRepositoryTargets([
    'https://github.com/RalfNick/relf-agent/blob/main/docs/current-delivery.md',
    'https://github.com/RalfNick/relf-agent/blob/main/docs/user-input.md',
    'https://github.com/RalfNick/relf-agent/tree/main/docs/current-delivery.md',
    'https://github.com/RalfNick/relf-agent/blob/main/docs/current-delivery.md?raw=1',
    'https://github.com/RalfNick/relf-agent/blob/main/docs/current-delivery.md#status',
    'https://github.com/RalfNick/relf-agent/blob/main/docs/../docs/current-delivery.md',
    'https://github.com/RalfNick/relf-agent/blob/main/docs/%63urrent-delivery.md',
  ], new Set());
  assert.equal(problems.length, 6);
  assert.ok(problems.every((problem) => problem.startsWith('Unpinned repository URL:')));
});

test('build validation rejects unresolved current delivery aliases', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'relf-repository-links-'));
  try {
    await writeFile(join(dir, 'index.html'), '<a href="current-delivery:docs/current-delivery.md">Current</a>');
    await assert.rejects(checkBuiltRepositoryLinks(dir), /Unresolved repository link/);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test('build validation catches missing refs and unpublished files in outgoing links', () => {
  const problems = checkRepositoryTargets([
    'https://github.com/RalfNick/relf-agent/blob/main/docs/user-input.md',
    repositoryUrl('website/src/content/guides/en/overview.md'),
    repositoryUrl('docs/user-input.md'),
    repositoryUrl('docs', 'tree'),
  ], new Set(['docs/user-input.md']));
  assert.equal(problems.length, 2);
  assert.match(problems[0], /Unpinned/);
  assert.match(problems[1], /Unpublished/);
});

test('build validation rejects cached links to the previous repository after rename', () => {
  const problems = checkRepositoryTargets([
    'https://github.com/RalfNick/ralf-agent',
    'https://github.com/RalfNick/ralf-agent/blob/0b9b6c9682c40285d91994cd831aa93d7e814bf1/docs/user-input.md',
    'https://github.com/RalfNick/ralf-agent/tree/0b9b6c9682c40285d91994cd831aa93d7e814bf1/docs',
    'https://github.com/RalfNick/ralf-agent/releases/tag/v0.1.0a2',
    'https://github.com/RalfNick/ralf-agent-extra/blob/main/docs/user-input.md',
    repositoryUrl('docs/user-input.md'),
  ], new Set(['docs/user-input.md']));
  assert.equal(problems.length, 4);
  assert.ok(problems.every((problem) => problem.startsWith('Stale repository URL:')));
});
