---
entity_id: feat_1484_night_temp_metric
type: module
created: 2026-08-06
updated: 2026-08-06
status: draft
version: "1.0"
tags: [metrics, sms, briefing, editor]
---

<!-- Issue #1484 — Nacht-Tiefsttemperatur getrennt wählbar (Folge aus #1415) -->

# Nacht-Tiefsttemperatur als eigene wählbare Wettergröße

## Approval

- [ ] Approved

## Purpose

Die Nacht-Tiefsttemperatur am Etappenziel (`N`-Kürzel, nur Abend-Briefing) hängt
heute an der Wettergröße „Temperatur" (`K`/`D`). PO-Entscheidung 2026-08-03:
*„N soll getrennt wählbar sein. Wer in der Hütte übernachtet, den interessiert
der Wert z.B. nicht."* Tages- und Nachttemperatur werden zwei unabhängige
Auswahl-Entscheidungen — wer im Zelt schläft, wählt die Nacht ohne den Tag;
wer die Hütte gebucht hat, umgekehrt.

## Source

- **File:** `src/app/metric_catalog.py` — NEUER Registereintrag `temperature_night`
  (`selectable=True`, Kategorie wie `temperature`, `dp_field="t2m_c"`, nur
  Aggregation `min`; Vorbild-Struktur: `wind_chill`, Zeilen 124–146).
  **NICHT** `temperature_cold` (Zeile 114–123) anfassen — das ist die interne
  Alarm-Pseudogröße mit `selectable=False` (#914), bei #1415 geprüft und verworfen.
- **File:** `src/output/renderers/sms_trip.py:114-118` — Bindungstabelle
  `SMS_MULTI_SYMBOLS_BY_METRIC` aufteilen: `"temperature": ("K","D")`,
  `"temperature_night": ("N",)`. Auswertung (`trip_report.py:290-307`) und
  Sichtbarkeitsentscheid (`tokens/builder.py:_visible`, Abend-Gate `:278-279`)
  bleiben unverändert — sie folgen der Tabelle.
- **File:** `src/output/renderers/compact_summary.py:168-183` — Nacht-Untergrenze
  der E-Mail-Kurzzusammenfassung an `temperature_night` statt `temperature` binden.
- **File:** `src/output/renderers/narrow.py:518-522` — Telegram-Abendübersicht:
  Nacht-Untergrenze folgt `temperature_night`.
- **File:** `src/services/trip_report_scheduler.py:~875` + `src/services/preview_service.py:206-217` —
  Nacht-Datenbeschaffung (`fetch_night_weather`) zusätzlich auslösen, wenn
  `temperature_night` gewählt ist (heute nur an `show_night_block` gekoppelt);
  sonst zeigt `N` bei ausgeschalteter Nacht-Stundentabelle still den Tageswert
  (Fallback in `sms_trip.py:241`).
- **File:** `src/app/models.py` (`UnifiedWeatherDisplayConfig`) bzw. Lesestelle
  `src/output/renderers/trip_metric_ids.py` — Bestandsdaten-Ableitung (s.u.).
- **Frontend:** KEINE neue Komponente. `WeatherMetricsTab` lädt den Katalog aus
  `GET /api/metrics` — der neue Eintrag erscheint automatisch als Checkbox in
  „Welche Metriken ins Briefing?". Zu prüfen: Ausschlussliste
  `corridorEditorState.ts:111` (`FRONTEND_EXCLUDED_CATALOG_IDS`) um
  `temperature_night` ergänzen (keine Alarm-/Korridor-Funktion, s. Abgrenzung).
- **Parität:** `internal/model/alert_metric_mapping.generated.json` regenerieren
  bzw. Paritätstest (`test_alert_metric_mapping_parity.py`) und Kürzel-Ratsche
  (`test_sms_token_symbol_register_ratchet.py`) bedienen.

## Estimated Scope

- **LoC:** ~80–120 produktiv (Katalogeintrag, Tabellen-Split, 3 Bindungen,
  Datenbeschaffung, Bestandsableitung) + Tests
- **Files:** ~8 produktiv
- **Effort:** medium

## Bestandsdaten (PFLICHT-Regel aus CLAUDE.md)

Gespeicherte Trips kennen `temperature_night` nicht. Ableitungsregel beim Lesen
(kein Migrationslauf, kein Replace):

> Fehlt in `display_config.metrics[]` ein Eintrag `temperature_night`, gilt die
> Größe als **aktiviert genau dann, wenn `temperature` aktiviert ist** —
> das heutige Verhalten bleibt exakt erhalten, niemand wird überrascht.

Erst ein bewusster Editor-Save schreibt den expliziten Eintrag — über den
bestehenden Merge-Pfad (`weather_config.go: mergeConfigMap`), nie Replace.
Gleiches gilt für den Altbestands-Fallback `DEFAULT_TRIP_METRIC_IDS`
(`trip_metric_ids.py`): dort zieht `temperature_night` mit ein, damit
Alt-Trips ohne `display_config` das `N` behalten.

## Abgrenzungen (bewusst NICHT in dieser Scheibe)

1. **`FN` (gefühlte Nacht) bleibt an „Gefühlte Temperatur"** (`wind_chill`,
   Kürzel `FN`/`FK`/`FD`/`WC`) gekoppelt. Eine symmetrische Trennung wäre ein
   Folgeschnitt — hier nicht enthalten, um den Schnitt klein zu halten.
