---
spec_file: docs/specs/modules/fix_2896_kontrast_zierpunkt_avatar.md
spec_sha256: ac596bf46c6e83053eba1b3b16da4ae5ed0760be4fdde95c9ca460b0b1b124e8
spec_frozen_sha256: 3fb3f57a196ffb14394c330dc41d97b3f49ffddbe646dd45b138f33151ac573a
---

# PO-Briefing: fix-2896-kontrast-zierpunkt-avatar

- **Spec:** docs/specs/modules/fix_2896_kontrast_zierpunkt_avatar.md
- **Issue:** #2896
- **Erstellt:** 2026-11-09

## Was gebaut wird

Der Punkt im Logo und die Initialen im Konto-Kreis werden dunkler und damit gut lesbar.

## Definition of Done

Logo-Punkt und alle Avatar-Initialen erreichen messbar mindestens 4,5:1 Kontrast, und die Prüfung auf der Staging-Seite läuft grün.

## Wie geprüft wird

Automatische Kontrastmessung im Browser auf Staging für alle drei Seiten sowie Komponententests; das Aussehen beurteilt nur ein Screenshot-Blick.

## Kritische Anmerkungen

- Der Konto-Kreis wird sichtbar dunkler orange; zusätzlich angepasst: Konto-Blatt, Design-Seite und dunkle Logo-Variante (nicht im Ticket).
- Logo-Wort „zwanzig" (4,34:1) bleibt bewusst unverändert, da Markenfarbe.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
