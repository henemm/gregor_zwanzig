---
issue: "#592 + #593"
status: approved
created: 2026-06-04
---

# Spec: Trips-Liste Navigation (#592 + #593)

## Problem

Auf `/trips` gibt es zwei Navigations-Bugs:
- **#593 Desktop:** Die Tabellenzeile hat einen Hover-Effekt, ist aber nicht klickbar. Nur der Namens-Link navigiert zur Detailseite.
- **#592 Mobile:** Ein Tipp auf eine Karte expandiert Quick-Actions statt direkt zur Detailseite zu navigieren.

## Lösung

### Desktop (#593)
`<tr>` bekommt `onclick` + `cursor-pointer`. Die Aktions-Cell (Buttons, Dropdown) stoppt die Event-Propagation, damit Klich auf Buttons nicht gleichzeitig `<tr>` auslöst.

### Mobile (#592)
`trip-card-content-btn` navigiert direkt zu `/trips/{id}`. Die Expansion-Mechanik (`expandedCardId`) entfällt. "Briefing senden" wird in den Action-Sheet integriert, damit kein Quick-Action verloren geht.

## Acceptance Criteria

**AC-1:** Given Desktop-Ansicht (≥1024px), when Nutzer auf eine Tabellenzeile klickt (nicht auf Name-Link oder Aktions-Buttons), then navigiert der Browser zu `/trips/{id}`.

**AC-2:** Given Desktop-Ansicht, when Nutzer auf den Aktions-Button ("Briefing-Vorschau" / Dropdown) klickt, then löst nur dieser Button seine Aktion aus — die Zeilen-Navigation wird NICHT zusätzlich ausgelöst.

**AC-3:** Given Mobile-Ansicht (≤1023px), when Nutzer auf `trip-card-content-btn` tippt, then navigiert der Browser direkt zu `/trips/{id}` ohne Zwischenschritt.

**AC-4:** Given Mobile-Ansicht, when Nutzer auf EllipsisVertical-Button tippt, then öffnet der Action-Sheet wie bisher — und enthält jetzt auch "Briefing senden" → `/trips/{id}?tab=preview`.

**AC-5:** Given Mobile-Ansicht, when der Action-Sheet geöffnet ist, then ist die Expansion-Mechanik (expandedCardId) vollständig entfernt — keine Quick-Action-Zeile erscheint mehr nach Kartentipp.
