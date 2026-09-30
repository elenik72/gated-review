#!/usr/bin/env bash
set -euo pipefail
git init -q -b main . && git config user.email e@x && git config user.name e
mkdir -p src && printf 'export async function load(id: string) { return fetchUser(id); }\n' > src/user.ts
git add -A && git commit -qm base && git checkout -qb feature/cache
cat > src/user.ts <<'TS'
const cache = new Map<string, Promise<User>>();
// cache the promise, not the value: concurrent callers share one request
export function load(id: string) {
  let p = cache.get(id);
  if (!p) { p = fetchUser(id).catch((e) => { cache.delete(id); throw e; }); cache.set(id, p); }
  return p;
}
TS
git add -A && git commit -qm "perf: dedupe user loads"
