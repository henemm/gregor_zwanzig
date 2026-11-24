# Adversary Dialog — feat-3305-tabelle-trip-anlegen
Spec: docs/specs/modules/feat_3305_tabelle_trip_anlegen.md
Datum: 2026-11-24 07:22

## Checkliste
- [ ] **Input:** Nutzer legt einen Trip an, wählt Metriken im Schritt Wetter, stellt in der Karte Haken, Formate, Reihenfolge und Schalter ein und legt den Trip an.
- [ ] **Output:** Genau ein `POST /api/trips` mit `display_config.placements` und den Schalterfeldern; der Reiter Wetter des neuen Trips zeigt genau das Eingestellte.
- [ ] **Side effects:** Nur lesende Vorschau-Aufrufe während des Anlegens; kein PUT, kein Speichern vor dem Anlegen.
- [ ] **AC-1:** Given ein angemeldeter Nutzer im Anlegen eines neuen Trips / When er den Schritt Wetter öffnet, in der Mobil- und in der Desktop-Ansicht / Then ist die Tabelle „Was steht wo“ mit den Schaltern darunter sichtbar, und ihr Stand (Haken, Formate, Reihenfolge, Schalter) bleibt beim Wechsel zwischen Mobil und Desktop und beim Weiter- und Zurückgehen der Schritte erhalten.
- [ ] **AC-2:** Given die Karte im Anlegen ist geöffnet / When der Nutzer einen Haken, ein Format oder die Reihenfolge ändert und den Trip anlegt / Then enthält der eine Anlege-POST diese Änderung in `display_config.placements` (Zeilen in der eingestellten Reihenfolge, Haken und Formate wie gesetzt).
- [ ] **AC-3:** Given die Karte im Anlegen ist geöffnet / When der Nutzer Nacht-Block, Etappen-Statistik, Vortagesvergleich, Mail-Format und Telegram-Kurzstil ändert und den Trip anlegt / Then stehen diese Werte im POST (`display_config.show_night_block`, `report_config.show_stage_stats`, `show_yesterday_comparison`, `email_format`, `telegram_style`), und Versandzeiten sowie Kanalwahl bleiben genau so, wie sie ohne Bedienung der Karte wären.
- [ ] **AC-4:** Given der Nutzer bedient die Karte im Anlegen / When er mehrere Änderungen macht und den Trip anlegt / Then gibt es bis zum Anlegen weder einen PUT noch einen Autosave, und beim Anlegen genau einen POST auf die Trip-Anlage.
- [ ] **AC-5:** Given die Karte zeigt eine Tabelle mit vom Nutzer gesetzten Haken, Formaten und Reihenfolge / When er im Schritt Wetter eine Metrik hinzufügt oder entfernt / Then kommt die Zeile der neuen Metrik hinzu bzw. die Zeile der entfernten entfällt, und alle übrigen Einstellungen (Haken, Formate, Reihenfolge) bleiben unverändert.
- [ ] **AC-6:** Given eine Vorschau-Anfrage ist unterwegs / When der Nutzer inzwischen einen Haken klickt oder die Metriken wechselt und danach die ältere Antwort eintrifft / Then überschreibt die späte Antwort den neueren Stand nicht, der Haken bleibt gesetzt und die Metrikliste entspricht dem letzten Stand.
- [ ] **AC-7:** Given der Nutzer öffnet den Schritt Wetter, ändert aber an der Karte nichts / When er den Trip anlegt / Then enthält der POST wie heute keine `rows` und keine Schalterfelder aus der Karte, und der Server baut die Tabelle aus der Grundauswahl.
- [ ] **AC-8:** Given ein Trip wurde mit geänderter Tabelle und geänderten Schaltern angelegt / When der Nutzer den Reiter Wetter dieses Trips öffnet / Then zeigt er dieselben Haken, Formate, Reihenfolge und Schalterwerte, die beim Anlegen eingestellt waren.
- [ ] **AC-9:** Given zwei verschiedene Nutzer A und B / When A einen Trip mit geänderter Tabelle anlegt / Then erscheint der Trip nur bei A, B sieht ihn und seine Einstellungen nicht, und die Vorschau beim Anlegen nutzt nur die Daten des jeweils angemeldeten Nutzers.
- [ ] **AC-10:** Given der Schritt Wetter im Anlegen ist geöffnet / When der Nutzer nur Haken, Formate, Reihenfolge oder Schalter ändert (keine Metrikänderung) / Then lädt keine neue Vorschau nach und es entsteht keine Endlosschleife; bei einer Metrikänderung genau ein entprelltes Nachladen.

