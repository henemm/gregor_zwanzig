# Spec: Neue Tour anlegen — Progressive Tab Editor (#622)

**Status:** Entwurf — Spec/Plan, noch kein Code (PO 2026-06-06)
**Issue:** #622 (`trip-new-progressive-editor`)
**Design-Quelle (verbindlich, 1:1):** `docs/design-requests/trip-anlegen-2026-06-06/` — `Gregor 20 - Trip anlegen.html`, `screen-trip-new-v2.jsx` (+ `-mobile`), `screen-trip-edit-v2-weather.jsx` (Roh/Einfach, kein Detail)
**Baut auf / wiederverwendet:** #587 (`WetterMetrikenTabV2`), #616 (Tab-IA), #617 (`TE2_ZeitplanTab`/`TE2_AlertsTab`), #585/#503 (`ScreenWaypointEditor` embedded). **Ersetzt** den 5-Schritt-Wizard (`screen-trip-wizard.jsx` → deprecated).

## Kernkonzept

**Kein separater Wizard.** „Neue Tour anlegen" ist der **Erstellen-Modus desselben Tab-Editors** wie „Trip bearbeiten" — mit **sequenziellem Freischalt-Zustand** (Tabs öffnen progressiv). Route `/trips/new`.

### Tab-Struktur (6 Tabs, Freischalt-Logik 1:1 aus `TN_unlocked`/`TN_doneSet`)

| # | Tab | Freischalt-Bedingung | Optional | „Done"-Bedingung |
|---|-----|----------------------|----------|------------------|
| 1 | Route | immer offen | nein | Name + Startdatum |
| 2 | Etappen & GPX | Name + Startdatum | nein | alle GPX geladen |
| 3 | Wegpunkte prüfen | alle GPX geladen | **ja** | — |
| 4 | Wetter-Metriken | alle GPX geladen | nein | Tab besucht |
| 5 | Briefing-Zeitplan | Wetter-Tab besucht | nein | Tab besucht |
| 6 | Alerts | Zeitplan-Tab besucht | nein | — |

Wegpunkte + Wetter schalten **gleichzeitig** frei (beide nach allen GPX). Gesperrter Tab-Klick → Flash + Tooltip „Gesperrt — <lockHint>". „Tour speichern" erst aktiv, wenn Zeitplan besucht (`done.has("zeitplan")`).

### Wichtige Datenmodell-Änderung
- **GPX pro Etappe** statt Gesamt-Trip-GPX. Jede Etappe hat ihre eigene `.gpx`.
- **Startdatum** (Pflicht) → Etappen-Datum = Startdatum + Index-Tage (auto, 1:1 `TN_stageDate`).

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet `/trips/new`, When die Seite lädt, Then erscheint der Tab-Editor (Sidebar + Breadcrumb „Trips / Neue Tour" + Hero „Neue Tour anlegen" + Fortschrittsbalken) mit 6 Tabs — **kein** mehrstufiger Wizard-Stepper.

**AC-2:** Given der Erstellen-Modus, When noch keine Vorbedingung erfüllt ist, Then sind nur erlaubte Tabs klickbar (Route offen, Rest gesperrt mit ⊘ + Tooltip), exakt nach der Freischalt-Logik der Tabelle; ein Klick auf einen gesperrten Tab wechselt NICHT, sondern zeigt den Flash/Tooltip.

**AC-3:** Given der Route-Tab, When der Nutzer Tour-Name + Startdatum ausfüllt, Then wird „Etappen anlegen →" aktiv, der Etappen-Tab schaltet frei, und die Hero-Überschrift zeigt den Namen (sonst „Noch kein Name"). Region ist optional (max 50). Datum-Feld ist `type=date`.

**AC-4:** Given der Etappen-&-GPX-Tab, When der Nutzer Etappen anlegt/benennt und **je Etappe eine GPX-Datei** hochlädt, Then zeigt jede Zeile T-Nummer · Name (inline editierbar) · Auto-Datum (Start + Index) · GPX-Slot · Entfernen; „X/Y GPX geladen" zählt korrekt; Wegpunkte + Wetter schalten erst frei, wenn **alle** Etappen eine GPX haben.

**AC-5:** Given alle GPX geladen, When der Nutzer fortfährt, Then kann er entweder „Wegpunkte prüfen →" (optionaler Tab mit eingebettetem `ScreenWaypointEditor embedded`) oder „Wetter direkt →" wählen; Wegpunkte ist überspringbar.

**AC-6:** Given die Tabs Wetter-Metriken, Briefing-Zeitplan und Alerts, When sie geöffnet werden, Then rendern sie **dieselben Komponenten** wie der Bearbeiten-Modus (`WetterMetrikenTabV2` mit Roh/Einfach ohne Detail, `TE2_ZeitplanTab`, `TE2_AlertsTab`); der im Wetter-Tab gesetzte Kanal-Zustand fließt in Zeitplan + Alerts (kein Signal — nur Email/Telegram/SMS).

**AC-7:** Given der Anlege-Flow ist vollständig (Zeitplan besucht), When der Nutzer „Tour speichern" klickt, Then wird eine Tour mit Name, Region, Startdatum, Etappen (Namen + Auto-Daten), Etappen-GPX, Wetter-Metrik-Konfig, Zeitplan und Alerts angelegt und persistiert (Read-Modify-Write, keine Daten gehen verloren); vorher ist „Tour speichern" deaktiviert mit Hinweis „Zeitplan einrichten zum Speichern".

**AC-8:** Given der alte Wizard, When der neue Flow live ist, Then ist `/trips/new` der Progressive-Tab-Editor und der alte 5-Schritt-Wizard (`screen-trip-wizard.jsx`-Pendant im Frontend) wird nicht mehr verwendet (deprecated/entfernt) — kein paralleler Anlege-Pfad (PO: „ein Trip-Pfad").

**AC-9 (Mobile):** Given ein Handy-Viewport, When `/trips/new` geöffnet wird, Then gilt volle Parität gemäß `screen-trip-new-v2-mobile.jsx`.

## Pixel-Fidelity
Inline-Styles 1:1 aus `screen-trip-new-v2.jsx` (nur `var(--g-*)`-Tokens). Playwright-Pixel-Diff gegen Soll-Bilder (`soll-trip-new-route-tab.png`, `-etappen-tab.png`, `-wegpunkte-tab.png`) als Hard-Gate.

## Abhängigkeiten & Risiken (PLAN-relevant)
- **Reuse-Abhängigkeit:** `WetterMetrikenTabV2`/`TE2_ZeitplanTab`/`TE2_AlertsTab` baut die Parallel-Session in #587 — #622 importiert sie, editiert sie nicht (Kollisionsrisiko gering, aber #587 muss stabil sein).
- **Backend (GPX pro Etappe):** Upload-Pfad + Persistenz „GPX je Etappe" statt Gesamt-Trip-GPX — vermutlich eigener Backend-Slice / Koordination nötig. **Vor Umsetzung Datenmodell prüfen** (`src/app/models.py`, Stage-GPX-Felder) — Daten-Schema-Pflicht.
- **Startdatum → Etappen-Datum:** existiert teils schon (#498 „Etappen-Datum bearbeitbar"); abgleichen.

## Out of Scope (mögliche Folge-Slices)
- Backend „GPX pro Etappe" (falls Modell es noch nicht trägt) → eigener Slice
- Löschen des alten Wizard-Codes (nach Verifikation)
- Naismith/Wegpunkt-Berechnung (bestehend, #503/#296)
