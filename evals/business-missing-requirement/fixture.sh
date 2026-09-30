#!/usr/bin/env bash
set -euo pipefail
git init -q -b main . && git config user.email e@x && git config user.name e
cat > TICKET.md <<'MD'
# PAY-42 Возвраты

Требования:
1. Возврат на полную сумму оплаты разрешён.
2. Повторный запрос возврата с тем же refund_id не создаёт второй возврат.
MD
mkdir -p src/billing && printf 'export const refunds: { id: string; amount: number }[] = [];\n' > src/billing/store.ts
git add -A && git commit -qm base && git checkout -qb feature/refund
cat > src/billing/refund.ts <<'TS'
import { refunds } from './store';

export function refund(refundId: string, paid: number, refunded: number, amount: number) {
  if (refunded + amount > paid) throw new Error('refund exceeds payment');
  refunds.push({ id: refundId, amount }); // planted: no check that refundId was already refunded
  return refunds.length;
}
TS
git add -A && git commit -qm "feat: refunds"
