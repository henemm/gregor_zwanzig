# Context: Issues #212 + #216 — Button-Duplikat-Cleanup

## Request Summary

Phasen B + C der Button-Konsolidierung. Migration (Phase B / #212) ist
zu 96% fertig — nur noch **2 Dateien** verwenden die alte `Button`-Komponente.
Phase C (#216) entfernt das Verzeichnis komplett.

## Verbleibende Migrations-Stellen

```
frontend/src/lib/components/edit/EditRouteSection.svelte
  Z. 4   import { Button } from '$lib/components/ui/button/index.js';
  Z. 193, 200, 226 — 3× <Button> (variant="outline")

frontend/src/lib/components/edit/EditStagesSection.svelte
  Z. 3   import { Button } from '$lib/components/ui/button/index.js';
  Z. 65, 81, 91, 102, 119, 158, 169 — 7× <Button> (variant="outline" | "ghost")
```

Gesamt: **10 `<Button>`-Aufrufe in 2 Dateien**. Verwendete Variants: `outline`,
`ghost`; Sizes: `sm`, `icon-sm` — alle in `Btn` vorhanden.

## Btn vs Button — Kompatibilitäts-Matrix

| Aspekt | Button (alt) | Btn (neu, kanonisch) | Migration |
|--------|--------------|----------------------|-----------|
| Default-Variant | `default` | `primary` | Beide ungenutzt in den 2 Dateien |
| Variants | default, outline, secondary, ghost, destructive, link | primary, accent, outline, ghost, secondary, destructive, link | `outline`, `ghost` 1:1 |
| Sizes | default, xs, sm, lg, icon | xs, sm, md, lg, icon, icon-xs, icon-sm, icon-lg | `sm`, `icon-sm` 1:1 |
| Props | `variant`, `size`, `onclick`, `class`, `disabled`, `title` etc. | identische API | direkter Tag-Tausch reicht |

## Phantomreferenzen

`grep -rn "buttonVariants\|ButtonProps\|ButtonVariant\|ButtonSize" frontend/src/` außerhalb des button-Verzeichnisses → **0 Treffer**.

`grep -rn "import.*Button[ ,}]" frontend/src/` außerhalb Btn-Imports → **0 Treffer** außer den 2 zu migrierenden.

Daher: Komplette Eliminierung des `ui/button/`-Verzeichnisses möglich.

## Related Files

| Datei | Aktion |
|-------|--------|
| `frontend/src/lib/components/edit/EditRouteSection.svelte` | Migrieren — Import + 3 Tags |
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | Migrieren — Import + 7 Tags |
| `frontend/src/lib/components/ui/button/button.svelte` | Löschen |
| `frontend/src/lib/components/ui/button/index.ts` | Löschen (komplettes Verzeichnis) |

## Existing Patterns

- 16 andere Dateien nutzen bereits `Btn` korrekt — kein Architektur-Risiko.
- `dialog/dialog-content.svelte`, `dialog/dialog-footer.svelte` haben Btn im UI-Bereich integriert.

## Dependencies

- **#214** (Btn Feature-Parität) — Btn deckt seit Issue #214 alle benötigten Variants und Sizes ab.
- **svelte-check Baseline:** 23 Errors (nach #228-Stub). Migration darf nicht erhöhen.

## Risks & Considerations

- **Visuelle Regression:** Beide Komponenten erzeugen optisch ähnliche Buttons, aber unterschiedliche CSS-Classes. Manuelle Sichtprüfung der Trip-Edit-Seite + Wizard nötig.
- **Test-Coverage:** E2E-Tests in `forms-dialogs-btn-migration.spec.ts` und `trip-header-btn-migration.spec.ts` decken Migrations-Roundtrip bereits ab.
- **Scope:** 2 Files modifizieren + 1 Verzeichnis löschen. Klein.

## Scope-Schätzung

~20 LoC Code-Edits + Verzeichnis-Löschung (~150 LoC entfernt). Klein.
