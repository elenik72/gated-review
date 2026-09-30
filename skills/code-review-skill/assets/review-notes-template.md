# Review Notes Template

One page per review, kept at `REVIEW-NOTES.md` in a scratch directory (not committed to the
repository under review). Rewrite it as each finding resolves — not at the end.

`<skill>/scripts/finding.py` generates this page from `.review/state.json` after every
change, so it cannot drift from the findings. Use this template when filling it in by hand.

It exists for one reason: **the context window compacts, and this file is the only thing
that survives it.** After a compaction, re-read this file first and continue from `План`.

Keep it to roughly one screen. That constraint is the point — when the page is full,
observations have to compete, which forces raw sightings ("this component hardcodes
`data-cy`") to be compressed into rules ("this feature ignores the module's selector
convention; two components so far").

---

## Проверено

Only findings whose check was run and failed to kill them. Each line: the claim, the
evidence, the verdict.

- `ломается при пустом массиве items → таблица падает на .length of undefined` —
  `MediaTable.tsx:64`, вызовы: `git grep "MediaTable" -n` → 3 места, ни одно не
  гарантирует непустой массив. **подтверждено**, рунг 1.
- `требование "открытие нового оверлея закрывает предыдущий" не реализовано` —
  три независимых состояния в `List.tsx:22-31`. **подтверждено**, рунг 0 → 🟡.

## Предполагается

Mechanisms that look real but are not checked yet, and what would check them. Anything
still here at Phase 4 is posted as **предположение** with the reason, or not posted.

- Возможна гонка между `refresh()` и `onSelect` — проверить прогоном
  `media.spec.ts` (рунг 3). Пока не запускал.
- `useMediaList` может делать лишний запрос при монтировании — нужен запуск приложения
  (рунг 5), вероятно не окупается.

## Опровергнуто

**Do not skip this section.** It stops a second lap around a hypothesis already killed, and
it is the evidence that a subsystem was examined rather than skimmed. Each line: what you
believed → what killed it.

- Думал: `formatSize` не обрабатывает 0 → в `utils/format.ts:12` есть явная ветка `if (!n)`.
- Думал: класс `.panel` конфликтует с веткой `feature/library` →
  `git grep -l "\.panel" origin/feature/library` пусто.
- Думал: `dataCy` нигде не читается → читается в `e2e/media.cy.ts:41`.

## Покрытие

The inventory from Phase 0.4, with marks. What stays unticked here goes into the Phase 4
coverage statement verbatim — silence about a subsystem reads as approval of it.

- [x] `src/features/media/**` — 6 компонентов, 2 хука
- [x] `src/shared/ui/Dialog/**`
- [ ] миграции `db/migrations/**` — не смотрел, нет контекста по схеме
- [ ] `e2e/**` — не смотрел

## План

- [ ] Сравнить `MediaDialog` с `ChangeLogDialog` и `ExportDialog` (neighbour diff)
- [ ] Прогнать типизацию по всему проекту и отфильтровать свои файлы (`tsc --noEmit -p … | grep -F -f .review/js.txt`; `tsc <files>` игнорирует tsconfig) — команды в плане `finding.py init`
- [ ] Свести таблицу требований для Phase 4

---

## Counts for Phase 4

Read straight off the sections above and copy into the summary:

> Проверено находок: **<число строк в «Проверено»>**.
> Отброшено собственными проверками: **<число строк в «Опровергнуто»>**.
> Осталось предположениями: **<число строк в «Предполагается», которые всё же публикуются>**.
> Осмотрено: **<отмеченное в «Покрытие»>**. Не осмотрено: **<неотмеченное>**.
