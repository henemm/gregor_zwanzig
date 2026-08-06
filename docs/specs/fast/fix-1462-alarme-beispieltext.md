# Mini-Spec: #1462 — Beispiel-Warnung im Alarme-Reiter nennt den richtigen Auslöser

**Issue:** #1462 (Alerts S4: Steuerung ausschliesslich im Reiter Alarme)
**Track:** Fast Track · **Erstellt:** 2026-08-06
**PO-Freigabe Wortlaut:** 2026-08-06 (Auswahl im Intake, Beleg als Issue-Kommentar)

## Ausgangslage (auf Staging `21117b1f` durchgeklickt)

Der im Issue beschriebene Umfang ist bereits erfüllt — belegt durch echten Klickpfad:

| Forderung | Ist-Stand |
|---|---|
| Wertebereiche-Reiter steuert nicht mehr | ✅ #1371 S6 (Schalter), #1460 P1a (Auslöser), #1425 S2C (Text) |
| Abschnitt „Korridor-Auslöser" im Alarme-Reiter | ✅ entfällt (`alarmeTabSections.ts`) |
| Wertebereiche-Text verweist auf Alarme | ✅ „Warnungen zwischen den Briefings stellst du im Reiter Alarme ein." |
| Amtliche Warnungen: Inhalt vs. Auslöser getrennt | ✅ #1301 D2 |

**Ein Rest bleibt:** Im Reiter *Alarme* des **Ortsvergleichs** steht über der Beispiel-Karte
„So sieht eine ausgelöste Warn-Mail aus, wenn ein Wert den Wertebereich verlässt."
Seit #1460 löst der Wertebereich nichts mehr aus — Auslöser sind Vorhersage-Änderung,
Nowcast und amtliche Warnung. Der Satz ist damit dasselbe falsche Versprechen, gegen das
sich #1462 richtet, nur an anderer Stelle.

Betroffen ist ausschließlich der Vergleichs-Zweig: `AlarmeTab.svelte:399` rendert
`VTAlertSample context="vergleich"`; der Trip-Zweig nutzt `AlertPreviewCard` ohne diesen Satz.

## Was ändert sich

- `frontend/src/lib/components/shared/versand-tab/VTAlertSample.svelte:52`
  - vorher: „So sieht eine ausgelöste Warn-Mail aus, wenn ein Wert den Wertebereich verlässt."
  - nachher: „So sieht eine ausgelöste Warn-Mail aus, wenn sich die Vorhersage deutlich ändert."
- Neuer Wächter, der den alten Wortlaut dauerhaft ausschließt (Muster: `corridorEditorCopy.test.ts`,
  `# doc-compliance-test`-Klasse — reiner Anzeigetext hat keine ausführbare Logik).

## Was darf sich nicht ändern

- Die Beispiel-Karte selbst (Zeilen, Überschrift „Wetter-Änderung erkannt", Spalten) bleibt unberührt.
- Der Trip-Zweig (`AlertPreviewCard`) bleibt unberührt.
- Keine Logik, kein Datenfeld, kein Endpoint. `corridors[].notify` bleibt im Datenmodell.

## Acceptance Criteria

**AC-1:** Given ein Nutzer öffnet im Ortsvergleich den Reiter *Alarme*,
When er zur Beispiel-Warnung scrollt,
Then nennt der einleitende Satz die Vorhersage-Änderung als Auslöser und **nicht** den Wertebereich.

**AC-2:** Given jemand setzt den alten Wortlaut („Wertebereich verlässt") später wieder ein,
When die Frontend-Tests laufen,
Then schlägt der Wächter fehl und benennt die Stelle.

**AC-3:** Given der Trip-Reiter *Alarme*,
When er geöffnet wird,
Then ist seine Beispiel-Darstellung unverändert (kein Text aus `VTAlertSample`).

## Manuelle Test-Schritte

1. Auf Staging anmelden, Orts-Vergleich `Validator-1025 Compare` öffnen, Reiter *Alarme*.
2. Nach unten zur *Beispiel-Warnung*: der Satz nennt die Vorhersage-Änderung.
3. Einen Trip öffnen, Reiter *Alarme*: Darstellung unverändert.

## Inline-Test

- [ ] `frontend/src/lib/components/shared/versand-tab/__tests__/vtAlertSampleCopy.test.ts`
      — alter Wortlaut ausgeschlossen, neuer Wortlaut vorhanden (AC-1, AC-2)
