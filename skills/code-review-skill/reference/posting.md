# Posting review comments — format, placement, the re-review loop

> Read before posting anything to an MR. `<skill>` below is the directory of SKILL.md
> (Claude Code substitutes it as `${CLAUDE_SKILL_DIR}` in SKILL.md itself).

## Format and placement

When review findings are posted to a pull/merge request:

- **Attach each comment to the exact line of code it is about** — an inline diff
  comment (a discussion anchored to that file and line), NOT a general
  page-level comment on the PR/MR. If a finding also concerns another location,
  still anchor it to the most relevant changed line and name the other place in
  the text.
- **One comment per finding.** Do not bundle several findings into one comment.
- **Start every comment with the bold tag, its type and weight on the first line**,
  exactly in this shape (keep `**[ai-review-bot]**` bold, in square brackets):

  ```
  **[ai-review-bot]** · <тип> · <блокирует мерж | желательно | не важно> · <подтверждено | предположение>
  ```

  `finding.py render` writes it; never type it by hand. The type is not chosen — it
  follows from the claim form the gate checked:

  | Тип | Формы | Что значит для автора |
  |---|---|---|
  | 🐞 Баг | `breaks`, `unread` | ломается или не работает |
  | 📋 Требование | `unimplemented`, `unrequested` | расходится с тикетом |
  | 🔀 Коллизия | `collision` | столкнётся с соседней веткой — договориться до мержа |
  | ⚠️ Риск | `invariant` | корректность держится на незакреплённом условии |
  | 📐 Единообразие | `drift`, `rule` | расходится с соседями или с правилом репо |

  The weight is the severity in a word: blocking → «блокирует мерж», important →
  «желательно», nit → «не важно».
- **Two more headers, each with its own command.** A question to the author —
  `**[ai-review-bot]** · ❓ Вопрос`, posted with `post --question`; it claims nothing and
  stays open for the answer. A note for the author — `**[ai-review-bot]** · 💬 Заметка`, written
  by `finding.py fyi --location <path:line> --source <ticket | MR | path:line> --text "…"`:
  worth knowing, nothing to fix (merge order with a sibling MR, a ticket that contradicts the
  docs, debt outside this MR). It needs a source, stays under 240 characters, carries no verdict
  and no fix. `post-batch` posts the notes with the findings, but not as
  threads: all of them go into **one ordinary MR comment**, each under a link to its line. A
  thread fails either way — open, it holds the merge wherever the project requires every thread
  resolved, and nobody but the reviewer closes it; closed at posting, it is folded away before
  the author reads it. A plain comment stays on the Overview and holds nothing. `threads` lists
  it as `comment`: there is nothing to re-check or resolve.
- **The body is built by `finding.py render`, in this order:** the claim in one
  sentence → «Ломается при» with one scenario → «Что сделать» as up to three
  steps (a list when there is more than one) → the sibling / rule / assumption
  line → the command and its proving lines folded under
  `<details><summary>Как проверено</summary>`. The reader sees the problem and the
  fix first; the proof is one click away. Field lengths are capped at `add` —
  see *Language and Wording* in SKILL.md for what goes into `note` instead.
- **A подтверждено comment carries its evidence**: the command that was run and
  what it printed, or the exact `path/File.tsx:NN` of the sibling it is compared
  against. A предположение comment says in one sentence why the check could not
  be run. A comment with neither does not get posted at all.

### How to actually post them (GitLab) — use the script, not `glab api`

**`glab api -f "position[new_line]=171" ...` does not produce an inline comment.**
glab sends bracketed keys as flat form fields, GitLab never parses them into the nested
`position` object, and the API answers `201 Created` with an ordinary MR-level note. There
is no error to notice — the review just silently ends up as a pile of page-level comments
detached from the code. The same trap applies to `--input file.json`, which glab sends
without a content-type (`HTTP 415`). The position object must go as a JSON request body.

[`scripts/gitlab_comment.py`](../scripts/gitlab_comment.py) does exactly that, and **verifies
every post**: if the created note comes back as anything other than a `DiffNote` on the
requested line, it deletes the note it just made and exits non-zero. Never hand-roll the
request; if the script cannot be used, the fallback is `curl` with
`-H "Content-Type: application/json" --data @body.json`, followed by the same check.

**The gate holds at the moment of posting, too.** `post` and `post-batch` publish a comment
only if its body is exactly what `finding.py render` produced for a finding at that
location (`.review/` in the current directory, or `--dir`). An edited body, a comment
written by hand or a finding moved to another line is refused before the first request —
the fix is `finding.py add`, then posting its output unchanged. A question to the author
claims nothing and goes with `post --question`: its first line is exactly
`**[ai-review-bot]** · ❓ Вопрос` (no verdict — it claims nothing); one that carries a
verdict or a failure scenario is refused as a disguised finding. A `reply` must start with
`**[ai-review-bot]**` too — `threads` finds the re-review work by that tag. `resolve` is not gated.

