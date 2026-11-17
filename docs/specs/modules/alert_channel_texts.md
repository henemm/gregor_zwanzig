---
entity_id: alert_channel_texts
type: module
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: 2986-alarmvorschau-versandprojektion
issue: 2986
tags: [alerts, refactoring, vorschau, versand, ortsvergleich]
---

# Alert Channel Texts (geteilter Baustein Alarm-Vorschau und Versand)

## Approval

- [ ] Approved

## Purpose

Die Alarm-Vorschau des Ortsvergleichs baut Nachricht und Kanaltexte (Betreff, Mail, SMS, Telegram-Blasen) heute neben dem Versand noch einmal nach. Dieses Modul ist die einzige Stelle fuer Nachrichtenbau, Kanal-Rendern, SMS-Limit und Telegram-Plan; Vorschau und Versand rufen es gemeinsam auf (Paar P05 aus #1986, Issue #2986). Reines Refactoring: das fuer Nutzer sichtbare Verhalten bleibt byte-gleich.

## Source

- **File:** `src/services/alert_channel_texts.py` (neu)
- **Identifier:** `build_deviation_message`, `build_onset_message`, `render_channel_texts` (liefert `AlertChannelTexts`), `plan_telegram` (liefert `TelegramPlan`), `official_header_texts`, `official_telegram_text`

> **Schicht:** Python-Core (`src/services/`). Kein Frontend, keine Go-API betroffen.
>
> **Trip/Ortsvergleich-Teilung:** Der Baustein bedient beide Seiten. `_dispatch_alert_message` ist weiter der gemeinsame Dispatcher fuer Trip-Delta, Trip-Radar, Compare-Delta, Compare-Radar (ADR-0011, ADR-0021); Trip-Pendant der Vorschau (`validator_render_service.render_alert_preview`) ist nicht Gegenstand (Trip-Bericht: #2983).
>
> **Mandantentrennung:** Keine Nutzerdaten werden bewegt oder gespeichert; `user_id` laeuft unveraendert durch die bestehenden Aufrufer. Es entsteht kein neuer datenbewegender Endpoint.
>
> **Kanaele:** Alle vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) behalten gleichen Inhalt in kanalgerechter Form; der Baustein aendert keinen Inhalt.

## Estimated Scope

- **LoC:** Diff ca. +300/-300, ueberwiegend verschobener Code; neuer Produktivcode netto unter 100; Netto-Bilanz ca. -140 in den Bestandsdateien. Rueckfall: Greift das LoC-Gate, wird der amtliche Teil (ca. 40 LoC) als Kind-Issue abgespalten und der Workflow auf Delta und Radar beschraenkt.
- **Files:** 5 (1 neu Produktiv, 2 Produktiv geaendert, 2 Tests, dazu Paritaetstest unveraendert)
- **Effort:** medium (Risiko MEDIUM: `_dispatch_alert_message` bedient auch Trip-Alarme)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_channel_texts.py` | CREATE | Reine Bausteine ohne I/O; SMS-Limit 140 lebt nur noch hier |
| `src/services/notification_service.py` | MODIFY | `send_multi_location_deviation_alert`/`_radar_alert` nutzen `build_*_message`; `_dispatch_alert_message` nutzt `render_channel_texts` und `plan_telegram`; amtliche Komposition und Telegram-Entscheidung ueber `official_*` |
| `src/services/compare_alert_preview_service.py` | MODIFY | `_deviation/_onset/_official/_channels` werden duenne Wrapper (Namen und Signaturen bleiben); Eigenbauten und `_SMS_LIMIT` entfallen |
| `tests/tdd/test_profil_ampel_kette.py` | MODIFY | Ratsche `DIENST_EINSTIEGE` angepasst (schrumpft) |
| `tests/tdd/test_alarmvorschau_versandbaustein.py` | CREATE | Struktur- und Wirkort-Tests |
| `tests/tdd/test_alert_preview_compare_paritaet.py` | KEEP | Bleibt als Regressionswaechter am Draht |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.alert.project` | module | `to_multi_point_alert_message`, `to_multi_location_onset_alert_message` |
| `output.renderers.alert.render` | module | `render_subject/email/sms/telegram` |
| `official_alerts` | module | `build_compare_official_alert_notices`, `render_official_alert_sms_with_allclears` |
| `app.ampel.resolve_ampel` | function | Ampel-Aufloesung (Ratsche DIENST_EINSTIEGE) |
| `utils.timezone` | module | `tz_for_coords`, `resolve_location_tz`, `local_fmt` |
| `notification_service` Helfer `_official_*` | functions | Schon geteilte amtliche Bausteine (lazy Import) |
| `compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` | modules | Aufrufer der Versand-Methoden |
| `api/routers/validator.py` | module | Einziger Produktiv-Aufrufer der Vorschau |
| `docs/specs/modules/shared_preview_tab.md` | spec | AC-17..19 Alarm-Vorschau = Versand |
| `docs/specs/modules/compare_channel_preview_dispatch.md` | spec | Kanal-Vorschau/Dispatch (#1270) |

## Implementation Details

Reihenfolge (jeweils mit grünem Schutznetz davor):

1. Schutznetz gruen: Paritaetstest (:338/:420/:512), Trip-Alarm-Tests, Teilzustellung #1467.
2. `render_channel_texts` aus dem Dispatcher ziehen (Betreff, Mail, SMS mit Limit 140 und Ortsnummern, Telegram-Text); zunaechst nur Versand umstellen.
3. `build_deviation_message` / `build_onset_message`: Versand und Vorschau umstellen. `stand_at` wird einmal dort gebildet (`local_fmt(now_utc, tz)`).
4. `plan_telegram`: Kurzform (= SMS-Text) VOR Auffaecherung je Ort (#1467 K-6); Blasen mit Label, parse_mode und `render()`. Die Versandschleife (try/except je Blase, `failed_count`, `telegram_fully_sent`, Teilzustellungs-Hinweis, RuntimeError bei "alle gescheitert") bleibt im Dispatcher.
5. Amtlich: `official_header_texts` (Reihenfolge Quelle, Betreff, Bodies, SMS) und `official_telegram_text` (pro Kanal lazy, keine eager Komposition).
6. Vorschau-Eigenbauten und `_SMS_LIMIT` entfernen; Ratsche `DIENST_EINSTIEGE` anpassen.

Festgelegte Detailentscheidungen:

- Zeitzone Delta: Versandvariante (`tz_for_coords` vom Punkt `groups[0]`). Die Vorschau liefert praktisch dieselben Koordinaten, daher kein sichtbarer Unterschied.
- Radar und amtlich: `resolve_location_tz(first) or UTC` auf beiden Seiten, unveraendert; ein `tz`-Override bleibt Versand-Parameter.
- `reference_at` bleibt nur im Versand (die Vorschau setzt es heute nicht) und wird bewusst nicht veraendert.
- Fehlerverhalten Vorschau: `render()` ohne try (heutiges Verhalten); die Unterscheidung `vergleich_keine_warnung` vs. `sent=False` bleibt in den Wrappern.
- Die Vorschau darf nie ueber `send_*` mit Senken laufen, weil der SMS-Zweig vorher das SMS-Tageskontingent reserviert; deshalb reine Render-Funktionen, die beide Seiten aufrufen.

## Expected Behavior

- **Input:** Positionen/Gruppen und Alarmdaten (Delta, Radar, amtliche Warnungen) wie bisher von den Aufrufern.
- **Output:** Betreff, HTML-/Text-Mail, SMS-Text (hoechstens 140 Zeichen mit Ortsnummern) und Telegram-Blasen, byte-gleich zum Stand vor dem Umbau, fuer Vorschau und Versand identisch.
- **Side effects:** Keine im Baustein selbst (kein I/O). Die Vorschau reserviert kein SMS-Kontingent und sendet nichts.

## Test Plan

Kern deterministisch, ohne Live-Netz und ohne Mocks. Nachweis am Draht mit den lokalen Telegram-/seven.io-Stubs und der Mail-Senke wie im bestehenden Paritaetstest.

- Neu: `tests/tdd/test_alarmvorschau_versandbaustein.py` (AC-2, AC-3, AC-4, AC-6, AC-8).
- Bestand als Regressionswaechter: `test_alert_preview_compare_paritaet.py` (AC-1), Trip-Alarm-Drahttests und Teilzustellung #1467 (AC-5), `test_profil_ampel_kette.py` (AC-7), dazu `test_fix_1767_nowcast_mehrort_kurzform.py`, `test_alert_hour_rows.py`, `test_fix_2598_ortsvergleich_alarm_kopfzeile.py`, `test_s1c4b_einstiege_loesen_das_abo_auf.py`, `tests/integration/test_alert_preview_kind_isolation.py`.
- Gezielter Vorher/Nachher-Lauf dieser Dateien, keine Vollsuite. Mutationsgegenprobe gemaess AC-3.
- Staging: Alarm-Vorschau Ortsvergleich im Editor und ein ausgeloester Ortsvergleich-Alarm liefern dieselben Texte wie vor dem Umbau.

## Definition of Done

- Alle ACs mit gruenen Tests belegt, Mutationsgegenprobe ohne ueberlebende Verfaelschung.
- Vorschau-Modul enthaelt keine eigenen Kanal-Aufbauten und kein `_SMS_LIMIT` mehr.
- Paritaetstest, Trip-Alarm-Tests und Ratsche gruen; alle 6 CI-Checks gruen.
- Staging-Nachweis erbracht, Prod-Deploy mit Selftest Exit 0.
- Nebenbefund Zeitzone liegt als #3120 vor.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit Alarm vom Typ Delta, Radar oder amtlich / When Vorschau und echter Versand erzeugt werden / Then sind Betreff, Mail-Text, SMS-Text und alle Telegram-Blasen byte-gleich zum Stand vor dem Umbau, und der bestehende Paritaetstest am Draht bleibt gruen.
  - Test: Ein Nutzer sieht in der Vorschau exakt das, was zugestellt wird (Paritaetstest `test_alert_preview_compare_paritaet.py` mit lokalen Telegram-/seven.io-Stubs und Mail-Senke).

- **AC-2:** Given der geteilte Baustein `alert_channel_texts` / When Nachrichtenbau, Kanal-Rendern, SMS-Limit 140 und Telegram-Plan (Kurzform vor Auffaecherung je Ort) geprueft werden / Then liegen sie nur dort, und das Vorschau-Modul ruft keinen Renderer und keine Projektion (`render_sms/telegram/email/subject`, `to_multi_*_alert_message`) direkt auf.
  - Test: AST-Strukturtest ueber Vorschau-Modul und Versandpfad in `test_alarmvorschau_versandbaustein.py`; geprueft wird der Aufrufgraph der Module, nicht ein Textinhalt.

- **AC-3:** Given eine Verfaelschung im geteilten Baustein (SMS-Limit 140 auf 139, Reihenfolge Kurzform/Auffaecherung, Ortsnummern oder Betreff) / When Vorschau-Test und Versand-Test laufen / Then werden beide Tests rot.
  - Test: Mutationsgegenprobe per String-Ersetzung im Baustein mit externer Sicherungskopie; je Mutation faellt mindestens ein Vorschau- und ein Versand-Test.

- **AC-4:** Given ein Telegram-Versand je Ort, bei dem das Rendern eines Orts mit echter kaputter Eingabe scheitert (wie #1467) / When der Versand laeuft / Then gehen die uebrigen Blasen raus, `telegram_fully_sent` ist False und der Teilzustellungs-Hinweis erscheint; scheitern alle Blasen, endet der Versand mit einem Fehler.
  - Test: Versandtest am Draht mit lokalem Telegram-Stub; Teil- und Gesamtausfall getrennt.

- **AC-5:** Given Trip-Delta und Trip-Radar ueber den gemeinsamen Dispatcher `_dispatch_alert_message` / When sie nach dem Umbau versendet werden / Then sind Betreff, Mail, SMS und Telegram byte-gleich zum Stand davor.
  - Test: Bestehende Trip-Alarm-Drahttests bleiben unveraendert gruen; Byte-Vergleich fuer Trip-Delta, Trip-Radar, Compare-Delta, Compare-Radar.

- **AC-6:** Given die Alarm-Vorschau des Ortsvergleichs / When sie aufgerufen wird / Then reserviert sie kein SMS-Tageskontingent und sendet auf keinem Kanal etwas.
  - Test: Vorschau-Aufruf mit echtem Kontingentspeicher: Zaehlerstand vorher gleich nachher, keine Anfrage an die lokalen Stubs.

- **AC-7:** Given die Ratsche `DIENST_EINSTIEGE` in `test_profil_ampel_kette.py` / When die Projektion in `build_deviation_message`/`build_onset_message` wandert / Then ist die Liste der Ampel-Einstiege kleiner als vorher (nur Schrumpfen) und der Ratschentest gruen.
  - Test: Ratschentest `test_profil_ampel_kette.py` mit angepasster exakter Einstiegsliste je Funktion.

- **AC-8:** Given Delta-Alarme mit gespeicherter Orts-Zeitzone / When Vorschau und Versand laufen / Then bleibt die Zeitzonen-Herleitung wie heute (`tz_for_coords`); `reference_at` wird weiter nur im Versand gesetzt.
  - Test: Vergleich der Uhrzeiten in Vorschau und Versand fuer einen Ort mit abweichender Orts-Zeitzone; Ergebnis identisch zum Stand vor dem Umbau.

## Known Limitations

- Nebenbefund, kein Teil dieser Spec: Delta-Alarm (Vorschau und Versand) nutzt `tz_for_coords` und ignoriert `SavedLocation.timezone`, Radar und amtlich nutzen `resolve_location_tz`. Ein Fix waere eine Verhaltensaenderung und wird als eigenes Issue #3120 gefuehrt.
- `reference_at` und der `official_notices`-Zweig bleiben ausschliesslich im Versand.
- Interne Signaturen von `_onset/_deviation` bleiben bestehen, weil Tests (`test_s1c4b_einstiege_loesen_das_abo_auf.py:516`) sie direkt aufrufen.
- Fallback bei LoC-Gate: amtlicher Teil als Kind-Issue abspalten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; bestaetigt ADR-0011 (ein Alarm-Renderer) und ADR-0021 (Rendering/Versand geteilt)
- **Rationale:** Reine Zusammenfuehrung doppelten Codes im Rahmen bestehender Entscheidungen; keine neue Entscheidungsflaeche.

## Changelog

- 2026-11-17: Initial spec created (Issue #2986, Paar P05 aus #1986)
