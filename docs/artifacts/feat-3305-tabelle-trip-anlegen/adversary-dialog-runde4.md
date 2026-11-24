# Adversary Dialog — feat-3305-tabelle-trip-anlegen
Spec: docs/specs/modules/feat_3305_tabelle_trip_anlegen.md
Datum: 2026-11-24 07:34

## Checkliste
- [x] **Input:** Nutzer legt einen Trip an, wählt Metriken im Schritt Wetter, stellt in der Karte Haken, Formate, Reihenfolge und Schalter ein und legt den Trip an. Beweis: Verdrahtungs- und Payload-Test, Mutationen M4 (TripNewEditor.svelte:561) und M5 rot.
- [x] **Output:** Genau ein `POST /api/trips` mit `display_config.placements` und den Schalterfeldern; der Reiter Wetter des neuen Trips zeigt genau das Eingestellte. Beweis: Verdrahtungs- und Payload-Test, Mutationen M4 (TripNewEditor.svelte:561) und M5 rot.
- [x] **Side effects:** Nur lesende Vorschau-Aufrufe während des Anlegens; kein PUT, kein Speichern vor dem Anlegen. Beweis: PUT-Sperre-Mutation (wasStehtWoSpeicherung.ts:146) rot.
- [x] **AC-1:** Given ein angemeldeter Nutzer im Anlegen eines neuen Trips / When er den Schritt Wetter öffnet, in der Mobil- und in der Desktop-Ansicht / Then ist die Tabelle „Was steht wo“ mit den Schaltern darunter sichtbar, und ihr Stand (Haken, Formate, Reihenfolge, Schalter) bleibt beim Wechsel zwischen Mobil und Desktop und beim Weiter- und Zurückgehen der Schritte erhalten. Teilbeleg: Remount-Test M5, POST-Verdrahtung M4, Vorschau-Rumpf ohne user_id/fremde Daten. Live-Nachweis gegen Staging in /e2e-verify (E2E trip-anlegen-was-steht-wo-3305.spec.ts).
- [x] **AC-2:** Given die Karte im Anlegen ist geöffnet / When der Nutzer einen Haken, ein Format oder die Reihenfolge ändert und den Trip anlegt / Then enthält der eine Anlege-POST diese Änderung in `display_config.placements` (Zeilen in der eingestellten Reihenfolge, Haken und Formate wie gesetzt). Beweis: Mutationen am Pruefort rot (M4, M6, M6b, M13, F-B1, Version :145, Entprellung :175).
- [x] **AC-3:** Given die Karte im Anlegen ist geöffnet / When der Nutzer Nacht-Block, Etappen-Statistik, Vortagesvergleich, Mail-Format und Telegram-Kurzstil ändert und den Trip anlegt / Then stehen diese Werte im POST (`display_config.show_night_block`, `report_config.show_stage_stats`, `show_yesterday_comparison`, `email_format`, `telegram_style`), und Versandzeiten sowie Kanalwahl bleiben genau so, wie sie ohne Bedienung der Karte wären. Beweis: Mutationen am Pruefort rot (M4, M6, M6b, M13, F-B1, Version :145, Entprellung :175).
- [x] **AC-4:** Given der Nutzer bedient die Karte im Anlegen / When er mehrere Änderungen macht und den Trip anlegt / Then gibt es bis zum Anlegen weder einen PUT noch einen Autosave, und beim Anlegen genau einen POST auf die Trip-Anlage. Beweis: Mutationen am Pruefort rot (M4, M6, M6b, M13, F-B1, Version :145, Entprellung :175).
- [x] **AC-5:** Given die Karte zeigt eine Tabelle mit vom Nutzer gesetzten Haken, Formaten und Reihenfolge / When er im Schritt Wetter eine Metrik hinzufügt oder entfernt / Then kommt die Zeile der neuen Metrik hinzu bzw. die Zeile der entfernten entfällt, und alle übrigen Einstellungen (Haken, Formate, Reihenfolge) bleiben unverändert. Beweis: Mutationen am Pruefort rot (M4, M6, M6b, M13, F-B1, Version :145, Entprellung :175).
- [x] **AC-6:** Given eine Vorschau-Anfrage ist unterwegs / When der Nutzer inzwischen einen Haken klickt oder die Metriken wechselt und danach die ältere Antwort eintrifft / Then überschreibt die späte Antwort den neueren Stand nicht, der Haken bleibt gesetzt und die Metrikliste entspricht dem letzten Stand. Beweis: Mutationen am Pruefort rot (M4, M6, M6b, M13, F-B1, Version :145, Entprellung :175).
- [x] **AC-7:** Given der Nutzer öffnet den Schritt Wetter, ändert aber an der Karte nichts / When er den Trip anlegt / Then enthält der POST wie heute keine `rows` und keine Schalterfelder aus der Karte, und der Server baut die Tabelle aus der Grundauswahl. Beweis: Mutationen am Pruefort rot (M4, M6, M6b, M13, F-B1, Version :145, Entprellung :175).
- [x] **AC-8:** Given ein Trip wurde mit geänderter Tabelle und geänderten Schaltern angelegt / When der Nutzer den Reiter Wetter dieses Trips öffnet / Then zeigt er dieselben Haken, Formate, Reihenfolge und Schalterwerte, die beim Anlegen eingestellt waren. Teilbeleg: Remount-Test M5, POST-Verdrahtung M4, Vorschau-Rumpf ohne user_id/fremde Daten. Live-Nachweis gegen Staging in /e2e-verify (E2E trip-anlegen-was-steht-wo-3305.spec.ts).
- [x] **AC-9:** Given zwei verschiedene Nutzer A und B / When A einen Trip mit geänderter Tabelle anlegt / Then erscheint der Trip nur bei A, B sieht ihn und seine Einstellungen nicht, und die Vorschau beim Anlegen nutzt nur die Daten des jeweils angemeldeten Nutzers. Teilbeleg: Remount-Test M5, POST-Verdrahtung M4, Vorschau-Rumpf ohne user_id/fremde Daten. Live-Nachweis gegen Staging in /e2e-verify (E2E trip-anlegen-was-steht-wo-3305.spec.ts).
- [x] **AC-10:** Given der Schritt Wetter im Anlegen ist geöffnet / When der Nutzer nur Haken, Formate, Reihenfolge oder Schalter ändert (keine Metrikänderung) / Then lädt keine neue Vorschau nach und es entsteht keine Endlosschleife; bei einer Metrikänderung genau ein entprelltes Nachladen. Beweis: Mutationen am Pruefort rot (M4, M6, M6b, M13, F-B1, Version :145, Entprellung :175).

