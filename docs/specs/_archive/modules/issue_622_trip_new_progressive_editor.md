# Spec: Neue Tour anlegen — Progressive Tab Editor (#622)

**Status:** Freigegeben für Umsetzung — **Desktop-Scope** (PO 2026-06-07). Blocker #587/#616/#617 sind live.
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

### Persistenz-Architektur (festgelegt 2026-06-07)
Die verbindliche JSX (`screen-trip-new-v2.jsx`) hält **allen Anlege-State lokal** (eigene
`useState` pro Tab, GPX gemockt, **kein** inkrementelles Speichern) und persistiert **einmal am
Ende** per `POST /api/trips`. → Der Anlege-Flow nutzt **„lokaler State im Shell + ein POST am
Schluss"** (wie der alte `WizardState`), **nicht** das inkrementelle PUT-Muster des Edit-Flows.

**Konsequenz für die Wiederverwendung (AC-6):** Die Edit-Tabs unterscheiden sich im Create-Reifegrad:
| Komponente | Create-tauglich? | Anpassung |
|---|---|---|
| `EditReportConfigSection` (Zeitplan) | ✅ hat `mode='create'`, bindable | keine |
| `AlertRulesEditor` | ✅ bindable `rules` | keine |
| `WeatherMetricsTab` | ⚠️ PUT auf `/api/trips/{id}/weather-config` | **Create-Modus:** Config per Binding/`onChange` emittieren statt PUT; zusätzlich `onChannelsChange`-Output für Kanal-Weitergabe |
| `EditStagesPanelNew` | ⚠️ PUT auf `/api/trips/{id}` | **Create-Modus:** Etappen/GPX nur per Binding halten, kein PUT; im Anlege-Flow ggf. schlankerer Etappen-Tab nach JSX statt voller Editor |

Anpassungen an geteilten Edit-Komponenten erfolgen **additiv** (neue optionale Props, Default =
bisheriges Edit-Verhalten) — kein Bruch des Edit-Flows. **Backend: kein Schema-Change** nötig
(`POST /api/trips` existiert; GPX wird über `/api/gpx/parse?stage_date=` pro Etappe geparst →
`stage.Waypoints`).

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet `/trips/new`, When die Seite lädt, Then erscheint der Tab-Editor (Sidebar + Breadcrumb „Trips / Neue Tour" + Hero „Neue Tour anlegen" + Fortschrittsbalken) mit 6 Tabs — **kein** mehrstufiger Wizard-Stepper.

**AC-2:** Given der Erstellen-Modus, When noch keine Vorbedingung erfüllt ist, Then sind nur erlaubte Tabs klickbar (Route offen, Rest gesperrt mit ⊘ + Tooltip), exakt nach der Freischalt-Logik der Tabelle; ein Klick auf einen gesperrten Tab wechselt NICHT, sondern zeigt den Flash/Tooltip.

**AC-3:** Given der Route-Tab, When der Nutzer Tour-Name + Startdatum ausfüllt, Then wird „Etappen anlegen →" aktiv, der Etappen-Tab schaltet frei, und die Hero-Überschrift zeigt den Namen (sonst „Noch kein Name"). Region ist optional (max 50). Datum-Feld ist `type=date`.

**AC-4:** Given der Etappen-&-GPX-Tab, When der Nutzer Etappen anlegt/benennt und **je Etappe eine GPX-Datei** hochlädt, Then zeigt jede Zeile T-Nummer · Name (inline editierbar) · Auto-Datum (Start + Index) · GPX-Slot · Entfernen; „X/Y GPX geladen" zählt korrekt; Wegpunkte + Wetter schalten erst frei, wenn **alle** Etappen eine GPX haben.

**AC-5:** Given alle GPX geladen, When der Nutzer fortfährt, Then kann er entweder „Wegpunkte prüfen →" (optionaler Tab mit eingebettetem `ScreenWaypointEditor embedded`) oder „Wetter direkt →" wählen; Wegpunkte ist überspringbar.

**AC-6:** Given die Tabs Wetter-Metriken, Briefing-Zeitplan und Alerts, When sie geöffnet werden, Then rendern sie **dieselben Komponenten** wie der Bearbeiten-Modus (`WetterMetrikenTabV2` mit Roh/Einfach ohne Detail, `TE2_ZeitplanTab`, `TE2_AlertsTab`); der im Wetter-Tab gesetzte Kanal-Zustand fließt in Zeitplan + Alerts (kein Signal — nur Email/Telegram/SMS).

