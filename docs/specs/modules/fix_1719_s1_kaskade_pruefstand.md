---
entity_id: fix_1719_s1_kaskade_pruefstand
type: bugfix
created: 2026-08-11
updated: 2026-08-11
status: approved
version: "1.0"
tags: [metrics, cascade, adr, matrix-test, issue-1719]
---

<!-- Issue #1719, Scheibe 1 -- NUR Festlegung (ADR-0050) + Pruefstand.
     Kein Produktivcode-Fix. Grundlage: docs/context/fix-1719-s1-kaskade-pruefstand.md
     (gemessen 2026-08-11, Prod-Commit 64b78c63). S2 (Backend-Verfeinerungsfilter),
     S3 (Frontend), S4 (Legende) sind eigene, spaetere Scheiben. -->

# Metrik-Kaskade: Festlegung (ADR-0050) + Prüfstand, der den KHW-Widerspruch reproduzierbar rot zeigt (#1719 Scheibe 1)

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-08-11

## Purpose

Trip KHW `5f534011` lieferte eine SMS-Kurzform mit einer Metrik
(`wind_chill`), die im SMS-Kanal-Reiter abgewählt war — der Renderer folgte
stattdessen der globalen Grundauswahl. Ursache ist kein einzelner Bug,
sondern ein **fehlender Grundsatz**: die Kaskade zwischen globaler
Metrik-Auswahl und Kanal-Layout hatte keine schriftlich fixierte
Beziehung (49 ADRs, keines zur Kaskade), und der bestehende
Vollständigkeits-Wächter (`test_channel_metric_matrix.py`, AC-13/14/15)
konnte diesen Fehler strukturell nicht sehen (fünf Konstruktionsfehler,
s. `docs/context/fix-1719-s1-kaskade-pruefstand.md` Abschnitt 5). Diese
Scheibe liefert **beides nach**: eine Zusage (ADR-0050: die Kaskade ist
eine Verfeinerung, kein Ersatz — die Grundauswahl ist das Maximum) und
einen Prüfstand, der genau gegen diese Zusage testet, mit einer echten
anonymisierten Trip-Fixture über den echten Loader und Renderpfad, statt
einer im Speicher gebauten Zwei-Metriken-Attrappe. **Kein Produktivcode
wird verändert** — der Prüfstand muss den heutigen Konstruktionsfehler
reproduzierbar ROT zeigen, bevor irgendetwas repariert wird (S2).

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core (Testcode) + Dokumentation
> (ADR). Kein Frontend, keine Go-Beteiligung.

