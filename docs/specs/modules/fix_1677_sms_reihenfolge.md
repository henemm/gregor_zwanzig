---
entity_id: fix_1677_sms_reihenfolge
type: module
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.0"
tags: [metrics, sms, telegram, tokens, briefing, ordering]
---

<!-- Issue #1677 — Drag&Drop-Reihenfolge des SMS-Kanal-Tabs muss in der
     zugestellten Trip-Kurzform wirken (PO-Auftrag 2026-08-10: "Der User ist
     Experte, er wird nicht bevormundet"). Scheibe B: Vollstaendigkeits-Matrix
     Kanal x Metrik gegen die Fehlerklasse "Bedienelement ohne Wirkung". -->

# SMS-Kurzform: Nutzer-Reihenfolge aus dem SMS-Tab wirkt

## Approval

- [ ] Approved

## Purpose

Der Trip-Editor bietet für den SMS-Kanal einen eigenen Tab mit Drag&Drop-
Metrik-Reihenfolge (`WeatherMetricsTab`, `channel_layouts.sms`) — diese
Sortierung wird bereits gespeichert und wirkt in E-Mail-Spalten, Telegram-
rich und dem Ortsvergleich, aber NICHT in der Trip-Kurzform (SMS/Telegram-
Kurzform): `trip_report.py` kollabiert die sortierte Kaskaden-Liste in ein
Set, bevor sie `output/tokens/builder.py` erreicht, das anschließend eine
feste `POSITIONAL`-Tabelle anwendet. PO-Auftrag #1677: die im SMS-Tab
gezogene Reihenfolge muss dieselbe Wirkung entfalten wie in den anderen
Kanälen — ohne neue Bedienfläche, denn die Auswahlmechanik existiert
bereits (Muster von #1660 A/B). Zusätzlich verlangt der PO eine
Vollständigkeits-Matrix über Metrik-Katalog × Kanal, damit die Fehlerklasse
„Bedienelement ohne Wirkung" (#1450, #1362, #1660 A/B) strukturell bewacht
ist statt fallweise entdeckt zu werden.

## Source

> **Schicht-Hinweis:** Änderungen liegen ausschließlich im Python-Core.
> Quelle der Reihenfolge: `src/app/models.py` (`UnifiedWeatherDisplayConfig`,
> bereits vorhandene Kaskade). Transport + Sortierung: `src/output/tokens/`
> (bleibt frei von `src/app/`-Importen — Schichtgrenze). Verdrahtung:
> `src/output/renderers/trip_report.py`. Doku: `docs/reference/sms_format.md`.

### 1. Quelle der Reihenfolge (`src/app/models.py`) — kein neuer Ableitungsweg

`UnifiedWeatherDisplayConfig.get_metrics_for_channel("sms", report_type)`
liefert bereits eine nach Editor-Position sortierte **Liste**
(`_sorted_by_layout`, Issue #1575) über die dreistufige Kaskade
(per_report > per_channel > global). Diese Scheibe ändert an der Kaskade
selbst nichts — sie sorgt nur dafür, dass die Listen-**Reihenfolge**, statt
nur die Listen-**Menge**, den Renderer erreicht.

Neu: eine Methode `UnifiedWeatherDisplayConfig.cascade_source_for_channel(
channel: str, report_type: str) -> Literal["per_report", "per_channel",
"global"]`, die exakt dieselben drei Bedingungen wie
`get_metrics_for_channel` prüft (Ebene 1: `per_report_layouts[report_type]`
enthält `channel`; Ebene 2: `per_channel_layouts` enthält `channel`; sonst
`"global"`). `get_metrics_for_channel` und die neue Methode teilen sich die
Bedingungsprüfung (ein privater Helfer, keine zweite Kopie der drei
if-Zweige). `api/routers/validator.py::_determine_cascade_source` — bisher
laut eigenem Docstring ein bewusster **Spiegel** von
`get_metrics_for_channel` — wird auf einen Aufruf dieser neuen Methode
umgestellt; damit gibt es für „auf welcher Kaskadenebene antwortet der
SMS-Kanal?" nur noch EINEN Ableitungsweg, den Produktionscode und
Validator-Endpoint gemeinsam nutzen (Test-Referenz:
`tests/integration/test_issue_448_validator_metrics_for_channel.py` bleibt
grün, da sich das beobachtbare Verhalten des Endpoints nicht ändert).

### 2. Verdrahtung (`src/output/renderers/trip_report.py`)

- Zeile ~290-293 (Set-Kollaps) wird durch die **Liste** ersetzt:
  `sms_metrics_ordered = _dc_uncollapsed.get_metrics_for_channel("sms",
  report_type)`. Aus dieser Liste wird weiterhin `sms_metric_ids` (als Menge,
  für die bestehenden Abwahl-/Schwellwert-Ableitungen darunter unverändert)
  UND zusätzlich eine `position`-Zuordnung `metric_id -> index` abgeleitet.
- Aktivierungs-Gate (DEC-2): `position` wird NUR dann an die erzeugten
  `MetricSpec`-Objekte durchgereicht, wenn
  `_dc_uncollapsed.cascade_source_for_channel("sms", report_type)` `"per_report"`
  oder `"per_channel"` ist. Bei `"global"` bleibt `position=None` für ALLE
  Specs — der Builder fällt dann vollständig auf die bisherige
  `POSITIONAL`-Sortierung zurück (Byte-Identität, s. DEC-2).
- Für Mehrfach-Symbol-Metriken (`SMS_MULTI_SYMBOLS_BY_METRIC`: temperature,
  temperature_night, wind_chill, wind_chill_night, thunder) erhalten
  **alle** zugehörigen Symbole dieselbe `position` wie ihre Metrik (DEC-5) —
  die vorhandenen Erzeugungsstellen der jeweiligen `MetricSpec`-Objekte
  (`_disabled_sms_specs`-Aufbau, `build_extended_metric_specs`) werden um
  das additive `position`-Feld ergänzt, ohne ihre bestehende
  enabled/disabled-Logik zu verändern.

### 3. Transport (`src/output/tokens/dto.py`)

`MetricSpec` bekommt ein additives Feld `position: Optional[int] = None`
(frozen dataclass, Muster #1410/#1660 B — Default hält jeden
Bestandsaufrufer byte-identisch).

### 4. Sortierung (`src/output/tokens/builder.py::build_token_line`)

Die finale Sortierung (Zeile ~465-468) wird um eine erste Sortierstufe
erweitert: für jeden Token wird über `by_sym` die zugehörige `MetricSpec`
nachgeschlagen; trägt sie ein `position`, sortiert der Token danach
(Bucket 0); alle übrigen Token (kein Symbol-Spec, Spec ohne `position`,
oder Kategorien, die grundsätzlich nicht sortierbar sind — Vigilance,
amtliche Warnungen, Fire, `W?`, `DBG`) fallen in Bucket 1 und behalten dort
exakt die bisherige `POS_INDEX`-Reihenfolge als zweite Sortierstufe. Die
zweistufige Sortierung `(Bucket, Rang-innerhalb-Bucket)` ist stabil
(`list.sort`) und garantiert automatisch DEC-4 (System-Blöcke IMMER hinter
dem sortierbaren Block) — **nicht** durch explizites Verschieben der
System-Blöcke, sondern weil im Aktiv-Zustand alle sortierbaren Metriken
durchgehend `position` tragen und alle System-Blöcke nie eine `position`
haben. Im Default-Zustand (kein `position` bei irgendeinem Token) fallen
ausnahmslos alle Token in Bucket 1 — die Sortierung ist dann identisch zur
heutigen einstufigen `POS_INDEX`-Sortierung (Byte-Identität).

Die Kategorien `official_alert` (eigener `OFFICIAL_ALERT_POS`) bleiben von
dieser Änderung unberührt — amtliche Warnungen sind nicht Teil des
Metrik-Katalogs und tragen nie eine `position`.

### 5. Kürzung (`src/output/tokens/render.py`) — keine Änderung

`DROP_ORDER`, `PRIORITY` (builder.py) und `_strip_peaks`/`_truncate`
bleiben unverändert symbol-/prioritätsbasiert (DEC-6). Die
Anzeige-Reihenfolge (neu: Nutzer-Position) beeinflusst NICHT, welches Token
beim Kürzen zuerst fällt.

### 6. Doku (`docs/reference/sms_format.md`)

§2 wird versioniert erweitert (v2.23): Klarstellung, dass die in §2
gezeigte Reihenfolge der **Default** ist (kein SMS-Kanal-Layout aktiv);
ist eine SMS-spezifische Kaskadenebene (per_report/per_channel) für den
Trip gesetzt, bestimmt sie die Reihenfolge der Vorhersage-/
Wintersport-Token, während Vigilance-Adjazenz (§3.3), amtlicher Warn-Block,
Fire und die Blockstruktur unverändert fix bleiben.

## Estimated Scope

- **LoC:** ~90-140 produktiv (models.py Methode + Helfer-Extraktion ~25,
  trip_report.py Verdrahtung ~30-40, dto.py 1 Feld, builder.py
  Sortierschlüssel ~15, validator.py Umstellung auf den Helfer ~10). Scheibe
  B (Matrix-Tests über den Katalog × 3 Kanäle) treibt das Test-LoC-Delta
  deutlich über das 250-LoC-Grundlimit.
- **Files:** ~5 produktiv (`models.py`, `dto.py`, `builder.py`,
  `trip_report.py`, `api/routers/validator.py`) + 1 Referenz-Doku.
- **Effort:** medium (Mechanik ist additiv und folgt einem bereits
  etablierten Muster; die Matrix-Tests sind der größere Aufwandstreiber).

> **⚠️ LoC-Limit:** Mit den parametrisierten Matrix-Tests aus Scheibe B
> (Katalog × {E-Mail, Telegram-rich, SMS-Kurzform} × {Auswahl, Abwahl,
> Reihenfolge}) liegt das Gesamt-Delta voraussichtlich über dem
> 250-LoC-Grundlimit. `workflow.py set-field loc_limit_override` vorab beim
> PO einholen (CLAUDE.md), nicht erst bei der Blockade.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fix_1660a_temp_trennung` | Spec | Vorbild-Mechanik (Kanal-Kaskade, DEC-Stil, Kürzel-Bindung) |
| `fix_1660b_sms_token_wiring` | Spec | 14 erweiterte Metriken, `PRIORITY`/`POSITIONAL`/`DROP_ORDER`-Verdrahtung, die hier NICHT erneut geändert wird |
| `issue_448_validator_metrics_for_channel` (Archiv) | Spec | Vorhandener `_determine_cascade_source`-Spiegel, wird auf den neuen models.py-Helfer umgestellt |
| Kanal-Kaskade #429/#434/#1575 (`fix_1575_channel_metric_selection`) | Spec/Feature | Liefert die bereits sortierte SMS-Metrikliste, die diese Scheibe nutzt statt neu zu bauen |
| `sms_format` | Spec | Token-Grammatik v2.22, wird auf v2.23 fortgeschrieben |
| `metric_catalog.py` | Modul | Katalog-Reihenfolge als Default-Fallback (unverändert) |

## Implementation Details

Kernänderung in einem Satz: die SMS-Kaskade liefert bereits eine sortierte
LISTE (`get_metrics_for_channel`), aber `trip_report.py` faltet sie vor der
Weitergabe in ein Set zusammen — dieser eine Kollaps ist die Bruchstelle.
Der Fix ersetzt den Kollaps durch eine `position`-Annotation je `MetricSpec`
(additiv, Default `None`), aktiv nur wenn eine SMS-spezifische Kaskadenebene
antwortet (sonst bleibt alles beim Alten). `build_token_line` sortiert
zweistufig: positionierte Token zuerst nach `position`, alle übrigen
(inkl. sämtlicher System-Blöcke) danach unverändert nach `POS_INDEX`.

## Expected Behavior

- **Input:** Metrik-Reihenfolge aus dem SMS-Kanal-Tab des Trip-Editors
  (`per_channel_layouts.sms` oder `per_report_layouts[rt].sms`), gespeichert
  über die bestehende `PUT /api/trips/{id}/weather-config`-Route.
- **Output:** Trip-Kurzform (SMS-Text und Telegram-Kurzform-Zeile, identische
  `TokenLine`-Quelle) zeigt die gewählten Vorhersage-/Wintersport-Token in
  genau der vom Nutzer gezogenen Reihenfolge; System-Blöcke (Vigilance,
  amtliche Warnungen, Fire, `W?`, `DBG`) bleiben unverändert dahinter in
  ihrer bisherigen relativen Reihenfolge. Ohne SMS-spezifisches Layout:
  zeichengleiche Ausgabe zum Vorzustand.
- **Side effects:** keine neuen Datenabrufe, keine Schema-/Persistenz-
  Änderung (die Kaskaden-Struktur existiert bereits seit #429/#434); die
  Kürzungs-Rangfolge bei Überlänge bleibt unverändert sicherheitsbasiert.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit SMS-Kanal-Layout (`per_channel_layouts.sms`), in dem die Metriken in der Reihenfolge Böen (`gust`), Wind (`wind`), Niederschlag (`precipitation`) gezogen wurden (Default-Reihenfolge wäre Niederschlag, Wind, Böen) / When das Abendbriefing als SMS erzeugt wird / Then erscheinen die Token in der SMS in der Reihenfolge `G... W... R...` (Böen vor Wind vor Niederschlag), nicht in der Default-Reihenfolge `R... W... G...`.
  - Test: SMS-Rendering mit realistischem Forecast-Fixture, Assertion auf die exakte Token-Reihenfolge im gerenderten String (Regex-Positionsvergleich, kein bloßer `in`-Check).

- **AC-2:** Given ein Trip OHNE SMS-Kanal-Layout (weder `per_channel_layouts.sms` noch `per_report_layouts[rt].sms` gesetzt, nur eine globale Metrikliste) / When Abend- und Morgenbriefing als SMS gerendert werden / Then ist die Token-Reihenfolge exakt die heutige `POSITIONAL`-Reihenfolge — alle 5 Goldens in `tests/golden/sms/*.txt` bleiben unverändert grün, und ein zusätzlicher Zeichen-für-Zeichen-Vergleich gegen den Stand vor dieser Änderung bestätigt Byte-Identität für ein realistisches Nicht-Golden-Fixture.
  - Test: bestehende Golden-Suite läuft unverändert; zusätzlicher expliziter String-Vergleich für ein Fixture mit mehreren aktiven Metriken ohne SMS-Layout.

- **AC-3:** Given ein Trip mit `per_channel_layouts.sms` = Reihenfolge A (z.B. Wind, Regen, Böen) UND zusätzlich `per_report_layouts["evening"].sms` = Reihenfolge B (z.B. Böen, Wind, Regen) / When das Abendbriefing gerendert wird / Then folgt die SMS-Token-Reihenfolge B (per_report schlägt per_channel); wird stattdessen das Morgenbriefing gerendert (kein `per_report_layouts["morning"].sms` gesetzt) / Then folgt die SMS-Token-Reihenfolge A (per_channel greift als Fallback).
  - Test: zwei Renderings desselben Trips (`report_type="morning"`/`"evening"`), Assertion auf jeweils unterschiedliche, korrekt zugeordnete Token-Reihenfolge.

- **AC-4:** Given ein Trip mit SMS-Layout, das Gewitter (`thunder`) an erster Position führt, während zusätzlich echte Vigilance-Daten (`HR:`/`TH:`, französischer Provider) für dieselbe Etappe vorliegen / When die SMS gerendert wird / Then steht das Vorhersage-Gewitter-Token `TH:` (Kategorie `forecast`, Nutzer-Position 0) VOR dem Vigilance-Block, und `HR:`/`TH:` (Kategorie `vigilance`) bleiben unmittelbar aneinander fusioniert (`HR:...TH:...` ohne Leerzeichen dazwischen, §3.3) — unabhängig von der gewählten Nutzer-Reihenfolge.
  - Test: SMS-Rendering mit Vigilance-Fixture UND aktivem SMS-Layout, Assertion sowohl auf Block-Reihenfolge (forecast vor vigilance) als auch auf die ununterbrochene `HR:...TH:...`-Fusion (Regex ohne Leerzeichen).

- **AC-5:** Given ein Trip mit SMS-Layout, in dem „Temperatur" (`temperature`) an Position 2 und „Gefühlte Temperatur" (`wind_chill`) an Position 0 steht / When die SMS gerendert wird / Then erscheinen `FK`/`FD` (Windchill-Symbole) VOR `K`/`D` (Temperatur-Symbole), und innerhalb jedes Metrik-Ankers bleibt die interne Reihenfolge unverändert (`K` vor `D`, `FK` vor `FD`) — die Nutzer-Position gilt pro Metrik, nicht pro Symbol.
  - Test: SMS-Rendering mit beiden Metriken aktiv, Assertion auf Block-Reihenfolge (FK/FD-Paar vor K/D-Paar) UND auf die unveränderte interne Paar-Reihenfolge.

- **AC-6:** Given ein Trip mit SMS-Layout, das eine der 14 erweiterten Metriken (z.B. CAPE, `cape`) an erste Position setzt, kombiniert mit einem Fixture, das eine Zeilenlänge >160 Zeichen erzwingt (mehrere Wintersport- und Sicherheitsgrößen aktiv) / When die SMS gerendert und gekürzt wird / Then fällt `CP` trotz Position 0 als eines der ERSTEN Token weg (unverändert nach `DROP_ORDER`, direkt nach `DBG`), bevor auch nur ein Wintersport- oder Sicherheitstoken (`R`/`PR`/`W`/`G`/`TH:`) entfernt wird.
  - Test: konstruiertes Überlängen-Fixture mit aktivem SMS-Layout, Assertion auf die Reihenfolge des Wegfalls (welche Symbole zuerst verschwinden), nicht nur auf die Endlänge — Gegenprobe: Anzeige-Position ≠ Überlebensrang.

- **AC-7:** Given ein Trip mit SMS-Layout und einer Auswahl aus mindestens zwei Wintersport-Metriken (z.B. `snow_depth`, `avalanche_risk`) UND mindestens einer Vorhersage-Metrik, alle in einer vom Nutzer definierten Reihenfolge, die eine Wintersport-Metrik vor eine Vorhersage-Metrik setzt / When die SMS gerendert wird / Then folgt der Wintersport-Token (z.B. `SD`) direkt der Nutzer-Reihenfolge (erscheint vor dem später positionierten Vorhersage-Token), UND beide stehen trotzdem vor den nicht-sortierbaren System-Blöcken (Vigilance/Fire/`W?`/`DBG`).
  - Test: SMS-Rendering mit gemischter forecast+wintersport-Reihenfolge, Assertion auf die konkrete Token-Abfolge inkl. der System-Block-Grenze.

- **AC-8:** Given ein Ortsvergleich mit eigener globaler Metrik-Reihenfolge (`comparison.py`) UND ein Trip mit aktiver amtlicher Alarm-Konfiguration (`alert/render.py`, eigene Baustrecke) / When Compare-Kurzform bzw. Alert-SMS gerendert werden / Then bleibt ihre Token-Reihenfolge unverändert zum Stand vor dieser Änderung — bestehende Tests für `comparison.py` und `alert/render.py` laufen ohne Anpassung grün, kein Code in diesen beiden Pfaden wird berührt.
  - Test: bestehende Compare-SMS- und Alert-SMS-Testsuiten laufen unverändert grün (Regressionsnachweis, kein neuer Testcode nötig, sofern kein Code dort geändert wurde).

- **AC-9:** Given ein Trip mit `cascade_source_for_channel("sms", report_type)` == `"per_channel"` / When derselbe Zustand über `GET /api/_validator/metrics-for-channel?channel=sms&...` abgefragt wird / Then meldet der Validator-Endpoint `source: "per_channel"` — Produktionscode (Aktivierungs-Gate in `trip_report.py`) und Validator-Endpoint verwenden denselben models.py-Helfer, keine zweite, unabhängig gepflegte Bedingungsprüfung.
  - Test: ein Trip-Fixture wird sowohl über den Validator-Endpoint abgefragt als auch direkt gerendert; Assertion, dass der gemeldete `source`-Wert exakt dann `"per_report"`/`"per_channel"` ist, wenn die Nutzer-Reihenfolge in der SMS tatsächlich wirkt (Kopplung von Meldung und Wirkung).

- **AC-10:** Given ein Trip mit gewählten Metriken aus dem gesamten wählbaren Katalog (forecast + wintersport + die 14 erweiterten Metriken), einmal mit SMS-Layout A und einmal mit SMS-Layout B (zwei disjunkte Permutationen derselben Metrik-Menge) / When die SMS für beide Layouts gerendert wird / Then unterscheiden sich beide Ausgaben AUSSCHLIESSLICH in der Token-Reihenfolge — dieselbe Menge an Symbolen mit denselben Werten, aber zwei nachweisbar verschiedene Reihenfolgen.
  - Test: zwei Renderings desselben Fixtures mit vertauschtem Layout, Assertion auf identische Symbol-**Menge** UND verschiedene Symbol-**Reihenfolge** (Permutations-Nachweis).

- **AC-11:** Given ein Trip mit SMS-Layout und einer gewählten Metrik aus allen drei Grammatik-Klassen von #1660 B (z.B. `humidity`, `visibility`, `wind_direction`) in einer definierten Nutzer-Reihenfolge / When SMS-Text und Telegram-Kurzform-Zeile für dieselbe Etappe erzeugt werden / Then sind beide Token-Zeilen zeichengleich inklusive der Nutzer-Reihenfolge (gemeinsame `TokenLine`-Quelle, kein zweiter Rendering- oder Sortier-Pfad für Telegram).
  - Test: Rendering über beide Aufrufer (`SMSTripFormatter`/Telegram-Kurzform-Renderer), String-Vergleich der kompletten Zeile.

- **AC-12:** Given ein Trip mit allen 14 erweiterten Metriken plus mehreren Kern-Metriken in einer vom Nutzer definierten SMS-Reihenfolge, real gegen Staging zugestellt (Test-SMS bzw. E-Mail-Kurzform-Kopfzeile über das Test-Postfach, `GZ_TEST_IMAP_*`) / When die zugestellte Nachricht per IMAP abgerufen und geprüft wird / Then enthält der tatsächlich zugestellte Text die Token in der konfigurierten Nutzer-Reihenfolge — nicht nur eine Zwischenstufe im Renderer-Unit-Test (Prüfort = Wirkort, CLAUDE.md).
  - Test: `GET /api/preview/<trip>/sms` gegen Staging PLUS eine tatsächlich zugestellte Kurzform-Mail, Muster wie in `fix_1660b_sms_token_wiring` AC-15.

- **AC-13 (Matrix, Scheibe B — E-Mail):** Given jede wählbare Metrik des Katalogs einzeln aktiviert bzw. deaktiviert wird UND in zwei unterschiedlichen Kanal-Reihenfolgen konfiguriert wird / When das E-Mail-Briefing gerendert wird (`format_email`-HTML, Spaltenreihenfolge) / Then wirkt (a) die Aktivierung — die Metrik-Spalte erscheint —, (b) die Deaktivierung — die Spalte verschwindet —, (c) die Reihenfolge — zwei verschiedene Konfigurationen erzeugen zwei nachweisbar verschiedene Spaltenreihenfolgen, jeweils parametrisiert über den vollständigen Metrik-Katalog.
  - Test: parametrisierter Test über `metric_catalog`-Einträge × {aktiv, inaktiv, Reihenfolge A, Reihenfolge B}, Assertion an der gerenderten HTML-Spaltenstruktur (`_col_order`), nicht an der Konfiguration.

- **AC-14 (Matrix, Scheibe B — Telegram-rich):** Given dieselbe Parametrisierung wie AC-13, aber für das Telegram-rich-Layout (`narrow.py::render_for_channel`) / When das Telegram-Briefing gerendert wird / Then wirken Auswahl, Abwahl und Reihenfolge analog zu AC-13 im narrow-Layout.
  - Test: parametrisierter Test über den Katalog, Assertion an der gerenderten Telegram-Struktur (Reihenfolge der Bubbles/Zeilen).

- **AC-15 (Matrix, Scheibe B — SMS-Kurzform):** Given dieselbe Parametrisierung wie AC-13, jetzt für die SMS-Kurzform (`report.sms_text`) / When das Briefing als SMS gerendert wird / Then wirken (a) Auswahl, (b) Abwahl, (c) Reihenfolge wie in AC-1, UND zusätzlich (d) ohne gesetztes SMS-Layout ist die Ausgabe für jede Katalog-Metrik byte-identisch zum Stand vor dieser Änderung.
  - Test: parametrisierter Test über den vollständigen Metrik-Katalog × {aktiv/inaktiv, Reihenfolge A/B, mit/ohne SMS-Layout}, Assertion am gerenderten SMS-String — Ziel: die Fehlerklasse „Bedienelement ohne Wirkung" ist strukturell bewacht statt fallweise entdeckt.

## Known Limitations

1. **Compare-Editor bekommt keine Kanal-Tabs.** Der Ortsvergleich hat eine
   EINE globale Metrik-Reihenfolge (`wiz.activeMetricKeys`), keine
   SMS-spezifische Kaskadenebene — die Compare-Kurzform respektiert bereits
   diese globale Reihenfolge (unverändert, DEC-7). Dass Trip und Compare
   damit strukturell unterschiedliche Editor-Eingaben für „Reihenfolge"
   haben, ist ein bekannter Architektur-Mismatch, der hier nur dokumentiert,
   nicht behoben wird (kein neuer Kanal-Tab für Compare in dieser Scheibe).
2. **Keine Umsortierung der System-Blöcke.** Vigilance, amtlicher Warn-Block,
   Fire, `W?`, `DBG` bleiben in ihrer heutigen relativen Reihenfolge und
   Position (hinter dem sortierbaren Block) — sie sind nicht Teil der
   wählbaren Metrik-Kaskade und bekommen nie eine `position`.
3. **Kein neues UI.** Der SMS-Tab mit Drag&Drop existiert bereits; diese
   Scheibe verdrahtet ausschließlich seine bisher wirkungslose Ausgabe.
4. **`filter_for_subject` bleibt Stub** (wie in `fix_1660b_sms_token_wiring`
   dokumentiert) — außerhalb des Scopes dieser Scheibe.
5. **Keine Reihenfolge-Wirkung in Alert-SMS.** Die alarmgetriebene SMS
   (`alert/render.py`) nutzt eine eigene Baustrecke ohne `MetricSpec`/
   `TokenLine`-Kaskade und wird von dieser Scheibe nicht angefasst (DEC-7);
   eine Nutzer-Reihenfolge für Alarm-Token ist fachlich auch nicht sinnvoll
   (Alarme sind nach Dringlichkeit, nicht nach Vorliebe sortiert).
6. **`WC` (Windchill-Wintersport-Token) bleibt praktisch unerreichbar.**
   Wie in `sms_format.md` §3.6 dokumentiert, entsteht `WC` im Produktivpfad
   nie (nur Legacy-CLI `profile="wintersport"`) — die Mehrfach-Symbol-Bindung
   `wind_chill → (FK, FD, WC)` erhält trotzdem dieselbe `position`-Regel wie
   die übrigen Anker, ohne dass dies über den Trip-Versandweg beobachtbar
   wäre.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Schnitt schließt eine bestehende Lücke in einer bereits
  etablierten Kaskade (#429/#434/#1575) und einer bereits etablierten
  Token-Sortier-Infrastruktur (`POSITIONAL`/`POS_INDEX`, zuletzt erweitert
  durch #1660 A/B) um ein additives Sortierkriterium. Keine neue
  Persistenz-, Auth- oder Provider-Entscheidungsfläche.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT —
oder nur dort, wo der Code steht?**

1. **AC-2 (Byte-Identität).** Golden-Vergleiche müssen den **gerenderten
   Text** vergleichen, nicht nur, dass die Tests „grün" sind — ein Test, der
   nur prüft, dass keine Exception fliegt, deckt eine verschobene
   Reihenfolge nicht auf.
2. **AC-4 (System-Block-Grenze / HR:TH:-Fusion).** Ein Test ohne echte
   Vigilance-Daten kann die Adjazenz-Regel nicht brechen — es braucht ein
   Fixture, das `HR:`/`TH:` tatsächlich erzeugt, UND ein aktives SMS-Layout,
   das eine sortierbare Metrik VOR den Vigilance-Block schiebt.
3. **AC-6 (Kürzung).** Ein Fixture ohne echten Kürzungsdruck (<160 Zeichen)
   beweist nichts über die Drop-Reihenfolge, egal welche `position` gesetzt
   ist.
4. **AC-9 (kein zweiter Ableitungsweg).** Ein Test, der nur den
   Validator-Endpoint ODER nur den Renderer prüft, deckt ein Auseinanderlaufen
   beider Pfade nicht auf — es braucht den gekoppelten Vergleich.

**Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer
Sicherungskopie — nie `git checkout/stash/reset`):**

- Den Set-Kollaps in `trip_report.py` wieder einführen (`{m.metric_id for m
  in ...}` statt der Liste) — welcher Test wird rot? (Muss AC-1 sein, nicht
  nur ein Existenz-Check.)
- Das Aktivierungs-Gate (DEC-2) entfernen, sodass `position` IMMER gesetzt
  wird, auch ohne SMS-spezifisches Layout — werden die 5 Goldens
  (`tests/golden/sms/*.txt`) rot? (Muss der Fall sein, sonst prüft AC-2
  nichts.)
- Das `position`-Feld in `build_token_line` ignorieren (Sortierschlüssel
  bleibt einstufig `POS_INDEX`) — welcher Test bemerkt, dass die
  Nutzer-Reihenfolge wirkungslos bleibt? (Muss AC-1/AC-7/AC-10 sein.)
- Bei Mehrfach-Symbol-Metriken nur EINEM der zugehörigen Symbole die
  `position` zuweisen (z.B. nur `K`, nicht `D`) — fängt AC-5 den
  auseinanderlaufenden Anker?
- Den geteilten `cascade_source_for_channel`-Helfer in `trip_report.py`
  durch eine eigene, unabhängig geschriebene Bedingungsprüfung ersetzen
  (zweiter Ableitungsweg) und in `api/routers/validator.py` gezielt eine
  abweichende Formulierung derselben Bedingung belassen — fängt AC-9 das
  Auseinanderdriften, wenn eine der beiden Stellen künftig geändert wird,
  ohne die andere nachzuziehen?
- `DROP_ORDER` unverändert lassen, aber die Kürzungs-Reihenfolge testweise
  an der `position` statt an `PRIORITY`/`DROP_ORDER` ausrichten — wird AC-6
  rot? (Belegt, dass Anzeige-Reihenfolge und Überlebensrang tatsächlich
  entkoppelt geprüft sind.)

## Changelog

- 2026-08-10: Initial spec created (Issue #1677)
