import test from 'node:test';
import assert from 'node:assert/strict';
import { createSearchBootstrap } from '../src/lib/search-bootstrap.ts';
import { createSnapshotIndex, buildSearchSnapshot, embedSearchSnapshot } from '../src/lib/search-snapshot.ts';

const english = {
  version: 1, locale: 'en', documents: [
    { url: '/en/docs/workflows/', title: 'Workflows', content: 'Use node-executor with durable approval recovery. Literal <tool> arguments.' },
    { url: '/en/docs/recovery/', title: 'Approval recovery', content: 'Inspect approval evidence and then resume the original run.' },
    { url: '/en/docs/api-reference/', title: 'API reference', content: 'AgentRun.subscribe_events and stream_updates expose durable observations.' },
  ],
};
const chinese = {
  version: 1, locale: 'zh', documents: [
    { url: '/zh/docs/workflows/', title: '工作流与节点', content: '受\u200b管理\u200b异步\u200b节点，使用 node-executor。' },
    { url: '/zh/docs/operations/', title: '运行与部署', content: '通过 subscribe_events 订阅事件，stream_updates 提供展示更新。' },
  ],
};

async function results(payload: unknown, locale: 'en' | 'zh', query: string) {
  const index = createSnapshotIndex(JSON.stringify(payload), locale);
  return Promise.all((await index.search(query)).results.map((r) => r.data()));
}

test('first English and Chinese queries find complete API identifiers without a search server', async () => {
  assert.deepEqual((await results(english, 'en', 'SUBSCRIBE_EVENTS')).map((r) => r.url), ['/en/docs/api-reference/']);
  assert.deepEqual((await results(english, 'en', 'node-executor')).map((r) => r.url), ['/en/docs/workflows/']);
  assert.deepEqual((await results(chinese, 'zh', '异步节点')).map((r) => r.url), ['/zh/docs/workflows/']);
  assert.deepEqual((await results(chinese, 'zh', 'stream_updates')).map((r) => r.url), ['/zh/docs/operations/']);
});

test('multiple terms must all match and an exact title ranks before body-only matches', async () => {
  assert.deepEqual((await results(english, 'en', 'approval recovery')).map((r) => r.url), ['/en/docs/recovery/', '/en/docs/workflows/']);
  assert.deepEqual(await results(english, 'en', 'approval subscribe_events'), []);
  assert.deepEqual(await results(chinese, 'zh', '   '), []);
  assert.deepEqual(await results(chinese, 'zh', '没有这个关键词'), []);
});

test('excerpts retain literal code as plain text', async () => {
  const [result] = await results(english, 'en', '<tool>');
  assert.equal(result.excerptFormat, 'text');
  assert.match(result.excerpt, /Literal <tool> arguments/);
  const [zh] = await results(chinese, 'zh', 'node-executor');
  assert.match(zh.excerpt, /节点，使用 node-executor。/);
});

test('snapshots fail closed for a wrong language, unsafe URL, duplicate document or malformed content', () => {
  for (const payload of [
    { ...english, locale: 'zh' }, { ...english, version: 2 },
    { ...english, documents: [{ ...english.documents[0], url: 'https://evil.invalid/en/docs/x/' }] },
    { ...english, documents: [{ ...english.documents[0], url: '/en/docs/../../zh/docs/x/' }] },
    { ...english, documents: [english.documents[0], english.documents[0]] },
    { ...english, documents: [{ ...english.documents[0], content: null }] },
    { ...english, documents: [] },
  ]) assert.throws(() => createSnapshotIndex(JSON.stringify(payload), 'en'));
  assert.throws(() => createSnapshotIndex('{', 'en'));
});

test('retry rereads the snapshot after an initialization failure and does not require Pagefind', async () => {
  let payload = '{';
  const bootstrap = createSearchBootstrap(async () => { throw new Error('network unavailable'); }, 'en', () => createSnapshotIndex(payload, 'en'));
  await assert.rejects(bootstrap.load());
  bootstrap.reset();
  payload = JSON.stringify(english);
  const index = await bootstrap.load();
  assert.equal((await (await index.search('node-executor')).results[0].data()).url, '/en/docs/workflows/');
});

test('build uses actual indexed text, requires complete coverage, and safely embeds literal script text', () => {
  const fragments = [{ url: '/zh/docs/workflows/', meta: { title: '工作流' }, content: '异\u200b步\u200b节点 </script><script>alert(1)</script>' }];
  const snapshot = buildSearchSnapshot(fragments, 'zh', ['workflows']);
  const html = embedSearchSnapshot('<html><script id="search-catalog" type="application/json">null</script></html>', snapshot);
  assert.equal((html.match(/<script\b/g) || []).length, 1);
  const serialized = html.match(/application\/json">([\s\S]*?)<\/script>/)![1];
  assert.equal(JSON.parse(serialized).documents[0].content, '异步节点 </script><script>alert(1)</script>');
  assert.throws(() => buildSearchSnapshot(fragments, 'zh', ['workflows', 'testing']), /coverage/i);
  assert.throws(() => embedSearchSnapshot('<html></html>', snapshot), /placeholder/i);
});
