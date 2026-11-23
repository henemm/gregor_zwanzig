# Adversary Dialog — rework-3267-i18n-doppelte-tests
Spec: docs/specs/modules/rework_3267_i18n_dubletten.md
Datum: 2026-11-23 18:45

## Checkliste
- [x] **Input:** Testbestand mit zehn Dopplungen (F1-F10) in der Sprachkatalog-Testgruppe.
- [x] **Output:** gleiche geprueften Zusicherungen, je an einer wirksamen Stelle; rund 50 Zeilen weniger; Kern-Schicht der betroffenen Dateien weiter 100 % gruen.
- [x] **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.
- [x] **AC-1:** Given die Funde F1-F10 sind identisch oder echte Teilmenge einer bleibenden Zusicherung / When der Umbau fertig ist / Then sind F1, F4, F5, F6 und F10 als ganze Tests entfernt (F6 inklusive der dann unbenutzten Konstante `PAKET_MODULE`, F10 mit Import-Entfernung nur wenn sonst unbenutzt), von F2, F3, F7, F8 und F9 nur die genannten Zeilen beziehungsweise der Fall `limit=140`, und die Testnamen dieser Teil-Faelle bleiben unveraendert.
- [x] **AC-2:** Given die Gegenseiten `test_echte_kataloge_paritaet` (A) in `tests/unit/test_i18n_katalog_paritaet.py`, `test_allowlist_ist_leer` (B) und die uebrigen genannten Gegenseiten (`byte_gleich`, `:244`, `ac1`) / When der Umbau fertig ist / Then sind diese Tests und ihre Dateien byte-identisch zum Stand davor und laufen gruen.
- [x] **AC-3:** Given Verfaelschungen M1-M5 (einseitiger Katalogschluessel, Allowlist-Eintrag, SMS-Limit, nutzerabhaengige Vergleichs-SMS, deutscher Text in englischer Mail) per String-Ersetzung mit externer Sicherungskopie / When sie vor und nach dem Umbau in der Kern-Schicht angewendet werden / Then wird jede Verfaelschung, die ein entfernter Teil vorher fing, nachher weiterhin von der Gegenseite gefangen, und nach Wiederherstellung aus der Sicherung sind die Dateien wieder gruen.
- [x] **AC-4:** Given die Grenzfaelle G1 (`unit/test_i18n_katalog_paritaet.py:37-42`) und G2 (`test_telegram_briefing_zweisprachig.py:88-95`) sowie alles unter "Geprueft, bleibt" / When der Umbau fertig ist / Then sind diese Tests und Zeilen unveraendert, und das Protokoll begruendet je bleibendem Paar, warum es nur aehnlich und nicht doppelt ist.
- [x] **AC-5:** Given der Docstring Z. 17-21 in `test_i18n_keine_hartkodierten_nutzertexte_python.py` beschreibt eine sinkende Allowlist und `test_i18n_inbound_katalog_paritaet.py:78` verweist auf den entfernten F4-Test / When der Umbau fertig ist / Then beschreibt der Docstring den Endstand (leere Allowlist, `test_allowlist_ist_leer` als Waechter) und der Verweis nennt keinen entfernten Test mehr, waehrend der Helfer `_tote_eintraege` und `test_ratsche_erkennt_bekannte_faelle` bleiben.
- [x] **AC-6:** Given alle betroffenen Testdateien, beide Gegenseiten und die Namensverweis-Dateien / When sie namentlich mit `-m "not live"` ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen, alle 6 CI-Checks des PR sind gruen, alle geaenderten Dateien liegen unter `tests/` oder `docs/`, und der Produktionscode ist byte-identisch zur Sicherung wiederhergestellt.

## Dialog

### Runde 1
**Adversary:** Diff gegen Spec geprueft (8 Dateien, +6/-64). Testlauf der 13 benannten Dateien (-m "not live"): 2196 passed (docs/artifacts/rework-3267-i18n-doppelte-tests/adversary-test-output.txt). Mutationsskript selbst neu gelaufen: M1a-e, M2, M3a/b, M4, M5 nachher alle rot durch die Gegenseiten, byte-identisch wiederhergestellt, src/ ohne Diff.

