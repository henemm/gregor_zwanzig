# Context: rework-3267-i18n-doppelte-tests

## Request Summary
Issue #3267 (Teil von #1196, abgespalten aus #3208): die Sprachkatalog-Testdateien (`test_i18n_*`,
`*_zweisprachig`) auf doppelte Zusicherungen prüfen und Dopplungen entfernen. Kriterium wie
#3208/#3264/#3265/#3266: entfernt wird nur, was identisch ist (Funktion + Eingabe + Erwartung) oder
echte Teilmenge einer bleibenden Zusicherung; „ähnlich" (andere Ebene, andere Werte, anderer
Eingangsweg, anderer Kanal, anderer Nutzer) bleibt. Mutationsnachweis vorher/nachher, Kern-Schicht
100 % grün.

## Related Files (23 statt der im Issue geschätzten ~30, 4075 Zeilen, 214 Testfunktionen)
| File | Tests | Relevanz |
|------|-------|----------|
| tests/test_alarm_validator_zweisprachig.py | 6 | Radar-Validator Funktion/Prozess |
| tests/test_alarm_zweisprachig.py | 30 | **F7** |
| tests/test_amtliche_warnungen_validator_zweisprachig.py | 5 | Warnmail-Validator |
| tests/test_amtliche_warnungen_zweisprachig.py | 26 | Warnungen en, Ratsche |
| tests/test_i18n_api_katalog_paritaet.py | 3 | **F1** |
| tests/test_i18n_doku_vollstaendig.py | 11 | Doku-Wächter |
| tests/test_i18n_glossar_und_vertrag.py | 9 | Glossar/ADR/API-Vertrag |
| tests/test_i18n_inbound_katalog_paritaet.py | 5 | **F2, F6** |
| tests/test_i18n_keine_hartkodierten_nutzertexte_python.py | 5 | **F4**; Gegenseite `test_allowlist_ist_leer` |
| tests/test_i18n_kuerzel_legende_und_aktionsknoepfe.py | 4 | Legende/Knöpfe |
| tests/test_i18n_ratsche_narrow_telegram.py | 4 | **F5** |
| tests/test_i18n_vergleich_abruffehler_kontosprache.py | 2 | `_abruf_fehlertext` |
| tests/test_tagesvergleich_zeile_zweisprachig.py | 7 | Vortag-Zeile |
| tests/test_telegram_briefing_zweisprachig.py | 17 | **F3** |
| tests/test_vergleichs_mail_validator_zweisprachig.py | 4 | Vergleichs-Validator |
| tests/test_vergleichs_mail_zweisprachig.py | 26 | **F8, F9** |
| tests/test_versand_zweisprachig.py | 19 | Versand am Draht |
| tests/unit/test_i18n_sprache_zwei_nutzer.py | 3 | `resolve_user_lang` |
| tests/unit/test_i18n_format_datum_wochentag.py | 5 | `fmt_*`, Locale |
| tests/unit/test_i18n_t_platzhalter_plural_fallback.py | 7 | `t`/`tn` |
| tests/unit/test_i18n_katalog_paritaet.py | 9 | Gegenseite F1–F3: `test_echte_kataloge_paritaetisch` |
| tests/tdd/test_telegram_live_zweisprachig.py | 4 | Live-Sprachschalter |
| tests/tdd/test_gate_testmails_zweisprachig.py | 4 | `send_gate_test_mails --lang` |

## Existing Patterns
- Methode aus #3208/#3264/#3265/#3266: Mutation per String-Ersetzung mit externer Sicherungskopie
  (nie `git checkout/stash/reset`), Protokoll vorher/nachher unter `docs/artifacts/<workflow>/`.

## Dependencies
- Upstream: nur Testcode, Produktionscode unverändert.
- Downstream: Keine andere Datei importiert Helfer aus diesen 23 Modulen (Helfer liegen in `tests/helpers/`).
- Dateinamen-Verweise (Dateien bleiben alle): `tests/unit/test_paritaet_begruendung_marker.py:34-36`,
  `tests/test_i18n_doku_vollstaendig.py:38`, `tests/tdd/test_765_backend_hygiene_compliance.py:151`,
  `tests/tdd/test_telegram_live_datenwurzel_zuruecksetzen_2813.py:158`.
