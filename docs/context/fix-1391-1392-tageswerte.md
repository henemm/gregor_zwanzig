# Kontext: #1391 + #1392 — fehlende Tages-Auswertungsfelder im zentralen Wetterkatalog

Workflow: `fix-1391-1392-tageswerte` (BUG fast-track)
Worktree: `.claude/worktrees/fix-1391-1392-tageswerte`
Etappen-Einordnung: Nebenausläufer aus #1373 Scheibe A (Epic #1372 / Dach #1374).
Keiner Etappe S1–S6 zugeordnet — deshalb parallel zu Scheibe B zulässig.

## Analysis

### Type
Bug (#1391, nutzersichtbar) + Struktur-Doppelung mit Nutzerwirkung (#1392).
Gebündelt, weil beide dieselbe Ursache haben (fehlende Tages-Auswertungsangabe
im Katalog) und beide dieselbe Ausnahmeliste desselben Wächters betreffen —
getrennt bearbeitet würden sie in `test_compare_catalog_derives_from_central_catalog.py`
kollidieren.

### Befund 1 (#1391) — am Code verifiziert

| Station | Belegstelle | Zustand |
|---|---|---|
| Tageswert existiert | `src/app/models.py:374` (`SegmentWeatherSummary.snowfall_limit_m`) | ✅ vorhanden |
| Tageswert wird berechnet | **nur im Compare-Pfad** `summarize_points()` (`weather_metrics.py:997,1032`) → `_compute_snowfall_limit()` (`:848-858`, MIN) | ⚠️ **halb** |
| Trip-Pfad befüllt ihn | `compute_extended_metrics()` (`weather_metrics.py:697`) berechnet 13 Größen — `_compute_snowfall_limit` ist **nicht** darunter | ❌ **fehlt** |
| Katalog kennt ihn | `src/app/metric_catalog.py:271-280` — **kein** `summary_fields`, Kommentar `# No summary_fields: not on SegmentWeatherSummary` | ❌ **falsch** |
| Alarm-Schwellen-Aufbau | `src/services/weather_change_detection.py:436` — `for field in metric_def.summary_fields.values()` | läuft ins Leere |

Folge: `default_change_threshold=200.0`, `cmp="unter"`, `sms_code="SL"` sind
gesetzt, aber es entsteht nie eine Schwelle. Der Abweichungs-Alarm für die
Schneefallgrenze kann strukturell nicht feuern.

**Korrektur 2026-07-26 (aus der RED-Runde, am Code nachgeprüft):** Es sind
ZWEI Lücken in derselben Kette, nicht eine. Der Katalogeintrag allein reicht
nicht — im Trip-Pfad bleibt `snowfall_limit_m` ohnehin immer `None`, weil
`compute_extended_metrics()` ihn gar nicht erst berechnet. Nur der
Compare-Pfad (`summarize_points()`) füllt ihn. Beide Lücken müssen geschlossen
werden, sonst bleibt der Alarm auch nach der Katalog-Korrektur stumm.
Damit ist auch die frühere Aussage unten unter „Gespeicherte Vergleichsbasis"
überholt: für Trip-Schnappschüsse steht dort heute kein Wert, der Alarm greift
erst mit den Schnappschüssen **nach** dem Deploy.

### Befund 2 (#1392) — am Code verifiziert

- `cloud_low_pct/cloud_mid_pct/cloud_high_pct` existieren nur stündlich
  (`models.py:127-129`); auf `SegmentWeatherSummary` gibt es nur
  `cloud_avg_pct` (`:358`) für die Gesamtbewölkung.
- Der Ortsvergleich mittelt sie sich **zweimal innerhalb derselben Datei**
  selbst aus: `src/services/comparison_engine.py:203-211` und `:449-457`
  (identischer Code), Ablage auf `LocationResult` (`src/app/user.py:136`).
- Katalog trägt entsprechend dreimal `# No summary_fields` — hier ist der
  Kommentar sachlich richtig, das Feld fehlt tatsächlich.

### Geprüftes Risiko — entwarnt

Ein Tageswert für die drei Bewölkungsstufen erzeugt **keine** neuen Alarme:
`default_change_threshold` ist bei `cloud_low/mid/high` nicht gesetzt (Default
`None`), und `from_display_config()` überspringt genau diesen Fall
(`weather_change_detection.py:~430`). Gegenprobe: `cloud_total` trägt
ausdrücklich `default_change_threshold=None` als Vorboten-Metrik (#889/ADR-0010).

### Technischer Ansatz (Empfehlung)

1. **#1391 — reine Katalog-Korrektur.** `summary_fields={"min": "snowfall_limit_m"}`
   eintragen, falschen Kommentar entfernen. `min` ist nicht frei wählbar,
   sondern durch die tatsächliche Berechnung (`_compute_snowfall_limit` = MIN)
   und durch `cmp="unter"` festgelegt — `max` wäre ein Bedeutungsfehler.
2. **#1392 — Tageswert ins gemeinsame Datenmodell, kanonisch gerechnet.**
   Drei Felder `cloud_low_avg_pct/cloud_mid_avg_pct/cloud_high_avg_pct` auf
   `SegmentWeatherSummary`; Berechnung als **eine** Funktion im
   `WeatherMetricsService` (Vorbild `_compute_snowfall_limit`), von dort
   befüllt; `comparison_engine.py` ruft an **beiden** Stellen diese Funktion
   auf statt selbst zu mitteln. `summary_fields={"avg": "cloud_*_avg_pct"}`
   im Katalog.
   **Bewusste Abgrenzung:** `LocationResult` und der Vergleichs-Renderer
   bleiben unangetastet — die Umstellung des Vergleichs auf
   `SegmentWeatherSummary` ist Epic #1230 und würde hier den Rahmen sprengen.
   Ziel dieser Lieferung ist, dass die Zahl **einmal** gerechnet wird, nicht
   dass der Vergleich sein Datenmodell wechselt.
3. **Ausnahmeliste zurückbauen.** `AGGREGATION_CHECK_EXEMPTIONS` wird durch
   diese Lieferung **leer** (alle vier Einträge fallen weg), ebenso
   `PINNED_EXEMPT_AGGREGATIONS`.

### Fallstricke (für Umsetzung und Adversary)

- **Wirkungsnachweis darf nicht still verstummen.** `test_…_exemptions…`
  (`:422-441`) iteriert über die Ausnahmeliste — bei leerer Liste läuft der
  Wirkungsnachweis als No-Op grün durch. Der Nachweis muss künftig über einen
  **künstlich eingesetzten** Ausnahme-Eintrag geführt werden, sonst ersetzt
  diese Lieferung einen echten Wächter durch einen leeren.
- **Harte Referenz auf `snowfall_limit`.** Zeile ~317 greift direkt auf
  `PINNED_EXEMPT_AGGREGATIONS['snowfall_limit']` zu → `KeyError`, sobald der
  Eintrag verschwindet. Test mit anpassen, nicht löschen.
- **`summary_fields` hat vier weitere Leser** — jeder bekommt durch die neuen
  Einträge zusätzliche Treffer:
  `alert/project.py:23` (Rückwärtssuche Feld → Metrik, für die Alarm-Anzeige),
  `alert_preset.py:204` (ausdrücklich abgeschaltete Felder),
  `weather_change_detection.py:255` (Zeitpunkt des Spitzenwerts — muss die
  Auswertung `min` korrekt behandeln, bisher für keine Größe mit `cmp="unter"`
  auf diesem Weg erprobt), `:436` (Schwellenaufbau, der eigentliche Fix).
- **Gespeicherte Vergleichsbasis.** `weather_snapshot.py` legt
  `SegmentWeatherSummary` als JSON ab (Basis des Abweichungs-Vergleichs).
  Neue Felder sind additiv mit Default `None` → Bestandsschnappschüsse laden
  weiter. Erster Lauf nach dem Deploy vergleicht gegen `None`; das darf weder
  krachen noch einen Fehlalarm erzeugen. Für die Schneefallgrenze ist das
  unkritisch, weil das Feld im Schnappschuss längst mitgeschrieben wird — der
  Alarm greift dort sofort mit Bestandsdaten.

### Affected Files

| Datei | Art | Zweck |
|---|---|---|
| `src/app/metric_catalog.py` | MODIFY | 4 Einträge bekommen `summary_fields`, falsche Kommentare raus |
| `src/app/models.py` | MODIFY | 3 neue Optional-Felder auf `SegmentWeatherSummary` (schema-relevant → Backup-Hook) |
| `src/services/weather_metrics.py` | MODIFY | kanonische Bewölkungsstufen-Mittelung + Befüllung |
| `src/services/comparison_engine.py` | MODIFY | zwei Eigenrechnungen (`:203-211`, `:449-457`) durch den kanonischen Aufruf ersetzen |
| `tests/unit/test_compare_catalog_derives_from_central_catalog.py` | MODIFY | Ausnahmeliste leeren, Wirkungsnachweis auf künstlichen Eintrag umstellen |
| Repro-Tests (Verhalten benannt, keine Issue-Nummern) | CREATE | Alarm-Schwelle Schneefallgrenze; Tageswert Bewölkungsstufen; Doppelrechnung weg |

### Scope Assessment

- Dateien: 5 MODIFY + Tests
- LoC: ~180–200 netto (unter dem 250er-Deckel, kein Override nötig)
- Risiko: **MEDIUM** — die Katalog-Änderung wirkt auf vier Lesepfade; das
  Datenmodell ist schema-relevant.

### Abgrenzung — bewusst nicht angefasst

`compare_metric_ids.py`, die Frontend-Speicherpfade des Vergleichs (#1373
Scheibe B), der Vergleichs-Renderer (`compare_html.py`, S3/S5) und der
Trip-Ausblick (#1388 läuft parallel in `ws-overview-0725`).
