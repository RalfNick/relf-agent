import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const helper = fileURLToPath(new URL('../scripts/ensure-docs-source.sh', import.meta.url));

test('source preload makes a development commit available in a main-only clone', async () => {
  const root = await mkdtemp(join(tmpdir(), 'relf-docs-fetch-'));
  try {
    const origin = join(root, 'origin.git');
    const checkout = join(root, 'checkout');
    const env = {
      ...process.env,
      GIT_AUTHOR_NAME: 'Website fixture', GIT_COMMITTER_NAME: 'Website fixture',
      GIT_AUTHOR_EMAIL: 'website@example.invalid', GIT_COMMITTER_EMAIL: 'website@example.invalid',
    };
    const git = (cwd: string, args: string[], input?: string) =>
      execFileSync('git', args, { cwd, input, encoding: 'utf8', env, stdio: ['pipe', 'pipe', 'pipe'] }).trim();
    git(root, ['init', '--bare', origin]);
    const commit = (body: string, parent?: string) => {
      const blob = git(origin, ['hash-object', '-w', '--stdin'], body);
      const tree = git(origin, ['mktree'], `100644 blob ${blob}\tguide.md\n`);
      return git(origin, ['commit-tree', tree, ...(parent ? ['-p', parent] : [])], 'Source fixture\n');
    };
    const main = commit('Main source\n');
    const baseline = commit('Development source\n', main);
    const publishedTip = commit('Newer development source\n', baseline);
    git(origin, ['update-ref', 'refs/heads/main', main]);
    git(origin, ['update-ref', 'refs/heads/sdk-update', publishedTip]);
    git(root, ['clone', '--depth=1', '--single-branch', '--branch=main', pathToFileURL(origin).href, checkout]);
    assert.notEqual(spawnSync('git', ['cat-file', '-e', `${baseline}^{commit}`], { cwd: checkout }).status, 0);
    await writeFile(join(checkout, 'guide.md'), 'Local draft\n');

    const result = spawnSync('bash', [helper, baseline, 'refs/heads/sdk-update'], { cwd: checkout, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.equal(git(checkout, ['show', `${baseline}:guide.md`]), 'Development source');
    assert.equal(git(checkout, ['merge-base', baseline, publishedTip]), baseline);
    assert.equal(git(checkout, ['rev-parse', 'HEAD']), main);
    assert.equal(await readFile(join(checkout, 'guide.md'), 'utf8'), 'Local draft\n');
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('source preload rejects mutable refs before contacting an origin', () => {
  const result = spawnSync('bash', [helper, 'main'], { encoding: 'utf8' });
  assert.equal(result.status, 2, result.stderr || result.stdout);
});
