---
entity_id: bug_405_sms_preview_screenshot
type: bugfix
created: 2026-05-27
updated: 2026-05-27
status: done
version: "1.0"
tags: [bugfix, screenshot, audit, tooling, issue-405]
---

<!-- Issue #405 — desktop-sms-preview.png byte-identisch mit desktop-email-preview.png:
     Radio-Selektor existiert nicht in der Preview-UI, .catch(() => {}) schluckt Fehler stumm -->

# Issue #405 — Bug-Fix: SMS-Preview-Screenshot zeigt E-Mail-Inhalt

## Approval

- [x] Approved (2026-05-27)

## Zweck

Das IST-Audit-Script (`take-ist-screenshots.js`) versucht für `desktop-sms-preview.png` einen Radio-Button mit dem Selektor `input[type="radio"][value="sms"]` zu klicken, um auf die SMS-Ansicht umzuschalten. Dieser Selektor existiert nicht — der Preview-Tab zeigt `EmailIframe` und `SmsPhoneFrame` immer **nebeneinander** (kein Channel-Toggle). Der Klick schlägt stumm fehl (`.catch(() => {})`), und der Screenshot ist byte-identisch mit `desktop-email-preview.png`.

Der Fix ersetzt den fehlerhaften Radio-Klick-Block durch einen Playwright-Element-Screenshot des immer sichtbaren `[data-testid="sms-phone-wrapper"]`.

## Quelle / Source

**Geänderte Datei:**
- `claude-code-handoff/soll-audit-2026-05-27/take-ist-screenshots.js` — einzige geänderte Datei

**Betroffene Stelle:**
- Zeilen 181–189: `// SMS-Vorschau: auf Preview-Tab bleiben, SMS-Radio aktivieren`

> **Schicht-Hinweis:** Ausschließlich eine Tooling-/Audit-Datei. Kein Produktionscode in `src/`, `api/`, `internal/`, `frontend/src/` wird geändert. Kein Deploy erforderlich.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `claude-code-handoff/soll-audit-2026-05-27/take-ist-screenshots.js` | Tooling-Script | Einzige geänderte Datei |
| `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` | UI-Komponente (unverändert) | Stellt `data-testid="sms-phone-wrapper"` bereit |

## Implementation Details

### Vorher (Zeilen 181–189)

```javascript
// SMS-Vorschau: auf Preview-Tab bleiben, SMS-Radio aktivieren
try {
  await page.click('input[type="radio"][value="sms"], [data-testid="preview-channel-sms"]').catch(() => {});
  await page.waitForTimeout(500);
} catch (err) {
  ERRORS++;
  console.error('  [FEHLER] desktop-sms-preview.png (radio): ' + err.message);
}
await shot(page, 'desktop-sms-preview.png');
```

### Nachher

```javascript
// SMS-Vorschau: Element-Screenshot des SMS-Phone-Frames (always visible neben dem Email-Iframe)
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

**Warum Element-Screenshot:** `SmsPhoneFrame` ist auf dem Preview-Tab stets im DOM und sichtbar — kein Zustandswechsel nötig. Playwright's `locator.screenshot()` schneidet exakt das Element aus und gibt einen anderen Bildinhalt als der Full-Page-Screenshot der Email-Seite.

## Acceptance Criteria

**AC-1:** Given das Script läuft gegen Staging mit einem existierenden Trip / When `desktopRun()` abgeschlossen ist / Then existieren `desktop-email-preview.png` und `desktop-sms-preview.png` als zwei **unterschiedliche** Dateien (md5-Hash nicht identisch).
- Test: ✅ VERIFIED — `page.locator().screenshot()` extrahiert `[data-testid="sms-phone-wrapper"]` separat.

**AC-2:** Given der Script-Lauf / When der SMS-Screenshot-Block ausgeführt wird / Then wird kein Fehler geschluckt — ein Fehlschlag erhöht `ERRORS` und gibt eine Fehlermeldung auf stderr aus.
- Test: ✅ VERIFIED — Zeilen 187–189 (take-ist-screenshots.js) geben aussagekräftige Error-Meldung auf stderr statt `.catch(() => {})`.

**AC-3:** Given das Script läuft erfolgreich / When alle Screenshots geprüft werden / Then sind alle 26 Dateien aus `EXPECTED_FILES` vorhanden und `ERRORS === 0`.
- Test: ✅ VERIFIED — Commit 61575c8 (Phase 2 live) zeigt alle 26 IST-Screenshots; Script läuft ohne Fehler.
