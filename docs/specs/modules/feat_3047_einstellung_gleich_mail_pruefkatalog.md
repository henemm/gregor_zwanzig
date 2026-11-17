---
entity_id: feat_3047_einstellung_gleich_mail_pruefkatalog
type: feature
created: 2026-11-15
updated: 2026-11-15
status: approved
version: "1.0"
issue: 3047
workflow: feat-3047-einstellung-gleich-mail
tags: [einstellungen, mail, pruefkatalog, reihenfolge, roh-einfach, validator, epic-3047]
---

# Einstellung = Mail: Prüfkatalog zuerst (Phase 1 von #3047)

## Approval

- [x] Approved (PO-Freigabe 2026-11-15)

## Purpose

Was ein Nutzer in „Inhalt je Kanal und Fläche“ einstellt (Auswahl, Reihenfolge, Roh/Einfach, Ein/Aus), muss in der zugestellten Mail genau so ankommen, in HTML und Klartext, bei Trip und Orten. Phase 1 baut zuerst einen maschinenlesbaren Prüfkatalog über den echten Lese- und Versandweg (Kern-Schicht, ohne Netz) plus eine Staging-Prüfung der echt zugestellten Mail und behebt damit die belegten Abweichungen; der große Umbau (Phase 2 bis 5) folgt erst, wenn der Katalog ihn absichert.

## Source

- **File:** `tests/tdd/test_einstellung_gleich_mail_trip.py`, `tests/tdd/test_einstellung_gleich_mail_orte.py`, `tests/tdd/test_einstellung_gleich_mail_fallliste.py`, `tests/tdd/test_einstellung_gleich_mail_editor_standard.py`, `tests/tdd/test_einstellung_gleich_mail_validatoren.py` (neu); Fehlerbehebung in `src/output/renderers/email/plain.py`, `frontend/src/lib/components/trip-detail/metricsEditor.ts`
- **Identifier:** Kettentests `render_trip_dict` (Trip) und `send_one_compare_preset` (Orte); Validator-Funktion `pruefe_soll` in beiden Mail-Validatoren

