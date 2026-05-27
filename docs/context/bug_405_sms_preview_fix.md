# Context: bug_405_sms_preview_fix

## Request Summary
`desktop-sms-preview.png` aus dem IST-Audit-Script (Phase 2, Epic #404) ist byte-identisch mit `desktop-email-preview.png`, weil der Selektor für einen vermeintlichen SMS-Radio-Button nicht existiert und der Fehler still geschluckt wird.

## Betroffene Datei
| Datei | Relevanz |
|-------|---------|
| `claude-code-handoff/soll-audit-2026-05-27/take-ist-screenshots.js` Zeilen 181–189 | Enthält den kaputten Radio-Klick + stille `catch(()=>{})` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Zeigt die Preview-UI — kein SMS/Email-Umschalter |
| `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` | SMS-Komponente, hat `data-testid="sms-phone-wrapper"` |
| `frontend/src/lib/components/preview/EmailIframe.svelte` | Email-Komponente, hat `data-testid="email-iframe-wrapper"` |

## Kernbefund
Der Preview-Tab in `TripTabs.svelte` zeigt **immer beide** Komponenten nebeneinander — `EmailIframe` links und `SmsPhoneFrame` rechts. Es gibt **keinen** Radio-Button zum Wechseln zwischen Email und SMS. Die einzigen Radio-Inputs im Tab sind für "Morgen"/"Abend" (ReportType).

Das Script versucht:
```javascript
await page.click('input[type="radio"][value="sms"], [data-testid="preview-channel-sms"]').catch(() => {});
```
Beide Selektoren existieren nicht → Klick schlägt stumm fehl → zweiter Screenshot ist identisch mit dem ersten.

## Fix-Strategie (ohne UI-Änderung)
Da `[data-testid="sms-phone-wrapper"]` immer sichtbar ist, reicht es, einen **Element-Screenshot** des SMS-Phone-Frames zu machen statt einen Full-Page-Screenshot:

```javascript
// Statt Radio-Klick: Element-Screenshot des SMS-Rahmens
try {
  await page.locator('[data-testid="sms-phone-wrapper"]').screenshot({
    path: path.join(OUT_DIR, 'desktop-sms-preview.png')
  });
  console.log('  [ok] desktop-sms-preview.png');
} catch (err) {
  ERRORS++;
  console.error('  [FEHLER] desktop-sms-preview.png: ' + err.message);
}
```

Außerdem sollte die Email-Seite länger warten (Iframe-Fetch braucht Zeit), z.B. `[data-testid="email-iframe-wrapper"]` als Selector statt `timeout: 1500`.

## Abhängigkeiten
- **Upstream:** Keine — nur Script-Fix, kein UI-Code betroffen
- **Downstream:** Phase 3 von Epic #404 (SOLL-IST-Vergleich) braucht einen verwertbaren SMS-Screenshot

## Risiken
- Keins — reine Tooling-Datei, kein Produktionscode betroffen
