# Python Code Review Guide

> Язык: Python 3.10–3.14 (3.14.7 — текущий стабильный; 3.15.0 выходит 2026-10-01, PEP 790).
> Инструменты сверены 2026-09-30: ruff 0.16.9, mypy 2.3.1, pyright 1.1.414, bandit 1.9.4,
> semgrep 1.178.0, pip-audit 2.10.1, uv 0.12.21, deptry 0.25.1, vulture 2.16,
> import-linter 2.15, pytest 9.1.1, diff-cover 10.6.0.
> Фреймворк — отдельный файл, грузить только если он есть в стеке: [FastAPI + Pydantic](python-fastapi.md).
> Какие файлы грузить и какие команды у этого репо, печатает `finding.py init` (план ревью).
> Общие темы не повторяются: [async](cross-cutting/async-concurrency-patterns.md),
> [ошибки](cross-cutting/error-handling-principles.md), [N+1](cross-cutting/n-plus-one-queries.md),
> [SQLi](cross-cutting/sql-injection-prevention.md), [XSS](cross-cutting/xss-prevention.md),
> [command injection / SSRF / IDOR](security-review-guide.md).

---

## 1. Phase 0 для Python — какой стек и какие проверки у репо уже есть

```bash
# git ls-files вместо ls с глобами: в zsh несовпавший глоб роняет всю команду
git ls-files | grep -E '(^|/)(pyproject\.toml|setup\.cfg|tox\.ini|noxfile\.py|Makefile|\.gitlab-ci\.yml|\.pre-commit-config\.yaml|ruff\.toml|\.ruff\.toml|mypy\.ini|\.mypy\.ini|pyrightconfig\.json|\.importlinter|\.bandit|uv\.lock|poetry\.lock|pdm\.lock|pylock\..*toml|requirements.*\.txt)$'
grep -nE '^\[tool\.(ruff|mypy|pyright|basedpyright|ty|bandit|importlinter|deptry|vulture|pytest|coverage|django-stubs)' pyproject.toml
grep -nE 'ruff|mypy|pyright|bandit|semgrep|lint-imports|deptry|vulture|pip-audit|uv audit|xenon|radon|pytest|diff-cover|makemigrations' \
   .gitlab-ci.yml .pre-commit-config.yaml Makefile tox.ini noxfile.py 2>/dev/null
git grep -n -w -i -E 'fastapi|pydantic' -- pyproject.toml 'requirements*.txt'   # грузить ли python-fastapi.md
```

Правила:

- **Источник правды — то, что гоняет CI** (`.gitlab-ci.yml`, `make lint`, pre-commit). Нарушение
  правила, включённого в конфиге репо, — факт, его можно постить как есть.
- **Всё остальное — зонд.** `ruff --select B023` в репо, где `B` не включён, — это способ
  проверить механизм бага, а не «нарушение стандарта». В комментарии пишется баг и его сценарий,
  не «ruff ругается». Если правило стоит в `ignore` конфига — команда его сознательно выключила;
  стилевую находку по нему не постить. Проверено: CLI `--select` перекрывает `ignore` из конфига,
  но `per-file-ignores` продолжают действовать.
- **Раннер по lock-файлу:** `uv.lock` → `uv run --frozen`, `poetry.lock` → `poetry run`,
  `pdm.lock` → `pdm run`, иначе `.venv/bin/python -m`. Ниже везде `uv run --frozen` — заменить.
  Инструмента нет в окружении — `uvx <tool>@<версия из rev: в pre-commit>`: правила меняются
  между версиями.
- **pre-commit — самый дешёвый «весь rung 2 репо разом»:** `pre-commit run --files <файлы>`.
  Хуки с `--fix`/форматтеры правят файлы — запускать только в чистом worktree ревью, правки
  не коммитить (их наличие — уже доказательство «форматтер не прогнан»).

Список изменённых файлов `.review/py.txt` пишет `finding.py init --target origin/<target>`.
Без него — вручную:

```bash
T=origin/<target>; mkdir -p .review
git diff --name-only --diff-filter=d "$T"...HEAD -- '*.py' > .review/py.txt
```

## 2. Evidence Ladder для Python

