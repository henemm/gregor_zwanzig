# Design Request — Issue #561: Multi-Day Trend im Abendbericht (E-Mail)

**Priorität:** Medium  
**GitHub Issue:** #561 — "F3: Multi-Day Trend — 3-Tage-Vorschau im Abendbericht"  
*(Claude Design hat keinen Zugriff auf GitHub Issues — alle relevanten Infos stehen vollständig in diesem Dokument.)*  
**Kontext:** Abend-E-Mail eines aktiven Trips, am Ende des Reports, nach dem Haupt-Wetterteil

---

## Was gezeigt werden soll

Am Ende des Abendberichts erscheint ein kompakter Block: die **nächsten 2–3 Wanderetappen** mit je einer Zeile Wettervorschau. Das hilft dem Wanderer zu entscheiden, ob er morgen eine Extra-Etappe einlegt oder lieber wartet.

**Daten pro Etappe:**
- Wochentag (Mo/Di/…)
- Etappenname (z. B. „Sóller → Tossals Verds")
- Wetter-Zusammenfassung: Temperatur, Niederschlag, Wind, Gewitter

## Kontext im E-Mail-Layout

Die E-Mail hat bereits folgende Abschnitte (von oben nach unten):
1. Header (Trips-Name, Datum, Etappe)
2. Kompaktzusammenfassung (1–2 Sätze Wetter)
3. Stunden-Tabelle (Metriken pro Wegpunkt)
4. Gewitter-Vorschau (optionaler Block)
5. **→ Hier: Nächste Etappen (neuer Block)**
6. Highlights / Zusammenfassung

## Designfragen für Claude Design

### Frage 1: Spalten oder Fließtext?

**Option A — Spaltenformat** (klarer, schneller scanbar):
```
Nächste Etappen
Mo  Sóller → Tossals Verds    ⛅ 8–16°C   🌧 3mm   💨 20km/h   ⚡ –
Di  Tossals Verds → Lluc      ☀ 6–18°C   🌧 0mm   💨 12km/h   ⚡ –
Mi  Lluc → Scorca             ⛅ 7–14°C   🌧 8mm   💨 35km/h   ⚡ MED
```

**Option B — 2-Zeilen-Summary** (informativer, mehr Kontext):
```
Nächste Etappen
Mo  Sóller → Tossals Verds
    8–16°C, ⛅, trocken bis 13:00 dann 3mm, mäßiger Wind W 20 km/h

Di  Tossals Verds → Lluc
    6–18°C, ☀, trocken, schwacher Wind W
```

### Frage 2: Visuell abgesetzt oder eingebettet?

Der Block steht zwischen Gewitter-Vorschau und Highlights. Soll er:
- A) Durch eine Trennlinie / andersfarbigen Hintergrund klar abgesetzt sein?
- B) Nahtlos wie die anderen Abschnitte integriert sein, nur mit eigenem Heading?

### Frage 3: Heading-Text

Vorschläge: „Nächste Etappen", „Ausblick", „Weiterer Verlauf" — was passt zum Ton des Briefings?

## Constraints

- **E-Mail-HTML:** Kein CSS Grid/Flexbox. Nur `<table>`, `<div>`, inline styles.
- **Plain-Text-Variante** muss ebenfalls definiert sein (für Signal/SMS-Fallback).
- **Max. 3 Etappen** im Block — kein Scrollen.
- **Breite:** Optimiert für 600px (Standard-E-Mail-Breite), lesbar auch schmaler.
- **Gewitter-Ampel:** ⚡ NONE / LOW / MED / HIGH — muss auf einen Blick erkennbar sein.
- Dieses Feature gehört zum E-Mail-Rendering (`src/formatters/trip_report.py`), **nicht** zum Frontend-UI.
