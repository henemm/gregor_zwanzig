<!-- gregor-zwanzig-handoff: stable_id=alert-message-render -->
# Issue 27 · Alert-Nachricht — generisches Render-System (Betreff + Email · Telegram · SMS)

**Type:** Frontend (Live-Vorschau) + Backend (Versand-Renderer) — identische Logik beidseitig
**Priority:** High
**Baut auf:** #687 (Alerts-Tab — liefert `level`/Schwellwerte), #14 (Output-Layout-System — Metrik-Registry, Kanal-Constraints), #20 (kanonische IA)
**Design-Quelle:** `Gregor 20 - Alert Mail Vorschläge.html` (Vorher/Nachher + 6 Hebel + Betreff/erste Zeile pro Kanal)

> **Abgrenzung:** #687 baut die **Konfiguration** (welche Metrik bei welcher
> Empfindlichkeit auslöst). Dieses Issue baut die **Nachricht selbst** — wie ein
> ausgelöster Alert in Betreff, Email, Telegram und SMS formatiert wird. Beide
> teilen die Metrik-Registry und die Schwellwert-Tabelle aus #687/#14.

---

## Problem (PO-Feedback, Screenshot der aktuellen Alert-Mail)

![Vorher · aktuelle Alert-Mail](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-27-alert-vorher.png)

Die heutige Alert-Mail meldet **dass** sich etwas geändert hat, aber nicht **wie
weit** und **in welche Richtung**:

1. **Betreff trägt keine Information.** `[KHW 403] Wetter ändert sich seit dem Briefing`
   ist bei jedem Alert identisch — im Postfach-Stapel nicht unterscheidbar.
2. **Überschrift = Betreff.** Die prominenteste Stelle wiederholt nur den Betreff.
3. **Keine Richtung, kein Schwellwert-Bezug.** `1230 → 620` ohne Pfeil, ohne
   Bezug zur konfigurierten Alarm-Schwelle (drüber/drunter?).
4. **Roh-Zahlen + Langform.** `1230.0` (Nachkommastelle = Rauschen), Langname
   „Gewitterenergie" statt des Tabellen-Kürzels `CAPE`.

