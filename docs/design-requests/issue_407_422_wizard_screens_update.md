# Design-Request: Wizard-Screens auf aktuelle Implementierung aktualisieren

**Priorität:** Hoch — Handoff-Screens sind veraltet und blockieren korrekte SOLL-IST-Vergleiche

## Hintergrund

Der Trip-Wizard (`/trips/new`) wurde in Issue #300 bewusst umstrukturiert:

| | Altes Design (noch im Handoff) | Aktuelles Design (implementiert, korrekt) |
|-|-------------------------------|------------------------------------------|
| Step 1 | Profil & Eckdaten (Activity-Chips + Name + Kürzel) | Route (Name + Region + GPX-Upload) |
| Step 2 | GPX-Import (Drag-Drop) | Etappen (erkannte Etappen-Liste nach GPX) |
| Step 3 | Wegpunkte bestätigen (KI-Vorschläge) | Wetter (Aktivitätsprofil-Dropdown + Metriken-Tabelle) |
| Step 4 | Briefings & Kanäle (Kanal-Toggles) | Reports (2×2 Cards: Abend/Morgen/Warnungen/Trend) |

Der Handoff zeigt noch das alte Design. Die Implementierung folgt dem neuen Design — das ist richtig.

## Was benötigt wird

**Aktualisierte SOLL-Screens für alle 4 Wizard-Schritte** — Desktop (1440px) + Mobile (390px):

### Step 1 — Route
- Trip-Name-Input (Pflicht) + Region-Input (optional, max 50 Zeichen)
- GPX-Upload-Dropzone (dashed accent border)
- "Aus Dateisystem wählen" + Drag-Drop
- Stepper: "SCHRITT 1 VON 4 · NEUE TOUR", H1 "Route — wie kennt das System deinen Weg?"
- Footer: Abbrechen | Weiter → (disabled bis Name + GPX)
- Referenz IST: `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/desktop-wizard-step1.png`

### Step 2 — Etappen
- Header: "N ETAPPEN ERKANNT AUS N GPX" + "Zusammenführen"-Link
- Etappen-Liste: Nummer · Name · Datum · km · ↑Höhe · WP-Zähler · "+N Vorschläge" (orange gestrichelte Pill)
- Rechte Spalte: Vorlagen-Panel (GR20, Karnischer Höhenweg, Stubaier Höhenweg)
- Footer: ← Zurück | "Pausentag einfügen" | Weiter →
- Referenz IST: `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/desktop-wizard-step2.png`

### Step 3 — Wetter
- Aktivitätsprofil-Dropdown (Alpen-Trekking Sommer, Skitouren, Küsten, …)
- Metriken-Tabelle: pro Zeile Checkbox + Metrik-Name + 3 Horizon-Pills (HEUTE/MORGEN/ÜBERMORGEN) + Format-Label
- Schwarze Oval-Pills für Horizons — aber: IST-Styling ist sehr dunkel/dominant, bitte polieren
- Footer: ← Zurück | Weiter →
- Referenz IST: `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/desktop-wizard-step3.png`

### Step 4 — Reports
- **2×2 Card-Grid:**
  1. Abend-Briefing: Aktiv-Checkbox + Uhrzeit **18:00** (24h!) + Kanal-Chips
  2. Morgen-Update: Aktiv-Checkbox + Uhrzeit 06:00 + Kanal-Chips
  3. Warnungen · AUTARK: kein Zeitfeld, Badge "AUTARK" + Beschreibungstext + Kanal-Chips
  4. Mehrtages-Trend: Hinweistext "Im Abend-Briefing enthalten"
- Abschluss-Button: "**Tour speichern**" (nicht "Speichern")
- Footer-Hinweis kursiv: "Unterwegs läuft alles autark. Kein Eingreifen nötig."
- Referenz IST: `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/desktop-wizard-step4.png`

## Bekannte IST-Probleme die das SOLL bereinigen sollte

- Step 3: Schwarze Oval-Buttons für HEUTE/MORGEN/ÜBERMORGEN sind optisch zu dominant → polieren
- Step 4: Uhrzeiten aktuell als 12h (06:00 PM) — SOLL muss 24h zeigen (18:00)
- Step 4: Button heißt "Speichern" — SOLL heißt "Tour speichern"
- Alle Steps: Stepper-Subtext unter den Schritten fehlt im IST — im SOLL zeigen (z.B. "Route · Etappen · Wetter · Reports")

## Mobile (390px)

Gleiche 4 Steps, aber:
- Step 1: Fortschrittsbalken (4 Segmente) statt nur Text-Stepper
- Step 4: Cards gestapelt (1-spaltig), nicht 2×2
- Kein Bottom-Nav während Wizard-Session
