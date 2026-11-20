---
entity_id: fix-3200-rueckfrage-153
type: bugfix
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
tags: [premium-sms, inbound, rueckfrage]
issue: 3200
---

# Mini-Spec: Premium-Rückfrage rechnet mit 153 statt 160 Zeichen (#3200)

## Was ändert sich
- Die Premium-SMS-Rückfrage bei Mehrdeutigkeit (`_rueckfrage_text` in `src/services/trip_selection.py`) wählt die Kürzlänge der Namen gegen das Kanal-Budget `CHANNEL_LIMITS["premium_sms"]["max_chars"]` (153) statt gegen die feste Zahl 160.
- Folge: Passt eine eindeutige Kürzung in 153 Zeichen, kommt die Rückfrage vollständig an (alle Kandidaten **und** der Antwort-Hinweis „Reply with name, e.g. '…'“), statt dass der zentrale 153er-Versand das Ende mit `~` abschneidet.
- Bestehende Tests, die gegen 160 prüfen (AC-15 in `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py`), werden auf 153 angehoben.

## Was darf sich nicht ändern
- Telegram-Rückfrage bleibt ungekürzt mit vollen Namen.
- Eindeutigkeit hat Vorrang vor Länge (#2615 AC-7): passt keine eindeutige Kürzung in 153, bleibt die kürzeste eindeutige Länge (bewusst hingenommen, Known Limitation aus #3133).
- GSM-7-Faltung der Namen, Boden 4 Zeichen, Anzahl der Kandidaten und die Wörter für Trip/Vergleich bleiben unverändert.
- Der Antwort-Parser findet die gekürzten Namen weiterhin (Roundtrip).

## Nicht im Umfang
- Seiten oder Nummern-Antwort, damit bei spät eindeutigen Namen alle Kandidaten erreichbar bleiben: das wäre eine Produktentscheidung (Issue-Absatz „Zusätzlich“); bleibt Known Limitation.

## Acceptance Criteria
**AC-1:** Given ein Nutzer hat mehrere Trips/Vergleiche mit langen Namen, deren eindeutige Kürzung eine Premium-Rückfrage von 154–160 Zeichen ergäbe, When er per Premium-SMS einen mehrdeutigen Befehl sendet, Then ist die Rückfrage höchstens 153 Zeichen lang, endet nicht mit `~` und enthält alle Kandidaten sowie den vollständigen Antwort-Hinweis.

**AC-2:** Given dieselbe Lage, When der Befehl über Telegram kommt, Then bleibt die Rückfrage ungekürzt mit vollen Namen.

**AC-3:** Given Namen, die erst nach mehr Zeichen eindeutig werden, als in 153 Zeichen passen, When die Premium-Rückfrage gebaut wird, Then wird weiterhin die kürzeste eindeutige Länge gewählt (keine Mehrdeutigkeit durch Kürzung).

## Manuelle Test-Schritte
1. Zwei Nutzer, je ein Trip + zwei Vergleiche mit langen Namen; mehrdeutigen Befehl „pause“ über den echten Premium-Eingang senden.
2. Antwort prüfen: ≤153 Zeichen, kein `~`, Hinweis vollständig.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Rot-Nachweis: Fixture, deren Rückfrage bei Budget 160 im Band 154–160 liegt, durch den echten Versandweg (inkl. 153er-Kürzung) → heute endet sie mit `~`/Hinweis fehlt; nach Fix vollständig.
- [ ] AC-1: neuer Test `test_3200_premium_rueckfrage_im_band_154_160_kommt_vollstaendig_an` in `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py` (Fixture im Band 154–160 bei altem Budget, Text durch die echte Versand-Kürzung geschickt, ≤153, kein `~`, alle Kandidaten + Hinweis).
- [ ] AC-2: im selben Test dieselbe Fixture über `telegram` → volle Namen, Länge > 160 (ungekürzt); zusätzlich bleibt `test_premium_sms_rueckfrage_hoechstens_160_mit_allen_kandidaten` (auf 153 angehoben) mit seiner Telegram-Prüfung grün.
- [ ] AC-3: `tests/tdd/test_befehle_pausierte_vergleiche.py::test_ac7_kuerzung_bleibt_eindeutig_wenn_160_zeichen_nicht_reichen` und `::test_ac7_gekuerzte_namen_sind_paarweise_verschieden_und_passen_in_160` (Grenzen auf 153 angehoben) bleiben grün; `::test_ac7_telegram_bleibt_bei_vollen_namen` sichert AC-2 zusätzlich.
