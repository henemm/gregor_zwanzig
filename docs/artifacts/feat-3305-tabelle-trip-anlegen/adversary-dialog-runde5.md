# Adversary Dialog — feat-3305-tabelle-trip-anlegen
Spec: docs/specs/modules/feat_3305_tabelle_trip_anlegen.md
Datum: 2026-11-24 08:33

## Checkliste
- [x] **Input:** Nutzer legt einen Trip an, wählt Metriken im Schritt Wetter, stellt in der Karte Haken, Formate, Reihenfolge und Schalter ein und legt den Trip an. Beweis: Verdrahtungs- und Payload-Test, Mutationen M4 (TripNewEditor.svelte:561) und M5 rot; 41 Frontend-Tests erneut gruen.
- [x] **Output:** Genau ein `POST /api/trips` mit `display_config.placements` und den Schalterfeldern; der Reiter Wetter des neuen Trips zeigt genau das Eingestellte. Beweis: Verdrahtungs- und Payload-Test, Mutationen M4 (TripNewEditor.svelte:561) und M5 rot; 41 Frontend-Tests erneut gruen.
- [x] **Side effects:** Nur lesende Vorschau-Aufrufe während des Anlegens; kein PUT, kein Speichern vor dem Anlegen. Beweis: PUT-Sperre (wasStehtWoSpeicherung.ts:146) rot; Vorschau-Fix schreibt nichts (test_3305 Dateibaum vorher gleich nachher).
- [x] **AC-1:** Given ein angemeldeter Nutzer im Anlegen eines neuen Trips / When er den Schritt Wetter öffnet, in der Mobil- und in der Desktop-Ansicht / Then ist die Tabelle „Was steht wo“ mit den Schaltern darunter sichtbar, und ihr Stand (Haken, Formate, Reihenfolge, Schalter) bleibt beim Wechsel zwischen Mobil und Desktop und beim Weiter- und Zurückgehen der Schritte erhalten. Teilbeleg: Remount-Test, POST-Verdrahtung M4; Vorschau fuer fruehen Entwurf liefert 200 statt 422 (test_3305). Live-Nachweis gegen Staging in /e2e-verify.
- [x] **AC-2:** Given die Karte im Anlegen ist geöffnet / When der Nutzer einen Haken, ein Format oder die Reihenfolge ändert und den Trip anlegt / Then enthält der eine Anlege-POST diese Änderung in `display_config.placements` (Zeilen in der eingestellten Reihenfolge, Haken und Formate wie gesetzt). Beweis: Frontend-Mutationen Runde 4 (M4, M6, M6b, M13, F-B1, :145, :175) rot; Frontend-Code unveraendert, 41 Tests gruen.
- [x] **AC-3:** Given die Karte im Anlegen ist geöffnet / When der Nutzer Nacht-Block, Etappen-Statistik, Vortagesvergleich, Mail-Format und Telegram-Kurzstil ändert und den Trip anlegt / Then stehen diese Werte im POST (`display_config.show_night_block`, `report_config.show_stage_stats`, `show_yesterday_comparison`, `email_format`, `telegram_style`), und Versandzeiten sowie Kanalwahl bleiben genau so, wie sie ohne Bedienung der Karte wären. Beweis: Frontend-Mutationen Runde 4 (M4, M6, M6b, M13, F-B1, :145, :175) rot; Frontend-Code unveraendert, 41 Tests gruen.
- [x] **AC-4:** Given der Nutzer bedient die Karte im Anlegen / When er mehrere Änderungen macht und den Trip anlegt / Then gibt es bis zum Anlegen weder einen PUT noch einen Autosave, und beim Anlegen genau einen POST auf die Trip-Anlage. Beweis: Frontend-Mutationen Runde 4 (M4, M6, M6b, M13, F-B1, :145, :175) rot; Frontend-Code unveraendert, 41 Tests gruen.
- [x] **AC-5:** Given die Karte zeigt eine Tabelle mit vom Nutzer gesetzten Haken, Formaten und Reihenfolge / When er im Schritt Wetter eine Metrik hinzufügt oder entfernt / Then kommt die Zeile der neuen Metrik hinzu bzw. die Zeile der entfernten entfällt, und alle übrigen Einstellungen (Haken, Formate, Reihenfolge) bleiben unverändert. Beweis: Frontend-Mutationen Runde 4 (M4, M6, M6b, M13, F-B1, :145, :175) rot; Frontend-Code unveraendert, 41 Tests gruen.
- [x] **AC-6:** Given eine Vorschau-Anfrage ist unterwegs / When der Nutzer inzwischen einen Haken klickt oder die Metriken wechselt und danach die ältere Antwort eintrifft / Then überschreibt die späte Antwort den neueren Stand nicht, der Haken bleibt gesetzt und die Metrikliste entspricht dem letzten Stand. Beweis: Frontend-Mutationen Runde 4 (M4, M6, M6b, M13, F-B1, :145, :175) rot; Frontend-Code unveraendert, 41 Tests gruen.
- [x] **AC-7:** Given der Nutzer öffnet den Schritt Wetter, ändert aber an der Karte nichts / When er den Trip anlegt / Then enthält der POST wie heute keine `rows` und keine Schalterfelder aus der Karte, und der Server baut die Tabelle aus der Grundauswahl. Beweis: Frontend-Mutationen Runde 4 (M4, M6, M6b, M13, F-B1, :145, :175) rot; Frontend-Code unveraendert, 41 Tests gruen.
- [x] **AC-8:** Given ein Trip wurde mit geänderter Tabelle und geänderten Schaltern angelegt / When der Nutzer den Reiter Wetter dieses Trips öffnet / Then zeigt er dieselben Haken, Formate, Reihenfolge und Schalterwerte, die beim Anlegen eingestellt waren. Teilbeleg: Remount-Test, POST-Verdrahtung M4; Vorschau fuer fruehen Entwurf liefert 200 statt 422 (test_3305). Live-Nachweis gegen Staging in /e2e-verify.
- [x] **AC-9:** Given zwei verschiedene Nutzer A und B / When A einen Trip mit geänderter Tabelle anlegt / Then erscheint der Trip nur bei A, B sieht ihn und seine Einstellungen nicht, und die Vorschau beim Anlegen nutzt nur die Daten des jeweils angemeldeten Nutzers. Teilbeleg: Vorschau nutzt nur Daten des angemeldeten Nutzers (test_3304 AC-5 gruen, Fix liest nichts, schreibt nichts). Live-Nachweis gegen Staging in /e2e-verify.
- [x] **AC-10:** Given der Schritt Wetter im Anlegen ist geöffnet / When der Nutzer nur Haken, Formate, Reihenfolge oder Schalter ändert (keine Metrikänderung) / Then lädt keine neue Vorschau nach und es entsteht keine Endlosschleife; bei einer Metrikänderung genau ein entprelltes Nachladen. Beweis: Frontend-Mutationen Runde 4 (M4, M6, M6b, M13, F-B1, :145, :175) rot; Frontend-Code unveraendert, 41 Tests gruen.

