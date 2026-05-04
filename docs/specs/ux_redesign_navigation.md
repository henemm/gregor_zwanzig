---
entity_id: ux_redesign_navigation
type: design
created: 2026-04-17
updated: 2026-04-17
status: approved
version: "1.0"
tags: [ux, navigation, frontend, sveltekit]
---

# UX Redesign: Navigation & Use-Case-Struktur

## Approval

- [x] Approved (2026-04-17, Feature-Diskussion)

## Purpose

Neuorganisation der Gregor 20 Navigation entlang der zwei Kern-Use-Cases statt entlang der Datenstruktur. Die App ist ein Vorbereitungs-Cockpit fuer Wanderer, die zuhause Trips und Orts-Vergleiche konfigurieren. Unterwegs kommen nur die Reports per E-Mail/Signal/SMS.

## Kontext

### Ist-Zustand (8 Nav-Eintraege)

```
Uebersicht | Trips | Locations | Abos | Vergleich | Wetter | Einstellungen | Konto
```

Organisiert nach Datenstruktur. User muss selbst verstehen, wie Locations, Abos und Compare zusammenhaengen.

### Soll-Zustand (3 Bereiche + Startseite)

```
Startseite       →  Kachel-Uebersicht (Trips + Orts-Vergleiche)
├── Meine Touren →  Trip-Liste, Wizard, Wetter-Drill-Down
├── Orts-Vergleich → Sidebar (Orte in Gruppen) + Content (Vergleich/Auto-Reports)
└── Konto        →  Kanaele, Passwort, System-Status, Account loeschen
```

## Zwei Kern-Use-Cases

### UC1: Trip (Mehrtages-Tour)

*"Ich wandere naechste Woche den GR20. Sag mir jeden Abend und jeden Morgen was ich wissen muss."*

- Route (GPX oder manuell)
- Etappen-Details (Zwischenstationen, Timing)
- Welche Wetterdaten — kontextabhaengig pro Report-Typ (Abend: Nacht-Minimum, Morgen: UV+Gewitter)
- Welcher Kanal — E-Mail, SMS, Signal, Satellite
- Welche Reports wann — Abend-Briefing, Morgen-Update, Untertags-Warnung

### UC2: Orts-Vergleich (fester Ort, beste Wahl)

*"Dieses Wochenende Skifahren — welches Gebiet hat die besten Bedingungen?"*

- Orte in Gruppen (Skigebiete Tirol, Surfspots Portugal...)
- Welche Parameter zaehlen — Neuschnee, Wind, Sonne...
- Entscheidungshilfe zu konfigurierbarem Zeitpunkt
- Updates bei Warnwetter

---

## 1. Startseite

### Layout: Kacheln

Trips und Orts-Vergleiche als Cards nebeneinander. Jede Kachel zeigt Kern-Info auf einen Blick.

```
┌─────────────┐ ┌─────────────┐
│ 🥾 GR20     │ │ 🥾 GR221    │
│ 21. April   │ │ 10. Mai     │
│ 5 Etappen   │ │ 4 Etappen   │
│ Reports ✓   │ │ Reports ✓   │
└─────────────┘ └─────────────┘
┌─────────────┐ ┌─────────────┐
│ ⛷ Ski Tirol │ │ 🏄 Surf PT  │
│ tägl. 07:00 │ │ Do 18:00    │
│ Stubaier #1 │ │ Peniche #1  │
└─────────────┘ └─────────────┘

       [+ Neue Tour]  [+ Neuer Vergl.]
```

- Klick auf Trip-Kachel → oeffnet Trip in "Meine Touren"
- Klick auf Vergleichs-Kachel → oeffnet Vergleich in "Orts-Vergleich"
- Schnellzugang zum Anlegen neuer Touren und Vergleiche

---

## 2. Meine Touren

### Trip-Liste

Bestehende Trip-Tabelle bleibt erhalten. Funktioniert bereits gut.

### Wizard "Neue Tour anlegen" (4 Schritte)

Gefuehrter Ablauf ersetzt heutiges TripForm + GPX Upload + ReportConfig + WeatherConfig.

#### Schritt 1: Route

- **GPX primaer** — Upload per Drag & Drop
- Ein-Datei-Upload: Auto-Split in Etappen (via `<trk>`-Elemente, `<trkseg>`, oder Heuristik)
- Multi-Datei-Upload: Jede Datei wird eine Etappe
- Automatische Erkennung ob Gesamt-Track oder Einzel-Etappen
- Fallback: Manuelles Anlegen (fuer User ohne GPX-Daten)
- Trip-Name vergeben

```
Schritt 1 von 4: Route
━━━━━━━━━━━━━━━━━━━━
● Route  ○ Etappen  ○ Wetter  ○ Reports

[GPX hochladen] (Drag & Drop)

1 Datei  → Auto-Split in Etappen
N Dateien → Je eine Etappe

  ── oder ──

  Manuell anlegen >

          [Weiter →]
```

