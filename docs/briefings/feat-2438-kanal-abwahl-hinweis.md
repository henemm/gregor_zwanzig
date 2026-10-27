---
spec_file: docs/specs/modules/feat_2438_kanal_abwahl_hinweis.md
spec_sha256: 26f2fba1f4bf2ab13b7147d53a7c974e653a0db5f43924fbf697c66459d363ba
spec_frozen_sha256: 2c8ef74d57c88429810810db96faad59152bb448578e1cd3204bc7018f48218f
---

# PO-Briefing: feat-2438-kanal-abwahl-hinweis

- **Spec:** docs/specs/modules/feat_2438_kanal_abwahl_hinweis.md
- **Issue:** #2438
- **Erstellt:** 2026-10-19

## Was gebaut wird

Kanal-Reiter beider Editoren erklären, dass ein Kanal nur abwählen kann, was in der Grundauswahl steht.

## Definition of Done

Unter „Aus in diesem Kanal" steht in beiden Editoren der Hinweis, auch bei leerer Gruppe, bis 320 Pixel lesbar.

## Wie geprüft wird

Tests prüfen Wortlaut, Sichtbarkeit und Handybreite in beiden Editoren, nicht ob der Text verständlich ist.

## Kritische Anmerkungen

- Hinweis steht dauerhaft, auch wenn nichts fehlt; dann womöglich überflüssig.
- Premium-SMS-Reiter ungeklärt: AC-1 nennt nur drei Kanäle, AC-6 vier.
- Ortsvergleich-Ausblick zeigt den Hinweis ebenfalls, nicht verlangt.

## Freigabe-Frage

Ist der Wortlaut „Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist. Was dort fehlt, erscheint in keinem Kanal." so freigegeben?
