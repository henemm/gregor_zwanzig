<!-- gregor-zwanzig-handoff: stable_id=email-metrics-summary -->

# Email: Optionaler Metriken-Überblick (Issue #664)

## Was wurde designed (Mockup: `screen-output-preview.jsx`)

Neuer optionaler Block direkt nach dem Email-Header-Bereich. Wenn aktiv,
**ersetzt** er den bisherigen Quick-Take-Block (Prosa + Tags) vollständig.

---

## Visuelles Konzept

Gleiche Pill/Tag-Optik wie der bisherige Quick-Take — aber **datengesteuert**
für alle konfigurierten Metriken des Nutzers. Eine Pill pro Metrik.

```
[8–11°C · Max 15:00]  [gef. min 6.6°C · 13:00]  [Wind max 12 km/h (11:00)]
[Böen max 25 km/h (12:00)]  [Regen ab 11:00 · 7.3 mm]  [Regen-W. >50% ab 12:00 · max 68% (13:00)]
[Gewitter max 5% (12:00)]  [60–95% bewölkt · Max 12:00]  [Sicht <2 km ab 08:00 · min 1.2 km]
[UV max 2.4 (14:00)]  [0°-Linie 2.310–2.550 m · Max 15:00]  [Feuchte >90% ab 12:00 · max 95%]
[Taupunkt min 5.8°C (08:00)]  [Tiefer Wolken max 80% (12:00)]  [88 min Sonne]
```

**Farb-Logik** (wie bestehende EmailTag-Komponente):
- `ok` (grün): kein Regen, kein Gewitter, Wind unter Schwellwert
- `warn` (orange): Schwellwert erstmals überschritten (Wind, Böen, Regen-W., Sicht, Feuchte)
- `risk` (rot): Gewitter über Schwellwert
- `info` (blau/neutral): rein informative Werte (Temp, UV, 0°-Grenze etc.)

---

## Pro-Metrik-Algorithmus

Für jede konfigurierte Metrik des Nutzers wird aus den **stündlichen Forecast-Rows**
der Etappe berechnet:

| Feld | Berechnung |
|------|-----------|
| `min` / `max` | reduce über alle Stunden |
| `maxHour` | Stunde des Maximums (Format: `HH`) |
| `firstAbove(threshold)` | erste Stunde ≥ Schwellwert (null wenn nicht erreicht) |
| `firstBelow(threshold)` | erste Stunde < Schwellwert (für Sichtweite) |
| `sum` | Summe über alle Stunden (Regen mm, Sonnenschein min) |

Schwellwerte kommen aus der **Nutzerkonfiguration** der jeweiligen Metrik
(nicht aus den Alert-Thresholds!). Fallback-Defaults:
```
wind: 20 km/h · gust: 30 km/h · rainP: 50% · thunder: 20%
vis: 2 km · hum: 90%
```

---

## Pill-Text-Format je Metrik

| Metrik | ok/info | warn |
|--------|---------|------|
| Temperatur | `8–11°C · Max 15:00` | — |
| Gefühlt | `gef. min 6.6°C · 13:00` | — |
| Wind | `Wind max 12 km/h (11:00)` | `Wind >20 km/h ab 11:00 · max 22 km/h (13:00)` |
| Böen | `Böen max 25 km/h (12:00)` | `Böen >30 km/h ab 13:00 · max 43 km/h (14:00)` |
| Regen | `kein Regen` | `Regen ab 11:00 · 7.3 mm` |
| Regen-W. | `Regen-W. max 25%` | `Regen-W. >50% ab 12:00 · max 68% (13:00)` |
| Gewitter | `kein Gewitter` / `Gewitter max 5% (12:00)` | `Gewitter >20% ab 16:00` (risk/rot) |
| Bewölkung | `60–95% bewölkt · Max 12:00` | — |
| Sichtweite | `Sicht min 1.2 km (08:00)` | `Sicht <2 km ab 08:00 · min 1.2 km` |
| UV-Index | `UV max 2.4 (14:00)` | — |
| 0°-Grenze | `0°-Linie 2.310–2.550 m · Max 15:00` | — |
| Luftfeuchte | `Feuchte 75–95% · Max 12:00` | `Feuchte >90% ab 12:00 · max 95% (12:00)` |
| Taupunkt | `Taupunkt min 5.8°C (08:00)` | — |
| Tiefer Wolken | `Tiefer Wolken max 80% (12:00)` | — |
| Sonnenschein | `88 min Sonne` / `kein Sonnenschein` | — |

---

## Weitere Änderungen in derselben Email

### 1. Quick-Take ersetzt wenn aktiv
Wenn `show_metrics_summary = true` in der Trip-Konfiguration:
- Quick-Take-Block (Prosa + Tags) **nicht rendern**
- Metriken-Überblick-Block **stattdessen rendern**

Wenn `false`: altes Verhalten, Quick-Take wie bisher.

### 2. Ausblick: Gewitter-Badge
In der „Ausblick · nächste 4 Tage"-Sektion erhält jede Etappenzeile
einen optionalen roten Badge wenn Gewitterrisiko > Schwellwert:

```
⚡ Gewitter möglich 15:00–16:00      ← wenn forecast thunder% > threshold
⚡ Gewitter erwartet ab 13:00        ← stärker (thunderstorm kategorie)
```

Badge-Daten kommen aus dem Tages-Forecast der jeweiligen Folge-Etappe.

### 3. Tages-Summe entfernt
Der bisherige „Tages-Summe"-Block (Regen gesamt, Max Wind, Min Sicht,
Gewitter % max) wird aus der Email **entfernt** — diese Infos sind
vollständig im Metriken-Überblick enthalten.

### 4. Antwort-Kommandos (neue Sektion vor Footer)
Neue Sektion mit Reply-Keywords, die der Nutzer per Email-Antwort senden kann:

```
PAUSE 2d    Briefings pausieren
SKIP        Nächstes überspringen
STOP        Dauerhaft deaktivieren
STATUS      Trip-Status abrufen
CONFIG      Spalten ändern
HELP        Alle Kommandos
```

Hinweiszeile: „Antworte auf diese E-Mail mit einem Schlüsselwort."

**Backend**: Reply-Handler muss diese Keywords auswerten und entsprechende
Aktionen auf dem Trip/Subscription-Objekt ausführen.

---

## User-Setting

```python
class TripEmailSettings:
    show_metrics_summary: bool = False   # neu — Default aus
    # ... bestehende Felder
```

Alternativ als Teil der bestehenden Channel-Konfiguration.

---

## Acceptance Criteria

- [ ] `show_metrics_summary`-Flag in Trip-Konfiguration speicherbar
- [ ] Wenn aktiv: Quick-Take-Block durch Metriken-Überblick ersetzt
- [ ] Alle konfigurierten Metriken des Nutzers als Pills dargestellt
- [ ] Schwellwert-Crossings korrekt als `warn`/`risk` markiert
- [ ] Zeit des Maximums in jedem Pill enthalten
- [ ] Ausblick-Zeilen zeigen ⚡-Badge wenn Gewitter im Tages-Forecast
- [ ] Tages-Summe-Block aus Email entfernt
- [ ] Antwort-Kommandos-Sektion im Email-Footer
- [ ] Reply-Handler verarbeitet PAUSE/SKIP/STOP/STATUS/CONFIG/HELP
