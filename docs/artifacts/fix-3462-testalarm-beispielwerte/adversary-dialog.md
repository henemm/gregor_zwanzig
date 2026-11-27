# Adversary Dialog — fix-3462-testalarm-beispielwerte
Spec: docs/specs/modules/fix_3462_testalarm_beispielwerte.md
Datum: 2026-11-27 22:31

## Checkliste
- [x] **Input:** Trip- oder Vergleichs-Konfiguration mit aktiven Alarm-Regeln (oder keine).
- [x] **Output:** Beispiel-Änderungen, die der echte Renderer als "über" der Schwelle beurteilt, mit höchstens einer Änderung je angezeigter Bezeichnung.
- [x] **Side effects:** keine; echte Alarmwege, Renderer und Katalog bleiben unverändert.
- [x] **AC-1:** Given ein Trip mit ABSOLUTE-, DELTA- und THRESHOLD_CROSSING-Regeln, ein Ortsvergleich mit Standardmetriken und der Rückfall ohne aktive Regel / When der Test-Alarm die Beispiel-Änderungen erzeugt / Then beurteilt der echte Renderer jede Beispiel-Änderung als "über" der Schwelle (Differenz mindestens so groß wie die Schwelle).
- [x] **AC-2:** Given ein gerenderter Test-Alarm in E-Mail, Telegram, SMS und Premium-SMS, jeweils auf Deutsch und Englisch / When die Nachricht vom echten Renderer erzeugt wird / Then steht darin nie "unter deiner Alarm-Schwelle" und nie das englische Pendant der "unter"-Seite aus `alarm.abweichung.urteil`.
- [x] **AC-3:** Given ein Trip oder Ortsvergleich mit Standardmetriken, die auf dieselbe Katalog-Metrik fallen (Temperatur-Minimum und Temperatur-Änderung, Niederschlag-Summe und Niederschlag-Änderung) / When die Beispiel-Änderungen erzeugt werden / Then gibt es je angezeigter Bezeichnung höchstens eine Änderung (Temperatur erscheint genau einmal, obwohl Minimum, Maximum und Änderung aktiv sind; Niederschlag genau einmal), und ein Temperatur-Minimum-Beispiel fällt.
- [x] **AC-4:** Given eine aktive Gewitter-Regel und eine aktive Sicht-Regel / When der Test-Alarm gerendert wird / Then trägt das Gewitter-Beispiel eine Gewitter-Bezeichnung (mindestens "mäßig", nie "Luftmasse") und das Sicht-Beispiel fällt (neuer Wert kleiner als alter).
- [x] (Phase-6-Anteil bewiesen: Renderer-Tests DE/EN, vier Kanäle am echten Renderer; Staging-Nachweis in /e2e-verify) **AC-5:** Given der Staging-Server und ein Test-Postfach / When ein Test-Alarm für Trip und für Ortsvergleich auf Deutsch und Englisch tatsächlich als Mail zugestellt wird / Then enthält die zugestellte Mail kein "unter deiner Alarm-Schwelle" (bzw. englisches Pendant) und je Block keine Wettergröße doppelt.

## Dialog

### Runde 1
**Adversary:** Tests (3 Dateien, benannt): alle gruen (docs/artifacts/fix-3462-testalarm-beispielwerte/adversary-pytest.txt). 
Code reference: src/services/alert_test_service.py:83
(_werte, Betrag 1.2*|S|), :106 (_beispiel, Richtung aus Katalog), :123 (_je_bezeichnung_einmal), :191 (Dedupe vor Rueckfall). Sondierung ueber alle AlertMetric x Kind x Schwellen (0, 1, 3, 4, 5, 50, 100, 150, -25): jede Aenderung erfuellt |neu-alt| >= S, ausser Gewitter bei S > 3 (Stufe gedeckelt auf 3, Delta 3 < S). Schwelle 0 und -25 unkritisch. Rueckfall: Boeen 40->100 ueber 50 (durch Test belegt). Mutationen: 12 gefahren, 8 gefangen. Ueberlebende: (a) %-Deckel entfernt (neu=min(100,..) -> pass; und `if False`), (b) alt=max(0,..) entfernt, (c) Gewitter max(2)/min(3) entfernt, (d) Dedupe-Richtung auf 'increase' (aequivalent, beide Seiten heissen 'Temp').
**Implementierer:** (nicht im Kontext; Befund unten)

