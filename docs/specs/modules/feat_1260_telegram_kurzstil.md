---
entity_id: feat_1260_telegram_kurzstil
type: feature
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [telegram, sms, notification, dispatch, multi-user]
workflow: feat-1260-telegram-kurzstil
---

<!-- Issue #1260 -->

# Feature 1260 — Telegram im SMS-Kurzstil (Opt-in)

## Approval

- [x] Approved (PO, 2026-07-15)

## Purpose

Nutzer bekommen einen opt-in Schalter „Telegram im Kurzstil": ist er aktiviert, erhält
Telegram für den betroffenen Pfad exakt dieselbe kurze Ein-Zeilen-Nachricht wie SMS statt
der reichen Multi-Bubble-Darstellung mit Inline-Knöpfen. Der reiche Stil bleibt Default —
das Feature dient Nutzern, die Telegram bewusst wie einen zweiten SMS-Kanal (kompakt, ohne
Bedienelemente) nutzen wollen, z.B. bei schwacher Verbindung oder aus Präferenz.

## Source

- **File:** `src/services/notification_service.py`
- **Identifier:** `class NotificationService` — vier Dispatch-Methoden, an denen der Schalter
  greift: `send_trip_report()` (Zeile ~267), `_dispatch_alert_message()` (Zeile ~790,
  Trip-Abweichungs-Alarm), `send_official_alert()` (Zeile ~536, Trip-amtliche Warnung),
  `_dispatch_compare_official_telegram()` (Zeile ~648, amtliche Compare-Warnung)

> **Schicht-Hinweis:** Alle vier Dispatch-Stellen liegen im Python-Core
> (`src/services/`, `src/app/`), nicht im Go-API-Layer. Die Go-Structs (`internal/model/`)
> werden NICHT geändert, weil beide neuen Config-Felder opak in bereits generisch
> gemergte Blobs (`report_config`, `display_config`) fallen (siehe Implementation Details).

## Estimated Scope

- **LoC:** ~300–450 (inkl. Tests)
- **Files:** 8 Quelldateien (Backend 5, Frontend 3) + neue Testdateien in `tests/tdd/`
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig.email_format` (`src/app/models.py:759`) | Precedent | Blaupause für das neue Feld `telegram_style` — identisches String-Enum-Muster |
| `TripReportConfig` (`src/app/models.py:726-767`) | Modul | Trägt das neue Feld `telegram_style: str = "rich"` |
| `ComparePreset.display_config` (dict) | Modul | Trägt den neuen Key `telegram_style` im Compare-Preset (kein neues Go-Feld nötig) |
| `src/app/loader.py` generischer Config-Merge | Modul | Persistiert `report_config`/`display_config` als Read-Modify-Write-Merge — deckt das neue Feld automatisch ab, ohne Loader-Änderung im Kernpfad |
| `trip_alert.py::_effective_alert_channels()` | Funktion | Bestehende Kanal-Auflösung für Trip-Alarme; muss den aufgelösten Style zusätzlich an den Dispatch durchreichen |
| `compare_official_alert.py::_effective_channels()` | Funktion | Analoge Kanal-Auflösung für Compare-amtliche Warnungen |
| `render_sms()` (`sms_trip.py`, `alert/render.py`, `alert/official_alerts.py`) | Funktion | Liefert den bereits fertigen Kurzstil-Text — wird NICHT verändert, nur im Dispatch umgeleitet (kein `renderer_mail_gate`-Trigger, #811) |
| `TelegramOutput.send()` (`src/output/channels/telegram.py`) | Transport | Muss mit `parse_mode=None` aufgerufen werden können (Redirect-Pfad sendet unescapten SMS-Text) |
| `email_format`-Frontend-Muster (`EditReportConfigSection.svelte:454-473`) | Precedent | Blaupause für die geteilte Bedienkomponente |

## Implementation Details

**Ansatz: Dispatch-Redirect, kein Renderer-Edit.** Alle vier Pfade haben den kurzen
SMS-Text bereits fertig gerendert oder ohne Renderer-Änderung abrufbar vorliegen
(`report.sms_text`, `sms_body`, `render_official_alert_sms(...)`). Der Schalter tauscht
am Dispatch-Punkt nur die Nutzlast, die an `TelegramOutput.send()` geht — die Renderer
(`narrow.py`, `trip_report.py`, `sms_trip.py`, `alert/render.py`, `alert/official_alerts.py`)
bleiben unangetastet. Das hält den Diff klein und triggert `renderer_mail_gate` (#811) nicht,
das genau diese Dateien deckt.

```
if telegram_style == "kurzform":
    TelegramOutput(settings).send(
        subject=subject, body=<kurzer_sms_text>,
        parse_mode=None,               # SMS-Text ist nicht HTML-escaped
        suppress_subject_line=True,
    )
