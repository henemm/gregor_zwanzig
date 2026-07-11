<!-- gregor-zwanzig-handoff: stable_id=config-change-flow -->
# Issue 23 · Wetter-Metriken-Tab — 4-Abschnitte-Layout + Live-Mail + Kanal-Verbindung (Desktop + Mobile)

**Type:** Frontend (UX-Redesign des Wetter-Metriken-Tabs im Trip-Edit-Screen)
**Priority:** High
**Baut auf:** #14 (Output-Layout-System · Datenmodell + Renderer), #496 (Pro-Kanal-Vorschau), #20 (kanonische IA), #503 (Tab-Set)
**Design-Quelle:**
- `Gregor 20 - Trip bearbeiten.html` — Haupt-Deliverable (Desktop + Mobile)
- `screen-trip-edit-v2-weather.jsx` — Wetter-Metriken-Tab (4 Abschnitte + Live-Mail)
- `screen-trip-edit-v2-main.jsx` — Trip-Edit-Shell + alle 5 Tabs
- `screen-trip-edit-v2-mobile.jsx` — Mobile-Screen
- `Gregor 20 - Mail Vorschau.html` — vollständige Briefing-Email + Kanal-Varianten

---

## ⚠️ Kanal-Korrektur (PO Henning, 2026-06-05) — zuerst lesen

**Signal ist als Kanal entfernt.** Es gibt nur noch **Email · Telegram · SMS**.
**Telegram (max 8 Spalten)** ist der engste Tabellen-Kanal — dort entscheidet
die Spalten-Reihenfolge, was als Tabelle überlebt.

```
CHANNEL_LIMITS = {
  "email":    {"max_table_cols": None, "max_bytes": None},
  "telegram": {"max_table_cols": 8,    "max_bytes": 4096},
  "sms":      {"max_table_cols": 0,    "max_bytes": 140},
}
PRIMARY_SLOTS = 8  # war 5 (Signal-Budget), jetzt Telegram-Budget
```

`organisms.jsx` am Projekt-Root ist bereits bereinigt (2026-06-05):
- `CHANNEL_BUDGET`: kein `signal`-Key mehr
- `CHANNEL_LIMITS`: Signal-Eintrag entfernt, Telegram.max = 8
- `PRIMARY_SLOTS`: 5 → 8
- `MetricEditorRow`: `isSignalLimit` → `isTelegramLimit`

Folge-Aufgabe: `channel_layout.py` im Backend analog bereinigen (Signal-Branch
raus, Telegram-Budget auf 8 heben). Bodies **#14** und **#496** nennen noch
„Signal (max 6)" — bitte dort ebenfalls bereinigen.

---

## Problem (PO-Feedback 2026-06-05)

> „Ich habe nicht verstanden, was diese Segmente sollten und konnte auch keinen
> Zusammenhang zwischen den Möglichkeiten und der tatsächlich erzeugten E-Mail
> sehen."

**Drei Fehler des Ist-Zustands:**

1. **Keine Wirkung sichtbar.** Änderungen im Editor zeigen keine Mail-Konsequenz.
2. **Zu verschachtelt.** Das neue Design war anfangs eine separate 3-Tab-Meta-App
   — PO-Feedback: „wieder komplett anders und noch verschachtelter."
3. **Wizard und Editor zu weit auseinander.** Erstellen (Wizard) und Bearbeiten
   (Editor) sollen **dieselbe Struktur** nutzen. Ein Trip öffnet immer im
   Bearbeiten-Modus.

---

## Lösung — Architektur

**Der Wetter-Metriken-Tab lebt als einer von fünf Tabs im bestehenden
Trip-Edit-Screen** — keine separate Seite, keine eigene Navigation.

### Tab-Set (kanonisch, deckt sich mit #20)
```
Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Briefing-Zeitplan · Alerts
```
Ein Trip öffnet immer direkt im Bearbeiten-Modus; kein read-only-Zwischenzustand.

