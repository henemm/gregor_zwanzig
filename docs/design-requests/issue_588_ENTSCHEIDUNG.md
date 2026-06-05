# Entscheidung #588 · LocationNew-Modal — welche Variante ist die Wahrheit?

**Status:** ENTSCHIEDEN (Tech-Lead-Vote, PO-Override möglich)
**Datum:** 2026-06-05
**Löst:** `issue_588_location_new_variante_klaerung.md` · entblockt Issue #588 (Epic #575)

---

## TL;DR — Entscheidung

> **Variante A (Smart-Import-Modal) ist die Wahrheit. JSX gewinnt.**
> `screen-location-new.jsx` bleibt unverändert. **Das SOLL-PNG
> `M-location-new.png` ist falsch und wird neu erzeugt** (Re-Screenshot der
> JSX). #588 schließt danach als „1:1 erfüllt". Kein Modal-Neubau.

Variante B wird **verworfen**, Variante C (Tabs) **zurückgestellt** (kein
Bedarf in V1). Begründung unten.

---

## Wichtigste Korrektur zuerst — die Klärungs-Notiz beschreibt A falsch

Die Notiz stellt A als reines „POI-Smart-Import-Modal" dar und behauptet, B
würde Benennung / Gruppe / Aktivitätsprofil erst einführen — A verlöre sie.

**Das stimmt nicht.** Die Live-JSX `screen-location-new.jsx` enthält bereits:

| Feld / Sektion        | Variante A (JSX, live) | Variante B (SOLL-PNG) |
|-----------------------|:----------------------:|:---------------------:|
| Ortsname              | ✅ Step 2              | ✅                    |
| Gruppe                | ✅ Step 2              | ✅                    |
| Aktivitätsprofil      | ✅ Step 3 (3 Karten)   | ✅ (Dropdown)         |
| Koordinaten-Eingabe   | ✅ Smart-Import (URL/Coords) | ⚠️ Karte/Adresse |
| Format-Vielfalt       | ✅ 6 Chips (Komoot · GMaps · DMS · Dezimal · UTM · GPX) | ❌ |
| Koord-Vorschau (DEM/TZ/Quelle) | ✅ Erkannt-Card  | ❌                    |
| Karte                 | Mini-Map (Vorschau)    | groß, interaktiv      |
| „Wetter-Template"     | ❌ — **existiert im Produkt nirgends** | ⚠️ erfunden |

**Folge:** Die Variantenlücke ist viel kleiner als die **62,95 % Pixel-Diff**
suggeriert. Der Diff entsteht fast vollständig aus **Layout** (vertikale
Steps 720px vs. Karte-links/Formular-rechts) — **nicht aus fehlender
Funktionalität.** Die Wahl für A verliert keine strukturierten Felder.

---

## Warum A gewinnt (4 Gründe)

1. **Pilot-Regel #575/#583: „JSX gewinnt bei Konflikt."** Konsequent
   angewandt ⇒ A. Eine Ausnahme bräuchte einen starken Produktgrund —
   den gibt es nicht (siehe 2–4).

2. **Paradigmen-Konsistenz.** Der Compare-Wizard (`screen-compare-wizard.jsx`,
   Step „Orte hinzufügen") nutzt **selbst Smart-Import** (linke Spalte
   URL/Coords-Paste). A spricht dieselbe Sprache. B (Klick-auf-Karte) wäre die
   **einzige** Klick-auf-Karte-Fläche im ganzen Produkt — ein Fremdkörper.

