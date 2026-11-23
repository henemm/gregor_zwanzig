# Adversary Dialog — rework-3264-nowcast-dubletten
Spec: docs/specs/modules/rework_3264_nowcast_dubletten.md
Datum: 2026-11-23 08:08

## Checkliste
- [x] **Input:** Testbestand mit einer Teilmengen-Dopplung (G5a) und zwei wortgleichen Asserts (G5b).
- [x] **Output:** gleiche geprueften Zusicherungen, je an einer wirksamen Stelle; ein Test (4 Stufen) und zwei Asserts weniger; Kern-Schicht der vier Dateien weiter 100 % gruen.
- [x] **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.
- [x] **AC-1:** Given der Test `test_ac2_intensity_to_text_levels` in 656 ist echte Teilmenge von `test_ac1_intensity_non_convective_unchanged` in 660 / When der Umbau fertig ist / Then ist der 656-Test entfernt, der 660-Test unveraendert vorhanden, und der Testverweis bei AC-2 in `docs/specs/modules/radar_nowcast.md` nennt statt des entfernten Tests den 660-Test (die beiden `format_now_text`-Verweise bleiben).
- [x] **AC-2:** Given `test_ac2_chain_routing_precedence` in 761 enthaelt Berlin- und Atlantik-Assert, die wortgleich im wirksamen Test `test_ac2_chain_routing_berlin_radar_atlantic_global` in 734 stehen / When der Umbau fertig ist / Then fehlen beide Asserts samt der unbenutzten Konstanten `_BERLIN_LAT/_BERLIN_LON` in 761, der Docstring beschreibt nur noch den AROME-Vorrang vor ICON-D2 (Slowenien, Schweiz-West), `_ATLANTIC` und der `within`-Assert bleiben, und der Test ist weiter unter xfail strict=False markiert.
- [x] **AC-3:** Given die Mutationen M1 (Grenze leicht/maessig in `intensity_to_text` von 1.0 auf 3.0 verschoben) und M2 (Default `is_convective` von False auf True) per String-Ersetzung mit externer Sicherungskopie / When sie vor und nach dem Umbau in der Kern-Schicht angewendet werden / Then sind vorher 656 und 660 rot, nachher 660 rot (Teilmenge verliert keinen Schutz), und nach Wiederherstellung aus der Sicherung sind beide Dateien wieder gruen.
- [x] **AC-4:** Given die Mutation M3 an der Routing-Kette in `get_nowcast` (Berlin bzw. Atlantik wird falsch geroutet) / When sie vor und nach dem Umbau mit `-m live` gegen 734 und 761 angewendet wird / Then faengt der Test in 734 die Mutation in beiden Staenden, waehrend 761 dort wegen xfail nichts faengt, und nach Wiederherstellung aus der Sicherung ist 734 wieder gruen.
- [x] **AC-5:** Given es gibt aehnliche, aber nicht doppelte Tests (`ac4_*_convective_drives_intensity` in 734 und 761, `within(_ATLANTIC)`, 656 `ac4_radar_alert_*` und `format_now_text_*` gegen 660) / When der Umbau fertig ist / Then sind diese Tests und Asserts unveraendert, und das Mutationsprotokoll nennt je Paar die Begruendung (andere Quelle, andere Werte, andere Funktion, anderer Fall), warum es bleibt.
- [x] **AC-6:** Given die vier Testdateien 656, 660, 734 und 761 / When sie namentlich mit `-m "not live"` ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen und alle 6 CI-Checks des PR sind gruen.
- [x] **AC-7:** Given der Umbau betrifft nur Testsammlung und Dokumentation / When der Diff gegen `origin/main` geprueft wird / Then liegen alle geaenderten Dateien unter `tests/` oder `docs/`, `src/services/radar_service.py` ist byte-identisch zur externen Sicherung wiederhergestellt (kein Diff gegen `origin/main`), und es gibt keine Aenderung an Gate-Konfiguration.

## Dialog

### Runde 1
**Adversary:** Mutationsskript erneut gelaufen (adversary-test-output.txt): M1, M2 nur 660 rot (656-Test ist weg); M3a/M3b 734 rot; Wiederherstellung byte-identisch, kein Diff gegen origin/main. Kernlauf der vier Dateien: 16 passed, 3 xfailed. Diff: nur die in AC-1/AC-2 genannten Entfernungen.
Code reference: tests/tdd/test_feature_656_radar_nowcast.py:115 (Test entfernt, format_now_text-Tests bleiben)
Code reference: tests/tdd/test_feature_761_icon_d2_nowcast.py:74 (nur Slowenien- und Schweiz-West-Assert bleiben, xfail strict=False Z. 73 intakt, _ATLANTIC Z. 30/70 bleibt)
Code reference: docs/specs/modules/radar_nowcast.md:102 (AC-2-Verweis auf 660-Test)
Confirmation: AC-1, AC-2, AC-3, AC-4, AC-5, AC-7 CONFIRMED. AC-6 lokal CONFIRMED (16 passed, 3 xfailed), CI-Checks erst nach PR zu belegen.
**Implementierer:** keine Einwaende.

### Runde 2
**Adversary:** Eigene Zusatzmutationen an intensity_to_text (src/services/radar_service.py:639-645), jeweils auf 656+660 (not live): A Heavy-Schwelle auf 100 -> 660 rot (und 656 ac4 Alert-Test); B Trockenschwelle 0.5 -> 660 rot; C NaN-Guard liefert HEAVY statt DRY -> alles gruen. C ist aber auch VOR dem Umbau ungefangen gewesen (der entfernte Test pruefte nur 0.0/0.3/2.5/8.0, Teilmenge von 660), also keine Regression. Kein Test, den nur der entfernte 656-Test gefangen haette: G5a ist echte Teilmenge. Spec-Verweise auf den entfernten Namen ausserhalb der Rework-Spec: keine in docs/specs/modules; Rest nur in docs/context (Analyse).
Finding F001: Severity LOW, Category edge_case, Code reference: src/services/radar_service.py:639, Description: NaN-Guard in intensity_to_text von keinem Test bewacht (vorbestehend, nicht durch diese Scheibe), Spec requirement: AC-3 (nicht betroffen), Conflict: keiner im Scope, Remediation: Nebenbefund fuer Sammel-Issue #1199.
**Implementierer:** F001 ausserhalb des Umfangs, in #1199 notieren.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

VERDICT: VERIFIED

## Geprüfte Dateien

- sha256:11ef8556d0fc00498d51d5f899ea415f85bf4e0efe88e9c44f94ae14d15700d4  docs/specs/modules/radar_nowcast.md
- sha256:63cf134c0cc4a0d0ecf70644dd1a78f86b3309c5e90166482e0d8a0bb3c18638  tests/tdd/test_feature_656_radar_nowcast.py
- sha256:628b30c5dca67447613a9d7538f6faaaaf7809dd0038f48265472965f9eaca86  tests/tdd/test_feature_761_icon_d2_nowcast.py

## Prüfbasis

- base: 4bb5fecdea6c5fc5c070b5c05b5b3122f692b30b
- blob:f79b52c825203fdc5ce008f7bdc6bf5986e2c692  docs/specs/modules/radar_nowcast.md
- blob:dc66f61cdf1d6b0f5931cf657ecbb845994d0e5a  tests/tdd/test_feature_656_radar_nowcast.py
- blob:72c678f3a150fca987824471b1fc3843f77467f2  tests/tdd/test_feature_761_icon_d2_nowcast.py
