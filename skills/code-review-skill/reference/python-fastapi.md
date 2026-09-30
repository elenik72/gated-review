# FastAPI + Pydantic v2 Review Guide

> Грузить, если в зависимостях `fastapi` или `pydantic`. Базовая лестница и языковые формы — в
> [python.md](python.md). Сверено 2026-09-30: FastAPI 0.142.1, Pydantic 2.13.5, Starlette 1.x.

## Версии, от которых зависит правильный ответ

Сначала узнать версию из lock-файла — половина форм ниже зависит от неё:

```bash
grep -n -A1 -E '^name = "(fastapi|pydantic|starlette)"' uv.lock poetry.lock 2>/dev/null
```

| Версия FastAPI | Что поменялось (release notes) |
|---|---|
| 0.118.0 (2025-09-29) | код после `yield` в зависимости снова выполняется **после** отправки ответа |
| 0.121.0 (2025-11-03) | `Depends(..., scope="function" \| "request")`: `"function"` закрывает до отправки ответа |
| 0.126.0 / 0.128.0 (дек 2025) | Pydantic v1 не поддерживается; затем убран и `pydantic.v1` |
| 0.129.0 (2026-02-12) | нет Python 3.9 |
| 0.132.0 (2026-02-23) | `strict_content_type` по умолчанию: JSON без `Content-Type: application/json` отклоняется |
| 0.137.0 (2026-06-14) | `router.routes` — дерево, а не плоский список `APIRoute` |

Диф поднимает FastAPI через одну из этих границ — отдельная находка на строке lock-файла.

## Claim-формы

| Claim | The free check that could kill it | It dies when |
|---|---|---|
| `эндпоинт <path> блокирует event loop вызовом <x>` | (1) `git grep -n -B1 "def <handler>"` — `async def` или `def`; то же для каждой зависимости в `Depends`; (3) `PYTHONASYNCIODEBUG=1 pytest` | обработчик/зависимость — обычный `def`: FastAPI выполняет их в threadpool · [async](https://fastapi.tiangolo.com/async/#path-operation-functions) |
| `эндпоинт <path> отдаёт <поле> (хэш пароля, внутренний id)` | (1) есть ли `response_model=` или аннотация возврата моделью; (4) схема `app.openapi()` (команда ниже); (3) тест через TestClient на ключи ответа | выходная модель без поля: FastAPI фильтрует по ней, `response_model` приоритетнее аннотации. Не умирает, если аннотация `dict`/`Any` или возвращается `Response`/`JSONResponse` напрямую — фильтрации нет · [response-model](https://fastapi.tiangolo.com/tutorial/response-model/#return-type-and-data-filtering), [response-directly](https://fastapi.tiangolo.com/advanced/response-directly/) |
| `ошибка, пойманная в зависимости с yield, пропадает без следа` | (1) прочитать `except` вокруг `yield` | в `except` есть `raise` (или новое исключение) — документация требует именно этого · [yield+except](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#always-raise-in-dependencies-with-yield-and-except) |
| `ресурс из зависимости с yield (сессия, соединение) держится до конца отправки ответа` | (1) версия FastAPI; `scope=` у `Depends`; ответ стриминговый? | `Depends(scope="function")` (≥0.121) или ответ не стриминговый и короткий — тогда это не находка · [scope](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope) |
| `зависимость <dep> выполняется несколько раз за запрос` | (1) один ли это callable в дереве `Depends` | тот же callable: FastAPI кэширует результат на запрос, пока нет `use_cache=False` · [sub-dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/) |
| `параметр пути <p> не попадает в обработчик` | (2) `ruff --select FAST003` | параметр есть в сигнатуре или берётся зависимостью |
| `поле <x>: Optional[T] стало обязательным → клиенты без него получат 422` | (4) `python -c "from app.schemas import M; print({n: f.is_required() for n, f in M.model_fields.items()})"` | у поля есть `= None` · [migration](https://pydantic.dev/docs/validation/latest/get-started/migration/#required-optional-and-nullable-fields) |
| `поля подкласса <Sub> не попадут в ответ (или попадут лишние)` | (4) `Out(user=Sub(...)).model_dump()` — проверено на 2.13.5: остаются только поля аннотированного типа | поле аннотировано конкретным подклассом или `SerializeAsAny[...]` · [serialization](https://pydantic.dev/docs/validation/latest/concepts/serialization/#subclass-instances-for-fields-of-basemodel-dataclasses-typeddict) |
| `число в поле str теперь даёт 422` | (4) `M.model_validate({"code": 123})` | `model_config = ConfigDict(coerce_numbers_to_str=True)` · [migration](https://pydantic.dev/docs/validation/latest/get-started/migration/) |
| `остался API Pydantic v1 (.dict(), @validator, class Config, orm_mode, parse_obj)` | (3) `pytest -W error::pydantic.warnings.PydanticDeprecatedSince20 tests/<area>` | предупреждений нет. Само по себе 🟢 (работает с DeprecationWarning); 🟡/🔴, если импортируется `pydantic.v1`, а FastAPI ≥0.128 · [validators](https://pydantic.dev/docs/validation/latest/get-started/migration/#changes-to-validators) |
| `после апгрейда FastAPI клиенты без Content-Type получают отказ` | (1) версия в lock до/после; `git grep -n strict_content_type` | `strict_content_type=False`, или клиенты шлют заголовок (свой фронт/SDK) · [strict content-type](https://fastapi.tiangolo.com/advanced/strict-content-type/) |
| `код, обходящий router.routes, после 0.137 теряет маршруты` | (1) `git grep -n -E "\.routes\b" -- '*.py'` | обхода нет, или он через публичный API (`app.openapi()`) |

## Команды

```bash
git grep -n -E "^\s*async def " -- app/api app/routers          # что выполняется прямо на event loop
xargs uv run --frozen ruff check --select FAST,ASYNC --output-format concise < .review/py.txt
uv run --frozen python -c "import json; from app.main import app; \
  print(json.dumps(app.openapi()['paths']['/users/{user_id}']['get']['responses']['200'], indent=1))"
uv run --frozen pytest -q -p no:cacheprovider -W error::pydantic.warnings.PydanticDeprecatedSince20 tests/<area>
PYTHONASYNCIODEBUG=1 uv run --frozen uvicorn app.main:app --port 8001   # rung 5: медленные колбэки в логе под нагрузкой curl
```

Сессия БД в зависимости с `yield` — см. формы про `scope=` выше; одна `AsyncSession` на несколько
задач `asyncio.gather` — это гонка на одном соединении: общий случай в
[async-concurrency-patterns](cross-cutting/async-concurrency-patterns.md).
