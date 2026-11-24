# Adversary Dialog — feat-3305-tabelle-trip-anlegen
Spec: docs/specs/modules/feat_3305_tabelle_trip_anlegen.md
Datum: 2026-11-24 07:02

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
**Adversary:** Tests 5 Dateien, 37 Tests gruen (adversary-test-output.txt). Die sechs frueheren Ueberlebenden sind gefangen (selbst wiederholt, Originale per diff byte-gleich zurueck): M4 karte aus POST (TripNewEditor.svelte:561, rot 3), M5 karteStart je Einbettung (TripNewEditor.svelte:938/1194, rot je 1), M6 vorschauNachMetrik-Aufruf und Metrik-Bedingung (WetterTabInhalt.svelte:149, rot), M8 `if (bedient)` (WasStehtWoKarte.svelte:196, rot), M13 bedient-Init (WasStehtWoKarte.svelte:73, rot), M10 Kartenbedingung (WetterTabInhalt.svelte:322, rot). F007 behoben: Mutationen F7a/F7b/StartF/S2 (WasStehtWoKarte.svelte:188, wasStehtWoSpeicherung.ts:119) rot; Fehlerzustand bei gescheitertem Nachladen: Mutationen Fehler/Fehler2/Fehler3 (WasStehtWoKarte.svelte:102, wasStehtWoSpeicherung.ts:174) rot. Verdrahtungstests sind kein Dateiinhalt-Theater: sie werten die echten Instanz-Skripte und die echten Attribut-Ausdruecke der Einbettungen aus und schneiden den echten api.post von buildAndSave mit. Weitere 33 Mutationen (Entprellung, Version, RMW, Differenz, Report-Config, Zeitgeber, Merge, Rumpf, mitsenden u. a.) gefangen. UEBERLEBT: (a) W4 `grundauswahlGeaendert` im Reiter nur ausserhalb des Anlegens rufen (WetterTabInhalt.svelte:140): kein Test, die Verdrahtung Reiter -> Karte fuer AC-5 im Anlegen wird nur mit Doppel-Karte (vorschauNachMetrik) geprueft; ohne den Aufruf bleiben im Anlegen Zeilen entfernter Metriken im lokalen Stand (lokal wird in createMode von der Vorschau nie ersetzt, WasStehtWoKarte.svelte:82). (b) Entwurf `entwurf={() => ({})}` (WetterTabInhalt.svelte:331): kein Test prueft den Vorschau-Rumpf ueber die echte Einbettung; Vorschau bekaeme keine Metriken. (c) FS `felderStart ??=` -> `=` (WasStehtWoKarte.svelte:86): kein Test; wirkungsgleich, solange Vorschau-Schalter aus dem Entwurf stammen. (d) E1 jede Karten-Meldung loest wetterNeuaufbau aus (TripNewEditor.svelte:474): Tests gruen trotz Neuaufbau je Klick. (e) K4 `!lokal` in melde() (WasStehtWoKarte.svelte:154): aequivalent, nicht erreichbar.
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

### Runde 2
**Adversary:** Abweichungen gesucht an den geaenderten Stellen: Fehlerzustand ohne Antwort zeigt Fehler (Zeile 234), mit Antwort bleibt Ansicht; Metrikwechsel vor erster Antwort und aeltere Antwort danach beide verworfen (Version zaehlt hoch); unbediente Karte meldet nichts (AC-7); Reihenfolge Melden -> Nachladen belegt (nachladen[0] ohne entfernte Metrik). Keine Fehlfunktion im Produktivcode gefunden, nur die Wirksamkeitsluecken (a) bis (d). AC-1/8/9 offen fuer Staging (/e2e-verify), kein Defekt.
**Implementierer:** (nicht erreichbar, Kontext-Isolation)

## Herkunft der Vorbedingungen

Kein Sprachprofil konfiguriert (`precondition_origins.default_lang`); Vorbedingungen (Nutzer angemeldet, Trip im Anlegen, Staging-Stack) stammen aus Spec und Auftrag, nicht aus Eigenmessung.

## Verdict
BROKEN (Testluecken, kein belegter Funktionsdefekt; Wirkungsluecke F-A1 MEDIUM)
Finding F-A1 MEDIUM edge_case, Code reference: frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:140 — Aufruf karte.grundauswahlGeaendert im Anlegen ungeprueft (AC-5), Mutation ueberlebt.
Finding F-A2 MEDIUM edge_case, Code reference: frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:331 — entwurf-Verdrahtung der Vorschau ungeprueft (AC-10), Mutation ueberlebt.
Finding F-A3 LOW, Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:474 — Neuaufbau je Kartenmeldung nicht bewacht; frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:86 — felderStart ??= nicht bewacht.
Confirmed: AC-2/3/4/5/6/7/10 (Einheit + Verdrahtung), F007 behoben. Offen fuer Staging: AC-1, AC-8, AC-9.
