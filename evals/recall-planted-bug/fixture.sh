#!/usr/bin/env bash
set -euo pipefail
git init -q -b main . && git config user.email e@x && git config user.name e
mkdir -p src/billing src/legacy
printf 'export const total = (xs: number[]) => xs.reduce((a, b) => a + b, 0);\n' > src/billing/sum.ts
printf 'export const avg = (xs: number[]) => xs.reduce((a,b)=>a+b)/xs.length; // pre-existing bug on []\n' > src/legacy/report.ts
git add -A && git commit -qm base
git checkout -qb feature/refund
cat > src/billing/refund.ts <<'TS'
export function refundable(paid: number, refunded: number, amount: number): boolean {
  // planted: must be <=, off-by-one rejects a full refund
  return refunded + amount < paid;
}
TS
git add -A && git commit -qm "feat: refunds"
