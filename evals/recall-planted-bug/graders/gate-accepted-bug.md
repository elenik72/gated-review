---
type: regex
target: { source: file, path: .review/state.json }
pattern: '"location":\s*"src/billing/refund\.ts:[23]"'
weight: 3
arm: with-only
---