**AC-7:** Given der Anlege-Flow ist vollständig (Zeitplan besucht), When der Nutzer „Tour speichern" klickt, Then wird eine Tour mit Name, Region, Startdatum, Etappen (Namen + Auto-Daten), Etappen-GPX, Wetter-Metrik-Konfig, Zeitplan und Alerts angelegt und persistiert (Read-Modify-Write, keine Daten gehen verloren); vorher ist „Tour speichern" deaktiviert mit Hinweis „Zeitplan einrichten zum Speichern".

**AC-8:** Given der alte Wizard, When der neue Flow live ist, Then ist `/trips/new` der Progressive-Tab-Editor und der alte 5-Schritt-Wizard (`screen-trip-wizard.jsx`-Pendant im Frontend) wird nicht mehr verwendet (deprecated/entfernt) — kein paralleler Anlege-Pfad (PO: „ein Trip-Pfad").

**AC-9 (Mobile) — ✅ LIVE (2026-06-08, Issue #661):** Mobile-Parität gemäß `screen-trip-new-v2-mobile.jsx`.
Der ursprüngliche Issue-Text stufte Mobile-Adaption als „V1.5 / Out of Scope" ein → eigenes Folge-Issue.
Slice 3 (Issue #661) implementierte responsive Layout @ 899px Breakpoint (CSS-only). Alle 9 ACs des #622-Pakets sind nun abgeschlossen.

## Slice-Plan (Desktop + Mobile)

Wegen 250-LoC-Workflow-Grenze in drei Slices:

- **Slice 1 ✅ LIVE (11edbfe7, 2026-06-07):** Editor-Shell + Lock-/Done-State (`TN_unlocked`/`TN_doneSet`) +
  TabBar (Flash/Tooltip) + Fortschrittsbalken + **Route-Tab** + **Etappen-&-GPX-Tab** (Create-Modus,
  lokaler State, Auto-Datum) + **Reuse-Tabs** Wetter/Zeitplan/Alerts im Create-Modus (Kanal-Binding)
  + **Speichern** (`POST /api/trips`) + alter Wizard deprecated. → AC-1, 2, 3, 4, 6, 7, 8.
- **Slice 2 ✅ LIVE (2026-06-08, Issue #658):** Optionaler **Wegpunkte-Tab** (`EditStagesPanelNew embedded`, AC-5)
  + Persistenz der aus GPX berechneten (ggf. editierten) Wegpunkte im `POST /api/trips`-Payload. → AC-5.
- **Slice 3 ✅ LIVE (2026-06-08, Issue #661):** **Mobile-Parität** (≤899px, CSS-only responsive Layout)
  + App-Leiste statt Breadcrumb + Floating-CTAs + vertikale Karten + Bottom-Sheet-Etappennamen
  + Touch-bedienbare TabBar → AC-9.

**#622-Paket komplett: Alle 9 ACs (Desktop + Mobile) abgeschlossen.**

## Pixel-Fidelity
Inline-Styles 1:1 aus `screen-trip-new-v2.jsx` (nur `var(--g-*)`-Tokens). Playwright-Pixel-Diff gegen Soll-Bilder (`soll-trip-new-route-tab.png`, `-etappen-tab.png`, `-wegpunkte-tab.png`) als Hard-Gate.

## Abhängigkeiten & Risiken (PLAN-relevant)
- **Reuse-Abhängigkeit:** `WetterMetrikenTabV2`/`TE2_ZeitplanTab`/`TE2_AlertsTab` baut die Parallel-Session in #587 — #622 importiert sie, editiert sie nicht (Kollisionsrisiko gering, aber #587 muss stabil sein).
- **Backend (GPX pro Etappe): GEKLÄRT — kein Schema-Change.** `POST /api/trips` existiert; GPX wird heute schon pro Etappe über `/api/gpx/parse?stage_date=&start_hour=` geparst → abgeleitete `stage.Waypoints`. Go-`Stage` trägt kein rohes GPX-Feld (nur `Waypoints`) und braucht keins.
- **Startdatum → Etappen-Datum:** existiert teils schon (#498 „Etappen-Datum bearbeitbar"); abgleichen.

## Out of Scope (mögliche Folge-Slices)
- Backend „GPX pro Etappe" (falls Modell es noch nicht trägt) → eigener Slice
- Löschen des alten Wizard-Codes (nach Verifikation)
- Naismith/Wegpunkt-Berechnung (bestehend, #503/#296)