#### Schritt 2: Etappen

- Erkannte Etappen anzeigen
- Editierbar: zusammenfuehren, trennen, umbenennen, Datum zuweisen
- Wegpunkte pro Etappe sichtbar
- Uebernachtungstyp (Huette/Zelt/Biwak) — vorbereitet fuer F5

#### Schritt 3: Wetter-Template

- **Template waehlen** als Startpunkt (Alpen-Trekking Sommer, Kuesten-Wandern, Skitouren, Kanu...)
- **Override:** Metriken hinzufuegen/entfernen
- **Zeithorizont pro Metrik:** Jede Metrik kann eigenen Horizont haben (heute/morgen/uebermorgen)
- Angepasstes Template **im Profil speichern** fuer Wiederverwendung bei neuen Trips

```
Template: Alpen-Trekking (Sommer)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Gewitter:
  ✓ heute  ✓ morgen  ✓ übermorgen

Temperatur:
  ✓ heute  ○ morgen  ○ übermorgen

Wind:
  ✓ heute  ✓ morgen  ○ übermorgen

Hinzugefügt:
  + Frostgrenze (heute, morgen)

[Im Profil speichern]     [Weiter →]
```

#### Schritt 4: Reports & Kanaele

- **Verschiedene Report-Typen** mit jeweils eigenen Metrik-Sets:
  - Abend-Report: Uhrzeit, Kanaele, Metriken (z.B. Nacht-Minimum, Frost, Gewitter+2d)
  - Morgen-Report: Uhrzeit, Kanaele, Metriken (z.B. Max-Temp, UV, Niederschlag)
  - Warnungen: An/Aus, Schwellwerte
- **Kanaele pro Report-Typ waehlbar** — aus im Konto eingerichteten Kanaelen (E-Mail, Signal, SMS, Satellite)

```
Schritt 4 von 4: Reports
━━━━━━━━━━━━━━━━━━━━━━━━

Abend-Report  18:00  [E-Mail] [Signal]
  Metriken: Tiefsttemp, Frost,
  Gewitter+1d+2d, Grat-Wind
  [Anpassen]

Morgen-Report  07:00  [E-Mail]
  Metriken: Max-Temp, UV,
  Niederschlag, Gewitter+1d
  [Anpassen]

Warnungen  ✓ aktiv
  Bei: Gewitter, Wind >60km/h

          [Tour speichern]
```

### Wetter-Drill-Down

Keine eigene Wetter-Seite mehr. Stattdessen: stuendliche Wetter-Detailansicht erreichbar aus einer Etappe oder einem Ort heraus.

---

## 3. Orts-Vergleich

### Layout: Sidebar + Content (Master-Detail)

Heutige Locations, Compare und Subscriptions werden in einem Bereich zusammengefuehrt.

```
┌────────────┐┌───────────────────────┐
│ Meine Orte ││ Content               │
│            ││                       │
│ ▼ Ski Tirol││ (Auto-Reports oder    │
│   Stubaier ││  Vergleichsergebnis   │
│   Hintertux││  oder Abo-Config)     │
│   Axamer   ││                       │
│            ││                       │
│ ▶ Surf PT  ││                       │
│            ││                       │
│ [+ Gruppe] ││                       │
│ [+ Ort]    ││                       │
└────────────┘└───────────────────────┘
```

### Sidebar: Orte in Ordnern/Kategorien

- Orte sind in Gruppen organisiert (Skigebiete Tirol, Surfspots Portugal, Wandern Mallorca...)
- Ein Ort gehoert zu genau einer Gruppe
- Gruppe als Ganzes fuer Vergleich waehlbar
- Checkboxen zur Auswahl fuer Ad-hoc-Vergleich
- Bestehende LocationForm wiederverwenden

```
Meine Orte
━━━━━━━━━━
▼ Skigebiete Tirol
    ☑ Stubaier Gletscher
    ☑ Hintertux
    ☐ Axamer Lizum
▼ Surfspots Portugal
    Nazare
    Peniche
    Ericeira
▶ Wandern Mallorca (3)

[+ Gruppe]  [+ Ort]
```

### Content: Default-Ansicht (kein Vergleich aktiv)

Uebersicht der aktiven Auto-Reports mit letztem Ergebnis und naechstem Lauf.

```
Deine Auto-Reports
━━━━━━━━━━━━━━━━━━

Ski Tirol  täglich 07:00
  Letzter: Stubaier #1
  Nächster: morgen 07:00

Surf PT  woch. Donnerstag
  Letzter: Peniche #1
  Nächster: Do 18:00
```

### Content: Nach Vergleich