## Dialog

### Runde 1
**Adversary:** 40 Tests (5 Dateien) gruen (adversary-test-output.txt). Runde-1/2-Mutationen wiederholt, alle gefangen (Originale per diff byte-gleich): M4 TripNewEditor.svelte:561, M5 :938/:1194, M6/M6b WetterTabInhalt.svelte:149-150, M8 WasStehtWoKarte.svelte:196, M13 :73, M10 WetterTabInhalt.svelte:322, F-A1 :140 (Aufruf nur ausserhalb Anlegen -> rot), F-A2 :331 (entwurf leer -> rot), F-A3 TripNewEditor.svelte:474 (Neuaufbau je Meldung -> rot), F-A3b WasStehtWoKarte.svelte:86 (`??=` -> `=` -> rot). Weitere 14 neue Mutationen gefangen (Entprellung wasStehtWoSpeicherung.ts:175, Version :145, PUT-Sperre :146, zumMitsenden :158, Rumpf :80, lokal-Schutz Karte :82, Differenz tripNewLogic.ts:351, placements-Merge :351, Feld-Meldung Karte:154, Fehlerzustand :102, grundauswahl-lokal :188, Mitfuehren :192, melde() :131, VORSCHAU_MS). UEBERLEBT: F-B1 `if (antwort) antwort = weg.reduce(antwortOhneZeile ...)` -> `if (false)` (WasStehtWoKarte.svelte:190): kein Test bewacht, dass die Ansicht (anzeige() = antwort.rows, :126) die Zeile einer entfernten Metrik sofort verliert; sie bleibt bis zur entprellten Vorschau (400 ms) sichtbar, bei gescheitertem Nachladen dauerhaft (Fehler mit vorhandener Antwort lässt Ansicht stehen, :100-103), und ein Klick darauf ruft mitHaken mit anzeige() inkl. entfernter Metrik.
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

### Runde 2
**Adversary:** Gegenprobe der Tests: die neuen Verdrahtungstests werten die echten Einbettungs-Ausdruecke und den echten api.post aus (kein Dateiinhalt-Theater); F-A1/F-A2/F-A3 jetzt jeweils mit eigenem Test rot-gruen belegt. Nachweise: unbediente Karte meldet nicht (AC-7, M6/M13 rot), kein PUT im Anlegen (Put-Mutation rot, AC-4), alte Antworten verworfen (Ver rot, AC-6), kein Nachladen ohne Metrikwechsel (M6b rot, AC-10). Unerreichbar/aequivalent: `!lokal` in melde() (K4). Keine Fehlfunktion ausser der Wirksamkeitsluecke F-B1. AC-1/8/9 offen fuer Staging (/e2e-verify), kein Defekt.
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

## Herkunft der Vorbedingungen

Kein Sprachprofil konfiguriert (`precondition_origins.default_lang`); Vorbedingungen stammen aus Spec und Auftrag, nicht aus Eigenmessung.

## Verdict
BROKEN (nur eine Wirksamkeitsluecke, LOW/MEDIUM)
Finding F-B1 MEDIUM edge_case, Code reference: frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:190 — Entfernen der Zeile aus der Ansicht (antwort) ungeprueft (AC-5); Mutation ueberlebt. Remediation: Test, der nach grundauswahlGeaendert(weg) ohne Vorschau-Antwort die Ansicht ohne die Zeile prueft.
Confirmed: AC-2/3/4/5(lokaler Stand)/6/7/10; Offen fuer Staging: AC-1, AC-8, AC-9.