### Runde 2
**Adversary:** Nachbohren (a)/(b): Kein AlertMetric loest auf eine %-Einheit auf (Skript: keine Treffer), der %-Zweig ist toter Code; der Test test_ac4_..._prozent_in_0_bis_100 (tests/tdd/test_3462_testalarm_beispielwerte.py:323) prueft `all([])` und ist vakuum. Spec-Zusicherung "%-Werte 0..100" ist damit weder erreichbar noch bewacht (kein Nutzerschaden, da keine %-Metrik). Nachbohren (c): Gewitter S=1 testet nur die Mitte; S=0.5 (ceil=1 -> "Luftmasse") und S=3 (ceil 4 -> Deckel) sind ungetestet, Mutationen ueberleben. Gewitter S>=4 ist nicht "ueber" (Stufe max 3), praktisch unerreichbar (Stufenmetrik 0..3), daher LOW. Keine Spec-Verletzung der ACs 1-4 im realistischen Bereich gefunden. AC-5 erst nach Deploy in /e2e-verify, kein Defekt.
**Implementierer:** (nicht im Kontext)

## Findings
Finding: F001 | Severity: MEDIUM | Category: edge_case |
Code reference: src/services/alert_test_service.py:100
%-Deckel ist toter Code, Test tests/tdd/test_3462_testalarm_beispielwerte.py:323 prueft leere Liste (vakuum); Mutation `if False` bleibt gruen. Remediation: Test mit synthetischer %-Metrik oder Deckel streichen / Test auf Nicht-Leere pruefen.
Finding: F002 | Severity: LOW | Category: edge_case |
Code reference: src/services/alert_test_service.py:92
Gewitter-Stufe: Untergrenze 2 und Deckel 3 ungetestet (nur S=1); S>3 ergibt Delta 3 < S, nicht "ueber". Remediation: Tests fuer S=0.5 und S=3 ergaenzen.

## Confirmations
- Checkliste 1-3: CONFIRMED
  Code reference: src/services/alert_test_service.py:191
(nur Beispielwerte, Alarmwege/Renderer/Katalog unveraendert laut git diff).
- AC-1: CONFIRMED
  Code reference: src/services/alert_test_service.py:83
(Sondierung + Mutationen auf Betrag/abs/Rueckfall rot).
- AC-2: CONFIRMED
  Code reference: src/services/alert_test_service.py:83
(Tests in vier Kanaelen DE/EN gruen).
- AC-3: CONFIRMED
  Code reference: src/services/alert_test_service.py:123
(Dedupe-Mutationen rot, temp_min faellt rot bei cmp-Mutation).
- AC-4: CONFIRMED
  Code reference: src/services/alert_test_service.py:92
- AC-5: Phase-6-Anteil CONFIRMED (Renderer-Tests DE/EN, vier Kanäle), Staging-Zustellung nach Deploy in /e2e-verify.
  Code reference: src/services/alert_test_service.py:83

## Herkunft der Vorbedingungen

<!-- vom Prüfer auszufüllen, siehe `precondition_origins.py` -->

Zwischenstand Runde 2: VERIFIED mit F001 MEDIUM, F002 LOW als Test-Luecken, kein Produktivfehler.

### Runde 3
**Adversary:** Developer hat F001/F002 mit Tests geschlossen, Produktivcode laut diff gegen Sicherung unverändert.
Code reference: src/services/alert_test_service.py:100
Code reference: src/services/alert_test_service.py:92
(Prozent-Deckel Zeile 100, Gewitter-Stufe Zeile 92.)
Drei benannte Testdateien erneut gelaufen (adversary-pytest-runde3.txt). Überlebende Mutationen neu gefahren, alle jetzt rot: Deckel entfernt (rot), max(0,…) entfernt (rot), `if False` am %-Zweig (rot), Gewitter ohne Untergrenze (rot bei S=0.5), ohne Deckel 3 (rot bei S=3), beide weg (rot). Original per diff identisch wiederhergestellt. F001 und F002 geschlossen.

## Verdict
**VERIFIED**
F001 und F002 geschlossen, Mutationen rot, Produktivcode unveraendert, kein offenes Finding; AC-5 Staging-Nachweis in /e2e-verify.

## Geprüfte Dateien

- sha256:92775489749248ef59990edb0d92adafdaefddbcd53c857bde4483f1b6a02aa4  src/services/alert_test_service.py

## Prüfbasis

- base: c8e152fb53e02b86adada9e0f119fa8e6b348285
- blob:e64fc8f0d49a23978eb099fb4774735e43e6fb51  src/services/alert_test_service.py
