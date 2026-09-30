---
type: regex
target: { source: file, path: .review/state.json }
pattern: '"severity":\s*"blocking"'
match: not_contains
weight: 3
arm: with-only
---
