---
entity_id: fix_3168_test3100_vorbedingung
type: fast
created: 2026-11-19
status: approved
---

# Mini-Spec: fix-3168-test3100-vorbedingung

Issue #3168 (main rot). Reine Test-Korrektur, kein Produktionscode.

## Ursache (belegt)
`test_ac4_ueberlaenge_premium_kuerzt_vom_listenende_warnung_bleibt` (#3100) legt die
amtlichen Warnungen mit `valid_from = jetzt - 12 h` an. Die SMS-Warntokens tragen die
lokale Beginnstunde (`!TS:M@22` bzw. `!TS:M@1`). Ist diese Stunde einstellig (Testlauf
zwischen 12:00 und 21:59 Ortszeit Innsbruck, d. h. ca. 11-21 Uhr UTC), ist der SMS-Text
vier Zeichen kuerzer (152 statt 156) und die Vorbedingung `> 153` scheitert. Belegt per
freezegun: 09:30 UTC gruen (156, `@22`), 11:30/15:30 UTC rot (152, `@0`/`@4`), 22:30 UTC
gruen (156, `@11`); der Stand vor #3153 (3ae62dc26) ist um 12 Uhr UTC ebenso rot. #3153
aendert nur Orte-Texte, nicht die Trip-SMS -- der zeitliche Zusammenfall war Zufall.

## Was aendert sich
- `_warnungen_heute()` setzt den Warnbeginn fest auf **gestern 22:00 Ortszeit** (statt
  `jetzt - 12 h`): die Warnung ist zu jeder Laufzeit aktiv, die Beginnstunde ist immer
  zweistellig, der SMS-Text damit unabhaengig von der Uhrzeit > 153 Zeichen.

## Was darf sich nicht aendern
- Alle Zusicherungen von AC-4 (#3100) bleiben unveraendert: Vorbedingung
  `153 < len(SMS) <= 160`, Premium <= 153, Warnblock identisch und am Ende, Metrik-Tokens
  als echtes Anfangsstueck.
- Kein Produktionscode.

## Acceptance Criteria
**AC-1:** Given der AC-4-Test von #3100, When er zu einer beliebigen Uhrzeit (z. B. 05, 09, 11, 15, 21 Uhr UTC) laeuft, Then ist der SMS-Text laenger als 153 Zeichen und der Test gruen.
**AC-2:** Given die Mutation des Warnbeginns zurueck auf eine einstellige Ortsstunde (z. B. 01:00 heute), When der Test laeuft, Then scheitert die Vorbedingung (die Zusicherung bewacht die Ueberlaenge weiter).

## Manuelle Test-Schritte
1. `uv run pytest tests/tdd/test_3100_premium_sms_fallliste.py -q` -> gruen.
2. Mit freezegun zu mehreren UTC-Stunden ausfuehren -> jeweils gruen.
3. Mutation Warnbeginn 01:00 Ortszeit -> rot; zuruecksetzen.

## Inline-Test
- [ ] `tests/tdd/test_3100_premium_sms_fallliste.py` (bestehender Test, Fixture angepasst)
