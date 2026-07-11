<!-- gregor-zwanzig-handoff: stable_id=issue-561-multiday-trend -->
## Kontext

Am **Ende des Abend-Briefings** (E-Mail eines aktiven Trips, nach dem
Haupt-Wetterteil) erscheint ein kompakter Block: die **nächsten 2–3
Wanderetappen** mit je einer Zeile Wettervorschau. Er hilft dem Wanderer zu
entscheiden, ob er morgen eine Extra-Etappe einlegt oder lieber wartet.

Reihenfolge der Abschnitte (von oben):
`04 Gewitter-Vorschau → ` **`05 Nächste Etappen (dieser Block)`** ` → 06 Highlights`.

Feature gehört zum **E-Mail-Rendering** (`src/formatters/trip_report.py`),
**nicht** zum Frontend-UI.

## Entscheidung (Claude Design · Tech-Lead)

Die Design-Request stellte drei Fragen. Antworten + Begründung:

| Frage | Entscheidung | Begründung |
|---|---|---|
| **F1 · Spalten oder Fließtext?** | **Spalten, 2-zeilig je Etappe** | Der Block dient dem **Vergleich über Tage** — fluchtende Mono-Spalten machen Mo↔Di↔Mi auf einen Blick vergleichbar; Fließtext kann das nicht. Etappenname auf **eigener Zeile**, Werte fluchtend darunter — löst lange Routennamen bei 600 px, ohne die Metrik-Spalten zu sprengen. |
| **F2 · abgesetzt oder eingebettet?** | **Leicht abgesetzt** | Obere Haarlinie (2px ink) + warmer Paper-Tint (`#f6f4ee`) signalisieren „anderer Zeit-Horizont" ohne schwere Box. Hauptreport bleibt auf Weiß. Text voll kontrastreich (Grundgesetz: Lesbarkeit vor Optik). |
| **F3 · Heading-Text?** | **„Nächste Etappen"** | Konkret, User-Sprache. „Ausblick" zu vage, „Weiterer Verlauf" zu wortig. Mono-Sublabel `3-Tage-Trend · gesendet So 18:00` gibt den Kontext rechtsbündig. |

Mockup-Referenz im Design-Repo: `Gregor 20 - Issue 561 Mehrtages-Trend.html`
(faithful Email-Table-HTML + Plain-Text-Fallback + Atomic-Mapping).

## ⚠ Tech-Lead-Flag · keine Wetter-Emoji in den Spalten

Die Design-Request skizzierte `⛅ 🌧 💨 ⚡` in den Spalten. **Nicht umsetzen:**
Wetter-Emoji haben **variable Breite** und rendern in Outlook / Gmail / Apple
Mail uneinheitlich — das zerstört die Mono-Ausrichtung der fluchtenden Spalten.
Stattdessen reine Mono-Text-Tokens (`8–16°C  3 mm  W 20`). Die **Gewitter-Ampel**
trägt im HTML ein **Farb-Quadrat (8×8px) + Text-Wort** (`kein / LOW / MED / HIGH`),
nie Farbe allein (Lesbarkeits-Grundgesetz). Der Blitz `⚡` bleibt **nur im
Plain-Text** als Genre-Marker.

## Konfiguration

### Aktivierung — kein User-Toggle

Der Trend-Block ist **kein opt-in**. Er erscheint automatisch, sobald ein
aktiver Trip **mehr als eine Folge-Etappe** hat. Keine eigene Einstellung im
Frontend-UI. Begründung: der Block ist immer nützlich wenn Etappen existieren
— ein Toggle wäre ein leerer Config-Aufwand ohne echten User-Mehrwert.

```python
# Aktivierungs-Bedingung in trip_report.py
trend = build_trend(trip)           # holt nächste Etappen aus Trip-Plan
if len(trend.stages) > 0:          # C5: 0 Etappen → Block entfällt ohnehin
    report.append(render_trend_block(trend, channel))
```

### Etappen-Quelle — automatisch aus Trip-Plan

Die 2–3 Etappen kommen **automatisch** aus dem strukturierten Trip-Plan
(`trip.stages`, geordnet nach Datum). Es gibt keine manuelle Eingabe. Der
Block greift immer auf die **nächsten 3 noch nicht abgelaufenen Etappen**
ab dem morgigen Tag zu.

