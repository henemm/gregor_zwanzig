---
entity_id: refactor_2987_standardwerte_eine_quelle
type: module
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: refactor-2987-standardwerte-eine-quelle
tags: [frontend, trip, standardwerte, zustellung, refactor]
---

# Trip-Briefing-Startwerte aus einer Quelle (Issue #2987)

## Approval

- [ ] Approved

## Purpose

Die Startwerte des Trip-Briefings (Slots Morgen/Abend, Zeiten 07:00/18:00, vier Kanaele mit E-Mail an) werden heute an zwei Stellen gelesen: im sichtbaren Reiter Zustellung und beim Anlegen-POST. Dieser Umbau fuehrt beides auf EINE Lesefunktion zurueck, entfernt den von Hand gefuellten Schein-`zustand` im Standardwerte-Ergaenzer und haengt den Paritaetswaechter von den nicht mehr sichtbaren Alt-Reitern ab, damit er das Loeschen in #3020 ueberlebt. Fuer den Nutzer aendert sich nichts: der POST-Koerper bleibt auf jedem Bedienweg bitgleich (einzige, nicht per Bedienung erreichbare Abweichung: AC-3).

## Source

- **File:** `frontend/src/lib/components/shared/briefingStartwerte.ts` (neu)
- **Identifier:** `leseBriefingStartwerte` (Arbeitsname), Konstanten `MORGEN_STANDARD`/`ABEND_STANDARD`, `hhmm`

Betroffen (alle Pfade unter `frontend/src/lib/components/`):
`shared/versand-tab/reportConfigPayload.ts` (`ladeReportZustand`), `shared/zustellung-tab/zustellungModell.ts` (`standAusTrip`, `standAusPreset`), `trip-new/tripNewLogic.ts` (`ergaenzeStandardwerteReportConfig`).

> **Schicht:** ausschliesslich Frontend (SvelteKit). Keine Aenderung an Go-API oder Python-Core.

> **Querschnitts-Pruefpunkte**
> - **Trip/Ortsvergleich-Teilung:** Das neue Modul liegt unter `shared/`. `standAusPreset` (Orts-Briefing) nutzt daraus nur die Konstanten und `hhmm`; seine Slot-Vorgaben (Abend aus) bleiben fachlich bewusst anders und werden nicht angeglichen. Keine neue Komponente mit Pendant, daher keine Pendant-Sperre.
> - **Mandantentrennung:** Reine Funktionen auf dem uebergebenen Blob, keine Nutzerdaten-Zugriffe, kein neuer Endpoint, keine `user_id`-Logik. Ein Zwei-Nutzer-Test entfaellt, weil nichts Nutzerdaten bewegt, was nicht schon der bestehende Anlege-POST tut.
> - **Kanaele:** Die vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) werden unveraendert gelesen: E-Mail an, uebrige aus. Inhalt und Form der Briefings aendern sich nicht.

## Scope

### Affected Files

Pfade unter `frontend/src/lib/components/`.

| File | Change Type | Description |
|------|-------------|-------------|
| `shared/briefingStartwerte.ts` | CREATE | Lesefunktion, Konstanten 07:00/18:00, `hhmm` |
| `shared/versand-tab/reportConfigPayload.ts` | MODIFY | `ladeReportZustand` nutzt die Lesefunktion |
| `shared/zustellung-tab/zustellungModell.ts` | MODIFY | `standAusTrip` nutzt die Lesefunktion, `standAusPreset` nur Konstanten und `hhmm` |
| `trip-new/tripNewLogic.ts` | MODIFY | Schein-`zustand` in `ergaenzeStandardwerteReportConfig` entfernt |
| `trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts` | MODIFY | feste Erwartungswerte statt Alt-Reiter |
| `shared/__tests__/briefing_startwerte.test.ts` | CREATE | Lesefunktion und beide Leser gegen feste Werte |

Nicht in dieser Spec: siehe Known Limitations.

## Estimated Scope

