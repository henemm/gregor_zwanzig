---
spec_file: docs/specs/modules/feat_3431_klartext_zellformate.md
spec_sha256: 3f362a6b514c70152bb0afb1a1e45cc6afb442960f8ef0edffd4cba20d9a1bec
spec_frozen_sha256: 096baf53bd8222a478193245bed94719641520729e807de5a5b2a3f0d435bb0a
---

# PO-Briefing: feat-3431-klartext-zellformate

- **Spec:** docs/specs/modules/feat_3431_klartext_zellformate.md
- **Issue:** #3431
- **Erstellt:** 2026-11-27

## Was gebaut wird

Die Klartext-Vergleichsmail zeigt Windrichtung, Sonnenstunden und leere Werte genauso wie der HTML-Teil derselben Mail.

## Definition of Done

Windrichtung, Sonnenstunden, Wolkenschichten und leere Zellen sehen im Klartext wie im HTML aus, auf Deutsch und Englisch, mit grünen Tests und Deploy.

## Wie geprüft wird

Automatische Tests vergleichen Klartext- und HTML-Zellen je Zeile, auch für Telegram und Kompaktmail; echte Lesbarkeit beim Empfänger wird nicht geprüft.

## Kritische Anmerkungen

- Leerzeichen vor der Einheit (`213 °`, `4.0 h`): Das Issue verlangte dazu eine PO-Frage vor der Spec; die Spec entscheidet selbst.
- Zusätzlich geändert, im Issue nicht verlangt: Wolkenschichten werden gerundet (`40%` statt `40.3%`).
- Auch Telegram-Vergleich und Kompakt-Vergleichsmail ändern sich sichtbar, obwohl das Issue nur die Klartext-Mail nennt.

## Freigabe-Frage

Soll das Leerzeichen vor der Einheit (`213 °`, `4.0 h`) in Klartext, Telegram und Kompaktmail gelten, samt gerundeten Wolkenwerten?

## Ampel

Ampel: rot
