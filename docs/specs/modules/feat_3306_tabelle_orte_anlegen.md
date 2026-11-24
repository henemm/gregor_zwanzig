---
entity_id: feat_3306_tabelle_orte_anlegen
type: module
created: 2026-11-24
updated: 2026-11-24
status: approved
version: "1.0"
workflow: feat-3306-tabelle-orte-anlegen
tags: [was-steht-wo, placements, anlegen, ortsvergleich, epic-3122]
---

# Tabelle „Was steht wo“ beim Ortsvergleich-Anlegen (#3306)

## Approval

- [x] Approved (automatisch, Ampel grün, 2026-11-24)

## Purpose

Beim Anlegen eines Ortsvergleichs zeigt der Schritt „Wetter“ dieselbe Tabelle „Was steht wo“ samt Schaltern (Stundenverlauf, Ausblick, Telegram-Kurzstil) wie der Reiter Wetter eines gespeicherten Ortsvergleichs. Der eine Anlege-Aufruf trägt Tabelle und Schalter mit, und nach dem Anlegen zeigt der Reiter Wetter genau diesen Stand. Teil C von #3041 (Epic #3122), Pendant zu #3305 (Trip) über denselben Code mit `context="vergleich"`; Zustellungsschritt und Entfernen des Alt-Panels (#3307) sind nicht Teil dieser Spec.

## Source

- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts`, `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`
- **Identifier:** `baueVergleichAnlegeRumpf`, `legeVergleichAn` (Feld `wetter.karte`), `karteStand` und `handleKarteStand` (neu in `CompareNewEditor`), Vorschau-Entwurf `wetterAbo`

> **Schicht-Hinweis:** Ausschließlich Frontend (SvelteKit, `frontend/src/...`). Go-API (`anlageTabelle` in `internal/handler/compare_preset.go` übernimmt mitgeschickte `placements.rows` unverändert) und Python-Vorschau (#3304, `build_placements_preview('vergleich', …)`) bleiben unverändert. Ausnahme nur, falls der TDD-RED-Test zeigt, dass der Kern einen frühen Anlege-Entwurf mit Fehler ablehnt: dann kleine Kernkorrektur wie bei #3305 und Aufnahme in den Scope.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Keine neue Komponente. `WasStehtWoKarte`, `WetterTabInhalt`, `wasStehtWoSpeicherung.ts` und `KarteAnlegeStand` aus #3305 werden mit `context="vergleich"` wiederverwendet; neu ist nur die Verdrahtung im Editor und im Anlege-Rumpf (Gate #1170).
> - **Mandantentrennung:** Die Vorschau nimmt Orte nur aus dem eigenen Bestand des angemeldeten Nutzers (fremde oder unbekannte IDs fallen weg, #3304); der POST legt beim angemeldeten Nutzer an, nie `"default"`. Test mit zwei verschiedenen Nutzern.
> - **Kanäle:** Die Karte zeigt E-Mail, Telegram, SMS und Premium-SMS mit demselben Inhalt wie im Reiter Wetter; kein Kanal wird ersetzt, Versandzeiten und Kanalwahl bleiben unberührt.

## Estimated Scope

- **LoC:** Produktion ca. +40 bis +70, Tests ca. +200 bis +300
- **Files:** 2 Produktionsdateien + ca. 4 Testdateien
- **Effort:** small bis medium (Risiko LOW bis MEDIUM: Datenverlust, wenn die Karte sichtbar ist, ihr Stand aber nicht im POST ankommt; Doppel-POST)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `baueVergleichAnlegeRumpf` und `legeVergleichAn` bekommen `wetter.karte?: KarteAnlegeStand`; nur wenn gesetzt: `display_config.placements = karte.placements` und `felderNutzlast('vergleich', karte.felder, karte.felderStart)` per Read-Modify-Write einmischen (`hourly_enabled` top-level, `display_config.telegram_style`); ohne Karte Rumpf unverändert |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | `karteStand` als `$state` plus `handleKarteStand`; `karteStart` und `onAnlegeKarte` an beiden WetterTab-Stellen (Desktop und Mobil); `karte: karteStand` an `legeVergleichAn`; Vorschau-Entwurf `wetterAbo` um `location_ids: wiz.pickedIds`, `hourly_enabled: wiz.hourlyEnabled`, `display_config.telegram_style: wiz.telegramStyle` ergänzt |
| `frontend/src/lib/components/compare/__tests__/` (node --test) | CREATE/MODIFY | Rumpf mit und ohne Karte, keine Altschlüssel, Editor-Verdrahtung (ein POST, kein PUT) |
| `tests/` (pytest, Python-Kern) | CREATE | Vorschau `kind=vergleich` beantwortet einen frühen Entwurf (ohne `name`/`schedule`, leere oder gesetzte `location_ids`) mit 200 |
| `frontend/e2e/vergleich-anlegen-was-steht-wo-3306.spec.ts` | CREATE | Anlegen mit geänderter Tabelle und Schaltern, genau ein POST, Hub zeigt den Stand, zweiter Nutzer |

### Nicht in dieser Spec

- `ZustellungTab` im Anlege-Modus und Entfernen des Alt-Panels (Altblock im Schritt Zustellung): **#3307**.
- Bereinigung von Altdaten: **#3277**.
- Änderungen an Vorschau-Endpunkt, Go-Anlage, GET/PUT-Weg oder Gate-Konfiguration.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/briefings/placements/vorschau?kind=vergleich` (#3304) | API | Liefert die Ansicht für den noch nicht gespeicherten Entwurf, schreibt nichts, filtert Orte auf den eigenen Bestand |
| `WasStehtWoKarte`, `WetterTabInhalt`, `WetterTab` (#3305) | Frontend | Karte im Anlege-Modus, `karteStart`/`onAnlegeKarte` kontextneutral |
| `KarteAnlegeStand`, `felderNutzlast` (`wasStehtWoSpeicherung.ts`) | Frontend | Stand der Karte und Schalter-Differenz zum Start |
| `anlageTabelle` (Go, `internal/handler/compare_preset.go`) | Go | Übernimmt mitgeschickte `rows` unverändert |
| `feat_3305_tabelle_trip_anlegen`, `feat_3304_was_steht_wo_vorschau`, `feat_3122_was_steht_wo` | Spec | Vorbild, Vorschau, Antwortform |
| ADR-0124, ADR-0077 | ADR | Tabelle als einzige Quelle; Zeilen werden wie beim PUT übernommen |

## Implementation Details

**Muster #3305, Kontext vergleich.** Der Editor hält `karteStand` als `$state`, damit der Stand den Wechsel Desktop und Mobil sowie das Vor- und Zurückgehen der Schritte übersteht. Die Karte startet aus diesem Stand und meldet über `onAnlegeKarte` (`handleKarteStand`). Es gibt weder PUT noch Autosave im Anlege-Modus; beim Anlegen geht genau ein POST hinaus.

**Rumpf.** `baueVergleichAnlegeRumpf` mischt erst beim POST und nur, wenn `wetter.karte` gesetzt ist: `display_config.placements` aus der Karte, dazu `felderNutzlast('vergleich', felder, felderStart)` (nur Geändertes) per Read-Modify-Write in den vorhandenen Rumpf. Wer die Karte nie bedient, sendet wie heute keine `rows`; der Server baut die Tabelle bei der Erstanlage. Der Ausblick-Schalter ist `outlook_reports` in der Tabelle und reist mit `placements`. Keine Altschlüssel im POST (`channel_layouts`, `outlook_metrics`, `outlook_metric_formats`, `channel_active_metrics`, `hourly_metrics`, `hourly_metric_formats`, #3276); `hourly_enabled` und `telegram_style` sind keine Altschlüssel.

**Vorschau-Entwurf.** `wetterAbo` erhält `location_ids: wiz.pickedIds` (der Schritt Orte liegt vor Wetter), `hourly_enabled: wiz.hourlyEnabled` und `display_config.telegram_style: wiz.telegramStyle`. Damit rechnet die Vorschau mit den gewählten Orten (Beispielwerte statt leerer Ansicht) und die Schalter starten mit dem Stand des Feldsatzes. `anlegeSpeicherer('vergleich')` meldet daraus weiterhin nur Ampel, Auswahl und Tabelle; `handleWetterAnlegeStand` verwirft `placements`, die Tabelle reist allein über `karteStand`.

**Zwei Bedienstellen bis #3307.** Stundenverlauf und Telegram-Kurzstil stehen vorübergehend an zwei Stellen (Karte und Altblock im Schritt Zustellung). Regel wie bei #3305: Die Karte startet aus dem Entwurfsstand; beim POST wird nur angewandt, was in der Karte gegenüber ihrem Start geändert wurde. Entfällt mit #3307.

**Früher Entwurf im Kern.** Der RED-Test prüft, dass `kind=vergleich` einen frühen Entwurf (ohne `name` und `schedule`, mit leerer oder gesetzter `location_ids`) mit 200 beantwortet. Zeigt er das Gegenteil, wird eine kleine Kernkorrektur wie in #3305 ergänzt und der Scope entsprechend erweitert.

## Expected Behavior

- **Input:** Nutzer legt einen Ortsvergleich an, wählt Orte, stellt im Schritt Wetter Haken, Formate, Reihenfolge und Schalter (Stundenverlauf, Ausblick, Telegram-Kurzstil) in der Tabelle ein und legt an.
- **Output:** Genau ein `POST` auf die Ortsvergleich-Anlage mit `display_config.placements`, `hourly_enabled` und `display_config.telegram_style`; der Reiter Wetter des neuen Ortsvergleichs zeigt genau das Eingestellte.
- **Side effects:** Nur lesende Vorschau-Aufrufe während des Anlegens; kein PUT, kein Speichern vor dem Anlegen.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer legt einen neuen Ortsvergleich an und hat Orte gewählt / When er den Schritt Wetter öffnet, in der Mobil- und in der Desktop-Ansicht / Then ist die Tabelle „Was steht wo“ mit den Schaltern Stundenverlauf, Ausblick und Telegram-Kurzstil sichtbar, zeigt Beispielwerte der gewählten Orte, und ihr Stand bleibt beim Wechsel zwischen Mobil und Desktop sowie beim Weiter- und Zurückgehen der Schritte erhalten.
  - Test: E2E in beiden Ansichten: Karte erscheint, Haken setzen, Ansicht und Schritte wechseln, Haken ist weiterhin gesetzt; Beispielwerte der gewählten Orte sichtbar.

- **AC-2:** Given die Karte im Anlegen ist geöffnet / When der Nutzer einen Haken, ein Format oder die Reihenfolge ändert und den Ortsvergleich anlegt / Then enthält der eine Anlege-POST diese Änderung in `display_config.placements` (Zeilen in der eingestellten Reihenfolge, Haken und Formate wie gesetzt).
  - Test: E2E zeichnet den POST-Körper auf und prüft `display_config.placements.rows`; Unit-Test `baueVergleichAnlegeRumpf` mit gesetztem `karte`.

- **AC-3:** Given die Karte im Anlegen ist geöffnet / When der Nutzer Stundenverlauf, Ausblick und Telegram-Kurzstil ändert und anlegt / Then stehen im POST `hourly_enabled`, `display_config.telegram_style` und der Ausblick als `outlook_reports` in der Tabelle, Versandzeiten und Kanalwahl bleiben wie ohne Kartenbedienung, und der POST enthält keinen der Altschlüssel (`channel_layouts`, `outlook_metrics`, `outlook_metric_formats`, `channel_active_metrics`, `hourly_metrics`, `hourly_metric_formats`).
  - Test: Unit-Test und E2E vergleichen den POST-Körper mit und ohne Kartenbedienung: nur die geänderten Felder weichen ab, keine Altschlüssel; `feat3276_vergleich_ohne_altfelder` bleibt grün.

- **AC-4:** Given der Nutzer bedient die Karte im Anlegen / When er mehrere Änderungen macht und den Ortsvergleich anlegt / Then gibt es bis zum Anlegen weder einen PUT noch einen Autosave, und beim Anlegen genau einen POST auf die Ortsvergleich-Anlage.
  - Test: E2E zählt Netzwerkaufrufe: null PUT, null Schreibaufrufe vor dem Anlegen, genau ein POST; `compare_new_editor_postet_einmal` bleibt grün.

- **AC-5:** Given der Nutzer öffnet den Schritt Wetter, ändert aber an der Karte nichts / When er den Ortsvergleich anlegt / Then enthält der POST wie heute keine `rows` und keine Schalterfelder aus der Karte, und der Server baut die Tabelle aus der Grundauswahl.
  - Test: Unit-Test `baueVergleichAnlegeRumpf` ohne `karte` bitgleich zu heute; E2E prüft, dass im POST keine `placements.rows` stehen.

- **AC-6:** Given ein Ortsvergleich wurde mit geänderter Tabelle und geänderten Schaltern angelegt / When der Nutzer den Reiter Wetter dieses Ortsvergleichs öffnet / Then zeigt er dieselben Haken, Formate, Reihenfolge und Schalterwerte, die beim Anlegen eingestellt waren.
  - Test: E2E-Rückweg: nach dem Anlegen Reiter Wetter öffnen und jeden eingestellten Wert vergleichen.

- **AC-7:** Given zwei verschiedene Nutzer A und B, B besitzt eigene Orte / When A einen Ortsvergleich mit geänderter Tabelle anlegt und dabei eine Orts-Kennung von B in der Vorschau mitschickt / Then erscheint der Ortsvergleich nur bei A, die Vorschau rechnet nur mit den Orten von A (Orte von B fallen weg), und B sieht den Ortsvergleich von A nicht.
  - Test: E2E mit zwei Prüfkonten: A legt an, B listet Ortsvergleiche und öffnet die Kennung von A (kein Zugriff); Vorschau als A mit Kennung eines Ortes von B enthält keine Beispielwerte dieses Ortes.

- **AC-8:** Given die Vorschau für Ortsvergleiche bekommt einen frühen Entwurf / When der Entwurf weder Namen noch Zeitplan hat und die Ortsliste leer oder gesetzt ist / Then antwortet die Vorschau mit Erfolg und einer Ansicht statt mit einem Fehler.
  - Test: Python-Test gegen den Kern: Vorschau `kind=vergleich` mit leerem Entwurf, mit leerer und mit gesetzter `location_ids` liefert 200.

- **AC-9:** Given die Karte im Anlegen zeigt Stundenverlauf oder Telegram-Kurzstil und der Altblock im Schritt Zustellung kann dieselben Schalter setzen / When der Nutzer einen Schalter nur im Altblock ändert und die Karte nicht bedient / Then gilt im POST der Wert des Altblocks, und wenn er den Schalter in der Karte gegenüber ihrem Start ändert, gilt der Wert der Karte.
  - Test: Unit-Test `baueVergleichAnlegeRumpf` mit unveränderten und mit geänderten Feldern der Karte (`felderStart` gleich bzw. verschieden).

## Definition of Done

- AC-1 bis AC-9 durch Kern-Tests (`node --test`, Python-Test, ohne Mock-Theater) und E2E grün; Datenverlust (AC-2, AC-3) und früher Entwurf (AC-8) zuerst rot nachgewiesen.
- Bestehende Bestände unverändert grün: `compare_new_editor_postet_einmal`, `feat3276_vergleich_ohne_altfelder`, Anlege-Fixtures des Ortsvergleichs ohne Kartenbedienung (AC-4, AC-5); Wächterliste (`bausteine_waechter_regeln.ts`) ohne neue Verstöße.
- Staging: Ortsvergleich mit Prüfkonto angelegt, Tabelle und Schalter beim Anlegen geändert, genau ein POST, Reiter Wetter zeigt danach dasselbe; zweiter Nutzer sieht nichts (AC-6, AC-7).
- Live auf Produktion, Selftest Exit 0. Keine Änderung an Gate-Konfiguration.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN `karte` gesetzt WHEN `baueVergleichAnlegeRumpf` THEN `display_config.placements` und Schalter-Differenz (`hourly_enabled`, `telegram_style`) im Rumpf, Versandzeiten und Kanäle gleich, keine Altschlüssel (AC-2, AC-3)
- [ ] Test 2: GIVEN `karte` nicht gesetzt WHEN `baueVergleichAnlegeRumpf` THEN Rumpf bitgleich zu heute (AC-5)
- [ ] Test 3: GIVEN Schalter nur im Altblock geändert, Karte unverändert WHEN Rumpf gebaut THEN Altblock-Wert gilt; Karte geändert THEN Karten-Wert gilt (AC-9)
- [ ] Test 4: GIVEN Editor im Anlege-Modus WHEN Karte bedient und angelegt THEN genau ein POST, kein PUT, `karteStand` im POST (AC-2, AC-4)
- [ ] Test 5: GIVEN früher Entwurf `kind=vergleich` (ohne `name`/`schedule`, `location_ids` leer und gesetzt) WHEN Vorschau THEN 200 (AC-8)
- [ ] Test 6: GIVEN Vorschau mit Orts-Kennung eines fremden Nutzers WHEN als A aufgerufen THEN keine Werte des fremden Ortes (AC-7)
- [ ] Test 7: E2E Karte sichtbar Mobil und Desktop, Stand überlebt Wechsel (AC-1)
- [ ] Test 8: E2E ein POST, kein PUT, Körper mit Tabelle und Schaltern (AC-2, AC-3, AC-4)
- [ ] Test 9: E2E Rückweg Reiter Wetter zeigt dasselbe (AC-6)
- [ ] Test 10: E2E zwei Nutzer (AC-7)

Test-Politik: kein Mock-Theater; Kern-Tests deterministisch ohne Netz (`node --test`, pytest mit benannten Dateien), Live-Nachweis im E2E gegen Staging. Dateiinhalt-Checks sind kein Verhaltensnachweis.

## Known Limitations

- Stundenverlauf und Telegram-Kurzstil standen bis #3333 (2026-11-24) an zwei Stellen (Karte und Altblock); mit #3333 ist der Altblock im Orte-Anlegen entfallen, die Karte ist die einzige Bedienstelle.
- Die Vorschau zeigt Beispielwerte aus dem festen Datensatz, keine echten Wetterwerte (wie im Reiter Wetter); ohne gewählte Orte gibt es keine Beispielwerte.
- Zeilen werden vom Server wie beim PUT nicht inhaltlich geprüft (ADR-0077); keine neue Lücke.
- Das Alt-Panel im Schritt Zustellung ist mit #3333 (2026-11-24) aus dem Orte-Anlegen entfernt; die Panel-Dateien bleiben bis #3020/#3036.
- Der Auftrag braucht keine Sperren-Aufhebung und keine Änderung der Gate-Konfiguration.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0124 gilt unverändert)
- **Rationale:** ADR-0124 macht die Tabelle zur einzigen Quelle; diese Spec bindet die vorhandene Karte nur im Anlegen eines Ortsvergleichs an und ändert keine frühere Entscheidung. Umsetzung der PO-Vorgabe „Anlegen = Bearbeiten“ mit gemeinsamem Code für Trip und Ortsvergleich.

## Changelog

- 2026-11-24: Initial spec created (Teil C von #3041, Issue #3306, Epic #3122).
- 2026-11-24: Nachtrag (docs-updater, #3333 / Teil D2 von #3307): Zustellung im Orte-Anlegen über den Reiter Zustellung, Altblock und Alt-Panel entfallen; Known Limitations zu „bis #3307“ aktualisiert. Karte und Vergleichs-Tabelle unverändert.
