# Adversary Dialog — feat-3306-tabelle-orte-anlegen
Spec: docs/specs/modules/feat_3306_tabelle_orte_anlegen.md
Datum: 2026-11-24 11:38

## Checkliste
- [x] **Input:** Nutzer legt einen Ortsvergleich an, wählt Orte, stellt im Schritt Wetter Haken, Formate, Reihenfolge und Schalter (Stundenverlauf, Ausblick, Telegram-Kurzstil) in der Tabelle ein und legt an.
- [x] **Output:** Genau ein `POST` auf die Ortsvergleich-Anlage mit `display_config.placements`, `hourly_enabled` und `display_config.telegram_style`; der Reiter Wetter des neuen Ortsvergleichs zeigt genau das Eingestellte.
- [x] **Side effects:** Nur lesende Vorschau-Aufrufe während des Anlegens; kein PUT, kein Speichern vor dem Anlegen.
- [x] **AC-1:** Given ein angemeldeter Nutzer legt einen neuen Ortsvergleich an und hat Orte gewählt / When er den Schritt Wetter öffnet, in der Mobil- und in der Desktop-Ansicht / Then ist die Tabelle „Was steht wo“ mit den Schaltern Stundenverlauf, Ausblick und Telegram-Kurzstil sichtbar, zeigt Beispielwerte der gewählten Orte, und ihr Stand bleibt beim Wechsel zwischen Mobil und Desktop sowie beim Weiter- und Zurückgehen der Schritte erhalten.
- [x] **AC-2:** Given die Karte im Anlegen ist geöffnet / When der Nutzer einen Haken, ein Format oder die Reihenfolge ändert und den Ortsvergleich anlegt / Then enthält der eine Anlege-POST diese Änderung in `display_config.placements` (Zeilen in der eingestellten Reihenfolge, Haken und Formate wie gesetzt).
- [x] **AC-3:** Given die Karte im Anlegen ist geöffnet / When der Nutzer Stundenverlauf, Ausblick und Telegram-Kurzstil ändert und anlegt / Then stehen im POST `hourly_enabled`, `display_config.telegram_style` und der Ausblick als `outlook_reports` in der Tabelle, Versandzeiten und Kanalwahl bleiben wie ohne Kartenbedienung, und der POST enthält keinen der Altschlüssel (`channel_layouts`, `outlook_metrics`, `outlook_metric_formats`, `channel_active_metrics`, `hourly_metrics`, `hourly_metric_formats`).
- [x] **AC-4:** Given der Nutzer bedient die Karte im Anlegen / When er mehrere Änderungen macht und den Ortsvergleich anlegt / Then gibt es bis zum Anlegen weder einen PUT noch einen Autosave, und beim Anlegen genau einen POST auf die Ortsvergleich-Anlage.
- [x] **AC-5:** Given der Nutzer öffnet den Schritt Wetter, ändert aber an der Karte nichts / When er den Ortsvergleich anlegt / Then enthält der POST wie heute keine `rows` und keine Schalterfelder aus der Karte, und der Server baut die Tabelle aus der Grundauswahl.
- [x] **AC-6:** Given ein Ortsvergleich wurde mit geänderter Tabelle und geänderten Schaltern angelegt / When der Nutzer den Reiter Wetter dieses Ortsvergleichs öffnet / Then zeigt er dieselben Haken, Formate, Reihenfolge und Schalterwerte, die beim Anlegen eingestellt waren.
- [x] **AC-7:** Given zwei verschiedene Nutzer A und B, B besitzt eigene Orte / When A einen Ortsvergleich mit geänderter Tabelle anlegt und dabei eine Orts-Kennung von B in der Vorschau mitschickt / Then erscheint der Ortsvergleich nur bei A, die Vorschau rechnet nur mit den Orten von A (Orte von B fallen weg), und B sieht den Ortsvergleich von A nicht.
- [x] **AC-8:** Given die Vorschau für Ortsvergleiche bekommt einen frühen Entwurf / When der Entwurf weder Namen noch Zeitplan hat und die Ortsliste leer oder gesetzt ist / Then antwortet die Vorschau mit Erfolg und einer Ansicht statt mit einem Fehler.
- [x] **AC-9:** Given die Karte im Anlegen zeigt Stundenverlauf oder Telegram-Kurzstil und der Altblock im Schritt Zustellung kann dieselben Schalter setzen / When der Nutzer einen Schalter nur im Altblock ändert und die Karte nicht bedient / Then gilt im POST der Wert des Altblocks, und wenn er den Schalter in der Karte gegenüber ihrem Start ändert, gilt der Wert der Karte.

