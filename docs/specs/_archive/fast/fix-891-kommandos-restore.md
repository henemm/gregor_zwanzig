# Mini-Spec: fix-891 — Entfernte E-Mail-Kommandos wiederherstellen

## Was ändert sich
- `_render_kommandos_section()` in `src/output/renderers/email/html.py` erhält 9 statt 6 Einträge
- Fehlende Kommandos werden wiederhergestellt: HEUTE, MORGEN, JETZT/NOW, STOP/WEITER, HILFE/HELP
- Grid wächst von 3×2 auf 3×3

## Was darf sich nicht ändern
- Visuelles Format (Grid, Mono-Bold, Farben, Hintergrund #fbfaf6)
- Alle anderen Mail-Sektionen
- Plain-Text-Renderer

## Acceptance Criteria
**AC-1:** Given eine gerenderte Briefing-Mail, When die Antwort-Kommandos-Sektion betrachtet wird, Then erscheinen alle 9 Befehle: HEUTE, MORGEN, JETZT / NOW, PAUSE 2d, SKIP, STOP / WEITER, STATUS, CONFIG, HILFE / HELP.

## Manuelle Test-Schritte
1. Test-Mail über Staging senden
2. Stalwart öffnen → alle 9 Kommandos sichtbar?
3. 3×3-Grid korrekt dargestellt?