else:  # "rich" (Default)
    <bisheriges Bubble-/HTML-Verhalten unverändert>
```

**Konfig-Feld — neu, kein Reaktivieren von `telegram_kurzform`:** Das tote Feld
`UnifiedWeatherDisplayConfig.telegram_kurzform` (`models.py:580`, #614) sitzt am falschen
Ort (Anzeige-Config) und ist semantisch mit dem stillgelegten #1001-Konzept belastet.
Stattdessen:
- **Trip:** `TripReportConfig.telegram_style: str = "rich"` (Werte `"rich"` oder
  `"kurzform"`), exakt das `email_format`-Muster. Liegt im `report_config`-Blob →
  generischer Merge deckt RMW ab, keine Go-Struct-Änderung nötig.
- **Compare:** Key `ComparePreset.display_config["telegram_style"]` (Default `"rich"`),
  Präzedenzfall `metric_alert_levels` liegt ebenfalls als DisplayConfig-Sub-Key — wird bereits
  feldweise gemergt (#1159-Fix).

**Kappung:** 1:1 beibehalten — Trip-Briefing ≤160 Zeichen, Alarme ≤140 Zeichen, weil der
bereits gerenderte SMS-String unverändert weiterverwendet wird.

**Kanal-Auflösung Trip-Alarme:** `_effective_alert_channels()` bleibt in seiner Kanal-Logik
unverändert; zusätzlich löst `trip_alert.py` den Style aus `trip.report_config.telegram_style`
auf und reicht ihn an `_dispatch_alert_message()` / `send_official_alert()` durch — mit
explizitem Default `"rich"`, damit der geteilte `_dispatch_alert_message()` (bedient auch
reguläre Compare-Abweichungs-Alarme, NICHT im Scope) keine implizite Kopplung bekommt.

**Kanal-Auflösung Compare-amtlich:** `compare_official_alert.py::_effective_channels()`
bleibt unverändert; eine neue kleine Hilfsfunktion `_effective_telegram_style(preset)` liest
`preset["display_config"]["telegram_style"]` mit Default `"rich"` und wird an
`_dispatch_compare_official_telegram()` durchgereicht.

### Slice-Reihenfolge (jede Scheibe eigenständig test- und auslieferbar)

| Slice | Inhalt |
|-------|--------|
| S1 | Config-Feld `telegram_style` + Persistenz (RMW) für Trip |
| S2 | Trip-Briefing-Redirect (`send_trip_report`) |
| S3 | Trip-Alarme-Redirect (Abweichung `_dispatch_alert_message` + amtlich `send_official_alert`) |
| S4 | Compare-amtlich-Redirect (`_dispatch_compare_official_telegram`) inkl. Compare-Config-Feld + RMW |
| S5 | Geteilter Frontend-Schalter (Trip-Versand-Tab + Alarme-Tab, Prop `context` = `route` oder `vergleich`) |

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/models.py` | MODIFY | `TripReportConfig.telegram_style: str = "rich"` |
| `src/app/loader.py` | MODIFY | RMW-Merge deckt neues Feld ab (Trip-Pfad, ggf. kleiner Merge-Test) |
| `src/services/notification_service.py` | MODIFY | Redirect in 4 Dispatch-Stellen, `parse_mode=None` |
| `src/services/trip_alert.py` | MODIFY | Style aus `report_config` auflösen + an Dispatch durchreichen |
| `src/services/compare_official_alert.py` | MODIFY | `_effective_telegram_style(preset)` + Durchreichen |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | MODIFY | Kurzstil-Schalter unter der Telegram-Zeile (geteilte Komponente, Prop `context` = `route`/`vergleich`) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Kurzstil-Anzeige/-Bedienung im Alarm-Kontext (Trip + Compare via bestehenden `context`) |
| `frontend/src/lib/types.ts` | MODIFY | Typ `telegram_style` (Werte `rich`/`kurzform`) analog `email_format` |
| `tests/tdd/*` | CREATE | Siehe Test Coverage |

## Expected Behavior

- **Input:** Nutzer aktiviert den Kurzstil-Schalter für Telegram (Trip-Versand-Tab oder
  Compare-Alarme-Tab); danach lösen die vier Scope-Pfade regulär aus (Scheduler-Briefing,
  Abweichungs-Alarm-Trigger, amtliche Warnung, Compare-amtliche Warnung).
- **Output:** Telegram erhält für die vier Scope-Pfade EINE kurze Ein-Zeilen-Nachricht
  (identisch zur SMS-Variante, ≤160/140 Zeichen), ohne Inline-Knöpfe. Bei deaktiviertem
  Schalter (Default) bleibt die reiche Multi-Bubble-/HTML-Darstellung wie bisher.