| Rung | Команды (scoped на изменённое) | Что может убить | Чего НЕ убивает |
|---|---|---|---|
| 0 | читать диф | — | — (🟢 максимум) |
| 1 | `git grep -n -w <name>`; соседние файлы; `vulture` как подсказка | «никто не вызывает», «вход не бывает None», «так не делают соседи» | динамику: `getattr`, строки-пути (`mock.patch("a.b")`, Celery-имена задач, `INSTALLED_APPS`, entry points) — грепать и их |
| 2 | ruff, mypy/pyright, bandit/semgrep, lint-imports, deptry, pip-audit, `makemigrations --check` | синтаксические шаблоны (B023, ASYNC*, DTZ*), типовые утверждения, нарушение контракта слоёв | тело **неаннотированной** функции (mypy его не проверяет без `check_untyped_defs`), всё, что течёт через `Any` |
| 3 | существующие тесты на путь, с asyncio debug; diff-cover | «ломается при X» — если тест на X есть и зелёный | путь, который ни один тест не исполняет (diff-cover это покажет) |
| 4 | свой падающий тест / однострочный repro | почти всё; N+1 и гонки — счётчиком запросов | прод-данные и конфиг, которых нет локально |
| 5 | поднять приложение (uvicorn / runserver / worker) + curl | интеграцию, middleware, реальный event loop | — |

```bash
# rung 1 — вызовы и соседи (слово целиком, чтобы поймать строки и декораторы)
git grep -n -w "<name>" -- '*.py' '*.toml' '*.cfg' '*.ini' '*.yaml' '*.html'
xargs uv run --frozen vulture --min-confidence 80 < .review/py.txt   # только подсказка: каждую находку добить git grep

# rung 2 — конфиг репо, потом зонды
xargs uv run --frozen ruff check --output-format concise < .review/py.txt
xargs uv run --frozen ruff check --output-format concise \
  --extend-select B,ASYNC,DTZ,S,BLE,TRY,RUF006,RUF012,PGH,FAST,DJ < .review/py.txt
xargs uv run --frozen ruff check --preview --select B909,PLE1141,RUF029 < .review/py.txt   # preview-only правила
xargs uv run --frozen mypy < .review/py.txt 2>&1 | grep -F -f .review/py.txt              # mypy идёт по импортам — оставить свои файлы
xargs uv run --frozen mypy --warn-unused-ignores --warn-redundant-casts \
  --enable-error-code ignore-without-code,possibly-undefined,unused-awaitable < .review/py.txt 2>&1 | grep -F -f .review/py.txt
xargs uv run --frozen pyright < .review/py.txt          # проверяет и неаннотированные тела; reportUnusedExcept/UnusedCoroutine = error по умолчанию
xargs uv run --frozen bandit -q -c pyproject.toml < .review/py.txt   # только если есть [tool.bandit]; иначе ruff S покрывает те же проверки
semgrep scan --config p/python --metrics=off --error --baseline-commit "$(git merge-base "$T" HEAD)"  # только новые находки; нужен чистый tree
uv run --frozen lint-imports                            # весь граф; --contract <id> для затронутого
uv run --frozen deptry .                                # DEP001 нет в зависимостях · DEP002 лишняя · DEP003 транзитивная · DEP004 dev в проде
xargs uv run --frozen ruff check --select C901,PLR0912,PLR0915 < .review/py.txt   # сложность; radon/xenon — только если они в CI

# зависимости — только если диф трогает pyproject.toml / *.lock / requirements*
uv audit                                                # uv ≥ 0.12
uvx pip-audit -r requirements.txt                       # pip
uvx pip-audit --locked .                                # pylock.*.toml (PEP 751)

# rung 3 — какие тесты держат путь, и прогнать только их
git grep -l -w "<changed_func>" -- 'tests/' '*test*.py'
uv run --frozen pytest --co -q -k "<name>"              # 0 collected → тестов нет, rung 3 недоступен
uv run --frozen pytest -x -q -p no:cacheprovider tests/<area>/test_x.py -k "<name>"
PYTHONASYNCIODEBUG=1 uv run --frozen pytest -q -p no:cacheprovider tests/<area> --log-cli-level=WARNING 2>&1 \
  | grep -E "took [0-9.]+ seconds|never awaited"        # блокировка event loop > 100 мс и забытые await
uv run --frozen pytest -q --cov=<pkg> --cov-report=xml tests/<area> \
  && uv run --frozen diff-cover coverage.xml --compare-branch="$T" --show-uncovered   # изменённые строки, которые ни один тест не исполнил

# rung 4 — repro: файл в tests/ worktree ревью (чтобы подхватился conftest), не коммитить, удалить после
uv run --frozen pytest -q -p no:cacheprovider tests/test__review_probe.py
```

