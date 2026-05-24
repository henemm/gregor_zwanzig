# Anforderung an Claude Design — Konsolidierung der Wetter-Editoren

**Zugehöriges Issue:** #345 (Sub-Issue 4 von #304 — letzter offener Teil)
**Erstellt:** 2026-05-24
**Status:** offen — wartet auf Design-Entscheidung (+ ggf. Mockups)

## Worum es geht (in einem Satz)

Die Wetter-Werte einer Tour lassen sich heute an **drei verschiedenen Stellen** einstellen —
mit unterschiedlichem Funktionsumfang. Wir wollen das auf **eine** Bedien-Logik
vereinheitlichen. Bevor wir umbauen, brauchen wir von dir die UX-Entscheidung, welche der
Stellen bleibt und wie sie aussieht.

## Kontext

Epic #304 hat „Pro-Metrik-Zeithorizont" eingeführt: Im **vollen Wetter-Editor** (Tab im
Tour-Detail) kann jede Metrik pro Tag — **heute / morgen / übermorgen** — ein- und
ausgeschaltet werden. Der Server filtert die Briefings danach, abgeleitet vom Etappen-Datum.

Die drei vorigen Teil-Aufgaben sind fertig und live:
- #342 Backend (Datenmodell + Filter pro Etappe)
- #343 die HEUTE/MORGEN/ÜBERMORGEN-Chips im vollen Editor
- #344 die „Wetter-Profile"-Karte zum Verwalten gespeicherter Vorlagen auf der Konto-Seite

Offen ist nur noch das Aufräumen: zwei ältere Editoren, die diese Neuerungen **nicht** haben.

## IST-Zustand: drei Editoren

### 1. Voller Wetter-Editor — REFERENZ, bleibt
Wo: Tab „Wetter" im **Tour-Detail**. Hat alles: HEUTE/MORGEN/ÜBERMORGEN-Chips pro Metrik,
Roh/Indikator-Umschalter, Vorlagen-Liste, Live-Tabellenvorschau, „Als Profil speichern",
Speichern/Verwerfen mit „ungespeicherte Änderungen"-Hinweis.
*(Code: `WeatherMetricsTab.svelte` — gilt als Soll.)*

### 2. Wetter-Sektion in der Tour-Bearbeiten-Maske — veraltet
Wo: aufklappbarer Abschnitt „Wetter" in der **Tour-Bearbeiten-Maske** (eine lange Maske mit
Abschnitten Route / Etappen / Wetter / Alarmregeln / Briefings, EIN Speichern-Knopf unten).
Kann nur An/Aus + Roh/Indikator. **Keine** Zeithorizonte.
*(Code: `EditWeatherSection.svelte` in `TripEditView.svelte`.)*

### 3. Schnell-Fenster aus den Listen — veraltet
Wo: kleines Pop-up-Fenster, das man **aus den Listen** „Abos", „Orte" und „Touren" pro
Eintrag öffnet, um dessen Wetter-Werte schnell zu setzen. Kann nur An/Aus + Roh/Indikator.
**Keine** Zeithorizonte.
*(Code: `WeatherConfigDialog.svelte`, genutzt von `/subscriptions`, `/locations`, `/trips`.)*

```
┌─ Tour-Detail ──────────┐   ┌─ Tour bearbeiten ──────┐   ┌─ Liste (Abo/Ort/Tour) ─┐
│ Tab: Wetter            │   │ ▸ Route                │   │  Eintrag … [⚙ Wetter]  │
│  ✓ Temp [H][M][Ü] …    │   │ ▸ Etappen              │   │        │                │
│  ✓ Wind [H][M][Ü] …    │   │ ▾ Wetter  (alt, ohne   │   │        ▼ öffnet Pop-up  │
│  Vorlagen · Vorschau   │   │     Horizonte)         │   │   ┌──────────────────┐  │
│  [Als Profil speichern]│   │ ▸ Alarmregeln          │   │   │ ✓ Temp  Roh/Ind. │  │
│  [Verwerfen][Speichern]│   │ ▸ Briefings            │   │   │ ✓ Wind  Roh/Ind. │  │
│        = REFERENZ       │   │ [Speichern (alles)]    │   │   │ [Abbr.][Speichern]│  │
└────────────────────────┘   └────────────────────────┘   │   └──────────────────┘  │
                                                            └────────────────────────┘
```