- **LoC:** Produktion ca. +55/-40 (95), Tests ca. +130/-80 (210), zusammen ca. 305 geaenderte Zeilen. Das liegt ueber der Richtgrenze von 250, ueberwiegend durch den Testumbau; die Freigabe dieser Spec deckt bis 320 Zeilen ab. Tests und Umsetzung werden als getrennte, je unter 250 liegende Commits geliefert. Darueber hinaus wird gestoppt. Nicht gesplittet, weil der Waechter-Umbau nur zusammen mit der neuen Quelle einen Massstab hat.
- **Files:** 4 Produktionsdateien (1 neu, 3 geaendert), 2 Testdateien (1 neu, 1 umgebaut), zusammen 6 (Richtgrenze 4-5)
- **Effort:** low (Risiko LOW)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `utils/reportSlotAktiv` | Modul | Slot-Regel (bereits eine Quelle, gemeinsame Fixture TS/Python/Go) |
| `toHHMMSS` | Funktion | Zeitformat im Payload |
| `mergeReportConfig` | Funktion | Read-Modify-Write des Blobs beim Ergaenzer |
| `DEFAULT_DAILY_SUMMARY_METRICS` | Konstante | Mail-Standardmetriken |
| `ladeMailZustand` (`shared/mailInhaltZustand.ts`) | Funktion | Mail-Baustein, bleibt als Quelle der Mail-Werte |
| `baueReportConfigPayload` | Funktion | bleibt unveraendert (Pflichtfeld `zustand`), von VersandTab/MailInhaltCard/`ergaenzeVersandStandard` gebraucht |
| #3020 | Issue | Loeschen der Alt-Bausteine; kommt NACH diesem Umbau |

## Implementation Details

Reihenfolge (TDD, je Schritt gruen):

1. `shared/briefingStartwerte.ts` anlegen: eine reine Lesefunktion `Blob -> { Slots, Zeiten, vier Kanaele }` (Slots ueber `reportSlotAktiv`, Zeiten ueber `hhmm` mit Standard 07:00/18:00, Kanaele: E-Mail an, Rest aus) plus die Konstanten und `hhmm`. Importiert nur aus `utils/`, kein i18n und keine Stores, damit keine Importzyklen entstehen.
2. `ladeReportZustand` = Lesefunktion + `telegram_style`; Signatur unveraendert. `standAusTrip` nutzt dieselbe Lesefunktion; `standAusPreset` nutzt nur Konstanten und `hhmm`.
3. In `ergaenzeStandardwerteReportConfig` den Schein-`zustand` entfernen: statt `baueReportConfigPayload` wird `mergeReportConfig({ snapshot: basis, live: nachVersand, own: mail })` aufgerufen, wobei `mail` inklusive Kopie von `daily_summary_metrics` uebergeben wird. Ergebnis zeichengleich inklusive Schluesselreihenfolge, Eingabe unveraendert. (Probe in der Analyse: 9 von 9 Blobs gleich.)
4. Waechter `trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts`: den Massstab `durchgeklickt()` (VersandTab/MailInhaltCard) durch feste Erwartungswerte ersetzen. Die Faelle #3155 AC-7/AC-13, F001/F002, Reinheit und Klick im echten `TripNewEditor` bleiben. Nicht doppeln, was `trip_anlegen_zustellung_verdrahtung_3332.test.ts` (POST gleich feste Fixture, Startstand des Reiters gleich POST) schon prueft.

Die einzige Wertabweichung: `ladeReportZustand` nutzt kuenftig `hhmm` statt `slice(0,5)`. Bei gueltigen Zeiten identisch; bei leerem oder ungueltigem Zeittext entsteht 07:00/18:00 statt eines Rohstuecks (`null`/fehlend ergab schon bisher den Standard). `ergaenzeVersandStandard` und damit `ergaenzeStandardwerteReportConfig` erben die Regel, weil sie `ladeReportZustand` aufrufen; `VersandTab` (nicht sichtbar) ebenso. Beim Anlegen ist das ueber die Bedienung nicht erreichbar (`reportConfig` entsteht dort nur aus Tagesfenster, Karte und `mitZustellung`, rasterfremde Zeiten werden verworfen; Go prueft Zeiten in `internal/handler/trip.go`). Die Regel ist daher durch Unit-Tests belegt, nicht durch einen Bedienpfad. Die uebrigen Leser (`cockpitHelpers`, `kanalStilSpeicherung`) lesen keine Zeiten.

