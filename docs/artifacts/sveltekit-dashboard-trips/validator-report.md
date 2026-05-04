# External Validator Report

**Spec:** docs/specs/modules/sveltekit_dashboard_trips.md
**Datum:** 2026-04-13T14:45:00+02:00
**Server:** http://localhost:3000 (SvelteKit) + http://localhost:8090 (Go API)
**Validator:** Unabhaengige Session (External Validator Agent)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Dashboard: 3 Stats-Cards (Trips, Locations, Health) | Screenshot 01_dashboard.png — Trips: 2, Locations: 15, System Status: API ok, Python Core ok, v0.1.0 | **PASS** |
| 2 | Dashboard: "Verwalten" Links zu /trips und /locations | Links vorhanden: `a[href='/trips']` und `a[href='/locations']`, Text "Verwalten" | **PASS** |
| 3 | Dashboard: SSR, kein Loading-Spinner | Kein Spinner-Element gefunden, Daten sofort sichtbar beim Laden | **PASS** |
| 4 | Trips: Tabelle mit Name, Etappen, Zeitraum, Aktionen | Screenshot 02_trips_list.png — Table-Headers: Name, Etappen, Zeitraum, Aktionen | **PASS** |
| 5 | Trips: Etappen als Badge mit Anzahl | HTML bestaetigt: `data-slot="badge"` shadcn Badge-Komponente, "4 Etappen" | **PASS** |
| 6 | Trips: Datumsbereich (erste — letzte Stage.date) | "2026-01-17 — 2026-01-20" fuer GR221 Mallorca (4 Etappen) | **PASS** |
| 7 | Trips: Edit/Delete Buttons pro Zeile | Buttons "Bearbeiten" und "Loeschen" in jeder Tabellenzeile | **PASS** |
| 8 | Trips: Create Button oeffnet Dialog mit leerem TripForm | "Neuer Trip" Button oeffnet Dialog, leeres Formular mit Placeholder "Name des Trips" | **PASS** |
| 9 | Trips: Edit Button oeffnet vorausgefuellten Dialog | Screenshot 08_edit_dialog.png — "Trip bearbeiten" Dialog, Name "Validator-Test-Trip" vorausgefuellt | **PASS** |
| 10 | Trips: Delete mit Bestaetigungsdialog | Screenshot 10_delete_confirm.png — "Trip loeschen: Moechtest du ... wirklich loeschen? Diese Aktion kann nicht rueckgaengig gemacht werden." mit Abbrechen/Loeschen | **PASS** |
| 11 | Trips: Delete entfernt Trip aus Liste | Trip nach Bestaetigung nicht mehr in Tabelle | **PASS** |
| 12 | TripForm: Dynamische Stages (hinzufuegen/entfernen) | Screenshot 05_create_with_stage.png — "Etappe 1" mit Datumsfeld und X-Button zum Entfernen | **PASS** |
| 13 | TripForm: Dynamische Waypoints pro Stage | Screenshot 06_create_with_waypoint.png — "Punkt 1" mit Lat 47, Lon 11 (Defaults laut Spec) | **PASS** |
| 14 | TripForm: Client Validation — Name required | Screenshot 12_validation_empty.png — "Trip-Name ist erforderlich" in Rot | **PASS** |
| 15 | TripForm: Mindestens eine Stage zum Speichern | Screenshot 13_stage_validation.png — Fehlermeldung bei Save ohne Stage | **PASS** |
| 16 | TripForm: Mindestens ein Waypoint pro Stage | Screenshot 14_waypoint_validation.png — Fehlermeldung bei Stage ohne Waypoint | **PASS** |
| 17 | CRUD-Zyklus: Create → in Liste, Edit → aktualisiert, Delete → entfernt | Playwright-Test durchgespielt: Create "Validator-Test-Trip" → Edit zu "Validator-Edited-Trip" → Delete → weg | **PASS** |

## Findings

### F1: Validierungsmeldungen teilweise Englisch
- **Severity:** LOW
- **Expected:** Konsistent deutsche UI-Texte
- **Actual:** Stage/Waypoint-Validierung auf Englisch: "At least one stage required", "stage Etappe 1: At least one waypoint required"
- **Evidence:** Screenshots 13_stage_validation.png, 14_waypoint_validation.png
- **Impact:** Inkonsistenz — Name-Validierung ist deutsch ("Trip-Name ist erforderlich"), aber Stage/Waypoint-Validierung kommt auf Englisch vom Go API zurueck

### F2: Go API Auth — Env-Var-Prefix unklar
- **Severity:** MEDIUM (Deployment-relevant)
- **Expected:** Go API liest `GZ_AUTH_USER`/`GZ_AUTH_PASS` aus Environment
- **Actual:** Go Binary nutzt `envconfig` mit unklarem Prefix. Weder `AUTH_USER`, `GZ_AUTH_USER`, noch andere Prefix-Kombinationen funktionierten bei manuellem Start. Login funktioniert nur wenn SvelteKit die Env-Vars beim Prozessstart korrekt weitergibt.
- **Evidence:** `strings ./gregor-api` zeigt `AuthUser envconfig:"AUTH_USER"`, aber alle Prefix-Varianten lieferten 401
- **Impact:** Startup-Scripts und Systemd-Service muessen korrekte Env-Var-Namen verwenden

### F3: SvelteKit CSRF ohne ORIGIN Env-Var
- **Severity:** MEDIUM (betrifft localhost-Deployment)
- **Expected:** Login funktioniert auf localhost
- **Actual:** Ohne `ORIGIN=http://localhost:3000` gibt SvelteKit 403 "Cross-site POST form submissions are forbidden"
- **Evidence:** Playwright-Tests schlugen fehl bis ORIGIN gesetzt wurde
- **Impact:** Muss in Startup-Konfiguration dokumentiert werden

## Verdict: VERIFIED

### Begruendung

**VERIFIED** — Alle 17 Expected-Behavior-Punkte aus der Spec bestanden.

**Funktionalitaet vollstaendig:**
- **Dashboard:** 3 Stats-Cards (Trips, Locations, System Status) mit korrekten Counts und "Verwalten"-Links
- **Trips-Liste:** Tabelle mit Name, Etappen (Badge), Zeitraum, Aktionen — exakt wie in Spec definiert
- **CRUD komplett:** Create → Edit → Delete end-to-end verifiziert inkl. Bestaetigungsdialog
- **TripForm:** Verschachtelter Editor (Trip → Stages → Waypoints) mit dynamischem Hinzufuegen/Entfernen
- **Validierung:** Name-Pflicht, Stage-Pflicht, Waypoint-Pflicht — alle drei Regeln greifen
- **SSR:** Kein Loading-Spinner, Daten server-side gerendert

**Verbesserungen gegenueber vorherigem Validator-Lauf (BROKEN → VERIFIED):**
- Delete-Bestaetigungsdialog implementiert (war CRITICAL)
- Health/System Status Card hinzugefuegt
- Card-Layout durch Tabelle ersetzt
- Datumsbereich in Tabelle sichtbar
- Seiten-Duplizierung nach Save gefixt
- UI-Texte eingedeutscht ("Verwalten", "Bearbeiten", "Loeschen", "Neuer Trip", "Speichern", "Abbrechen")

**3 nicht-funktionale Findings** (LOW/MEDIUM) betreffen Lokalisierung und Deployment-Konfiguration, nicht die Kernfunktionalitaet.
