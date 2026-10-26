# Adversary Dialog — feat-2347-paritaets-e2e
Spec: docs/specs/modules/feat_2347_s1_paritaets_e2e.md
Datum: 2026-10-26 12:03

## Checkliste
- [x] **Input:** CI-Lauf `e2e` gegen den isolierten Stack; Unit-Lauf des Wächters. → Runde 3: Hauptlauf 3x 369 passed gegen isolierten Stack, Unit 32 passed
- [x] **Output:** Trip- und Vergleichs-Hub werden durch **dieselben** Specs mit denselben Zusicherungen geprüft; eine neue Compare-only-Spec ohne Begründung macht den Unit-Lauf rot. → Runde 1-3: beide kinds per HUB_KINDS-Schleife; neue Compare-Datei ohne Kopf macht Unit rot (F002)
- [x] **Side effects:** Testdaten mit Präfix `E2E-GZ-` (werden im `finally`/`afterAll` und durch `global.teardown.ts` geräumt); ein Zweitnutzer pro Lauf. → Runde 3: keine Hub-Objekte im Stack-Datenbestand nach den Läufen, ein Zweitnutzer je Lauf
- [x] **AC-1:** Given ein Trip und ein Ortsvergleich mit Versand-Uhrzeit 06:00 / When der Nutzer im Hub im Abschnitt `#versand` des Reiters Wetter-Metriken die Morgen-Uhrzeit auf 08:00 ändert / Then geht genau ein PUT an den jeweiligen Endpunkt, der geteilte Speicher-Chip `save-indicator` steht auf „Gespeichert" mit Uhrzeit HH:MM, der gespeicherte Stand trägt 08:00 und der Wert überlebt das Neuladen — in einer Spec, die per Schleife über beide kinds läuft. → Runde 3: Doppel-PUT 400/800/1400 ms rot je kind, Chip- und Wert-Mutationen rot
- [x] **AC-2:** Given zwei verschiedene Nutzer, A besitzt einen Trip und einen Ortsvergleich / When Nutzer B per API auf beide mit PUT schreibt / Then antwortet der Server in beiden Fällen mit Status 404 (nicht 403, nicht 200), und der Trip bzw. Vergleich von A ist per GET des Eigentümers unverändert (Name, `updated_at`/ETag) — mit genau einer Zweitnutzer-Registrierung für beide kinds. → Runde 1+3: Go-Mutationen je kind rot (404), ETag-Prüfung nicht vakuum
- [x] **AC-3:** Given der Ordner `frontend/e2e/` / When der Wächter-Unit-Test läuft / Then ist jede `*compare*.spec.ts` und jede Compare-Hub-Spec ohne Trip-Gegenstück entweder durch eine kind-Schleife oder durch einen `gz-eigenstaendig:`-Kopf (mind. 15 Zeichen Begründung) gedeckt oder steht in der expliziten Altlastliste, und die Altlastliste ist exakt (kein toter, kein konformer, kein zusätzlicher Eintrag über `ALTLAST_MAX`). → Runde 3: ALTLAST_MAX-Umgehung und KOPF_ZEILEN 300 rot, Selbsttests
- [x] **AC-4:** Given die CI-Ampel / When die Ratsche geprüft wird / Then enthält `.github/ci_e2e_specs.txt` `hub-cross-user-write-block.spec.ts` und `hub-versand-autosave-chip.spec.ts` und nicht mehr `compare-cross-user-write-block.spec.ts`, `E2E_MIN_SPECS` entspricht exakt der Listenlänge (64), `MANDANTEN_SPECS` nennt die umbenannte Datei, und `E2E_MIN_EXECUTED_HAUPT` ist der am Endstand per `--list` gemessene Wert (erwartet 369) mit fortgeschriebener Begründung. → Runde 3: 64 Einträge, 369 gemessen, toter Listeneintrag rot
- [x] **AC-5:** Given die neuen Specs und der geänderte Rest / When sie im Zielverbund (Hauptlauf der Positivliste) dreimal hintereinander laufen / Then sind alle drei Läufe grün, und die neuen sowie die in S1 angefassten Specs (`hub-*`, `compare-versand-speichert-selbst`, `trip-hub-kopf-region-aktivitaet`) enthalten kein `waitForTimeout` und kein `skip` (Wartebedingungen über `waitForResponse`/`expect.poll`); der Versand-Anhang ist aus Trip-AC-11 und AC-1 aus `compare-versand-speichert-selbst` entfernt, die übrigen Zusicherungen beider Dateien laufen unverändert grün. → Runde 3: 3x 369 passed am Endstand, kein waitForTimeout/skip, Fallzahl 6->5