Funktionen bleiben <=50 LoC.

## Expected Behavior

- **Input:** `report_config`-Blob (auch leer/undefined, mit unbekannten Bestandsfeldern, Kurzform, `null`/leere/ungueltige Zeiten).
- **Output:** auf jedem Bedienweg identischer Anlege-POST-Koerper wie vor dem Umbau; Reiter Zustellung zeigt dieselben Startwerte wie zuvor.
- **Side effects:** keine. Keine neuen Permissions, keine geaenderten Speicher-Keys, keine Datenschema-Aenderung.

## Acceptance Criteria

- **AC-1:** Given ein neuer Trip im echten TripNewEditor mit unveraenderten Standardwerten und einem Blob mit unbekannten Bestandsfeldern / When der Nutzer auf „Mit Standardwerten speichern“ klickt / Then entspricht der Anlege-POST-Koerper `report_config` exakt der festen erwarteten Fixture, unbekannte Felder inklusive.
  - Test: Klick im echten Editor, POST-Koerper gegen feste Fixture (nicht gegen eine zweite Berechnung).

- **AC-2:** Given dieselbe Fallliste von Blobs (leer, Slots einzeln/beide an, eigene Zeiten, Kanaele gesetzt) / When Reiter Zustellung (`standAusTrip`) und Anlege-Weg (`ladeReportZustand`) sie lesen / Then liefern beide dieselben Slots, Zeiten und Kanaele, und zwar gleich den festen erwarteten Werten; wird die gemeinsame Lesefunktion geaendert, wirkt es auf beide.
  - Test: Unit-Test gegen feste Erwartungswerte je Fall; Mutation der Lesefunktion macht beide Leser rot.

- **AC-3:** Given ein Blob mit ungueltiger, leerer oder `null`-Zeit bzw. mit `HH:MM:SS` / When die Zeit gelesen wird / Then entstehen 07:00 (Morgen) bzw. 18:00 (Abend) fuer ungueltig, leer und `null`, und `HH:MM:SS` wird zu `HH:MM`.
  - Test: Randfall-Unit-Tests der Lesefunktion. Offen dokumentiert: nur fuer leeren oder ungueltigen Zeittext weicht `ladeReportZustand` vom bisherigen `slice` ab (samt seinen Aufrufern); ueber die Bedienung beim Anlegen ist das nicht erreichbar.

- **AC-4:** Given ein neues Orts-Briefing / When der Startstand ueber `standAusPreset` gebildet wird / Then ist der Abend-Slot aus (Orts-Vorgabe) und es gilt nicht die Trip-Slot-Regel, die Zeiten sind 07:00/18:00.
  - Test: Unit-Test `standAusPreset` gegen feste Werte; Mutation "Trip-Slot-Regel im Preset" wird rot.

- **AC-5:** Given beliebige Eingabe-Blobs (leer, `undefined`, `enabled:false`, unbekannte Felder, Kurzform, fehlende/`null`/gueltige Zeiten) / When `ergaenzeStandardwerteReportConfig` ohne Schein-`zustand` (ueber `mergeReportConfig` mit `own` = Mail inklusive Kopie der `daily_summary_metrics`) laeuft / Then ist das Ergebnis zeichengleich zum bisherigen inklusive Schluesselreihenfolge und die Eingabe bleibt unveraendert; bei leerem oder ungueltigem Zeittext unterscheidet sich ausschliesslich der Zeitwert nach AC-3.
  - Test: Serialisierungsvergleich (JSON-String) gegen feste Erwartung je Blob und Pruefung der unveraenderten Eingabe (Reinheit).