```python
def build_trend(trip: Trip, today: date) -> MultiDayTrend:
    upcoming = [s for s in trip.stages if s.date > today]
    return MultiDayTrend(stages=upcoming[:3])   # C3: hart auf 3 begrenzt
```

### Anzahl Tage — automatisch, max. 3

Nicht konfigurierbar. Die Anzahl ergibt sich aus den vorhandenen Etappen
(1–3). Eine feste „Wie-viele-Tage"-Einstellung würde nur leere Zeilen
erzeugen wenn zu wenige Etappen vorhanden sind — vermeiden.

### Metriken-Spalten — fix, nicht aus dem Metriken-Editor

Die vier Spalten `Temp · Regen · Wind · Gewitter` sind **hartcodiert**,
**nicht** mit dem generischen Output-Layout-System (#14 / Metriken-Editor)
verbunden. Begründung:

- Der Trend-Block hat einen spezifischen Entscheidungs-Kontext
  („Extra-Etappe einlegen oder nicht?") — genau diese vier Felder sind dafür
  optimal, kein anderes Set.
- Der Metriken-Editor konfiguriert den **Haupt-Wetterteil** (Abschnitte 01–04).
  Der Trend-Block ist ein eigenständiger Abschnitt 05 mit eigener Semantik.
- Kopplung würde Komplexität ohne Nutzen erzeugen.

Konfigurierbare Spalten im Trend-Block sind als **Folge-Issue** vorgesehen
(siehe „Out of scope").

### Schwellenwerte Ampel — fix

| Metrik | Schwelle | Farb-Stufe |
|---|---|---|
| Regen | ≥ 1 mm | info-blau bold |
| Wind | ≥ 30 km/h | accent bold |
| Wind | ≥ 50 km/h | Risiko-Hinweistext erscheint |
| Gewitter | `LOW` / `MED` / `HIGH` | Ampel-Badge + optionaler Hinweis |

Schwellenwerte sind **nicht** im Frontend konfigurierbar (V1). Änderungen
erfolgen als Code-Konstanten in `trip_report.py`. Ein Config-UI für Schwellen
ist explizit **out of scope** (zu hohe Komplexität, zu wenig User-Nutzen).

### Zusammenfassung: Was ist konfigurierbar?

| Aspekt | V1 | Begründung |
|---|---|---|
| Block ein/aus | ✗ nein — immer aktiv wenn Etappen vorhanden | kein Mehrwert |
| Anzahl Tage | ✗ automatisch (1–3) | ergibt sich aus Trip |
| Metriken-Spalten | ✗ fix (Temp/Regen/Wind/Gewitter) | Folge-Issue |
| Schwellenwerte | ✗ fix (Code-Konstanten) | out of scope |
| Heading-Text | ✗ fix „Nächste Etappen" | Design-Entscheidung F3 |

## Atomic-Design — bestehende Komponente wiederverwenden

**Kein neues Atom.** Das Morgen-Briefing hat bereits `UpcomingRow` +
„Ausblick · nächste 4 Tage" in `screen-output-preview.jsx`. Empfehlung:
diese Molecule auf das **Spalten-Layout vereinheitlichen** (neue Prop
`variant="metrics"`), statt einer zweiten, divergierenden Variante. Der
bisherige Prosa-Hinweis bleibt als **optionaler Risiko-Eskalations-Slot**
erhalten (siehe Mi-Zeile: „Regen ab 13:00 · Böen bis 50 km/h").

| Ebene | Komponente |
|---|---|
| **Atom** | `Wochentag-Label` (Mono, accent) · `Metrik-Token` (Mono, tabular-nums) · `Ampel-Badge` (Quadrat + Wort) |
| **Molecule** | `EtappenTrendZeile` = Wochentag + Etappenname + Metrik-Strip + optionaler Risiko-Hinweis |
| **Organism** | `TrendBlock` = Heading + 2–3 `EtappenTrendZeile`, eingebaut zwischen Gewitter (04) und Highlights (06) |

## Datenmodell

```python
@dataclass
class TrendStage:
    weekday: str        # "Mo" | "Di" | …
    name: str           # "Sóller → Tossals Verds"
    temp_lo: int        # °C Nacht/Tief
    temp_hi: int        # °C Tag/Hoch
    precip_mm: float    # 0.0 → "–"
    wind_dir: str       # "W" | "NE" | …
    wind_kmh: int       # mittlerer Wind
    thunder: str        # "NONE" | "LOW" | "MED" | "HIGH"
    note: str | None    # optional, nur bei thunder != NONE oder hohem Wind/Regen

@dataclass
class MultiDayTrend:
    stages: list[TrendStage]   # 2–3 Einträge, NIE mehr (kein Scrollen)
```

## Ampel-Mapping (HTML + Plain-Text)

| `thunder` | Quadrat-Farbe | Wort (HTML) | Plain-Text |
|---|---|---|---|
| `NONE` | `#9a958a` (ink-4) | `kein` | `⚡–` |
| `LOW`  | `#2c5a8c` (info) | `LOW`  | `⚡LOW` |
| `MED`  | `#c08a1a` (warn) | `MED`  | `⚡MED` |
| `HIGH` | `#a83232` (bad)  | `HIGH` | `⚡HIGH` |

Wort-Farbe HTML: NONE→ink-3, LOW→info, MED→accent-deep `#8c3e1a`, HIGH→bad.

## E-Mail-HTML (table-only, inline styles — kein Grid/Flex)

Eine `table` mit **festen Spaltenbreiten** (`table-layout:fixed`), damit die
Werte aller Etappen fluchten. Pro Etappe **zwei Zeilen**: Name (colspan) +
Metrik-Strip. Einmal Spaltenköpfe oben.

```
┌ 05 · AUSBLICK ──────────────────────  3-Tage-Trend ┐  (border-top 2px ink,
│ Nächste Etappen                       So · 18:00    │   bg #f6f4ee)
│                                                     │
│ TEMP        REGEN   WIND      GEWITTER              │  ← mono 9px, ink-4
│ Mo · Sóller → Tossals Verds                        │  ← name, Inter 14/600
│ 8–16°C      3 mm    W 20      ▪ kein                │  ← mono 13, tnum
│ Di · Tossals Verds → Lluc                          │
│ 6–18°C      –       W 12      ▪ kein                │
│ Mi · Lluc → Scorca                                 │
│ 7–14°C      8 mm    W 35      ▪ MED                 │  ← mm blau, W35 accent
│   Regen ab 13:00, Böen bis 50 km/h                 │  ← optionaler Hinweis
└─────────────────────────────────────────────────────┘
```

Spaltenbreiten (600px-Body, 28px-Padding): `Temp 120 · Regen 84 · Wind 112 ·
Gewitter rest`. Kritikwerte hervorgehoben: `precip_mm > 1` → info-blau bold,
`wind_kmh > 30` → accent bold.

## Plain-Text-Varianten (Signal / Telegram + SMS)

Spalten-Kanäle (Signal ≤ 6, Telegram ≤ 8 — Trend nutzt 4) als fluchtender
Mono-Block; SMS (0 Spalten) flach komprimiert.

**Signal / Telegram (Mono):**
```
Nächste Etappen
Mo  Sóller→Tossals Verds   8–16°C  3mm  W20  ⚡–
Di  Tossals Verds→Lluc     6–18°C   –    W12  ⚡–
Mi  Lluc→Scorca            7–14°C  8mm  W35  ⚡MED
    ↳ Regen ab 13:00 · Böen 50
```

**SMS (flach, ≤ 140 Zeichen, kein Raster):**
```
Trend 3T:
Mo 8-16 R3 W20
Di 6-18 R- W12
Mi 7-14 R8 W35 GEW-MED
```

## Renderer-Logik

```python
def render_trend_block(trend: MultiDayTrend, channel: Channel) -> str:
    stages = trend.stages[:3]            # C3 · hart auf 3 begrenzt
    if not stages:
        return ""                        # C5 · leerer Trend → Block entfällt
    if channel is Channel.EMAIL:
        return _email_table(stages)      # 2-zeilig, feste Spalten
    if channel in (Channel.SIGNAL, Channel.TELEGRAM):
        return _mono_block(stages)       # fluchtend, 4 Spalten ≤ Limit
    if channel is Channel.SMS:
        return _sms_flat(stages)         # flach, ≤140, GEW-{LEVEL} statt ⚡

def _fmt_precip(mm: float) -> str:
    return f"{mm:g} mm" if mm > 0 else "–"
```

Identische Ampel- und Formatierungs-Logik in Backend (`trip_report.py`) und
der Frontend-Live-Vorschau (`UpcomingRow` / `screen-output-preview.jsx`), damit
die Vorschau exakt dem gesendeten Briefing entspricht.

## Files

- `src/formatters/trip_report.py` — Trend-Block in den Abend-Report einhängen
  (zwischen Gewitter-Vorschau und Highlights), vier Kanal-Renderer.
- `screen-output-preview.jsx` (Design-Repo) — `UpcomingRow` auf
  `variant="metrics"` vereinheitlichen; Morgen-„Ausblick" + Abend-Trend teilen
  die Molecule.

## Constraints

- **C1** Nur `<table>` / `<div>` + inline styles. **Kein** CSS Grid/Flexbox.
- **C2** `table-layout:fixed` mit festen Spaltenbreiten → Werte aller Etappen fluchten.
- **C3** **Max. 3 Etappen** — kein Scrollen. Mehr werden abgeschnitten.
- **C4** Optimiert für **600 px**, lesbar auch schmaler (feste Spalten brechen nicht um).
- **C5** Leerer Trend (0 Etappen) → Block wird **weggelassen**, kein leeres Heading.
- **C6** Plain-Text-Variante für Signal/Telegram **und** SMS definiert (SMS = 0 Spalten, flach, ≤ 140).
- **C7** Gewitter-Ampel: **Farb-Quadrat + Wort**, nie Farbe allein. Keine Wetter-Emoji in den fluchtenden Spalten.
- **C8** Beispielwerte als solche markiert — kein Live-Wetter im Mockup.
- **C9** Renderer-Logik identisch Backend/Frontend (Live-Vorschau).

## Acceptance criteria

- [ ] Abend-E-Mail zeigt am Ende den Block „Nächste Etappen" zwischen Gewitter-Vorschau und Highlights.
- [ ] Block ist leicht abgesetzt: obere 2px-Haarlinie + Paper-Tint `#f6f4ee`, Hauptreport auf Weiß.
- [ ] Pro Etappe zwei Zeilen: Wochentag + Etappenname (Zeile 1), Temp/Regen/Wind/Gewitter fluchtend (Zeile 2).
- [ ] Metrik-Spalten fluchten über alle 2–3 Etappen (feste Breiten).
- [ ] Gewitter-Ampel als Farb-Quadrat + Wort (`kein/LOW/MED/HIGH`); **keine** Wetter-Emoji in den Spalten.
- [ ] Optionaler Risiko-Hinweis nur bei `thunder != NONE` (oder hohem Wind/Regen).
- [ ] Plain-Text-Rendering für Signal/Telegram (Mono, fluchtend) und SMS (flach, ≤ 140 Zeichen, `GEW-{LEVEL}`).
- [ ] Max. 3 Etappen; leerer Trend lässt den Block weg.
- [ ] Email-HTML nutzt nur table/div + inline styles (Outlook/Gmail/Apple-Mail-kompatibel).
- [ ] `UpcomingRow` (Design-Repo) auf `variant="metrics"` vereinheitlicht — Morgen + Abend teilen die Molecule.

## Edge cases

| Fall | Verhalten |
|---|---|
| 0 Etappen im Trend | Block entfällt komplett (kein Heading) |
| nur 1 Folge-Etappe | Block mit 1 Zeile rendern (kein Mindest-Padding-Hack) |
| > 3 Etappen verfügbar | auf die nächsten 3 begrenzen |
| `precip_mm == 0` | Spalte zeigt `–` (ink-4), nicht `0 mm` |
| sehr langer Etappenname | umbricht in Zeile 1 (eigene Zeile) — Metrik-Spalten bleiben unberührt |
| `thunder == NONE` für alle | Ampel-Spalte zeigt durchgehend `▪ kein`, kein Hinweistext |
| SMS-Zeile > 140 Zeichen | Etappennamen entfallen, nur Wochentag + Kernwerte (Priorität) |

## Out of scope (Folge-Issues)

- Konfigurierbare Spalten-Auswahl im Trend-Block (folgt Output-Layout-System #14).
- Klickbare Etappen im Trend (E-Mail ist statisch; Interaktion gehört in die App).
- 7-Tage-Variante (`screen-trip-detail.jsx` Schedule-Karte nennt „3–7-Tage" — V2).

## 📎 Screenshots

**Soll · E-Mail (600 px) — Trend-Block in situ zwischen Gewitter (04) und Highlights (06)**

![soll-issue561-email](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-issue561-email.png)

**Soll · Plain-Text-Fallback — Signal/Telegram (Mono) + SMS (flach, ≤ 140)**

![soll-issue561-plaintext](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-issue561-plaintext.png)
