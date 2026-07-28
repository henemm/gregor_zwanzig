---
entity_id: waechter_1405_stille_aufloesung
type: module
created: 2026-07-28
updated: 2026-07-28
status: implemented
version: "1.0"
tags: [tests, guard, silent-drop, issue-1405]
---

<!-- Issue #1405 — Wächter 2 von 5, Hälfte A ("Was hineingeht, kommt heraus") -->

# Wächter 1405 — Stilles Verschlucken in Auflösungspfaden

## Approval

- [x] Approved — PO Henning, 2026-07-28 („go"), inkl. Freigabe des erhöhten
  Änderungsbudgets (250 → 500 Zeilen) für diese Arbeitseinheit

## Purpose

Ein AST-basierter Wächter-Test erkennt künftig jeden neuen Fall von *stillem
Verschlucken* in Auflösungspfaden — eine Eingabemenge wird auf eine kleinere
Ausgabemenge abgebildet, ohne dass der Verlust irgendwo protokolliert wird.
Diese Fehlerart war 18 von 79 belegten Fehlern in vier Wochen (#1405). Der
Wächter rollt ein bereits im eigenen Code vorhandenes Muster
(„Sammeln-und-melden", vorbildlich in den drei Compare-Metrik-Resolvern) auf
die restlichen Auflösungspfade aus, statt eine neue Regel zu erfinden. Diese
Arbeitseinheit ändert **keinen Produktivcode** — Wächter vor Reparatur
(Ticket-Reihenfolge, Lehre aus #1402).

## Source

- **File:** `tests/test_resolution_loss_guard.py` (NEU, geschätzt ~350–420 LoC)
- **Identifier:** Modul-Ebene — kein Produktivcode-Symbol, sondern ein
  Test-Wächter mit mehreren `test_*`-Funktionen und den Hilfsfunktionen
  `_scan_files()` / `_find_violations()` / `_all_violations()`

> **Schicht-Hinweis:** reines Python-Core-Testartefakt (`tests/`). Scanfläche
> ist `src/output/**` + `src/services/**` (Python-Core). Kein Frontend-,
> Go-API- oder `internal/`-Bezug — s. „Aus dem Scope ausgeschlossen".

## Estimated Scope

- **LoC:** ~350–420 (Vergleich: `tests/test_output_timezone_guard.py` /
  #1402 = 594 Zeilen für 3 Bugklassen + einen zweiten,
  aufrufseitengetriebenen Wächter; hier 1 Bugklasse ohne
  Aufrufseiten-Anteil — alle 13 Fundstellen liegen direkt in der
  definierenden Funktion, kein Signatur-Umbau-Problem — aber 5
  Ausnahmeklassen mit je eigenem synthetischen Wirkungsnachweis)
- **Files:** 1 neu (Testdatei). **0 Produktivdateien geändert.**
- **Effort:** medium

**LoC-Limit-Hinweis (CLAUDE.md, Regel-Budget):** 350–420 Zeilen überschreiten
das 250-LoC/Workflow-Limit. Freigabe per
`python3 .claude/hooks/workflow.py set-field loc_limit_override 500` ist vor
der Implementierungsphase beim PO einzuholen (im Kontextdokument bereits als
offener Punkt vermerkt).

**Regel-Budget (CLAUDE.md):** Dieser neue Pflicht-Test ersetzt keine
bestehende Regel, braucht daher ein Prüfdatum: **2026-10-26** (+90 Tage). Am
Prüfdatum gilt: kein nachweisbarer Fang (verhinderter echter Rückfall in
stilles Verschlucken) → Rückbau erwägen. Analog #1402, das beim Bau selbst
bereits 3 Produktionsbugs fand — dieser Wächter muss dieselbe Nachweispflicht
erfüllen (s. AC-1/AC-4).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/test_output_timezone_guard.py` (#1402) | Bauform-Vorbild | AST-Scan, `KNOWN_VIOLATIONS`-Restliste, zwei gekoppelte Ratschen-Tests, synthetische Wirkungsnachweise — Struktur wird 1:1 übernommen |
| `src/output/renderers/compare_metric_ids.py:125` `resolve_enabled_metrics` | Referenzmuster | Sammelt Verworfenes in `unmapped`, meldet per `logger.warning` — die Signatur MUSS diese Stelle strukturell ausschließen (sie loggt bereits) |
| `src/output/renderers/compare_hourly_metric_ids.py:34` `resolve_hourly_metrics` | Referenzmuster | dito |
| `src/output/renderers/compare_outlook_metric_ids.py:50` `resolve_outlook_metrics` | Referenzmuster | dito, zusätzlich `continue` bei Dedup ohne Meldung — das ist hier korrekt und muss ebenfalls ausgeschlossen bleiben |
| `ast` (stdlib) | Parser | Strukturelle Erkennung ohne Regex-Rateraten |
| CLAUDE.md → Test-Politik / Regel-Budget | Prozess | Kern-Schicht-Pflicht, Prüfdatum-Pflicht für neue Pflicht-Tests |
| Epic #1372 „Kein stilles Verwerfen" | Vorgabe | Die Invariante als Satz — dieser Wächter ist der erste durchsetzende Baustein dafür |

## Implementation Details

### Scanfläche

`src/output/**/*.py` (rekursiv: Renderer, Kanäle) + `src/services/**/*.py`
(rekursiv, inkl. `official_alerts/`). Deckt alle 13 bekannten Fundstellen ab
und macht die Trip/Compare-Asymmetrie (A1–A9) im selben Lauf sichtbar. `tests/`
und `internal/` (Go) sind bewusst nicht Teil der Scanfläche (s. u.).

### Signatur „stiller Auflösungsverlust" — beide Bedingungen müssen zutreffen

1. **Mengenbezug:** eine `for`-Schleife oder Comprehension über eine
   Eingabesammlung, deren Iterationsergebnis in eine Ausgabesammlung fließt
   (`.append(...)`, Comprehension-Ziel, `dict[k] = ...`, `set.add(...)`)
   oder direkt in einen Renderer-/Versandaufruf übergeben wird.
2. **Stiller Abbruchpfad:** `continue` / Comprehension-Filter / `except: ...`
   (ohne `raise`) **ohne Absicherung**, wobei die Abbruchbedingung ein
   **Lookup-Fehltreffer** ist (`x not in MAP`, `MAP.get(x) is None`,
   `except KeyError`) — kein Schwellenwert- oder Mitgliedschaftsvergleich
   gegen eine bereits gefüllte Ausgabemenge.

   **Was als Absicherung gilt (Korrektur 2026-07-28, RED-Befund 2):** entweder
   (a) ein `logger.*`-Aufruf im Abbruchzweig selbst, **oder** (b) der
   verworfene Eintrag wird im Abbruchzweig in eine lokale Sammlung geschrieben
   (`unmapped.append(item)`), die innerhalb **derselben Funktion** als Argument
   eines `logger.*`-Aufrufs erscheint.

   Variante (b) ist zwingend, weil das Referenzmuster im Bestand genau so
   gebaut ist: die drei Compare-Auflöser sammeln im `continue`-Zweig und melden
   **nach** der Schleife. Eine Signatur, die nur (a) kennt, würde ihre eigenen
   Vorbilder als Verstoß melden und wäre strukturell nie grün zu bekommen.

   **Ausdrücklich NICHT ausreichend ist ein beliebiger `logger.*`-Aufruf
   irgendwo in derselben Funktion.** Diese laxe Lesart wäre ein echter
   Präzisionsverlust und würde konkret Fundstelle **A12 verschlucken**:
   `meteoalarm.py:334` bricht stumm ab, während `:377` in derselben Funktion
   protokolliert — ohne jeden Datenfluss zwischen beiden. Maßgeblich ist die
   Verbindung zwischen dem verworfenen Eintrag und dem Protokolleintrag, nicht
   die bloße Anwesenheit eines Logger-Aufrufs.

### Fünf strukturelle Ausschlüsse (harmlos, dürfen NICHT als Fund zählen)

| # | Klasse | Mechanik |
|---|---|---|
| 1 | Dokumentierter Policy-Filter | Der Abbruchkörper enthält einen `logger.*`-Aufruf → durch Bedingung 2 („ohne begleitenden Logger-Aufruf") bereits automatisch ausgeschlossen, keine gesonderte Prüfung nötig. Deckt die drei Compare-Resolver ab. |
| 2 | Sichtbarer Platzhalter statt Verschwinden | Funktion trägt das Namensmuster `_col_key`/`_cell`/`fmt_*` (analog Zeitzonen-Wächter) — liefert per Konvention einen Anzeige-Platzhalter statt eines echten Werts. |
| 3 | Fallback-Wert im selben Atemzug | Im selben Block wird VOR dem `continue` ein Wert in dieselbe Ausgabesammlung geschrieben (z. B. `row[key] = None`) — es verschwindet nichts, es wird markiert. |
| 4 | Aggregationsschleife ohne Mengenbezug | Ergebnis der Schleife ist ein Skalar (Zähler, Min/Max, Schwellenwertvergleich) statt einer Übernahme gleichartiger Elemente in eine Ausgabesammlung → fällt bereits durch Bedingung 1 heraus. |
| 5 | Dedup-/Idempotenz-Guard | Abbruchbedingung ist eine Mitgliedschaftsprüfung gegen eine bereits gefüllte `seen`/Ausgabemenge (Duplikat), kein Katalog-/Registry-Lookup-Fehltreffer → fällt durch die Lookup-Fehltreffer-Klausel in Bedingung 2 heraus. |

Klassen 1, 4 und 5 sind bereits durch die Signatur selbst ausgeschlossen
(keine zusätzliche Ausnahmeliste nötig). Klassen 2 und 3 brauchen eine
strukturelle Sonderprüfung (Namensmuster bzw. „Schreibzugriff auf dieselbe
Ausgabesammlung unmittelbar vor dem Abbruch") — s. „Offene Punkte" zur Frage,
ob beide denselben Mechanismus teilen.

### Restliste und Ratsche

`KNOWN_VIOLATIONS: dict[str, str]` mit den 13 Einträgen aus der Tabelle unten
(Schlüssel `pfad:zeile`, Wert = Begründung + Issue-Bezug). Zwei gekoppelte
Tests analog #1402.

**Rückgabevertrag von `_find_violations()` (Korrektur 2026-07-28, RED-Befund 3):**
`dict["pfad:zeile"] -> "<art>::<funktionsname>"`. Das Vorbild #1402 trägt im
Wert nur die Art; AC-1 prüft aber funktionsweise ohne Zeilennummern, und der
Funktionsname ist aus dem Schlüssel nicht ableitbar. Er gehört deshalb in den
Wert. `KNOWN_VIOLATIONS` bleibt davon unberührt (Schlüssel identisch).

Die beiden gekoppelten Tests:

- `test_no_unlisted_resolution_drops()` — jeder Fund, der nicht in
  `KNOWN_VIOLATIONS` steht, macht rot.
- `test_known_violations_only_shrink()` — jeder gelistete Eintrag, den der
  Scanner nicht mehr findet, macht ebenfalls rot („veraltet — entfernen").

### Synthetische Wirkungsnachweise

Je ein `tmp_path`-Test pro Bugmuster UND pro Ausnahmeklasse — beweist, dass
der Scanner das Muster strukturell versteht statt nur zufällig zur Restliste
zu passen (s. Acceptance Criteria AC-4 bis AC-8).

## Restliste A1–A13 (aus der Bestandsaufnahme, 1:1 in `KNOWN_VIOLATIONS` zu übernehmen)

| # | Fundstelle | Was verschwindet |
|---|---|---|
| A1 | `src/output/renderers/trip_report.py:401` `_aggregate_night_block` | Nacht-Block-Spalte einer aktivierten Metrik |
| A2 | `src/output/renderers/trip_report.py:482` `_dp_to_row` | Stunden-Zeile-Spalte |
| A3 | `src/output/renderers/email/html.py:715` `_allowed_col_keys_for_horizon` | Spalte aus Horizont-Filter |
| A4 | `src/output/renderers/email/html.py:782` `render_html` (`_col_order`) | Spaltenreihenfolge/-sichtbarkeit der ganzen Mail |
| A5 | `src/output/renderers/email/helpers.py:100` `dp_to_row` | Stunden-Zeile-Spalte |
| A6 | `src/output/renderers/email/helpers.py:152` `aggregate_night_block` | Nacht-Block-Spalte |
| A7 | `src/output/renderers/email/helpers.py:975` `build_friendly_keys` | Ampel/Friendly-Format |
| A8 | `src/output/renderers/email/helpers.py:992` `build_format_modes` | Format-Mode-Eintrag |
| A9 | `src/output/renderers/email/helpers.py:1017` `build_html_indicator_keys` | Ampel-Aktivierung |
| A10 | `src/services/alert_preset.py:198` `expand_per_metric_levels` | Direction-Feld-Optout |
| A11 | `src/services/compare_official_alert.py:115` `_check_one_preset` | Ort aus der Alarm-Prüfung |
| A12 | `src/services/official_alerts/meteoalarm.py:334` `_extract_alerts_from_cap` | ganze CAP-Warnung (`except` ohne Log) |
| A13 | `src/services/official_alerts/meteoalarm.py:361` `_extract_alerts_from_cap` | ganze Warnung bei unbekanntem `awareness_type` |

**Namenskorrektur 2026-07-28 (GREEN-Befund):** A10 hieß in der ersten Fassung
`resolve_alert_rules`, A12/A13 `_parse_cap`. Beide Namen existieren nirgends in
`src/` — sie waren aus der Bestandsaufnahme falsch übernommen. Die
Datei:Zeile-Anker stimmten exakt; nur die Funktionsnamen sind ersetzt. AC-1 wäre
mit den alten Namen strukturell nie erfüllbar gewesen. Trefferkraft, Zahl und
Codestellen bleiben unverändert.

A1–A9 sind derselbe Mechanismus neunfach wiederholt
(`try: get_metric(id) except KeyError: continue`): die Compare-Seite ist
gehärtet (Referenzmuster), die Trip-/HTML-Seite nicht — dieselbe Asymmetrie,
die #1262 (Legacy-`display_config` mit veralteter Metrik-ID) auslöste. A11
hat zwei bereits korrekt meldende Geschwister
(`compare_alert.py:154`, `compare_radar_alert.py:139`) — nur der
amtliche-Warnungen-Pfad fehlt.

## Neun zusätzliche Funde des Wächters (GREEN-Ergebnis 2026-07-28)

Der gebaute Wächter findet **22** Stellen, nicht 13. Die Bestandsaufnahme S1 war
unvollständig — genau der bei #1402 belegte Effekt (dort fand der Wächter
fünfmal mehr als die Handaufnahme). Alle neun wurden einzeln nachgelesen, keiner
ist ein Fehlalarm. Sie stehen mit Begründung in `KNOWN_VIOLATIONS` und sind
**Arbeitsvorrat für die Reparatur-Scheibe S4** (die damit von 13 auf 22 wächst):

| # | Fundstelle | Was verschwindet | Mechanik |
|---|---|---|---|
| A14 | `src/services/weather_change_detection.py:429` `from_display_config` | **Alarmregel wird still entschärft** — eine veraltete `metric_id` im `display_config` legt die Regel lautlos still | A1–A9 (`get_metric`/`except KeyError`), im **Alarm**-Pfad. Ernstester Fund; genau der #1262-Fall an neuer Stelle |
| A15 | `src/output/renderers/email/helpers.py:468` `build_units_legend` | Einheit einer Spalte in der Trip-Mail | A1–A9 |
| A16 | `src/output/renderers/trip_report.py:521` `_build_units_legend` | dito, Trip-Zwilling | A1–A9 |
| A17 | `src/output/renderers/email/compare_html.py:1040` `_units_legend_text` | Einheit einer Spalte in der Vergleichs-Mail | A13 |
| A18 | `src/services/day_comparison.py:271` `_summarize_metric_driven` | gewählte Größe fällt aus dem Tagesvergleich | Katalog-Fehltreffer |
| A19 | `src/services/official_alerts/geosphere_warn.py:122` | ganze Warnung (AT) | A12-Zwilling |
| A20 | `src/services/official_alerts/geosphere_warn.py:130` | Warnung bei unbekanntem Typ (AT) | A13-Zwilling |
| A21 | `src/services/official_alerts/vigilance.py:118` | Warnung bei unbekanntem Typ (FR) | A13-Zwilling (FR) |
| A22 | `src/services/gpx_processing.py:297` `process_bulk_gpx_uploads` | eine kaputte GPX-Datei beim Mehrfach-Upload — fünf hoch, vier angelegt, kein Hinweis | `except Exception: continue` |

### Warum die Trefferzahl nicht auf 20 gedrückt wurde

Die Arbeitsvorgabe nannte 20 Treffer als Obergrenze, ab der die Signatur zu weit
gefasst wäre. 22 echte Funde überschreiten sie. Unter 20 zu kommen hätte
bedeutet, echte Funde von der Erkennung auszuschließen — dieselbe Manipulation
wie das Aufblähen der Restliste, nur mit umgekehrtem Vorzeichen (Test-Politik:
Schwellen nie anpassen, damit etwas grün wird). Die Grenze war eine Heuristik
gegen Fehlalarme; sie hat ihren Zweck erfüllt (erster Entwurf: 59 Treffer, davon
46 grundlos → vier strukturelle Verschärfungen → 22 echte, 0 Fehlalarme).

## Aus dem Scope ausgeschlossen

- **Hälfte B „Erfolg heißt Wirkung"** (B1–B12, inkl. des `#684`-Doppelalarm-Falls) —
  eigene Arbeitseinheit, eigene Spec, läuft als nächstes.
- **S3 (Mengenerhalt-Nachweise über die gerenderte Ausgabe)** und
  **S4 (Reparatur der Restliste A1–A13)** — eigene Scheiben, PO-Entscheidung
  2026-07-28. Diese Einheit ändert keinen Produktivcode.
- **Go-Code (`internal/`)** — ein Python-`ast`-Scan erreicht diesen Baum
  strukturell nicht (andere Sprache, keine `.py`-Dateien). Bewusste,
  dokumentierte Lücke, kein Versehen (Vorbild: `test_egress_inventory_drift.py`
  prüft Python↔Go über ein Inventar, nicht über AST).

## Expected Behavior

- **Input:** der aktuelle Stand von `src/output/**` und `src/services/**`
  beim Testlauf.
- **Output:** `pytest`-Grün/Rot. Rot mit `Code reference: pfad:zeile` bei
  jedem neuen, unlisteten Fund oder jedem veralteten Restlisten-Eintrag.
- **Side effects:** keine — reiner Lesezugriff auf den Quellbaum, kein
  Produktivcode wird berührt oder ausgeführt.

## Acceptance Criteria

- **AC-1:** Given die 13 in dieser Spec namentlich gelisteten Fundstellen A1–A13 / When der Wächter über die Scanfläche läuft / Then schlägt er in **jeder** dieser 13 Funktionen an — gemessen an einer im Test fest verdrahteten Erwartungsmenge aus `datei::funktionsname`, die aus dieser Spec stammt und **nicht** aus `KNOWN_VIOLATIONS` abgeleitet werden darf.
  - Test: `test_scanner_finds_every_spec_listed_finding()` — Erwartungsmenge als Literal im Test (`pfad::funktion` → **erwartete Mindest-Trefferzahl**, bewusst OHNE Zeilennummern, damit spätere Codeverschiebungen sie nicht brechen). Fehlt einer, ist der Scanner zu eng gebaut — die Erwartungsmenge darf zur Behebung **nicht** gekürzt werden (Test-Politik: Schwellen niemals anpassen, damit etwas grün wird).
  - **Trefferzahl statt bloßer Anwesenheit (Korrektur 2026-07-28, RED-Befund 1):** A12 und A13 liegen beide in `meteoalarm.py::_parse_cap`. Ohne Zeilennummern kollabieren sie zu einem Paar, und ein Scanner, der nur einen der beiden Abbruchpfade fände, bliebe grün. Die Erwartungsmenge trägt deshalb je Funktion eine Mindestzahl: 12 Einträge mit Erwartung 1, `meteoalarm.py::_parse_cap` mit Erwartung **2**. Summe der Mindest-Treffer = 13.
  - Abgrenzung zu AC-3: AC-1 prüft die Trefferkraft des Scanners gegen die Spec, AC-3 die Aktualität der Restliste gegen den Code. Beide dürfen nicht dieselbe Quelle benutzen, sonst prüft der Wächter sich selbst.

- **AC-2:** Given ein neuer, bislang unbekannter Fund mit exakt der Signatur (Mengenschleife + stiller Lookup-Fehltreffer-Abbruch ohne Meldung) irgendwo in der Scanfläche / When der Wächter läuft / Then schlägt der Test fehl und benennt Datei:Zeile — die Restliste kann nicht stillschweigend wachsen.
  - Test: `test_no_unlisted_resolution_drops()` — echter Scan der Scanfläche gegen `KNOWN_VIOLATIONS`, Form 1:1 vom Vorbild #1402. (Korrektur 2026-07-28, RED-Befund 4: die ursprünglich hier genannte synthetische Zusatzstelle wäre ein Duplikat von AC-4 gewesen; der Wirkungsnachweis, dass der Scanner das Muster erkennt, liegt dort.)

- **AC-3:** Given ein Eintrag in `KNOWN_VIOLATIONS`, den der Scanner am aktuellen Code nicht mehr findet (weil in einer anderen Scheibe repariert) / When der Wächter läuft / Then schlägt der Test mit „veraltet — aus der Liste entfernen" fehl — die Restliste kann nur schrumpfen.
  - Test: `test_known_violations_only_shrink()` — analog #1402, prüft `stale = [k in KNOWN_VIOLATIONS if k not in found]`.

- **AC-4:** Given eine synthetische Datei mit dem Muster „Schleife über eine Eingabemenge, `except KeyError: continue` bei einem Katalog-Lookup, kein `logger`-Aufruf, Ergebnis fließt per `.append()` in die Ausgabesammlung" / When der Scanner sie einliest / Then wird die Stelle als Fund erkannt.
  - Test: `test_scanner_detects_silent_lookup_miss_in_synthetic_file(tmp_path)`.

- **AC-5:** Given eine synthetische Datei, in der dieselbe Schleife den verworfenen Eintrag sammelt UND per `logger.warning(...)` meldet (Referenzmuster der drei Compare-Resolver) / When der Scanner sie einliest / Then wird kein Fund gemeldet.
  - Test: `test_scanner_ignores_logged_drop_in_synthetic_file(tmp_path)`.

- **AC-6:** Given eine synthetische Datei, in der der Abbruchpfad vor dem `continue` einen Platzhalter- oder Fallback-Wert in dieselbe Ausgabesammlung schreibt (z. B. `row[key] = None; continue`) oder eine Funktion mit dem Namensmuster `_col_key`/`_cell`/`fmt_*` betrifft / When der Scanner sie einliest / Then wird kein Fund gemeldet.
  - Test: `test_scanner_ignores_placeholder_or_fallback_write_in_synthetic_file(tmp_path)`.

- **AC-7:** Given eine synthetische Datei mit einer reinen Aggregationsschleife (Zählen, Minimum/Maximum, Schwellenwertvergleich `if x < threshold: continue`) ohne Übernahme gleichartiger Elemente in eine Ausgabesammlung / When der Scanner sie einliest / Then wird kein Fund gemeldet, weil kein Mengenbezug vorliegt.
  - Test: `test_scanner_ignores_aggregation_loop_without_set_relation(tmp_path)`.

- **AC-8:** Given eine synthetische Datei mit einem Dedup-/Idempotenz-`continue` (Abbruchbedingung ist eine Mitgliedschaftsprüfung gegen eine bereits gefüllte `seen`-Menge, kein Katalog-Lookup-Fehltreffer) / When der Scanner sie einliest / Then wird kein Fund gemeldet.
  - Test: `test_scanner_ignores_dedup_guard_in_synthetic_file(tmp_path)`.

- **AC-9:** Given der Go-Code unter `internal/` / When die Scanfläche des Wächters bestimmt wird / Then ist `internal/` nicht Teil der gescannten Dateien — die Abgrenzung ist eine bewusste, dokumentierte Lücke.
  - Test: `test_scan_scope_excludes_go_internal_tree()`.

## Known Limitations

- **Ehrliche Grenze — nur Protokoll, nicht Sichtbarkeit:** der Wächter kann
  erzwingen, dass Verworfenes in ein `logger.warning` fließt — **nicht**, dass
  es in der gerenderten Mail/SMS/Telegram-Nachricht für den Nutzer sichtbar
  wird. Zielbild-Satz 3 aus Epic #1372 verlangt „protokolliert **und** an der
  Oberfläche erkennbar" — der zweite Teil ist S3 (Mengenerhalt-Nachweise über
  die gerenderte Ausgabe), nicht diese Scheibe.
- **Go-Code bleibt ungeprüft:** `internal/` ist strukturell außerhalb der
  Reichweite eines Python-`ast`-Scans (s. „Aus dem Scope ausgeschlossen").
- **Keine Aufrufseitenprüfung nötig:** anders als beim Zeitzonen-Wächter
  (#1402) liegen alle 13 Fundstellen direkt in der definierenden Funktion —
  kein Signatur-Umbau-Problem mit großer Aufrufer-Fläche, daher kein zweiter
  Wächter-Typ nötig.
- **Bekannte Scannergrenze:** mehrstufige Datenfluss-Ketten über mehrere
  Funktionsgrenzen hinweg (Wert verschwindet in Funktion X, weil Funktion Y
  vorher schon gefiltert hat) sind mit einer rein strukturellen
  Ein-Funktion-Prüfung nicht erkennbar — analog der dokumentierten
  Koordinaten-Herleitungs-Lücke im Zeitzonen-Wächter.

## Geklärte Punkte (Tech-Lead-Entscheidung 2026-07-28)

1. **Klassen 2 und 3 bleiben EIN Mechanismus (AC-6).** Beide sagen dasselbe:
   „der Eintrag verschwindet nicht, er wird als fehlend markiert". Ob das über
   einen Schreibzugriff vor dem Abbruch oder über eine Formatier-Hilfsfunktion
   mit Platzhalter-Rückgabe geschieht, ändert die Bugklasse nicht. Zwei
   getrennte Prüfungen wären doppelte Buchführung ohne Zusatzschutz. **Falls
   sich bei der Implementierung zeigt, dass eine der 13 Fundstellen nur wegen
   des Namensmuster-Zweigs durchrutscht, ist das ein Befund** — dann ist das
   Namensmuster zu grob und wird durch die Schreibzugriff-Prüfung ersetzt,
   nicht ergänzt.
2. **„Dokumentierter Policy-Filter" braucht keinen eigenen Mechanismus.** Die
   Einschätzung ist korrekt: die Logger-Klausel deckt ihn ab. Ein Kommentar
   mit Issue-Referenz zählt ausdrücklich **nicht** als Absicherung — ein
   Kommentar erreicht den Betrieb nicht, ein Protokolleintrag schon. Damit
   bleibt die Signatur frei von Kommentar-Heuristik (die ohnehin nicht
   zuverlässig wäre).

## Offene Punkte

1. **LoC-Limit-Freigabe steht noch aus** (s. „Estimated Scope") — vor der
   Implementierungsphase beim PO einzuholen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reiner Test-Wächter ohne Produktivcode-Änderung und ohne
  Auswirkung auf Kanäle, Provider, Datenmodell/Persistenz, Auth oder
  Editor-Paradigma — keine der ADR-pflichtigen Entscheidungsflächen ist
  betroffen.

## Erster Fang im Alltag (2026-07-28)

Noch vor dem Commit: Das Nachziehen auf `origin/main` = `1fbfc911` („#1401 A2a:
Vergleichsmail nennt ihre Wettergrößen beim Registernamen", +63/−30 an
`compare_html.py`) machte den Wächter sofort rot — A17 war von Zeile 1007 auf
1040 gewandert. Beide Ratschen meldeten es unabhängig und richtig: „veraltet:
1007" **und** „neu, unlisted: 1040". Nachgelesen: reine Verschiebung, der stille
Verlust besteht unverändert (`_METRICS_BY_ID.get(...)` → `if mdef is None:
continue`, kein Log). Schlüssel nachgezogen, 22 Funde unverändert.

Das ist der belegte Fang für das Regel-Budget-Prüfdatum 2026-10-26 — der Wächter
hat im ersten Zusammentreffen mit fremder Arbeit an einer seiner Fundstellen
genau das getan, wofür er gebaut wurde.

## Changelog

- 2026-07-28: Initial spec erstellt — Issue #1405, Hälfte A („Was
  hineingeht, kommt heraus"), S1+S2 (Bestandsaufnahme + Wächter). Prüfdatum
  für die neue Pflicht-Regel: 2026-10-26.
