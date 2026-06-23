<!-- gregor-zwanzig-handoff: stable_id=alerts-tab-687 -->
# Issue 687 · Alerts-Tab — Empfindlichkeits-Presets pro Metrik (Desktop + Mobile)

**Type:** Frontend (UX-Redesign des Alerts-Tabs im Trip-Edit-Screen)
**Priority:** High
**Supersedes:** die ältere Schwellwert-Zahlen-Spec dieses Issues (freie Zahlen-Inputs pro Metrik). **Aktueller Stand: `issue_846_alert_preset` (approved).**
**Baut auf:** #23 (Wetter-Metriken-Tab — Kanal-Verbindung), #20 (kanonische IA), #14 (Output-Layout-System)
**Design-Quelle:**
- `Gregor 20 - Trip bearbeiten.html` — Haupt-Deliverable (Desktop + Mobile)
- `screen-trip-edit-v2-main.jsx` — Desktop: `TE2_AlertsTab` (+ `TE2_ALERT_PRESET_TABLE`, `TE2_SensSeg`, `TE2_MetricSensRow`)
- `screen-trip-edit-v2-mobile.jsx` — Mobile: `TM2_AlertsTab` (+ `TM2_*`-Pendants)

---

## Was Alerts leisten (Funktion)

Gregor Zwanzig schickt dem Wanderer **zwischen** Morgen- und Abend-Briefing
automatisch eine Kurz-Mail, wenn sich das Wetter anders entwickelt als beim
letzten Briefing vorhergesagt. Zwei Arten:

1. **Abweichungs-Alert (Forecast):** Hat sich Wind, Regen, Gewitter etc. um mehr
   als einen Schwellwert verändert? Knappe Mail: welche Metrik, von-nach, auf
   welcher Etappe.
2. **Radar-Alert (Nowcast):** Kommt in den nächsten ~20 Minuten unerwartet Regen
   oder Gewitter? Sofort-Meldung.

---

## Problem (PO-Feedback → issue_846)

Die vorherige Iteration ließ den Nutzer **Zahlen pro Metrik** eintippen
(Schwellwert-Tabelle mit Number-Inputs, dazu Modus-Karten Δ / Absolut / Beides).
Das war zu fummelig und fehleranfällig. PO-Entscheidung:

> Der Nutzer gibt **keine Zahlen** mehr ein. Statt einer Zahl wählt er **pro
> Metrik eine Empfindlichkeit** aus einem festen Set. Die konkreten Schwellwerte
> hinter jeder Stufe sind vorgegeben (Backend-Defaults).

**Entfällt vollständig:**
- Zahlen-Inputs pro Metrik
- Modus-Karten (Δ / Absolut / Beides) — der Modus steckt implizit im Preset
- Signal als Kanal (Kanäle sind nur Email · Telegram · SMS; Alerts erben die im
  Briefing-Zeitplan aktiven Kanäle)
- Severity-Felder

---

## Lösung — Architektur

### Kernprinzip

> Die Alerts-Liste ist **keine eigene Entität** — sie ist eine Projektion der
> aktiven Trip-Metriken. Pro Metrik wählt der Nutzer **eine Empfindlichkeit**:
> `off` · `relaxed` · `standard` · `sensitive`. Default je Metrik: `standard`.

