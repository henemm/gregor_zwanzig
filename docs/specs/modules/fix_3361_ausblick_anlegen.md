---
entity_id: fix_3361_ausblick_anlegen
type: bugfix
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
issue: 3361
workflow: fix-3361-ausblick-anlegen
tags: [anlegen, ausblick, was-steht-wo, trip, orts-vergleich]
---

# Fix #3361: 3-Tages-Ausblick beim Anlegen folgt der Zustellung

## Approval

- [ ] Approved

## Purpose

Beim Anlegen von Trip und Orts-Vergleich friert die Karte „Was steht wo" den Ausblick-Stand der Vorschau ein, obwohl der Nutzer ihn nie angefasst hat. Wer danach „nur Morgen-Briefing" einstellt, bekommt den Ausblick in keinem Briefing. Soll (#3155 AC-7, #3122 AC-9, ADR-0124 Nr. 6): Ohne eigene Wahl gilt die Vorbelegung des Python-Kerns, die dem Briefing folgt, das es gibt.

## Source

- **File:** `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte`
- **Identifier:** `uebernehmen` (Anlege-Zweig, `createMode`)

> **Schicht:** ausschließlich Frontend (SvelteKit). Go-API und Python-Core bleiben unverändert: Go lässt mitgeschickte `placements` unangetastet (`internal/handler/placements.go`), Python liest einen fehlenden `outlook_reports`-Schlüssel als `None` und wendet die Vorbelegung bei jedem Lesen an (`resolve_outlook_reports`, `src/services/placements.py`).
>
> **Trip/Ortsvergleich-Teilung:** Die Karte ist ein einziger Code für beide Kontexte (ADR-0097); die Korrektur wirkt damit für Trip und Orts-Vergleich zugleich, kein Pendant nötig.
>
> **Kanäle:** Der Ausblick steht in allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS) im jeweiligen Briefing; die Korrektur ändert nur, ob `outlook_reports` gespeichert wird, nicht den Inhalt je Kanal.

## Scope

- **Im Umfang:** Anlegen von Trip und Orts-Vergleich mit der Karte „Was steht wo“: Der Anlege-Stand trägt den 3-Tages-Ausblick nur, wenn der Nutzer ihn selbst gewählt hat. Änderung an genau einer geteilten Stelle (Karte + reine Stand-Funktion).
- **Nicht im Umfang:** Bearbeiten im Detail-Hub, Go-API, Python-Kern (siehe „Nicht im Umfang“ unten).

## Estimated Scope