- **Side effects:** Kein Effekt auf E-Mail- oder SMS-Versand; keine Änderung an regulären
  Ortsvergleich-Briefings/-Alarmen (bleiben E-Mail-only, unangetastet).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat den Kurzstil-Schalter für Telegram NICHT aktiviert (Default) / When sein Trip-Briefing (Morgen oder Abend) per Telegram verschickt wird / Then erhält er weiterhin die bisherige reiche Multi-Bubble-Darstellung mit Inline-Knöpfen, unverändert zum heutigen Verhalten.
  - Test: Regressions-Snapshot der Telegram-Ausgabe bei `telegram_style="rich"` bzw. unbelegtem Feld — bleibt bubble-basiert.

- **AC-2:** Given ein Nutzer hat den Kurzstil-Schalter für Telegram aktiviert / When sein Trip-Briefing (Morgen oder Abend) per Telegram verschickt wird / Then erhält er in Telegram genau eine Nachricht mit demselben kurzen Zeilentext wie die SMS-Variante (≤160 Zeichen) und ohne Inline-Knöpfe.
  - Test: Trip-Briefing-Dispatch mit `telegram_style="kurzform"` — gesendeter Telegram-Body ist byte-identisch zum parallel erzeugten `sms_text`.

- **AC-3:** Given ein Nutzer hat den Kurzstil-Schalter aktiviert und einen Trip-Abweichungs-Alarm mit eigenen Schwellwerten konfiguriert / When der Alarm auslöst und Telegram als Kanal aktiv ist / Then erhält er in Telegram denselben kurzen Alarmtext wie per SMS (≤140 Zeichen) statt der reichen HTML-Alarmnachricht.
  - Test: `_dispatch_alert_message()` mit aktivem Kurzstil — gesendeter Telegram-Body entspricht `sms_body`, nicht `telegram_body`.

- **AC-4:** Given ein Nutzer hat den Kurzstil-Schalter aktiviert / When für seinen Trip eine amtliche Wetterwarnung standalone (ohne Wetter-Delta) per Telegram verschickt wird / Then erhält er denselben kurzen Warntext wie per SMS statt der reichen Telegram-Warnvorlage.
  - Test: `send_official_alert()` mit aktivem Kurzstil — gesendeter Telegram-Body entspricht `render_official_alert_sms(...)`, nicht `render_official_alert_telegram(...)`.

- **AC-5:** Given ein Nutzer hat den Kurzstil-Schalter für seinen Orts-Vergleich (amtliche Warnungen) aktiviert / When eine amtliche Warnung für einen oder mehrere verglichene Orte per Telegram verschickt wird / Then erhält er denselben kurzen Warntext wie per SMS statt der reichen Vergleichs-Warnvorlage.
  - Test: `_dispatch_compare_official_telegram()` mit aktivem Kurzstil — gesendeter Telegram-Body entspricht `render_official_alert_sms(...)`.

- **AC-6:** Given ein Nutzer hat den Kurzstil-Schalter aktiviert / When ein regulärer Orts-Vergleich-Bericht oder ein regulärer Abweichungs-/Radar-Alarm im Vergleich fällig wird / Then bleibt dieser Versand unverändert E-Mail-only — es entsteht kein neuer Telegram- oder SMS-Versandweg für diese Pfade.
  - Test: Regulärer Compare-Briefing-/Radar-Alarm-Dispatch mit gesetztem `telegram_style` — kein Telegram-/SMS-Sink wird aufgerufen, nur E-Mail.

- **AC-7:** Given der Kurzstil ist für einen der vier Scope-Pfade aktiv und der Wetterinhalt enthält Zeichen wie „&" oder „<" (z.B. in Ortsnamen oder Werten) / When die Kurzstil-Nachricht an Telegram gesendet wird / Then kommt die Nachricht unverstümmelt beim Nutzer an, ohne dass der Versand wegen eines Formatierungsfehlers der Bot-API scheitert.
  - Test: `TelegramOutput.send()`-Aufruf im Redirect-Zweig wird mit `parse_mode=None` geprüft (nicht `"HTML"`) — inkl. Fixture-Text mit `&`/`<`.

- **AC-8:** Given ein Nutzer hat den Kurzstil-Schalter für seinen Trip bereits aktiviert / When er über die Oberfläche einen Teil-Speichervorgang auslöst, der den Kurzstil-Schalter nicht anfasst (z.B. nur die Sende-Uhrzeit ändert) / Then bleibt der Kurzstil-Schalter danach weiterhin aktiviert — er geht beim Speichern nicht verloren.
  - Test: RMW-Roundtrip — PUT mit Teil-Payload ohne `telegram_style`, danach GET desselben Trips prüft, dass `telegram_style="kurzform"` erhalten bleibt.