**Wichtig (CLAUDE.md-Leitprinzip):** Das System **interpretiert die Wetterdaten
nicht** und gibt **keine Handlungsempfehlungen** („Start verschieben"). Es ist
ein Profi-Werkzeug — alle Angaben sind rein rechnerisch ableitbar (Pfeil aus dem
Vorzeichen, Prozent aus zwei Werten, über/unter aus der konfigurierten Schwelle).
Kein Modell, keine Deutung der Wetterlage.

---

## Lösung — Architektur

### Kernprinzip

> Ein Alert ist eine Liste von **`AlertEvent`** (eine pro Metrik, die seit dem
> letzten Briefing eine Schwelle überschritten hat). Vier reine Renderer
> projizieren dieselben Events in **Betreff · Email · Telegram · SMS**. Reihenfolge
> bei mehreren Events: **nach Schwere** (Abstand zur Schwelle, normiert). Das gilt
> **generisch für jede Metrik** — die Renderer kennen keine Metrik namentlich,
> sondern lesen alles aus der Registry.

### Datenmodell

```typescript
type Direction = "up" | "down";        // rein aus value_to vs value_from
type Cmp = "über" | "unter";           // aus der Metrik-Registry

interface AlertEvent {
  metric_id:    string;                // FK → Metrik-Registry
  value_from:   number;                // Wert im letzten Briefing
  value_to:     number;                // aktueller Wert
  threshold:    number;                // aus Empfindlichkeit (level) abgeleitet, #687
  cmp:          Cmp;                    // Vergleichsrichtung der Schwelle
  occurred_at:  string;                // "HH:MM" — Zeitpunkt des Werts
  km_from:      number;                // Segment-Start (km)
  km_to:        number;                // Segment-Ende (km)
}

interface AlertMessage {
  trip_short:   string;                // "KHW 403"
  stand_at:     string;                // "HH:MM" — Stand der Auswertung
  events:       AlertEvent[];          // ≥1, vom Trigger geliefert (#687)
}
```

### Abgeleitete Größen (rein rechnerisch, KEINE Deutung)

```
direction(e)  = e.value_to > e.value_from ? "up" : "down"        // ↑ / ↓
arrow(e)      = direction(e) == "up" ? "↑" : "↓"
delta_pct(e)  = round((e.value_to - e.value_from) / e.value_from * 100)   // "−50 %"
over_thr(e)   = e.cmp == "über" ? e.value_to > e.threshold
                                : e.value_to < e.threshold
side_label(e) = over_thr(e) ? "über" : "unter"                   // Schwellwert-Seite
severity(e)   = e.cmp == "über" ? (e.value_to - e.threshold) / e.threshold
                                : (e.threshold - e.value_to) / e.threshold
km_span       = [min(events.km_from), max(events.km_to)]         // Union über alle Events
```

Werte werden **gerundet** dargestellt (keine Nachkommastelle, außer die Einheit
braucht sie — siehe `decimals` in der Registry, z. B. Sicht `0.5`).

---

## Metrik-Registry (generisch — Single Source)

Jeder alert-fähige Metrik-Eintrag hat: **Tabellen-Kürzel** (für Email/Telegram/
Betreff), **SMS-Code** (für SMS), Einheit, Vergleich, Nachkommastellen. Kürzel +
Vergleich + Einheit kommen aus der bestehenden Registry (`organisms.jsx`
METRICS / `screen-metrics-editor.jsx`); die Schwelle aus #687.

**Neu in diesem Issue: SMS-Codes für alle alert-fähigen Metriken** — die etablierten
bleiben (`N D R PR W G TH`), fehlende werden ergänzt (Konvention: 1–2 Großbuchstaben,
kollisionsfrei, ASCII):

| Metrik (id)        | Kürzel (Tabelle) | SMS-Code | Einheit | Vergleich | Dezimal |
|--------------------|------------------|----------|---------|-----------|---------|
| `gust`             | Böen             | `G`      | km/h    | über      | 0       |
| `wind`             | Wind             | `W`      | km/h    | über      | 0       |
| `precip`           | Niedersch        | `R`      | mm/h    | über      | 1       |
| `rain_probability` | Regen%           | `PR`     | %       | über      | 0       |
| `thunder`          | Gewitter         | `TH`     | %       | über      | 0       |
| `cape`             | CAPE             | `CP` ⟵neu| J/kg    | über      | 0       |
| `temp_min`         | Temp             | `N`      | °C      | unter     | 0       |
| `temp_max`         | Temp             | `D`      | °C      | über      | 0       |
| `snowfall`         | Schnee           | `SN` ⟵neu| cm      | über      | 0       |
| `snowfall_limit`   | 0°-Grenze        | `SL` ⟵neu| m       | unter     | 0       |
| `visibility`       | Sicht            | `VS` ⟵neu| km      | unter     | 1       |
| `humidity`         | Feuchte          | `HU` ⟵neu| %       | über      | 0       |

> **Regel:** Jede alert-fähige Metrik MUSS einen SMS-Code haben. Beim Hinzufügen
> einer neuen Metrik wird hier ein Code vergeben (nicht im Renderer hartkodiert).
> Δ-/Änderungs-Metriken (Temp-/Wind-/Niederschlags-Änderung aus #687) brauchen
> **keinen** eigenen Code — der Alert zeigt immer den aktuellen Wert + Richtung
> (das `+`/`−`-Vorzeichen trägt die Änderung).

---

## Renderer 1 · Betreff

Reihenfolge fest: **Trip · Ort (km) · Richtung · Metrik**.

```
# 1 Event:
[<trip>] km <a>–<b> · <arrow> <Kürzel>: <from>→<to>
  → [KHW 403] km 0–1.8 · ↓ CAPE: 1230→620

# ≥2 Events (Top-3 nach severity, arrow = Richtung des schwersten Events):
[<trip>] km <a>–<b> · <arrow> <N> über Schwelle: <K1> <to1>, <K2> <to2>, <K3> <to3>
  → [KHW 403] km 0–4 · ↑ 3 über Schwelle: Böen 52, Gewitter 55%, Niedersch 14
```

`<N>` = Anzahl Events über Schwelle. Bei >3 Events werden nur die schwersten 3
genannt; der Rest steckt in der vollen Mail.

---

## Renderer 2 · Email

![Email · 1 Event (optimiert)](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-27-alert-mail-single.png)

![Mehrere Metriken · nach Schwere geordnet](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-27-alert-mail-multi.png)

```
EYEBROW (verdict, faktisch):
  1 Event:  <arrow> <delta_pct> · jetzt <side_label> Schwelle <thr>
  ≥2:       <arrow> <N> Schwellen überschritten

H1 (faktisch, generisch — KEINE abgeleiteten Wörter wie „halbiert"):
  1 Event:  <Kürzel> <delta_pct> seit dem Briefing
  ≥2:       <N> Werte über der Alarm-Schwelle

DATENBLOCK (eine Zeile pro Event, nach severity sortiert):
  <Kürzel> · Schwelle <thr> <einheit>      <from> <arrow> <to> <einheit>  [über|unter]
  (Events unter Schwelle, falls mitgeliefert, gedimmt am Ende)

FOOTER:
  Stand: heute <stand_at> · verglichen mit dem letzten Briefing · km <a>–<b>
```

- Pfeil rot, wenn `over_thr` (Wert auf der Alarm-Seite), sonst grün — die Farbe
  kodiert **Schwellwert-Seite**, nicht „gut/schlecht".
- Kein Freitext-Satz „Was heißt das", keine Empfehlung.

---

## Renderer 3 · Telegram

```
<b><trip> · km <a>–<b> · <arrow> <Kürzel | "N über Schwelle"></b>
<from>→<to> (<delta_pct>) · <side_label> Schwelle <thr>          # 1 Event
<K1> <f1>→<t1> · <K2> <f2>→<t2> · <K3> <f3>→<t3>                  # ≥2 Events
```

Fette erste Zeile = dieselbe Verdikt-Reihenfolge wie der Betreff. Unicode-Pfeile
erlaubt (kein Zeichensatz-Limit).

---

## Renderer 4 · SMS

![Betreff/erste Zeile pro Kanal](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-27-alert-channels.png)

Striktes Token-Format, **ASCII/GSM-7**, max 140 Zeichen. Aufbau:

```
<trip-kompakt> km<a>-<b>: <sign><CODE><to>[@<hh>] <sign><CODE><to>[@<hh>] …
  1 Event:  KHW403 km0-1.8: -CP620@09
  ≥2:       KHW403 km0-4: +G52@15 +TH55%@15 +R14 +PR90%@14
```

- **Richtung über Vorzeichen-Präfix:** `+` = gestiegen, `−`(ASCII `-`) = gefallen.
- **Kein Unicode** (auch kein `^`/`↑` — `^` ist in GSM-7 ein Escape-Zeichen und
  zählt doppelt; Unicode-Pfeile kippen das Limit von 140 auf 70 Zeichen).
- Token = `<sign><CODE><value>` + optional `@<hh>` (Stunde). `%`-Metriken hängen
  `%` direkt an den Wert (`TH55%`).
- **Längen-Budget:** Tokens nach `severity` einsortieren, bis 140 Zeichen füllen.
  Überzählige weglassen und mit `+<k>` am Ende anzeigen (k = Anzahl weggefallen) —
  identische Logik wie der bestehende `CP_smsRender` in
  `screen-channel-preview-redesign.jsx`. So bleibt SMS auch bei vielen Metriken kurz.

---

## Geteilte Logik (Backend + Frontend)

Die vier Renderer sind **reine Funktionen** über `AlertMessage` → String. Sie
laufen identisch:
- **Backend** beim Versand (`trip_report.py` / Alert-Sender) für Email/Telegram/SMS.
- **Frontend** in der Live-Vorschau (`BEISPIEL-ALERT` im Alerts-Tab #687, sowie im
  Vorschau-Tab) — damit der Profi vor der Reise sieht, wie ein Alert aussieht.

Empfehlung: Renderer als reines Modul `alert_render.{py,ts}` mit gemeinsamer
Fixture-Testsuite (gleiche Inputs → gleiche Strings beidseitig).

```python
def render_subject(msg: AlertMessage) -> str:
    evs = sorted(msg.events, key=severity, reverse=True)
    km = km_span(msg.events)
    if len(evs) == 1:
        e = evs[0]
        return f"[{msg.trip_short}] km {km[0]}–{km[1]} · {arrow(e)} {short(e)}: {fmt(e.value_from)}→{fmt(e.value_to)}"
    top = evs[:3]
    lead = arrow(evs[0])
    parts = ", ".join(f"{short(e)} {fmt(e.value_to)}{pct_unit(e)}" for e in top)
    return f"[{msg.trip_short}] km {km[0]}–{km[1]} · {lead} {len(evs)} über Schwelle: {parts}"

def render_sms(msg: AlertMessage, maxlen=140) -> str:
    evs = sorted(msg.events, key=severity, reverse=True)
    km = km_span(msg.events)
    prefix = f"{compact(msg.trip_short)} km{km[0]}-{km[1]}:"
    toks, dropped = [], 0
    for e in evs:
        sign = "+" if direction(e) == "up" else "-"
        tok = f"{sign}{sms_code(e)}{fmt(e.value_to)}{pct(e)}" + (f"@{e.occurred_at[:2]}" if has_time(e) else "")
        if len(" ".join([prefix, *toks, tok])) + (5) > maxlen:   # +Reserve für "+k"
            dropped += 1; continue
        toks.append(tok)
    tail = f" +{dropped}" if dropped else ""
    return " ".join([prefix, *toks]) + tail
```

---

## Constraints

| ID | Constraint |
|----|-----------|
| C1 | **Keine Interpretation der Wetterdaten, keine Handlungsempfehlung** — nur Richtung, Delta, Schwellwert-Bezug (alles rein rechnerisch). |
| C2 | Betreff-Reihenfolge fest: **Trip · Ort (km) · Richtung · Metrik**. |
| C3 | Metrik-Namen = **Tabellen-Kürzel** aus der Registry (z. B. `CAPE`), nicht Langform. |
| C4 | Richtung: Email/Telegram über Pfeil `↑`/`↓`; SMS über Vorzeichen `+`/`−`. Farbe (rot/grün) kodiert die **Schwellwert-Seite**, nicht „gut/schlecht". |
| C5 | Ort als **km-Spanne** (`km a–b`), nie als Segment-Nummer; Union über alle Events. |
| C6 | Werte gerundet (Registry-`decimals`); keine künstlichen Nachkommastellen. |
| C7 | SMS strikt **ASCII/GSM-7**, ≤140 Zeichen; jede alert-fähige Metrik hat einen SMS-Code; bei Überlauf nach `severity` füllen + `+k` für weggefallene. |
| C8 | Mehrere Events nach `severity` (normierter Schwellwert-Abstand) sortiert; Betreff/SMS nennen die schwersten zuerst. |
| C9 | H1 generisch & faktisch (kein „halbiert"/„verdoppelt" — solche Wörter sind metrik-/wert-spezifisch und gelten als Deutung). |
| C10 | Renderer sind reine Funktionen, **backend- und frontend-identisch** (gemeinsame Fixtures). |

---

## Acceptance Criteria

- [ ] Betreff bei 1 Event: `[Trip] km a–b · <Pfeil> <Kürzel>: from→to`
- [ ] Betreff bei ≥2 Events: `[Trip] km a–b · <Pfeil> N über Schwelle: K1 v1, K2 v2, K3 v3` (Top-3 nach severity)
- [ ] Email: Eyebrow-Verdikt (faktisch), generische H1, Datenblock mit Pfeil + Δ% + Schwellwert-Seite, km-Footer
- [ ] Telegram: fette Verdikt-Zeile + Detailzeile(n), Unicode-Pfeile
- [ ] SMS: Token-Format `±CODE value[@hh]`, ASCII/GSM-7, ≤140, severity-Füllung + `+k`
- [ ] Neuer SMS-Code `CP` (CAPE) + `SN`/`SL`/`VS`/`HU` vergeben; keine Metrik ohne Code
- [ ] Werte gerundet; `1230.0`→`1230`
- [ ] Kein Freitext-Interpretations-Satz, keine Empfehlung in irgendeinem Kanal
- [ ] Farbe kodiert Schwellwert-Seite (über=rot, unter-Schwelle/entfernt=grün), nicht Wertung
- [ ] Renderer identisch in Versand (Backend) und Live-Vorschau (Frontend), durch gemeinsame Fixtures abgesichert
- [ ] Generisch über **alle** alert-fähigen Metriken getestet (nicht nur CAPE)

---

## Edge Cases

| Fall | Verhalten |
|------|-----------|
| Wert von 0 ausgehend gestiegen | `delta_pct` undefiniert → nur Absolutwerte zeigen, kein `%` |
| Mehrere Events, gemischte Richtung | Lead-Pfeil = Richtung des schwersten Events; je Event eigener Pfeil im Datenblock |
| Event spannt mehrere Segmente | km-Spanne = Union (min km_from … max km_to) |
| >3 Events | Betreff/SMS: Top-3 / severity-Füllung; Email/Telegram: alle |
| SMS-Überlauf trotz Füllung | weggefallene als `+k` am Ende; nie >140 |
| Metrik ohne SMS-Code | Build-Fehler/Lint — Code-Pflicht (C7), nicht stillschweigend weglassen |
| Δ-/Änderungs-Metrik löst aus | aktueller Wert + Vorzeichen; kein eigener Δ-Token |

---

## Out of Scope (Folge-Issues)

- **Mehrsprachigkeit** der Renderer (aktuell DE).
- **Push-Notifications** als vierter Kanal.
- **Alert-History/Log** (eigener Archiv-Tab).
- **Radar-/Nowcast-Alert-Format** (Sofort-Regen/Gewitter) — eigenes, kürzeres Schema; hier nur der Abweichungs-Alert gegen das letzte Briefing.