- **AC-6:** Given der Paritaetswaechter `standardwerte_payload_paritaet_trip.test.ts` / When VersandTab und MailInhaltCard aus dem Testlauf entfernt sind (Zustand nach #3020) / Then besteht er weiterhin, behaelt die Faelle #3155 AC-7/AC-13, F001/F002, Reinheit und Klick im echten Editor und vergleicht gegen feste Erwartungswerte; jede der folgenden Mutationen der Implementierung macht mindestens einen Test des Umfangs (Waechter, `briefing_startwerte.test.ts` oder `trip_anlegen_zustellung_verdrahtung_3332.test.ts`) rot: "Abend-Slot-Vorgabe aus", "07:00/18:00 geaendert oder vertauscht", "Kanal-Vorgabe geaendert oder vertauscht", "`hhmm` durch `slice` ersetzt", "Mail-Baustein weggelassen", "`multi_day_trend_reports` falsch" und "`standAusPreset` mit Trip-Slot-Regel".
  - Test: Der Waechter wird mit den beiden Alt-Bausteinen ausserhalb des Testlaufs ausgefuehrt (kein Dateiinhalt-Check), die Mutationen per String-Ersetzung mit externer Sicherungskopie im Validator-Lauf.

- **AC-7:** Given ein bestehender Trip-Blob mit unbekannten Feldern und bereits gesetzten Werten (Zeiten, Kanaele, Slots, `multi_day_trend_reports`) / When die Standardwerte ergaenzt werden / Then bleiben die unbekannten Felder erhalten und die gesetzten Werte gewinnen gegen die Standardwerte (Read-Modify-Write, kein Replace).
  - Test: Unit-Test mit Blob aus unbekannten und gesetzten Feldern gegen feste Erwartung.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (AC-2, AC-3): GIVEN Fallliste von Blobs inkl. Zeit-Randfaellen WHEN Lesefunktion, `standAusTrip` und `ladeReportZustand` lesen THEN feste Erwartungswerte je Fall
- [ ] Test 2 (AC-4): GIVEN leeres Orts-Briefing WHEN `standAusPreset` THEN Morgen an, Abend aus, 07:00/18:00
- [ ] Test 3 (AC-5, AC-7): GIVEN Blobs mit unbekannten und gesetzten Feldern WHEN `ergaenzeStandardwerteReportConfig` THEN JSON-Text gleich fester Erwartung, Eingabe unveraendert
- [ ] Test 4 (AC-1): GIVEN echter TripNewEditor WHEN Klick auf „Mit Standardwerten speichern“ THEN ein POST mit fester `report_config`
- [ ] Test 5 (AC-6): GIVEN Waechter ohne Einbindung der beiden Alt-Bausteine WHEN er laeuft THEN gruen; die Mutationsgegenprobe ist ein getrennter Lauf im `implementation-validator`

Tests 1 und 2 sind vor der Umsetzung rot (Modul fehlt bzw. Zeitregel); 3 bis 5 sichern das Bestandsverhalten und duerfen vorher gruen sein. Test-Politik: node:test mit benannten Dateien, kein Mock-Theater, kein Dateiinhalt-Check.

## Definition of Done

- AC-1 bis AC-7 durch Kern-Tests gruen, Bestandstests unveraendert gruen (Golden, 3332 Payload und Verdrahtung, Infobox).
- Alle in AC-6 genannten Mutationen werden von mindestens einem Test gefangen.
- Alle 6 CI-Checks gruen; Staging: Trip mit Standardwerten angelegt, Reiter Zustellung zeigt 07:00/18:00, beide Briefings an, nur E-Mail an.
- Produktion ausgeliefert, Selftest Exit 0.

## Known Limitations

- Aussen vor: Loeschen der Alt-Bausteine (#3020), Literale 07:00/18:00 in `compareEditorSave.ts`, `versandVergleichSpeicherung.ts`, `versandPropsAus.ts` und Python `loader.py`, das Schein-Objekt in `MailInhaltCard.svelte` (faellt mit #3020). `baueReportConfigPayload` und alle Signaturen bleiben.
- Nicht geprueft: ob Bestandsdaten eine leere Zeit tragen (beruehrt den Umbau nicht, nur den Anlege-Weg); der Compare-Paritaetstest ist nicht Teil des Umfangs.
- Rund 40 Tests lesen die Alt-Bausteine und werden nicht angefasst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Umbau ohne Aenderung von Kanaelen, Providern, Datenmodell, Auth, Editor-Paradigma oder Test-/Deploy-Strategie. Er folgt dem bestehenden Muster "eine Funktion statt Doppelung" (`reportSlotAktiv`, `anlegeVorbelegung.ts`) und widerspricht keinem ADR.

## Changelog

- 2026-11-25: Initial spec created