## Dialog

### Runde 1
**Adversary:**
Baseline: node --test (payload + Verdrahtung) 22 pass / 0 fail; pytest tests/tdd/test_3306_vorschau_vergleich_entwurf_frueh.py 8 passed. E2E nur gelesen: VA-1..VA-5 decken AC-1..AC-7 ab (POST-Zaehlung, kein PUT, Altschluessel, Rueckweg, zwei Nutzer).
Mutations-Gegenprobe (String-Ersetzung, Sicherungskopie im Scratchpad, md5 danach identisch zum Original), 16 Mutationen, Zielsuite beide node-Dateien:
0 mitKarte-Aufruf entfernt: 13 fail. 1 mitKarte nur wenn ampel gesetzt: 1 fail. 2 placements weggelassen: 11 fail. 3 felderNutzlast gegen leeren Start (Vollwerte statt Differenz): 1 fail. 4 Object.assign(rest) entfernt (hourly_enabled/telegram_style): 8 fail. 5 display_config-Diff (telegram_style) weg: 7 fail. 6 Read-Modify-Write verworfen (Ampel/Auswahl ueberschrieben): 4 fail. 7 karte nicht an legeVergleichAn: 5 fail. 8 location_ids aus wetterAbo: 2 fail. 9 hourly_enabled aus wetterAbo: 2 fail. 10 telegram_style aus wetterAbo: 2 fail. 11 karteStart nur Desktop entfernt: 3 fail. 12 onAnlegeKarte Desktop entfernt: 6 fail. 13 karteStart Mobil entfernt: 2 fail. 14 onAnlegeKarte Mobil entfernt: 3 fail. 15 handleKarteStand verschluckt Stand: 5 fail.
Ergebnis: alle 16 Mutationen werden gefangen, keine ueberlebt. Wirkort geprueft: die Verdrahtungstests laufen ueber die echten Instanz-Skripte von Editor und Karte bis zum echten legeVergleichAn (nicht nur an der Hilfsfunktion).
Randfaelle: AC-5 (Karte nie bedient, kein rows) per Verdrahtungstest V6 und E2E VA-3 gedeckt; AC-8/AC-7 Kern per pytest (leere/gesetzte/fremde Orte); Kein Backend-Change (git diff nur 2 Dateien).
Restrisiko (kein Finding): E2E nicht ausgefuehrt (Staging-Lauf offen); Mutation 1 und 3 werden jeweils nur von einem Test gefangen (duenn, aber wirksam).
**Implementierer:** keine Rueckfragen.


### Runde 2
**Adversary:**
Runde 2: Nachpruefung der Randfaelle gegen den Code. Reihenfolge mitKarte: Ampel/Auswahl-Merge laeuft vorher, mitKarte mischt display_config per Read-Modify-Write (Mutation 6 beweist es). felderNutzlast('vergleich') liefert hourly_enabled top-level und telegram_style in display_config; ohne Aenderung gegenueber felderStart keine Schalterfelder (AC-9/AC-5, Mutation 3). Keine Altschluessel eingefuehrt. Zweiter Prueflauf der Mutationen ebenfalls ohne Ueberlebende. Keine offenen Findings.
**Implementierer:** keine Rueckfragen.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:635
Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:336
Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:168

## Verdict

VERDICT: VERIFIED

## Geprüfte Dateien

- sha256:edc006eb388bf8c34438ccd061b6f5079de3964f5188f356870dce7b4cf70afb  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- sha256:558bb67cddef88bc576af2393a7fa37891649e95a1cfebeaae36dd88c6abe7f7  frontend/src/lib/components/compare/compareEditorSave.ts

## Prüfbasis

- base: 5a442bd419817f6310b8c5a9536036156ca61e95
- blob:dd42b3083c5871449038599d247299d39928488d  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- blob:b1f4a151037557e97ecaf00f0357ee0e28d63fe9  frontend/src/lib/components/compare/compareEditorSave.ts
