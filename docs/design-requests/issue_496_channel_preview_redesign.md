# Design Request — Issue #496: "Pro Kanal"-Vorschau neu denken

**Priorität:** Medium  
**Bezug:** Issue #496, Component `ChannelPreviewBlock.svelte` + `ChannelPreviewCard.svelte`  
**Kontext:** Trip editieren → Wetter-Metriken-Tab → Block "VORSCHAU · SO KOMMT ES BEIM EMPFÄNGER AN · Pro Kanal"

---

## Was der Block heute tut (und warum es nicht funktioniert)

Der Block zeigt vier kleine Kacheln nebeneinander (Email / Telegram / Signal / SMS). Jede Kachel enthält eine Monospace-Mini-Tabelle mit erfundenen Beispielwerten (`11.6`, `30`, `78 %` usw.) und soll zeigen, welche Metriken als Tabellenspalten erscheinen und welche in eine "Detail-Zeile" rutschen.

**Das Problem:** Kleine Kacheln können eine E-Mail nicht sinnvoll abbilden. Eine E-Mail-Tabelle hat Dutzende Zeichen Breite, eine Kachel im 4er-Grid hat ~200 px. Was man sieht, ist unleserliche Monospace-Text-Fragmente — kein verständliches Bild.

**Der User kann daraus nicht ablesen:**
- Was konkret passiert, wenn er 12 Metriken wählt
- Worin sich Email (unbegrenzte Spalten) vs. Signal (max. 5) unterscheidet
- Warum manche Metriken "in die Detail-Zeile rutschen"

---

## Was der Block leisten SOLL (der eigentliche Nutzen)

Der Nutzer konfiguriert, welche Wetter-Metriken in seinem Briefing erscheinen sollen. Verschiedene Kanäle haben unterschiedliche Kapazität:

| Kanal    | Tabellen-Spalten | Besonderheit |
|----------|-----------------|--------------|
| Email    | unbegrenzt      | Volle HTML-Tabelle |
| Telegram | max. 7          | Monospace-Tabelle |
| Signal   | max. 5          | Monospace-Tabelle |
| SMS      | 0               | Nur Fließtext, max. 140 Zeichen |

Wenn der Nutzer 10 Metriken wählt und Signal als Kanal nutzt: **5 erscheinen in der Tabelle, 5 rutschen in eine Detail-Zeile darunter.** Das ist eine wichtige Konsequenz seiner Konfiguration — er soll sie verstehen, bevor er speichert.

---

## Die kritische Design-Frage

**Kann dieses Konzept überhaupt mit kleinen Kacheln funktionieren?**

Die aktuelle Umsetzung als 4er-Grid mit Mini-Karten scheitert am Grundproblem: Der E-Mail-Kanal hat faktisch keine Spalten-Grenze und könnte 20+ Spalten enthalten — eine Kachel kann das nie sinnvoll zeigen.

**Kernfrage an Claude Design:** Welches UI-Pattern ist hier das richtige? Mögliche Richtungen (keine Präferenz — offen für andere Vorschläge):

### Option A: Konsequenz-Anzeige statt Vorschau
Statt "wie sieht es aus" → "was passiert mit deinen Metriken":
- Kompakte Zusammenfassung: "Email: alle 12 als Spalten · Signal: 5 Spalten, 7 als Detail-Text · SMS: 12 als Text"
- Kein Layout-Preview, nur die Zahl und was passiert
- Warnung wenn Metriken "zu weit hinten" rutschen (z.B. ⚠ Signal zeigt nur 5/12 als Spalten)

### Option B: Ein-Kanal-Fokus mit Wechsler
- Statt 4 kleine Kacheln: eine größere Vorschau für den aktiven/primären Kanal
- Tab oder Dropdown oben: Email · Telegram · Signal · SMS
- Genug Platz für eine echte Tabellen-Vorschau

### Option C: Entfernen, Konsequenz inline
- Block komplett entfernen
- Stattdessen: beim Metrik-Auswahl-Editor direkt eine Zeile "Signal zeigt 5 von 12 Metriken als Spalten" einblenden
- Keine eigene Sektion, nur Inline-Feedback im Editor

---

## Entscheidungs-Grundlage für Claude Design

- **Nutzungskontext:** Desktop-Planungstool (kein Mobile-first). Side-by-Side-Layouts sind normal.
- **Nutzungsmoment:** Nutzer konfiguriert den Trip VOR dem Urlaub. Er schaut sich die Konfiguration einmal an — braucht ein klares Signal, ob seine Metriken-Auswahl "passt".
- **Primäre Frage:** Rutschen wichtige Metriken in die Detail-Zeile oder gar weg? Wenn ja: welche?
- **Kein Live-Wetter:** Der Block soll keine echten Wetterdaten zeigen — nur die Layout-Konsequenz der Konfiguration.

---

## Bestehendes Design-System

Referenz: `docs/design-system/` (CHARTER, COMPONENTS, TOKENS, SCREENS.json)  
Design-Leitprinzip: **Lesbarkeit über Optik** — Inhalt muss unter Zeitdruck klar sein.

## Deliverable

Einen oder zwei Mockups (Svelte-JSX-Format wie in `docs/design/`), die zeigen:
1. Wie die Konsequenz der Kanal-Kapazität kommuniziert wird
2. Ob eine Vorschau sinnvoll möglich ist oder ein anderes Pattern besser passt

Die Entscheidung, welche Option, liegt bei Claude Design — bitte mit kurzer Begründung.
