# Context: feat-3305-tabelle-trip-anlegen

## Request Summary
Issue #3305 (Teil B von #3041, Epic #3122): Beim Trip-Anlegen steht im Schritt „Wetter" dieselbe Tabelle „Was steht wo" samt Schaltern wie im Reiter Wetter (derselbe Code). Ihre Angaben (placements + Schalterfelder) gehen mit dem einen Anlege-POST mit; danach zeigt der Reiter Wetter genau das Eingestellte.

Grundanalyse des Gesamtvorhabens: `docs/context/feat-3041-tabelle-beim-anlegen.md` (Schnitt A–D, Befunde für B). Teil A (#3304) ist live: `POST /api/briefings/placements/vorschau?kind=` (Entwurf im Körper, Antwort = GET-Ansicht, `stored=false`, schreibt nichts; Entwurf ohne id bekommt Platzhalter-Kennung).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | Karte; Props `context`, `id` (Pflicht), `saveController`, `enqueueHubWrite`, `onUebernahme`; lädt GET `/api/briefings/{id}/placements`. `grundauswahlGeaendert` (Z.151) und `placementsZumMitspeichern` (Z.162) brechen bei `!antwort.stored` ab → Anlege-Modus braucht eigenen Pfad (Vorschau-POST, Stand immer melden) |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` | `erstelleTabellenSpeicherung` (PUT + If-Match, `zumMitsenden(tabelleGespeichert)` Z.122), `felderNutzlast`/`erstelleFelderSpeicherung` (Trip: `report_config.{show_stage_stats, show_yesterday_comparison, email_format, telegram_style}`, `display_config.show_night_block`) |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts`, `wasStehtWoAnsicht.ts` | reine Zustands-/Ansichtsfunktionen, unverändert nutzbar (Vorschau-Antwort hat GET-Form) |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Karte nur bei `{#if !createMode && aboId}` (Z.313); Anlege-Rückkanal `onAnlegeStand` über `anlegeSpeicherer` (Z.103/108) |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts` | `anlegeSpeicherer`; Reiter trägt `placements` beim Speichern mit |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | `wetterAnlegeTrip` (Z.471, Entwurf für die Vorschau), `handleWetterAnlegeStand` (Z.480) verwirft placements/Schalter; POST über `buildCreateTripPayload` (Z.557); Alt-Panel Z.919/1176 bleibt bis Teil D |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | `buildCreateTripPayload` (Z.275): kein `placements`, kein `show_night_block`, Schalter-`report_config`-Felder prüfen |
| `api/routers/placements.py:53`, `src/services/placements_view_service.py` | Vorschau-Endpunkt (Teil A), fertig |
| `internal/router/router.go:392`, `internal/handler/placements.go` | Go-Proxy Vorschau; `anlageTabelle` übernimmt mitgeschickte `display_config.placements.rows` unverändert beim POST |
| `internal/handler/trip.go` (POST) | Trip-Anlage ruft `anlageTabelle` |

## Existing Patterns
- Anlege-Modus = `createMode` + `onAnlegeStand` (Stand nach oben statt PUT), bereits im Wetter-Reiter etabliert → Karte bekommt dasselbe Muster, kein Autosave.
- Code-Teilung über `context="route"|"vergleich"` (Gate #1170): keine neue Komponente, Karte selbst erweitern; Orte-Anbindung folgt in #3306 mit demselben Code.
- Go-Anlage mit mitgeschickten rows: kein Kern-Aufruf (`TestAnlage3237MitgeschickteTabelleBleibtOhneKernAufruf`) → Server-Seite steht.

## Dependencies
- Upstream: Vorschau-Endpunkt (#3304, live), `/api/auth/profile` (Telegram-Status in der Karte).
- Downstream: Anlege-POST Trip, E2E `hub-anlegen-ablauf.spec.ts` (AN-6: genau ein POST, Körper geprüft), Wächterliste `src/lib/__tests__/bausteine_waechter_regeln.ts`, Trip-new-Tests (`p11_neuanlage_payload_fixture`, `standardwerte_payload_paritaet_trip`).

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` (Anlegen kommt mit #3041), `feat_3237_altpfad_entfernen.md`, `feat_3304_*` (Vorschau, falls vorhanden), Anlegen: `rework_2837_s2_anlege_rahmen.md`, `feat_2277_s4_anlege_lockengine.md`; ADR-0124.

## Risks & Considerations
- Datenverlust (Warnung PR #3042): Karte nie zeigen, ohne dass ihr Stand in den POST geht; im Anlege-Modus Stand unabhängig von `stored` melden.
- Metrik-Änderung im Schritt Wetter → Vorschau neu laden (entprellt), bestehende Haken/Formate/Reihenfolge per `grundauswahlGeaendert`-Logik erhalten; Sequenznummer gegen späte Antworten.
- Genau ein POST; keine PUTs/Autosave beim Anlegen (Karte ohne id/saveController).
- Rows werden von Go ungeprüft übernommen (wie PUT, ADR-0077) — keine neue Lücke.
- Zwei-Nutzer-Test: Vorschau nutzt Orte/Daten nur des angemeldeten Nutzers; Anlage landet beim richtigen Nutzer.
- Rückweg-Prüfung: nach Anlage zeigt der Reiter Wetter dieselben placements/Schalter (E2E).

## Analysis

### Type
Feature (Teil B von #3041)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts | MODIFY | Anlege-Variante der Tabellen-Speicherung: `POST /api/briefings/placements/vorschau?kind=route` mit Entwurf (inkl. lokalem `display_config.placements`), Ticket-Sequenz `nr/version` wiederverwendet, kein PUT/schedule, `zumMitsenden` ohne `stored`-Bedingung, Vorschau entprellt (~400 ms, eigener Timer, kein saveController) |
| frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte | MODIFY | Props `createMode`, `entwurf: () => Trip`, `start` (Stand nach Remount), `onAnlegeStand`; `stored`-Abbrüche (Z.151/162) im Anlege-Modus aufheben; `feld()` ohne `erstelleFelderSpeicherung`, meldet Stand; Antwort-Übernahme ersetzt im Anlege-Modus nur Ansicht (Beispielwerte), nicht `lokal` |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | MODIFY | Gate Z.313 → `{#if createMode \|\| aboId}`; Entwurf/Start/Rückkanal `onAnlegeKarte` durchreichen; Vorschau-Nachladen nur bei Änderung der Metrik-Signatur |
| frontend/src/lib/components/trip-new/TripNewEditor.svelte | MODIFY | `$state karteStand` (überlebt Remount Desktop/Mobil und `{#key wetterNeuaufbau}`), Handler, Übergabe an `buildCreateTripPayload`; Wächter: Bestand darf nicht steigen → Logik in tripNewLogic.ts |
| frontend/src/lib/components/trip-new/tripNewLogic.ts | MODIFY | `CreateTripState.karte?` ; Merge nur wenn gesetzt: `display_config.placements`, Schalter-Diff über `felderNutzlast('route', neu, start)` in `display_config`/`report_config` (Versandzeiten/Kanäle unberührt) |
| Tests (node --test) | CREATE/MODIFY | Speicherung Anlege-Variante (kein PUT, späte Antwort nach Klick und nach Metrikwechsel verworfen), Karte Anlege-Modus (Stand ohne `stored` gemeldet, Haken bleiben nach Metrikwechsel), Payload-Merge, `anlegen_ohne_autosave`, Fixtures p11/standardwerte ohne Karte unverändert |
| frontend/e2e/hub-anlegen-ablauf.spec.ts (+ Helfer) | MODIFY | Karte im Schritt Wetter sichtbar, Haken/Schalter ändern, genau ein POST mit placements+Schaltern, kein PUT; Reiter Wetter zeigt danach dasselbe; zweiter Nutzer sieht nichts |

### Scope Assessment
- Files: 5 Produktion + ~5 Tests
- Estimated LoC: +130…160 Produktion (unter Limit), Tests +250…350
- Risk Level: MEDIUM (Datenverlust bei falscher `stored`-Behandlung, Effekt-Schleife, Remount)

### Technical Approach
Ein Anlege-Zweig in derselben Karte/Speicherung (Gate #1170), Stand liegt im TripNewEditor (Remount-fest), eigener Rückkanal der Karte (nicht über `handleWetterAnlegeStand`, der nur bei Metrikänderung meldet). Vorschau-Nachladen hängt ausschließlich an der Metrik-Signatur (JSON-Vergleich, `untrack`); `karteStand` fließt nie in `wetterAnlegeTrip` zurück (Schleifenschutz, vgl. #1775). Späte Antworten über Ticket-Version verworfen; lokale Haken/Formate/Reihenfolge werden bei Übernahme nicht überschrieben, neue Metriken kommen über `grundauswahlGeaendert`/Server-Ergänzung fehlender rows. Merge erst beim POST: wer die Karte nie bedient, sendet wie heute keine rows (Server baut sie aus der Grundauswahl).

### Tech-Lead-Entscheidungen
- `kind=route` (nicht `trip`) für die Vorschau — so akzeptiert der Server.
- `email_format`/`telegram_style` haben auf der Anlegeseite bis #3307 zwei Bedienstellen (Karte + Zustellung). Regel: Karte startet aus `reportConfig` des Entwurfs; beim POST wird nur angewandt, was in der Karte gegenüber ihrem Start geändert wurde (Diff via `felderNutzlast`, Parität zum Reiter-PUT). Keine Produktfrage — vorübergehend, entfällt mit #3307.
- Kein Split: ein Workflow.

### Dependencies
- Upstream: Vorschau-Endpunkt #3304 (live), Go `anlageTabelle` übernimmt mitgeschickte rows unverändert, `CreateTripHandler` übernimmt `display_config`/`report_config` roh (show_night_block opak).
- Downstream: Orte-Anbindung #3306 nutzt denselben Anlege-Zweig (`context="vergleich"`), #3307 entfernt Alt-Panel.

### Open Questions
- keine (Anlegen = Bearbeiten ist PO-Vorgabe)
