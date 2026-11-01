import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { repositoryInfo } from '../src/lib/repository.mjs';

const checker = fileURLToPath(new URL('../scripts/check-docs.mjs', import.meta.url));
const guide = 'sources: [docs/extending.md]\n\nFixture guide.\n';

async function fixture(run: (website: string, root: string) => void) {
  const root = await mkdtemp(join(tmpdir(), 'relf-docs-source-'));
  const website = join(root, 'website');
  try {
    for (const locale of ['zh', 'en']) {
      const dir = join(website, 'src/content/guides', locale);
      await mkdir(dir, { recursive: true });
      await writeFile(join(dir, 'fixture.md'), guide);
    }
    await mkdir(join(root, 'docs'));
    await writeFile(join(root, 'docs/extending.md'), 'Later working-tree maintenance.\n');
    const hash = createHash('sha256').update(guide).digest('hex');
    await writeFile(join(website, 'docs-source-lock.json'), JSON.stringify({
      repository: repositoryInfo,
      guides: { fixture: {
        translations: { zh: hash, en: hash },
        sources: { 'docs/extending.md': 'cf56f6ff6b559e009f953e91b073cd7a03ed2888f90c355d9e6104a17fdbfcff' },
      } },
    }));
    run(website, root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test('documentation sources come from the pinned Git object despite later working-tree changes', async () => {
  await fixture((cwd) => {
    const result = spawnSync(process.execPath, [checker], { cwd, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.match(result.stdout, /1 bilingual guide pairs match reviewed sources/);
  });
});

test('missing pinned Git objects fail clearly without falling back to working-tree sources', async () => {
  await fixture((cwd, root) => {
    const result = spawnSync(process.execPath, [checker], {
      cwd, encoding: 'utf8',
      env: { ...process.env, GIT_OBJECT_DIRECTORY: join(root, 'missing-objects'), GIT_ALTERNATE_OBJECT_DIRECTORIES: '' },
    });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Cannot read pinned documentation source 300c62ce8dd417df6b471ce1c10a1b7a562d2c46:docs\/extending.md/);
    assert.match(result.stderr, /A full checkout containing this Git object is required/);
  });
});