Confirmation AC-1 (F1-F10 entfernt, Teil-Testnamen bleiben), je Datei:
  Code reference: tests/test_i18n_api_katalog_paritaet.py:165
  Code reference: tests/test_i18n_inbound_katalog_paritaet.py:45
  Code reference: tests/test_telegram_briefing_zweisprachig.py:233
  Code reference: tests/test_i18n_keine_hartkodierten_nutzertexte_python.py:161
  Code reference: tests/test_i18n_ratsche_narrow_telegram.py:91
  Code reference: tests/test_alarm_zweisprachig.py:295
  Code reference: tests/test_vergleichs_mail_zweisprachig.py:304
  Code reference: tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py:228
  Evidence: Diff zeigt genau die Spec-Entfernungen; F6 samt PAKET_MODULE; ungenutzte Imports (parity_errors, ALLOWLIST) mit entfernt, benutzte (json, REPO) bleiben. Status: CONFIRMED
Confirmation AC-2: Gegenseite A (tests/unit/test_i18n_katalog_paritaet.py) nicht im Diff; B `test_allowlist_ist_leer` unveraendert (:164); alle gruen. CONFIRMED.
Confirmation AC-4: G1/G2 nicht im Diff; Golden-/Zwei-Nutzer-Tests unveraendert. CONFIRMED.
Confirmation AC-5: Modul-Docstring Z. 17-19 beschreibt leere Allowlist mit `test_allowlist_ist_leer`; tests/test_i18n_inbound_katalog_paritaet.py:58-61 nennt keinen entfernten Test; `_tote_eintraege`, `test_ratsche_erkennt_bekannte_faelle` weiter gruen. Kein Bezug auf entfernte Namen ausserhalb historischer Specs. CONFIRMED.
Confirmation AC-3: siehe eigene Mutationen in Runde 2 plus Skriptlauf. CONFIRMED.
Confirmation AC-6: 2196 passed; nur tests/ und docs/ geaendert (src/, tests/fixtures, tests/helpers ohne Diff gegen origin/main). CI-Checks des PR stehen noch aus (nicht Gegenstand des Adversary-Laufs).
**Implementierer:** keine Rueckmeldung noetig.

### Runde 2
**Adversary:** Eigene Mutationen jenseits des Skripts, Frage: wirkt die Zusicherung dort, wo sie geprueft wird?
- F2: en/inbound.json Platzhalter `{trip_name}` -> `{trip}`: rot durch Gegenseite A (`test_echte_kataloge_paritaetisch`), 1 failed / 161 passed.
- F3: nur-en-Schluessel in telegram: Skript M1d, A und `test_ac9_...` rot; Fremdpraefix in beiden Sprachen (M1e) durch A rot (Formpruefung).
- F5/F6: Allowlist mit Eintrag `narrow.py: 0` -> `test_allowlist_ist_leer` rot. Allowlist-Datei fehlt ganz -> B bleibt gruen (wie vorher bei F5/F6, die dann frueh zurueckkehrten), aber `test_restbefund_p11_nur_solange_allowlistet` rot: also kein Verlust.
- F8: Vergleichs-SMS wird von der Fixture ohne `lang` aufgerufen und `render_compare_sms` hat keinen Sprachparameter (TypeError-Test); die entfernte Zeile war eine Tautologie, `:244` + TypeError-Test bleiben. M4 rot.
- F9: deutscher Titel im Text-Teil der EN-Mail (comparison.py:492 auf "de"): `ac1_kein_deutscher...`, `ac1_ueberschriften...` und `ac6_reihenfolge` rot; `_englisch_alles` enthaelt `text.splitlines()`, also Obermenge.
- F7: byte_gleich (Standardlimit 140, None/de/en) faengt M3a; M3b (limit+200) faengt `[60]`/`[30]`.
Alle Mutationen byte-identisch aus externer Sicherung zurueckgenommen (cmp), kein Diff in src/, tests/fixtures.
Schwaechen: keine Schutzluecke gefunden. Beobachtung (kein Finding): M1c (inbound-Schluessel einseitig) wird nur noch von A gefangen, wie in der Spec vorgesehen.
**Implementierer:** keine Rueckmeldung noetig.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

VERDICT: VERIFIED
Tests: 2196 passed, 0 failed (13 benannte Dateien, -m "not live"); Skriptlauf 233 passed Basis, alle Mutationen nachher durch Gegenseiten rot, Wiederherstellung byte-identisch.
Findings: keine. Regressions: keine. Checklist: 7/7 proven.

## Geprüfte Dateien

