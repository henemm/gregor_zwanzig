# Context: Issue #228 — `Btn.test.ts` braucht Svelte-Loader

## Request Summary

`frontend/src/lib/components/ui/btn/Btn.test.ts` schlägt mit
`ERR_UNKNOWN_FILE_EXTENSION` für `.svelte` fehl. Der Test importiert
`Btn` aus `./index.ts`, das `Btn.svelte` re-exportiert. Node-Test-Runner
`--experimental-strip-types` kann `.ts` parsen, aber keine `.svelte`-Dateien.

## Related Files

| Datei | Zeilen | Inhalt |
|-------|--------|--------|
| `frontend/src/lib/components/ui/btn/Btn.test.ts` | 230 | Bricht beim Import |
| `frontend/src/lib/components/ui/btn/index.ts` | 2 | Re-Export von `Btn.svelte` |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | 77 | Komponente — schlank, kein komplexer Algorithmus |
| `docs/specs/modules/issue_214_btn_feature_parity.md` | — | Original-Spec der Btn-Komponente |

## Bewertung der Issue-Optionen

| Option | Bewertung |
|--------|-----------|
| **(1) Custom Node-Loader für `.svelte`** | Komplex (Svelte 5 SSR-Pipeline programmatisch nachbauen). Bricht bei jedem Svelte-Update. Hoher Pflegeaufwand. |
| **(2) Helper-Extraktion** (Issue-Empfehlung) | Schwierig hier — Btn.svelte hat keinen extrahierbaren Algorithmus, nur Tag-Switch + Attribut-Forwarding. Helper-Extraktion würde die Komponente künstlich aufspalten. |
| **(3) Vitest installieren** | Wie Issue korrekt anmerkt: Anti-Empfehlung (zwei Test-Frameworks parallel). |
| **(4) Test-Datei stubben + Archiv in Spec** | Klein, pragmatisch, kein Coverage-Verlust (die Tests laufen sowieso nicht). Pfad zur Reaktivierung dokumentiert. |

## Tech-Lead-Empfehlung

**Option 4:** Test-Suite-Archiv in `docs/specs/modules/issue_214_btn_feature_parity.md` integrieren (oder neue Archive-Datei) + `Btn.test.ts` durch 3-Zeilen-Skip-Stub mit Verweis auf #228 + #214 ersetzen.

**Begründung:**
- Issue-Priorität ist **Low** — Tests waren seit Anbeginn tot (Vitest nie installiert)
- Btn-Komponente hat aktuell **0 Tests** und KEINEN Coverage-Verlust durch den Stub (Tests liefen sowieso nicht)
- TypeScript fängt fehlerhafte Props-Verwendung. Playwright fängt visuelle Regressions in `forms-dialogs-btn-migration.spec.ts` und `trip-header-btn-migration.spec.ts`.
- Tests bleiben als Source archiviert für künftige Vitest-/Playwright-Component-Tests-Migration

## Dependencies

- **#214** (Btn Feature-Parität) — Original-Spec der Tests
- **#225** (Vitest → node:test Migration) — hat den Bug überhaupt sichtbar gemacht

## Risks & Considerations

- **Risiko sehr gering:** Tests waren tot, neuer Stub ändert nichts an Production-Verhalten.
- **Coverage-Verlust:** Nein — vorher 0 (gebrochen), nachher 0 (skip). Indirekte Coverage via TypeScript + Playwright bleibt.
- **Reaktivierungs-Pfad:** Wenn künftig Vitest oder Playwright Component Tests eingeführt werden, kann Test-Code aus Archive-Datei zurückgeführt werden.

## Scope

1-2 Files modifiziert, ~230 LoC archiviert + ~10 LoC Stub. Sehr klein.
