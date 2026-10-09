---
entity_id: telegram_kurzform_sms_auswahl_2455
type: module
created: 2026-10-09
updated: 2026-10-09
status: draft
version: "1.0"
tags: [telegram, kurzform, sms, layout, doku, issue-2455]
---

# Telegram-Kurzform folgt der SMS-Auswahl (Klarstellung #2455)

## Approval

- [ ] Approved

## Purpose

PO-Entscheidung 2026-10-09 (Issue #2455): Die Telegram-Kurzform (`telegram_style="kurzform"`, Schalter "Telegram im SMS-Kurzstil") übernimmt die SMS-Auswahl (Metriken/Layout aus `channel_layouts.sms`) 1:1 — gewolltes Verhalten, kein Bug. Die eigene Telegram-Layout-Auswahl gilt nur für das normale (ausführliche) Telegram. Das Backend tut das bereits; diese Spec macht die Regel in der Oberfläche und der Doku sichtbar und sichert sie mit einem Wächter-Test ab.

## Source

- **File:** `frontend/src/lib/components/shared/TelegramKurzstilToggle.svelte`
- **Identifier:** Hinweistext des Schalters (geteilt: Trip `versand-tab/VTBriefingChannels.svelte`, Ortsvergleich `AlarmeTab.svelte`)

Backend-Ist (unverändert, nur durch Test abgesichert): `src/services/notification_service.py:674-685`, `src/output/renderers/trip_report.py:352,464`, `src/services/scheduler_dispatch_service.py:636-647`.

## Estimated Scope

- **LoC:** ~60 Code (Frontend ~20, Tests ~40) plus Doku
- **Files:** 11
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/i18n/index.ts` (`t(key)`) | module | Textkatalog-Zugriff für die neuen Hinweistexte |
| `frontend/src/lib/i18n/messages/de.json` | data | Ablage der neuen Texte |
| `versand-tab/vtBriefingChannelsText.ts` | module | Telegram-Unterzeile im Versand-Reiter |
| `tests/helpers/einstellung_auslieferung_orakel.py` | test helper | Bestehendes Orakel "Text = SMS-Text" |
| `src/services/notification_service.py`, `trip_report.py`, `scheduler_dispatch_service.py` | module | Bestehende Kurzform-Auflösung (nur lesend) |

## Implementation Details

1. `TelegramKurzstilToggle.svelte`: Den hartkodierten Satz (Zeile 62) durch `t(...)`-Texte aus `de.json` ersetzen. Neuer Inhalt: Telegram bekommt denselben kurzen Ein-Zeilen-Text wie SMS, ohne Knöpfe. Inhalt und Werte folgen der SMS-Auswahl im Layout-Reiter. Die Telegram-Auswahl gilt nur für das ausführliche Telegram. Label "Telegram im SMS-Kurzstil" bleibt unverändert (gepinnt durch `__tests__/telegram_kurzstil_shared_toggle.test.ts:48`).
2. `versand-tab/vtBriefingChannelsText.ts:42`: `vtBriefingSubTexts` bekommt einen optionalen Parameter `telegramStyle`. Bei `kurzform` lautet die Telegram-Unterzeile "folgt der SMS-Auswahl" statt "Layout · N Spalten". `VTBriefingChannels.svelte` reicht den Wert durch.
3. Wächter-Test Backend: Eine abweichende Telegram-Auswahl (anderes `channel_layouts.telegram` als `channel_layouts.sms`) wird bei `telegram_style="kurzform"` ignoriert — Trip und Ortsvergleich. Der Telegram-Text ist gleich dem SMS-Text; bei `rich` greift die Telegram-Auswahl.
4. Doku: `docs/reference/sms_format.md` (Abschnitt Telegram-Kurzform) und `docs/reference/metric_output_matrix.md` um die Regel ergänzen. Dort `:352` die Namensverwechslung mit der alten ADR-0014-"Kurzform"-Blase kurz abgrenzen. Widersprüche korrigieren: `docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md:257,413-417` und `docs/briefings/bug-2454-kurzform-gefuehlte-temperatur.md:28` (dort gilt die SMS-Auswahl als Defekt, richtig: gewolltes Verhalten gemäß #2455).

## Expected Behavior

- **Input:** Nutzer öffnet Versand-Reiter (Trip) bzw. Alarme/Versand (Ortsvergleich) mit Telegram aktiv.
- **Output:** Der Hinweis am Schalter erklärt, dass die SMS-Auswahl gilt. Die Telegram-Unterzeile verweist bei Kurzform auf die SMS-Auswahl.
- **Side effects:** Keine. Kein Datenmodell- und kein Renderer-Eingriff.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat Telegram als Kanal aktiv (Trip oder Ortsvergleich) / When er den Schalter "Telegram im SMS-Kurzstil" betrachtet / Then steht darunter, dass Inhalt und Werte der SMS-Auswahl im Layout-Reiter folgen und die Telegram-Auswahl nur für das ausführliche Telegram gilt.
  - Test: `frontend/src/lib/components/shared/__tests__/telegram_kurzstil_shared_toggle.test.ts` (node:test) — der Hinweis aus dem Textkatalog enthält beide Aussagen und gilt identisch für `context="route"` und `context="vergleich"`; das Label "Telegram im SMS-Kurzstil" bleibt.

- **AC-2:** Given Telegram ist inaktiv / When der Nutzer den Schalter betrachtet / Then ist er ausgegraut und der Hinweis lautet weiterhin "Erst aktiv, wenn Telegram als Kanal an ist."
  - Test: `frontend/src/lib/components/shared/__tests__/telegram_kurzstil_shared_toggle.test.ts` (node:test) — disabled-Text unverändert aus dem Textkatalog.

- **AC-3:** Given ein Trip hat die Telegram-Kurzform aktiv / When der Nutzer im Versand-Reiter die Telegram-Zeile liest / Then verweist die Unterzeile auf die SMS-Auswahl statt "Layout · 7 Spalten"; bei ausführlichem Telegram bleibt "Layout · 7 Spalten".
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/vtBriefingChannelsText.test.ts` (node:test) — `vtBriefingSubTexts` mit `kurzform` vs. `rich`, beide Kontexte.

- **AC-4:** Given ein Trip hat Telegram-Kurzform aktiv und eine Telegram-Auswahl, die von der SMS-Auswahl abweicht / When das Briefing versendet wird / Then erhält der Nutzer in Telegram exakt den SMS-Text, die abweichende Telegram-Auswahl bleibt wirkungslos.
  - Test: `tests/tdd/test_telegram_kurzform_ignoriert_telegram_auswahl.py::test_trip_kurzform_nutzt_sms_auswahl` (pytest) — Gegenprobe mit `rich` greift die Telegram-Auswahl.

- **AC-5:** Given ein Ortsvergleich hat Telegram-Kurzform aktiv und eine abweichende Telegram-Auswahl / When das Ortsvergleich-Briefing versendet wird / Then erhält der Nutzer in Telegram exakt den SMS-Text, die abweichende Telegram-Auswahl bleibt wirkungslos.
  - Test: `tests/tdd/test_telegram_kurzform_ignoriert_telegram_auswahl.py::test_vergleich_kurzform_nutzt_sms_auswahl` (pytest) — Gegenprobe mit `rich`.

- **AC-6:** Given ein Leser schlägt die Regel in der Doku nach / When er `sms_format.md`, `metric_output_matrix.md` und die #2454-Dokumente liest / Then steht überall: Kurzform übernimmt die SMS-Auswahl, gewolltes Verhalten (#2455), und kein Dokument nennt das einen Defekt.
  - Test: `tests/tdd/test_telegram_kurzform_ignoriert_telegram_auswahl.py::test_doku_nennt_regel_widerspruchsfrei` (pytest, `# doc-compliance-test`) — Regel vorhanden, Defekt-Formulierung entfernt.

## Known Limitations

- Im Layout-Reiter (`layout-tab/LTChannelPicker.svelte`, `ltChannels.ts`) wird kein Hinweis "gilt nur für ausführliches Telegram" ergänzt. Der Reiter kennt `telegram_style` nicht (keine Referenz im `layout-tab`-Verzeichnis); ihn dorthin durchzureichen wäre ein Datenfluss-Umbau über den Umfang hinaus. Der Hinweis am Schalter (AC-1) und die Versand-Unterzeile (AC-3) decken die Regel ab. Folgearbeit nur bei PO-Wunsch.
- Die Unterzeile aus AC-3 gilt im Trip-Kontext. Im Ortsvergleich gibt es dort keine Telegram-Unterzeile mit Spaltenangabe, der Hinweis aus AC-1 trägt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Klarstellung bestehenden, bereits implementierten Verhaltens. Kein neuer Kanal, Provider, kein Datenmodell- oder Auth-Eingriff und keine Abkehr von einer dokumentierten Entscheidung, daher kein neues ADR nötig.

## Changelog

- 2026-10-09: Initial spec created (PO-Entscheidung #2455)
