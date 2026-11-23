# Context: rework-3266-fixloop-doppelte-tests

## Request Summary
Issue #3266 (Teil von #1196, abgespalten aus #3208, Gruppe G7 Fixloop-/Runden-Dateien): die
Fixloop- und Runden-Testdateien zu 3039, s1c4b und 3047 auf doppelte Zusicherungen prüfen und
Dopplungen entfernen. Kriterium wie #3208/#3264/#3265: entfernt wird nur, was identisch ist
(Funktion + Eingabe + Erwartung) oder echte Teilmenge einer bleibenden Zusicherung; „ähnlich"
(andere Ebene, andere Werte, anderer Eingangsweg, anderer Kanal) bleibt. Mutationsnachweis
vorher/nachher, Kern-Schicht 100 % grün.

## Related Files (alle `tests/tdd/`, tatsächlich 14 statt der im Issue genannten 11)
| File | Tests | Relevanz |
|------|-------|----------|
| test_compare_channel_layouts_3039.py (487) | 17 | Vergleichs-Kanal-Layouts, Kette; Helferquelle für 3039_fixloop |
| test_compare_channel_layouts_3039_fixloop.py (200) | 7 | importiert Helfer aus 3039 |
| test_s1c4b_fixloop1_findings.py (485) | 14 | Abo-Ampel in Tabelle/Telegram/SMS-Klammer; Helferquelle für fixloop2/3, s1c4b_letzte_luecken, s1c4b_temperatur_… |
| test_s1c4b_fixloop2_findings.py (224) | 7 | Kacheln/Ausblick; Helferquelle für fixloop3, s1c4b_temperatur_… |
| test_s1c4b_fixloop3_versandweg.py (249) | 7 | Versandweg Vorlage; Gleichstand |
| test_3047_runde7_orte_kanaele.py (516) | 11 | Orte-Kette; Fixture-/Helferquelle für 3047_p9, 3098, 3099, 3100, 3133 |
| test_3047_runde7_orte_luecken.py (334) | 8 | Orte-Lücken, `X?`-Marker |
| test_3047_runde7_orte_mail.py (83) | 2 | Orte-Mail Hinweise |
| test_3047_runde7_orte_sms_kuerzung.py (252) | 4 | Orte-SMS-Kürzung |
| test_3047_runde7_sonnenstunden_settings.py (71) | 3 | Sonnenstunden ohne Settings |
| test_3047_runde7_telegram_tagesfenster.py (205) | 4 | Trip-Tagesfenster; Helferquelle für r8py |
| test_3047_r7_kanaele_trip.py (303) | 7 | Trip-Kanäle; Helferquelle für 3099, 3100 |
| test_3047_r8py_luecken.py (278) | 8 | **Fundstelle** |
| test_3047_r9_orte_altbestand_ausblick.py (78) | 2 | Orte-Altbestand Ausblick |

## Existing Patterns
- Methode aus #3208/#3263/#3264/#3265: Mutation per String-Ersetzung mit externer Sicherungskopie
  (nie `git checkout/stash/reset`), Protokoll vorher/nachher unter `docs/artifacts/<workflow>/`.

## Dependencies
- Upstream: nur Testcode, Produktionscode unverändert.
- Downstream: Viele Helfer/Fixtures dieser Dateien werden von anderen Testdateien importiert (siehe Tabelle) → keine Datei, kein Helfer wird gelöscht.
- Gate `tests/tdd/test_einstellung_gleich_mail_fallliste.py::pruefe_testverweise` prüft, dass jeder in
  `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte}.json` genannte Test existiert.
  Betroffener Test `test_f1_altbestand_leer_jeder_kanal_folgt_editor` steht in keiner Fallliste
  (und sein Name bleibt ohnehin).

## Analysis (Summe 1: Kontext und Analyse in einem Durchgang, gegen Quelltext geprüft 2026-11-23)

### Type
Rework (Testsuite-Bereinigung, kein Produktionscode).

### Ergebnis der Vollprüfung
Alle 101 Testfunktionen der 14 Dateien paarweise (innerhalb und dateiübergreifend) verglichen.
**Kein ganzer Test und kein Parametrisierungsfall** ist identisch oder echte Teilmenge.
Genau **eine Teilmenge auf Zusicherungsebene**:

### G7a — r8py `test_f1_altbestand_leer_jeder_kanal_folgt_editor` Z. 117–118 (ENTFERNEN)
- Bleibende Seite: `test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert` Z. 51–53:
  `sms == "E1 W- G45@4 R2.0@4 TH:M@4 TH+:- FZ2500@4 VS- D15/15"`, `sms_gesp == sms`,
  `premium == premium_gesp == sms`.