- Kein Testname F1–F9 steht in Falllisten (`tests/fixtures/**`) oder `.claude/`; nur in der reinen
  Messliste `docs/artifacts/perf-3209-pytest-laufzeit/collect-base.txt` (liest kein Test).

## Analysis (Summe 2: Kontext und Analyse in einem Durchgang, gegen Quelltext geprüft 2026-11-23)

### Type
Rework (Testsuite-Bereinigung, kein Produktionscode).

### Gegenseite A — `tests/unit/test_i18n_katalog_paritaet.py:45-46` `parity_errors(MESSAGES) == []`
`parity_errors` (`src/i18n/catalog.py`) meldet über alle `BEREICHE`: fehlende/kaputte Dateien,
einseitige Schlüssel, abweichende Platzhalter, Schlüsselform (`SCHLUESSEL_RE`,
`key.split(".")[0] == bereich`). Gleicher Ordner `src/i18n/messages`.
- **F1** `test_i18n_api_katalog_paritaet.py:168-174` `test_api_schluessel_und_platzhalter_paritaet` —
  ganzer Test (`set(de)==set(en)` für api + gefilterte `parity_errors`-Liste ⊂ leere Gesamtliste).
- **F2** `test_i18n_inbound_katalog_paritaet.py:52` und `:54-55` — nur diese Zeilen; `:53` (`len>=150`)
  und `:56` (Werte nicht leer) bleiben, Testname bleibt.
- **F3** `test_telegram_briefing_zweisprachig.py:235-236` (`set(de)==set(en)`, Präfix `telegram.`) —
  Präfix folgt aus der Formprüfung; `:237-239` bleiben.

