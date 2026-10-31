---
spec_file: docs/specs/modules/feat_2587_compare_briefing_nachholen.md
spec_sha256: b4542cb456b891c17ef48af41572a88539d7f6eeeef6309faa850820a8442ddc
spec_frozen_sha256: ce73968da71e1e1ccb3d07d25601c467b0f22e2332a4580dad7feb236b0d5be2
---

# PO-Briefing: feat-2587-compare-briefing-nachholen

- **Spec:** docs/specs/modules/feat_2587_compare_briefing_nachholen.md
- **Issue:** #2587
- **Erstellt:** 2026-10-31

## Was gebaut wird

Scheitert der automatische Ortsvergleich-Versand auf allen Kanälen, wird er am selben Tag nachgeholt und im Monitoring als offen geführt.

## Definition of Done

Ein vollständig gescheitertes Ortsvergleich-Briefing kommt später am Zieltag mit dem Hinweis „Nachgeliefert“ an, und das Monitoring zeigt es bis dahin als offen.

## Wie geprüft wird

Automatische Tests mit echten Dateien und zwei Nutzern prüfen Vormerken, Nachholen, Verfall und Trip-Unverändertheit; der Hinweis in SMS fehlt und bleibt ungeprüft.

## Kritische Anmerkungen

- Nachhol-Hinweis erscheint nur in E-Mail und Telegram, nicht in SMS oder Premium-SMS; beim Trip ist das ebenso (bekannte Lücke).
- Nicht nachgeholt werden Fälle ohne konfigurierte Kanäle oder ohne Wetterdaten; sie sind als Nebenbefund vermerkt.
- Die frühere Aufteilung „Nachholen nur beim Trip“ wird bewusst abgelöst; Trip-Verhalten bleibt unverändert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