### Kanal-Zustand fließt durch alle Tabs
```
Wetter-Metriken (Quelle)
  └─ channels: { email: bool, telegram: bool, sms: bool }
       ├─ Briefing-Zeitplan liest davon (zeigt nur aktive Kanäle als Zeitplan-Option)
       └─ Alerts übernimmt als Vorbelegung (pro Alert überschreibbar)
```

---

## Wetter-Metriken-Tab — 4 Abschnitte

**Zwei-Spalten-Layout (Desktop):** Abschnitte 01–04 links, Live-Mail-Vorschau
rechts (sticky). Jede Änderung links → sofortiges Update rechts.

**Gestapelt (Mobile):** alle 4 Abschnitte scrollen vertikal; Mail-Vorschau öffnet
als Bottom-Sheet via „So kommt es an"-Button.

### 01 — Profil
- Preset-Chips: Alpen-Trekking · Wandern · Küsten-Wandern · Skitouren · ★ KHW 403 (eigen)
- Wenn User von Preset abweicht: „geändert — als eigenes Profil speichern"

### 02 — Grundauswahl
- Frage: **„Welche Metriken ins Briefing?"**
- Toggle-Chips pro Metrik, gruppiert nach Kategorie (Temperatur · Wind · Niederschlag · Atmosphäre · Winter)
- Jede aktivierte Metrik erscheint in Abschnitt 03

### 03 — Reihenfolge & Darstellung
- **Spalten-Block:** nummerierte Liste, jede Zeile hat ▲/▼ (Reihenfolge) · Roh/Einfach-Toggle · → Detail · Entfernen
- **Telegram-Schnittlinie:** nach Position 8 erscheint eine orange gestrichelte Linie
  `✂ ab hier bei Telegram → automatisch Detail-Zeile (max 8 Spalten)` — **direkt im Editor**, kein Tab-Wechsel nötig
- **Detail-Zeile-Block:** ↑ Spalte · Entfernen · Roh/Einfach

### 04 — Kanäle
- Toggle-Liste: Email / Telegram / SMS
- Jeder Toggle erklärt seine Einschränkung (`max 8 Spalten`, `kein Raster · 140 Zeichen`)
- Hinweis: „Aktivierte Kanäle erscheinen auch im Briefing-Zeitplan und in den Alerts"

