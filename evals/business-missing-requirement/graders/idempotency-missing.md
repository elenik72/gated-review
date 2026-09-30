---
type: regex
target: { source: file, path: .review/state.json }
pattern: '"status":\s*"(missing|partial)"'
weight: 3
arm: with-only
---