2. **E-Mail-Nacht-Stundentabelle bleibt an `show_night_block`.** Sie ist eine
   Tabellen-Sektion (eigenes Bedienelement, `night_interval_hours`), keine
   Metrik-Spalte. Die neue Größe steuert den Nacht-**Wert** (SMS-Token,
   Kurzzusammenfassungs-/Telegram-Untergrenze), nicht die Tabelle.
3. **Keine Alarm-/Grenzwert-Funktion** für `temperature_night` (keine
   `alert_metrics`, kein `sms_threshold`, nicht im Korridor-Editor). Der
   Kälte-Alarm bleibt vollständig bei `temperature_cold` (#914).
4. **Ortsvergleich:** keine Sonderbehandlung; erscheint dort nur, was ohnehin
   über den geteilten Katalog ankommt (Gleichziehen ist #1463).
5. Die `?`-/Null-Form-Logik aus #1415 bleibt unverändert (Datenlücke bei
   gewählter Größe ⇒ `N-`, abgewählt ⇒ Token entfällt).

## Expected Behavior

- **Input:** Metrik-Auswahl im Editor (Reiter Wertebereiche), Kombinationen
  `temperature` × `temperature_night` je an/aus.
- **Output:** Abend-Briefing in SMS/E-Mail/Telegram zeigt Nachtwert genau dann,
  wenn `temperature_night` gewählt ist; `K`/`D` genau dann, wenn `temperature`
  gewählt ist. Morgen-Briefing zeigt nie `N` (Abend-Gate bleibt).
- **Side effects:** Nacht-Wetterabruf auch ohne `show_night_block`, wenn
  `temperature_night` gewählt.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit abgewählter „Nacht-Tiefsttemperatur" und gewählter „Temperatur" / When das Abend-Briefing als SMS erzeugt wird / Then enthält die SMS `K` und `D`, aber kein `N`-Token.
  - Test: SMS-Rendering mit realistischem Forecast-Fixture, Assertion auf Token-Menge.
- **AC-2:** Given ein Trip mit gewählter „Nacht-Tiefsttemperatur" und abgewählter „Temperatur" / When das Abend-Briefing als SMS erzeugt wird / Then enthält die SMS `N` mit dem Nacht-Minimum, aber weder `K` noch `D`.
  - Test: wie AC-1, umgekehrte Auswahl; Wert stammt aus dem Nachtfenster (Ankunft→06:00).
- **AC-3:** Given ein Trip mit gewählter „Nacht-Tiefsttemperatur" / When das Morgen-Briefing erzeugt wird / Then erscheint kein `N` — das bestehende Nur-Abends-Gate wirkt unverändert.
  - Test: bestehende Suite `test_night_temp_evening_only.py` bleibt grün, ergänzt um den neuen Metrik-Fall.
- **AC-4:** Given „Nacht-Tiefsttemperatur" abgewählt und „Temperatur" gewählt / When die Abend-E-Mail-Kurzzusammenfassung und die Telegram-Abendübersicht erzeugt werden / Then erscheint dort keine Nacht-Untergrenze; mit gewählter Nachtgröße erscheint sie — in beiden Kanälen.
  - Test: compact_summary- und narrow-Rendering, beide Richtungen.
- **AC-5:** Given der Metrik-Katalog / When `GET /api/metrics` abgerufen wird / Then enthält die Antwort „Nacht-Tiefsttemperatur" als wählbare Größe in der Temperatur-Kategorie, und `temperature_cold` bleibt weiterhin nicht enthalten.
  - Test: API-Test gegen den Router (FastAPI TestClient), Assertion auf beide IDs.
- **AC-6:** Given ein gespeicherter Bestands-Trip mit aktivierter „Temperatur" und ohne `temperature_night`-Eintrag / When der Trip geladen und das Abend-Briefing erzeugt wird / Then erscheint `N` wie vor der Änderung, und ein anschließender Config-Save erhält alle übrigen `display_config`-Felder (Merge, kein Replace).
  - Test: Roundtrip mit echtem Bestands-JSON-Fixture (Format wie `data/users/default/trips/*.json`).
- **AC-7:** Given ein gespeicherter Bestands-Trip mit deaktivierter „Temperatur" / When der Trip geladen wird / Then ist „Nacht-Tiefsttemperatur" abgeleitet AUS — es taucht kein neues Token unangefordert auf.
  - Test: Ableitungsregel beide Richtungen, inkl. `DEFAULT_TRIP_METRIC_IDS`-Altbestand.
- **AC-8:** Given „Nacht-Tiefsttemperatur" gewählt und die Nacht-Stundentabelle (`show_night_block`) ausgeschaltet / When das Abend-Briefing erzeugt wird / Then zeigt `N` das echte Nacht-Minimum (Ankunft→06:00), nicht still den Tageswert.
  - Test: Scheduler-/Preview-Pfad mit `show_night_block=False`, Nachtwert ≠ Tageswert im Fixture, Assertion auf den Nachtwert.
- **AC-9:** Given zwei verschiedene Nutzer mit entgegengesetzter Auswahl der Nachtgröße / When beide ihr Abend-Briefing erzeugen / Then wirkt jeweils nur die eigene Auswahl (keine Vermischung über `user_id`-Grenzen).
  - Test: zwei User-Verzeichnisse, zwei Renderings, gegenläufige Assertions.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md anwenden: Ist die Zusicherung dort geprüft, wo sie
WIRKT? Insbesondere AC-8 (Datenbeschaffung) und AC-6/AC-7 (Ableitung beim
Lesen, nicht nur im Katalog) sind die Stellen, an denen ein grüner Testlauf
ohne Wirkung möglich wäre. Mutations-Gegenprobe: Bindungstabelle zurück auf
`("N","K","D")` drehen — welche Tests fangen es?