- Eingabe identisch: `trip_json(["wind"], report_config=_SMS_KANAELE)` ↔ `{**_SMS_KANAELE, "email_format": "full"}`
  (Vorgabe von `trip_json` ist bereits `"full"`, `_einstellung_gleich_mail_trip_fixtures.py:115`),
  beide `render_trip_mit_ausblick`, `metrics` ∈ {`[]`, gleich aufgebautes `gespeichert`}.
- Erwartung Z. 117 (`sms`-Präfixe == `_SMS_KUERZEL`) folgt zwingend aus dem exakten String von Z. 51;
  Z. 118 (`premium_sms == sms_roh`) ist in Z. 53 enthalten ⇒ echte Teilmenge.
- Mit den Zeilen fallen die dann unbenutzten Dict-Schlüssel `sms`, `premium_sms`, `sms_roh` in
  `_alle_kanaele` und die Konstante `_SMS_KUERZEL` weg (nur dort benutzt). Docstring nennt den
  SMS-Test als Wächter für SMS/Premium-SMS. Testname bleibt.

### Geprüft, bleibt (ähnlich, nicht identisch) — Auswahl
- fixloop3 Premium-Ausgang ↔ Trip-Versand: Premium-Test strenger (exakt `R-`, genau eine Sendung).
- Versand ↔ Vorschau (fixloop3, 3039 ac13, orte_kanaele k7 Renderer/Kette/Vorschau): andere Wege.
- r8py t4 (Fenster 10,10) ↔ tagesfenster nie eingestellt: andere Eingabe, eigener Rückfallzweig.
- r7 ac22 roh_gleich_mail_roh ↔ roh_zeigt_grad: zusätzliche Mail-Liste, anderes Prüfziel.
- orte_luecken bl2 sms ↔ marker: `preset()` vs. nie eingestellt, „irgendwo" vs. „am Ende".
- orte_luecken bl4 ↔ sms_kuerzung nie eingestellt: andere Wetter-Naht und Soll-Listen.
- 3039 ac1/ac7/f001/f005: bewusst verschiedene Eingaben (`False` / Feld fehlt / Dublette).
- s1c4b Klammer-Tests (fixloop1/2/3): verschiedene Reihen, je eine eigene Regel.
- fixloop1 leere Ampel ↔ fixloop2 Gewitter-Leser: andere Produktfunktionen.
- Tabelle ↔ Kachel ↔ Telegram-Kurzübersicht: andere Ebenen.
- r8py t2 ↔ r9: eigene `outlook_metrics` vs. Altbestand ohne Liste.
- Doppelter Helfercode (`_sms_ort`, `zwei_nutzer`, `_ergebnis`, `mit`, `preset` in den Orte-Dateien)
  ist keine doppelte Zusicherung → nicht Gegenstand dieses Tickets.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_3047_r8py_luecken.py | MODIFY | Z. 117–118 entfernen, dazu ungenutzte Schlüssel `sms`/`premium_sms`/`sms_roh` und `_SMS_KUERZEL`; Docstring anpassen |
| docs/artifacts/rework-3266-fixloop-doppelte-tests/ | CREATE | Mutationsprotokoll vorher/nachher |

### Scope Assessment
- Files: 1 MODIFY + 1 Artefakt; LoC ca. −8 / +2; Risk LOW (nur Testcode).

### Technical Approach
1. Mutation VORHER (Kern-Schicht, nur r8py-Datei): `src/output/tokens/builder.py` `FORECAST_THP = "TH+:"`
   → `"TX+:"` muss von BEIDEN f1-Tests rot gefangen werden (Seite B in Z. 117).
2. Zeilen entfernen.
3. Mutation NACHHER: dieselbe Mutation weiter von `test_f1_altbestand_leer_sms_folgt_register…` gefangen;
   zweite Mutation (Premium-SMS-Text weicht von SMS ab, z. B. Premium-Kürzung) weiter von Z. 53 gefangen.
4. Benannte Dateien grün: r8py, Fallliste-Gate `test_einstellung_gleich_mail_fallliste.py`.

## Risks & Considerations
- Kleiner Ertrag: die 14 Dateien sind fast durchweg „ähnlich", nicht doppelt — ehrlich so berichten.
- Mutationen nur per String-Ersetzung mit Sicherungskopie außerhalb des Baums.

## Open Questions
- keine (keine Produktfrage).