Ein **globaler Quickset** („Alle Metriken auf …") setzt alle Zeilen auf eine
Stufe; danach kann jede Metrik einzeln übersteuert werden (Zustand „gemischt").

### Datenmodell

```typescript
type SensLevel = "off" | "relaxed" | "standard" | "sensitive";

interface TripAlertConfig {
  cooldown_minutes: number;            // default 60, min 1, max 1440
  quiet_from: string;                  // "HH:MM", default "22:00"
  quiet_to:   string;                  // "HH:MM", default "06:00"  (darf quiet_from überschreiten → Mitternacht-Wrap)
  rules: AlertRule[];                  // eine pro aktiver Metrik
}

interface AlertRule {
  metric_id: string;                   // Foreign key → TripMetric.id
  level: SensLevel;                    // default "standard"
}
```

Kein `threshold`-Feld mehr im Frontend-State — der Schwellwert ergibt sich aus
`level` + `metric_id` über die unten stehende Preset-Tabelle (Backend ist
Source-of-Truth; das Frontend spiegelt sie nur zur Anzeige).

### Empfindlichkeits-Tabelle (13 Metriken × 3 Stufen)

Stufe `off` löst nie aus. Die drei aktiven Stufen (vorgegebene Werte, Backend-Default):

| Metrik | Einheit | Vergleich | Entspannt | Standard | Sensibel |
|---|---|---|---|---|---|
| Böen | km/h | über | 85 | 70 | 55 |
| Niederschlag | mm/h | über | 8 | 5 | 3 |
| Gewitter | % | über | 60 | 40 | 25 |
| Schneefallgrenze | m | unter | 1200 | 1500 | 1800 |
| Temp. Min | °C | unter | −10 | −5 | 0 |
| Temp. Max | °C | über | 32 | 28 | 24 |
| Temp.-Änderung | °C | Δ ≥ | 8 | 5 | 3 |
| Wind-Änderung | km/h | Δ ≥ | 30 | 20 | 12 |
| Niederschlags-Änderung | mm | Δ ≥ | 15 | 10 | 5 |
| Neuschnee | cm | über | 20 | 10 | 5 |
| CAPE | J/kg | über | 800 | 500 | 300 |
| Sichtweite | km | unter | 0.5 | 1 | 2 |
| Luftfeuchtigkeit | % | über | 98 | 95 | 90 |

„Sensibel" = engste Schwelle (löst am frühesten aus), „Entspannt" = lockerste.
Sowohl absolute Schwellen als auch Änderungs-Schwellen (Δ) sind im Preset
abgebildet — der Nutzer unterscheidet das nicht mehr explizit.

---

## Desktop-Design (`TE2_AlertsTab`)

![Desktop Alerts-Tab](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-687-desktop-alerts.png)

### Aufbau

```
ALERTS · SOFORT-MELDUNG
Sofort-Meldung zwischen den Briefings
<Intro: Abweichungs-Alert + Radar-Alert, Empfindlichkeit je Metrik>

Alle Metriken auf:  [Aus][Entspannt][Standard][Sensibel]   N von 13 aktiv · gemischt

┌─ Tabelle (Card, kein padding) ──────────────────────────────────┐
│ METRIK            EMPFINDLICHKEIT                    SCHWELLWERT  │
│ Böen  km/h        [Aus][Entsp][Standard][Sens]            > 70   │
│ Niederschlag      [Aus][Entsp][Standard][Sens]            > 5    │
│ …  (Aus-Zeile: gedimmt, Segment „Aus" dunkel, „kein Alert")     │
└──────────────────────────────────────────────────────────────────┘

Cooldown: [60] Minuten        Stille Stunden: [22:00] – [06:00]

BEISPIEL-ALERT
<Alert-Mail-Vorschau: Metrik · Vorher · Nachher · Etappe·Zeitfenster>
```

### Verhalten

- **Segmented-Control pro Zeile** mit 4 Stufen. Aktive Stufe: Akzent-Pill
  (Burnt Orange); Stufe `off`: dunkle Pill (`--g-ink-3`), Zeile gedimmt
  (`opacity: .6`), Schwellwert-Spalte zeigt „kein Alert".
- **Schwellwert-Spalte** ist read-only und zeigt den aus `level` abgeleiteten
  Wert (`> 70`, `< 1500`, `Δ ≥ 5`). Kein Input.
- **Globaler Quickset** setzt alle Zeilen (`setAll`). Sind die Zeilen nicht
  einheitlich, ist kein Quickset-Segment aktiv und der Zähler zeigt „· gemischt".
- **Cooldown / Stille Stunden** direkt sichtbar (kein Accordion). Dimmen, wenn
  alle Metriken `off`.
- **Beispiel-Alert**: kompakte Mail-Vorschau (Metrik · Vorher · Nachher ·
  Etappe·Zeitfenster).

---

## Mobile-Design (`TM2_AlertsTab`)

![Mobile Alerts-Tab](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-687-mobile-alerts.png)

Gleiche Logik, mobil-optimiert:

| Aspekt | Desktop | Mobile |
|---|---|---|
| Segmented-Control | inline (`6px 14px`) | full-width, `flex:1`, `min-height: 42` |
| Stufen-Labels | „Aus/Entspannt/Standard/Sensibel" | gekürzt „Aus/Entsp./Std./Sens." |
| Metrik-Zeile | Grid (Label · Seg · Wert) | gestapelt: Label + Wert oben, Seg darunter |
| Cooldown/Stille | 2-Spalten-Grid | gestapelt (flex-column), Inputs `font-size: 16` (kein iOS-Zoom) |
| Quickset | inline | full-width Segmented + Zähler-Zeile |

---

## API-Endpunkte

```
GET /api/trips/{trip_id}/alerts        → TripAlertConfig
PUT /api/trips/{trip_id}/alerts        → 200 | 422   (komplette Config, nicht per Regel)
```

### Metriken-Sync

Fügt der User im Wetter-Metriken-Tab eine Metrik hinzu/entfernt sie, synchronisiert
das Backend `rules`:
- Neue Metrik → neue `AlertRule { level: "standard" }`
- Entfernte Metrik → Regel löschen

---

## Constraints

| ID | Constraint |
|----|-----------|
| C1 | Keine freien Alert-Regeln — eine Regel pro aktiver Trip-Metrik |
| C2 | **Keine Zahlen-Eingabe** — nur Stufenwahl; Schwellwerte sind vorgegeben |
| C3 | Stufen-Set fix: `off · relaxed · standard · sensitive`; Default `standard` |
| C4 | Globaler Quickset setzt alle Zeilen; Einzel-Übersteuerung erlaubt („gemischt") |
| C5 | Kein Modus-Toggle (Δ/Absolut/Beides) — Modus steckt im Preset |
| C6 | Kein Signal-Kanal, keine Severity-Felder, kein Per-Regel-Kanal (Alerts erben Zeitplan-Kanäle) |
| C7 | Cooldown 1…1440 Min; Stille Stunden dürfen Mitternacht überspannen |
| C8 | Schwellwert-Spalte read-only, abgeleitet aus `level` |

---

## Alert-Trigger-Logik (Backend)

```python
THRESHOLDS = {  # (level -> wert) je metric_id, siehe Tabelle oben
  "gust": {"relaxed": 85, "standard": 70, "sensitive": 55, "cmp": "gt"},
  # …
}

def should_alert(rule, current_value, change_value, cooldown_state, config):
    if rule.level == "off":
        return False
    spec = THRESHOLDS[rule.metric_id]
    thr = spec[rule.level]
    val = change_value if spec.get("delta") else current_value
    if spec["cmp"] == "gt" and val <= thr: return False
    if spec["cmp"] == "lt" and val >= thr: return False
    last = cooldown_state.get(rule.metric_id)
    if last and (now() - last).seconds < config.cooldown_minutes * 60:
        return False
    if in_quiet_hours(config.quiet_from, config.quiet_to):
        return False  # gestaute Alerts → Zusammenfassung mit Morgen-Briefing
    return True
```

---

## Acceptance Criteria

- [ ] **AC-1:** Given ein Trip mit aktiven Wetter-Metriken, When der Nutzer den Alerts-Tab öffnet, Then sieht er exakt die im Wetter-Metriken-Tab aktiven Metriken — keine eigene Verwaltung
- [ ] **AC-2:** Given die Metrik-Liste, When der Nutzer eine Metrik ansieht, Then gibt es pro Metrik ein Segmented-Control mit `Aus · Entspannt · Standard · Sensibel` (Default `Standard`) — **kein Zahlen-Input**
- [ ] **AC-3:** Given Stufe `off`, When die Zeile gerendert wird, Then ist die Zeile gedimmt (`opacity .6`) und die Schwellwert-Spalte zeigt „kein Alert"
- [ ] **AC-4:** Given mehrere Metriken auf verschiedenen Stufen, When der Globale Quickset angezeigt wird, Then zeigt der Zähler „N von 13 aktiv · gemischt" und kein Segment ist aktiv
- [ ] **AC-5:** Given Cooldown und Stille Stunden, When der Tab gerendert wird, Then sind beide direkt sichtbar (kein Accordion); dunkeln ab wenn alle Metriken `off`
- [ ] **AC-6:** Given eine Änderung der Alert-Config, When `PUT /api/trips/{id}/alerts` aufgerufen wird, Then persistiert die Config mit Stufen statt Zahlen
- [ ] **AC-7:** Given eine neue Metrik im Wetter-Metriken-Tab, When der Nutzer sie aktiviert, Then synchronisiert das Backend eine neue `AlertRule { level: "standard" }`
- [ ] **AC-8:** Given Mobile-Ansicht, When der Tab gerendert wird, Then sind Touch-Targets ≥ 44px, Inputs `font-size: 16px`, Stufen-Labels gekürzt „Aus/Entsp./Std./Sens."

---

## Out of Scope (Folge-Issues)

- **Eigene Schwellwerte pro Metrik** — bewusst weggelassen; Stufen-Set reicht. Falls je gewünscht, als „Experten-Modus" separat.
- **Per-Regel-Kanal-Override** — V1 nutzt die Zeitplan-Kanäle global.
- **Push-Notifications** — aktuell Email/Telegram/SMS.
- **Alert-History/Log** — eigener Archiv-Tab.