Проверено на песочнице: `pytest` печатает `RuntimeWarning: coroutine '…' was never awaited`, но
тест зелёный; чтобы он упал — `-W error::RuntimeWarning -W error::pytest.PytestUnraisableExceptionWarning`.
`PYTHONASYNCIODEBUG=1` (или `python -X dev`) логирует `Executing <Task …> took 0.2 seconds`.

Грейд по инструменту: pip-audit/semgrep/bandit-хит — rung 2 (🟡). 🔴 — только если показан путь:
уязвимая функция/вход достижимы (rung 1) и есть тест или repro (rung 3–4).

## 3. Claim-формы для Python

Номер в скобках — rung, на котором живёт проверка.

| Claim | The free check that could kill it | It dies when |
|---|---|---|
| `изменяемый default <арг> в <func> копит состояние между вызовами` | (2) `ruff --select B006,B008,RUF009`; (1) прочитать, мутирует ли функция аргумент, и `git grep` вызовы без него | аргумент только читается; это поле Pydantic (default копируется на каждый экземпляр) или dataclass (упадёт `ValueError` при импорте) · [tutorial](https://docs.python.org/3/tutorial/controlflow.html#default-argument-values), [pydantic](https://pydantic.dev/docs/validation/latest/concepts/fields/#mutable-default-values) |
| `замыкание в цикле берёт последнее значение <var>` | (2) `ruff --select B023` | замыкание вызывается в той же итерации (`sorted(key=…)`, сразу), или значение связано через `lambda x=x` / `functools.partial` · [FAQ](https://docs.python.org/3/faq/programming.html#why-do-lambdas-defined-in-a-loop-with-different-values-all-return-the-same-result) |
| `<вызов> блокирует event loop в async def <f>` | (2) `ruff --select ASYNC210,ASYNC212,ASYNC22,ASYNC230,ASYNC240,ASYNC251,S113`; (1) грепнуть синхронные драйверы (`requests`, `psycopg2`, `pymysql`, sync `Session`, `boto3`) — ruff их не знает; (3) `PYTHONASYNCIODEBUG=1 pytest` → `took … seconds` | функция — обычный `def` (FastAPI/Starlette гонят её в threadpool), вызов обёрнут в `await asyncio.to_thread` / `run_in_threadpool` / `sync_to_async` · [asyncio-dev](https://docs.python.org/3/library/asyncio-dev.html#running-blocking-code) |
| `пропущен await у <coro> → код не выполняется` | (2) mypy `unused-coroutine`, `truthy-function` (`if fetch:`); pyright `reportUnusedCoroutine`; (3) `pytest` → `never awaited` | корутина сохранена и дожидается позже (`create_task`, `gather`, возврат из функции) · [asyncio-dev](https://docs.python.org/3/library/asyncio-dev.html#detect-never-awaited-coroutines) |
| `фоновая задача <create_task> может пропасть / её ошибка теряется` | (2) `ruff --select RUF006`; (1) прочитать `gather(...)`: `return_exceptions`, разбор результатов | ссылка хранится (set + `add_done_callback(discard)`), используется `TaskGroup` (3.11+, отменяет остальные и поднимает `ExceptionGroup`), результаты `gather(return_exceptions=True)` проверяются на исключения · [create_task](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task), [gather](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather) |
| `except <X> глушит ошибку <какую>, наверх уходит "успех"` | (2) `ruff --select BLE001,S110,S112,E722,B012,TRY203`; (1) прочитать обработчик | есть `raise` / `raise … from`; это граница изоляции (воркер, middleware) и лог с трейсбеком (`logger.exception`); тип узкий. `return` в `finally` глушит всегда — на 3.14 это SyntaxWarning (PEP 765) · [Google 2.4](https://google.github.io/styleguide/pyguide.html#s2.4-exceptions), [PEP 765](https://peps.python.org/pep-0765/) |
| `ветка except <Sub> недостижима — её ловит except <Base> выше` | (2) `pyright <file>` → `reportUnusedExcept` (error по умолчанию); `ruff --select B014,B025` | классы не в отношении наследования (`python -c "print(issubclass(Sub, Base))"`) · [tutorial](https://docs.python.org/3/tutorial/errors.html#handling-exceptions) |
| `изменение <dict/list> во время обхода → RuntimeError / пропуск элементов` | (2) `ruff --preview --select B909,PLE1141`, `B020`; (4) repro в одну строку | обход идёт по копии (`list(d)`, `d.copy()`, `[:]`) или меняются только значения существующих ключей · [stdtypes](https://docs.python.org/3/library/stdtypes.html#dictionary-view-objects) |
| `is вместо == для <значение>` | (2) `ruff --select F632,E711,E712` | сравнение с синглтоном (`None`, `True/False`, член Enum, sentinel-объект) — там `is` правильный · [FAQ](https://docs.python.org/3/faq/programming.html#when-can-i-rely-on-identity-tests-with-the-is-operator) |
| `naive datetime в <поле> → сдвиг на часовой пояс / TypeError при сравнении` | (2) `ruff --select DTZ`; (1) `USE_TZ`, тип колонки `DateTime(timezone=True)`; (3) Django: `pytest -W error::RuntimeWarning` (`received a naive datetime`) | значение идёт через `django.utils.timezone.now()` / `datetime.now(UTC)`, колонка aware, или это только локальное отображение · [datetime](https://docs.python.org/3/library/datetime.html) (`utcnow()` deprecated с 3.12) |
| `деньги в float в <поле> → копейки теряются` | (1) тип по всей цепочке: модель (`DecimalField`/`Numeric`), схема, JSON; (2) `ruff --select RUF032`; (4) repro | это не деньги (счётчик, доля), или `Decimal` от модели до ответа, округление через `quantize` · [decimal](https://docs.python.org/3/library/decimal.html#floating-point-notes) |
| `в лог уходит <секрет/PII> в <строка>` | (1) grep логгер-вызовов с секретными именами (команда под таблицей); конфиг логирования: `logging.Filter`, structlog-процессоры, Sentry `before_send`/`send_default_pii` | значение маскируется выше по цепочке или поле не секретное · [OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) |
| `команда собирается из <вход> и уходит в shell` | (2) `ruff --select S602,S604,S605,S607`; (1) довести аргумент до источника | аргументы константы или список без `shell=True` · [subprocess](https://docs.python.org/3/library/subprocess.html#security-considerations); подробно — security guide |
| `pickle/yaml.load/eval на данных из <источник>` | (2) `ruff --select S301,S506,S307,S102`; (1) откуда байты | `yaml.safe_load` / `Loader=SafeLoader`; данные только свои и подписаны · [pickle](https://docs.python.org/3/library/pickle.html) |
| `путь из <запроса> выходит за <base>` | (1) найти `open`/`Path(base) / x`/`os.path.join`/`FileResponse`; (2) `ruff --select S202` для tar; (4) repro с `../` и `/etc/passwd` | путь резолвится и проверяется `resolved.is_relative_to(base)`, имя из allowlist; tar на 3.14 распаковывается с фильтром `data` по умолчанию. `os.path.join(base, "/abs")` отбрасывает `base` · [os.path.join](https://docs.python.org/3/library/os.path.html#os.path.join), [tarfile](https://docs.python.org/3/library/tarfile.html#extraction-filters) |
| `cast / Any / # type: ignore прячет реальную ошибку в <строка>` | (2) `mypy --warn-unused-ignores --warn-redundant-casts --enable-error-code ignore-without-code`; `ruff --select PGH003,ANN401`; (2) убрать ignore/cast локально и перезапустить mypy на файл | без ignore ошибки нет (тогда ignore просто лишний — 🟢), или тип гарантирован проверкой выше (`isinstance`) и у ignore есть код и причина · [mypy codes](https://mypy.readthedocs.io/en/stable/error_code_list2.html) |

```bash
# секреты в логах (в таблице не помещается из-за | в регулярке)
git grep -n -E "log(ger)?\.[a-z_]+\(.*(password|token|secret|authorization|api_key)" -- '*.py'
```

Формы FastAPI и Pydantic — в [python-fastapi.md](python-fastapi.md).

## 4. Стиль, типы, докстринги — что руками, что инструментом

**Не комментировать руками** (это работа ruff/`ruff format`/black по конфигу репо): длина строки,
импорты, кавычки, PEP 8-пробелы, нейминг (N8xx), `X | None` вместо `Optional` (UP007 по
`requires-python`), f-строки в логах (G004). Если правило не включено — это не находка.

**Руками — только то, что инструмент не видит:**

- **PEP 8 «A Foolish Consistency»**: согласованность с модулем важнее руководства → это
  `расходится с <файл:строка>`, а не цитата из PEP 8. Публичный/внутренний API: новый
  публичный символ без `_` и без упоминания в `__all__` там, где соседи его ведут.
- **Google Style Guide** (цитировать с номером раздела): 2.4 — не ловить `Exception` кроме
  точки изоляции с re-raise/логом; 2.5 — избегать изменяемого глобального состояния; 2.12 —
  изменяемые default; 2.14 — `if x is None`, а не `if not x`, когда `0`/`""` валидны
  (ruff этого не отличит — это логика); 2.19 — «power features» (метаклассы, `__del__`,
  динамическое наследование) без нужды; 3.18 — функция > ~40 строк повод подумать, не правило.
- **Типы (PEP 484/604/695/698/742):** политика — строгость репо, не наша. Проверка: конфиг
  `[tool.mypy]` + per-module overrides. Требовать аннотации на новых/изменённых публичных
  функциях можно, если так делают соседи или конфиг (`disallow_untyped_defs`); Google 2.21
  советует аннотировать публичные API. Синтаксис новее `requires-python` — не мнение, а
  ошибка импорта: ruff сам выводит target из `requires-python` и пишет
  `Cannot use type parameter lists on Python 3.11` (проверено).
  `# type: ignore` без кода и `cast` без комментария «почему гарантировано» — 🟢/🟡 по вреду.
- **Докстринги (PEP 257, Google 3.8):** формат — ruff `D` с `convention` репо. Руками —
  только правда: `Raises:` совпадает с тем, что функция реально бросает (зонд:
  `ruff --preview --select DOC501,DOC502`), `Returns:` совпадает с типом.

## 5. Архитектура: слои и направление зависимостей

Слои типично: `api/routers` → `services` → `repositories` → `models/domain`. Нижний слой не
импортирует верхний; домен не импортирует фреймворк.

- **Есть import-linter** (`[tool.importlinter]` / `.importlinter`) → `lint-imports` — rung 2,
  сломанный контракт = факт. Типы контрактов 2.15: `layers`, `forbidden`, `independence`,
  `protected`, `acyclic_siblings`. Диф меняет сам контракт или добавляет `ignore_imports` —
  отдельная находка: правило ослабили молча.
- **Контракта нет** → не выдумывать его. Зонд — grep по направлению:

  ```bash
  git grep -n -E "^\s*(from|import) app\.(api|routers)" -- app/services app/repositories   # низ импортирует верх
  git grep -n -E "^\s*(from|import) (fastapi|django|sqlalchemy)" -- app/domain            # домен знает фреймворк
  ```

  Хит — это `расходится с соседями`, и он обязан назвать соседей.
- Предложить контракт можно (📚/💡), как одну вставку в pyproject:

  ```toml
  [tool.importlinter]
  root_package = "app"

  [[tool.importlinter.contracts]]
  id = "layers"
  name = "api -> services -> repositories -> models"
  type = "layers"
  layers = ["app.api", "app.services", "app.repositories", "app.models"]
  ```

**Как формулировать «расходится с соседями»** (форма `расходится с <файл:строка>`):

> Расходится с `app/services/orders.py:41` и `app/services/users.py:37`: там репозиторий
> приходит через конструктор, здесь `payments.py:12` создаёт `Session()` сам. Когда для
> `payments` понадобится тест без базы или вторая транзакция в одном запросе, сессию будет
> не подменить.

Чем умирает: соседи сами делают по-разному (конвенции нет → вопрос автору или дроп); сосед
устарел (`git log -1 --format=%cs -- <сосед>` старше, а третий, свежий, делает как новый код).
Грейд по умолчанию 🟢, 🟡 — если второй вызов уже назван в тикете (см. SKILL.md → Severity).