## Dialog

### Runde 1
**Adversary:** Unit-Lauf 30/30 gruen, Playwright-Hauptlauf (63 Dateien ohne bug-703, eigener Lauf) 369/369 gruen; Entwickler-Zielverbund 3x 369 passed (zielverbund-1..3). Danach Mutations-Gegenprobe (Details: adversary-test-output.txt).

Finding F001
  Severity: HIGH
  Category: spec_violation
  Code reference: frontend/e2e/hub-versand-autosave-chip.spec.ts:75-78 (Begruendung im Kopf Z. 11-13)
  Description: "Genau ein PUT" wird mit page.reload() als Schranke geprueft. Das Neuladen zerstoert den JS-Kontext der Seite und damit einen noch wartenden Timer; ein verspaeteter zweiter PUT wird nie abgeschickt statt gezaehlt.
  Spec requirement: AC-1 / Implementation Details -- stabile PUT-Anzahl ueber zwei expect.poll-Abfragen statt Schlaf; Zuordnungstabelle: "Es entfaellt in S1 keine Zusicherung ersatzlos" (die ersetzte Vergleichs-AC-1 hatte 1200 ms Nachfrist).
  Conflict: Mutation in frontend/src/lib/api.ts (put ruft setTimeout(request PUT, 400) zusaetzlich auf): beide Faelle (route, vergleich) bleiben GRUEN (pw_mutA_400). Synchroner Doppel-PUT und 100 ms Verzoegerung werden rot. Die alte Spec haette 400 ms gefangen -> Regression der Schutzwirkung.
  Remediation: vor dem Reload die Anzahl ueber mindestens zwei getrennte Poll-Intervalle als konstant 1 belegen (ein einfaches expect.poll(() => puts.length).toBe(1) besteht beim ersten Durchlauf und beweist nichts). Danach 400- und 800-ms-Mutation erneut fahren.

Finding F002
  Severity: HIGH
  Category: spec_violation
  Code reference: tests/unit/test_e2e_compare_paritaet_waechter.py:90
  Description: ALTLAST_MAX = len(ALTLAST) -- die Obergrenze folgt der Liste. test_altlast_waechst_nicht_ueber_den_einfuehrungsstand kann nie rot werden.
  Spec requirement: AC-3 -- "kein zusaetzlicher Eintrag ueber ALTLAST_MAX"; ALTLAST_MAX = Laenge beim Einfuehren (48).
  Conflict: neue Datei compare-zzz-neu.spec.ts ohne Kopf + Eintrag in ALTLAST -> 19 passed. Der Fang "neue Compare-only-Spec ohne Begruendung macht den Unit-Lauf rot" ist per Altlast-Eintrag umgehbar.
  Remediation: ALTLAST_MAX = 48 als Literal.

Finding F003
  Severity: LOW
  Category: edge_case
  Code reference: tests/unit/test_e2e_compare_paritaet_waechter.py:34 und :197
  Description: test_marker_hinter_zeile_30_zaehlt_nicht baut den Fuellblock aus der Konstante KOPF_ZEILEN selbst; KOPF_ZEILEN 30->300 bleibt gruen (19 passed).
  Spec requirement: AC-3 (Kopf = erste 30 Zeilen)
  Conflict: der Selbsttest bewacht den Wert 30 nicht.
  Remediation: Fuellblock mit literal 30 Zeilen bzw. assert KOPF_ZEILEN == 30.

Finding F004
  Severity: LOW
  Category: edge_case
  Code reference: tests/unit/test_e2e_positivliste_ratschen_bindung.py:92 (Existenz nur fuer MANDANTEN_SPECS)
  Description: Listeneintrag auf nicht existierende Datei bei gleicher Laenge -> 30 passed. Die Spec nennt "Existenzpruefung rot"; der Fang liegt nur im CI-Job (ci.yml:358ff), lokal nicht demonstrierbar. E2E_MIN_EXECUTED_HAUPT +1 faengt e2e_gate.py (expected < min), -1 nicht (untere Schranke, bestehendes Design).
  Spec requirement: AC-4 Mutation
  Conflict: Unit-Ebene bewacht Existenz neuer Eintraege nicht.
  Remediation: Existenzpruefung aller Listeneintraege in den Kern-Test aufnehmen oder AC-4-Mutationstext auf CI-Ebene einschraenken.

