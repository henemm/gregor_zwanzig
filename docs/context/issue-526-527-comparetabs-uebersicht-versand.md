# Context: #526 + #527 — CompareTabs Übersicht- und Versand-Tab

## Request Summary

Zwei Tabs im Compare Hub (`CompareTabs.svelte`) sollen design-konform umgebaut werden:
- **#526** Übersicht-Tab: 2×2 SummaryCard-Grid + weiße Monitoring-Card + Hinweis-Box
- **#527** Versand-Tab: 2-Spalten-Layout mit Rhythmus/Kanal-Cards + Aktivierungs-Card

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Haupt-Änderungsdatei — beide Tabs leben hier |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | `deriveStatusFromPreset`, `presetScheduleLabel`, `formatLastSent`, `STATUS_MAP` |
| `docs/design-requests/orts-vergleich/gregor-zwanzig/project/screen-compare-detail.jsx` | Referenz-Mockup (CD_StatRow, CD_MailThumb) |
| `internal/model/compare_preset.go` | Datenmodell — keine `enabled`-Flag, Status wird abgeleitet |
| `internal/handler/compare_preset.go` | `PUT /api/compare/presets/{id}`, `POST /api/compare/presets/{id}/send` |
| `frontend/src/lib/components/atoms/index.ts` | Atoms: Card, Btn, Dot, Eyebrow, Pill, Switch, Segmented |

## Existing Patterns

- **Status-Ableitung:** `deriveStatusFromPreset(p)` → `'active'|'paused'|'draft'`
  - `draft` wenn kein Name oder keine location_ids
  - `paused` wenn `schedule === 'manual'`
  - sonst `active`
- **Pausieren:** Kein eigener API-Endpunkt — `PUT /api/compare/presets/{id}` mit `schedule: 'manual'` setzt auf Paused
- **Aktivieren:** `PUT` zurück auf `schedule: 'daily'` oder `'weekly'` — bisheriger Wert geht verloren wenn nur `manual` gespeichert
- **Tab-Wechsel:** `handleValueChange(value)` — wechselt activeTab + URL-Param `?tab=`
- **API-Call für Senden:** `POST /api/compare/presets/{id}/send` — bereits in Vorschau-Tab via `handleSend()`
- **Card-Atom:** `Card.svelte` in atoms — wird in Molecules verwendet
- **Switch-Atom:** `Switch.svelte` in atoms — verfügbar für Kanal-Toggles

## Datenmodell-Constraints

Das `ComparePreset`-Modell hat **kein** `channels`-Feld und kein Channel-enabled/disabled.
- `empfaenger: string[]` = Empfänger-Adressen (E-Mail-Adressen, nicht Channel-Typen)
- Channel-Verbundenstatus (Signal/Telegram/SMS) ist **nicht** im Preset gespeichert
- Für #527 AC-2: Channel-Zeilen werden als statische Liste mit Nicht-verbunden-Status gezeigt, nur Email als "verifiziert" wenn `empfaenger.length > 0`
- Toggle-Switches für Signal/Telegram/SMS sind visuell vorhanden, aber zunächst ohne Persistenz (Channel-Setup ist Folge-Issue)

## Dependencies

- **Upstream:** `api.js` → `PUT /api/compare/presets/{id}` für Pause/Aktivieren
- **Upstream:** `api.js` → `POST /api/compare/presets/{id}/send` für Test-Briefing
- **Downstream:** `CompareDetail.svelte` bindet `CompareTabs` ein — keine strukturelle Änderung nötig
- **Atoms:** `Card`, `Btn`, `Dot`, `Eyebrow`, `Switch` — alle bereits importiert oder vorhanden

## Existing Specs

- `docs/specs/modules/issue_517_compare_hub.md` — Basis-Spec für CompareTabs (6-Tab-Orchestrator)

## Risks & Considerations

1. **Pause/Aktivieren ohne eigenes API:** Aktuell kein `PATCH`/`pause`-Endpoint → `PUT` mit komplettem Preset-Objekt. Das ist ein Read-Modify-Write: `preset.schedule = 'manual'` (pausieren) bzw. zurücksetzen (aktivieren). Da das Original-Schedule beim Pausieren verloren geht, muss der Aktivieren-Button auf `daily` zurücksetzen (Standard-Default) — dies ist eine bekannte Einschränkung.
2. **Channel-Verbundenstatus:** Nicht im Datenmodell — AC-2 zeigt Email als verbunden wenn Empfänger vorhanden, Signal/Telegram/SMS als "nicht verbunden" (statisch). Kanal-Setup ist Scope für separates Issue.
3. **LoC-Limit:** Beide Issues in einer Datei → überschreitet 250-LoC-Limit; LoC-Override auf 500 planen.
4. **SummaryCard als lokale Komponente:** Es gibt keine globale SummaryCard-Atom — wird inline im Template mit Card-Atom umgesetzt.
