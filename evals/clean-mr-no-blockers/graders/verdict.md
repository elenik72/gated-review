---
type: llm
---
PASS if the reply states there are no blocking issues in src/user.ts.
FAIL if it reports a race, a memory leak or a swallowed error in load() as blocking.
