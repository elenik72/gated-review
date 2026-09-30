# gated-review — code review, в котором замечание сначала пытаются опровергнуть

Скилл для Claude Code и Codex. Находка становится комментарием в MR, только если дешёвая проверка,
которая могла её убить (grep, тип-чекер, тест, правило репо, названный сосед), её не убила. Сила
доказательства ограничивает серьёзность: 🔴 не ставится на прочитанный дифф.

## Режимы и стеки

Режим выбирается аргументом или в начале ревью (Claude спросит одним вопросом, Codex — сообщением):

| Режим | Что проверяет | Особенности |
|---|---|---|
| `business` | реализованы ли требования тикета и верна ли бизнес-логика | требования цитируются (`finding.py req`), у каждого статус с доказательством, уровень соответствия считает скрипт; без тикета `render` откажет; nit в MR — 0 |
| `design` | стайлгайд, архитектура и дизайн кода **по правилам самого репо** | форма `rule` цитирует строку правила (`--rule AGENTS.md:12-14`), контракты слоёв (import-linter, dependency-cruiser), лимит nit — 5 |
| `security` | инъекции, доступ, секреты, небезопасные API | nit в MR — 0 |
| `full` | всё вместе | по умолчанию |

Стек определяется по изменённым файлам и ближайшему манифесту (`package.json`, `pyproject.toml`):
`ts-react` (React 19, Vite SPA), `node-nestjs`, `typescript`, `python-fastapi`, `python`. План ревью
печатает, какие справочники читать и какие команды у этого репо на каждой ступени (pnpm/yarn/npm,
uv/poetry; только инструменты, которые в репо уже есть).

## Установка локально

Скилл — каталог `skills/code-review-skill/`. Его можно подключить симлинком (так сейчас) или
плагином из этого репозитория как локального маркетплейса.

```bash
# Claude Code и Codex — симлинком (без плагина)
ln -sfn "$PWD/skills/code-review-skill" ~/.claude/skills/code-review-skill
ln -sfn "$PWD/skills/code-review-skill" ~/.codex/skills/code-review-skill
```

```bash
# Claude Code — плагином (тогда симлинк из ~/.claude/skills убрать, иначе скилл загрузится дважды)
claude plugin marketplace add ~/Projects/skills/gated-review
claude plugin install gated-review@review-tools
```

Codex читает этот же `.claude-plugin/marketplace.json`: `codex plugin marketplace add <путь или git-URL>`,
затем `/plugins`. Требования: `python3` ≥ 3.9 (скрипты только на stdlib), `git`, для постинга в GitLab —
`glab` с логином (`glab auth login --hostname <host>`).

## Запуск

```text
/code-review-skill business !482          # или: /gated-review:code-review-skill … при установке плагином
проведи ревью MR !482 по тикету PAY-42     # обычной фразой — скилл сработает сам и спросит режим
```

Внутри скилл ведёт состояние в `.review/` репозитория под ревью (в git не коммитится):

```bash
S=skills/code-review-skill/scripts
python3 $S/finding.py init --target origin/main --pr "!482" --mode business --stack auto   # печатает план
python3 $S/finding.py req --add "повторный возврат с тем же refund_id не создаёт второй" --source PAY-42
python3 $S/finding.py add --form breaks --severity blocking --rung 3 --claim … --breaks-when "… -> …" \
  --location src/a.ts:12 --evidence "pnpm exec vitest related --run src/a.ts" --output "1 failed"
python3 $S/finding.py render --json > /tmp/findings.json
python3 $S/gitlab_comment.py post-batch --mr group/project!482 --input /tmp/findings.json
```

`gitlab_comment.py` публикует только то, что прошло гейт, побайтно; хост — `GITLAB_HOST` или `--host`.

## Проверки

```bash
cd skills/code-review-skill/scripts && python3 -m unittest test_finding test_gitlab_comment test_pr_analyzer test_review_plan
claude plugin validate --strict .
# evals: три кейса (подложенный баг, чистый MR без блокеров, невыполненное требование тикета)
claude plugin eval . --scaffold --allow-tools "Bash(git *)" "Bash(python3 *)" --threshold 0.8 --no-publish
```

Evals вызывают модель (каждый кейс — прогоны с плагином и без), это стоит денег; `--max-cost-usd 0`
только проверяет, что кейсы загружаются.

## Перед публикацией на GitHub

- [ ] Хост GitLab по умолчанию: `skills/code-review-skill/scripts/gitlab_comment.py` (`DEFAULT_HOST`) и
      `reference/posting.md` — заменить внутренний хост на `gitlab.com` или требовать `GITLAB_HOST`.
- [ ] `author` в `.claude-plugin/plugin.json` и `owner` в `marketplace.json` — какие имя и почту показывать.
- [ ] Ключи тикетов в примерах (`SPH-…`) — внутренние, но безвредны; заменить при желании.
- [ ] Язык: комментарии и справочники в основном на русском, часть исходных справочников — на китайском
      (наследие awesome-skills/code-review-skill).
- [ ] Прогнать evals с `--threshold` и приложить отчёт.

## Структура

```text
.claude-plugin/{plugin.json,marketplace.json}   манифесты — их читают и Claude Code, и Codex
skills/code-review-skill/
  SKILL.md                    процесс и гейт; начинается с выбора режима и стека
  agents/openai.yaml          для Codex
  reference/                  справочники по режимам, стекам и сквозным темам (грузятся по плану)
  assets/                     шаблоны сводки и заметок
  scripts/finding.py          гейт находок, требования тикета, заметки, рендер
  scripts/review_plan.py      реестр режимов × стеков: что читать и что запускать
  scripts/gitlab_comment.py   inline-комментарии в GitLab только для прошедших гейт находок
  scripts/pr-analyzer.py      размер и порядок чтения PR
  scripts/test_*.py           тесты (stdlib unittest, без сети)
evals/                        кейсы для claude plugin eval
```

Лицензия — MIT (см. `LICENSE`); основано на awesome-skills/code-review-skill.
