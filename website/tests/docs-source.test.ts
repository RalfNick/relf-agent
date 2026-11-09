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
        sources: { 'docs/extending.md': '8d972ecf44342c33096562592434079a09fadadda3e1d7add98d7631384951e3' },
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
    assert.match(result.stderr, /Cannot read pinned documentation source 4bb46fe7a8935e6d13962a6c34e02519122c4c53:docs\/extending.md/);
    assert.match(result.stderr, /A full checkout containing this Git object is required/);
  });
});
