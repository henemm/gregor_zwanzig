# Context: Issue #297 — AlertRulesEditor „Beides"-Modus mit zwei Threshold-Feldern

## Request Summary

Wenn der User im Alert-Editor den Modus „Beides" wählt, erscheint aktuell nur EIN Threshold-Feld. Das ist semantisch falsch: Absolut-Schwelle und Δ-Schwelle haben unterschiedliche Einheiten/Bedeutungen. Lösung: „Beides" zeigt zwei separate Eingabefelder, ModeCard wird zu ModePill mit Feld-Anzahl-Badge, und Paar-Regeln werden in der List-View visuell gruppiert.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Haupt-Edit-Form — hier fehlen die zwei Threshold-Felder + Zeitfenster-Select |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | Wird zu `ModePill` mit „N Felder"-Badge umgebaut |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Braucht Pair-Markierung in der List-View (pair_id-Gruppierung) |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | `expandRules()` bekommt neue Signatur: `(base, mode, absThreshold, deltaThreshold, deltaWindow)` |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | Unit-Tests für `expandRules()` — müssen wegen Signatur-Änderung angepasst werden |
| `frontend/src/lib/types.ts` | `AlertRule`-Interface braucht optionale Felder: `pair_id?: string`, `delta_window?: string` |
| `frontend/e2e/alert-rules-editor.spec.ts` | Bestehende E2E-Tests (AC-1..AC-10) — müssen weiterhin grün bleiben |
| `internal/model/trip.go` | Go-Struct `AlertRule` braucht `PairID` + `DeltaWindow` (omitempty, backward-compatible) |
| `internal/handler/trip.go` | Pass-through — keine spezielle Logik nötig, nur neue Felder werden akzeptiert |

## Existing Patterns

- **expandRules() Pattern (Issue #179):** Pure Function in `alertRuleDefaults.ts`, gibt `AlertRule[]` zurück. Aufrufer: `AlertRuleRow.svelte::saveEdit()`. Aktuelle Signatur: `expandRules(rule: AlertRule, mode: AlertRuleMode): AlertRule[]`.
- **DELTA_ONLY_METRICS-Guard (AC-6):** Bei delta-only-Metriken (`temperature_change`, `wind_change`, `precipitation_change`) und mode='both' → nur eine delta-Rule. Dieser Guard muss erhalten bleiben.
- **ModeCard-Radio-Pattern:** 3 Buttons als `role="radio"`, `aria-checked={selected}`, `data-testid="mode-card-{mode}[-selected]"`. Die `data-testid`-Konvention muss beim Umbau zu ModePill beibehalten werden.
- **Issue #284 Restyle (bereits implementiert):** `SEVERITY_LABEL_DE`, `data-outlined` auf Severity-Pill und Kind-Badge, `<Btn>` statt plain buttons — bereits im Code vorhanden, darf nicht rückgebaut werden.
- **Read-Modify-Write (CLAUDE.md):** Backend-Handler liest existing Trip und mergt — `alert_rules` wird als ganzes Array überschrieben (kein Problem, da Frontend vollständiges Array sendet).
- **startEdit()-Logik:** Setzt `editMode` aus `rule.kind` — muss erweitert werden für Pair-Erkennung.

## State: AlertRule in TypeScript vs. Go

**TypeScript (`types.ts`)** — aktuell:
```ts
interface AlertRule {
  id: string; kind: AlertRuleKind; metric: AlertMetric;
  threshold: number; unit?: string; severity: AlertSeverity; enabled: boolean;
}
```
Fehlt: `pair_id?: string`, `delta_window?: string`, `abs_threshold?: number` (oder threshold bleibt für backward-compat und abs_threshold ist neu)

**Go (`internal/model/trip.go`)** — aktuell:
```go
type AlertRule struct {
  ID string; Kind AlertRuleKind; Metric AlertMetric;
  Threshold float64; Unit string; Severity AlertSeverity; Enabled bool;
}
```
Fehlt: `PairID *string`, `DeltaWindow *string`

## Form-State (AlertRuleRow.svelte) — was sich ändert

Aktuell: `draft.threshold` wird für beide Rules (absolute + delta) genutzt.

Neu: Separate Zustandsvariablen:
- `draftAbsThreshold: number` — für mode='absolute' oder 'both'
- `draftDeltaThreshold: number` — für mode='delta' oder 'both'
- `draftDeltaWindow: string` — für mode='delta' oder 'both' (Select: 1h/3h/6h/12h/24h)

## expandRules() — neue Signatur

```ts
expandRules(
  base: Omit<AlertRule, 'kind' | 'threshold'> & { metric: AlertMetric, severity: AlertSeverity, enabled: boolean },
  mode: AlertRuleMode,
  absThreshold: number,
  deltaThreshold: number,
  deltaWindow: string,
): AlertRule[]
```

Für mode='both': erzeugt zwei Rules mit gleichem `pair_id` (crypto.randomUUID()).

## Dependencies

- **Upstream:** `types.ts` (AlertRule-Interface), `alertRuleDefaults.ts` (expandRules)
- **Downstream:** `AlertRuleRow.svelte` → `AlertRulesEditor.svelte` → Trip-Edit-Seite → PUT /api/trips/{id} → Go-Backend

## Existing Specs

- `docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md` — expandRules-Spec (wird durch #297 erweitert)
- `docs/specs/modules/issue_223_alert_rules_editor.md` — AlertRulesEditor-Spec (E2E-Tests)
- `docs/specs/modules/issue_284_alert_rules_restyle.md` — Restyle (bereits implementiert)

## Risiken & Überlegungen

1. **Signatur-Bruch `expandRules()`:** Alle bestehenden Tests in `alertRuleDefaults.test.ts` müssen angepasst werden — sie übergeben aktuell nur `(rule, mode)`.
2. **startEdit()-Vorauswahl für bestehende Pair-Regeln:** Wenn eine absolute-Rule `pair_id` hat, sollte editMode='both' vorausgewählt sein. Aber beide Regeln eines Paares werden einzeln gerendert — d.h. der User würde jede Paar-Regel separat bearbeiten können. Das Issue beschreibt keine Bearbeitung bestehender Pair-Regeln — wir fokussieren auf das Anlegen.
3. **Backward-Compatibility:** Bestehende Rules ohne `pair_id`/`delta_window` müssen weiterhin korrekt funktionieren.
4. **Go-Schemamigration:** Da `pair_id` + `delta_window` optional/omitempty sind, ist keine Datenmigration nötig — alte Rules haben die Felder einfach nicht.
5. **delta_window Default-Wert:** Wenn mode='delta' und kein `deltaWindow` gesetzt ist, Default='6h' (lt. Issue).
