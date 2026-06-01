# #310 — Design: Trip-Wizard Steps 2–4 — Detaillierte Screens (Desktop + Mobile)

**Labels:** `priority:high` `frontend` `area:trips` `area:editor` `for:claude-design`
**URL:** https://github.com/henemm/gregor_zwanzig/issues/310
**Erstellt:** 2026-05-21

---

## Was fehlt

Der Trip-Wizard (`/trips/new`) hat **nur für Step 1 (Route/GPX-Upload) einen vollständigen Soll-Mockup** (aus letztem Handoff). Die Schritte 2, 3 und 4 sind nur konzeptionell in `docs/specs/ux_redesign_navigation.md §2` beschrieben — keine visuellen Specs.

## Was bereits existiert

- Step 1 Soll-Mockup: `soll-flow1B-wizard-step1-route.png` ✅
- Step 2 Konzept: „Erkannte Etappen anzeigen, editierbar, Wegpunkte sichtbar" (nur Text)
- Step 3 Konzept: „Template wählen + Override-Toggles" (nur Text)
- Step 4 Konzept: „Report-Typen mit Uhrzeit + Kanal-Auswahl" (nur Text)

## Was ich brauche

**Desktop + Mobile** für:

### Step 2: Etappen bestätigen
- Liste der erkannten Etappen (Name, Datum, Etappentyp-Icon)
- Editierbare Felder pro Etappe: Datum-Picker, Name-Input
- Zusammenführen / Trennen von Etappen
- Algorithmus-Vorschläge für Wegpunkte (orange gestrichelt markiert?)
- Navigation: „Zurück" + „Weiter"

### Step 3: Wetter-Template
- Template-Auswahl (Radio-Cards oder Dropdown): Alpen-Trekking, Küsten-Wandern, Skitouren, Kanu, Wintersport
- Override-Tabelle: Metrik / Heute / Morgen / Übermorgen (Checkboxes)
- Button „Im Profil speichern"
- Navigation: „Zurück" + „Weiter"

### Step 4: Reports & Kanäle
- Je Report-Typ (Abend / Morgen / Warnungen) eine expandierbare Sektion
- Uhrzeit-Input, Kanal-Toggles (E-Mail / Signal / SMS)
- Preview-Text des Reports
- Submit: „Trip anlegen"

## Betroffene Dateien

- `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte`
