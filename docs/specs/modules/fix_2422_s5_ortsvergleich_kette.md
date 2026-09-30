---
entity_id: fix_2422_s5_ortsvergleich_kette
type: bugfix
created: 2026-09-30
updated: 2026-09-30
status: draft
version: "1.0"
tags: [testing, ortsvergleich, compare, kanaele, metrik-auswahl, slots, end-date, telegram-kurzstil, alarm, fix]
workflow: fix-2422-s5-ortsvergleich-kette
---

# Fix #2422 (Scheibe S5): Kette Ortsvergleich — Preset-JSON bis zum gesendeten Text je Kanal — Tests + Fix

## Approval

- [ ] Approved

## Purpose

Issue #2422 lautet „Konfiguration und Auslieferung nicht getestet!". S1–S4 haben diese Kette für
Trip-Briefings und Trip-Alarme geprüft. **Scheibe S5 prüft dieselbe Frage für den Ortsvergleich:**
Was im gespeicherten Vergleichs-JSON (`ComparePreset`) eingestellt ist, muss im tatsächlich
gesendeten Text je Kanal (E-Mail, Telegram, SMS, Premium-SMS) ankommen — Metrik-Auswahl je Kanal,
Kanal an/aus je Tarif, Morgen-/Abend-Slot, Laufzeit (`end_date`), Telegram-Kurzstil und die
Alarm-Kanäle für Abweichung, Radar und amtliche Warnungen. Bisher existiert für den Ortsvergleich
nur der reine Render-Test `test_compare_kanal_metriken.py` und Teilstücke (Weiche, Slot-Funktion,
Go-Handler), aber keine Kette „Datei → Loader → Resolver → Renderer → Transport-Aufzeichner".

**Ein bestätigter Produktfehler (nicht nur Testlücke):**

1. **Der Telegram-Kurzstil erreicht den Ortsvergleich-Versand nicht.** Der Alarme-Reiter des
   Ortsvergleichs bietet den Schalter „Telegram im SMS-Kurzstil" an (`AlarmeTab.svelte:538`, bindet
   an `display_config.telegram_style`, Sub-Text: „Telegram bekommt denselben kurzen Ein-Zeilen-Text
   wie SMS — ohne Knöpfe"). Die drei Alarmdienste lesen ihn (`compare_alert.py:267`,
   `compare_radar_alert.py:345`, `compare_official_alert.py:285` über
   `effective_compare_telegram_style`, `compare_alert_channels.py:65-74`). Das planmäßige
   Vergleichs-Briefing liest ihn **nie**: `send_one_compare_preset`
   (`scheduler_dispatch_service.py:640-644`) ruft `render_compare_telegram(...)` ohne Stilangabe
   auf, und `send_compare_report` (`notification_service.py:1240-1255`) hat keinen Stil-Parameter.
   Das Trip-Briefing dagegen honoriert denselben Schalter (`notification_service.py:674-686`).
   Ergebnis: derselbe Schalter, dieselbe Beschriftung, aber im Briefing des Ortsvergleichs
   wirkungslos — exakt das Fehlerbild aus #2422 („Editor zeigt X, Auslieferung macht Y"). Die
   Spec `feat_1260_telegram_kurzstil.md` AC-6 („regulärer Compare-Bericht bleibt E-Mail-only") ist
   seit #1270/#2275 überholt: das Compare-Briefing läuft längst über Telegram, SMS und Premium-SMS.
   AC-6 aus #1260 wird hiermit für den Briefing-Pfad ausdrücklich abgelöst (siehe Known
   Limitations).

**Zwei Dokumentations-/Kommentar-Fehler, die im selben Ticket bereinigt werden:**

- `docs/reference/api_contract.md:2217` behauptet „Bekannte Lücke: kann per PUT nicht auf nil
  zurückgesetzt werden (KL-7)". Der Handler löst den Sentinel `end_date: ""` bereits auf
  (`internal/handler/compare_preset.go:338-340`), Tests belegen das
  (`internal/handler/compare_preset_test.go:934`), und der Editor sendet ihn (Frontend-Test
  `versand_enddatum_ohne_ereignis_bleibt_wirksam.test.ts:69`).