- **AC-9:** Given ein Nutzer hat den Kurzstil-Schalter für ein amtliches Compare-Warnungs-Preset bereits aktiviert / When er über die Oberfläche einen Teil-Speichervorgang auslöst, der andere Preset-Felder ändert (z.B. Orte hinzufügt) / Then bleibt der Kurzstil-Schalter danach weiterhin aktiviert — er geht beim Speichern nicht verloren.
  - Test: RMW-Roundtrip — PUT mit Teil-Payload ohne `display_config.telegram_style`, danach GET desselben Presets prüft Feld-Erhalt.

- **AC-10:** Given zwei verschiedene Nutzer A und B haben je einen eigenen Trip mit aktiviertem Telegram-Kanal, Nutzer A hat den Kurzstil-Schalter aktiviert, Nutzer B hat ihn deaktiviert / When beide unabhängig voneinander ein Briefing über Telegram erhalten / Then bekommt ausschließlich Nutzer A den Kurzstil-Text, Nutzer B weiterhin die reiche Darstellung — keine Vermischung zwischen den Konten, kein `user_id="default"`-Fallback.
  - Test: Zwei vollständige Trip-Fixtures unter verschiedenen `user_id`, gleichzeitiger Dispatch, getrennte Assertion je Nutzer-Ausgabe.

- **AC-11:** Given ein Nutzer öffnet den Versand-Tab seines Trips oder den entsprechenden Alarme-/Versand-Tab seines Orts-Vergleichs / When er den Kurzstil-Schalter für Telegram bedient / Then sieht und bedient er in beiden Kontexten dieselbe Bedienkomponente (gleiche Beschriftung, gleiche Position relativ zur Telegram-Checkbox) — kein unabhängig gepflegter Compare-Nachbau.
  - Test: Komponenten-Test/Playwright prüft, dass sowohl `context="route"` als auch `context="vergleich"` denselben Schalter-Baustein rendern (Trip/Compare-Sharing-Invariante).

## Known Limitations

- Im Kurzstil entfallen die Telegram-Inline-Knöpfe/Aktionen (z.B. Weiterblättern, PAUSE/SKIP) —
  inhärent zu „SMS-Stil = eine Zeile ohne Bedienelemente". Bewusster Kompromiss, kein Bug.
- Reguläre Ortsvergleich-Briefings und -Abweichungs-/Radar-Alarme bleiben E-Mail-only (kein
  Telegram/SMS-Versand vorhanden) — dieses Feature ändert daran nichts.
- Telegram hat technisch kein 160-Zeichen-Limit; die Kappung wird trotzdem 1:1 vom SMS-Format
  übernommen ("exakt der SMS-Stil" ist PO-Vorgabe, keine Telegram-spezifische Neuformatierung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive, opt-in Erweiterung nach etabliertem Muster (`email_format`
  full/compact, #722). Kein neuer Architektur-Layer, keine neue Transport-Integration, keine
  Go-Struct-Änderung (beide Felder liegen opak in bereits generisch gemergten Config-Blobs).
  Der Redirect bleibt innerhalb der bestehenden `NotificationService`-Dispatch-Schicht.

## Test Coverage

Tests in `tests/tdd/` (Verhalten-benannt, nicht issue-nummeriert; Kern-Schicht deterministisch,
keine Mocks als Verhaltensnachweis — echte Fixture-Trips/-Presets, echte Renderer-Aufrufe):

- `test_telegram_kurzstil_trip_briefing.py` — AC-1, AC-2: Default bleibt reich; aktivierter
  Schalter liefert `sms_text`-identischen Telegram-Body ohne Bubbles/Knöpfe
- `test_telegram_kurzstil_trip_alert.py` — AC-3, AC-4: Abweichungs-Alarm UND amtliche
  Trip-Warnung liefern im Kurzstil den SMS-Text statt HTML/Bubble-Text
- `test_telegram_kurzstil_compare_official_alert.py` — AC-5, AC-6: amtliche Compare-Warnung
  im Kurzstil korrekt umgeleitet; reguläre Compare-Briefings/-Alarme bleiben unverändert
  E-Mail-only
- `test_telegram_kurzstil_parse_mode.py` — AC-7: Redirect-Aufruf nutzt `parse_mode=None`,
  auch bei Sonderzeichen im Text (kein API-Fehler)
- `test_telegram_style_config_roundtrip.py` — AC-8, AC-9: RMW-Roundtrip für
  `TripReportConfig.telegram_style` und `ComparePreset.display_config["telegram_style"]`
- `test_telegram_kurzstil_multi_user_isolation.py` — AC-10: zwei Nutzer, getrennte
  Schalter-Zustände, keine Vermischung
- Frontend: geteilter Komponenten-Test für `VTBriefingChannels.svelte`/`AlarmeTab.svelte`
  unter `context="route"` und `context="vergleich"` — AC-11

## Changelog

- 2026-07-15: Initial spec created — Issue #1260