3. **Präzision ist Produkt-Kern.** Briefings hängen an exakter Koordinate +
   **DEM-Höhe** (A zeigt „Höhe (DEM) 3.250 m"). Gipfel/Gletscher haben keine
   sinnvolle Postadresse; „Klick auf Karte" ist für 3.250-m-Punkte zu unscharf.
   Paste-Komoot-URL / DMS / UTM liefert metergenaue Koordinaten — genau was ein
   Wetter-Briefing-Werkzeug braucht.

4. **„Wetter-Template" ist ein Phantom.** B führt ein zweites Dropdown
   „Wetter-Template · Skitouren (Basis)" ein. Dieses Konzept existiert **nirgends**
   im Live-Produkt. Das **Aktivitätsprofil IST** bereits der Metrik-Setter —
   wörtlich im Wizard: „Bestimmt, welche Wetter-Metriken … auftauchen." Ein
   zweites Preset-Feld wäre Redundanz, die B mockt, aber kein Code stützt.

---

## Was Claude Code konkret tut (#588)

1. **`screen-location-new.jsx` NICHT anfassen.** Kein Modal-Neubau.
2. **SOLL-PNG ersetzen:** `…/soll/M-location-new.png` neu erzeugen als
   Re-Screenshot der gerenderten JSX (Artboard `location-new` aus
   `Gregor 20 - Desktop.html`, Modal-Crop @720px). Damit fällt der
   Diff-Tool-Befund von 62,95 % auf ~0 %.
3. **#588 schließen** als „1:1 erfüllt — SOLL an JSX angeglichen".
4. **`design-diff-M-location-new.json` neu rechnen** nach SOLL-Tausch (Gegenprobe).

**Nicht** in #588: kein Karten-Layout, kein „Wetter-Template"-Feld, keine Tabs.

---

## Eine echte offene Produktfrage — eskaliert an PO (nicht an Claude Code)

B trennt **Aktivitätsprofil** (Was mache ich) und **Wetter-Template**
(benanntes Metrik-Preset) in zwei Felder. Das ist die **einzige** inhaltlich
interessante Idee aus B. Sie ist aber eine **Datenmodell-Frage**, kein
Layout-Konflikt.

**Tech-Lead-Empfehlung: für V1 NICHT trennen.**
- Aktivitätsprofil setzt sinnvolle Default-Metriken (reicht zum Anlegen).
- Benannte, wiederverwendbare Presets leben bereits im **Metrik-Editor**
  (`L-metrics-editor-save-preset.png` existiert). Dort gehören sie hin —
  „einmal anlegen, im dedizierten Editor verfeinern" ist die Produkt-Architektur.
- Ein zweites Preset-Dropdown im Anlage-Modal verdoppelt Konzepte und Kognition.

⇒ Wenn der PO nicht widerspricht, bleibt es bei **einem** Feld (Aktivitätsprofil).
Falls der PO benannte Wetter-Templates schon im Anlage-Flow will: **eigenes
Issue**, nicht #588, und Anschluss an den Metrik-Editor (nicht als isoliertes
Modal-Dropdown).

---

## Verworfene Optionen

- **B (Karte+Formular wird Wahrheit):** kompletter Neubau, opfert Smart-Import
  + Format-Vielfalt + DEM-Vorschau, bricht Paradigmen-Konsistenz, führt
  Phantom-Feld ein. Schlechtester ROI.
- **C (beides als Tabs):** Mehr-Build für eine Klick-auf-Karte-Mode, die der
  einzige (technische) Nutzer praktisch nie zieht. Over-Engineering für V1.
  **Rückstellung, kein Nein:** Falls je nicht-technische Nutzer dazukommen,
  ist „Karte" als *sekundärer* Tab neben Smart-Import der richtige Ort —
  als V1.5-Issue.

## Optionale V1.5-Veredelung (eigenes Issue, niedrige Prio)

Die eine gute Idee aus B verlustfrei mitnehmen: A's **Vorschau-Mini-Map
draggable** machen, sodass der erkannte Pin fein-justierbar ist (visuelle
Platzierungs-Bestätigung) — **ohne** Smart-Import aufzugeben. Klein, additiv,
kein #588-Scope.

---

## Bezug
- Issue #588 (Sub-Issue Epic #575 Design-Fidelity)
- Original-Klärung: `issue_588_location_new_variante_klaerung.md`
- Visueller A/B-Vergleich: `issue_588_AB-vergleich.html` (dieses Verzeichnis)
- JSX (Variante A): `screen-location-new.jsx`
- SOLL-PNG (Variante B): `…/soll/M-location-new.png`