```bash
S=<skill>/scripts/gitlab_comment.py   # <skill> — каталог SKILL.md (в Claude: ${CLAUDE_SKILL_DIR})
F=<skill>/scripts/finding.py

# all findings at once, straight from the gate
python3 $F render --json > /tmp/findings.json
python3 $S post-batch --mr group/project!69 --input /tmp/findings.json

# one finding (the body file holds its rendered comment)
python3 $S post --mr group/project!69 --file app/steps/decision.py --line 87 \
    --body-file /tmp/finding1.md

# a question to the author — no verdict, no failure scenario
python3 $S post --mr group/project!69 --file app/steps/decision.py --line 87 \
    --question --body-file /tmp/question.md

# the re-review work list, replies, resolve
python3 $S threads --mr group/project!69
python3 $S reply   --mr group/project!69 --thread <id> --body-file /tmp/reply.md
python3 $S resolve --mr group/project!69 --thread <id>
python3 $S delete  --mr group/project!69 --note <note_id>     # undo a bad post
```

`--line` is the line in the **new** file; for a line the PR removed, pass `--old-line`
instead (in `post-batch` input, add `"old_line": N` to that item). A "NOT inline" failure almost always means the chosen line is not part of the
diff — re-anchor the finding to a changed line rather than falling back to a page-level
comment. Auth reuses the `glab` token (`glab auth login --hostname <host>`), so no separate
login. The host is taken from `origin` of the repo under review; `GITLAB_HOST` or
`--host` override it.

**Verify before reporting done.** After posting, run `threads` once and confirm every
finding shows as `DiffNote` with a file and line (the notes for the author: one `comment` row). Reporting a review as posted when the
comments landed at page level is a false completion claim.

### Re-review after fixes (the loop)

The durable state of the review loop is the MR's own discussion threads, not local
files. Before re-reviewing after the author pushed fixes, list the existing
`[ai-review-bot]` threads — open threads are the work list; do not re-derive them.

- **Verify the fix at the anchored line first.** The same gate applies on the way
  out: a thread closes on evidence — re-run the check that produced the finding —
  never on the commit message or the author's "done".
- **Fixed and verified** — reply into the thread with what was checked and on which
  revision, then resolve the thread.
- **Not fixed, or fixed differently than needed** — reply with what is still missing
  and leave the thread open. Never resolve a thread whose problem is still in the code.
- **New commits move line numbers.** `finding.py render` warns when HEAD has moved
  since `init`, and `post` / `post-batch` refuse while the MR head differs from the commit
  the review ran on — GitLab anchors to the latest version, so the comment would land on
  code nobody checked. Re-verify each finding's `--location` against the current diff,
  then move the review: `finding.py rehead --why "<what was re-checked>"`.

## Too long and scannable

Too long (one finding carrying four):

> Описание закрывает PAY-12 словом Closes, а её runtime-часть по Block 6 не сделана: карточка
> по снимку Run и подпись события Failed (D-66). Сама PAY-12 говорит… **Что сделать:** заменить
> Closes на Relates to. Остаток можно делать уже сейчас на devmock: 1) … 2) … Уже на месте: … ,
> … , … . Отдельной истории запусков делать не нужно: … PAY-12 закрыть тем MR, который …

Scannable — the same finding; the rest went to `note`, the two missing UI parts became
two findings of their own:

```text
**[ai-review-bot]** · 📋 Требование · желательно · подтверждено

`Closes PAY-12` закроет задачу при мерже, хотя её вторая часть — переключение на API — не сделана.

**Ломается при:** мерж MR → GitLab закрывает PAY-12 → переключение на API остаётся без задачи.

**Что сделать:**
- заменить `Closes PAY-12` на `Relates to PAY-12`;
- закрыть PAY-12 тем MR, который переключит экран на API.

<details><summary>Как проверено</summary> … команда и 1–3 строки её вывода … </details>
```

## Plain forms

- **If a technical term is truly unavoidable, explain it in plain words in
  parentheses the first time it appears.** Examples of the plain form to use:
  - "plausible bug" → "возможная проблема — механизм реальный, но воспроизвести на конкретных данных пока не доказано"
  - "clamp the page number" → "ограничить номер страницы допустимым диапазоном (не больше числа страниц)"
  - "stale state" → "устаревшее значение, оставшееся в состоянии компонента"
  - "race condition" → "состояние гонки — два действия выполняются одновременно и мешают друг другу"
  - "off-by-one" → "ошибка на единицу в границах (например, цикл заходит на один шаг дальше нужного)"