- Ergebnis-Tabelle (bestehende Compare-Darstellung wiederverwenden)
- **"Als Auto-Report speichern"** — erstellt Abo direkt aus Ad-hoc-Vergleich
- Metrik-Konfiguration: Wie bei Trips (Template + Override, Zeithorizont pro Metrik)
- Unterschiedliche Metrik-Sets pro Report-Typ (Morgen/Abend/Warnung)
- Kanaele: Aus Konto waehlbar, pro Report-Typ

---

## 4. Konto

- **Benachrichtigungskanaele:** E-Mail, Signal, SMS, Satellite (Credentials einrichten)
- **Gespeicherte Wetter-Templates:** Eigene angepasste Templates verwalten
- **Passwort aendern**
- **System-Status:** Kompakte Anzeige ob Reports laufen (Scheduler-Status, naechster Report)
- **Account loeschen**

---

## Mapping: Alt → Neu

| Heute | Wird zu | Aenderung |
|-------|---------|-----------|
| Uebersicht | Startseite (Kacheln) | Redesign |
| Trips | Meine Touren (Trip-Liste) | Umbenannt, Wizard statt Dialoge |
| GPX Upload | Wizard Schritt 1 | Kein separater Nav-Punkt |
| Locations | Orts-Vergleich → Sidebar | Teil des Vergleichs-Bereichs |
| Compare | Orts-Vergleich → Content | Zusammengefuehrt |
| Abos (Subscriptions) | Orts-Vergleich → Auto-Reports | Zusammengefuehrt |
| Wetter | Drill-Down aus Ort/Etappe | Kein eigener Nav-Punkt |
| Einstellungen | Konto → System-Status | Integriert |
| Konto | Konto (erweitert) | + Templates, + System-Status |

## Wetter-Metriken: Template-System

### Vordefinierte Templates

Templates liefern eine sinnvolle Basis-Konfiguration. Der User uebernimmt ein Template und passt es an. Angepasste Templates werden im Profil gespeichert und sind bei neuen Trips/Vergleichen wiederverwendbar.

- **Alpen-Trekking (Sommer):** Temp, Wind, Boeen, Gewitter, Niederschlag, Sichtweite, Grat-Wind, Frostgrenze
- **Kuesten-Wandern:** Temp, Wind, Niederschlag, Bewoelkung, UV
- **Skitouren:** Schnee, Neuschnee, Wind, Sicht, Frost, Nullgrad, Lawine (wenn F10)
- **Kanu/Kajak:** Wind, Wellen, Niederschlag, Stroemung, Sicht
- **Wintersport (Piste):** Schneehoehe, Neuschnee, Wind, Gefuehlte Temp, Sonne

### Pro-Metrik-Zeithorizont

Jede Metrik kann einen eigenen Zeithorizont haben:

```
Gewitter:     ✓ heute  ✓ morgen  ✓ übermorgen
Temperatur:   ✓ heute  ○ morgen  ○ übermorgen
Wind:         ✓ heute  ✓ morgen  ○ übermorgen
```

### Unterschiedliche Sets pro Report-Typ

Abend-Report, Morgen-Report und Warnungen koennen verschiedene Metrik-Sets haben:

- **Abend:** Tiefsttemp Nacht, Frostgrenze, Gewitter morgen+uebermorgen, Grat-Wind
- **Morgen:** Max-Temp, UV, Niederschlag stuendlich, Gewitter uebermorgen
- **Warnung:** Gewitter, Starkregen, Wind >60km/h

---

## Designprinzipien

1. **Use-Case-zentriert** — Navigation folgt den zwei Zielen des Users, nicht der Datenstruktur
2. **Bestehende Komponenten wiederverwenden** — LocationForm, Compare-Tabelle, Trip-Tabelle funktionieren und bleiben erhalten
3. **Wizard fuer Komplexes** — Gefuehrter Ablauf statt 4 verteilte Dialoge
4. **Templates statt 24 Toggles** — Sinnvolle Vorauswahl, Override moeglich, im Profil speicherbar
5. **Kanaele global, Zuweisung lokal** — Credentials im Konto, Auswahl pro Report

---

## Abhaengigkeiten zu bestehenden Features

| Feature | Status | Relevanz |
|---------|--------|----------|
| F5: Biwak-/Zelt-Modus | Offen | Wizard Schritt 2 (Uebernachtungstyp) vorbereitet |
| F1: SMS-Kanal | Offen | Konto: SMS als Kanal einrichten |
| F9: Satellite Messenger | Offen | Konto: Satellite als Kanal einrichten |
| F10: Lawinen-Integration | Offen | Template "Skitouren": Lawinen-Metrik |

## Nicht in Scope

- Trip-Umplanung per Kommando (F6) — eigenes Feature
- Regelbasierte Metrik-Konfiguration — Template+Override reicht vorerst
- Tags/Labels fuer Orte — Ordner/Kategorien genuegen

## Changelog

- 2026-04-17: Initial spec aus Feature-Diskussion erstellt
