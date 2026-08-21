# Context: #2020 — Auslösung des Regen-Alarms (Scheibe 1)

Issue: [#2020](https://github.com/henemm/gregor_zwanzig/issues/2020) · `priority:critical` ·
Milestone „Tour KHW 2026-08". Umgeschnitten auf PO-Entscheid 2026-08-21.
Vorgänger-Analyse (Formulierung → **Scheibe 2**): `docs/context/fix-2020-alarm-zeitangaben.md`,
Spec `docs/specs/modules/fix_2020_alarm_zeitangaben.md` (freigegeben, **zurückgestellt**;
die Freigabe gilt **nicht** für diesen Zuschnitt).

## Die Leitfrage des PO

> Hilft diese Information dem Nutzer? Warum hat er sie nicht bekommen, als sie ihm
> genutzt hätte? Und warum gab es keinen Nowcast — hat es überhaupt geregnet?

## Was wirklich gefallen ist

Open-Meteo-Rückschau, Ziel-Wegpunkt G4 (46.73042 / 12.321643), 2026-08-20, Ortszeit.
Von der Messung unabhängig bestätigt (Spitzenstunde 15:00 mit 11,5 mm exakt getroffen):

| Zeit | Regen | | Zeit | Regen |
|---|---|---|---|---|
| 11:00 | 0,1 mm | | 16:00 | 3,2 mm |
| 12:00 | 0,1 mm | | 17:00 | 0,7 mm |
| **13:00** | **9,7 mm** | | 18:00 | 0,4 mm |
| 14:00 | 0,0 mm | | 21:00 | 1,8 mm |
| **15:00** | **11,5 mm** | | 22:00 | 3,9 mm |
| | | | **Tag** | **33,1 mm** |

Es hat geregnet, mehr als vorhergesagt (33,1 gegen 29,4 mm). Der Alarm war inhaltlich
berechtigt. **Aber die Zeitachse entwertet ihn:** Ankunft laut Plan 11:33, erster
schwerer Guss 13:00, stärkste Stunde 15:00, erste Alarm-Mail **15:30**.

---

# Analyse (2026-08-21)

## Type

**Bug** — mit der Einschränkung, dass zwei der drei ursprünglich vermuteten Ursachen
widerlegt sind (siehe unten). Der verbleibende Kern ist echt.

## 🔴 Zwei widerlegte Hypothesen — beide hätten in die falsche Reparatur geführt

### W1 — A2 ist kein Defekt, sondern eine geltende Entscheidung

Der Negativ-Nachweis ist vollständig geführt: Es gibt genau **zwei** Produktiv-Aufrufer
von `detect_changes()` (`src/services/trip_alert.py:1058`,
`src/services/deviation_alert_engine.py:221`), beide mit `include_absolute=False`; kein
Produktionspfad erreicht `_detect_absolute_changes()`. Verschärfend:
`SyncAlertRules()` (`internal/model/trip.go:359-390`, #817) migriert **jede**
`kind=absolute`-Regel beim nächsten Speichern zu `kind=delta` — absolute Regeln sind
nicht nur ungenutzt, sie sind **nicht persistierbar**.

**Aber das ist Absicht, vierfach dokumentiert:**

- **ADR-0009** verwirft absolute Schwellen ausdrücklich (Alarm-Müdigkeit).
- **ADR-0013** führt den Pfad als Known Limitation; Rückkehr nur mit eigenem Render-Vertrag.
- **ADR-0040** listet „den Absolut-Pfad reaktivieren" wörtlich als **verworfene Alternative**
  (zwei Gründe: verlustbehaftete Abbildung, Render-Inkompatibilität `old_value = 0.0`).
- **ADR-0043** (geltend, PO-„go" 2026-08-03): *„Die Empfindlichkeitsstufe ist der einzige
  Alarm-Regler"* — absolute Grenzen verlieren ihre Wirkung ersatzlos. Und: *„Die Auswertung
  bleibt ein Vergleich gegen den zuletzt versendeten Briefing-Stand, nie gegen einen
  absoluten Systemwert."*

`include_absolute=False` umzulegen hieße, ADR-0043 **still zurückzunehmen**. Es hätte wie
ein Bugfix ausgesehen und wäre durch kein Gate gefallen. **A2 ist damit als Ursache
gestrichen.**

### W2 — Die Empfindlichkeitsstufe hätte es nicht gerettet (Nullhypothese widerlegt)

Es gibt bereits einen Regler (`src/services/alert_preset.py`):

| Metrik | entspannt | standard | sensibel |
|---|---|---|---|
| `precipitation_sum` (Δ ↑, mm) | 20 | **10** | 5 |
| `precipitation_change` (Δ ↑, mm) | 15 | 7 | 3 |
| `precipitation_heavy_onset` (Δ, h früher/später) | 2/4 | 1/3 | 1/2 |

KHW 403 lief mit `threshold: 10` = **standard**. Naheliegende Vermutung: „sensibel" (5 mm,
also Auslösung ab 12,4 mm statt 17,4 mm) hätte früher gewarnt.

**Gemessen: nein.** Beide Schwellen werden im **selben Stundenfenster (14–15 Uhr)**
überschritten, weil 11,5 der 33,1 mm in einer einzigen Stunde fielen. Der De-facto-Default
ist ohnehin „standard" (`alert_preset.py:389` backfillt so). **Eine strengere Stufe hätte
den Fall nicht gelöst.**

## Der belastbare Kern: es war kein Mengenproblem, sondern ein Vorlaufproblem

Aus dem Ausbleiben des Alarms folgt ableitbar: **Die Vorhersage blieb bis kurz vor 15:30
unter 17,4 mm.** Der 15-Minuten-Prüfzyklus ist lückenlos; wäre die Schwelle früher gerissen,
hätte er gefeuert.

Damit verschiebt sich die Ursache: Nicht die Schwelle war zu hoch, sondern **die Vorhersage
selbst kam zu spät hoch**. Vor 11:00 Ortszeit war zudem praktisch kein Regen gefallen — eine
mengenbasierte Regel *konnte* vor 10:00 nichts melden. Das ist Physik, keine Schwellenfrage.

**Die einzige Quelle mit kürzerem Vorlauf als die Vorhersage ist der Radar-Nowcast — und der
war gesperrt.** Damit ist A3 der verbleibende Kern.

### A3 — Die Nowcast-Unterdrückung prüft die Überholung nicht

`src/services/trip_alert.py` (Bezeichner, nicht Zeile — die Datei ist frisch verschoben):

```python
_briefing_announced = (_briefing_precip is not None and _briefing_precip >= 0.5)
if _briefing_announced and not result.is_convective:
    continue
```

Angekündigt 7,4 mm, gefallen 33,1 mm — die Vervierfachung galt als „schon bekannt". Es gibt
**keinen Betragsvergleich** zwischen Ankündigung und aktueller Vorhersage, nur ein binäres
„wurde überhaupt ≥ 0,5 mm angekündigt". Durchbrochen wird ausschließlich über
`result.is_convective` (Gewitter/Hagel, #883). **Reiner nicht-konvektiver Starkregen ist
gesperrt, sobald das Briefing für die Onset-Stunde ≥ 0,5 mm nannte.**

Präzisierung gegenüber der Erstannahme: `_briefing_precip_for_onset()` vergleicht gegen den
Wert der Onset-**Stunde** (`precip_1h_mm`), nicht gegen die Tagessumme. Die Sperre ist
**nicht persistent** — jeder Lauf prüft neu gegen seine eigene Onset-Stunde, `continue`
überspringt nur den einen Lauf.

## 🔴 Der zweite Befund: das System ist nicht beobachtbar

Von rund elf Unterdrückungsstufen protokollieren **drei**. Unsichtbar bleiben unter anderem
die **Δ-Auswertung selbst**, die **Briefing-Sperre (A3)** und `radar_alert_due=False`
(letztere ohne **jedes** Log, nicht einmal `debug`). Bestätigt im Docstring von
`append_suppressed_entry` (`src/services/alert_log.py`) als benannte Lücke **O3**.

Zusätzlich: **Prognose-Zwischenstände werden nirgends aufgezeichnet.** Deshalb ist nicht
rekonstruierbar, wann die Vorhersage von 7,4 auf 29,4 mm sprang — die Kernfrage des Tickets
ist mit den vorhandenen Daten **unbeantwortbar**.

**Betriebliche Konsequenz:** Der PO kann auf Tour eine Warnung nicht bekommen, und niemand
kann hinterher sagen, warum. Eine Unterdrückung ohne Spur ist von „es gab nichts zu melden"
nicht zu unterscheiden.

**Nebenbefund (→ #1199):** Der Docstring behauptet, amtliche Warnungen würden nicht
protokolliert — seit #1467 S4b-1 stimmt das nicht mehr (`trip_alert.py:1855`).

## Messergebnisse

Echte Open-Meteo-Prognose-Revisionen (Previous-Runs-API), 8 KHW-Wegpunkte, 14.–20.08.,
56 Zellen. Bericht im Scratchpad (`bericht_2020_hebelwirkung_flutrisiko.md`,
`ergaenzung_2020.md`).

| Regel | Auslösungen | davon **allein** | max. Breite/Tag | Bewertung |
|---|---|---|---|---|
| Ist (Δ > 10 mm, nur Anstieg) | 1 | — | — | Referenz |
| K1a (≥ 2× Basis, ab 5 mm) | 4 | **3** | 2 | stärkste Hebelwirkung, sehr sensibel |
| K1b (≥ 2× Basis, ab 10 mm) | 2 | 1 | 2 | — |
| K1c (≥ 1,5× Basis, ab 10 mm) | 2 | 1 | 2 | zellgenau identisch zu K1b |
| K2a (≥ 20 mm absolut) | 6 | **0** | 5 | architektonisch gesperrt (W1); **keine** Hebelwirkung |
| K2b (≥ 30 mm absolut) | 5 | **0** | 5 | dito |

- **Die absoluten Regeln haben null Hebelwirkung** — sie feuern nur dort mit, wo die
  bestehende Regel ohnehin feuert. Selbst ohne ADR-Sperre wären sie wertlos.
- **Die mm-Untergrenze dominiert nicht** (verwirft 76–85 % der reinen mm-Treffer, überwiegend
  Rückgänge bei hoher Basis) — sie bleibt ein Relevanzfilter, kein verkappter Auslöser.
- **Monotonie-Verstoß bestätigt:** (5,0 → 10,0 mm, Δ = 5,0) feuert, aber (10,0 → 19,8 mm,
  Δ = 9,8 — fast doppelt so groß) feuert **nicht**. Betrifft strukturell jede
  Verhältnis-ODER-Absolut-Kombination ohne Sprung-Untergrenze. **Muss in der Spec als
  Wächter stehen.**

**Korrektur im Messbericht selbst:** Die erste IST-Referenz (12 Auslösungen) zählte
`abs(delta)` wie der Code — 11 davon waren **Rückgänge**, ein Artefakt der Tages-Basis.
Bereinigt bleibt 1.

## Datengrenzen — ausdrücklich

1. **Untertägige Prognose-Revision ist mit keiner Quelle rekonstruierbar.** Die
   Previous-Runs-API liefert nur 24-h-Schritte (Beleg: der lead1-Wert für G4 lautet 59,8 mm
   und ist weder mit 7,4 noch mit 29,4 mm vereinbar). Die Kernfrage „wann sprang die
   Vorhersage" bleibt offen.
2. **Das Produktiv-Alarmprotokoll ist dieser Sitzung nicht zugänglich.** Datenwurzel seit
   #1595 unter `/var/lib/gregor` (Nutzer `claude-gregor`), `sudo` im automatischen Modus
   gesperrt. ⚠️ **Der Pfad `data/users/` im Checkout enthält nur Alt-/Testdaten** — der
   dortige KHW-Trip heißt `khw-402` und trägt Etappen aus **Mai 2024**. Wer dort misst,
   bekommt plausible Zahlen zum falschen Trip.
3. **Offen bis Datenzugriff:** `report_config.morning_time/evening_time` von KHW 403, die
   Reihenfolge in `metric_alert_levels`, und die `alert_log`-Einträge des 20.08.

## Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/trip_alert.py` | MODIFY | A3: Überholungs-Prüfung statt binärer Briefing-Sperre; Protokollierung der Unterdrückungen |
| `src/services/alert_log.py` | MODIFY | O3: `append_suppressed_entry` für Änderungsalarm-Pfad öffnen |
| `src/services/deviation_alert_engine.py` | MODIFY | Unterdrückungsgründe protokollieren statt `logger.debug` |
| `tests/tdd/test_nowcast_suppression_logging.py` | MODIFY | bestehende Abdeckung erweitern |
| (neu) Testdatei für Überholungs-Regel | CREATE | Verhaltensbenennung, keine Issue-Nummer |

**Nachbarschaft:** `src/services/trip_alert.py` hat drei Baustellen. #2017 B
(`intake-2017-b`) ist GREEN und committet — **wir rebasen auf sie**. #2018
(`intake-2018`) arbeitet am Ereignis-Identitäts-Gate, ~100 Zeilen entfernt, und hat
zugesichert, die Zustellmenge **nicht** zu verändern.

## Scope Assessment

- Files: 4–5
- Geschätzte LoC: +120 / −20 (unter dem 250er-Limit)
- Risk Level: **MEDIUM** — der Eingriff erhöht das Alarmaufkommen, zwei Tage vor Tourstart

## Summenwirkung (mit #2017 abgestimmt)

- #2017 Messpunkt-Verlegung: **±0 %** — die Onset-Wertemenge `[8, 23, 38, 53]` ist vor und
  nach der Verlegung identisch (hängt an der Wanduhr, nicht am Ort; 77 bewegliche Abrufe,
  Median-Abstand 1,976 km — Varianz war vorhanden, Nullbefund belastbar).
- #2017 Guard-Rückbau: **≤ +12,6 %** (Obergrenze bei gleichverteilten Onsets; 121 von 960).
- #2018: **±0 %** (zugesichert, reine Formänderung).
- Diese Scheibe: **erhöht** — Betrag erst nach Umsetzung messbar, weil die Basislinie heute
  unbeobachtbar ist. Genau deshalb Reihenfolge: **erst Sichtbarkeit, dann Schwelle.**

## Technische Empfehlung

**Reihenfolge ist Teil der Empfehlung**, nicht Beiwerk:

1. **Sichtbarkeit zuerst.** Jede Unterdrückung schreibt einen Protokolleintrag mit Grund.
   Ohne das ist die Wirkung von Schritt 2 nicht messbar und ein Fehlgriff auf Tour nicht
   diagnostizierbar. Reine Additiv-Änderung, kein Verhaltensrisiko.
2. **A3: Überholung prüfen.** Die Briefing-Sperre bricht, wenn die aktuelle Vorhersage die
   Ankündigung um einen Faktor überholt — statt binär „war angekündigt". Bleibt ein
   Vergleich gegen den Briefing-Stand und damit **ADR-0009/0043-konform**; es ist dieselbe
   Reparatur, die ADR-0043 für Gewitter über Niveaus bereits vollzogen hat.
3. **Monotonie-Wächter** als Pflichttest: Ein größerer Sprung darf nie zu einer schwächeren
   Meldung führen als ein kleinerer (Verstoß oben belegt).
4. **Nicht** in dieser Scheibe: absolute Regeln (W1), Empfindlichkeitsstufen (W2),
   Aufzeichnung von Prognose-Zwischenständen (eigenes Ticket, siehe offene Frage).

## Open Questions

- [ ] **An den PO:** Die Erwartung „Warnung vor 10:00" ist mit den verfügbaren Datenquellen
      nicht erfüllbar — vor 11:00 war weder Regen gefallen noch nachweislich die Vorhersage
      gestiegen. Erreichbar ist eine Warnung **kurz vor dem Guss** (Radar-Nowcast, Vorlauf
      Minuten bis ~1 h) statt 30 Minuten danach. Ist das das Ziel dieser Scheibe?
- [ ] **An den PO:** Sollen Prognose-Zwischenstände künftig aufgezeichnet werden? Ohne sie
      bleibt jede künftige Schwellenfrage Rätselraten. Eigenes Ticket, nicht diese Scheibe.
- [ ] Produktiv-Alarmprotokoll des 20.08. — welche Stufe hat konkret geschluckt? Blockiert.
