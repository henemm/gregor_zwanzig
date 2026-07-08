# Mini-Spec: fix-1097-compare-layout-cols

Issue: #1097 — Ortsvergleich Layout-Tab (Lese-Modus): EMAIL zeigt 99 Spalten-Chips statt der Orts-Anzahl.

## Root-Cause

`frontend/src/lib/components/compare/CompareTabs.svelte:101-105` hardcodiert
`CHANNEL_COLS = { email: 99, telegram: 8, sms: 0 }`. Das `99` ist als „E-Mail hat
quasi unbegrenzt Spalten"-Budget gemeint, wird aber wörtlich als 99 Chips gerendert
(`CompareLayoutRow` rendert `cols` Chips). Der Layout-Tab soll zeigen, wie viele
**Orts-Spalten** pro Kanal in die Ausgabe kommen — das ist durch die Anzahl der Orte
begrenzt. Dass TELEGRAM „richtig" 8 zeigt, ist Zufall (Budget 8 = die 8 Orte des
Test-Vergleichs); bei 3 Orten würde TELEGRAM fälschlich 8 zeigen.

## Was ändert sich

- Die pro Kanal gerenderte Chip-Anzahl wird auf die tatsächliche Orts-Anzahl gedeckelt:
  `cols = min(CHANNEL_COLS[ch], preset.location_ids.length)`.
- Bei 8 Orten: EMAIL zeigt 8 (statt 99), TELEGRAM zeigt 8, SMS bleibt flach.
- Bei z.B. 3 Orten: EMAIL 3, TELEGRAM 3, SMS flach.

## Was darf sich nicht ändern

- Das Kanal-Budget-Konzept bleibt: EMAIL unbegrenzt (99 als Platzhalter), TELEGRAM
  hartes Limit 8, SMS flach (0 → Hint „flach · ohne Spalten"). Deckelung nur nach unten.
- SMS-Sonderfall (cols===0 → „flach · ohne Spalten") bleibt unverändert; `min(0, N) === 0`.
- Erstes Chip accent-getönt, restliche default (bestehendes `CompareLayoutRow`-Verhalten).
- Kein Backend-/Datenpfad berührt; rein präsentationale Layout-Vorschau.

## Manuelle Test-Schritte (Staging, eingeloggt)

1. `/compare/…` einen Vergleich mit **8 Orten** öffnen → Tab „Layout".
2. EMAIL-Zeile zeigt **8** Chips (nicht 99), TELEGRAM 8, SMS „flach · ohne Spalten".
3. Gegencheck mit einem Vergleich mit weniger Orten (z.B. 3): EMAIL 3, TELEGRAM 3.

## Inline-Test (während Implementierung)

- [ ] Vitest-Component-Test: Layout-Tab bei Preset mit N=8 location_ids rendert
      genau 8 EMAIL-Chips (nicht 99) und 8 TELEGRAM-Chips.
- [ ] N=3 → EMAIL 3 Chips, TELEGRAM 3 Chips (Budget-Deckelung greift für beide).
