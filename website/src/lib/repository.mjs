import repositoryInfo from '../../repository.json' with { type: 'json' };

export { repositoryInfo };
export const repository = repositoryInfo.url;
export const currentDeliveryUrl = `${repository}/blob/main/docs/current-delivery.md`;

/** Build a source URL against the published documentation snapshot. */
export function repositoryUrl(path, kind = 'blob') {
  if (!['blob', 'tree'].includes(kind) ||
      !/^[\w.-]+(?:\/[\w.-]+)*(?:#[^\s?]*)?$/.test(path) ||
      path.split('#')[0].split('/').some((part) => part === '.' || part === '..')) {
    throw new Error(`Invalid repository target: ${kind}:${path}`);
  }
  return `${repository}/${kind}/${repositoryInfo.ref}/${path}`;
}

/** Sätteri exposes immutable nodes; record URL edits through its context. */
function resolveLink(node, context) {
  if (node.url.startsWith('repo:')) context.setProperty(node, 'url', repositoryUrl(node.url.slice(5)));
  else if (node.url.startsWith('current-delivery:')) {
    if (node.url !== 'current-delivery:docs/current-delivery.md')
      throw new Error(`Invalid current delivery target: ${node.url}`);
    context.setProperty(node, 'url', currentDeliveryUrl);
  }
}
export const repositoryLinks = {
  name: 'published-repository-links',
  link: resolveLink,
  definition: resolveLink,
};
