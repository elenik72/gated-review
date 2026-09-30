---
type: llm
weight: 2
---
PASS if the reply reports that refundable() in src/billing/refund.ts rejects a full refund (uses < where <= is needed) and gives a concrete failing input.
FAIL if that bug is missing, or if the reply reports the avg() issue in src/legacy/report.ts as a problem of this branch.