Finding F005
  Severity: LOW
  Category: edge_case
  Code reference: frontend/e2e/hub-cross-user-write-block.spec.ts:73 und :21
  Description: (a) updated_at kommt weder in internal/model noch in internal/handler vor -> die Zusicherung vergleicht undefined mit undefined; ETag traegt die Pruefung. (b) mode serial: faellt der Trip-Fall, steht der Vergleichs-Fall auf "did not run" statt gruen (pw_mutG1) -- Folge der Ein-Registrierung-Vorgabe.
  Spec requirement: AC-2
  Conflict: leichte Abschwaechung, kein Fehlverhalten.
  Remediation: updated_at-Zeile streichen oder auf vorhandenes Feld stuetzen; Serial-Verhalten im Kopf vermerken.

Mutationsmatrix (Kurzfassung)
  ROT: Vergleichs-PUT weg (nur vergleich), Trip-PUT weg (nur route), falscher Wert 08->09 (beide), Chip-Text "Gesichert" (beide), save-time leer (beide), synchroner und 100-ms-Doppel-PUT (beide), Go-Trip-Handler auf feste Eigentuemer-ID (nur route: 200 statt 404), Go-Compare-Handler ebenso (nur vergleich), Statuspruefung gelockert + Trip-Mutation -> Namenspruefung rot ("Hijack"), E2E_MIN_SPECS +-1, Spec aus Liste, alter Name, Regel 1/2 aus, MIN_BEGRUENDUNG, ALTLAST_MAX=3, toter Altlast-Eintrag, Altmuster-Regex.
  KEIN Test rot: 400-ms-Doppel-PUT (F001), ALTLAST + neue Datei (F002), KOPF_ZEILEN 300 (F003), nicht existenter Listenname (F004), E2E_MIN_EXECUTED_HAUPT 370 auf Unit-Ebene (CI e2e_gate.py faengt es).
**Implementierer:** (nicht beteiligt, Kontextisolation)

### Runde 2
**Adversary:** Nachpruefung der Vermutungen aus Runde 1.
- Verdacht des Entwicklers (reload statt expect.poll): BESTAETIGT, siehe F001 (400 ms rutscht durch, 100 ms nicht).
- Greift die Statuszusicherung allein? Statuspruefung auf toBeGreaterThan(0) gelockert, Trip-Mutation aktiv: Fall route rot mit "Name des Eigentuemers unveraendert ... Received Hijack" (pw_mutG3) -> Namenspruefung wirksam.
- CI-Ebene: ci.yml:353-357 (E2E_MIN_SPECS als -ge, Unit-Test erzwingt Gleichheit), ci.yml:358ff Existenzpruefung aller Eintraege, e2e_gate.py:69-70 (expected < min). Lokal nicht ausfuehrbar, nur gelesen.
- AC-5: waitForTimeout/skip/fixme = 0 in hub-versand-autosave-chip, hub-cross-user-write-block, compare-versand-speichert-selbst, trip-hub-kopf-region-aktivitaet; Fallzahl compare-versand-speichert-selbst 6 -> 5; Trip-AC-11: nur der Versand-Anhang entfernt. Filter B: Entwickler-Nachweis zielverbund-1..3 je 369 passed (von mir nicht 3x wiederholt), eigener Einzellauf 369/369.
- Stack gestoppt, Mutationen per Sicherungskopie zurueckgespielt, Repo-Status identisch zum Auftragsbeginn.
**Implementierer:** (nicht beteiligt)

### Runde 3
**Adversary:** Nachpruefung der Fix-Runde 1 am aktuellen Stand, Mutationen per Sicherungskopie (Ursprung je per Vergleich wiederhergestellt).
- F001 behoben: Doppel-PUT per setTimeout in frontend/src/lib/api.ts mit 400, 800 und 1400 ms -> beide kinds ROT, Meldung "eine Geste im Versand-Abschnitt darf nur EINEN PUT ausloesen" (Expected "stabil", Received 2). Das Fenster haelt auch bei 1400 ms.
  Code reference: frontend/e2e/hub-versand-autosave-chip.spec.ts:75-95
- F002 behoben: neue Datei compare-zzz-neu.spec.ts + ALTLAST-Eintrag -> ROT test_altlast_waechst_nicht_ueber_den_einfuehrungsstand (ALTLAST_MAX = 48 Literal).
  Code reference: tests/unit/test_e2e_compare_paritaet_waechter.py:92
