# React SPA — checks that decide a finding (React 19, Vite)

> Сверено 2026-09-30: React 19.3, React Compiler 1.0, eslint-plugin-react-hooks 7.1, TypeScript 6/7,
> ESLint 10, Vitest 5, knip 6, dependency-cruiser 18, size-limit 14. Основы хуков — в [react.md](react.md),
> TanStack Query и Actions — в [react-modern-stack.md](react-modern-stack.md) (план грузит его, если
> `@tanstack/react-query` в зависимостях). Команды этого репо печатает `finding.py init`.

## 1. Сначала — что меняет правильный ответ

Открыть `package.json` пакета и конфиг сборки до первой находки:

- **React Compiler включён** (`babel-plugin-react-compiler` в зависимостях, `reactCompiler` в
  конфиге Vite-плагина): новый `useMemo`/`useCallback` нужен только как запасной выход, отсутствие
  мемоизации — не находка. Существующие вызовы не удалять без тестов; смотреть `'use no memo'` и
  правило `react-hooks/incompatible-library`. [Compiler 1.0](https://react.dev/blog/2025/10/07/react-compiler-1)
- **react-hooks ≥ 7**: правила React (чистота рендера, неизменяемость props/state, `ref.current` не
  читается в рендере, `setState` не вызывается в рендере или синхронно в эффекте) — это правила
  линтера `purity`, `refs`, `immutability`, `set-state-in-render`, `set-state-in-effect`.
  [Rules of React](https://react.dev/reference/rules)
- **React 19**: `ref` — обычный prop (`forwardRef` не нужен), `<Context value>` вместо `.Provider`,
  у ref-callback есть cleanup (неявный `return` — ошибка TS), у функций нет `propTypes`/`defaultProps`,
  `act` импортируется из `react`. **19.2**: `useEffectEvent` для нереактивных чтений в эффекте,
  `<Activity>` — скрытое дерево хранит state, но его эффекты сняты.
- **TypeScript 7** нативный: типизированные правила typescript-eslint требуют TS 6 рядом
  (алиас `@typescript/typescript6`); `baseUrl` удалён, `paths` считаются от tsconfig.
  [TS 7.0](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)

## 2. Лестница — команды

`X` = `pnpm exec` / `yarn` / `bunx` / `npx --no` по lockfile (план `finding.py init` подставит).
Для проверки утверждения — инструмент напрямую с конфигом репо по изменённым файлам; скрипт репо
(`pnpm lint`) — последним, как в CI. Ошибка **новая**, только если её нет на целевой ветке:
тот же прогон в `git worktree add ../base origin/<target>`.

| Rung | Команда | Что убивает |
|---|---|---|
| 1 | `git grep -n "<Comp\b"`, `git grep -n "useThing("` по потребителям; ближайший `ErrorBoundary` вверх по дереву | «никто не использует», «ошибка роняет экран» |
| 2 | `X tsc --noEmit -p <pkg>/tsconfig.json --pretty false \| grep -F -f .review/js.txt` — **весь проект**, фильтр по своим файлам: `tsc <files>` игнорирует tsconfig | типовые утверждения |
| 2 | `xargs X eslint --max-warnings=0 --no-warn-ignored < .review/js.txt`; включено ли правило — `X eslint --print-config <file> \| jq '.rules["react-hooks/refs"]'` | правила React, хуки, a11y, typed-правила |
| 2 | `X knip --reporter compact`; `X knip --trace-file <f> --trace-export <name>` | «экспорт/зависимость больше не нужны» |
| 2 | `X depcruise src -T err-long --affected origin/<target>`; без правил в репо — только `X madge --circular --extensions ts,tsx src` | границы модулей, циклы |
| 2 | `X vite build`; `X size-limit --json` на base и head, `--why` | размер бандла |
| 3 | `xargs X vitest related --run < .review/js.txt` (без `--run` останется в watch); Jest — `--findRelatedTests` | существующие юнит-тесты |
| 3 | `X playwright test --only-changed=origin/<target>` — только изменённые spec; для исходников spec найти grep'ом и запустить `file:line` | e2e на пути |
| 4 | временный тест в worktree ревьюера; a11y — `new AxeBuilder({ page }).include('<sel>').withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa'])` | воспроизведение |
| 5 | `X vite` + страница: предупреждения в консоли (`optimistic state update occurred outside…`) | поведение в браузере |

Правило, выключенное в конфиге репо, — не находка по стилю: команда так решила. Ставить плагин в
репо ради проверки нельзя: `--rule` работает только для подключённого плагина.

## 3. Формы утверждений

| Claim | The free check that could kill it | It dies when |
|---|---|---|
| `нарушено правило React: <мутация props/state, ref.current в рендере, setState в рендере/эффекте>` | (2) `eslint <file>` на react-hooks ≥ 7; `--print-config` — правило включено | линт чистый на конфиге репо, или у файла осознанный `'use no memo'` · [Rules of React](https://react.dev/reference/rules) |
| `эффект/колбэк читает устаревшее <значение>` | (2) `eslint --rule '{"react-hooks/exhaustive-deps":"error"}' <file>` | это ref, сеттер состояния или `useEffectEvent` · [useEffectEvent](https://react.dev/reference/react/useEffectEvent) |
| `после <мутации> видны старые данные` | (1) в мутации `invalidateQueries` / `setQueryData`; ключ совпадает со стороной чтения: `git grep -n "queryKey: \['<key>'"` | ключ совпадает, или данные не кэшируются · [TanStack invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation) |
| `queryKey <…> не включает <параметр> → данные другого фильтра/пользователя` | (2) `eslint --rule '{"@tanstack/query/exhaustive-deps":"error"}' <file>`; сравнить переменные `queryFn` с фабрикой ключа | параметр не меняется за жизнь компонента или его включает `queryOptions`-фабрика · [плагин](https://tanstack.com/query/latest/docs/eslint/eslint-plugin-query) |
| `оптимистичное значение <X> мигает и откатывается` | (1) сеттер `useOptimistic` вызывается внутри `startTransition` / `action`? (5) предупреждение в консоли | вызов внутри Action · [useOptimistic](https://react.dev/reference/react/useOptimistic) |
| `ошибка в <компоненте> роняет весь экран` | (1) ближайший boundary вверх: `git grep -n "ErrorBoundary"`; для `useSuspenseQuery`/`use()` boundary нужен выше `<Suspense>` | boundary есть у сегмента или родителя. Помнить: boundary не ловит ошибки обработчиков и асинхронного кода |
| `<элемент> без доступного имени / не работает с клавиатуры` | (2) eslint jsx-a11y (компоненты кита сопоставлены тегам в `settings['jsx-a11y'].components`?); (3) `getByRole('<role>', { name })` в тесте; (4) axe | компонент кита рендерит нативный `<button>`/`<a href>`/`<label>` (открыть исходник) или имя передают все места вызова · [WCAG 2.2](https://www.w3.org/TR/WCAG22/) |
| `поле <name> не доходит до действия формы / форма очищается после отправки` | (1) `git grep -n 'name="<field>"'` в форме и `formData.get('<field>')`; помнить про автосброс неуправляемых форм `<form action>` в React 19 | поле управляемое или берёт `defaultValue` из возвращённого state; сброс задуман · [`<form>`](https://react.dev/reference/react-dom/components/form) |
| `строка <key> неверно склоняется/форматируется в ru` | (1) в каталоге `_one/_few/_many/_other` или ICU `{count, plural,…}`, вызов передаёт `count`; нет склейки строк вокруг `t()`; у `Intl` явная локаль | формы множественного числа есть и `count` передан · [CLDR](https://www.unicode.org/cldr/charts/latest/supplemental/language_plural_rules.html) |
| `экспорт/файл/зависимость <X> после PR никто не использует` | (2) `knip --trace-file <f> --trace-export <name>`; `knip` на base и head | потребитель — точка входа, динамический импорт или публичный `exports` пакета · [knip](https://knip.dev/guides/troubleshooting) |
| `<A> импортирует <B> через запрещённую границу / PR вводит цикл` | (2) `depcruise … --affected`; без правил — `madge --circular` | правила нет и соседи делают так же (тогда это `drift` с названным соседом); импорт только `import type`; цикл уже был на целевой ветке |
| `PR добавляет <N> kB JS (<lib> в общем чанке)` | (2) `size-limit --json` на base и head, `--why` | импорт ленивый или вытряхивается сборкой; прирост в пределах бюджета · [size-limit](https://github.com/ai/size-limit) |

Грейд: a11y 🔴 даёт только прогон (axe или тест с ролью), чтение кода — максимум 🟡.

## 4. Откуда стиль

Порядок и правило «первый выигрывает» — в [design-review.md](design-review.md). Для React
единственный стиль с силой правила — [Rules of React](https://react.dev/reference/rules) и
[You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect): они же правила
линтера. Airbnb — только как текст: конфиги `eslint-config-airbnb` заброшены (ESLint ≤ 8).