- `frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts:26-27`
  nennt Premium-SMS „reiner Alarm-Kanal (#1745)". Seit #2275 ist Premium-SMS auch Versandkanal des
  Vergleichs-Briefings — mit dem Inhalt der SMS (Entscheidung unten).

**Entschiedene Produktfrage: Premium-SMS = Inhalt der SMS, gewollt.** Der Editor bietet die
kanalweise Metrik-Auswahl nur für E-Mail, Telegram und SMS an (`COMPARE_CHANNEL_IDS`,
`compareChannelMetricLayouts.ts:28`); `resolve_compare_render_options` baut die Kanal-Listen genau
für diese drei (`report_config_resolver.py:336-339`), und `send_compare_report` reicht denselben
`sms_text` an SMS und Premium-SMS (`notification_service.py:1331`, `:1349`). Es gibt keinen
Editor-Weg, der eine eigene Premium-Auswahl erzeugt. Ein evtl. vorhandener Eintrag
`channel_active_metrics["premium_sms"]` bleibt ohne Wirkung (AC-6).

**Alle vier Kanäle sind gleichrangig** (Epic #2133): die Kanalmatrix wird für Briefing und Alarme
mit demselben Maßstab geprüft; keiner gilt als nachrangig.

## Source

- **File (Python-Core, produktiv, geändert):**
  - `src/services/scheduler_dispatch_service.py:640-644` — Fix Telegram-Kurzstil (siehe
    Implementation Details, Fix 1)
  - `src/services/compare_alert_guard.py` (`is_silenced`) — Fix abgelaufene Laufzeit (AC-21):
    „`end_date` vergangen" gehört zur Stilllegungs-Regel der drei Alarmdienste
- **File (Python-Core, nur gelesen):**
  - `src/services/scheduler_dispatch_service.py:414-427,430-693` (`send_one_compare_preset`,
    `_effective_compare_briefing_channels`)
  - `src/services/compare_alert_channels.py:32-74` (Briefing-Kanalwahl, Kurzstil-Auflösung)
  - `src/services/report_config_resolver.py:303-304,336-339` (Kanal-Listen nur email/telegram/sms)
  - `src/output/renderers/compare_metric_ids.py:200-241` (`resolve_channel_enabled_metrics`)
  - `src/output/renderers/comparison.py:692-800` (`render_compare_telegram`, Zellen ohne Label mit
    ` · ` verbunden, `:751`), `:967-1050` (`render_compare_sms`)
  - `src/services/notification_service.py:1240-1370` (`send_compare_report`: E-Mail-Import zur
    Laufzeit `:1294`, `mail_type="compare"` `:1302`, Telegram `parse_mode=None` `:1314`, SMS-Gate
    `:1324-1337`, Premium-SMS `:1342-1364`), `:474-492` (`_sms_gate_reserve`),
    `:1372-1486` (`send_multi_location_official_alert`)
  - `src/services/compare_slot_scheduler.py:81-100,103-172` (Slots, Morgen-Versatz 0, Abend-Versatz 1)
  - `src/services/alert_channels.py:29-93,123-137,187-213` (geteilte Alarm-Kanalauflösung)
  - `src/services/alert_channel_threshold.py` (`split_by_threshold`)
  - `src/services/compare_alert.py:121-245`, `compare_radar_alert.py:140-168,335`,
    `compare_official_alert.py:100-128,279`, `compare_alert_guard.py:39-54`
  - `src/services/user_tier.py:78-91` (`sms_allowed`, `premium_sms_allowed`)
- **File (Go-API, nur gelesen — kein Produktivcode-Wechsel geplant):**
  - `internal/model/compare_preset.go:48` (`DisplayConfig` opake Map), `:91-99,107,115,123`
    (Kanal-/Alarm-Felder), `:130-134` (Slots, `EndDate *string`)
  - `internal/handler/compare_preset.go:70,292-354` (`applyComparePresetPatch`, Sentinel `:338-340`)
  - `internal/handler/briefing_subscription.go:174-197,205` (zweiter Schreibweg
    `PUT /api/briefings/{id}?kind=vergleich`), `internal/handler/config_merge.go:11-22`
    (`mergeConfigMap`, nur eine Ebene tief)
- **File (Frontend, nur Kommentar geändert):**
  `frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts:26-27`
- **File (Doku, geändert):** `docs/reference/api_contract.md:2217` (KL-7 streichen)
- **File (Test-Infrastruktur, erweitert):**
  - `tests/helpers/transport_mitschrift.py` — Aufzeichner zusätzlich auf
    `output.channels.email.EmailOutput` (Laufzeit-Import des Vergleichs), Sendung merkt sich
    zusätzlich `compare_hourly_enabled`
  - `tests/helpers/einstellung_auslieferung_orakel.py` — Vergleichs-Orakel (Kanalmenge aus rohem
    JSON, erwartete Metrik-Menge und -Reihenfolge je Kanal, Parser für Vergleichs-E-Mail,
    -Telegram, -SMS)
- **File (Test-Daten, neu):** `tests/fixtures/compare_kette/*.json` (rohe Preset-JSONs im
  Persistenzformat; dieselben Dateien lesen der Python- und der Go-Test)
- **File (Test, neu):**
  - `tests/tdd/test_compare_einstellung_auslieferung_kette.py` (Blöcke A, B, C, E-Python, F, G)
  - `tests/tdd/test_compare_alarm_einstellung_auslieferung_kette.py` (Block D)
  - `internal/handler/compare_preset_kette_test.go` (Block E-Go, Roundtrip)
- **Identifier:** `send_one_compare_preset`, `send_compare_report`, `resolve_channel_enabled_metrics`,
  `effective_compare_briefing_channels`, `effective_compare_telegram_style`, `presets_due_for_hour`,
  `effective_alert_channels`, `applyComparePresetPatch`, `mergeBriefingPatch`

> **Schicht-Hinweis:** S5 ist überwiegend Testcode. Produktiv geändert werden genau **zwei** Stellen im
> Python-Core (Fix 1 Kurzstil, `scheduler_dispatch_service.py`; Fix 2 Laufzeit, `compare_alert_guard.py`). Go-API und Frontend bekommen keine
> Verhaltensänderung; das Frontend nur einen Kommentar, die Doku eine Zeile. Der Go-Teil ist ein
> reiner Test der Persistenz (Roundtrip).
>
> **Keine Schema-Änderung:** Alle Felder existieren bereits (`display_config`, `end_date`,
> `send_*`, `alert_channels`, `alert_channel_thresholds`, `official_warnings`). Der
> Pre-Snapshot-Hook `data_schema_backup.py` greift nicht.
>
> **Mail-Renderer-Berührung:** Fix 1 berührt `scheduler_dispatch_service.py` (Versandentscheidung),
> nicht die Mail-Inhalts-Renderer. Ob der Renderer-Commit-Gate am konkreten Diff trotzdem greift,
> klärt `/50`. Der Compare-Mail-Validator (`email_spec_validator.py`, `X-GZ-Mail-Type: compare`) ist
> für die E-Mail-Abnahme auf Staging maßgeblich, nicht der Trip-Validator.

## Estimated Scope

- **LoC produktiv:** ~20–35 (Fix 1 Kurzstil, Fix 2 Laufzeit) plus 1 Doku-Zeile und 1 Kommentar
- **LoC Test:** ~900–1100 (Vergleichs-Orakel ~150–200; Aufzeichner-Erweiterung ~30; Python-Kette
  ~500; Alarm-Kette ~250; Go-Roundtrip ~150; Fixtures)
- **Files:** ~14 neu/geändert
- **Effort:** high — viele Fälle, aber kaum Produktivänderung
- **LoC-Limit:** vor `/40` `workflow.py status` prüfen und bei Bedarf
  `workflow.py set-field loc_limit_override 1200` setzen (nicht eigenmächtig auf eine Teilscheibe
  verengen).
- **Saubere Schnittkante (falls das Limit trotzdem reißt):** Block D (Compare-Alarm-Kette,
  AC-14 bis AC-22) liegt in einer **eigenen** Testdatei und hat keinen Produktivcode-Anteil. Er
  kann als Scheibe S5b abgetrennt werden, ohne Blöcke A–C, E–G zu berühren. Wird D abgetrennt, ist
  das im Sammel-Issue #2422 als offener Folgepunkt mit Verweis auf diese Spec zu vermerken, nicht
  still zu streichen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader` (`load_compare_presets`, `compare_preset_to_dict`) | Modul | Upstream — Preset-JSON muss über den echten Loader laufen, nie als Dict im Speicher gebaut |
| `send_one_compare_preset` | Modul | Einstieg des Briefing-Versands; im Test mit echter Preset-Datei aufgerufen |
| `NotificationService.send_compare_report` | Modul | Kanal-Fan-out; Transporte werden am Ausgang aufgezeichnet |
| `resolve_channel_enabled_metrics` / `resolve_compare_render_options` | Modul | Prüfling — **nie** Quelle der Erwartung (Spiegel-Test verboten) |
| `effective_compare_briefing_channels` (`compare_alert_channels.py`) | Modul | Briefing-Kanalwahl; strikt getrennt von den Alarm-Kanälen |
| `effective_alert_channels` / `split_by_threshold` (`alert_channels.py`, `alert_channel_threshold.py`) | Modul | Geteilte Alarm-Kanalauflösung; Block D |
| `CompareAlertService`, `CompareRadarAlertService`, `CompareOfficialAlertService` | Modul | Öffentliche Einstiege `check_all_compare_presets()` der drei Alarmarten |
| `presets_due_for_hour` (`compare_slot_scheduler.py`) | Modul | Slot-Fälligkeit inkl. `end_date` |
| `services.user_tier` (`sms_allowed`, `premium_sms_allowed`) | Modul | Tarif-Gates; Tarif je Nutzer über `frisches_profil(tier=...)` |
| `tests/tdd/_einstellung_auslieferung_fixtures.py` (`frisches_profil`) | Testhilfe | Isoliertes Nutzerprofil mit Tarif |
| `tests/helpers/transport_mitschrift.py` (S1–S4) | Testhilfe | Aufzeichner der vier Ausgänge |
| `tests/helpers/einstellung_auslieferung_orakel.py` (S1–S4) | Testhilfe | Orakel aus rohem JSON + statischem Katalog |
| `tests/tdd/test_compare_dispatch_channel_fanout.py` | Test-Vorbild | `_install_engine_and_snapshot_seams`, Preset-/Settings-Aufbau |
| `tests/tdd/test_kanal_an_aus_kette.py` (S3), `test_alarm_szenario_mandantentrennung.py` | Test-Vorbild | Kanalmatrix × Tarif; Zwei-Nutzer-Muster Python |
| `internal/handler/compare_preset_alert_channels_test.go:361` | Test-Vorbild | Zwei-Nutzer-Muster Go (`WithUser`) |
| ADR-0021 (geteilte Alarm-Auflösung), ADR-0046 (Schwelle regelt WIE, nicht OB), ADR-0049 (Premium-SMS als Kanal), ADR-0050 (Kanal darf nur abwählen), ADR-0077 (`alert_metric_channels`) | ADR | Grundlage der Erwartungen |
| Issue #2293 (Compare-`alert_channels`, CLOSED), #2275 (Premium-SMS im Briefing), #1260 (Telegram-Kurzstil), #1232 (Slots/`end_date`) | Issue | Voraussetzungen / Vorgeschichte |
| Sammel-Issue #1199 | Issue | Nur falls Nebenbefunde anfallen (keine bekannten Abweichungen dorthin schieben) |

## Implementation Details

### Fix 1 — Telegram-Kurzstil im Vergleichs-Briefing

In `send_one_compare_preset` wird der Telegram-Text vor dem Aufruf von `send_compare_report`
entschieden: liefert `effective_compare_telegram_style(preset)` den Wert `"kurzform"`, ist der
Telegram-Text **derselbe String** wie `sms_text` (Auswahl und Reihenfolge der SMS-Kanalliste);
andernfalls bleibt es bei `render_compare_telegram(...)`. Fehlender Schlüssel, leerer Wert und
unbekannte Werte lösen bereits auf `"rich"` auf (`compare_alert_channels.py:73-74`). Dieselbe
Regel wie im Trip (`notification_service.py:676-686`: Kurzstil sendet den SMS-Text). Beide
Render-Aufrufe bleiben innerhalb des `try`-Blocks (Fehlerpfad #1629). Übertragung und
`parse_mode=None` ändern sich nicht (`notification_service.py:1314`). Kein neuer Parameter an
`send_compare_report`.

Folge (dokumentiert, kein Fehler): unter Kurzstil hat die Telegram-Kanalauswahl
`channel_active_metrics["telegram"]` keine Wirkung auf das Briefing — der Text ist der SMS-Text,
genau wie im Trip.

### Testinfrastruktur

- **Mitschrift-Falle:** `send_compare_report` importiert `EmailOutput` zur Laufzeit aus
  `output.channels.email` (`notification_service.py:1294`). Der bisherige Aufzeichner patcht nur
  `ns.EmailOutput` (`transport_mitschrift.py:105`) und sieht die Vergleichs-Mail nie — ein Test
  gegen ihn wäre grün mit null Sendungen. Der Aufzeichner wird deshalb zusätzlich auf
  `output.channels.email.EmailOutput` gesetzt (`monkeypatch.setattr` auf das Modulattribut wirkt,
  weil der Import erst beim Aufruf passiert), mit der echten `send()`-Signatur samt
  `plain_text_body`, `mail_type` und `compare_hourly_enabled`.
- **Warum nicht `mail_sink`:** `send_compare_report` ruft den Sink nur mit
  `mail_sink(subject=..., body=html_body)` auf (`:1289`). Er trägt weder Klartext-Fassung noch
  `mail_type`. Header (Block G) und Klartext-Parsing sind darüber nicht beobachtbar. Die Tests
  nutzen daher den Aufzeichner; `mail_sink` bleibt für Fälle, die nur den HTML-Körper brauchen.
- **Vorbedingung:** jeder Test ruft `vorbedingung_pruefen(...)` für die erwarteten Kanäle, damit
  „0 Sendungen" nie grün wirkt (AC-29).
- **Vergleichs-Orakel** (neu in `einstellung_auslieferung_orakel.py`; die Trip-Parser passen nicht:
  Telegram des Vergleichs geht mit `parse_mode=None` und Zellen ohne Label `a · b · c`
  (`comparison.py:751`), die E-Mail ist eine transponierte Matrix mit Orten als Spalten):
  - Kanalmenge aus dem rohen `json.load` des Presets + Tarif + globale Sendefähigkeit
  - erwartete Metrik-Menge und -Reihenfolge je Kanal aus `display_config.active_metrics` und
    `channel_active_metrics` (Schnitt, Reihenfolge der Kanal-Liste) — **nicht** aus
    `resolve_channel_enabled_metrics`
  - Parser für Vergleichs-E-Mail (Übersichtszeilen je Metrik), Vergleichs-Telegram (Zellen je Ort)
    und Vergleichs-SMS (Kürzel/Wert), Zuordnung Metrik ↔ Text nur über den statischen Katalog
    (Label/Kürzel)
  - Fixture-Werte je Metrik paarweise verschieden, damit unbeschriftete Telegram-Zellen eindeutig
    zuzuordnen sind; Auswahlgröße innerhalb der Telegram-Grenze (7 Werte je Ort) und des
    SMS-Budgets, sonst verdeckt Kappung eine Reihenfolge-Verfälschung. Ein eigener Fall prüft die
    Kappung bewusst (AC-4).
- **Wetterdaten:** aufgezeichnetes Vergleichsergebnis über die Engine-Naht aus
  `test_compare_dispatch_channel_fanout.py::_install_engine_and_snapshot_seams`, kein Netz.
- **Tarif und SMS-Tageslimit:** je Nutzer `frisches_profil(tier=...)`; das SMS-Tageslimit
  (`sms_daily_limit`) wird je Nutzer explizit gesetzt bzw. geleert, damit `_sms_gate_reserve`
  nicht still blockt.
- **Zwei Nutzer:** jeder datenbewegende Test läuft mit zwei Nutzern (Python: `user_id`-Parameter,
  getrennte `data/users/<id>/`-Verzeichnisse; Go: `s.WithUser(...)`); nie `"default"`.
- **Geteilte Fixtures:** `tests/fixtures/compare_kette/*.json` liegen im Persistenzformat. Der
  Python-Test liest sie per `json.load` und legt sie ins Nutzerverzeichnis; der Go-Test liest
  dieselben Dateien als PUT-Körper und vergleicht die Datei auf der Platte.

## Expected Behavior

- **Input:** gespeichertes Vergleichs-JSON mit beliebiger Kombination aus `display_config`
  (`active_metrics`, `channel_active_metrics`, `hourly_metrics`, `telegram_style`), `send_telegram`,
  `send_sms`, `send_premium_sms`, `alert_channels`, `alert_channel_thresholds`,
  `alert_metric_channels`, `official_warnings`, `official_alert_triggers_enabled`,
  `radar_alert_enabled`, Slot-Feldern, `end_date`.
- **Output:** Je Kanal geht exakt das hinaus, was das JSON aussagt: die Kanalmenge nach Opt-in,
  Sendefähigkeit und Tarif; im Text je Kanal die Metrik-Auswahl (nur Abwählen gegenüber der
  Grundauswahl, Reihenfolge der Kanal-Liste); zur Slot-Stunde mit dem Zieltag des Slots; der
  Telegram-Text im Kurzstil identisch zur SMS; E-Mail mit Kennung `compare`.
- **Side effects:** ein Produktivcode-Fix (Fix 1), eine Doku-Zeile, ein Kommentar; erweiterte
  Testinfrastruktur; neue Fixtures und Testdateien.

## Acceptance Criteria

### Block A — `channel_active_metrics` je Kanal

- **AC-1 (Kanal darf nur abwählen):** Given ein über den Loader geladenes Preset mit
  `display_config.active_metrics` (Grundauswahl aus mehreren Größen, darunter Temperatur, Wind und
  Böen) und `channel_active_metrics` mit einem SMS-Eintrag ohne Wind sowie einem Telegram-Eintrag,
  der zusätzlich eine Größe nennt, die nicht in der Grundauswahl steht / When
  `send_one_compare_preset` das Briefing versendet / Then enthält der SMS-Text genau die
  Schnittmenge aus Grundauswahl und SMS-Eintrag, der Telegram-Text zeigt die fremde Größe nicht,
  und die E-Mail zeigt weiterhin die volle Grundauswahl — für jeden der drei Kanäle einzeln
  geprüft.
  - Test: `test_compare_einstellung_auslieferung_kette.py::test_kanal_darf_grundauswahl_nur_abwaehlen`;
    Erwartung aus rohem JSON und statischem Katalog, nicht aus `resolve_channel_enabled_metrics`.

- **AC-2 (kein Eintrag folgt der Grundauswahl):** Given ein Altbestand-Preset ohne
  `channel_active_metrics` (Feld fehlt) und ein Preset, in dem nur der Kanal-Schlüssel `sms`
  fehlt / When das Briefing versendet wird / Then zeigt jeder Kanal ohne eigenen Eintrag die
  vollständige Grundauswahl, und die Kanaltexte sind identisch zu einem Preset, das dieselbe
  Grundauswahl als expliziten Eintrag trägt. Fehlt zusätzlich `active_metrics` ganz, wird nicht
  geschnitten und der Versand läuft mit der Standardauswahl.
  - Test: `..::test_fehlender_kanal_eintrag_folgt_der_grundauswahl` (Vergleichslauf mit explizitem
    Eintrag als Gegenprobe).

- **AC-3 (leer heißt leer):** Given (a) ein Preset mit `channel_active_metrics.sms = []` bei
  nicht-leerer Grundauswahl und (b) ein Preset mit `active_metrics = []` und nicht-leeren
  Kanal-Einträgen / When das Briefing versendet wird / Then trägt im Fall (a) der SMS-Text keine
  einzige Metrik-Zelle, während E-Mail und Telegram die Grundauswahl zeigen, und im Fall (b) tragen
  alle drei Kanaltexte keine Metrik-Zelle; in beiden Fällen kommt die Sendung zustande (kein
  Abbruch, kein Rückfall auf die Grundauswahl).
  - Test: `..::test_leere_auswahl_bleibt_leer_und_faellt_nicht_auf_grundauswahl_zurueck`.

- **AC-4 (Reihenfolge aus der Kanal-Liste, Kappung trifft die hinteren):** Given ein Preset, in
  dem die Kanal-Liste für Telegram und SMS die Größen in anderer Reihenfolge nennt als die
  Grundauswahl, und ein zweites Preset, dessen Auswahl größer ist als die Telegram-Grenze von
  sieben Werten je Ort / When das Briefing versendet wird / Then erscheinen die Zellen im
  Kanaltext in der Reihenfolge der Kanal-Liste (nicht der Grundauswahl), und bei Überschreitung
  des Platzes entfallen die hinteren Größen der Kanal-Liste, nicht die vorderen; der Kanaltext
  weist die verdrängten Größen aus.
  - Test: `..::test_reihenfolge_der_kanal_liste_bestimmt_zellen_und_kappung`.

- **AC-5 (Kanal-Auswahl betrifft nur die Übersicht, nicht den Stundenverlauf):** Given ein Preset
  mit `channel_active_metrics.email` ohne eine Größe, die in `display_config.hourly_metrics`
  steht / When die E-Mail versendet wird / Then fehlt die Größe in der Übersichtstabelle, steht
  aber weiterhin im Stundenverlauf (`hourly_enabled` an); der Stundenverlauf folgt ausschließlich
  `hourly_metrics`.
  - Test: `..::test_kanalauswahl_aendert_den_stundenverlauf_nicht`.

- **AC-6 (Premium-SMS = Inhalt der SMS):** Given ein Preset mit `send_premium_sms`, `alert_channels`
  gesetzt und Premium-Tarif, einmal ohne und einmal mit einem Eintrag
  `channel_active_metrics["premium_sms"]`, der von `["sms"]` abweicht / When das Briefing
  versendet wird / Then ist der Premium-SMS-Text byte-identisch zum SMS-Text desselben Laufs, und
  der Eintrag `premium_sms` verändert weder den Premium- noch den SMS-Text gegenüber dem Lauf
  ohne diesen Eintrag.
  - Test: `..::test_premium_sms_text_ist_der_sms_text_und_ein_premium_eintrag_wirkt_nicht`.

### Block B — Kanal an/aus × Tarif

- **AC-7 (Kanalmatrix Briefing):** Given Presets mit allen Kombinationen aus `send_telegram`,
  `send_sms`, `send_premium_sms` (Premium mit gesetztem `alert_channels`), den Tarifen `free`,
  `standard` und `premium` sowie Telegram/SMS global sendefähig bzw. nicht / When das Briefing
  versendet wird / Then wird genau die Kanalmenge bedient, die das Orakel aus rohem JSON, Tarif
  und Sendefähigkeit ableitet: Telegram bei Opt-in und Sendefähigkeit; SMS bei Opt-in,
  Sendefähigkeit und Tarif `standard`/`premium`; Premium-SMS bei Opt-in und Tarif `premium`.
  - Test: `..::test_kanalmatrix_briefing_nach_optin_faehigkeit_und_tarif` (parametrisiert;
    Erwartung `erreichbare_compare_kanaele` im Orakel).

- **AC-8 (E-Mail immer an):** Given ein Preset, in dem alle `send_*`-Schalter fehlen oder falsch
  sind, auch mit einem Rohschlüssel `send_email: false` im JSON / When das Briefing versendet wird /
  Then geht die E-Mail hinaus und ist der einzige bediente Kanal (der Ortsvergleich speichert kein
  `send_email`, E-Mail bleibt immer aktiv).
  - Test: `..::test_email_ist_immer_aktiv_auch_bei_allen_schaltern_aus`.

- **AC-9 (Premium-SMS ohne `alert_channels` ist kein Briefing-Kanal):** Given ein Preset mit
  `send_premium_sms: true` und Premium-Tarif, einmal ohne den Schlüssel `alert_channels` und einmal
  mit `alert_channels` / When das Briefing versendet wird / Then bleibt Premium-SMS im ersten Fall
  aus (Altbestand: das Kennzeichen war eine Alarm-Absicht) und wird im zweiten Fall bedient.
  - Test: `..::test_premium_sms_ohne_alert_channels_ist_kein_briefing_kanal`.

- **AC-10 (Tageslimit sperrt kanal- und nutzerbezogen, fail-soft):** Given zwei Nutzer mit
  Premium-Tarif, bei Nutzer A ist das SMS-Tageslimit erschöpft, bei Nutzer B nicht / When beide
  Presets versendet werden / Then bekommt Nutzer A keine SMS und keine Premium-SMS (Sperrgrund im
  Ergebnis unter `blocked_channels`), seine E-Mail und sein Telegram gehen dennoch hinaus, und
  Nutzer B wird auf allen Kanälen bedient.
  - Test: `..::test_sms_tageslimit_sperrt_nur_den_betroffenen_nutzer_und_kanal`.

### Block C — Slots morgen/abend

- **AC-11 (Slot-Fälligkeit und Zieltag):** Given ein Preset mit `morning_enabled`, `morning_time`,
  `evening_enabled`, `evening_time` aus der Fixture-Datei und eine Ortszeit, die jeweils zur
  Morgen- bzw. Abend-Stunde passt / When `presets_due_for_hour` und danach
  `send_one_compare_preset` mit dem gelieferten Eintrag laufen / Then ist der Morgen-Slot mit
  Versatz 0 und Zieltag heute fällig, der Abend-Slot mit Versatz 1 und Zieltag morgen, und das
  Betreff-Datum der gesendeten E-Mail ist der Zieltag des Slots; ist ein Slot abgeschaltet, wird
  zu seiner Stunde nichts fällig; sind beide aus, ist das Preset nie fällig.
  - Test: `..::test_slots_morgen_abend_faelligkeit_zieltag_und_betreff_datum`.

- **AC-12 (Altbestand ohne Slot-Zeiten):** Given ein Preset ohne `morning_time`, einmal mit
  `schedule: "daily_evening"` und einmal mit `schedule: "daily"` / When die Fälligkeit bestimmt
  wird / Then ist im ersten Fall nur der Abend-Slot (18:00) und im zweiten nur der Morgen-Slot
  (06:00) fällig.
  - Test: `..::test_altbestand_ohne_slot_zeiten_faellt_auf_schedule_zurueck`.

- **AC-13 (Slot-Zeit im Ortstag, zwei Nutzer):** Given zwei Nutzer mit je einem Preset, dessen Orte
  in verschiedenen Zeitzonen liegen, und derselbe UTC-Zeitpunkt / When die Fälligkeit bestimmt
  wird / Then wird jedes Preset gegen die Ortszeit seines ersten auflösbaren Orts geprüft, und ein
  Preset des einen Nutzers beeinflusst die Fälligkeit des anderen nicht.
  - Test: `..::test_slot_stunde_gilt_in_der_ortszeit_des_presets_je_nutzer`.

### Block D — Compare-Alarm-Kette (Radar, amtliche Warnungen, Abweichung)

*Voraussetzung #2293 (Compare-`alert_channels`) ist erfüllt. Kanalauflösung über
`effective_alert_channels`; alle vier Kanäle gleichrangig. Testdatei
`test_compare_alarm_einstellung_auslieferung_kette.py`.*

- **AC-14 (Briefing- und Alarm-Kanäle sind getrennt):** Given ein Preset mit `send_telegram: true`,
  aber `alert_channels.telegram: false`, und ein zweites mit umgekehrter Belegung / When das
  Briefing und danach ein Alarm ausgelöst werden / Then geht Telegram im ersten Preset nur beim
  Briefing hinaus und im zweiten nur beim Alarm; Änderungen an den Briefing-Schaltern verändern
  die Alarm-Kanäle nicht und umgekehrt.
  - Test: `..::test_briefing_und_alarm_kanaele_sind_unabhaengig`.

- **AC-15 (Abweichungsalarm: Kanalmenge und Schwelle):** Given ein Preset mit `alert_channels`
  (mehrere Kanäle an), `alert_channel_thresholds` mit einer Schwelle, die für genau einen Kanal
  eine Änderung unterdrückt, `alert_metric_channels` mit abweichender Kanal-Auswahl für eine
  Metrik und je Nutzer verschiedenem Tarif / When `CompareAlertService.check_all_compare_presets`
  eine Änderung meldet / Then bedient der Aufzeichner exakt die aus Überschreibung, Metrik-Union,
  Schwelle und Tarif abgeleitete Kanalmenge (E-Mail, Telegram, SMS, Premium-SMS gleich streng
  geprüft), und die beiden Nutzer bekommen jeweils ihre eigene Menge.
  - Test: `test_compare_alarm_einstellung_auslieferung_kette.py::test_abweichungsalarm_kanalmenge_schwelle_und_tarif`.

- **AC-16 (Radar-Alarm: Standard AUS, dann Kanalmenge und Schwelle):** Given ein Preset ohne
  `radar_alert_enabled`, eines mit `radar_alert_enabled: true` und `alert_channels`, und eine
  Radar-Lage knapp unter bzw. knapp über der eingestellten Kanal-Schwelle / When
  `CompareRadarAlertService.check_all_compare_presets` läuft / Then bleibt das erste Preset ohne
  jeden Abruf und ohne Versand, das zweite liefert unterhalb der Schwelle nichts und oberhalb an
  genau die aufgelösten Kanäle (alle vier gleichrangig); ein pausiertes oder archiviertes Preset
  schweigt.
  - Test: `..::test_radar_alarm_standard_aus_und_kanalmenge_mit_schwelle`.

- **AC-17 (Amtliche Warnung: Schalter-Vorrang und Kanalmenge):** Given Presets mit
  (a) `official_warnings.enabled: true` und `official_alert_triggers_enabled: false`,
  (b) `official_warnings.enabled: false` und `official_alert_triggers_enabled: true`,
  (c) `official_warnings: {}` und `official_alert_triggers_enabled: false`,
  (d) ohne beide Felder / When `CompareOfficialAlertService.check_all_compare_presets` eine
  amtliche Warnung meldet / Then wird in (a) und (d) ausgeliefert, in (b) und (c) nicht (aktueller
  Schalter hat Vorrang, ein leerer Block zählt als nicht migriert); die Auslieferung geht an die
  aus `alert_channels` und Tarif aufgelöste Kanalmenge auf allen vier Kanälen. Der Vorab-Filter,
  der beim Trip den Alarm verschluckt (S4), existiert im Ortsvergleich nicht — dieser Test
  bewacht das.
  - Test: `..::test_amtliche_warnung_schalter_vorrang_und_kanalmenge`.

- **AC-18 (Telegram-Kurzstil in allen drei Alarmpfaden):** Given ein Preset mit
  `display_config.telegram_style: "kurzform"` und Telegram in `alert_channels` / When ein
  Abweichungs-, ein Radar- und ein amtlicher Alarm ausgelöst werden / Then ist der Telegram-Text
  in jedem der drei Pfade identisch zum SMS-Text desselben Alarms; mit `"rich"` bzw. fehlendem
  Schlüssel bleibt der ausführliche Telegram-Text.
  - Test: `..::test_alarme_honorieren_telegram_kurzstil`.

- **AC-19 (Alarm-Mandantentrennung):** Given zwei Nutzer mit je einem Preset, aber
  unterschiedlichen `alert_channels`, Schwellen und Tarifen / When beide Alarmdienste je Nutzer
  laufen / Then erreicht jeden Nutzer ausschließlich der eigene Alarm über seine eigene
  Kanalmenge; kein Preset und kein Zähler eines Nutzers wirkt auf den anderen.
  - Test: `..::test_alarm_kette_trennt_zwei_nutzer`.

- **AC-20 (Ruhezeit und Sperrzeit im Ortsvergleich-Alarm):** Given ein Preset mit
  `alert_quiet_from`/`alert_quiet_to` und `alert_cooldown_minutes` / When ein Abweichungsalarm
  innerhalb der Ruhezeit und ein zweiter innerhalb der Sperrzeit nach einem gesendeten Alarm
  ausgelöst wird / Then bleibt die Auslieferung in beiden Fällen aus und wird im Protokoll mit
  Grund vermerkt; außerhalb beider Fenster liefert derselbe Auslöser normal aus.
  - Test: `..::test_ruhezeit_und_sperrzeit_unterdruecken_den_compare_alarm`.

- **AC-21 (Fix: abgelaufener Ortsvergleich ist stumm — Briefing UND Alarme):** Given ein Preset mit
  `end_date` in der Vergangenheit (Europe/Vienna) und aktivem Radar-, amtlichem und Abweichungsalarm /
  When die drei Alarmdienste und der Briefing-Lauf laufen / Then liefert keiner von ihnen über
  irgendeinen Kanal aus und verbraucht keinen State (Melde-Gedächtnis, Sperrzeit, Tageszähler);
  ein Preset mit `end_date` heute oder in der Zukunft sowie ohne `end_date` (Feld fehlt) alarmiert
  unverändert. PO-Entscheidung 2026-09-30: „ein abgelaufener Ortsvergleich ist stumm" — gleiche Regel
  wie beim Trip (`trip_alert.py:941`). Fix: die eine Stilllegungs-Regel `compare_alert_guard.is_silenced`
  erhält das Merkmal „`end_date` vergangen" (ein Ort für alle drei Alarmdienste); der Briefing-Pfad
  behält seine eigene Prüfung. Die bisherige Zusicherung `fix_1594_alarm_vorlauf_sperre.md` AC-7
  („`end_date` vergangen ⇒ Alarm geht normal raus") ist für diesen Fall abgelöst; der zugehörige
  Bestandstest in `tests/tdd/test_compare_alert_briefing_imminent.py` wird auf „stumm" umgestellt.
  Zwei Nutzer: der abgelaufene Ortsvergleich des einen Nutzers berührt den aktiven des anderen nicht.
  - Test: `..::test_abgelaufener_ortsvergleich_ist_fuer_briefing_und_alle_alarme_stumm`.

- **AC-22 (Alarm-Kanäle: Premium-SMS in jeder Art):** Given ein Preset mit Premium-Tarif und
  `alert_channels.premium_sms: true` / When Abweichungs-, Radar- und amtlicher Alarm ausgelöst
  werden / Then wird in allen drei Arten Premium-SMS bedient; bei Tarif `standard` in keiner.
  - Test: `..::test_premium_sms_ist_alarmkanal_in_allen_drei_arten_nur_im_premium_tarif`.

### Block E — `end_date`-Sentinel und Roundtrip von `display_config`

- **AC-23 (Sentinel löscht das Enddatum auf beiden Schreibwegen):** Given zwei Nutzer mit je einem
  Preset mit gesetztem `end_date` / When Nutzer A per `PUT /api/compare/presets/{id}` und
  Nutzer B per `PUT /api/briefings/{id}?kind=vergleich` das Feld mit `""` (Wert, den der Editor
  sendet) bzw. `null` überschreibt / Then fehlt der Schlüssel `end_date` in der jeweiligen Datei
  auf der Platte (roh gelesen, kein Feld mit leerem Wert), das Enddatum des anderen Nutzers bleibt
  unverändert, und ein PUT ganz ohne `end_date` erhält den alten Wert.
  - Test: `internal/handler/compare_preset_kette_test.go::TestEndDateSentinelAufBeidenSchreibwegenZweiNutzer`
    (ergänzt die vorhandenen Tests `compare_preset_test.go:934` und `:1047`, die nur den ersten
    Weg und einen Nutzer abdecken).

- **AC-24 (Python liest „Feld fehlt" als unbegrenzt):** Given die von Go geschriebene Datei ohne
  `end_date` (Fixture) / When der Loader das Preset liest und `presets_due_for_hour` zur Slot-Stunde
  läuft / Then ist der geladene Wert `None` (geprüft mit `is None`, nicht wahrheitswertig), das
  Preset ist fällig, und ein Preset mit `end_date` von gestern (Ortstag) ist nicht fällig, eines
  mit `end_date` von heute ist fällig.
  - Test: `test_compare_einstellung_auslieferung_kette.py::test_fehlendes_end_date_heisst_unbegrenzt_und_grenztag_ist_faellig`.

- **AC-25 (Roundtrip `display_config.channel_active_metrics` in Go):** Given ein Preset-Körper aus
  der geteilten Fixture mit `display_config.channel_active_metrics` (Einträge für `email`,
  `telegram`, `sms`, ein bewusst leerer Eintrag `[]`, ein fehlender Kanal, ein Fremdschlüssel
  `premium_sms`) / When er per PUT geschrieben und per GET sowie roh von der Platte gelesen wird /
  Then sind Schlüssel, Reihenfolge der Listen, der leere Eintrag `[]` (nicht `null`, nicht fehlend)
  und der Fremdschlüssel unverändert erhalten; ein PUT, der `display_config` ohne
  `channel_active_metrics` sendet, lässt die gespeicherte Map unberührt (Merge auf
  `display_config`-Ebene); zwei Nutzer sehen nie die Map des anderen.
  - Test: `compare_preset_kette_test.go::TestDisplayConfigChannelActiveMetricsRoundtripZweiNutzer`.

- **AC-26 (Teil-Map ersetzt die Map — Wirkung wird festgehalten):** Given ein Preset mit Einträgen
  für alle drei Kanäle / When ein PUT `channel_active_metrics` mit nur einem Kanal sendet / Then
  besteht die gespeicherte Map danach aus genau diesem Kanal (der Merge greift nur eine Ebene tief,
  `config_merge.go:18`), und der Python-Versand behandelt die fehlenden Kanäle als „folgt der
  Grundauswahl" (AC-2). Der Editor sendet stets die vollständige Map
  (`compareChannelMetricLayouts.ts:79`), sodass kein Editor-Speichern Kanäle verliert. Der Test
  hält dieses Verhalten fest, damit eine spätere Änderung am Merge bewusst geschieht.
  - Test: `compare_preset_kette_test.go::TestTeilMapChannelActiveMetricsErsetztDieMap`.

- **AC-27 (Doku stimmt mit dem Handler überein):** Given `docs/reference/api_contract.md` / When der
  Abschnitt zu `end_date` gelesen wird / Then beschreibt er den Lösch-Sentinel (`""` löscht,
  fehlendes Feld erhält, ungültiges Datum liefert 400) und enthält die Aussage „kann per PUT nicht
  auf nil zurückgesetzt werden (KL-7)" nicht mehr.
  - Test: `..::test_api_contract_beschreibt_end_date_sentinel` mit Markierung
    `# doc-compliance-test` (einzige erlaubte Dateiinhalt-Prüfung).

### Block F — Telegram-Kurzstil im Briefing (Fix)

- **AC-28 (Fix: Kurzstil erreicht das Briefing):** Given zwei Nutzer mit je einem Preset mit
  Telegram-Opt-in, Nutzer A mit `display_config.telegram_style: "kurzform"`, Nutzer B mit
  `"rich"` / When das Briefing beider Presets versendet wird / Then ist der Telegram-Text von
  Nutzer A byte-identisch zum SMS-Text desselben Laufs (ohne Knöpfe, `parse_mode=None`), und der
  Telegram-Text von Nutzer B ist der ausführliche Vergleichstext mit Ortsblöcken; fehlender
  Schlüssel, leerer Wert und unbekannter Wert verhalten sich wie `"rich"`. Vor dem Fix ist der
  Telegram-Text von Nutzer A ausführlich — der Test ist rot vor, grün nach dem Fix.
  - Test: `..::test_telegram_kurzstil_erreicht_das_vergleichs_briefing_je_nutzer`.

### Block G — Mail-Kennung und Beobachtbarkeit

- **AC-29 (Kennung `compare` und Klartext an der Naht):** Given ein Briefing-Lauf über den
  erweiterten Aufzeichner / When die E-Mail hinausgeht / Then trägt die aufgezeichnete Sendung
  `mail_type == "compare"` (nicht `trip-briefing`, nicht leer), einen nicht-leeren Klartext-Körper
  und das Kennzeichen `compare_hourly_enabled` passend zum Preset; die HTML-Fassung enthält die
  Vergleichsmatrix mit den Orten des Presets.
  - Test: `..::test_vergleichs_mail_traegt_kennung_compare_klartext_und_stundenkennzeichen`.

- **AC-30 (Null-Sendungen sind nie grün):** Given ein Aufzeichner, der wegen nicht installiertem
  Laufzeit-Patch keine Vergleichs-Mail sieht / When `vorbedingung_pruefen` für den E-Mail-Kanal
  läuft / Then schlägt sie mit einer Fehlermeldung fehl, statt eine leere Sendungsliste als
  bestanden zu werten; jeder Test dieser Spec ruft die Vorbedingung vor seinen Zusicherungen.
  - Test: `..::test_vorbedingung_schlaegt_bei_null_sendungen_an`.

## Test-Plan

Kern-Schicht (deterministisch, ohne Netz), Ausführung mit benannten Testdateien:
`tests/tdd/test_compare_einstellung_auslieferung_kette.py`,
`tests/tdd/test_compare_alarm_einstellung_auslieferung_kette.py` und Go
`internal/handler/compare_preset_kette_test.go`.

**Regeln**

- Erwartung ausschließlich aus rohem `json.load` der Fixture-Datei und dem statischen Katalog
  (`tests/helpers/einstellung_auslieferung_orakel.py`), nie aus `resolve_channel_enabled_metrics`,
  `effective_compare_briefing_channels` oder `effective_alert_channels` (Spiegel-Test).
- Preset-Datei ins Nutzerverzeichnis schreiben, echter Loader; kein Dict im Speicher.
- Jeder datenbewegende Test mit **zwei Nutzern** (Python `user_id`, Go `WithUser`).
- Tarif über `frisches_profil(tier=...)`; SMS-Tageslimit je Nutzer explizit setzen.
- Aufzeichner statt Mock: echte Klassen mit echten `send()`-Signaturen, auf `ns.*` **und**
  `output.channels.email.EmailOutput`; `vorbedingung_pruefen` vor jeder Zusicherung.
- `end_date`: Python `is None`, Go `EndDate == nil` bzw. Schlüssel roh nicht vorhanden; nie
  wahrheitswertig prüfen.
- Testdateien nach Verhalten benannt; Prüfling relativ zur Testdatei aufgelöst.

**Rot vor dem Fix:** AC-28 (Kurzstil), AC-21 (abgelaufene Laufzeit) und AC-27 (Doku). Alle übrigen ACs sichern den Ist-Stand ab
und sind mit dem ersten Lauf grün, sofern die Analyse stimmt; scheitert einer, ist das ein Fund
und wird im selben Ticket gefixt (nicht als Ausnahme geführt).

**Live-Schicht (nur `/e2e-verify` auf Staging):** Vergleichs-Test-Preset mit Test-Postfach, dann
`uv run python3 .claude/hooks/email_spec_validator.py` (Header `X-GZ-Mail-Type: compare`); nur bei
Exit 0 gilt „E2E bestanden". Der Trip-Validator ist hier der falsche.

### Mutations-Gegenprobe (Pflichtliste für den Adversary)

Mutationen nur per String-Ersetzung mit externer Sicherungskopie. Für jede Verfälschung muss der
genannte Test rot werden; wird keiner rot, ist das ein Fund.

| Verfälschung | Muss fangen |
|---|---|
| `resolve_channel_enabled_metrics`: Schnitt (`:240-241`) durch Vereinigung/Kanal-Liste ohne Filter ersetzen | AC-1 |
| ebenda: fehlender Kanal-Eintrag liefert `[]` statt Grundauswahl (`:230-231`) | AC-2 |
| ebenda: `[]` als „kein Eintrag" behandeln (Rückfall auf Grundauswahl) | AC-3 |
| ebenda: Ergebnis nach Reihenfolge der Grundauswahl statt der Kanal-Liste | AC-4 |
| `report_config_resolver.py:336-339`: Kanal-Schlüssel von `telegram` auf `sms` vertauschen | AC-1 |
| `report_config_resolver.py:338`: `"premium_sms"` in die Kanalliste aufnehmen | AC-6 |
| `scheduler_dispatch_service.py:572`: E-Mail nutzt `opts.enabled_metrics` statt Kanal-Liste | AC-1 |
| `scheduler_dispatch_service.py:565-573`: Stundenverlauf folgt der Kanal-Liste | AC-5 |
| `notification_service.py:1349`: Premium-SMS bekommt `telegram_text` oder gekürzten Text | AC-6 |
| `compare_alert_channels.py:47`: `can_send_telegram()` entfernen | AC-7 |
| `compare_alert_channels.py:49`: `sms_allowed` entfernen | AC-7, AC-10 |
| `compare_alert_channels.py:56-60`: `alert_channels is not None` entfernen | AC-9 |
| `compare_alert_channels.py:59`: `premium_sms_allowed` durch `sms_allowed` ersetzen | AC-7 |
| `compare_alert_channels.py:46`: E-Mail nur bei `send_email` | AC-8 |
| `notification_service.py:1326`: `_sms_gate_reserve` überspringen | AC-10 |
| Sperrgrund-Schlüssel eines Nutzers gilt für alle (gemeinsamer Zähler) | AC-10, AC-19 |
| `compare_slot_scheduler.py:170`: Abend-Slot gegen `morning_time` prüfen | AC-11 |
| `compare_slot_scheduler.py:39`: `ABEND_SLOT_VERSATZ = 0` | AC-11 |
| `compare_slot_scheduler.py:92`: `daily_evening`-Rückfall entfernen | AC-12 |
| `compare_slot_scheduler.py:138-141`: Zeitzone fest UTC statt Ortszone | AC-13 |
| `compare_slot_scheduler.py:147`: `<` durch `<=` | AC-24 |
| `alert_channels.py:135`: Briefing-Opt-ins statt `alert_channels` als Alarm-Basis | AC-14 |
| `compare_alert.py:307` bzw. `compare_radar_alert.py:335`: `split_by_threshold` umgehen | AC-15, AC-16 |
| `compare_radar_alert.py:154`: Standard `False` → `True` | AC-16 |
| `compare_official_alert.py:124-128`: Legacy-Feld vor `official_warnings` prüfen | AC-17 |
| `compare_radar_alert.py:345` / `compare_alert.py:267`: Stil nicht durchreichen | AC-18 |
| `compare_alert_guard.py`: „`end_date` vergangen" in `is_silenced` weglassen | AC-21 |
| `alert_channels.py:89-92`: Tarif-Gate entfernen | AC-15, AC-22 |
| Go `compare_preset.go:338-340`: Sentinel-Zeile entfernen | AC-23 |
| Go `briefing_subscription.go`: Sentinel im zweiten Weg auslassen | AC-23 |
| Go `compare_preset.go:134`: `omitempty` entfernen (leerer String bliebe stehen) | AC-23 |
| Go PUT ersetzt `display_config` statt zu mergen | AC-25 |
| Go: `s.WithUser(...)` durch festen Nutzer ersetzen | AC-23, AC-25 |
| `scheduler_dispatch_service.py` Fix 1 zurücknehmen | AC-28 |
| Fix 1: Stil aus falschem Nutzer/Preset lesen | AC-28 (Zwei-Nutzer-Fall) |
| `notification_service.py:1302`: `mail_type="compare"` → `"trip-briefing"` | AC-29 |
| Aufzeichner ohne Laufzeit-Patch | AC-30 |

## Known Limitations

- **Bewusste Kanal-Asymmetrien (kein Fehler):** unter Kurzstil wirkt `channel_active_metrics
  ["telegram"]` nicht (Text = SMS-Text, wie im Trip); Premium-SMS hat keine eigene Auswahl
  (AC-6); `metrics`/`alert_metric_channels` gelten nur beim Abweichungsalarm, nicht bei Radar und
  amtlich (dieselbe Regel wie S4 AC-8).
- **Kappung ist Absicht:** Telegram (sieben Werte je Ort) und SMS (Zeichenbudget) kürzen die
  Auswahl; AC-4 prüft, dass die hinteren Größen entfallen und dies ausgewiesen wird.
- **Laufzeit und Alarme (AC-21, PO-entschieden 2026-09-30):** ein abgelaufener Ortsvergleich ist
  für Briefing und Alarme stumm (wie beim Trip). Die Spec `fix_1594_alarm_vorlauf_sperre.md` AC-7
  ist für den Fall „`end_date` vergangen" abgelöst; Editor-Text `VTLaufzeitVergleich.svelte:76`
  („Der Versand läuft ohne Enddatum weiter") bleibt zutreffend.
- **`feat_1260_telegram_kurzstil.md` AC-6 wird für den Briefing-Pfad abgelöst:** die Aussage
  „reguläre Vergleichs-Berichte bleiben E-Mail-only" ist seit #1270/#2275 sachlich überholt; für
  Alarme (Abweichung/Radar) gilt der Kurzstil bereits.
- **Go-Merge nur eine Ebene tief:** `channel_active_metrics` wird bei Mitsenden als Ganzes ersetzt
  (AC-26); das ist heute unschädlich, weil der Editor die volle Map sendet.
- **Lokale Ausführung:** `uv run pytest` nur mit benannten Testdateien; lokale `.env` kann
  Host-abhängige Tests färben (Fixture `_ohne_dotenv` beachten).
- **Nebenbefunde** aus dem Adversary-Lauf, die keine Zusicherung dieser Spec berühren, gehen nach
  der Triage-Regel in #1199; bekannte Abweichungen zu den hier geprüften Zusicherungen werden im
  Ticket behoben.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue
- **Rationale:** S5 revidiert keine Architekturentscheidung. Fix 1 stellt Gleichbehandlung mit dem
  Trip-Briefing her (ADR-0021: geteilter Baustein, gleiche Regel) und folgt ADR-0049 (Premium-SMS
  trägt den SMS-Inhalt), ADR-0050 (Kanal darf nur abwählen) und ADR-0046 (Schwelle regelt das
  WIE). Die Entscheidung „Premium-SMS = SMS-Inhalt" ist durch den Editor-Stand belegt und wird
  hier per AC-6 festgeschrieben, nicht neu eingeführt.

## Changelog

- 2026-09-30: Initial spec created