### Live-Mail-Vorschau (rechts/Sheet)
- Kanal-Tabs: **Email · Telegram · SMS** (kein Signal)
- Diff-Banner: „[Metrik] — verschoben / wird Detail / wird Spalte / deaktiviert / Darstellung geändert"
- **Email:** HTML-Tabelle (Kopf + Segment-1-Zeilen 08/09/10 + Detail-Zeile)
- **Telegram:** Mono-Bubble mit Schnitt-Erklärung („N Spalten rutschen in die Detail-Zeile, weil Telegram max 8 zeigt — deshalb zählt die Reihenfolge")
- **SMS:** Token-Zeile + Zeichen-Counter + Erklärung (Reihenfolge irrelevant)

---

## Briefing-Zeitplan-Tab

- Nur Kanäle, die in Wetter-Metriken aktiv sind, erscheinen als Zeitplan-Option
- Hinweis-Banner: „Nur Kanäle, die du in Wetter-Metriken aktiviert hast, stehen hier zur Auswahl: [Email] [Telegram]"
- Falls kein Kanal aktiv → Warnzustand mit Link zu Wetter-Metriken
- 4 Briefing-Typen: Morgen-Briefing · Abend-Briefing · Alert-Trigger · Mehrtages-Trend
- Pro Karte: Toggle (an/aus) + Uhrzeitfeld + Kanal-Auswahl (nur aktive Kanäle)

---

## Alerts-Tab

- Alerts sind **eigenständig** — sie reagieren auf Schwellenwerte, unabhängig von Reihenfolge/Darstellung
- **Kanal-Vorbelegung:** Standard = aktive Kanäle aus Wetter-Metriken (verhindert doppelte Pflege)
- Pro Alert überschreibbar
- Pro Alert: Label · Metrik · Bedingung · An/Aus · Kanal-Auswahl

---

## Frontend-Spezifikation

### Datenmodell (identisch #14)
```typescript
type Bucket = "primary" | "secondary" | "off";
type Mode   = "raw" | "indicator";

interface MetricConfig {
  id:     string;    // z.B. "temperature", "wind"
  bucket: Bucket;
  order:  number;    // Position innerhalb des Buckets
  mode:   Mode;
}

interface WeatherConfig {
  preset_id: string;
  metrics:   MetricConfig[];
  channels:  { email: boolean; telegram: boolean; sms: boolean };
  dirty:     boolean;  // von Preset abgewichen
}
```

### Renderer (Frontend = Backend, #14)
```python
def render_for_channel(channel: str, config: WeatherConfig) -> RenderedOutput:
    primary   = [m for m in sorted(config.metrics, key=...) if m.bucket == "primary"]
    secondary = [m for m in sorted(config.metrics, key=...) if m.bucket == "secondary"]
    max_cols  = CHANNEL_LIMITS[channel]["max_table_cols"]

    if max_cols is None:           # Email
        in_table = primary
        detail   = secondary
    elif max_cols == 0:            # SMS
        in_table = []
        detail   = primary + secondary
    else:                          # Telegram (max_cols=8)
        in_table = primary[:max_cols]
        detail   = primary[max_cols:] + secondary
    ...
```

### Svelte-Komponenten (Ziele)

| Svelte-Komponente | Zweck | Mockup-Pendant |
|---|---|---|
| `TripEditView` | Shell: Breadcrumb · Hero · 5 Tabs | `ScreenTripEditV2` |
| `WeatherMetricsTab` | Host: 2-Spalten-Layout, State | `WetterMetrikenTabV2` |
| `WM_PresetBar` | Preset-Chips | `WM2_PresetBar` |
| `WM_GrundauswahlSection` | Metrik-Toggles nach Kategorie | `WM2_Grundauswahl` |
| `WM_ReihenfolgeSection` | Spalten-Liste + Detail-Liste + Schnittlinie | `WM2_Reihenfolge` |
| `WM_TelegramCutLine` | Gestrichelte Schnittlinie bei Index 8 | `WM2_CutLine` |
| `WM_KanaeleSection` | Kanal-Toggles | `WM2_Kanaele` |
| `WM_LiveMailPreview` | Kanal-Tabs + Diff-Banner + Renderer | `WM2_MailPreview` |
| `BriefingScheduleTab` | Zeitplan, liest channels aus WeatherMetricsTab | `TE2_ZeitplanTab` |
| `AlertsTab` | Alert-Liste, erbt channels als Default | `TE2_AlertsTab` |
| `WM_MailSheet` (Mobile) | Mail als Bottom-Sheet | `TM2_WetterTab` |

### Diff-Highlight-Arten
`moved · promoted · demoted · added · removed · mode · preset`
→ Banner-Text + Hervorhebung der betroffenen Stelle.
`removed` = roter Banner (Stelle weg, keine Tabellen-Markierung).

### Sieben mögliche Änderungen
| # | Änderung | Mail-Effekt |
|---|---|---|
| 1 | **Reihenfolge** — Spalte nach vorne/hinten | Spalten-Position tauscht; bei Telegram entscheidet sie über Tabelle vs. Detail |
| 2 | **Spalte → Detail** | Spalte verlässt Tabelle, erscheint in Detail-Zeile |
| 3 | **Detail → Spalte** | Detail-Wert wird Tabellen-Spalte |
| 4 | **Hinzufügen** (aus Grundauswahl) | Metrik erscheint neu als Spalte oder Detail |
| 5 | **Ausschalten** | verschwindet komplett (auch nicht in Detail-Zeile) |
| 6 | **Roh ↔ Einfach** | Zellwert: „100" ↔ „sehr wahrsch." |
| 7 | **Preset wechseln** | ganze Auswahl getauscht, kanal-sicher verteilt |

---

## Acceptance Criteria

- [ ] Trip öffnet direkt im Bearbeiten-Modus; kein read-only-Zwischenschritt
- [ ] Tab-Set: Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Briefing-Zeitplan · Alerts
- [ ] Wetter-Metriken hat **4 Abschnitte** (Profil · Grundauswahl · Reihenfolge & Darstellung · Kanäle) + Live-Mail rechts
- [ ] Jede Änderung rendert die Mail **sofort** + hebt geänderte Stelle hervor
- [ ] Telegram-Schnittlinie nach Spalte 8 erscheint **im Editor** (Abschnitt 03) und in der Mail-Vorschau
- [ ] **Kein Signal** — weder Tab, Limit noch Text
- [ ] `CHANNEL_LIMITS.telegram.max_table_cols = 8`, `PRIMARY_SLOTS = 8`
- [ ] Briefing-Zeitplan zeigt **nur aktive Kanäle** aus Wetter-Metriken
- [ ] Briefing-Zeitplan ohne aktiven Kanal → klarer Warnzustand
- [ ] Alerts erben Kanal-Vorbelegung aus Wetter-Metriken, pro Alert überschreibbar
- [ ] Mobile: 4 Abschnitte scrollen vertikal, Mail als Bottom-Sheet, volle Parität

## Edge Cases
| Fall | Verhalten |
|---|---|
| User verschiebt `temperature` auf Position 0 | blockiert (Zeit/Uhrzeit ist fix an Position 0 — sofern `hour`-Spalte existiert; sonst erste aktive Metrik) |
| Spalten > 8 + Kanal Telegram aktiv | Schnittlinie sichtbar; Telegram-Vorschau zeigt Bubble mit „N rutschen"-Banner |
| Kein Kanal aktiv, User öffnet Zeitplan | Warnzustand: „Aktiviere zuerst einen Kanal in Wetter-Metriken" |
| Metrik ohne Indikator-Mapping | kein Roh/Einfach-Toggle (nur „Roh" verfügbar, kein Switch) |
| SMS gewählt | nur Metriken mit Kurz-Code; Rest fällt weg; Reihenfolge/Detail irrelevant |
| Alert-Kanal deaktiviert, weil in Wetter-Metriken abgeschaltet | Alert-Kanal-Toggle bleibt überschreibbar — User kann Alert-Kanal aktivieren auch wenn Briefing-Kanal aus |

## Out of Scope (Folge-Issues)
- Echtes Drag-and-Drop (V1 nutzt ▲/▼)
- Pro-Kanal-Overrides für Metriken (siehe #14 V2)
- Bereinigung Signal-Reste in #14 / #496 (separate kleine Aufgabe)
- Backend `channel_layout.py` Signal-Bereinigung (Backend-Koordination)

## Dedupe-Hinweis (CLAUDE.md Regel 6)
Vor dem Anlegen: prüfen ob unter **Epic #575** ein Sub-Issue für Wetter-Metriken-Editor existiert → cross-linken statt duplizieren. Thematische Nähe: **#14** (Datenmodell/Renderer), **#496** (Vorschau → hier zur Live-Mail weitergedacht), **#20** (IA/Tab-Set).

## Screenshots
- Desktop · Wetter-Metriken · Email-Vorschau — `https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-23-desktop-email.png`
- Desktop · Telegram-Schnitt (−3 Spalten in Detail) — `https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-23-desktop-telegram.png`
- Mobile · Wetter-Metriken (Abschnitte 01–04) — `https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-23-mobile.png`
