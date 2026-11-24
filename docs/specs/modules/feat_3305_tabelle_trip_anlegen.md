---
entity_id: feat_3305_tabelle_trip_anlegen
type: module
created: 2026-11-24
updated: 2026-11-24
status: approved
version: "1.0"
workflow: feat-3305-tabelle-trip-anlegen
tags: [was-steht-wo, placements, anlegen, trip, epic-3122]
---

# Tabelle „Was steht wo“ beim Trip-Anlegen (#3305)

## Approval

- [x] Approved (automatisch, Ampel grün, 2026-11-24)

## Purpose

Beim Anlegen eines Trips zeigt der Schritt „Wetter“ dieselbe Tabelle „Was steht wo“ samt Schaltern darunter wie der Reiter Wetter eines gespeicherten Trips (derselbe Code, Anlegen = Bearbeiten, PO-Vorgabe). Die Karte lädt über den Vorschau-Weg aus #3304, meldet ihren Stand nach oben statt zu speichern, und der eine Anlege-POST trägt Tabelle und Schalter mit. Teil B von #3041 (Epic #3122); Orte (#3306) und Alt-Panel/Zustellung (#3307) sind nicht Teil dieser Spec.

## Source

- **File:** `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte`, `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts`, `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte`, `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `frontend/src/lib/components/trip-new/tripNewLogic.ts`
- **Identifier:** `WasStehtWoKarte` (Anlege-Modus), `erstelleTabellenSpeicherung` (Anlege-Variante), `buildCreateTripPayload` (Feld `karte`), `karteStand` (neu in `TripNewEditor`)

> **Schicht-Hinweis:** Ausschließlich Frontend (SvelteKit, `frontend/src/...`). Go-API (`anlageTabelle` übernimmt mitgeschickte `display_config.placements.rows` unverändert, `CreateTripHandler` übernimmt `display_config`/`report_config` roh) und Python-Vorschau (#3304) sind fertig und bleiben unverändert.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Keine neue Komponente. Die vorhandene `WasStehtWoKarte` und `wasStehtWoSpeicherung.ts` bekommen einen Anlege-Zweig; `context="route"` jetzt, `"vergleich"` folgt in #3306 über denselben Zweig (Gate #1170).
> - **Mandantentrennung:** Die Vorschau läuft mit der Anmeldung des Nutzers (Go setzt `user_id`); der Anlege-POST ordnet den Trip dem angemeldeten Nutzer zu. Test mit zwei verschiedenen Nutzern, nie `"default"`.
> - **Kanäle:** Die Karte zeigt E-Mail, Telegram, SMS und Premium-SMS mit demselben Inhalt wie im Reiter Wetter; kein Kanal wird ersetzt. Versandzeiten und Kanalwahl bleiben unberührt.

## Estimated Scope

- **LoC:** Produktion ca. +130 bis +160, Tests ca. +250 bis +350
- **Files:** 5 Produktionsdateien + ca. 5 Testdateien
- **Effort:** medium (Risiko MEDIUM: Datenverlust bei falscher `stored`-Behandlung, Effekt-Schleife, Neuaufbau der Ansicht)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` | MODIFY | Anlege-Variante der Tabellen-Speicherung: `POST /api/briefings/placements/vorschau?kind=route` mit Entwurf inklusive lokalem `display_config.placements`; Ticket-Sequenz (`nr/version`) wiederverwendet; kein PUT, kein Planen eines Speicherns; `zumMitsenden` ohne `stored`-Bedingung; Vorschau entprellt (ca. 400 ms, eigener Zeitgeber) |
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | MODIFY | Props `createMode`, `entwurf`, `start`, `onAnlegeStand`; die `stored`-Abbrüche in `grundauswahlGeaendert` und `placementsZumMitspeichern` entfallen im Anlege-Modus; Schalter melden Stand statt `erstelleFelderSpeicherung`; Antwort-Übernahme ersetzt nur die Ansicht (Beispielwerte), nicht den lokalen Stand |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | Karte auch bei `createMode` (Bedingung `createMode \|\| aboId`); Entwurf, Start und Rückkanal durchreichen; Vorschau nur bei Änderung der Metrik-Signatur nachladen |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | `karteStand` als `$state` im Editor (überlebt Wechsel Desktop/Mobil und Neuaufbau der Ansicht); Handler; Übergabe an `buildCreateTripPayload`; Stand fließt nie in `wetterAnlegeTrip` zurück |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | `CreateTripState.karte?`; nur wenn gesetzt: `display_config.placements` und Schalter-Differenz (`felderNutzlast('route', neu, start)`) in `display_config.show_night_block` und `report_config.{show_stage_stats, show_yesterday_comparison, email_format, telegram_style}`; Versandzeiten und Kanäle unberührt |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/` (node --test) | CREATE/MODIFY | Speicherung Anlege-Variante, Karte im Anlege-Modus, Payload-Merge, `anlegen_ohne_autosave`; Fixtures `p11_neuanlage_payload_fixture` und `standardwerte_payload_paritaet_trip` ohne Karte unverändert |
| `frontend/e2e/hub-anlegen-ablauf.spec.ts` (+ Helfer) | MODIFY | Karte im Schritt Wetter, Änderungen, genau ein POST, Rückweg Reiter Wetter, zweiter Nutzer |

### Nicht in dieser Spec

- Orte-Anbindung (`context="vergleich"`): **#3306**.
- `ZustellungTab` im Anlege-Modus und Entfernen von `WetterMetrikenVersandPanel`: **#3307**.
- Änderungen an Vorschau-Endpunkt, Go-Anlage, GET/PUT-Weg oder Gate-Konfiguration.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/briefings/placements/vorschau?kind=route` (#3304) | API | Liefert die Ansicht für den noch nicht gespeicherten Entwurf, `stored=false`, schreibt nichts |
| `wasStehtWoStand.ts`, `wasStehtWoAnsicht.ts` | Frontend | Reine Zustands- und Ansichtsfunktionen, unverändert nutzbar |
| `felderNutzlast` / `erstelleFelderSpeicherung` (`wasStehtWoSpeicherung.ts`) | Frontend | Schalter-Differenz zum Start, Parität zum Reiter-PUT |
| `anlageTabelle` (Go, `internal/handler/placements.go`) | Go | Übernimmt mitgeschickte `rows` unverändert, kein Kern-Aufruf |
| `/api/auth/profile` | API | Telegram-Status in der Karte |
| `feat_3122_was_steht_wo`, `feat_3304_was_steht_wo_vorschau`, `feat_3237_altpfad_entfernen` | Spec | Antwortform, Vorschau, Erstanlage-Regel |
| ADR-0124, ADR-0077 | ADR | Tabelle als einzige Quelle; Zeilen werden wie beim PUT ungeprüft übernommen |

## Implementation Details

**Anlege-Zweig statt neuer Komponente.** Die Karte bekommt `createMode`. Im Anlege-Modus hat sie keine Kennung und keinen `saveController`: sie lädt über den Vorschau-Weg, hält ihren Stand lokal und meldet ihn über `onAnlegeStand` an den Editor. Es gibt weder PUT noch Autosave.

**Stand immer melden (Datenverlust-Schutz, Warnung PR #3042).** Die Abbrüche bei `!antwort.stored` gelten nur für den gespeicherten Weg. Im Anlege-Modus ist `stored` immer `false`; dort wird der Stand trotzdem gemeldet und beim POST mitgesendet. Die Karte wird nie angezeigt, ohne dass ihr Stand in den POST gelangt.

**Stand im Editor.** `karteStand` liegt im `TripNewEditor`, damit er den Wechsel zwischen Desktop- und Mobil-Ansicht und den Neuaufbau (`{#key wetterNeuaufbau}`) übersteht; die Karte startet aus diesem Stand. Eigener Rückkanal der Karte, nicht über `handleWetterAnlegeStand`, der nur bei Metrikänderung meldet.

**Metrikänderung.** Das Nachladen der Vorschau hängt ausschließlich an der Metrik-Signatur (JSON-Vergleich, `untrack`). `karteStand` fließt nie in `wetterAnlegeTrip` zurück (Schleifenschutz, vgl. #1775). Bestehende Haken, Formate und Reihenfolge bleiben über die `grundauswahlGeaendert`-Logik erhalten; neue Metriken kommen als Zeilen hinzu, entfernte entfallen. Späte Antworten verwirft die Ticket-Version (`nr/version`), auch nach Klick und nach Metrikwechsel.

**Payload.** `buildCreateTripPayload` mischt erst beim POST und nur, wenn `karte` gesetzt ist: wer die Karte nie bedient, sendet wie heute keine `rows` (der Server baut sie aus der Grundauswahl). Schalter werden als Differenz zum Start der Karte angewandt.

**Zwei Bedienstellen bis #3307.** `email_format` und `telegram_style` stehen auf der Anlegeseite vorübergehend an zwei Stellen (Karte und Zustellung). Regel: die Karte startet aus `reportConfig` des Entwurfs; beim POST wird nur angewandt, was in der Karte gegenüber ihrem Start geändert wurde. Entfällt mit #3307.

**Vorschau-Art.** `kind=route` (nicht `trip`), so akzeptiert der Server.

## Expected Behavior

- **Input:** Nutzer legt einen Trip an, wählt Metriken im Schritt Wetter, stellt in der Karte Haken, Formate, Reihenfolge und Schalter ein und legt den Trip an.
- **Output:** Genau ein `POST /api/trips` mit `display_config.placements` und den Schalterfeldern; der Reiter Wetter des neuen Trips zeigt genau das Eingestellte.
- **Side effects:** Nur lesende Vorschau-Aufrufe während des Anlegens; kein PUT, kein Speichern vor dem Anlegen.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer im Anlegen eines neuen Trips / When er den Schritt Wetter öffnet, in der Mobil- und in der Desktop-Ansicht / Then ist die Tabelle „Was steht wo“ mit den Schaltern darunter sichtbar, und ihr Stand (Haken, Formate, Reihenfolge, Schalter) bleibt beim Wechsel zwischen Mobil und Desktop und beim Weiter- und Zurückgehen der Schritte erhalten.
  - Test: E2E in beiden Ansichten: Karte erscheint, Haken setzen, Ansicht wechseln und Schritte wechseln, Haken ist weiterhin gesetzt.

- **AC-2:** Given die Karte im Anlegen ist geöffnet / When der Nutzer einen Haken, ein Format oder die Reihenfolge ändert und den Trip anlegt / Then enthält der eine Anlege-POST diese Änderung in `display_config.placements` (Zeilen in der eingestellten Reihenfolge, Haken und Formate wie gesetzt).
  - Test: E2E zeichnet den POST-Körper auf und prüft `display_config.placements.rows`; Unit-Test `buildCreateTripPayload` mit gesetztem `karte`.

- **AC-3:** Given die Karte im Anlegen ist geöffnet / When der Nutzer Nacht-Block, Etappen-Statistik, Vortagesvergleich, Mail-Format und Telegram-Kurzstil ändert und den Trip anlegt / Then stehen diese Werte im POST (`display_config.show_night_block`, `report_config.show_stage_stats`, `show_yesterday_comparison`, `email_format`, `telegram_style`), und Versandzeiten sowie Kanalwahl bleiben genau so, wie sie ohne Bedienung der Karte wären.
  - Test: E2E und Unit-Test vergleichen den POST-Körper mit und ohne Kartenbedienung: nur die geänderten Schalterfelder weichen ab, Versandzeiten und Kanäle sind gleich.

- **AC-4:** Given der Nutzer bedient die Karte im Anlegen / When er mehrere Änderungen macht und den Trip anlegt / Then gibt es bis zum Anlegen weder einen PUT noch einen Autosave, und beim Anlegen genau einen POST auf die Trip-Anlage.
  - Test: E2E zählt Netzwerkaufrufe: null PUT, null Schreibaufrufe vor dem Anlegen, genau ein POST `/api/trips`; Unit-Test `anlegen_ohne_autosave`.

- **AC-5:** Given die Karte zeigt eine Tabelle mit vom Nutzer gesetzten Haken, Formaten und Reihenfolge / When er im Schritt Wetter eine Metrik hinzufügt oder entfernt / Then kommt die Zeile der neuen Metrik hinzu bzw. die Zeile der entfernten entfällt, und alle übrigen Einstellungen (Haken, Formate, Reihenfolge) bleiben unverändert.
  - Test: Unit-Test der Karte im Anlege-Modus (Haken nach Metrikwechsel noch gesetzt) und E2E mit Metrik hinzufügen/entfernen.

- **AC-6:** Given eine Vorschau-Anfrage ist unterwegs / When der Nutzer inzwischen einen Haken klickt oder die Metriken wechselt und danach die ältere Antwort eintrifft / Then überschreibt die späte Antwort den neueren Stand nicht, der Haken bleibt gesetzt und die Metrikliste entspricht dem letzten Stand.
  - Test: Unit-Test der Speicherung mit verzögerter erster Antwort: Antwort nach Klick und nach Metrikwechsel wird verworfen.

- **AC-7:** Given der Nutzer öffnet den Schritt Wetter, ändert aber an der Karte nichts / When er den Trip anlegt / Then enthält der POST wie heute keine `rows` und keine Schalterfelder aus der Karte, und der Server baut die Tabelle aus der Grundauswahl.
  - Test: Fixtures `p11_neuanlage_payload_fixture` und `standardwerte_payload_paritaet_trip` bleiben unverändert grün; E2E prüft, dass im POST keine `placements.rows` stehen.

- **AC-8:** Given ein Trip wurde mit geänderter Tabelle und geänderten Schaltern angelegt / When der Nutzer den Reiter Wetter dieses Trips öffnet / Then zeigt er dieselben Haken, Formate, Reihenfolge und Schalterwerte, die beim Anlegen eingestellt waren.
  - Test: E2E-Rückweg: nach dem Anlegen Reiter Wetter öffnen und jeden eingestellten Wert vergleichen.

- **AC-9:** Given zwei verschiedene Nutzer A und B / When A einen Trip mit geänderter Tabelle anlegt / Then erscheint der Trip nur bei A, B sieht ihn und seine Einstellungen nicht, und die Vorschau beim Anlegen nutzt nur die Daten des jeweils angemeldeten Nutzers.
  - Test: E2E mit zwei Prüfkonten: A legt an, B listet Trips und öffnet die Kennung von A (kein Zugriff); Vorschau als B enthält keine Daten von A.

- **AC-10:** Given der Schritt Wetter im Anlegen ist geöffnet / When der Nutzer nur Haken, Formate, Reihenfolge oder Schalter ändert (keine Metrikänderung) / Then lädt keine neue Vorschau nach und es entsteht keine Endlosschleife; bei einer Metrikänderung genau ein entprelltes Nachladen.
  - Test: Unit-Test und E2E zählen Vorschau-Aufrufe: null Aufrufe bei reiner Karten-Bedienung, genau einer nach einer Metrikänderung.

## Definition of Done

- AC-1 bis AC-10 durch Kern-Tests (`node --test`, ohne Mock-Theater) und E2E grün; Datenverlust- (AC-2/AC-5), Späte-Antwort- (AC-6) und Schleifen-Test (AC-10) zuerst rot nachgewiesen.
- Bestehende Anlege-Fixtures (Payload ohne Kartenbedienung) und `anlegen_ohne_autosave` unverändert grün (AC-4/AC-7); Wächter-Bestand `TripNewEditor.svelte` nicht gestiegen.
- Staging: Trip mit Prüfkonto angelegt, Haken/Schalter beim Anlegen geändert, genau ein POST, Reiter Wetter zeigt danach dasselbe; zweiter Nutzer sieht nichts (AC-8/AC-9).
- Live auf Produktion, Selftest Exit 0. Keine Änderung an Gate-Konfiguration.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Anlege-Modus WHEN Karte Stand ändert THEN `onAnlegeStand` meldet auch bei `stored=false`, kein PUT (AC-2, AC-4)
- [ ] Test 2: GIVEN gesetzte Haken WHEN Metrik hinzu/weg THEN Zeilen ergänzt/entfernt, Haken bleiben (AC-5)
- [ ] Test 3: GIVEN verzögerte Vorschau-Antwort WHEN Klick bzw. Metrikwechsel dazwischen THEN späte Antwort verworfen (AC-6)
- [ ] Test 4: GIVEN `karte` gesetzt WHEN `buildCreateTripPayload` THEN placements und Schalter-Differenz im Payload, Versandzeiten/Kanäle gleich (AC-2, AC-3)
- [ ] Test 5: GIVEN `karte` nicht gesetzt WHEN `buildCreateTripPayload` THEN Payload bitgleich zu heute (AC-7)
- [ ] Test 6: GIVEN Kartenbedienung ohne Metrikänderung WHEN Zeitgeber abläuft THEN null Vorschau-Aufrufe (AC-10)
- [ ] Test 7: E2E Karte sichtbar Mobil+Desktop, Stand überlebt Wechsel (AC-1)
- [ ] Test 8: E2E ein POST, kein PUT, Körper mit placements und Schaltern (AC-2, AC-3, AC-4)
- [ ] Test 9: E2E Rückweg Reiter Wetter zeigt dasselbe (AC-8)
- [ ] Test 10: E2E zwei Nutzer (AC-9)

Test-Politik: kein Mock-Theater; Kern-Tests deterministisch ohne Netz (`node --test`), Live-Nachweis im E2E gegen Staging. Dateiinhalt-Checks sind kein Verhaltensnachweis.

## Known Limitations

- Bis #3307 stehen Mail-Format und Telegram-Kurzstil auf der Anlegeseite an zwei Stellen; maßgeblich ist, was in der Karte gegenüber ihrem Start geändert wurde.
- Die Vorschau zeigt Beispielwerte aus dem festen Datensatz, keine echten Wetterwerte (wie im Reiter Wetter).
- Zeilen werden vom Server wie beim PUT nicht inhaltlich geprüft (ADR-0077); keine neue Lücke.
- Orte-Anlegen hat noch keine Karte (#3306); das Alt-Panel bleibt bis #3307.
- Der Auftrag braucht keine Sperren-Aufhebung und keine Änderung der Gate-Konfiguration.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0124 gilt unverändert)
- **Rationale:** ADR-0124 macht die Tabelle zur einzigen Quelle; diese Spec bindet die vorhandene Karte nur im Anlegen an und ändert keine frühere Entscheidung. Umsetzung der PO-Vorgabe „Anlegen = Bearbeiten“.

## Changelog

- 2026-11-24: Initial spec created (Teil B von #3041, Issue #3305, Epic #3122).
