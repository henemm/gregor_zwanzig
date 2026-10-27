# Spec: Startseite-Cockpit (Epic #368 Phase 2, Screen 1/6 · Issue #386)

**Status:** Draft — wartet auf PO-Approval
**Created:** 2026-05-26
**Issue:** #386 (Epic #368 Phase 2)
**Design-Quelle:** `docs/design-requests/issue_15_atomic_design/spec/screen-home.jsx` + DELIVERY-NOTE
**Folge (vertagt):** #393 (Briefing-Versandstatus + Alarm-Historie)

## Zweck

Die Startseite (`/`, `frontend/src/routes/+page.svelte`) wird vom heutigen schlichten Kachel-Grid auf das **Cockpit-Layout** der Design-Vorlage migriert: aktive Trip als Hero mit heutiger Etappe, Höhenprofil und Etappen-Streifen; rechte Spalte mit Briefing-Zeitplan + Alarmen; nächste Etappe; Archiv. Komponiert wird ausschließlich aus der Phase-1-Atomic-Bibliothek.

## Scope-Abgrenzung

**In Scope (echte Daten):**
- Aktive-Trip-Erkennung + „Tag X von Y" aus Etappen-Daten (Helfer `tripStatus`/Aktiv-Logik aus `_home/TripKachel.svelte` in geteiltes Util `$lib/utils/tripStatus.ts` extrahieren).
- Hero: aktive Trip (Name, Region/Strecke, Profil-Pill, Live-Pill), heutige Etappe (Code, Titel, Zeitfenster aus `start_time`, km/↑/↓/max via Wegpunkt-Utils `fullProfile.ts`), `ElevSparkline` aus Wegpunkt-Höhen, Wetter-Zusammenfassung + Risk-Pill via `GET /api/trips/{id}/stages/weather`.
- Etappen-Streifen: `StagePill` je Etappe (`active`/`future`, vergangene `done`).
- Nächste Etappe (Folge-Etappe nach heute): `SectionH` + `ElevSparkline` + Wetter, analog Hero.
- Archiv-Karte: bis zu 4 abgeschlossene/archivierte Trips (`archived_at` gesetzt oder Enddatum < heute), als Karten-Grid.
- Briefing-Zeitplan-Karte („Was geht heute raus"): geplante Briefings aus `report_config` (morning/evening + aktive Kanäle) via `BriefingTimelineRow`, Status zunächst „geplant".
- CTAs: „Neuer Trip" → `/trips/new`, „Neuer Vergleich" → `/compare`.
- Leerzustand (keine Trips/Vergleiche): bestehender Leerzustand bzw. `EmptyState` (#314).

**Out of Scope (vertagt → #393, sauberer Leerzustand):**
- Briefing-**Versandstatus** (gesendet/geplant): keine Quelle → alle als „geplant" markiert, kein „gesendet"-Badge.
- Alarm-**Historie** („N ausgelöst, letzte 24 h"): keine Quelle → Karte zeigt Leerzustand („Keine Alarme in den letzten 24 h" bzw. Verweis auf konfigurierte Regeln). Kein Fake-Wert.

**Nicht berührt:** App-Shell (Sidebar/Topbar/TopoBg) — die ist Layout (`+layout.svelte`), nicht Seite. Backend/Go unverändert.

## Datenquellen

| Cockpit-Element | Quelle | Status |
|---|---|---|
| Aktive Trip, Tag X/Y, Etappen-Status | `trips[].stages[].date` vs. heute | vorhanden |
| km / ↑ / ↓ / max / Profil-Array | `stages[].waypoints[].elevation_m` via `fullProfile.ts` | vorhanden |
| Zeitfenster | `stages[].start_time` | vorhanden |
| Wetter-Summary + Risk | `GET /api/trips/{id}/stages/weather` (StagesWeatherResponse) | vorhanden (Loader-Fetch für aktive Trip ergänzen) |
| Briefing-Zeitplan + Kanäle | `trips[].report_config` | vorhanden |
| Archiv | `trips[]` mit `archived_at` / Enddatum < heute | vorhanden |
| Briefing-Versandstatus | — | **vertagt #393** |
| Alarm-Historie | — | **vertagt #393** |

## Acceptance Criteria

**AC-1:** Given eine Trip, deren Etappen-Zeitraum „heute" einschließt, When die Startseite geladen wird, Then erscheint diese Trip als Hero-Karte mit Live-Pill „Tag X von Y" (X = Index der heutigen Etappe ab 1, Y = Etappenzahl) und Akzent-Randstreifen links.

**AC-2:** Given die aktive Trip hat eine heutige Etappe mit Wegpunkten, When die Hero-Karte rendert, Then zeigt sie Etappen-Code, Titel, Zeitfenster, km/↑/↓/max und ein `ElevSparkline` aus den Wegpunkt-Höhen; fehlen Wegpunkte, entfällt das Sparkline ohne Fehler.

**AC-3:** Given der Wetter-Endpoint liefert für die heutige Etappe Risk + Summary, When die Hero-Karte rendert, Then zeigt sie eine Risk-Pill (`good`/`warn`/`bad` je Risk-Stufe) und den Summary-Text; liefert der Endpoint nichts (Fehler/leer), Then rendert die Karte ohne Risk-Pill/Summary statt eines Fehlers.

**AC-4:** Given eine Trip mit N Etappen, When der Etappen-Streifen rendert, Then erscheint je Etappe eine `StagePill` mit Zustand `done` (Datum < heute), `active` (heute) oder `future` (Datum > heute).

**AC-5:** Given `report_config` mit aktivierten Morgen-/Abend-Briefings, When die „Was geht heute raus"-Karte rendert, Then erscheint je aktiviertem Briefing eine `BriefingTimelineRow` mit Uhrzeit + aktiven Kanälen und Status „geplant" (kein „gesendet"-Badge — vertagt #393).

**AC-6:** Given keine Alarm-Historie verfügbar, When die Alarm-Karte rendert, Then zeigt sie einen sauberen Leerzustand (kein erfundener Zähler, keine Fehlermeldung).

**AC-7:** Given abgeschlossene/archivierte Trips existieren, When die Archiv-Karte rendert, Then erscheinen bis zu 4 davon als Karten (Zeitraum, Name, Etappenzahl) mit Link; existiert keine, entfällt die Archiv-Karte.

**AC-8:** Given weder Trips noch Vergleiche, When die Startseite lädt, Then erscheint der Leerzustand (kein leeres Cockpit-Gerüst) und die beiden CTAs bleiben erreichbar.

**AC-9:** Given die migrierte Seite, When `svelte-check` und `contrast-audit.test.ts` laufen, Then sind beide grün; alle Farb-/Surface-Tokens sind die Sandbox-Namen **verbatim aus `screen-home.jsx`** (`--g-card`, `--g-paper`, `--g-ink-*`, `--g-accent*`, `--g-rule*`, `--g-r-*`) — keine Hex-Literale, kein Rename.

**AC-10:** Given die bestehende Route, When migriert, Then bricht nichts: `/` lädt mit `200`, keine Console-Errors, der Loader liefert weiterhin `trips`+`subscriptions` (additiv um den Wetter-Fetch der aktiven Trip erweitert), bestehende Links funktionieren.

**AC-11:** Given Trips existieren, aber **keine ist heute aktiv** (alle geplant/zukünftig oder abgeschlossen), When die Startseite lädt, Then zeigt der Hero die **nächste anstehende** Trip (frühestes Etappen-Startdatum ≥ heute) mit Label „Nächste Trip" statt „Live"; sind alle abgeschlossen, entfällt der Hero und es bleiben Archiv + (sofern vorhanden) Vergleiche/CTAs.

**AC-12 (Rückwärtskompatibilität):** Given weitere (nicht im Hero gezeigte) Trips und/oder Orts-Vergleiche existieren, When die Startseite rendert, Then bleiben diese unterhalb des Cockpits erreichbar — kompakte Abschnitte „Weitere Trips" (`TripKachel`, ohne die Hero-Trip) und „Orts-Vergleiche" (`CompareKachel`). Es geht **kein** heute sichtbarer Zugang verloren (additiv zum Cockpit; die Design-Vorlage ist ein Einzel-Trip-Mock und deckt diese Fälle nicht ab).

## Komponenten-Disziplin (DELIVERY-NOTE §1)

- Keine Inline-Atome/-Molecules neu definieren — Phase-1-Bibliothek nutzen: `Card`, `Pill`, `Dot`, `Eyebrow`, `Btn`, `StagePill`, `ElevSparkline`, `SectionH`, `BriefingTimelineRow`, `AlertRow`.
- Page-lokale Komposita erlaubt (Archiv-Kachel, Hero-Komposition) — aber nur als Komposition aus Bibliotheks-Bausteinen.
- Token-Namen 1:1 wie in der JSX (Bridge #369 löst auf).

## Tests (mock-frei)

> **Erweitert durch `docs/specs/_archive/modules/fix_1271_status_zeitformat.md` (2026-07-16):** `tripStatus()` ist inzwischen Thin-Wrapper um die kanonische `deriveTripStatus()` (6 Zustände inkl. `pausiert`), nicht mehr eigene Datumsableitung. Zeile unten (aktiv/geplant/fertig/draft) ist um `pausiert` zu ergänzen — historischer Stand.

- Unit: `tripStatus.ts`-Util (aktiv/geplant/fertig/draft + heutige Etappen-Index) — reine Funktion, node:test.
- Component/Integration: Startseite rendert für (a) aktive Trip mit Wetter, (b) nur geplante Trips, (c) leer — gegen echte Loader-Datenform (Fixtures aus echten Trip-DTOs, keine `Mock()`).
- E2E (Post-Push, Staging): `/` rendert, Hero + Etappen-Streifen sichtbar, keine Console-Errors (Playwright).

## Risiken

- Wetter-Fetch im Home-Loader erhöht Ladezeit → nur für **eine** (aktive) Trip fetchen, nicht alle; bei Fehler fail-soft (Hero ohne Wetter).
- LoC: Cockpit-Redesign überschreitet vermutlich das 250-Limit → `loc_limit_override` setzen.
