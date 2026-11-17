---
spec_file: docs/specs/modules/wetter_metrik_inhalte.md
spec_sha256: 7c94eb8a2c154fab2185e2f3d021dc4c03d1f7c7c17cf41cbd3a14269deaaef2
spec_frozen_sha256: 8af8d0b5c407da7fa204f4d0410cfaee7f80097eb7f5cbb3dc2625991226137a
---

# PO-Briefing: feature-2955-wetter-metrik-inhalte

- **Spec:** docs/specs/modules/wetter_metrik_inhalte.md
- **Issue:** #2955 (gebündelt mit #3012)
- **Erstellt:** 2026-11-16

## Was gebaut wird

Der Reiter Wetter zeigt Vorbote-Hinweise, Gewitter-Satz, Reihenfolge, Namen und Kopfzähler wie im Mockup, auf Deutsch und Englisch.

## Definition of Done

Auf Staging zeigen Trip und Orts-Vergleich, DE und EN, Vorbote-Texte, Gewitter-Satz, Reihenfolge, Namen und Zähler wie im Mockup; Alarme bleiben unverändert.

## Wie geprüft wird

Automatische Tests und Staging-Prüfung belegen jede Anforderung; ob es wirklich wie das Mockup aussieht, beurteilt nur ein Mensch.

## Kritische Anmerkungen

- #3012 verlangt „Luftfeuchtigkeit“ statt „Luftfeuchte“; die Spec macht das Gegenteil, weil das Mockup „Luftfeuchte“ schreibt.
- Das Ticket nennt „Tiefe Wolken“ als Vorbote; die Spec macht stattdessen „Bewölkung“, dazu Taupunkt und Luftdruck (nicht verlangt).
- Die neuen Namen ändern auch E-Mail, Telegram und SMS, nicht nur den Reiter.

## Freigabe-Frage

Soll „Luftfeuchte“ gelten, obwohl das Ticket „Luftfeuchtigkeit“ verlangt, und sollen die Namen auch in Mails und Nachrichten wechseln?

## Ampel

Ampel: rot
