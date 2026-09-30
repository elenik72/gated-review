---
type: regex
target: { source: file, path: .review/state.json }
pattern: '"quote":\s*"[^"]*refund_id'
weight: 2
arm: with-only
---
