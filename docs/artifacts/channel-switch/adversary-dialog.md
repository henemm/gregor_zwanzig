# Adversary Dialog — F12a Channel-Switch Subscriptions

## Date: 2026-04-04

## Checklist

- [x] Default send_email=true, send_signal=false
- [x] Beide Channels explizit aktivierbar
- [x] Email-false + Signal-true speicherbar und ladbar
- [x] Legacy JSON ohne Flags → defaults korrekt
- [x] Toggle preserviert send_signal
- [x] Default-Verhalten identisch zu vorher (email-only)
- [x] Beide Channels dispatched wenn aktiv
- [x] Signal-only: kein Email
- [x] Channel-Config nicht verloren bei Toggle
- [x] UI: Kanäle-Checkboxen in New + Edit Dialog
- [x] "Run Now" respektiert Channels
- [x] No-channel Warning im Scheduler geloggt

### Runde 1

Adversary prüfte alle 18 Spec-Punkte. Model + Loader via pytest (9/9 pass). Scheduler und UI via Code-Inspection und Screenshots. Alle Punkte bestanden.

### Runde 2

Adversary fand: Silent no-delivery wenn beide Channels false — Scheduler logte nichts. Fix: `logger.warning()` + early return hinzugefügt. 4 Warnings (stale heading, dead imports, SMTP banner) dokumentiert als UX-Verbesserungen.

### Runde 3

Re-Verification nach Fix: 9/9 Tests pass. Warning-Log korrekt implementiert.

## Verdict
**VERIFIED**