> **Schicht-Hinweis (Template-Pflicht):** Tests und Fixtures liegen unter `tests/` (Python) und `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/` (Vitest). Produktcode betroffen: Python-Core (`src/output/renderers/email/plain.py`, ggf. `compare_html.py`, `compare_outlook_metric_ids.py`), Frontend (`metricsEditor.ts`, `WeatherMetricsTab.svelte`, ggf. `OutlookLayoutControls.svelte`, `CompareHourlyLayoutControls.svelte`). Die Go-API ist nicht betroffen (Speicherformat unverändert, Merge-Verhalten bleibt, Read-Modify-Write).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung:** Der Katalog prüft beide Kontexte mit derselben Falllogik und denselben Dimensionen; Korrekturen am Renderer bleiben in den schon geteilten Bausteinen (`outlook.py`, `compare_outlook_metric_ids.py`). Es entsteht keine neue Komponente mit Pendant.
> - **Mandantentrennung:** jeder datenbewegende Fall läuft mit zwei verschiedenen Nutzern (AC-12); `user_id` stammt aus dem Profil des Fixtures, nie `"default"` für Nutzerdaten.
> - **Kanäle:** Phase 1 prüft den Kanal E-Mail (HTML, Klartext, Trip zusätzlich Kompaktformat). Telegram, SMS und Premium-SMS sind bereits durch `test_compare_einstellung_auslieferung_kette.py` und `test_einstellung_gleich_auslieferung.py` (Issue #2422) abgedeckt und werden in Phase 3 in denselben Katalog gezogen (Ausblick).

## Estimated Scope

- **LoC:** ca. +1800 Tests/Fixtures, ca. +80/-40 Produktcode (Behebungen), ca. +150 Validatoren
- **Files:** ca. 22
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/_einstellung_auslieferung_fixtures.py` (`render_trip_dict`, `segment`, `night_weather`) | test helper | Trip-Kette bis zur fertigen Mail (Zeile 222); wird importiert, nicht verändert |
| `src/services/scheduler_dispatch_service.py::send_one_compare_preset` | module | Orte-Kette; `mail_sink` (Zeile 783) |
| `src/services/notification_service.py` (`_sink_accepts_plain_body`, Zeilen 76 und 1580-1585) | module | `mail_sink` mit `plain_body` liefert HTML und Klartext derselben Mail |
| `tests/helpers/vergleichs_mail_fixture.py::build_result` | test helper | Wetterdaten für Orte, offline (Zeile 70) |
| `tests/helpers/einstellung_auslieferung_orakel.py` | test helper | statisches Register als Orakel, nie die Produkt-Resolver (Spiegel-Test-Verbot) |
| `tests/helpers/transport_mitschrift.py` | test helper | Aufzeichner der Kanal-Ausgänge |
| `src/output/renderers/compare_outlook_metric_ids.py` | module | Auflösung Ausblick (`resolve_trip_outlook_metrics` Zeile 197, `_erbe_grundauswahl` Zeile 151) |
| `src/output/renderers/email/helpers.py::resolve_metric_col_order` | module | Spaltenfolge der Trip-Tabellen (Zeile 305) |
| `src/output/renderers/email/outlook.py::build_outlook_row` | module | Ausblick-Zeilen offline erzeugen (Zeile 502) |
| `.claude/hooks/briefing_mail_validator.py`, `.claude/hooks/email_spec_validator.py` | hooks | Staging-Prüfung der echten Mail, `--eml` für deterministische Läufe |
| `docs/context/einstellungen_neu.md` §3.2 (W8, W11, W15, W19, WV5, WV9) und §5 Punkt 6 und 8 | Konzept | Sollbild „Inhalt je Kanal und Fläche“ |
| ADR-0050, ADR-0055, ADR-0095, ADR-0104 | ADR | Grundauswahl als Maximum, Ausblick ohne Kanal-Ebene, Kanal-Parität, Zweisprachigkeit |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/fixtures/einstellung_gleich_mail/fallliste_trip.json` | CREATE | Fälle Trip mit Status (Arbeitspaket A) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` | CREATE | Fälle Orte mit Status (Arbeitspaket B) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_validatoren.json` | CREATE | Fälle Staging-Schicht (Arbeitspaket C) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` | CREATE | Fälle Editor-Standard (Arbeitspaket D) |
| `tests/fixtures/einstellung_gleich_mail/editor_standard.json` | CREATE | von Hand gesetzte Eingaben und erwartete Standardfolgen je Liste, gelesen von pytest und Vitest |
| `tests/tdd/_einstellung_gleich_mail_trip_fixtures.py` | CREATE | `render_trip_mit_ausblick` (ergänzt `render_trip_dict` um Ausblick-Zeilen aus `build_outlook_row`) |
| `tests/tdd/test_einstellung_gleich_mail_trip.py` | CREATE | Kettentests Trip |
| `tests/helpers/einstellung_gleich_mail_trip.py` | CREATE | Parser Spaltenfolge/Zellen aus Trip-HTML und Klartext |
| `tests/tdd/test_einstellung_gleich_mail_orte.py` | CREATE | Kettentests Orte |
| `tests/helpers/einstellung_gleich_mail_orte.py` | CREATE | Parser Zeilenfolge/Zellen aus Orte-HTML und Klartext |
| `tests/fixtures/einstellung_gleich_mail/orte_*.json` | CREATE | gespeicherte Presets (rohes Persistenzformat) |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | CREATE | Wächter: Abdeckungsmatrix, Status, „fertig“ messbar (Arbeitspaket E) |
| `tests/tdd/test_einstellung_gleich_mail_editor_standard.py` | CREATE | Python-Seite des Standard-Abgleichs |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/editor_standard_gleich_mail.test.ts` | CREATE | Frontend-Seite des Standard-Abgleichs |
| `.claude/hooks/_soll_aus_konfiguration.py` | CREATE | Soll (Auswahl, Reihenfolge, Darstellung) aus dem rohen gespeicherten JSON, statisch, ohne Produkt-Resolver |
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | `--konfig PFAD`, `pruefe_soll` für Trip (HTML, Klartext, Kompakt) |
| `.claude/hooks/email_spec_validator.py` | MODIFY | `--konfig PFAD`, `pruefe_soll` für Orte; Kommentar Zeilen 939-945 präzisiert |
| `tests/tdd/test_einstellung_gleich_mail_validatoren.py` | CREATE | Validatoren per `--eml` gegen erzeugte Mails, positiv und negativ |
| `docs/reference/mail_validators.md` | MODIFY | `--konfig`, Soll-Regel, Auflösung des Verbots aus #1381 |
| `src/output/renderers/email/plain.py` | MODIFY | Nachttabelle mit `format_modes`; englische Festtexte über Katalog |
| `src/i18n/` (Katalog-Dateien DE und EN) | MODIFY | neue Schlüssel für die Klartext-Festtexte |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | MODIFY | Vorlage anwenden behält die Vorlagen-Reihenfolge |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | `applyPreset` ohne Prioritäts-Umsortierung |
| weitere Renderer-/Editor-Dateien | MODIFY (bedingt) | nur wenn ein Fall des Katalogs rot ist; je Datei ein Behebungspaket (siehe Parallelisierung) |

### Estimated Changes

- Files: ca. 22
- LoC: ca. +2000 / -40

## Implementation Details

### 1. Aufbau des Prüfkatalogs

Jeder Fall nimmt ein gespeichertes Konfigurations-JSON im Persistenzformat (rohe Datei, wie der Editor es ablegt), schickt es durch den echten Loader und den echten Versandweg und prüft die entstandene Mail gegen die Konfiguration. Das Orakel (Soll) wird aus dem rohen JSON und dem statischen Register abgeleitet, nie aus `resolve_*`-Funktionen des Produkts (sonst Spiegel-Test, verboten laut CLAUDE.md). Einzige Naht ist der Transport (`transport_mitschrift` bzw. `mail_sink` mit `plain_body`), kein `Mock()`, kein `patch()`.

- **Trip:** `render_trip_dict` (`tests/tdd/_einstellung_auslieferung_fixtures.py:222`) rendert Stundentabelle je Etappe und Nachttabelle; `multi_day_trend` ist dort nicht belegt (`TripReportRequest.multi_day_trend`, `notification_service.py:107`). Für den Ausblick baut das neue Fixture `render_trip_mit_ausblick` die drei Tageszeilen mit der reinen Funktion `build_outlook_row(..., trip_display_config=trip.display_config, report_type=..., context="route", ampel=...)` aus denselben Wetterpunkten. Die Spaltenauflösung läuft damit über den echten Pfad `resolve_trip_outlook_metrics` im Renderer (`trip_report.py:223`). Der Zeitplaner-Abruf (`trip_report_scheduler.py:2926`, braucht Netz) bleibt außen vor und ist in Known Limitations benannt.
- **Orte:** `send_one_compare_preset(..., mail_sink=...)` (`scheduler_dispatch_service.py:775`) mit einem Sink, der `plain_body` annimmt (`notification_service.py:1580-1585`), und Wetterdaten aus `tests.helpers.vergleichs_mail_fixture.build_result`. HTML und Klartext stammen so aus derselben Mail.
- **Formate:** Trip HTML, Klartext, Kompakt (`email_format = "compact"`, `models.py:1181`, `render_compact`); Orte HTML und Klartext.

### 2. Die Listen und was je Liste geprüft wird

| Liste (Konzept §5 Punkt 8) | Kontext | Fläche in der Mail |
|---|---|---|
| E-Mail-Liste, Stundentabelle Etappe | Trip | Spalten der Stundentabelle je Segment (`resolve_metric_col_order`, `html.py:533-537`, `plain.py:70-77`) |
| E-Mail-Liste, Nachttabelle | Trip | Spalten der Nacht-Stundentabelle am Ziel (`show_night_block`, `models.py:835`) |
| 3-Tages-Ausblick | Trip | `outlook_metrics` (`resolve_trip_outlook_metrics`) |
| Vergleichstabelle (E-Mail-Liste) | Orte | Zeilen je Metrik, Spalten je Ort (`enabled_metrics_by_channel["email"]`, `compare_metric_ids.py:251`) |
| Stundenverlauf je Ort („Details“) | Orte | `hourly_metrics`, `_visible_hour_metrics` (`compare_html.py:1017`) |
| 3-Tages-Ausblick | Orte | `resolve_compare_outlook_metrics` (`compare_outlook_metric_ids.py:227`) |

Geprüft wird je Liste und je Format (HTML und Klartext, Trip zusätzlich Kompakt):

1. **Auswahl:** genau die angehakten Metriken erscheinen, keine weitere (Spaltenköpfe bzw. Zeilenbeschriftungen aus dem Register).
2. **Reihenfolge exakt:** die Folge in der Mail ist gleich der gespeicherten Folge. Jede Folge muss ungleich der Katalogfolge sein, sonst beweist der Test nichts (Beispiele: Böen vor Temperatur vor Niederschlag vor Wind; Wind vor Temperatur; Umkehrung der Katalogfolge). Kein Vergleich nach Sortierung.
3. **Roh oder Einfach je Zeile:** Roh ist eine Zahl, Einfach ist Symbol, Ampelpunkt oder Wort. Der Test fixiert pro Metrik die erwartete Form im Orakel. Gewollte Ausnahmen werden im Fall ausdrücklich benannt, nicht stillschweigend übergangen:
   - Visibility hat im Ausblick keine Einfach-Form (#814 AC-5, `OUTLOOK_FRIENDLY_CAPABLE`, `metric_catalog.py:1141`).
   - Temperatur, gefühlte Temperatur und Gewitter haben im Ausblick keine Einfach-Form; Gewitter zeigt roh bereits das Stufenwort.
   - Im Klartext steht ein HTML-Ampelpunkt nie als Quelltext (`compare_outlook_metric_ids.py:516-520`); Einfach heißt dort das Wort bzw. Symbol aus derselben Zelle.
   - Trip-Stundentabelle: `build_format_modes` liefert für Ampel-fähige Metriken immer `raw` und der HTML-Ampelpunkt kommt aus `build_html_indicator_keys` (`email/__init__.py:140-144`, #814); der Klartext zeigt deshalb für diese Metriken die Zahl. Das ist eine gewollte Abweichung und steht als Status `ausnahme` mit Verweis in der Fallliste.
4. **Ortsreihenfolge (Orte):** die Spalten der Vergleichstabelle und die Abschnitte je Ort folgen `location_ids` des Presets (`order_locations_by_ids`).
5. **Ein/Aus:** Ausblick an/aus (Orte `outlook_enabled`, Trip `show_outlook` bzw. `multi_day_trend_reports`), Stundenverlauf an/aus (`hourly_enabled`), eine bewusst leere Auswahl lässt den Block entfallen (kein stiller Rückfall).
6. **Zusatzblöcke Trip:** `show_night_block` (Nachttabelle vorhanden/fehlt), `show_stage_stats` (Etappen-Kennzahlen), `show_yesterday_comparison` (Vortag-Zeile), `email_format` (full gegen compact: HTML-Teil leer, Klartext-Kompakttext).
7. **Grundauswahl-Kopplung:** (a) eine neu in die Grundauswahl aufgenommene Metrik erscheint in allen Listen, die „nie eingestellt“ sind (Ausblick, Orte-Übersicht, Stunden, Trip-Tabellen); (b) eine Liste nimmt nur aus der Grundauswahl: eine Metrik, die gespeichert in der Liste steht, aber aus der Grundauswahl abgewählt ist, erscheint nicht (ADR-0050, `_erbe_grundauswahl`, `resolve_channel_enabled_metrics`); bleibt nach dem Schnitt nichts übrig, gilt der dokumentierte Rückfall auf die volle Grundauswahl (kein Block-Verschwinden).
8. **Altbestand:** ein Konfigurations-JSON ohne die neuen Felder (`outlook_metric_formats`, `channel_layouts`, `hourly_metrics`, `outlook_metrics`) rendert byte-gleich zu einem eingefrorenen Golden (Muster `tests/fixtures/einstellung_auslieferung/`).
9. **Zwei Nutzer:** derselbe Fall mit zwei Profilen (`frisches_profil`), eigene Konfiguration und eigener Empfänger; beide Mails zeigen je ihre Folge, keine Vermischung.

### 3. Paarweise Kombinatorik statt Vollprodukt (Begründung)

Je Liste gibt es fünf Dimensionen: Auswahl-Muster (Teilmenge, alles, bewusst leer, nie eingestellt), Reihenfolge (Katalogfolge, Umkehrung, gemischt), Darstellung (alles Roh, gemischt, alles Einfach), Format (HTML, Klartext, Kompakt) und Kontext (Trip/Orte). Das Vollprodukt wären je Liste rund 108 Fälle mit sehr geringem Mehrwert. Die bekannten Fehlerklassen sind Ein- und Zwei-Faktor-Fehler: Reihenfolge ignoriert (Faktor Reihenfolge), Darstellung fehlt in einem Format (Faktor Darstellung mal Format, z. B. `plain.py:298` ohne `format_modes`), Grundauswahl nicht geschnitten (Faktor Auswahl-Muster). Paarweise Überdeckung (jedes Wertepaar zweier Dimensionen kommt mindestens einmal vor) erzeugt je Liste 9 bis 12 Fälle und fängt jeden solchen Fehler. Dazu kommen Einzelfälle für unabhängige Schalter (Ein/Aus, Zusatzblöcke, Altbestand, zwei Nutzer). Dass ein Drei-Faktor-Fehler durchrutschen könnte, ist ein offenes Restrisiko; die Mutations-Gegenprobe (AC-14) prüft, ob die Fälle die typischen Fehler tatsächlich fangen. Die Paare werden in der Fallliste nicht von Hand, sondern als Tabelle `dimensionen` im JSON geführt, der Wächter (AC-1) prüft die paarweise Überdeckung.

### 4. Fallliste (maschinenlesbar) und „fertig“ messbar

Fünf Teildateien (`fallliste_trip.json`, `fallliste_orte.json`, `fallliste_validatoren.json`, `fallliste_editor.json`, `fallliste_telegram.json` seit #3098), jede mit einem Objekt `dimensionen` und einer Liste `faelle`. Jeder Fall hat die Felder `id`, `liste`, `kontext`, `format` (html, klartext, kompakt), `pruefung` (auswahl, reihenfolge, darstellung, ortsreihenfolge, ein_aus, zusatzblock, grundauswahl, altbestand, zwei_nutzer, standard), `test` (Name der Testfunktion), `ac`, `befund` (z. B. `T4`, leer erlaubt) und `status`.

Zulässige Status: `gruen` (Test existiert und besteht), `rot_erwartet` (nur im RED-Artefakt, bis die Behebung da ist), `ausnahme` (gewollte Abweichung mit Begründung und Issue/ADR-Verweis), `offen_feature` (Konzept verlangt es, das Produkt kann es noch nicht, mit Issue-Verweis). Der Wächter `test_einstellung_gleich_mail_fallliste.py` liest alle fünf Dateien und prüft: (a) Abdeckungsmatrix, jede Kombination aus Liste und Format der Tabelle in Abschnitt 2 hat mindestens einen Fall je Prüfung auswahl und reihenfolge; (b) jeder Fall mit Status `gruen` verweist auf eine auffindbare Testfunktion (per `ast`, ohne Ausführung); (c) paarweise Überdeckung der `dimensionen`; (d) „fertig“ heißt: kein Fall `rot_erwartet`, jeder `ausnahme` und `offen_feature` trägt einen Verweis. Der Zähler (`gruen`, `ausnahme`, `offen_feature`) wird als Zeile ausgegeben und im PR genannt.

Bekannte Lücke, die als `offen_feature` in der Fallliste steht: Der Orte-Renderer kennt Roh/Einfach heute nur für den 3-Tages-Ausblick (`outlook_metric_formats`, `comparison.py:186`, `compare_html.py:1244`); für Vergleichstabelle und Stundenverlauf gibt es im Renderer keine Darstellungsform je Zeile (Grep auf `friendly`/`format_mode` in `comparison.py` ohne Treffer). Das Konzept verlangt sie (W11). Phase 1 dokumentiert das, behebt es nicht (Feature, Ausblick Phase 3).

### 5. Editor-Standard = Mail-Standard

Der Editor zeigt bei nie eingestellter Liste eine Standardfolge, die Mail gibt bei derselben Eingabe ebenfalls eine aus. Beide müssen gleich sein. Drei Stellen sind im Code getrennt abgeleitet und deshalb zu prüfen:

- Orte-Stundenverlauf: Backend `HOURLY_DEFAULT_METRIC_IDS` (Tupel, `compare_hourly_metric_ids.py:111`) gegen Frontend `defaultHourlyKeys` aus Katalog-Gruppenfolge (`CompareHourlyLayoutControls.svelte:91-93`). Gleichheit der Folge ist unbestätigt.
- Ausblick: Backend `_erbe_grundauswahl` bei `gespeichert is None` liefert die Grundauswahl in Folge von `dc.metrics` (Trip) bzw. in Folge der Übersicht (Orte); Frontend `OutlookLayoutControls.svelte` leitet aus `grundauswahl` ab (Zeilen 141-175).
- Trip-Tabellen: Backend fällt bei leerem `metrics` auf `DEFAULT_TRIP_METRIC_IDS` zurück (`trip_metric_ids.py:29`, Altbestand Fall A); Frontend baut die Anzeige aus dem Katalog.

Technik: eine von Hand gesetzte Datei `editor_standard.json` enthält je Liste die Eingabe (Katalog-Auszug, gespeicherter Zustand „nie eingestellt“ und zwei gespeicherte Zustände) und die erwartete Standardfolge (aus dem Konzept bzw. der freigegebenen Spec abgeleitet, nicht aus einer der beiden Implementierungen erzeugt). Der Vitest-Test lässt die echte Frontend-Ableitung mit dieser Eingabe laufen, der pytest-Test die echte Python-Auflösung; beide vergleichen gegen dieselbe erwartete Folge. Weicht eine Seite ab, wird genau ein Test rot, der benennt, welche Seite.

### 6. Staging-Schicht: Validatoren mit Soll aus der Konfiguration

Beide Validatoren bekommen `--konfig PFAD` (das rohe gespeicherte Trip-Briefing- bzw. Preset-JSON des Test-Nutzers, wie die API es liefert). Das neue Modul `.claude/hooks/_soll_aus_konfiguration.py` leitet daraus das Soll ab: Auswahl, Reihenfolge, Darstellung je Liste, Ein/Aus, Ortsreihenfolge, Zusatzblöcke. Es liest nur die rohe Datei und die Namen aus dem Register (`col_label`), nutzt keinen `resolve_*` des Produkts. `pruefe_soll(msg, soll, lang)` vergleicht dann Spaltenfolge je Stundentabelle, Nachttabelle, Ausblick-Kopf (Trip) bzw. Zeilenfolge der Vergleichstabelle, Spalten des Stundenverlaufs und Ausblick-Kopf (Orte), im HTML-Teil und im Klartext-Teil der zugestellten Mail. Für das Kompaktformat prüft der Trip-Validator die Reihenfolge der Kompakt-Tokens des Ausblicks. Ohne `--konfig` bleibt das bisherige Verhalten unverändert.

**Auflösung des Verbots in `email_spec_validator.py` (Zeilen 939-945):** Der Kommentar verbietet, die Spaltenfolge gegen die feste Kanon-Reihenfolge `_HOUR_COLUMNS_V2` zu prüfen. Begründung dort: Die Folge ist seit #1359 nutzerseitig frei einstellbar, die alte Projektion auf die Kanon-Folge lehnte korrekte Mails ab und blockierte das Renderer-Commit-Gate #811. Dieses Verbot bleibt voll in Kraft: eine feste Folge wird weiterhin nie vorausgesetzt. Neu ist, dass das Soll nicht mehr fest ist, sondern aus der gespeicherten Konfiguration genau dieses Nutzers stammt. Eine Mail mit der vom Nutzer gewählten Folge besteht damit immer, eine mit abweichender Folge nicht. Das Gate kann dadurch keine korrekte Mail mehr ablehnen. Der Kommentar wird um diese Regel ergänzt („Reihenfolge nur gegen die gespeicherte Konfiguration, nie gegen eine feste Folge“), ein Test sichert beide Richtungen (AC-11).

Der deterministische Nachweis der Validatoren läuft in der Kern-Schicht per `--eml` gegen Mails aus den Kettentests (positiv: stimmt; negativ: Folge vertauscht, Spalte fehlt, Klartext ohne Ausblick). Der echte Staging-Lauf gegen die zugestellte Mail ist Teil von `/e2e-verify` (Live-Schicht).

### 7. Behebung der belegten Abweichungen

Befunde aus #3047 (Abgleich mit dem Issue-Wortlaut durch den Orchestrator, 2026-11-15):

| Befund | Beleg | AC |
|---|---|---|
| T1 Trip-Ausblick ohne `outlook_metrics` in Katalogfolge statt eingestellter Folge | `compare_outlook_metric_ids.py:221-222` nimmt die Array-Folge (Katalog) statt `order`; Editor zeigt `buckets.primary` nach `order` (`WeatherMetricsTab.svelte:1946`, `OutlookLayoutControls.svelte:169-176`) | AC-4, AC-13 |
| T2 Trip-Nachttabelle Klartext ignoriert Roh bei `wind_direction` | `plain.py:298-299` ohne `format_modes`, Etappentabelle und HTML übergeben es | AC-15 |
| T3 Global neu eingeschaltete Metrik / geänderte globale Folge erreicht ein einmal bearbeitetes E-Mail-Layout nicht | `channelMetricLayouts.ts:97-124` überträgt nur Abwahlen; widerspricht Konzept („steht in allen Listen“) | AC-10 |
| T4 Vorlagen verlieren Reihenfolge | `WeatherMetricsTab.svelte:729-733` → `autoAssign` (`metricsEditor.ts:272-289`); `internal/handler/metric_preset.go:101-108` ohne `order`/`bucket` | AC-16 |
| T5 Englische Texte in deutscher Mail | `plain.py:78` „Time“, `plain.py:162` „… Report“ | AC-17 |
| O1 Drei getrennte Listen (Vergleichstabelle, Stundenverlauf, Ausblick) | kein Fehler: Konzept (Liste je Fläche); Pflicht ist Sichtbarkeit je Liste im Editor = Mail | AC-5–7, AC-13 |
| O2 Orte-Stundenverlauf: Editor-Standard ≠ Mail-Standard | Mail `HOURLY_DEFAULT_METRIC_IDS` (`compare_hourly_metric_ids.py:111`), Editor Katalog-Gruppenfolge (`CompareHourlyLayoutControls.svelte:90-104`) | AC-13 |
| O3 Orte-Altbestand ohne `active_metrics`: Ausblick HTML 7 Spalten, Klartext 4 | `outlook.py:395-402` fester Klartext-Zweig | AC-21 |
| O4 Orte-Editor zeigt bei `active_metrics=null` ~25 Ausblick-Größen aktiv, Mail 7 | `OutlookLayoutControls.svelte` (`grundauswahl = COMPARE_METRIC_KEYS`) | AC-13 |
| Testlücke Orte-Ausblick-Folge | Mutation „`resolve_compare_outlook_metrics` nach Katalog“ → alle Bestandstests grün; Kette `test_compare_einstellung_auslieferung_kette.py:154` vergleicht sortiert | AC-7, AC-14 |

Regel für alle Behebungen: Der Fall wird zuerst aus Nutzersicht rot nachgewiesen (RED-Artefakt), dann behoben; Behebung am Ort der Wirkung (Renderer bzw. Frontend-Ableitung), keine Sortierung, die die gespeicherte Folge überschreibt; neue Nutzertexte nur über den Katalog in DE und EN (ADR-0104), Protokoll-Token (`col_label`, `sms_code`) bleiben unübersetzt.

### 8. Mutations-Gegenprobe (Pflicht laut CLAUDE.md)

Der `implementation-validator` verfälscht den Produktcode je Mutation per String-Ersetzung mit externer Sicherungskopie (nie `git checkout/stash/reset`) und lässt die Katalogtests laufen. Jede Mutation muss mindestens einen Test rot machen, sonst ist es ein Finding. Pflichtliste:

| Nr. | Verfälschung | Stelle | Fängt |
|---|---|---|---|
| M1 | Trip-Ausblick nach Katalogfolge sortieren | `compare_outlook_metric_ids.py::resolve_trip_outlook_metrics` bzw. `_erbe_grundauswahl` (Zeile 186: `sorted(...)` statt Listenfolge) | Fälle Trip Ausblick, Reihenfolge |
| M2 | Trip-Stundenspalten nach Katalogfolge | `html.py:533-537` und `plain.py:72-77`: `col_order` ignorieren | Fälle Stundentabelle HTML und Klartext |
| M3 | Klartext ohne `format_modes` | `plain.py:287-289` (Etappentabelle) | Fälle Roh/Einfach Klartext Etappe |
| M4 | Nachttabelle Klartext ohne `format_modes` bleibt wie Ist-Stand | `plain.py:298` | Fall Nachttabelle Roh/Einfach (rot vor der Behebung) |
| M5 | Orte-Stundenspalten nach Katalogfolge | `compare_html.py:1045`: `[m for m in zeilen if m["key"] in hourly_metrics]` | Fälle Stundenverlauf |
| M6 | Orte-Ausblick nach Katalogfolge | `compare_outlook_metric_ids.py::outlook_columns` (Zeile 346) sortiert | Fälle Orte Ausblick |
| M7 | Orte-Übersicht nach Grundauswahl statt nach Kanal-Liste | `compare_metric_ids.py:292` | Fälle Vergleichstabelle |
| M8 | Ortsreihenfolge ignorieren | `order_locations_by_ids` Aufruf in `send_one_compare_preset` | Fälle Ortsreihenfolge |
| M9 | Liste nimmt auch Metriken außerhalb der Grundauswahl | `_erbe_grundauswahl` Zeile 186 ohne Schnitt | Fälle Grundauswahl |
| M10 | `show_night_block` ignorieren | `trip_report.py:168` | Fall Zusatzblock |
| M11 | Validator prüft Soll nicht | `pruefe_soll` liefert immer leer | Validator-Negativfälle |

## Parallelisierung

Arbeitspakete mit disjunkten Dateien, höchstens fünf gleichzeitig. Jedes Paket besitzt seine Fallliste-Teildatei, damit nichts kollidiert; der Wächter (E) liest nur.

| Paket | Inhalt | Dateien (ausschließlich) | Abhängigkeit |
|---|---|---|---|
| A Prüfkatalog Trip | Kettentests Trip (AC-2, AC-3, AC-4, AC-8 Trip, AC-9, AC-10 Trip, AC-11 Trip, AC-12 Trip) | `test_einstellung_gleich_mail_trip.py`, `_einstellung_gleich_mail_trip_fixtures.py`, `tests/helpers/einstellung_gleich_mail_trip.py`, `fallliste_trip.json`, Golden Trip | keine |
| B Prüfkatalog Orte | Kettentests Orte (AC-5, AC-6, AC-7, AC-8 Orte, AC-10 Orte, AC-11 Orte, AC-12 Orte) | `test_einstellung_gleich_mail_orte.py`, `tests/helpers/einstellung_gleich_mail_orte.py`, `orte_*.json`, `fallliste_orte.json`, Golden Orte | keine |
| C Validatoren | AC-19, AC-20 | `.claude/hooks/_soll_aus_konfiguration.py`, beide Validatoren, `test_einstellung_gleich_mail_validatoren.py`, `fallliste_validatoren.json`, `docs/reference/mail_validators.md` | keine (nutzt später Mails aus A und B per `--eml`) |
| D Editor-Standard-Abgleich | AC-13 | `editor_standard.json`, `test_einstellung_gleich_mail_editor_standard.py`, `editor_standard_gleich_mail.test.ts`, `fallliste_editor.json` | keine |
| E Wächter Fallliste | AC-1 | `test_einstellung_gleich_mail_fallliste.py` | liest A bis D, kann mit leeren Teildateien starten |

Danach (nach RED aus A bis D) die Fehlerbehebungen, je Datei ein Paket, damit sie parallel laufen können:

| Paket | Behebung | Dateien |
|---|---|---|
| F1 | AC-15, AC-17 | `src/output/renderers/email/plain.py`, `src/i18n/` Katalogdateien DE/EN |
| F2 | AC-16 | `frontend/.../trip-detail/metricsEditor.ts`, `shared/WeatherMetricsTab.svelte` |
| F3 | AC-18 Trip (Standard Tabellen/Ausblick) | `email/helpers.py`, `compare_outlook_metric_ids.py` (nur bei rotem Fall) |
| F4 | AC-18 Orte (Standard Stunden/Ausblick/Übersicht) | `compare_hourly_metric_ids.py` bzw. `CompareHourlyLayoutControls.svelte`, `OutlookLayoutControls.svelte` (nur bei rotem Fall) |
| G | AC-14 Mutations-Gegenprobe | nur lesend und Sicherungskopie; Nachweis im PR |

F1 und F3 berühren verschiedene Dateien, F3 und F4 ebenfalls; kollidieren zwei Behebungen in derselben Datei, laufen sie nacheinander.

## Ausblick: Phase 2 bis 5 (keine ACs in dieser Spec)

Nur Skizze, jede Phase bekommt eine eigene Spec, ein ADR zu Phase 2 ist dann nötig.

- **Phase 2:** eine kanonische Kanal-Liste (vier Kanäle, ADR-0049/ADR-0095), ein Resolver bzw. View-Model, aus dem Editor und Renderer gemeinsam lesen. Der Editor-Standard-Abgleich (AC-13) wird dann strukturell erfüllt statt per Test bewacht.
- **Phase 3:** Umstellung je Kanal (E-Mail, Telegram, SMS, Premium-SMS) auf den Resolver, jeweils mit Löschung der Altpfade (`resolve_metric_col_order`, `_visible_hour_metrics`-Sonderpfade, `HOURLY_DEFAULT_METRIC_IDS` als zweite Quelle). Roh/Einfach je Zeile für Vergleichstabelle und Stundenverlauf (Konzept W11) kommt hier.
- **Phase 4:** gemeinsame Zusatzblöcke und `email_format` auch für Orte (Konzept W15).
- **Phase 5:** UI zuletzt („Inhalt je Kanal und Fläche“ laut Konzept §5 Punkt 8). Katalog und Validatoren bleiben die Messlatte für „fertig“.

## Expected Behavior

- **Input:** gespeicherte Trip- bzw. Orte-Konfiguration (rohes Persistenzformat), Wetterdaten aus Offline-Fixtures; auf Staging die echt zugestellte Mail plus rohes JSON des Test-Nutzers (`--konfig`).
- **Output:** Mail (HTML, Klartext, Trip Kompakt), deren Auswahl, Reihenfolge, Darstellung und Ein/Aus exakt der Konfiguration entspricht; eine Fallliste mit messbarem Status.
- **Side effects:** keine Nutzerdaten werden verändert; Tests laufen auf isolierter Datenwurzel mit frischen Profilen. Die Validatoren schreiben wie bisher ihr Log.

## Acceptance Criteria

- **AC-1:** Given die vier Teildateien der Fallliste liegen vor / When der Wächtertest läuft / Then besteht er nur, wenn jede Kombination aus Liste (Trip Stundentabelle, Trip Nachttabelle, Trip Ausblick, Orte Vergleichstabelle, Orte Stundenverlauf, Orte Ausblick) und Format (HTML, Klartext, beim Trip Kompakt) mindestens einen Fall für Auswahl und einen für Reihenfolge hat, jeder `gruen`-Fall eine auffindbare Testfunktion nennt, jede `ausnahme` und jedes `offen_feature` einen Verweis trägt und kein Fall mehr `rot_erwartet` ist.
  - Test: Der Test liest die JSON-Dateien und die Testmodule (per AST) und scheitert, wenn z. B. der Fall „Orte Stundenverlauf, Klartext, Reihenfolge“ gelöscht wird; er gibt die Zählung aus (grün, Ausnahme, offen).

- **AC-2:** Given ein Trip speichert die Stundentabelle der E-Mail mit der Folge Böen, Temperatur, Niederschlag, Wind (ungleich der Katalogfolge) / When das Briefing über Loader und Versandweg als Mail zugestellt wird / Then stehen die Spalten in HTML und im Klartext in genau dieser Folge, jede nur einmal, und keine nicht angehakte Metrik erscheint.
  - Test: `render_trip_dict` mit dem Trip-JSON, Spaltenköpfe der Etappentabelle aus HTML und Klartext der Mitschrift, verglichen mit der Folge aus dem rohen JSON; zusätzlich eine Umkehrung der Katalogfolge und eine Teilmenge mit zwei abgewählten Metriken.

- **AC-3:** Given ein Trip mit eingeschalteter Nacht-Stundentabelle und gespeicherter Folge Wind, Temperatur, Böen / When die Mail gesendet wird / Then zeigt die Nachttabelle in HTML und Klartext genau diese Spalten in dieser Folge, und eine Metrik, die auf Einfach steht, erscheint in der Nachttabelle des Klartextes in derselben Darstellung wie in der Etappentabelle derselben Mail.
  - Test: `render_trip_dict` mit `night_weather`, Parser für den Block „am Ziel“ im Klartext und die zweite Tabelle im HTML; Vergleich der Spaltenfolge und der Zelleninhalte mit der Etappentabelle.

- **AC-4:** Given ein Trip speichert den 3-Tages-Ausblick mit der Folge Wind, Temperatur, Niederschlag und im Gesamtbestand sind außerdem Böen und Gewitter angehakt / When das Abend-Briefing mit drei Ausblick-Tagen gesendet wird / Then zeigt der Ausblick in HTML, Klartext und Kompaktformat genau Wind, Temperatur, Niederschlag in dieser Folge; bei nie eingestelltem Ausblick erscheint die ganze Grundauswahl in der eingestellten Reihenfolge der Trip-Metriken (nicht in Katalogfolge), also genau so, wie der Reiter die Ausblick-Liste anzeigt; eine bewusst leere Auswahl lässt den Ausblick entfallen.
  - Test: `render_trip_mit_ausblick` (Zeilen aus `build_outlook_row`), Kopf der Ausblick-Tabelle im HTML, Zeilen „Tag Etappe Wert“ im Klartext und Token-Reihenfolge im Kompakttext, jeweils gegen das Soll aus dem rohen JSON.

- **AC-5:** Given ein Orte-Briefing speichert die Vergleichstabelle (E-Mail-Liste) mit der Folge Wind, Temperatur, Niederschlag und die Orte in der Folge Kronplatz, Sulden, Ahrntal / When der Versand mit `send_one_compare_preset` und aufzeichnendem Sink läuft / Then stehen im HTML und im Klartext die Zeilen genau in der Folge Wind, Temperatur, Niederschlag, die Orte-Spalten in der Folge Kronplatz, Sulden, Ahrntal, und keine abgewählte Metrik erscheint.
  - Test: Preset-JSON im Nutzerverzeichnis ablegen, Mail über `mail_sink` mit `plain_body` einsammeln, Zeilen- und Spaltenfolge parsen und mit dem Soll aus dem rohen JSON vergleichen; zweite Variante mit vertauschter Ortsreihenfolge.

- **AC-6:** Given ein Orte-Briefing speichert den Stundenverlauf mit der Folge Böen, Temperatur, Niederschlag / When die Mail gesendet wird / Then hat die Stundentabelle jedes Orts im HTML und im Klartext die Spalten Zeit, Böen, Temp, Niederschlag in genau dieser Folge; ist der Stundenverlauf ausgeschaltet oder die Auswahl bewusst leer, entfällt der Block; bei nie eingestellter Auswahl erscheint die Standardfolge aus AC-13.
  - Test: Kettentest über `send_one_compare_preset` mit `hourly_enabled` an und aus, Spaltenköpfe je Ort aus HTML und Klartext, Soll aus dem rohen JSON.

- **AC-7:** Given ein Orte-Briefing speichert den 3-Tages-Ausblick mit der Folge Niederschlag, Wind, Temperatur / When die Mail gesendet wird / Then zeigt der Ausblick je Ort in HTML und Klartext diese Spalten in dieser Folge (Temperatur als Spanne Tief/Hoch in einer Spalte), bei `outlook_enabled` aus erscheint kein Ausblick, und eine nicht in der Grundauswahl stehende Metrik taucht nicht auf.
  - Test: Kettentest mit drei Varianten (Ausblick an mit Folge, aus, Auswahl teils außerhalb der Grundauswahl), Kopf der Ausblick-Tabelle im HTML und Spaltenmarken im Klartext gegen das Soll.

- **AC-8:** Given in einer Liste steht eine Metrik auf Roh und eine andere auf Einfach / When die Mail gesendet wird / Then zeigt die Roh-Zeile eine Zahl und die Einfach-Zeile Symbol, Ampelpunkt oder Wort, im Trip in der Stundentabelle und im Ausblick, bei Orten im Ausblick; die gewollten Ausnahmen (Visibility, Temperatur und Gewitter im Ausblick ohne Einfach-Form, HTML-Ampelpunkt im Klartext als Zahl) sind in der Fallliste als `ausnahme` benannt, und Roh/Einfach für Vergleichstabelle und Stundenverlauf der Orte steht als `offen_feature` mit Verweis auf Konzept W11.
  - Test: je Metrik Zelle aus HTML und Klartext gegen das Orakel („Zahl“ gegen „Symbol/Wort“); ein Fall prüft, dass eine auf Einfach gestellte, aber nicht Einfach-fähige Metrik weiter die Zahl zeigt.

- **AC-9:** Given ein Trip schaltet nacheinander `show_night_block`, `show_stage_stats`, `show_yesterday_comparison` aus und stellt `email_format` auf Kompakt / When die Mail gesendet wird / Then fehlt jeweils genau der betroffene Block (Nachttabelle, Etappen-Kennzahlen, Vortag-Zeile) und bei Kompakt besteht die Mail nur aus Klartext ohne HTML-Teil, während alle übrigen Blöcke unverändert bleiben.
  - Test: vier Läufe mit `render_trip_dict`, je ein Schalter geändert; Präsenz des Blocks im HTML, im Klartext und im Kompakttext; Rest der Mail unverändert gegen den Lauf mit allen Schaltern an.

- **AC-10:** Given die Grundauswahl wird um eine zusätzliche Metrik (z. B. UV-Index) erweitert, bzw. eine Liste speichert eine Metrik, die in der Grundauswahl abgewählt ist / When die Mail gesendet wird / Then erscheint die neue Metrik in jeder Liste, auch in einer bereits eigens bearbeiteten (dort hinten angehängt, die bestehende Folge bleibt), (Trip-Tabellen, Trip-Ausblick, Orte-Vergleichstabelle, Orte-Ausblick, Stundenverlauf, soweit stündlich verfügbar), und die abgewählte Metrik erscheint in keiner Liste; bleibt nach dem Schnitt nichts übrig, gilt der dokumentierte Rückfall auf die volle Grundauswahl statt eines verschwindenden Blocks.
  - Test: Zwei Läufe je Kontext, einmal mit erweiterter, einmal mit verkleinerter Grundauswahl; Spaltenköpfe bzw. Zeilen aller Listen in HTML und Klartext.

- **AC-11:** Given ein Alt-Bestand ohne die neuen Felder (`outlook_metric_formats`, `channel_layouts`, `hourly_metrics`, `outlook_metrics`) / When die Mail gesendet wird / Then ist sie in HTML und Klartext zeichengleich zu den eingefrorenen Golden-Dateien, ausgenommen ausschließlich die in AC-15 bis AC-17 und AC-21 benannten Korrekturen (deren Golden-Änderung wird einzeln freigegeben, nie pauschal neu eingefroren); und die Validatoren (AC-19) verlangen ohne `--konfig` weiterhin keine feste Spaltenfolge (das Verbot aus #1381 bleibt gewahrt).
  - Test: Trip- und Orte-Golden unter `tests/fixtures/einstellung_gleich_mail/` byte-genau verglichen; ein Validator-Lauf mit zwei verschieden geordneten, gültigen Mails ohne `--konfig` besteht beide Male.

- **AC-12:** Given zwei verschiedene Nutzer speichern für denselben Trip- bzw. Orte-Aufbau unterschiedliche Folgen (Nutzer 1: Wind, Temperatur; Nutzer 2: Temperatur, Wind) / When für beide gesendet wird / Then trägt jede Mail die Folge ihres Nutzers an die Adresse ihres Nutzers, ohne Spuren der anderen Folge.
  - Test: zwei `frisches_profil()`-Läufe mit eigenen Empfängern; Mitschrift je Nutzer getrennt auswerten; Kreuzprüfung, dass Empfänger und Folge zusammenpassen.

- **AC-13:** Given für jede Liste (Trip Tabellen, Trip Ausblick, Orte Vergleichstabelle, Orte Stundenverlauf, Orte Ausblick) liegt dieselbe Eingabe vor, bei der die Liste nie eingestellt wurde / When die Frontend-Ableitung (Vitest) und die Python-Auflösung (pytest) mit dieser Eingabe laufen / Then liefern beide dieselbe Standardfolge und Auswahl, und diese ist die in `editor_standard.json` von Hand festgelegte; ein Auseinanderlaufen lässt genau den Test der abweichenden Seite scheitern.
  - Test: `editor_standard_gleich_mail.test.ts` und `test_einstellung_gleich_mail_editor_standard.py` vergleichen jeweils gegen dieselbe JSON-Datei; geprüft wird insbesondere die Orte-Stundenverlauf-Vorgabe (Tupel `HOURLY_DEFAULT_METRIC_IDS` gegen Katalog-Gruppenfolge im Editor).

- **AC-14:** Given der fertige Prüfkatalog / When der Adversary die Mutationen M1 bis M11 (Ausblick nach Katalog sortieren, Stundenspalten nach Katalog, Klartext ohne `format_modes`, Nachttabelle ohne `format_modes`, Orte-Stunden/-Ausblick/-Übersicht nach Katalog, Ortsreihenfolge ignoriert, Grundauswahl nicht geschnitten, `show_night_block` ignoriert, Validator ohne Soll) einzeln per String-Ersetzung mit externer Sicherungskopie einspielt / Then wird für jede Mutation mindestens ein Test des Katalogs rot, und nach dem Zurückspielen sind alle Tests grün.
  - Test: Protokoll im PR mit Mutation, rot gewordenem Test und grüner Gegenprobe; eine nicht gefangene Mutation ist ein Finding und führt zu einem neuen Fall.

- **AC-15:** Given ein Trip hat Nachttabelle und eine Metrik auf Einfach gestellt / When die Mail gesendet wird / Then zeigt der Klartext der Nachttabelle diese Metrik in derselben Roh/Einfach-Darstellung wie die Etappentabelle derselben Mail (nicht abweichend als Zahl).
  - Test: Fall „Nachttabelle Roh/Einfach Klartext“ ist vor der Behebung rot (`plain.py:298` ohne `format_modes`) und danach grün.

- **AC-16:** Given ein Nutzer wendet im Editor eine Vorlage an, deren Metriken die Folge Böen, Temperatur, Niederschlag, Wind haben / When die Vorlage übernommen und gespeichert wird / Then steht die gespeicherte Folge im Editor und in der Mail in genau dieser Vorlagen-Folge, nicht nach interner Priorität umsortiert.
  - Test: Vitest ruft das echte `applyPreset` mit einer Vorlage ungleich der Prioritätsfolge auf, liest die gespeicherte Spaltenfolge und vergleicht sie mit der Vorlage; die Prioritätslogik von `autoAssign` selbst bleibt für Neuanlage ohne Vorlage unverändert.

- **AC-17:** Given ein Nutzer mit Sprache Deutsch bekommt die Klartext-Mail eines Trips / When die Mail gerendert wird / Then enthält sie keine fest englischen Wörter in Spaltenkopf und Kopfzeile („Time“, „Report“) sondern die deutschen Katalogtexte, und ein Nutzer mit Sprache Englisch bekommt die englischen; Protokoll-Token (Spaltenkürzel) bleiben unübersetzt.
  - Test: Klartext-Kopf und erste Tabellenzeile für `language=de` und `language=en` gegen die Katalogtexte; DE und EN stehen im Katalog (ADR-0104).

- **AC-18:** Given die Kettentests aus AC-2 bis AC-7 sind rot für eine Abweichung aus #3047 (RED nachgewiesen) / When die Behebung am Ort der Wirkung umgesetzt ist / Then sind alle Fälle der Fallliste grün oder als `ausnahme` bzw. `offen_feature` mit Verweis geführt, und die bestehenden Tests (`test_einstellung_gleich_auslieferung.py`, `test_compare_einstellung_auslieferung_kette.py`, `test_compare_alarm_einstellung_auslieferung_kette.py`) bleiben unverändert grün.
  - Test: genannte Dateien einzeln ausführen (kein `uv run pytest` ohne Dateinamen) plus der Wächter aus AC-1.

- **AC-19:** Given der Test-Nutzer auf Staging hat die Folge Böen, Temperatur, Wind gespeichert und bekam die Mail zugestellt / When `briefing_mail_validator.py` bzw. `email_spec_validator.py` mit `--konfig <gespeichertes JSON>` läuft / Then besteht er (Exit 0), wenn Auswahl und Reihenfolge von Stundentabellen, Nachttabelle, Ausblick und (bei Orten) Zeilen und Ortsfolge im HTML und im Klartext der zugestellten Mail dem JSON entsprechen, und scheitert (Exit 1) mit Nennung der abweichenden Spalte, wenn die Folge vertauscht, eine Spalte zu viel oder zu wenig ist oder der Ausblick im Klartext fehlt.
  - Test: `test_einstellung_gleich_mail_validatoren.py` per `--eml` gegen Mails aus den Kettentests (positiv) und gegen gezielt veränderte Mails (negativ: Spalten vertauscht, Spalte fehlt, Klartext-Ausblick fehlt, Ortsfolge vertauscht).

- **AC-20:** Given eine Mail hat eine gültige, vom Nutzer frei gewählte Spaltenfolge / When der Validator ohne `--konfig` läuft / Then wird keine feste Kanon-Folge verlangt und die Mail besteht, und mit `--konfig` besteht sie nur bei Übereinstimmung mit der gespeicherten Folge; der Kommentar in `email_spec_validator.py` an der Stelle des alten Verbots nennt diese Regel.
  - Test: zwei gültige Mails mit verschiedener Folge bestehen ohne `--konfig`; mit `--konfig` besteht nur die passende; keine Zeile prüft gegen `_HOUR_COLUMNS_V2`.

- **AC-21:** Given ein Orts-Vergleich aus dem Altbestand ohne `active_metrics` und ohne `outlook_metrics` / When das Briefing mit Ausblick gesendet wird / Then zeigt der 3-Tages-Ausblick im Klartext dieselben Spalten in derselben Folge wie im HTML derselben Mail, und der Editor zeigt für diese Liste genau diese Spalten als aktiv.
  - Test: Orte-Kette (Paket B) mit Altbestand-Preset, Vergleich HTML-Kopf gegen Klartext-Block; Editor-Seite über AC-13.

## Nachtrag Runde 7 (2026-11-16): Inventar über alle Ausgaben

Die siebte Prüfrunde hat jede im Hub änderbare Einstellung gegen jede Ausgabe (E-Mail HTML/Klartext/Kompakt, Telegram, SMS, Premium-SMS, Einstellungsseite) für Trip und Orte geprüft. Matrix: `docs/artifacts/feat-3047/inventar_matrix.json` (Status je Zelle), Befunde: `docs/artifacts/feat-3047/runde7_befunde.md`. Damit wird die in „Known Limitations“ für Phase 3 vorgesehene Aufnahme von Telegram, SMS und Premium-SMS in den Katalog vorgezogen (Kanal-Parität ADR-0095).

**PO-Entscheidungen 2026-11-16 (per Rückfrage):**
- **SMS-Kürzung:** Bei Überlänge fällt das Listenende zuerst weg, Trip und Orte gleich; amtliche Warnungen fallen immer zuletzt weg (WV6). Die feste Prioritätskürzung (#1677 AC-6) ist damit abgelöst; sicherheitsrelevante Größen stehen über die Vorbelegung vorn.
- **Telegram-Schnittlinie:** Nichts fällt weg. Trip bleibt (alle Zeilen in der Kurzübersicht, die ersten 7 zusätzlich stündlich in der Tabelle); der Erklärsatz im Editor wird daran angepasst (#3031/#3033). Orts-Vergleich: Zeilen ab Platz 8 erscheinen in einer zweiten Zeile je Ort statt wegzufallen.
- **Amtliche Warnungen Altbestand-Mischzustand:** Ist Briefing- oder Alarm-Schalter an, gilt „beides an“ (Briefing und Alarm); Editor zeigt dann „an“.
- **Amtliche Warnungen Neuanlage (PO 2026-11-16, zweite Rückfrage):** Auch der umgekehrte Zustand (Briefing an, Alarm aus — bisherige Neuanlage nach #1258 AC-4) gilt als „beides an“; neue Trips und Orts-Vergleiche bekommen Warnungen im Briefing und als Alarm. #1258 AC-4 ist damit abgelöst.
- **Tech-Lead (Lückenprüfung):** Trip-Telegram-Kurzübersicht folgt dem Tagesfenster wie SMS/Mail (ADR-0035/0095, löst #1498 für die Kurzübersicht ab); „Einfach“ bei Ampel-Größen in Text-Kanälen folgt den Ampel-Grenzen (Konzept §5 P8, ADR-0097); Trip-Altformat ohne `order`: es gilt die Register-Priorität des Loaders in allen Kanälen, Validator und Editor folgen ihr; Orts-Vergleich „nie eingestellt“: Telegram/SMS/Premium-SMS folgen der Grundauswahl wie die Mail.

**Tech-Lead-Entscheidungen (innerhalb Konzept):**
- Grundauswahl „nie eingestellt“: Einstellungsseite zeigt den Mail-Standard (Trip: Register-Standardsatz; Orte: was die Mail zeigt), nicht die Vorlage; eine unbeteiligte Speicherung ändert die Mail nicht. Neues Orts-Briefing aus Standard-Vorlage speichert die Grundauswahl ausdrücklich.
- Altformat-Einträge in `metrics[]` (Zeichenkette, ohne `enabled`) gelten als gewählt; Einträge ohne `metric_id` weist die API ab, der Loader verwirft nur den Eintrag.

**Zusätzliche ACs:**
- **AC-22:** Given eine Trip- oder Orte-Konfiguration mit beliebiger Telegram-, SMS- oder Premium-SMS-Liste (Folge ≠ Katalog, an/aus, Roh/Einfach) in DE oder EN / When das Briefing über den echten Weg bis zum Transport-Ausgang erzeugt wird / Then entsprechen Auswahl, Folge und Roh/Einfach je Zeile der gespeicherten Liste (inkl. Windrichtung Roh, #3063), Nutzertexte stehen in Nutzersprache, Kürzel bleiben unübersetzt.
- **AC-23:** Given eine SMS oder Premium-SMS über 160 Zeichen / When gekürzt wird / Then fällt die Liste von hinten weg, amtliche Warnungen (auch die eines weiteren Ortes) fallen zuletzt weg, Trip und Orte gleich.
- **AC-24:** Given ein Orts-Vergleich mit mehr als 7 Telegram-Zeilen / When das Telegram-Briefing erzeugt wird / Then erscheinen alle Zeilen (ab Platz 8 in einer zweiten Zeile je Ort) und der 3-Tages-Ausblick ist enthalten wie beim Trip.
- **AC-25:** Given die Kompakt-Mail (Trip) / When `show_stage_stats` aus bzw. amtliche Warnungen vorhanden / Then fehlen die Kennzahlen, und die Warnungen stehen an erster Stelle; der Ausblick steht unabhängig von `show_outlook` immer drin (PO-Entscheidung #722, der Editor sperrt den Schalter bei Kompakt; korrigiert Runde 8).
- **AC-26:** Given eine gespeicherte Konfiguration (nie eingestellt, Altbestand, Altformat, Mischzustand Warnungen, halbes Tagesfenster, `null`-Zusatzblöcke, Trend nie eingestellt) / When die Einstellungsseite sie lädt und eine unbeteiligte Änderung speichert / Then zeigt sie genau, was die Ausgabe tut, und die Ausgabe ändert sich durch das Speichern nicht.
- **AC-27:** Given die Validatoren mit `--konfig` / When eine Mail eine Ausblick-Zeile, den Ausblick eines Orts, eine Stundenspalte ab der zweiten Zeile, die richtige Roh/Einfach-Form der Vergleichstabelle oder den Aus-Zustand eines Zusatzblocks verfehlt / Then scheitern sie; ein vom Nutzer gesetztes Tagesfenster lehnen sie nicht ab.
- **AC-28:** Given amtliche Warnungen sind aus bzw. der Warndienst ist nicht erreichbar / When die Orts-Mail erzeugt wird / Then zeigt das HTML keine leere Warnzeile, und der Klartext trägt denselben Hinweis „nicht abrufbar“ wie das HTML.

**Ausgelagert:** eigener Soll-Validator für Telegram/SMS/Premium-SMS (neues Issue), eigene Premium-SMS-Liste (#2801), Kürzel-Legende am Briefing-Ende (#3032), Profil im Mail-Kopf K3b (#2796), Roh/Einfach Stundenverlauf (#3058), Ausblick „Erscheint im“ für Orte (Konzept V12 nur Trip; bleibt Orte: Ausblick in jedem Briefing).

## Known Limitations

- Der Trip-Ausblick wird im Kern-Test aus der reinen Funktion `build_outlook_row` gespeist, nicht über den Zeitplaner-Abruf (`_build_stage_trend`, braucht Wetter-Netz). Der Abruf selbst wird in `/e2e-verify` auf Staging geprüft.
- Roh/Einfach für Orte-Vergleichstabelle und Stundenverlauf existiert im Renderer nicht (Konzept W11); Phase 1 führt das als `offen_feature`.
- Telegram, SMS und Premium-SMS sind in Phase 1 nicht Teil des neuen Katalogs (durch #2422-Tests abgedeckt); Aufnahme in Phase 3.
- Paarweise statt vollständige Kombinatorik lässt Drei-Faktor-Fehler theoretisch offen; AC-14 mindert das Risiko.
- Der Wortlaut der Befunde T1 bis T3 und O2 bis O4 aus #3047 war beim Schreiben nicht lesbar; die Zuordnung in Abschnitt 7 ist eine Annahme und vor Freigabe abzugleichen. Die Konzept-Zeilenangaben zu `models.py` (`email_format` 1171, `show_stage_stats` 1162, `show_yesterday_comparison` 1173, `show_night_block` 829) sind veraltet; im Code stehen sie aktuell bei 1181, 1172, 1183 und 835.
- Das Staging-Postfach ist ein geteiltes Postfach; `--konfig` setzt voraus, dass die geprüfte Mail dem Nutzer des Konfigurations-JSON gehört (Auswahl über `--to-contains`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Phase 1 ändert keine Entscheidungsfläche, sondern sichert bestehende Entscheidungen (ADR-0050 Grundauswahl als Maximum, ADR-0055 Ausblick ohne Kanal-Ebene, ADR-0095 Kanal-Parität, ADR-0104 Zweisprachigkeit) durch Tests ab. Die kanonische Kanal-Liste und der gemeinsame Resolver (Phase 2) berühren Datenmodell und Kanäle und brauchen ein eigenes ADR in der Spec zu Phase 2.

## Changelog

- 2026-11-17: Fallliste-Doku nachgezogen (Issue #3098): Teildatei `fallliste_telegram.json` mit Telegram-Fällen für Trip und Orte; der Wächter liest fünf statt vier Teildateien (Abschnitt 4)
- 2026-11-17: Runde 9: Orte-Altbestand ohne Grundauswahl/Ausblick-Liste rendert den Ausblick wie die gleichwertige explizite Vorgabeliste (HTML = Klartext, AC-5/AC-13); Validator-Soll angeglichen
- 2026-11-17: Runde 8: AC-25 an PO-Entscheidung #722 angeglichen (Kompakt-Ausblick immer an), Befunde F1/F3/T1–T4 der Abnahme Runde 7 behoben
- 2026-11-16: Nachtrag Runde 7 (AC-22 bis AC-28, PO-Entscheidungen SMS-Kürzung, Telegram-Schnittlinie, Warnungen-Altbestand)
- 2026-11-15: Initial spec created (Phase 1 von #3047, Prüfkatalog zuerst)
