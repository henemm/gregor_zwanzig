# Mini-Spec: Monitor (CI) immer genehmigen

## Was ändert sich
- `.claude/settings.json` (Projekt-Settings, eingecheckt): `permissions.allow` bekommt den Eintrag `"Monitor"` dazu.
- Dadurch fragt keine Session mehr einzeln nach, wenn sie das Monitor-Tool (Beobachtung von Hintergrundprozessen/CI-Läufen) nutzt.

## Was darf sich nicht ändern
- Keine anderen Einträge in `permissions.allow`/`deny`/`ask` werden verändert.
- Keine Ausweitung auf andere Tools — nur `Monitor`.

## Manuelle Test-Schritte
1. `.claude/settings.json` öffnen, prüfen dass `"Monitor"` unter `permissions.allow` steht (Diff-Review).
2. In einer neuen Session/einem neuen Worktree das Monitor-Tool aufrufen (z.B. während ein Background-Task läuft) und beobachten, dass keine Genehmigungs-Abfrage mehr erscheint.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Kein automatisierter Test nötig — reine Permissions-Konfiguration ohne Programmlogik. Verifikation erfolgt manuell (s.o.) + Diff-Review.
