# Adversary Dialog — rework-3266-fixloop-doppelte-tests
Spec: docs/specs/modules/rework_3266_fixloop_dubletten.md
Datum: 2026-11-23 11:38

## Checkliste
- [x] **Input:** Testbestand mit einer Teilmengen-Dopplung (zwei Zeilen im Jeder-Kanal-Test gegen den SMS-Waechter).
- [x] **Output:** gleiche geprueften Zusicherungen, je an einer wirksamen Stelle; zwei Zeilen weniger; Kern-Schicht der 14 Dateien weiter 100 % gruen.
- [x] **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.
- [x] **AC-1:** Given die Zeilen 117-118 in `test_f1_altbestand_leer_jeder_kanal_folgt_editor` sind echte Teilmenge von Z. 51-53 des SMS-Waechters / When der Umbau fertig ist / Then sind diese beiden Zeilen sowie die dann ungenutzten Dict-Schluessel `sms`, `premium_sms`, `sms_roh` in `_alle_kanaele` und die Konstante `_SMS_KUERZEL` entfernt, der Docstring nennt den SMS-Test als Waechter fuer SMS und Premium-SMS, und der Testname bleibt unveraendert.
- [x] **AC-2:** Given die Mutation M1 (`FORECAST_THP` in `src/output/tokens/builder.py` von `"TH+:"` auf `"TX+:"`) per String-Ersetzung mit externer Sicherungskopie / When sie vor und nach dem Umbau in der Kern-Schicht auf `test_3047_r8py_luecken.py` angewendet wird / Then wird sie vorher von beiden f1-Tests gefangen, nachher weiterhin von `test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert`, und nach Wiederherstellung aus der Sicherung ist die Datei wieder gruen.
- [x] **AC-3:** Given die Mutation M2, bei der der Premium-SMS-Text von der SMS abweicht, per String-Ersetzung mit externer Sicherungskopie / When sie nach dem Umbau auf `test_3047_r8py_luecken.py` angewendet wird / Then faengt weiterhin der SMS-Waechter (Premium gleich SMS) die Mutation, und nach Wiederherstellung aus der Sicherung ist die Datei wieder gruen.
- [x] **AC-4:** Given die 14 Testdateien der Gruppe und das Gate `tests/tdd/test_einstellung_gleich_mail_fallliste.py` / When sie namentlich mit `-m "not live"` ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen und alle 6 CI-Checks des PR sind gruen.
- [x] **AC-5:** Given die uebrigen Paare sind nur aehnlich, nicht doppelt / When der Umbau fertig ist / Then ist ausser den in AC-1 genannten Zeilen und Hilfsdaten kein Test, kein Helfer und keine Datei geloescht, alle geaenderten Dateien liegen unter `tests/` oder `docs/`, der Produktionscode ist byte-identisch zur Sicherung wiederhergestellt, und das Protokoll nennt ehrlich, dass der Ertrag klein ist (eine Teilmenge in 101 Testfunktionen) und begruendet je bleibendem Paar, warum es bleibt.

## Dialog

### Runde 1
**Adversary:**
Teilmenge geprueft (Code reference: tests/tdd/test_3047_r8py_luecken.py:35-55 Waechter, :99-114 geaenderter Test; Aenderung unter tests/ nur in dieser Datei). Entfernt: SMS-Praefixe gleich _SMS_KUERZEL und premium_sms gleich sms_roh. Der Waechter (test_3047_r8py_luecken.py:51-53) prueft denselben Trip auf den exakten SMS-String und Premium gleich Premium gespeichert gleich SMS: strikt staerker. Einziger Unterschied: der entfernte Test lief mit email_format full/compact, der Waechter mit Standard; die SMS haengt nicht vom Mail-Format ab, kein Befund. Mutationslauf selbst ausgefuehrt (adversary-test-output.txt): Basis 2 passed; M1 rot im SMS-Waechter; M2 rot im SMS-Waechter; Wiederherstellung byte-identisch, src/ ohne Unterschied, 197 passed; beide f1-Tests gesammelt; _SMS_KUERZEL und sms_roh 0 Treffer. AC-5: Paar-Begruendungen im Skriptkopf plausibel; Ertrag ehrlich klein genannt.
Code reference: tests/tdd/test_3047_r8py_luecken.py:35 (SMS-Waechter, bleibt)
Code reference: tests/tdd/test_3047_r8py_luecken.py:99 (geaenderter Jeder-Kanal-Test)
**Implementierer:** (keine Rueckfrage noetig)

### Runde 2
**Adversary:**
Eigene Gegenprobe an der wirksamen Stelle (src), nur Mutationen, die die entfernten Zeilen gefangen haetten: (a) Kuerzel VS nach VX in src/output/tokens/builder.py:533: rot im SMS-Waechter (test_3047_r8py_luecken.py:51, exakter String), 1 failed und 15 passed, danach byte-identisch wiederhergestellt.
(b) Rang Tagestief trip_default_rank 8 nach 0 in src/app/metric_catalog.py:228: ueberlebt, aber ohne Bezug zum Umbau: die SMS-Position von D ist fest, die alten Zeilen waeren ebenfalls gruen geblieben. Kein Verlust durch den Umbau.
Premium nur bei gespeicherter Liste abweichend: durch die Zusicherung in Z. 55 gedeckt. AC-4 CI-Teil (6 Checks im PR): OFFEN, erst nach PR pruefbar, kein Finding. Lokal: 14 Dateien plus Fallliste 197 passed.
**Implementierer:** (keine Rueckfrage noetig)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`); keine Produktions-Schreibstelle betroffen.

## Verdict

Keine Findings. AC-1 bis AC-3, AC-5, Input, Output, Side effects CONFIRMED (Code reference: tests/tdd/test_3047_r8py_luecken.py:51, tests/tdd/test_3047_r8py_luecken.py:99). AC-4: lokaler Teil CONFIRMED, CI-Teil OFFEN (nach PR).

VERDICT: VERIFIED

## Geprüfte Dateien

- sha256:320c50e6398a83ccb87b83edf15db48f94e2be1aa77f2b5f4a7f814a9cd0635f  tests/tdd/test_3047_r8py_luecken.py

## Prüfbasis

- base: f167eaa6a7307dccb298731077435329e8218e19
- blob:9bf725b39ed0ea2c0935f6c09b89b43793241b0a  tests/tdd/test_3047_r8py_luecken.py
