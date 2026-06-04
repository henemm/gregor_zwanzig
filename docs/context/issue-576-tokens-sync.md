# Context: Issue #576 — tokens.css → app.css Sync (Fundament)

## Request Summary
Alle CSS-Token-Werte aus `claude-code-handoff/current/jsx/tokens.css` müssen 1:1 in
`frontend/src/app.css` übernommen werden. Einzige bekannte Wertabweichung laut SOLL-COVERAGE.md (2026-06-03): `--g-paper-deep`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/app.css` | Zieldatei — `:root`-Block enthält alle `--g-*` Token-Definitionen |
| `claude-code-handoff/current/jsx/tokens.css` | Autoritative Quelle (109 Zeilen, nur `:root` + Demo-Body-Styles) |
| `frontend/src/lib/tokens-bridge.test.ts` | Token-Guard-Tests — muss mitgeändert werden |

## Bestätigte Token-Unterschiede

### 1. Wertabweichung (korrekturbedürftig)
| Token | app.css | tokens.css | Quelle |
|-------|---------|------------|--------|
| `--g-paper-deep` | `#ede9df` | `#ecead9` | SOLL-COVERAGE.md: bestätigte Abweichung |

### 2. Bekannte intentionelle Abweichungen (NICHT ändern)
| Token | app.css | tokens.css | Begründung |
|-------|---------|------------|------------|
| `--g-info` | `#2a6cb3` | `#2c5a8c` | tokens-bridge.test.ts Z. 100: "Kollision — NICHT auf Sandbox-Wert umdefinieren" (Issue #369) |
| `--g-good`/`--g-warn`/`--g-bad` | nicht in app.css | in tokens.css | tokens-bridge.test.ts Z. 91–96: absichtlich entfernt in Issue #541 |
| `--g-weather-thunder` | `var(--g-wx-thunder)` | `#c43a2a` | alias = direkter Wert; tokens-bridge.test.ts Z. 61 bewacht dies |
| `--g-font-sans`/`--g-font-mono` | Alias auf `--g-font-ui`/`--g-font-data` | direkte Fontstacks | tokens-bridge.test.ts Z. 65–66 bewacht die Alias-Form |
| `--g-r-1`/`--g-r-2`/`--g-r-pill` | Alias auf `--g-radius-xs` etc. | `2px`/`4px`/`999px` | tokens-bridge.test.ts Z. 70–75 bewacht die Alias-Form |

## Test-Guard, der geändert werden muss

`frontend/src/lib/tokens-bridge.test.ts` Zeile 125:
```typescript
// VORHER (blockiert paper-deep-Update):
assert.ok(hasDecl('--g-paper-deep', '#ede9df'), '--g-paper-deep bleibt #ede9df (nicht im #378-Scope, C1)');
// NACHHER (Issue #576 hebt den #378-Aufschub auf):
assert.ok(hasDecl('--g-paper-deep', '#ecead9'), '--g-paper-deep auf tokens.css-Wert angehoben (#576)');
```

## Problem: Akzeptanzkriterium diff-Befehl ist unpraktikabel

Das AC im Issue lautet:
```bash
diff <(grep '\-\-g-' frontend/src/app.css) <(grep '\-\-g-' claude-code-handoff/current/jsx/tokens.css)
```

Dieser Befehl vergleicht ALLE Zeilen mit `--g-` — also auch alle Komponentenstile in app.css
(`[data-slot="btn"]`, `[data-slot="pill"]` usw.), die nie in tokens.css vorkommen.
Ergebnis: 190 vs 62 Zeilen → diff wird immer nicht-leer sein.

**Pratischer Ersatz-Check:** Nur `:root`-Deklarationen vergleichen:
```bash
# Alle Token-WERTE aus tokens.css in app.css vorhanden?
# Nach Fix: einzig verbleibende Unterschiede = intentionelle Abweichungen (oben dokumentiert)
```

## Existing Patterns
- `tokens-bridge.test.ts` nutzt Source-Inspection (liest app.css als String)
- Alle Token-Änderungen in app.css müssen immer mit `tokens-bridge.test.ts` synchronisiert werden

## Dependencies
- Upstream: `claude-code-handoff/current/jsx/tokens.css` (autoritativ)
- Downstream: ALLE `.svelte`-Dateien und `app.css`-Komponenten verwenden `--g-paper-deep` via `var()`

## Nutzung von --g-paper-deep
