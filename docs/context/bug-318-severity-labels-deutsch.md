# Context: Bug #318 — Severity-Labels auf Englisch

## Request Summary

In der `AlertsPreviewCard` (Trip-Detail-Übersicht) zeigt die Severity-Pill
die rohen englischen Enum-Werte (`warning`, `critical`) als gefüllte Pill statt
die deutschen outlined Bezeichnungen (`WARNUNG`, `KRITISCH`).

## Root Cause

**`frontend/src/lib/components/trip-detail/AlertRow.svelte` — Zeile 38:**

```svelte
<Pill tone={ALERT_SEVERITY_TONE[rule.severity]}>{rule.severity}</Pill>
```

Zwei Probleme:
1. `{rule.severity}` = roh-englisch statt `SEVERITY_LABEL_DE[rule.severity]`
2. Kein `data-outlined`-Attribut → gefüllte goldgelbe Pill statt outlined

## Related Files

| Datei | Relevanz |
|-------|---------|
| `frontend/src/lib/components/trip-detail/AlertRow.svelte` | **Bug-Datei** — rendert `{rule.severity}` direkt |
| `frontend/src/lib/utils/alertMetricLabels.ts` | `SEVERITY_LABEL_DE` Map (info→'Info', warning→'Warnung', critical→'Kritisch') — bereits korrekt |
| `frontend/src/app.css` (Zeile 328–336) | CSS für `[data-slot="pill"][data-outlined]` — bereits vorhanden |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Referenz-Implementierung: nutzt bereits `SEVERITY_LABEL_DE` + `data-outlined` ✓ |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Wrapper — rendert `AlertRow` pro enabled AlertRule |

## Existing Patterns

`AlertRuleRow.svelte` (der Editor) zeigt wie es sein soll:
```svelte
<Pill tone={ALERT_SEVERITY_TONE[rule.severity]} data-outlined
    >{SEVERITY_LABEL_DE[rule.severity]}</Pill>
```

## Fix (minimal)

In `AlertRow.svelte`:
1. `SEVERITY_LABEL_DE` zum Import hinzufügen
2. `{rule.severity}` → `{SEVERITY_LABEL_DE[rule.severity]}`
3. `data-outlined` Attribut hinzufügen

## Scope

Nur `AlertRow.svelte` — alle anderen Severity-Renderings sind bereits korrekt:
- `AlertRuleRow.svelte` ✓ (nutzt SEVERITY_LABEL_DE + data-outlined)
- `TripOverview.svelte` ✓ (nutzt SEVERITY_LABEL_DE)
- `AlertMetricRow.svelte` — severity nur im Select (kein Pill-Render)

## Risks & Considerations

Kein Risiko — reine Anzeige-Änderung, kein State/API-Einfluss.