### Gegenseite B — `test_i18n_keine_hartkodierten_nutzertexte_python.py:175-177` `test_allowlist_ist_leer`
`_allowlist() == {}` auf `tests/fixtures/i18n_python_allowlist.json` (fehlt die Datei: `{}`). Alle drei
Funde lesen denselben Pfad und sind bei leerer Allowlist zwingend wahr.
- **F4** `:166-172` `test_allowlist_hat_keine_toten_eintraege` — ganzer Test. Helfer `_tote_eintraege`
  bleibt (`test_ratsche_erkennt_bekannte_faelle`). Docstring Z. 17-21 („nur sinken") an den Endstand
  anpassen; Docstring-Verweis in `test_i18n_inbound_katalog_paritaet.py:78` anpassen. Spec
  `i18n_p11_api_meldungen_ratsche_2674.md` nennt den Namen historisch (bleibt).
- **F5** `test_i18n_ratsche_narrow_telegram.py:97-101` `test_kein_allowlist_eintrag_fuer_narrow_py` — ganzer Test.
- **F6** `test_i18n_inbound_katalog_paritaet.py:66-72` `test_allowlist_traegt_keine_paket_datei` —
  ganzer Test; Konstante `PAKET_MODULE` (Z. 33-35) wird unbenutzt und fällt weg.

### Weitere Teilmengen
- **F7** `test_alarm_zweisprachig.py:295` Parametrisierungsfall `limit=140` → `[60, 30]`. Gegenseite
  `:286-292` `test_ac4_sms_in_jeder_sprache_byte_gleich[fall]`: `render_fall` ruft `render_sms(msg)` mit
  Vorgabe `limit=140` (`src/output/renderers/alert/render.py:1885`) über `nachricht(fall, lang)` für
  None/de/en; Golden-Gleichheit beider Sprachen + `len <= 140` impliziert `de == en`, `len <= 140`.
- **F8** `test_vergleichs_mail_zweisprachig.py:326` (SMS Anna == SMS Bernd). Gegenseite `:244`:
  `render_kanaele(lang)[-1]` ist `render_compare_sms(result, …)` ohne `lang`
  (`tests/helpers/vergleichs_mail_fixture.py:143`) → bei beiden Nutzern identischer Aufruf. Testname bleibt.
- **F9** `test_vergleichs_mail_zweisprachig.py:307` (`treffer` auf `render_mail("en")`). Gegenseite
  `:107-108` `test_ac1_kein_deutscher_katalogtext…`: `_englisch_alles()` enthält genau
  `sichtbar(html) + text.splitlines()` von `render_mail("en")` (eingefrorene Zeit, `freeze_time`)
  plus Telegram-Zeilen → Obermenge; `treffer` zeilenweise. `:305-306` bleiben.

### Grenzfälle — bleiben (Zweifelsregel: nur durch Kombination zweier Tests impliziert)
- G1 `unit/test_i18n_katalog_paritaet.py:37-42` (alle zehn Bereichsdateien) — erst `:33` + `:45` zusammen.
- G2 `test_telegram_briefing_zweisprachig.py:88-95` — `:93` nur lückenhaft anderswo; Rumpftest bliebe.

### Geprüft, bleibt (Auswahl)
- Golden-Vergleiche ↔ Katalog-Teilstring-Tests: anderes Prüfziel (Schnappschuss vs. Katalogquelle).
- Zwei-Nutzer-Tests: Eingang über `resolve_user_lang`, fangen falsch aufgelöste Sprache.
- alarm byte_gleich ↔ ac7: `lang=None` und de-Golden nicht in ac7.
- Validator Funktion ↔ Prozess: anderer Eingangsweg.
- gate_testmails de-Basispostfach ↔ byte_gleich: nur 3 von 4 Pfaden überlappen.
- versand ac5 ↔ jeder_code / ac2 ↔ berichtsart: andere kwargs bzw. Werte.
- tagesvergleich `aehnlich[de]` ↔ `…deutsch_wie_vorher`: `lang="de"` vs. ohne `lang`.
- format_datum Locale-Test: andere Prozess-Locale als Eingabe.
- inbound `test_restbefund_p11_…`: verlangt Existenz der Allowlist-Datei, keine Teilmenge.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/test_i18n_api_katalog_paritaet.py | MODIFY | F1 Test entfernen |
| tests/test_i18n_inbound_katalog_paritaet.py | MODIFY | F2 Zeilen, F6 Test + `PAKET_MODULE`, Docstring-Verweis Z. 78 |
| tests/test_telegram_briefing_zweisprachig.py | MODIFY | F3 Zeilen |
| tests/test_i18n_keine_hartkodierten_nutzertexte_python.py | MODIFY | F4 Test + Docstring |
| tests/test_i18n_ratsche_narrow_telegram.py | MODIFY | F5 Test |
| tests/test_alarm_zweisprachig.py | MODIFY | F7 Fall 140 |
| tests/test_vergleichs_mail_zweisprachig.py | MODIFY | F8, F9 Zeilen |
| tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py | MODIFY | F10 Test |

Umfang: 8 Dateien, rund −50 Zeilen, nur Tests.

### F10 — Katalog-Parität außerhalb der Dateigruppe (in dieses Ticket aufgenommen)
`tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py:232-236` `test_ac6_katalog_paritaet_de_en`
(`parity_errors(MESSAGES_DIR) == []`, `MESSAGES_DIR` aus `i18n.catalog` = `src/i18n/messages`) ist
wörtlich identisch mit Gegenseite A. Es ist eine reine Sprachkatalog-Zusicherung und gehört damit
fachlich zu diesem Ticket; ganzer Test entfällt, Import `parity_errors`/`MESSAGES_DIR` nur entfernen,
wenn sonst unbenutzt. Name in keiner Fallliste/Gate.

## Risks & Considerations
- Mutationsnachweis muss zeigen: jede Verfälschung, die ein entfernter Teil fing, fängt die Gegenseite
  weiterhin (vorher und nachher gleich rot).
- F4 betrifft eine dokumentierte Ratsche: `test_allowlist_ist_leer` ist in
  `docs/reference/gates_und_ratschen.md` und `i18n_konventionen.md` als Endstand-Wächter genannt und bleibt.