- **File (ADR):** `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md`
- **File (Prüfstand):** `tests/tdd/test_channel_metric_matrix.py` — neue
  Testfunktionen, die den bestehenden AC-13/14/15- und
  AC-1-bis-AC-8-Block (#1677 B, #1703 S3) um einen eigenen, mit
  `test_kaskade_ac*` benannten Abschnitt ergänzen (Testnamensregel
  CLAUDE.md: keine neue, issue-nummerierte Testdatei; dieselbe Datei
  wurde bereits zweimal für genau diesen Matrix-Zweck erweitert).
  Iterationsbasis für die widerspruchsfreien Fälle bleibt der reale
  Renderpfad; die neue Achse ist die **Kaskadenquelle**
  (`cascade_source_for_channel`), nicht der Metrik-Katalog.
- **File (Fixture):** `tests/fixtures/metric_cascade/khw_display_config_widerspruch.json`
  — versionierte, anonymisierte Kopie NUR des `display_config`-Teilbaums
  des realen KHW-Trips (Koordinaten/Namen/Empfänger liegen strukturell
  außerhalb dieses Teilbaums, s. AC-3).
- **Identifier:** `app.loader._parse_display_config()`,
  `app.models.UnifiedWeatherDisplayConfig.get_metrics_for_channel()` /
  `.cascade_source_for_channel()`, `output.renderers.trip_report.TripReportFormatter.format_email()`,
  `output.renderers.channel_layout.render_for_channel()`.

**Ausdrücklich UNVERÄNDERT (reine Prüfziele, kein Edit):**

- `src/app/models.py` — `UnifiedWeatherDisplayConfig.get_metrics_for_channel()`
  (Z. 808-846, die Ersetzung-statt-Verfeinerung-Stelle selbst — bleibt in
  dieser Scheibe bewusst bestehen; der Umbau ist S2),
  `_cascade_source_for_channel()` (Z. 695-717)
- `src/app/loader.py` — `_parse_display_config()` (Z. 751 ff.), insbesondere
  der `channel_layouts`-Parse-Zweig (Z. 836-871)
- `src/output/renderers/trip_report.py` — `TripReportFormatter.format_email()`
  Kollabierungsschritt (Z. 122-138), `_sms_metrics_ordered = _dc_uncollapsed.get_metrics_for_channel("sms", report_type)`
  (Z. 295 — Beleg, dass Premium-SMS über denselben Kaskadenschlüssel `"sms"`
  läuft wie SMS, s. AC-11)
- `src/output/renderers/channel_layout.py` — `render_for_channel()` (Z. 81-95)
- `src/output/channels/premium_sms.py` — Kommentar „Der Nachrichtentext ist
  unverändert `report.sms_text`" (Z. 19, Beleg für AC-11)

## Estimated Scope

- **LoC:** ~180-260 Testcode (12 ACs, davon mehrere mit echtem
  Mehrfach-Render gegen die tatsächliche Produktionspipeline) + 1
  Fixture-JSON-Datei (~120-160 Zeilen, 26 Metrik-Einträge je Ebene) + 1 ADR
  (Doku, zählt nicht gegen das LoC-Limit) + Index-Zeile.
- **Files:** 3 neue (ADR, Fixture-JSON, ggf. eine kleine Fixture-Hilfsdatei
  für konstruierte Ein-Feld-Varianten) + 1 erweiterte Bestandsdatei
  (`test_channel_metric_matrix.py`) + 1 Doku-Update (`docs/adr/README.md`).
- **Effort:** medium — die Komplexität liegt nicht in der Testmenge, sondern
  darin, den Widerspruchsfall so zu konstruieren, dass er die volle
  Katalogbreite (26 Einträge) behält statt auf eine isolierte
  Zwei-Metriken-Attrappe zurückzufallen (genau das war Konstruktionsfehler
  #3 des Vorgängers).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/fix-1719-s1-kaskade-pruefstand.md` | GRUNDLAGE (gemessen) | Alle Zahlen/Belegstellen dieser Spec sind daraus übernommen, nicht neu recherchiert |
| `tests/tdd/test_channel_metric_matrix.py` | WIRD ERWEITERT | Bestehende AC-13/14/15 (#1677 B) und AC-1-8 (#1703 S3) laufen unverändert weiter; neuer Abschnitt nutzt dieselben Renderpfad-Helfer (`_mail_table`-Muster, `_telegram_cells`, `_render_sms`), aber gegen fixture-geladene statt in-memory gebaute Configs |
| `docs/specs/modules/fix_1703_s3_selectable_metrics.md` | REFERENZ (Teststil) | Vorbild für „Prüfort = Wirkort"-Argumentation und Mutations-Gegenprobe-Format |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | REFERENZ | Begründet, warum Premium-SMS strukturell denselben Kaskadenschlüssel `"sms"` erbt (AC-11) statt eigens gerendert zu werden |
| `docs/adr/README.md` | WIRD AKTUALISIERT | Neue Index-Zeile für ADR-0050 (bereits in dieser Scheibe erledigt) |
| `tests/test_adr_index_drift.py` | PRÜFT MIT | Erzwingt Index/Status-Konsistenz für ADR-0050 |
| `tests/tdd/_min_temp_felt_fixtures.py` (`F.segment()`/`F.night_weather()`) | WIRD WIEDERVERWENDET, UNVERÄNDERT | Realistische Wetterdaten-Basis für die Render-Aufrufe — bewusst OHNE die künstliche Schnee-Auffüllung aus `_matrix_segment()` (Konstruktionsfehler #5), s. AC-10 |

## Implementation Details

**Fixture-Familie (eine Basis, dokumentierte Ein-Feld-Varianten):**

Die Basis-Fixture `khw_display_config_widerspruch.json` enthält ausschließlich
den `display_config`-Teilbaum (Top-Level-Schlüssel: `trip_id`, `metrics`,
`channel_layouts` — genau die Schlüssel, die `_parse_display_config()` liest,
s. `loader.py:751-909`), mit `trip_id` durch eine neutrale
Test-Kennung ersetzt. `metrics` (Grundauswahl) und `channel_layouts.sms`
führen je 26 Einträge, mit der im Kontext-Dokument gemessenen
Aktiv/Inaktiv-Verteilung (15 global aktiv inkl. `wind_chill` AN, 13
SMS-Kanal-aktiv, `wind_chill` AUS) — das IST bereits der reale
„global AN + Kanal AUS"-Fall (AC-6, s. u.).

Für den fehlenden, aber entscheidenden Gegenfall („global AUS + Kanal AN",
AC-7) sowie die enabled:false-/Weglassen-Gegenüberstellung (AC-4/AC-5) und
die Reihenfolge-Gegenprobe (AC-12) baut der Testcode **kontrollierte
Varianten der geladenen Basis-Config** (`dataclasses.replace` auf einzelne
`MetricConfig`-Einträge, NICHT eine neue, kleinere Config) — jede Variante
ändert genau EIN Feld einer einzigen, dokumentiert kollisionssicheren
Metrik-ID (Vorbild `_partner_of()` im Bestand) und lässt die übrigen 25
Einträge der realen Fixture unangetastet. So bleibt jede Test-Variante bei
der vollen Katalogbreite (Konstruktionsfehler #3 vermieden), ohne 26
separate JSON-Dateien pflegen zu müssen.

Render-Aufrufe laufen für jeden Kanal über die tatsächlich produktiv
aufgerufene Funktion (kein Duplikat-Rendering, Vorbild AC-1/AC-2 in
`fix_1703_s3`):

- **E-Mail:** `TripReportFormatter().format_email(...)` → echter
  `<thead>` der Stundentabelle (Regex-Parsing wie `_mail_table()`)
- **Telegram-rich:** `render_for_channel("telegram", dc, report_type)` →
  `table_columns + detail_metrics`
- **SMS:** `TripReportFormatter().format_email(...).sms_text`
- **Premium-SMS:** kein eigener Render-Aufruf. AC-11 sichert
  verhaltensbasiert zu, dass die geladene Konfiguration **keine eigene
  `premium_sms`-Kaskadenebene** trägt — es existiert also kein zweiter
  Auswahlweg, der von der SMS-Auswahl abweichen könnte. Die inhaltliche
  Gleichheit des Textes ist am Wirkort über
  `test_kaskade_f002_sms_global_fallback_is_not_restricted_by_email_layout`
  gedeckt (echter gerenderter SMS-Text).

  > **Korrektur 2026-08-11 (CI-Befund, nach dem Adversary).** Die erste
  > Fassung von AC-11 prüfte zwei **Quelltext-Strings** — einen Modul-Docstring
  > in `premium_sms.py:19` und eine Codezeile in `trip_report.py:295` — und war
  > als `# doc-compliance-test` markiert. `test_765_no_product_source_read` hat
  > sie im CI-Lauf zu Recht abgelehnt: Ein Kommentar im Fremdmodul belegt kein
  > Verhalten, und die Doku-Ausnahme deckt Doku-Konsistenz, nicht das Ersetzen
  > eines fehlenden Verhaltenstests.
  >
  > **Das ist bemerkenswert, weil es exakt die Fehlerklasse ist, gegen die diese
  > Scheibe antritt** — geprüft wurde dort, wo der Code *steht*, nicht wo er
  > *wirkt*. Weder Spec-Autor noch Adversary haben es beanstandet (der Adversary
  > nannte es „nur ein String-Match", ohne daraus ein Finding zu machen); erst
  > ein bestehender Hygiene-Wächter im vollen CI-Lauf hat es gefangen. Belegt,
  > dass ein Gate mehr wert ist als drei sorgfältige Leser.

Wetterdaten kommen unverändert aus `F.segment()`/`F.night_weather()`
(`tests/tdd/_min_temp_felt_fixtures.py`) — ohne die künstliche
`snow_depth_cm`/`snowfall_limit_m`/`snow_new_sum_cm`-Injektion aus
`_matrix_segment()`. Metriken, die dadurch strukturell keinen realen Wert
tragen, werden im Testcode namentlich als Ausnahme von der
Kürzel-Präsenz-Prüfung dokumentiert (AC-10) — sie fließen nicht in AC-4/
AC-5/AC-7/AC-8/AC-12 als Zielmetrik ein.

## Expected Behavior

- **Input:** die anonymisierte Basis-Fixture (26/26 Einträge, realer
  KHW-Widerspruch), kontrollierte Ein-Feld-Varianten davon, unveränderte
  `F.segment()`/`F.night_weather()`-Wetterdaten.
- **Output:** ein neuer, benannter Testblock in
  `tests/tdd/test_channel_metric_matrix.py`. Nach dieser Scheibe ist
  MINDESTENS ein Test (AC-7) gegen den heutigen Produktivcode ROT — das
  ist beabsichtigt und wird erst mit S2 grün. Alle anderen ACs sind grün
  (Charakterisierung des heute bereits korrekten Verhaltens bzw. der
  Fixture-Eigenschaften selbst).
- **Side effects:** keine. Kein Produktivcode-Edit, keine neue Persistenz,
  kein neues Pflicht-Gate.

## Acceptance Criteria

- **AC-1 (ADR existiert und ist konsistent indiziert):** Given
  `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` enthält
  die fünf PO-Entscheidungspunkte aus dem Kontext-Dokument Abschnitt 6 /
  When `tests/test_adr_index_drift.py` gegen den aktualisierten
  `docs/adr/README.md`-Index läuft / Then ist ADR-0050 dort verlinkt,
  Status „Akzeptiert" stimmt zwischen Datei und Index überein.
  - Test: `tests/test_adr_index_drift.py` (Bestand, unverändert) läuft
    grün gegen die neue Datei.

- **AC-2 (Fixture ist eine echte, anonymisierte Kopie des gemessenen
  Widerspruchs, über den echten Loader geführt):** Given die Basis-Fixture
  `khw_display_config_widerspruch.json` mit 26 Einträgen in `metrics` (15
  aktiv, `wind_chill` AN) und 26 Einträgen in `channel_layouts.sms` (13
  aktiv, `wind_chill` AUS) / When sie über `app.loader._parse_display_config()`
  geparst wird (nicht als im Speicher gebautes
  `UnifiedWeatherDisplayConfig`) / Then liefert
  `cascade_source_for_channel("sms", "evening")` exakt `"per_channel"` und
  `get_metrics_for_channel("sms", "evening")` exakt 13 aktive Metriken ohne
  `wind_chill` — die gemessene Ist-Charakterisierung aus dem
  Kontext-Dokument Abschnitt 3 bleibt reproduzierbar.
  - Test: Laden über den echten Loader, keine Assertion gegen den
    Renderpfad (der folgt in AC-6/AC-11).

- **AC-3 (Anonymisierung ist geprüft, nicht nur behauptet):** Given die
  Fixture-Datei enthält AUSSCHLIESSLICH die Top-Level-Schlüssel `trip_id`,
  `metrics`, `channel_layouts` (der Schlüsselsatz, den
  `_parse_display_config()` liest) / When ein Test die Roh-JSON-Datei auf
  verbotene Schlüssel prüft (`name`, `mail_to`, `sms_to`,
  `premium_sms_reply_to`, `waypoints`, `gpx`, `lat`, `lon`, `stages`) UND
  `trip_id` gegen die reale Kennung `5f534011` abgleicht / Then sind alle
  verbotenen Schlüssel abwesend und `trip_id` ist NICHT die reale Kennung.
  - Test: Datei-Parsing (JSON, kein Renderpfad) + Schlüsselmengen-Vergleich.

- **AC-4 (Abwahl als `enabled: false` bei vorhandenem Kanal-Eintrag, je
  Kanal):** Given eine Variante der Basis-Fixture, in der eine
  kollisionssichere, global aktive Metrik-ID im SMS-Kanal-Layout als
  eigenständiger Eintrag mit `enabled: false` geführt wird (Eintrag
  EXISTIERT, ist aber deaktiviert — nicht weggelassen) / When die drei
  Kanal-Renderpfade (E-Mail-Kopfzeile, Telegram-rich-Zellen, SMS-Text) über
  die echte Fixture geführt werden / Then fehlt die Metrik im **SMS-Text**
  (dem einzigen Kanal mit eigenem Layout), erscheint aber unverändert in
  **E-Mail und Telegram** — dort existiert kein Kanal-Layout, also gilt dort
  die Grundauswahl. Eine Kanal-Abwahl wirkt **genau in ihrem Kanal** und
  nicht darüber hinaus.
  - Test: Ein-Feld-Variante der Basis-Fixture, Assertion gegen alle drei
    echten Renderpfade.

  > **Korrektur 2026-08-11 (nach TDD-RED, Befund des Entwicklers).** Der
  > ursprüngliche Wortlaut verlangte Abwesenheit „in KEINEM der drei Kanäle".
  > Das war **falsch spezifiziert** und widerspricht ADR-0050: eine Abwahl im
  > SMS-Reiter darf E-Mail und Telegram nicht mit abschalten — sonst wären
  > kanal-eigene Einstellungen sinnlos. Gemessen an der Fixture:
  > `cascade_source_for_channel` liefert `sms → per_channel`, `email → global`,
  > `telegram → global`. Der korrigierte AC ist **schärfer** als der
  > ursprüngliche: er bewacht zusätzlich, dass die Abwahl nicht überschießt.
  > Gilt sinngemäß auch für AC-5 und AC-6. Der Fehler stammt aus der Spec,
  > nicht aus der Umsetzung; er wurde gemeldet statt still umgangen.

- **AC-5 (Abwahl als Weglassen aus der Kanal-Liste, direkt der AC-4
  gegenübergestellt):** Given dieselbe Ziel-Metrik wie AC-4, diesmal aber
  im SMS-Kanal-Layout GAR NICHT geführt (Eintrag fehlt vollständig statt
  `enabled: false`) / When derselbe Renderpfad-Dreiklang läuft / Then ist
  das Ergebnis IDENTISCH zu AC-4 (im SMS abwesend, in E-Mail/Telegram
  vorhanden — s. Korrektur bei AC-4) — beide Abwahl-Formen liefern denselben
  beobachtbaren Effekt.
  - Test: zweite Ein-Feld-Variante, direkter String-/Listenvergleich der
    Ergebnisse gegen AC-4.

- **AC-6 (Widerspruchsfall global AN + Kanal AUS — Regression-Baseline,
  heute bereits korrekt):** Given die unveränderte Basis-Fixture
  (`wind_chill` global AN, im SMS-Kanal-Layout explizit `enabled: false`)
  / When alle drei Kanal-Renderpfade laufen / Then bleibt `wind_chill`
  (alle drei Kürzel `FK`/`FD`/`WC`, s. AC-8) im **SMS-Text** abwesend — die
  Kanal-Abwahl gewinnt — und in **E-Mail/Telegram** vorhanden, weil dort kein
  Kanal-Layout existiert (s. Korrektur bei AC-4). Konform zu ADR-0050
  Regel 1/2. Der Test bleibt GRÜN gegen den heutigen Produktivcode.
  - Test: direkte Wiederverwendung der Basis-Fixture, keine Variante nötig.

- **AC-7 (Pflicht-AC — Widerspruchsfall global AUS + Kanal AN, MUSS heute
  ROT sein):** Given eine Ein-Feld-Variante der Basis-Fixture, in der eine
  kollisionssichere, in der Basis-Fixture bereits GLOBAL deaktivierte
  Metrik-ID im SMS-Kanal-Layout explizit mit `enabled: true` geführt wird
  (alle übrigen 25 Einträge unverändert aus der realen Fixture) / When alle
  drei Kanal-Renderpfade laufen / Then MUSS die Metrik laut ADR-0050 Regel
  1/2 („Grundauswahl ist das Maximum, Kanal darf nur abwählen, nie
  hinzufügen") in KEINEM Kanal erscheinen — der Test ist beim Schreiben
  dieser Scheibe bewusst ROT, weil `get_metrics_for_channel()`
  (`models.py:808-846`) die Kanal-Ebene heute vollständig ERSETZT statt sie
  gegen die Grundauswahl zu begrenzen. Dieser Test bleibt bis zur Umsetzung
  von S2 ROT — das ist der geforderte, reproduzierbare Beleg des
  Konstruktionsfehlers, unabhängig vom nicht rekonstruierbaren
  KHW-Sendezeitpunkt-Zustand (Kontext-Dokument Abschnitt 3, letzter Absatz).
  - Test: Ein-Feld-Variante + Assertion gegen alle drei echten
    Renderpfade; MUSS beim ersten Lauf fehlschlagen (kein Mock, keine
    Behauptung — der reale Produktivcode liefert das falsche Ergebnis).

- **AC-8 (alle Kürzel einer Metrik, nicht nur das erste — `wind_chill`
  FK/FD/WC):** Given `wind_chill` (`SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"]
  == ("FK", "FD", "WC")`) ist im SMS-Kanal-Layout der Basis-Fixture AUS (s.
  AC-6) bzw. in einer Variante AN / When der echte SMS-Text
  (`report.sms_text`) auf alle drei Kürzel geprüft wird / Then verschwinden
  bei Abwahl ALLE DREI Kürzel gemeinsam (nicht nur `FK`), und bei Zuwahl
  erscheinen alle drei (soweit die zugrunde liegende Wetterdaten-Fixture
  reale Werte dafür liefert, s. AC-10).
  - Test: Iteration über `SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"]`, keine
    Verkürzung auf `[0]` (Vorbild: Bestandsfehler
    `_representative_symbol()` im Vorgänger-Wächter).

- **AC-9 (volle Katalogbreite, 26 Einträge, nicht zwei):** Given die
  Basis-Fixture / When `metrics` und `channel_layouts.sms` gezählt werden
  / Then führt jede Ebene 26 Einträge — exakt die im Kontext-Dokument
  gemessene Breite, keine auf zwei Metriken reduzierte Attrappe
  (Konstruktionsfehler #3 des Vorgängers).
  - Test: `len(...) == 26` auf beiden Ebenen der geladenen Fixture.

- **AC-10 (keine künstlich aufgefüllten Wetterdaten):** Given
  `F.segment()`/`F.night_weather()` werden UNVERÄNDERT verwendet (keine
  `dataclasses.replace(..., snow_depth_cm=..., snowfall_limit_m=...,
  snow_new_sum_cm=...)`-Injektion wie in `_matrix_segment()`) / When der
  Testcode Metriken benennt, die dadurch strukturell keinen realen Wert
  tragen (z. B. `snowfall_limit` im Sommer — analog zur real beobachteten
  Abwesenheit von `SL` im Kontext-Dokument Abschnitt 1) / Then sind diese
  Metriken als benannte, kommentierte Ausnahme von der
  Kürzel-Präsenz-Prüfung geführt (AC-4/5/7/8/12 wählen ihre Ziel-Metrik NIE
  aus dieser Ausnahmeliste) — kein stiller Auffüller ersetzt echte Daten.
  - Test: Code-Review-Charakter (Kommentar-Pflicht im Testcode, keine
    isolierte Laufzeit-Assertion) + eine Positiv-Assertion, dass die
    gewählten Ziel-Metriken in AC-4/5/7/8/12 NICHT in der
    Ausnahmeliste stehen.

- **AC-11 (Premium-SMS-Charakterisierung — kein eigener Render-Aufruf
  nötig):** Given `output/channels/premium_sms.py` dokumentiert „Der
  Nachrichtentext ist unverändert `report.sms_text`" UND
  `trip_report.py:295` liest die SMS-Kaskade unter dem Schlüssel `"sms"`,
  nicht `"premium_sms"` / When AC-4 bis AC-8 gegen `report.sms_text`
  laufen / Then gilt jedes Ergebnis strukturell auch für Premium-SMS —
  ein separater Render-Aufruf für den Kanalnamen `"premium_sms"` würde
  denselben Text erneut prüfen, ohne zusätzliche Aussagekraft (es existiert
  heute keine eigene Kaskaden-Ebene `channel_layouts.premium_sms`).
  - Test: KEIN eigener Render-Test — stattdessen ein Charakterisierungstest,
    der die beiden Code-Referenzen oben direkt liest/zitiert (z. B. per
    `inspect`/Quelltext-Grep auf die dokumentierte Zusicherung) UND
    festhält, dass `dc.per_channel_layouts` keinen `"premium_sms"`-Schlüssel
    kennt, solange S2/S3 keinen einführen.

- **AC-12 (Reihenfolge wird mitgeprüft, nicht nur die Menge):** Given zwei
  Ein-Feld-Varianten der Basis-Fixture, die sich NUR in der `order` zweier
  bereits im SMS-Kanal-Layout aktiver, kollisionssicherer Metrik-IDs
  unterscheiden (A vor B bzw. B vor A) / When beide über den echten
  SMS-Renderpfad laufen / Then erscheinen die zugehörigen Kürzel im
  gerenderten `report.sms_text` in der jeweils vorgegebenen Reihenfolge —
  nicht in der festen `POSITIONAL`-Katalogreihenfolge
  (`tokens/builder.py:78`), die die Grundauswahl-Kaskade laut
  Kontext-Dokument Abschnitt 2 bewusst nicht anwendet.
  - Test: Vorbild `test_ac15_sms_kurzform_selection_deselection_and_order`
    Teil (c) im Bestand, hier gegen die fixture-geladene statt in-memory
    gebaute Config.

## Known Limitations

1. **Der historische KHW-Sendezeitpunkt-Zustand (05:00 UTC, 2026-08-11)
   bleibt nicht rekonstruierbar** (Trip-Datei wurde 05:53 UTC erneut
   geschrieben). Der Prüfstand reproduziert den STRUKTURELLEN
   Konstruktionsfehler (Ersetzung erlaubt Hinzufügen entgegen der
   Grundauswahl), nicht den exakten historischen Datensatz — das ist
   nach Kontext-Dokument Abschnitt 3 ausdrücklich ausreichend, weil der
   Fehler unabhängig vom konkreten Vorfall besteht.
2. **AC-7 bleibt nach dieser Scheibe bewusst ROT.** Das Beheben
   (`get_metrics_for_channel()` um einen Global-Maximum-Filter erweitern)
   ist S2, nicht Teil dieser Scheibe.

   **Wie das mit der CI-Ampel zusammengeht — verbindliche Vorgabe, ergänzt
   nach Spec-Review:** Ein dauerhaft roter Test verstößt gegen die
   Merge-Regel (alle 5 Checks grün) UND gegen die Test-Politik („Kern MUSS
   100 % grün sein: sofort fixen ODER löschen"). AC-7 wird deshalb als
   **`@pytest.mark.xfail(strict=True, reason="ADR-0050 Regel 2 — Kanal darf
   nicht hinzufügen; Umbau in #1719 S2")`** markiert. Begründung für
   `strict=True`:

   - Die Suite bleibt grün, die Auslieferung ist nicht blockiert.
   - Der Befund bleibt **sichtbar und ausgeführt** — kein `skip`, kein
     auskommentierter Test, keine Zeile in einer Ausnahmeliste.
   - **Sobald S2 den Fehler behebt, wird der Test grün und `strict=True`
     lässt ihn FEHLSCHLAGEN** (`XPASS`). Damit meldet der Prüfstand von
     selbst, dass die Ausnahme abgelaufen ist — die Markierung kann nicht
     stillschweigend überleben und zur Dauer-Ausnahme verkommen.

   Ein einfaches `xfail` ohne `strict` ist ausdrücklich **nicht** zulässig:
   es würde bei erfolgreicher Behebung stumm bleiben und wäre damit genau
   die Sorte Wächter, die nichts bewacht. Das Entfernen der Markierung ist
   Teil der Definition of Done von S2.
3. **ADR-0050 Regel 4 („Aus ist ein Zustand, keine Löschung") wird hier
   NICHT geprüft** — betrifft den Editor (Frontend), Umsetzung ist S3. Der
   Prüfstand dieser Scheibe ist reiner Python-Core-Test.
4. **Migrationsverhalten für Bestandstrips**, deren gespeicherte
   Kanal-Layouts schon heute Metriken „hinzufügen" (wie AC-7 es
   konstruiert), ist nicht Gegenstand dieser Scheibe — gehört in die
   S2-Spec (s. Offene Fragen).
5. **Metriken ohne realen Wert in `F.segment()`/`F.night_weather()`**
   werden nur auf Auswahl-Präsenz/Absenz geprüft, nicht auf
   Wert-Korrektheit — das ist der bewusste Trade-off aus AC-10.

## Nicht in dieser Scheibe

- **Backend-Umbau auf Verfeinerung** (`get_metrics_for_channel()` um
  Global-Maximum-Filter erweitern, damit AC-7 grün wird) — Scheibe S2.
- **Frontend** (Editor-Zustandsanzeige statt Löschung, `onRemove`/`onToggleMetric`-Verhalten,
  `CHANNEL_COL_BUDGET.sms`-Korrektur) — Scheibe S3.
- **Legende/Erklärtext zur Kaskade im UI** — Scheibe S4.
- **Auswertungswahl-Abschnitt „05 — Auswertungen"** (Trennlinie
  Platz-statt-Kanal-Entscheid) — Issue #1728.
- **3-Tages-Vorschau-Spalten, `show_night_block`-Bedienoberfläche** —
  Issues #1720/#1721.
- **Live-Vorschau „So kommt es an"** (wird ersatzlos entfernt) — Scheibe S3.

## Offene Fragen

- Der GitHub-Issue-Text #1719 selbst konnte in dieser Session nicht per
  `gh issue view` abgerufen werden (kein Bash-Werkzeug in diesem
  Agent-Aufruf verfügbar) — diese Spec stützt sich vollständig auf das
  bereits gemessene Kontext-Dokument. Sollte der Issue-Text zusätzliche
  oder abweichende Vorgaben enthalten, ist das vor Freigabe abzugleichen.
- Migrationsverhalten für Bestandstrips mit heute schon „erweiternden"
  Kanal-Layouts nach der S2-Umsetzung (stiller Rückfall auf AUS vs.
  explizite Migration/Nutzer-Meldung) ist ungeklärt — Entscheidung gehört
  in die S2-Spec, nicht hierher vorweggenommen.
- Die exakte Liste, welche der 26 Katalog-Metriken in `F.segment()`/
  `F.night_weather()` strukturell keinen realen Wert tragen (Null-Form)
  und damit als AC-10-Ausnahme gelten, ist erst beim Schreiben des
  Testcodes empirisch zu ermitteln — hier bewusst nicht vorweggenommen,
  um keine Vermutung in die Spec zu schreiben.
- Ob Premium-SMS künftig (S2/S3) eine EIGENE Kaskaden-Ebene
  (`channel_layouts.premium_sms`) bekommt oder dauerhaft an `"sms"` hängt,
  ist nicht im Kontext-Dokument entschieden und nicht Gegenstand dieser
  Scheibe.
- Ob die konstruierten Ein-Feld-Varianten (AC-4/5/7/12) als separate
  JSON-Dateien oder als Code-Varianten der geladenen Basis-Fixture abgelegt
  werden, ist eine Implementierungsentscheidung der TDD-RED-Phase — hier
  nur als Ansatz beschrieben (s. Implementation Details).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0050 (`docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md`).
- **Rationale:** Diese Scheibe SCHREIBT das ADR — es ist die fehlende
  Zusage, ohne die kein Prüfstand zwischen „korrekt" und „Bug"
  unterscheiden kann (Kontext-Dokument Abschnitt 5, „Übergeordnet").
  Ergänzt ADR-0049 (Kanalliste) um die Kaskadensemantik, die dort nicht
  behandelt wurde.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT
— oder nur dort, wo der Code steht?** Konkret: AC-4 bis AC-12 laufen
bewusst gegen die ECHTEN Renderpfade (`TripReportFormatter().format_email()`,
`render_for_channel()`) und eine über den ECHTEN Loader geparste,
anonymisierte Fixture — nicht gegen isolierte Hilfsfunktionen oder eine im
Speicher gebaute Zwei-Metriken-Attrappe (genau die Konstruktionsfehler 1/3
des Vorgänger-Wächters).

**Pflicht-Nachweis „Prüfstand kann ROT sein" (kein Mutations-Bedarf, weil
der Fehlerfall bereits im Ist-Zustand vorliegt):**

- **AC-7 MUSS beim ersten Lauf gegen den unveränderten `main`-Stand von
  `get_metrics_for_channel()` fehlschlagen.** Schlägt er nicht fehl, ist
  entweder (a) die gewählte Ziel-Metrik-ID versehentlich mit einer bereits
  global aktiven identisch (Kollision, prüfen wie `_partner_of()` im
  Bestand das für andere ACs vermeidet), oder (b) der Test prüft nicht den
  echten Renderpfad, sondern eine Zwischen-Repräsentation, die den
  heutigen Ersetzung-Fehler nicht durchreicht.
- **Zusätzliche Mutations-Gegenprobe (empfohlen, nicht zwingend, da AC-7
  bereits ohne Mutation rot ist):** in AC-8 probeweise nur
  `SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"][0]` statt aller drei Kürzel
  prüfen — muss die „alle drei verschwinden gemeinsam"-Aussage
  abschwächen und wäre damit der exakte Rückfall in den
  Vorgänger-Konstruktionsfehler #4.
- **Verwechslungsprobe:** in AC-7 versehentlich dieselbe Metrik-ID wie
  AC-6 (`wind_chill`) verwenden — muss aus zwei Gründen scheitern:
  `wind_chill` ist in der Basis-Fixture bereits GLOBAL aktiv (falsche
  Vorbedingung für AC-7, das eine global INAKTIVE Metrik braucht) und
  würde damit gar nicht den Widerspruch konstruieren, den AC-7 prüfen soll.

## Changelog

- 2026-08-11: Initial spec created (Issue #1719, Scheibe 1). Grundlage:
  `docs/context/fix-1719-s1-kaskade-pruefstand.md` (gemessen, Prod-Commit
  `64b78c63`). ADR-0050 in derselben Scheibe geschrieben, Index in
  `docs/adr/README.md` nachgezogen.