## Dialog

### Runde 1
**Adversary:** 41 Tests (5 Dateien) gruen (adversary-test-output.txt). F-B1 bestaetigt behoben: `if (antwort) antwort = weg.reduce(...)` -> `if (false)` (WasStehtWoKarte.svelte:190) laesst jetzt 1 Test rot (fixloop1-Test); N6 (reduce -> `antwort`, :190) 1 rot; N2 (`if (bedient) melde()` -> immer, :192) 1 rot; N3 (`lokal = S.mitGrundauswahl` entfernt, :188) 4 rot. Fruehere Mutationen stichprobenartig in Runde 3 wiederholt gefangen. Originale per Vergleich byte-gleich zurueck. Produktionsdateien geprueft: wasStehtWoSpeicherung.ts:80/:145/:158/:175, WasStehtWoKarte.svelte:73/:86/:131/:154/:188-192, WetterTabInhalt.svelte:140/:149/:322/:331, TripNewEditor.svelte:474/:561/:938, tripNewLogic.ts:351.
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

### Runde 2
**Adversary:** Neue Mutationen an grundauswahlGeaendert ueberlebten: N1 Guard `!createMode && (...)` -> `if (false) return` (WasStehtWoKarte.svelte:183; wirkt nur im Nicht-Anlegen-Modus ohne gespeicherte Tabelle, dort ruft sie dann mitgefuehrt() statt zu enden); N4 `meldung = null` entfernt (:189, alte Fehlermeldung bleibt nach Metrikwechsel); N5 No-Op-Frueh-Return `if (!weg.length && ...) return` entfernt (:185, bei vorher==nachher unnoetiges mitgefuehrt()/melde()). Alle drei sind Randverhalten ohne Datenfolge im Anlegen (Aufrufer WetterTabInhalt.svelte:140 ruft nur bei geaenderter Auswahl), daher LOW. AC-1/8/9 offen fuer Staging (/e2e-verify), kein Defekt.
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

## Herkunft der Vorbedingungen

Kein Sprachprofil konfiguriert (`precondition_origins.default_lang`); Vorbedingungen stammen aus Spec und Auftrag, nicht aus Eigenmessung.

## Verdict
VERDICT: VERIFIED
Finding F-C1 LOW edge_case, Ort: frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:183-192 — Mutationen N1/N4/N5 (Guard, meldung=null, No-Op-Return) ungeprueft; ohne Auswirkung auf Anlege-POST. Remediation optional: Tests fuer Nicht-Anlegen-Fruehreturn und Fehlermeldungs-Reset.
Confirmed: AC-2/3/4/5/6/7/10 (auch F-B1 jetzt bewacht); offen fuer Staging: AC-1, AC-8, AC-9.
Tests: 41 passed, 0 failed.

Code reference: frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts:146

Code reference: frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:190

Code reference: frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:140

Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:561

Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:351

Code reference: frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:183

## Geprüfte Dateien

- sha256:921e32a91179fb0c99be0e55a7d1631bdd890a1d01a5dca63734d501119de5b3  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
- sha256:42383239d0180c0d7a7556b8b95eb169f15d7857618858da18d15fa036c0557a  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- sha256:48f09c3ca52751b31217d62137dccfa98ebf389854f1871be22a28847268f7cc  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- sha256:7632d67c23b9bccf545264c9b7c30f8175922bea48af2ddcae9577634cc0a03a  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- sha256:9082bbcf8e1fa3b03630cf65cb57f8975fddfd442b934d9985aea22218d45f06  frontend/src/lib/components/trip-new/tripNewLogic.ts

## Prüfbasis

- base: 48e6f90f08b8525d8e9104b0691cf7d7de8b31da
- blob:dbb60bd7878269cf24244c39001e5e1576688f8b  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
- blob:e83195382d12b5b527cf957ed86cc47d6041cfc0  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- blob:a137c9006b0b223ef0641133833ed34b27266e64  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- blob:f17640cd7a2b84383dd94502211d2e2623acd726  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- blob:877f4f57f108b10126a1d975fed8353783867ab9  frontend/src/lib/components/trip-new/tripNewLogic.ts
