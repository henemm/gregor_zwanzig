# Mini-Spec: #881 Einrückung Vortag-Vergleich

## Was ändert sich
- `src/output/renderers/email/html.py`: `day_comparison_html` erhält `padding:8px 20px` statt `padding:8px 16px`
- Vortag-Vergleich hat damit denselben linken Einzug (20px) wie Etappen-Kennzahlen im Header

## Was darf sich nicht ändern
- Visuelle Gestaltung der Box (Hintergrundfarbe, Akzent-Rand, Schriftgröße)
- Alle anderen E-Mail-Sektionen

## Acceptance Criteria
**AC-1:** Given eine E-Mail mit Etappen-Kennzahlen und Vortag-Vergleich, When der Nutzer die E-Mail öffnet, Then haben beide Sektionen denselben linken Einzug (20px).

## Manuelle Test-Schritte
1. Test-Briefing an gregor-test@henemm.com senden
2. Linker Rand von Etappen-Kennzahlen und Vortag-Vergleich visuell vergleichen → müssen bündig sein
