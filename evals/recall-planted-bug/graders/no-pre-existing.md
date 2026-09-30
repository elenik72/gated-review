---
type: regex
target: { source: file, path: .review/state.json }
pattern: 'src/legacy/'
match: not_contains
weight: 2
arm: with-only
---
