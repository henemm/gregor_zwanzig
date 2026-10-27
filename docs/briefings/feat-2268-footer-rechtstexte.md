---
spec_file: docs/specs/modules/app_footer_rechtstexte.md
spec_sha256: 5bbcea9808ab4cc892ca05f4f6622ba573e02d3f12024c1bcd17e6185a1a9315
---

# PO-Briefing: feat-2268-footer-rechtstexte

- **Spec:** docs/specs/modules/app_footer_rechtstexte.md
- **Issue:** #2268
- **Erstellt:** 2026-09-21

## Was gebaut wird

Jede Gregor-Seite zeigt am Ende Links zu Impressum und Datenschutz; die Registrierung bekommt darunter einen Datenschutz-Hinweissatz.

## Definition of Done

Live sind beide Links, auch ausgeloggt und mobil, am Seitenende erreichbar; die Registrierung zeigt den Hinweis unter dem Knopf.

## Wie geprüft wird

Tests prüfen den Seitenaufbau je Seite; ob Links mobil sichtbar und antippbar sind, zeigt nur die Live-Prüfung außerhalb der Ampel.

## Kritische Anmerkungen

- Kein dauerhaft sichtbarer Footer: auf Login und Registrierung erst nach Scrollen, mobil am Seitenende; Ticket sagt „erreichbar".
- Über das Ticket hinaus: neuer Tab, 44-Pixel-Tippfläche, Sonderregel Vergleichs-Editor; Designseite bewusst ohne Footer.
- „Editor verdeckt nichts" wird nur am Seitenaufbau geprüft, nicht am echten Bildschirm.

## Freigabe-Frage

Genügt es für den Start, dass die Links nur am Seitenende stehen und nicht dauerhaft eingeblendet sind?