- **LoC:** ca. 60 (ca. 10 Code, ca. 50 Test)
- **Files:** 4 (2 Code, 2 Test/Liste)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_outlook_reports` (`src/services/placements.py`) | Python-Funktion | Vorbelegung, wenn gespeichert `None` ist |
| `placements_aus_grundauswahl` | Python-Funktion | Quelle des aufgelösten Vorschau-Stands, der bisher eingefroren wurde |
| `mitKarte` (`frontend/src/lib/components/trip-new/tripNewLogic.ts`, `frontend/src/lib/components/compare/compareEditorSave.ts`) | TS-Funktion | setzt gemeldete `placements` unverändert in den Anlege-POST |
| `tripMehrreiterPruefstand` | Test-Prüfstand | echte Karte in der Kern-Schicht |

## Implementation Details

Variante A (eine Stelle, geteilt): In `frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts` kommt eine reine Funktion `ohneAusblick(placements)` hinzu, die `outlook_reports` entfernt. In `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` übernimmt `uebernehmen` im Anlegen (`createMode=true`) den Vorschau-Stand als `lokal = ohneAusblick(klon(a.placements))`. Bedient der Nutzer selbst einen Ausblick-Schalter, setzt `mitAusblick` den Wert wieder und er geht mit. Im Bearbeiten (`createMode=false`) bleibt alles unverändert. Die Anzeige der Schalter nutzt weiter `lokal?.outlook_reports ?? antwort?.outlook_reports` und zeigt damit ohne Wahl die Vorbelegung der Vorschau.

Variante B (Flag in `KarteAnlegeStand`, Entfernen in beiden `mitKarte`) wurde verworfen: vier Stellen, alle Fixtures bräuchten das Flag.

## Expected Behavior

- **Input:** Anlegen, Karte bedient, Ausblick nicht angefasst.
- **Output:** Anlege-POST trägt `placements` ohne `outlook_reports`; der Python-Kern löst die Vorbelegung beim Lesen nach dem dann gültigen Zustellungsstand auf.
- **Side effects:** keine; Bearbeiten im Detail-Hub schreibt wie bisher.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer legt einen Trip oder einen Orts-Vergleich an, bedient die Karte „Was steht wo" (ein Haken), fasst den 3-Tages-Ausblick nicht an und stellt die Zustellung auf „nur Morgen-Briefing" / When er das Anlegen abschließt / Then steht der 3-Tages-Ausblick im Morgen-Briefing, für Trip und Orte, und ein zweiter Nutzer mit eigenem Abo sieht davon nichts.
  - Test: Der vorhandene Test E137 in `frontend/src/lib/components/trip-new/__tests__/anlegen_ausblick_vorbelegung_folgt_zustellung.test.ts` läuft ohne `todo` und unverändert grün, mit echtem Python-Kern und zwei verschiedenen Nutzern.

- **AC-2:** Given ein Nutzer bedient die Karte beim Anlegen, fasst den Ausblick nicht an und lässt beide Briefings (Morgen und Abend) an / When er das Anlegen abschließt / Then steht der Ausblick im Abend-Briefing, die bisherige Vorbelegung bleibt unverändert.
  - Test: Kern-Schicht mit echter Karte (`tripMehrreiterPruefstand`) und echtem Python-Kern: Abo mit beiden Briefings an liefert `outlook_reports = ["evening"]`, für Trip und Orte.

- **AC-3:** Given ein Nutzer wählt den Ausblick beim Anlegen selbst (zum Beispiel Morgen und Abend) / When er die Zustellung danach beliebig ändert und anlegt / Then wird genau seine Wahl gespeichert, unabhängig von der Zustellung.
  - Test: Kern-Schicht: Ausblick-Schalter bedient, anschließend Zustellung „nur Morgen"; gemeldeter Stand und gespeichertes Abo tragen `["morning","evening"]`, für Trip und Orte.

- **AC-4:** Given ein bestehender Trip oder Orts-Vergleich wird im Detail-Hub bearbeitet (`createMode=false`) / When der Nutzer die Karte bedient und speichert / Then wird die Tabelle samt Ausblick wie bisher geschrieben, ohne Veränderung durch diesen Fix.
  - Test: Kern-Schicht: Karte mit `createMode=false` meldet den Stand inklusive `outlook_reports` der Vorschau unverändert.

- **AC-5:** Given ein Nutzer ist im Anlegen und hat den Ausblick nicht selbst gewählt / When er die Karte ansieht / Then zeigen die Ausblick-Schalter die Vorbelegung der Vorschau, obwohl nichts davon gespeichert wird.
  - Test: Kern-Schicht: gerenderte Karte im Anlegen zeigt den Schalter-Stand der Vorschau (Abend an bei beiden Briefings), während der gemeldete Stand keinen `outlook_reports` trägt.

## Testplan

### Kern-Schicht (`node --test`, deterministisch, ohne Netz)

- E137 aus `todo` nehmen, Inhalt unverändert (AC-1).
- Neuer Test neben E137: echte Karte über `tripMehrreiterPruefstand`, keine Mocks, die nur Annahmen spiegeln; Python-Kern echt wie in E137. Fälle: Haken bedient ohne Ausblick (gemeldeter Stand ohne `outlook_reports`), Ausblick bedient (Wahl bleibt), `createMode=false` unverändert, Anzeige der Schalter (AC-2 bis AC-5).
- Verweis auf #3361 in `frontend/src/lib/__tests__/rework_3020_rote_liste.ts` bereinigen, falls er den `todo` führt.
- Rot-Nachweis zuerst aus Nutzersicht: E137 ohne `todo` schlägt vor dem Fix fehl.

### Staging-E2E (`/e2e-verify`, nach dem Push)

- Anlegen über die echte Oberfläche bzw. echten POST auf Staging: Karte bedient, Ausblick nicht angefasst, Zustellung „nur Morgen".
- GET des angelegten Abos: `placements` ohne `outlook_reports`, das Morgen-Briefing enthält den Ausblick.
- Zwei verschiedene Nutzer, je ein Trip und ein Orts-Vergleich; der zweite Nutzer sieht das Abo des ersten nicht.

## Nicht im Umfang

- Hub-Abos ohne gespeicherte `rows` (Vorschau-Stand) frieren den Ausblick beim ersten PUT ebenso ein. Nach dem Datenlauf #3351 tragen Bestandsabos `rows`; der Nutzer sieht dort den Ausblick-Schalter im Ist-Stand. Beobachtung, kein Code; wird im Abschlusskommentar des Issues vermerkt.
- Änderungen an Go-API, Python-Kern oder Gate-Konfiguration.

## Known Limitations

- Die Korrektur gilt nur im Anlegen; Bearbeiten ist bewusst unverändert.

## Definition of Done

- AC-1 bis AC-5 durch Tests der Kern-Schicht nachgewiesen; E137 ohne `todo`, inhaltlich unverändert, grün.
- Adversary-Prüfung mit Mutations-Gegenprobe ohne offenes Finding.
- Alle 6 CI-Checks grün, Staging-E2E (Trip und Orte, zwei Nutzer) bestanden, Prod-Selbsttest Exit 0.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; setzt ADR-0124 Nr. 6 (Vorbelegung Ausblick) und ADR-0097 (geteilter Code) um.
- **Rationale:** Der Fix stellt die bereits entschiedene Vorbelegung wieder her, eine neue Entscheidung ist nicht nötig.

## Changelog

- 2026-11-26: Initial spec created (Issue #3361)