## Dialog

### Runde 1
**Adversary:** 41 Frontend-Tests (5 *3305*-Dateien) und 40 Python-Tests (test_3305_vorschau_entwurf_frueh 7, test_3304_placements_vorschau 33) gruen (adversary-test-output.txt). Der Fix `_mit_platzhalter_datum` wird nur aus `_entwurf_trip` gerufen, das nur `build_placements_preview` (POST Vorschau) nutzt; GET (`_trip_abo`), Erstanlage und Trip-Anlage beruehren den Pfad nicht. Mutationen am Dienst (src/services/placements_view_service.py:164): M1 Aufruf entfernt rot; M2 None nicht ersetzt rot; M3 leer nicht ersetzt rot; M4 jedes Datum ersetzt rot (datum-zahl); M7 ungueltiges Platzhalterdatum rot; M8 In-place-Aenderung rot (Aufrufer-Entwurf). Original per diff byte-gleich zurueck.

**Implementierer:** (nicht erreichbar, Kontext-Isolation)

### Runde 2
**Adversary:** Ueberlebende Mutationen: M5 (Platzhalter auch fuer Etappen MIT Datum, placements_view_service.py:154: gemischte Liste aus leerer und unlesbarer Etappe wuerde 200 statt 422 liefern; kein Test mit gemischter Liste), M6 (festes altes Datum statt heute; Tabelle haengt nicht am Datum), M9/M10/M11 aequivalent (Fehler wird weiter zu 422). Alle ohne Auswirkung auf Anlege-POST oder Nutzerdaten, daher LOW. Cross-User: Vorschau liest nur `user_id` des Aufrufs, der Trip-Zweig liest keine Nutzerdaten; test_3304 AC-5 gruen.
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

## Herkunft der Vorbedingungen

Kein Sprachprofil konfiguriert (`precondition_origins.default_lang`); Vorbedingungen stammen aus Spec und Auftrag, nicht aus Eigenmessung.

## Verdict
VERDICT: VERIFIED
Finding F-D1 LOW edge_case, Ort: src/services/placements_view_service.py:154 -- Mutationen M5 (Platzhalter fuer alle Etappen) und M6 (festes statt heutiges Datum) ueberleben; gemischte Etappenliste (leer + unlesbar) ungetestet. Remediation optional: Test mit gemischter Liste.
Confirmed: AC-2/3/4/5/6/7/10; AC-1/8/9 offen fuer Staging (/e2e-verify). Alle 6 Produktionsdateien geprueft.
Tests: 81 passed, 0 failed.

Code reference: frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts:146

Code reference: frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:190

Code reference: frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:140

Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:561

Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:351

Code reference: src/services/placements_view_service.py:164

## Geprüfte Dateien

- sha256:921e32a91179fb0c99be0e55a7d1631bdd890a1d01a5dca63734d501119de5b3  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
- sha256:42383239d0180c0d7a7556b8b95eb169f15d7857618858da18d15fa036c0557a  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- sha256:48f09c3ca52751b31217d62137dccfa98ebf389854f1871be22a28847268f7cc  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- sha256:7632d67c23b9bccf545264c9b7c30f8175922bea48af2ddcae9577634cc0a03a  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- sha256:9082bbcf8e1fa3b03630cf65cb57f8975fddfd442b934d9985aea22218d45f06  frontend/src/lib/components/trip-new/tripNewLogic.ts
- sha256:dbd6c9865e7c5dc23872693b788d686af1374eb34c69db117d9367c8d928de1d  src/services/placements_view_service.py

## Prüfbasis

- base: 48e6f90f08b8525d8e9104b0691cf7d7de8b31da
- blob:dbb60bd7878269cf24244c39001e5e1576688f8b  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
- blob:e83195382d12b5b527cf957ed86cc47d6041cfc0  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- blob:a137c9006b0b223ef0641133833ed34b27266e64  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- blob:f17640cd7a2b84383dd94502211d2e2623acd726  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- blob:877f4f57f108b10126a1d975fed8353783867ab9  frontend/src/lib/components/trip-new/tripNewLogic.ts
- blob:ea823237380b9b5481600d857b199a87c2786342  src/services/placements_view_service.py
