# Adversary Dialog — feat-3305-tabelle-trip-anlegen
Spec: docs/specs/modules/feat_3305_tabelle_trip_anlegen.md
Datum: 2026-11-24 06:42

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
**Adversary:** Tests (3 Dateien, 23 Tests) gruen, Ausgabe in adversary-test-output.txt. Mutations-Gegenprobe (14 String-Ersetzungen, Originale per diff byte-gleich zurueck). Gefangen: M1 melde() in aendern, M2 feld-Zweig, M3 anlegen-Return (PUT), M7 lokal-Ueberschreiben, M9 Entprellung, M11 Schalter-Diff, M12 Schleife, M14 Vorschau-Rumpf. UEBERLEBT: M4 `karte: karteStand` aus dem POST (TripNewEditor.svelte:561), M5 `karteStart` nicht uebergeben (TripNewEditor.svelte:938/1194), M6 vorschauNachMetrik-Aufruf (WetterTabInhalt.svelte:149), M8 `if (bedient) melde()` -> unbedingt (WasStehtWoKarte.svelte:187), M13 bedient-Init immer true (WasStehtWoKarte.svelte:73), M10 Kartenbedingung `createMode || aboId` (WetterTabInhalt.svelte:322). Alle ueberlebenden Stellen sind Verdrahtung dort, wo der Nutzer sie erreicht; Tests pruefen nur Einzelteile (buildCreateTripPayload, Speicherung), nicht den Weg Karte -> Editor -> POST.
F001 MEDIUM edge_case WasStehtWoKarte.svelte:179/80: grundauswahlGeaendert kehrt bei antwort==null zurueck; Metrikwechsel waehrend der ersten Vorschau-Ladephase (auch nach Remount mit start) geht fuer `lokal` verloren; spaetere Vorschau ersetzt lokal nie (Zeile 80). Stand im POST kann Zeile entfernter Metrik enthalten bzw. neue vermissen (Server ignoriert Unbekannte laut #3122-Regel, daher kein belegter Datenfehler).
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

### Runde 2
**Adversary:** Abweichungen: (1) Kartenbedingung korrekt (Orte zeigt keine Karte), aber Mutation M10 unbewacht. (2) Remount: start wird per untrack uebernommen, bedient=true; Schalter-only meldet ueber feld()->melde() (M2 gefangen). Mobil/Desktop-Wechsel haengt an karteStart, M5 unbewacht. (3) Nachladen nach melden(): Reihenfolge nicht getestet (Vorschau-Entwurf ohne neue Auswahl moeglich, Mutation Reihenfolge nicht durchgespielt). (4) Rumpf __new__: M14 gefangen. AC-1/8/9 offen fuer Staging (/e2e-verify), kein Defekt.
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

## Herkunft der Vorbedingungen

Kein Sprachprofil konfiguriert (`precondition_origins.default_lang`); Vorbedingungen (Nutzer angemeldet, Trip im Anlegen, Staging-Stack) stammen aus Spec und Auftrag, nicht aus Eigenmessung.

## Verdict
BROKEN (Testluecken, kein belegter Funktionsdefekt)
Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:561; frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:149,322; frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:73,187; frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts:144; frontend/src/lib/components/trip-new/tripNewLogic.ts:342
Confirmed (Code+Test): AC-2/AC-3/AC-4/AC-5/AC-6/AC-10 auf Einheitenebene. Offen fuer Staging: AC-1, AC-8, AC-9. AC-7 nur auf Payload-Ebene (M8/M13 ueberlebt).