## Wichtige fachliche Randbedingungen (bitte beim Entscheiden beachten)

- **Zeithorizonte brauchen ein Datum.** HEUTE/MORGEN/ÜBERMORGEN leitet sich vom Etappen-Datum
  ab. **Touren** haben Etappen-Daten — **Abos und Orte nicht.** Bei Abos/Orten sind die drei
  Chips fachlich sinnlos.
- **Stiller Datenverlust heute.** Die zwei alten Editoren speichern die Wetter-Konfiguration,
  indem sie sie **komplett überschreiben**. Wer also zuerst im vollen Editor Zeithorizonte
  setzt und danach über die alte Bearbeiten-Maske oder das Schnell-Fenster speichert, verliert
  die Horizont-Einstellungen unbemerkt. Das ist ein zusätzlicher Grund für die Vereinheitlichung
  (wird technisch ohnehin behoben).
- **Redundanz bei Touren.** Eine Tour ist heute an **zwei** Stellen wetter-bearbeitbar:
  im Detail-Tab (voll) **und** in der Bearbeiten-Maske (alt). Das verwirrt.

## Deine Entscheidungen — das brauchen wir von dir

### F1 — Schnell-Fenster (Pop-up aus Abos/Orte/Touren): bleibt oder geht?
- **(a) Bleibt, vereinheitlicht:** Schnellzugriff aus der Liste bleibt, nutzt aber dieselbe
  Optik/Bausteine wie der volle Editor — **ohne** Zeithorizont-Chips (auch bei Touren).
- **(b) Bleibt, bei Touren mit Horizonten:** wie (a), aber bei Touren zusätzlich die drei Chips
  (Abos/Orte weiter ohne). Zwei leicht verschiedene Varianten des Fensters.
- **(c) Geht weg:** Kein Schnell-Fenster mehr; Wetter setzt man nur noch auf der jeweiligen
  Detail-/Bearbeiten-Seite. Sauberste Lösung, aber für Abos/Orte ein Klick mehr.
- Falls (a)/(b): brauchst du dafür ein Mockup, oder reicht „Optik des vollen Editors im Modal"?

### F2 — Tour-Bearbeiten-Maske: Wetter-Abschnitt behalten oder streichen?
- **(a) Behalten + modernisieren:** Der Abschnitt „Wetter" in der Bearbeiten-Maske bleibt,
  bekommt aber die vollen Funktionen inkl. Zeithorizonte (eingebettet, speichert mit dem
  einen Speichern-Knopf der Maske).
- **(b) Streichen:** Wetter verschwindet aus der Bearbeiten-Maske; man bearbeitet es nur noch
  über den Tour-Detail-Wetter-Tab. Beseitigt die Doppel-Bedienung, ändert aber den gewohnten
  Ort. Falls (b): soll an der Stelle ein kurzer Verweis stehen („Wetter wird im Tab … bearbeitet")?

### F3 — Horizonte bei Abos/Orten
- Bestätige bitte: bei Abos/Orten erscheinen **keine** Zeithorizont-Chips (kein Datum).
- Falls du eine sinnvolle Alternative siehst (z. B. relative Tage ab Versand), benenne sie —
  sonst lassen wir sie dort einfach weg.

## Out of Scope für diese Anfrage

- Optik der HEUTE/MORGEN/ÜBERMORGEN-Chips selbst (existiert bereits, #343).
- Backend-Verhalten (#342 ist live).
- „Wetter-Profile"-Karte auf der Konto-Seite (#344 fertig).
- Innere Felder des vollen Editors (Vorlagen-Liste, Vorschau) — die bleiben wie sie sind.

## Deliverables

1. Klare Antwort auf **F1, F2, F3** (je 1–2 Sätze Begründung).
2. Wo nötig: Mockup(s) im Stil von `claude-code-handoff/screenshots/soll-flow1D-*.png`
   — insbesondere für ein eventuell modernisiertes Schnell-Fenster und/oder den
   eingebetteten Wetter-Abschnitt der Bearbeiten-Maske.
3. Falls Begriffe im UI auftauchen: kanonische Copy beachten (Tour, Ort, Abo, Briefing, Etappe).