- F003 behoben: KOPF_ZEILEN 300 -> ROT test_marker_hinter_zeile_30_zaehlt_nicht (zusaetzlich assert KOPF_ZEILEN == 30).
  Code reference: tests/unit/test_e2e_compare_paritaet_waechter.py:34 und :201
- F004 behoben: Listeneintrag auf nicht existente Datei bei gleicher Laenge -> ROT test_jeder_positivlisten_eintrag_existiert. Pfad wird relativ zur Testdatei (Path(__file__).parents[2]) aufgeloest, Vakuum-Schutz (>= 10 Eintraege) vorhanden.
  Code reference: tests/unit/test_e2e_positivliste_ratschen_bindung.py:98-113
- F005 behoben: ETag-Quelle auf undefined gesetzt -> AC-2 (route) ROT an "GET des Eigentuemers liefert einen ETag"; Nachher-ETag ist nicht mehr vakuum. Grenze: eine echte Server-Mutation, die den ETag aendert, wurde nicht gefahren (Name/Status-Mutationen aus Runde 1 bleiben der Hauptnachweis).
  Code reference: frontend/e2e/hub-cross-user-write-block.spec.ts:54-76
- Neue Schwaechen gesucht: Fenster-Poll (6 s Timeout gegen 1,5 s Fenster, Intervall 200 ms) lief in allen Laeufen stabil; kein waitForTimeout; kein vakuum-Pfad im neuen Unit-Test gefunden. Keine neuen Findings.
- AC-5 am Endstand: Hauptlauf (63 Dateien ohne bug-703) 3x gegen jeweils neu gestarteten Stack, admin.json vorher geloescht: 369 passed (6.8 min), 369 passed (6.9 min), 369 passed (6.9 min). Unit: 32 passed.
- Weitere geaenderte Dateien erneut gesichtet: frontend/e2e/helpers.ts:588-675, frontend/e2e/compare-versand-speichert-selbst.spec.ts:136-137, frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts:993-994, frontend/e2e/passkey-angebot.spec.ts:39, .github/ci_e2e_specs.txt, .github/workflows/ci.yml:285-286, docs/reference/gates_und_ratschen.md:236, frontend/e2e/compare-cross-user-write-block.spec.ts (HEAD-Pfad, geloescht).
- Stack gestoppt; Repo-Status identisch zum Stand vor Runde 3; keine Reste (compare-zzz-neu entfernt).
**Implementierer:** (nicht beteiligt)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
**VERIFIED**

Begruendung: F001-F005 am Endstand behoben und per Mutation bestaetigt (Doppel-PUT 400/800/1400 ms rot je kind; ALTLAST_MAX-Umgehung, KOPF_ZEILEN 300, toter Listeneintrag, ETag-Vakuum rot). Hauptlauf 3x 369/369 gruen am Endstand, Unit 32 passed. Keine neuen Findings.

## Geprüfte Dateien

- sha256:4881b56c70d6d7302124bd17f51439c0560ba10a5a3b75fddaf6872721844b84  frontend/e2e/hub-cross-user-write-block.spec.ts
- sha256:8d5570275c0ebdc7b796b93adae6ac1abe9935de0b373eb58f10148f909271be  frontend/e2e/hub-versand-autosave-chip.spec.ts
- sha256:395d019ab18560025ef7548ea35d561f2cce98f8d60e9d408ccaf18919b13dda  tests/unit/test_e2e_compare_paritaet_waechter.py
- sha256:88c90f6dc45bed8adf66c45b6216e9e88b9ce21465f4998fa31b956db98d22b3  tests/unit/test_e2e_positivliste_ratschen_bindung.py

## Prüfbasis

- base: b9a103f30ad24cdcfe80372675d013f267933d1c
- blob:210327336a0d4b63566d6f23005184114e90bcf3  frontend/e2e/hub-cross-user-write-block.spec.ts
- blob:c39e5db827b2677520a772432b62d9455f19633f  frontend/e2e/hub-versand-autosave-chip.spec.ts
- blob:6c81479cd3912fe417c1bb28a1746ca700e3021f  tests/unit/test_e2e_compare_paritaet_waechter.py
- blob:a639bcfdd3c575e7dc44001fa0792b5d9484cae6  tests/unit/test_e2e_positivliste_ratschen_bindung.py