- sha256:d27c239cb75b57f71108d29e9e3997901e03c733b73b9826ef3355897d337722  tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py
- sha256:a90f360b674dcddf7c5d8d12824903c003f5f2b52884abc180157601fd62a741  tests/test_alarm_zweisprachig.py
- sha256:ca9c215dd808742fc5c6a5227a8d8feb1b8b3f587838931669c2c6dec01d7367  tests/test_i18n_api_katalog_paritaet.py
- sha256:78f1caaea8f1a562d6254b225666724071b9eb735f707b2d3e4f1c5647322ac7  tests/test_i18n_inbound_katalog_paritaet.py
- sha256:f5e46dca0e5fdf7a87d18b1aa863ef65bf0fac6d28dc45fb85bc97b1869329c5  tests/test_i18n_keine_hartkodierten_nutzertexte_python.py
- sha256:19447e94c6d2d7083ddcfd5f042263c016e4c57d469b28e031dbed3b8af3e5ca  tests/test_i18n_ratsche_narrow_telegram.py
- sha256:bc1c6005c5f1920badd7a5409785c7c58815470be9e335cbf443dac58cbfc607  tests/test_telegram_briefing_zweisprachig.py
- sha256:ac6650fe3ff596dd4503d7537b168bcd60dfea52aabf672dab7a5414306a4f46  tests/test_vergleichs_mail_zweisprachig.py

## Prüfbasis

- base: c44ecac03cddc46a3dc0f24fd69f23790f7619db
- blob:3216fec295f16c1c1b00aa299392e70fd66a2ec3  tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py
- blob:9819a3114fce4454b370d975a3c3ffb3fcf8c9da  tests/test_alarm_zweisprachig.py
- blob:7c5423d081fb8e0fd9516e8361f0336325b19c54  tests/test_i18n_api_katalog_paritaet.py
- blob:731f8cd316e8d42e0b90a0b0f10d47bc65ce0b23  tests/test_i18n_inbound_katalog_paritaet.py
- blob:4f85e16e8f5749cd94f4fbc500b8730157284ef7  tests/test_i18n_keine_hartkodierten_nutzertexte_python.py
- blob:47706831100f9b8a13a7cd1c191a5ef250348293  tests/test_i18n_ratsche_narrow_telegram.py
- blob:eb087bceaf8c7aeae51f5e36995fa32b3233fddb  tests/test_telegram_briefing_zweisprachig.py
- blob:d2995ac467dea6904f729c05895e177a188fd48a  tests/test_vergleichs_mail_zweisprachig.py

## Geprüfte Dateien

- sha256:d27c239cb75b57f71108d29e9e3997901e03c733b73b9826ef3355897d337722  tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py
- sha256:a90f360b674dcddf7c5d8d12824903c003f5f2b52884abc180157601fd62a741  tests/test_alarm_zweisprachig.py
- sha256:ca9c215dd808742fc5c6a5227a8d8feb1b8b3f587838931669c2c6dec01d7367  tests/test_i18n_api_katalog_paritaet.py
- sha256:78f1caaea8f1a562d6254b225666724071b9eb735f707b2d3e4f1c5647322ac7  tests/test_i18n_inbound_katalog_paritaet.py
- sha256:f5e46dca0e5fdf7a87d18b1aa863ef65bf0fac6d28dc45fb85bc97b1869329c5  tests/test_i18n_keine_hartkodierten_nutzertexte_python.py
- sha256:19447e94c6d2d7083ddcfd5f042263c016e4c57d469b28e031dbed3b8af3e5ca  tests/test_i18n_ratsche_narrow_telegram.py
- sha256:bc1c6005c5f1920badd7a5409785c7c58815470be9e335cbf443dac58cbfc607  tests/test_telegram_briefing_zweisprachig.py
- sha256:ac6650fe3ff596dd4503d7537b168bcd60dfea52aabf672dab7a5414306a4f46  tests/test_vergleichs_mail_zweisprachig.py

## Prüfbasis

- base: c44ecac03cddc46a3dc0f24fd69f23790f7619db
- blob:3216fec295f16c1c1b00aa299392e70fd66a2ec3  tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py
- blob:9819a3114fce4454b370d975a3c3ffb3fcf8c9da  tests/test_alarm_zweisprachig.py
- blob:7c5423d081fb8e0fd9516e8361f0336325b19c54  tests/test_i18n_api_katalog_paritaet.py
- blob:731f8cd316e8d42e0b90a0b0f10d47bc65ce0b23  tests/test_i18n_inbound_katalog_paritaet.py
- blob:4f85e16e8f5749cd94f4fbc500b8730157284ef7  tests/test_i18n_keine_hartkodierten_nutzertexte_python.py
- blob:47706831100f9b8a13a7cd1c191a5ef250348293  tests/test_i18n_ratsche_narrow_telegram.py
- blob:eb087bceaf8c7aeae51f5e36995fa32b3233fddb  tests/test_telegram_briefing_zweisprachig.py
- blob:d2995ac467dea6904f729c05895e177a188fd48a  tests/test_vergleichs_mail_zweisprachig.py
