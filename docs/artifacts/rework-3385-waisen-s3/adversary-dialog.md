# Adversary Dialog — rework-3385-waisen-s3
Spec: docs/specs/modules/rework_3385_waisen_s3.md
Datum: 2026-11-26 07:10

## Checkliste
- [x] **Input:** Quelltext von `frontend/src`.
- [x] **Output:** Wächter grün, solange es keine Waise (ohne `AUSNAHMEN`) gibt; `BEKANNTE_WAISEN` ist leer, `OBERGRENZE_WAISEN` ist 0 und gleicht der Listenlänge; jede neue Datei ohne Aufrufer macht ihn rot. Löschung ohne Funktionsänderung.
- [x] **Side effects:** Keine sichtbare Änderung für Nutzer; Ratschenzahlen, Katalog und Goldens schrumpfen.
- [x] **AC-1:** Given die 7 Dateien der Gruppe S3 (`VTBriefingChannels.svelte`, `VTLaufzeitRoute.svelte`, `VTLaufzeitVergleich.svelte`, `VTNextBriefing.svelte`, `VTSchedulePlan.svelte`, `channelContactLabel.ts`, `vtBriefingChannelsText.ts`) / When das Dateisystem nach S3 geprüft wird / Then existiert keine der 7 Dateien mehr, kein Produktionscode importiert die gelöschten Basisnamen, und `EinstellTabelle.svelte` besteht weiter.
- [x] **AC-2:** Given `BEKANNTE_WAISEN` geleert und `OBERGRENZE_WAISEN` auf 0 gesetzt / When der Wächter die Erreichbarkeit ab `routes/` und `src/*.ts` berechnet / Then ist die Waisenmenge (ohne `AUSNAHMEN`) leer, `OBERGRENZE_WAISEN` ist die feste Literal-Konstante 0 und gleicht `BEKANNTE_WAISEN.length`, der Test ist grün, und eine neu angelegte Datei ohne Aufrufer macht ihn rot.
- [x] **AC-3:** Given der Kopfkommentar von `waisen_waechter.test.ts` zur Ratsche / When er gelesen wird / Then nennt er „BEKANNTE_WAISEN.length === OBERGRENZE_WAISEN“ (exakte Gleichheit, wie die Logik in `pruefeRatsche`) und kein „<=“ zwischen beiden.
- [x] **AC-4:** Given der echte Anlege-Editor des Ortsvergleichs (`CompareNewEditor` mit `AlarmeTab` und `ZustellungTab`) / When im Reiter Alarme der Cooldown auf 60 gesetzt und danach gelöscht wird (ebenso Stille Stunden) / Then übergibt der Editor dem Reiter Zustellung den Stand im Prop `preset` und speichert ihn im POST der Aktivierung: zuerst mit 60, danach ohne 60.
- [x] **AC-5:** Given die drei Fallliste-Fälle `E-R8-F3N-VERSAND-ORTE-DE`, `E-R8-F3N-VERSAND-ORTE-EN`, `E-R8-F3N-VERSAND-TRIP` / When `versand_telegram_je_kontext.test.ts` gelöscht ist / Then bestehen alle drei mit derselben Kennung weiter: `TRIP` als `gruen` auf dem neuen Trip-Karten-Testfall (AC-6), `ORTE-DE` und `ORTE-EN` als `ausnahme` mit `#3385`-Verweis und dem Grund „Editor zeigt die Telegram-Zeilengrenze nicht mehr“ (Befund: die Orte-Karte kennzeichnet Telegram je Zeile nicht), und der Verweis-Wächter der Fallliste ist grün.
- [x] **AC-6:** Given die Karte „Was steht wo“ beim Trip mit neun Zeilen, deren Telegram-Zellen ab der achten Zeile die Marke `nur_tageswert` tragen / When die Karte gerendert wird / Then steht „nur Tageswert“ genau in den Telegram-Zellen der Zeilen 8 und 9 und in keiner der ersten 7.
- [x] **AC-7:** Given die Löschung / When der Importscan im Lösch-Nachweis über `frontend/src` und `frontend/e2e` läuft und die Zahlenratschen (`BESTAND_OBERGRENZE`, ink4, `hoechststand`/`HOECHSTSTAND` ein_katalog, `EINGEFROREN` mit `EINGEFROREN_SOLL_ANZAHL` und ac2-Endbilanz samt Spec, Zählungen in `keine_hartkodierten_nutzertexte`, Katalogschlüssel de/en) geprüft werden / Then findet der Scan keinen Import der Löschliste mehr, die 11 reinen Waisentests sind gelöscht, die gemischten Tests nur um die Waisen-Fälle gekürzt und grün, die 14 HTML-Goldens von f6 gelöscht, `funktionen.de.txt` und `funktionen.en.txt` mit dem Projektwerkzeug neu erzeugt (Unterschied nur die 6 Zeilen `vtBriefingLeadText`/`vtBriefingSubTexts`), alle Zahlen stimmen mit der Messung nach dem Löschen überein und sind nur gesunken, `hoechststand` (JSON) und `HOECHSTSTAND` (Python) sind identisch, `EINGEFROREN` hat 10 Einträge (FACHLICH 5, DARSTELLUNG 2, HERKUNFT 3), de und en führen dieselbe Schlüsselmenge, kein Schlüssel ohne Verwender bleibt, `bausteine.json` ist unverändert.
- [x] **AC-8:** Given die Seiten und Ansichten (insbesondere Trip-Editor, Vergleichs-Editor, Hub-Übersicht, Alarme- und Zustellung-Reiter) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die svelte-check-Zahlen (Fehler/Warnungen) wurden vor dem Löschen auf dem Branch-Stand gemessen und steigen nachher nicht, und für Nutzer gibt es keine sichtbare Änderung.
- [x] **AC-9:** Given `EinstellTabelle.svelte` samt Test, `.claude/hooks`, alle Browser-Specs unter `frontend/e2e/` (#3374, darunter `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`) und die CI-Positivliste samt `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` / When S3 geliefert ist / Then sind diese Dateien und Werte unverändert.
- [x] **AC-10:** Given der Reaktivitäts-Wächter `reaktivitaet_waechter.test.ts` nach dem Löschen / When er läuft / Then hängt keiner seiner Selbsttests mehr an einem gelöschten Modul (die Fälle „sprachfreier Export → []“ und „tr-Helfer im Startwert → 3 eingefroren“ laufen auf erfundenen Mini-Modulen mit unveränderten Erwartungswerten), der Bereich „F6 #2655 Versand-Reiter“ samt seinem Messaufbau-Test ist gestrichen, die Wächter der übrigen Bereiche (F7 Zählung 2, F8 Zählung 0, „jede Ausnahme trifft noch einen Fund“) sind unverändert grün, und `TelegramKurzstilToggle.svelte` bleibt über den Bereich F7 (`AlarmeTab.svelte`) gescannt.

## Dialog

### Runde 1
**Adversary:** Loeschung, gekuerzte Tests (sms_unbestaetigt, naechstes_briefing_verdrahtung, versand_tab_sprache: nur Faelle der geloeschten Bausteine entfallen, Helferzusicherungen bleiben), Katalog, Fallliste und Ratschen gegen die Spec geprueft; 16 Mutationen per String-Ersetzung mit Sicherung im Scratchpad, jeweils zurueckgenommen und auf Identitaet geprueft, Index unveraendert. Ergebnis: 15 rot, eine NICHT.

Finding:
  ID: F001
  Severity: MEDIUM
  Category: spec_violation
  Code reference: frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts:68
  Description: Der Bereich F7 listet nur AlarmeTab.svelte, AlertChannelPicker.svelte und alerts-tab/; dateienUnter (reaktivitaet_scan.ts:218) scannt genau die Eintraege und folgt keinen Importen. TelegramKurzstilToggle.svelte (importiert in AlarmeTab.svelte:33) steht in keinem Bereich mehr, der gestrichene Bereich F6 hatte sie ausdruecklich gelistet. Mutation: $derived(tr('versand.status.bestaetigt')) in TelegramKurzstilToggle.svelte eingefuegt, reaktivitaet_waechter bleibt GRUEN (pass 14, fail 0); dieselbe Mutation in AlarmeTab.svelte ist rot.
  Spec requirement: AC-10 — TelegramKurzstilToggle.svelte bleibt ueber den Bereich F7 (AlarmeTab.svelte) gescannt
  Conflict: Die Komponente wird real nicht mehr gescannt; die Schutzwirkung ist geschwaecht, der Kommentar Z.46 der Testdatei behauptet das Gegenteil.
  Remediation: 'lib/components/shared/TelegramKurzstilToggle.svelte' in den Bereich F7 aufnehmen, oder Spec und Kommentar auf "nicht gescannt, da ohne $derived/tr" korrigieren.

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: tests/unit/test_i18n_katalog_paritaet.py
  Description: Mutation "lebenden en-Schluessel (versand.status.bestaetigt) entfernen" bleibt im Python-Paritaetstest gruen (9 passed); nur frontend paritaet_de_en.test.ts wird rot. Kein S3-Defekt, informativ.
  Spec requirement: AC-7 — de und en fuehren dieselbe Schluesselmenge
  Conflict: Bewacht wird die Zusicherung im Frontend-Test; Suite gruen.
  Remediation: keine fuer S3 noetig.

**Implementierer:** nicht Teil dieses Laufs; Fix durch den Orchestrator.

### Runde 2
**Adversary:** Nachpruefung: reaktivitaet_waechter Mini-Module laufen auf echten Mini-Dateien (sprachfrei.ts -> [], textHelfer.ts mit tr() -> 3 eingefroren); der zweite Import `import { t } from '$lib/i18n'` aendert die Aussage nicht, der Fall sendTargetLabel/ziel() ('6 derived') haengt nur vom ersten Import ab. F7 (2) und F8 (0) gruen, nicht vakuum. Waisen-Waechter mit leerer Liste: erfundene Waise rot. Gesamtlauf npm test 11512 pass/0 fail, build 0, svelte-check 32/70, pytest 355 passed.
**Implementierer:** F001 offen, siehe Verdict.

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts:8
  Evidence: Grep nach den 7 Basisnamen in frontend/src und frontend/e2e: nur Kommentare, kein import/from; npm run build Exit 0; Ordner versand-tab mit den lebenden .ts-Modulen intakt; einzige dynamische Schluesselbildung nextBriefingText.ts:61 (wochentag, lebend).
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:65
  Evidence: OBERGRENZE_WAISEN = 0, BEKANNTE_WAISEN leer (Z.55). Mutation 0->1 rot; neue Datei lib/zzorphan.ts rot; Wiederanlegen VTNextBriefing.svelte rot (Loeschnachweis + Waechter).
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:27
  Evidence: Kopfkommentar nennt "BEKANNTE_WAISEN.length === OBERGRENZE_WAISEN"; Mutation auf "<=" rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:219
  Evidence: zustellungAbo mit alert_cooldown_minutes/alert_quiet_from. Mutationen Cooldown->undefined, quiet_from->undefined (Editor) und onCooldownChange no-op (compare/alarmePropsAus.ts:165) je rot im Test hub_geteilte_felder_cooldown_quiet_konsistent.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:1838
  Evidence: ORTE-DE/EN ausnahme mit #3385-Verweis und #3390 (Issue existiert, offen), TRIP gruen auf dem Karten-Test (Z.1871). Mutationen: Testname verfaelscht rot, Verweis ohne #3385 rot; test_einstellung_gleich_mail_fallliste.py gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts:45
  Evidence: Marke nur_tageswert je Zelle aus der Antwort; Mutation des Marken-Textschluessels laesst was_steht_wo_karte.test.ts rot werden; der Test prueft Zeile 8/9 exakt und alle anderen Zellen ohne Marke.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:707
  Evidence: BESTAND_OBERGRENZE 162 (Mutation 163 rot im wirkort-Test), EINGEFROREN_SOLL_ANZAHL 10 (context_herkunft_zweige_eingefroren.test.ts:318; Mutation 13 rot), de/en versand.json je 36 gleiche Schluessel entfernt, keiner hat noch Verwender (nur Kommentare), Verwender-Test rot bei Zusatzschluessel, paritaet_de_en rot bei fehlendem en-Schluessel; Elementliste: 28 laufzeit-Eintraege, alle i18n_key in de und en vorhanden.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: docs/artifacts/rework-3385-waisen-s3/adversary-test-output.txt:1
  Evidence: Eigener Lauf: npm test 11512 pass, 0 fail; build Exit 0; svelte-check 32 Fehler / 70 Warnungen (Baseline 32/71).
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: docs/artifacts/rework-3385-waisen-s3/test-green-output.txt:1
  Evidence: Index enthaelt weder .claude/hooks noch frontend/e2e noch CI-Positivliste noch EinstellTabelle; pytest test_e2e_positivliste_ratschen_bindung gruen (355 passed).
  Status: CONFIRMED

Confirmation:
  AC: AC-10
  Code reference: frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts:68
  Evidence: Mini-Module sprachfrei.ts/textHelfer.ts liefern [] bzw. 3 eingefroren; F6-Bereich samt Messaufbau gestrichen; F7/F8 gruen und nicht vakuum (AlarmeTab-Mutation rot). TelegramKurzstilToggle-Teil: siehe F001 (DISPROVEN).
  Status: CONFIRMED

Mutationen (Datei, Verfaelschung, Ergebnis):
1. waisen_waechter.test.ts OBERGRENZE_WAISEN 0->1: rot
2. neue Datei lib/zzorphan.ts: rot
3. CompareNewEditor.svelte alert_cooldown_minutes -> undefined: rot
4. CompareNewEditor.svelte alert_quiet_from -> undefined: rot
5. alarmePropsAus.ts onCooldownChange no-op: rot
6. wasStehtWoAnsicht.ts nur_tageswert-Textschluessel vertauscht: rot
7. fallliste_editor.json Trip-Testname verfaelscht: rot
8. fallliste_editor.json Verweis ohne #3385: rot
9. bausteine_waechter_regeln.ts BESTAND_OBERGRENZE 162->163: rot (nur im wirkort-Test)
10. context_herkunft_zweige_eingefroren.test.ts EINGEFROREN_SOLL_ANZAHL 10->13: rot
11. de/versand.json unbenutzter Zusatzschluessel: rot
12. en/versand.json lebenden Schluessel entfernt: rot im Frontend, Python gruen (F002)
13. TelegramKurzstilToggle.svelte $derived(tr()) eingefuegt: GRUEN (F001)
14. AlarmeTab.svelte $derived(tr()) eingefuegt: rot (Gegenprobe)
15. waisen_waechter.test.ts Kopfkommentar === -> <=: rot
16. Wiederanlegen VTNextBriefing.svelte: rot

## Herkunft der Vorbedingungen

Nicht anwendbar: die Scheibe loescht Frontend-Dateien und aendert Waechter-Konstanten; es gibt keine Testvorbedingungen mit Feld-Zuweisungen im Sinne von precondition_origins.py (Kein Feld mit Test-Zuweisung gefunden - nichts zu pruefen).

## Verdict

### Runde 3
**Adversary:** F001 nachgeprueft: reaktivitaet_waechter.test.ts:71 listet TelegramKurzstilToggle.svelte jetzt in Bereich F7. Eigene Mutation ($derived(tr()) in der Komponente) ist jetzt rot (pass 12, fail 2), Rücknahme byte-gleich; unmutiert pass 14, fail 0. AC-10 Stichprobe (Mini-Module, F7 2, F8 0) gruen. F001 behoben, F002 bleibt informativ.
**Implementierer:** Datei in Bereich F7 aufgenommen, Kommentar korrigiert.

Confirmation:
  AC: AC-10
  Code reference: frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts:71
  Evidence: TelegramKurzstilToggle.svelte steht ausdruecklich im Bereich F7; Mutation rot, Gegenprobe gruen.
  Status: CONFIRMED

Mutation 17: TelegramKurzstilToggle.svelte $derived(tr()) eingefuegt: rot (nach Fix).

VERDICT: VERIFIED
F001 behoben (Runde 3), F002 LOW informativ. Tests: 11512 passed (Runde 1) plus reaktivitaet_waechter 14 passed, 0 failed.

## Geprüfte Dateien

- sha256:795fc1feaf29b67eac043302783d29c6d5925f4a9a289ef3221416772d625c8b  docs/artifacts/rework-3385-waisen-s3/adversary-test-output.txt
- sha256:1b43ae9bf244fb80d1d3ef7d7be41aeec1c2b2bfc1107ecc2f6dacfcd2d0e5e7  docs/artifacts/rework-3385-waisen-s3/test-green-output.txt
- sha256:6331e67b7f9d689736a631ced411d6ea9102bda9a806caab49dc90e5f3368f1d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:eaeed32281d49dbfcb9c1302551e4e040626cdf144061e72a5ac675edbfb2fa4  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:42fc38e5f0fe6e31a538d6a67057ffe7f21099fec9ddc159f700e9776a9e62dc  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- sha256:b83ada8ab689c753a3ef4aa9519e36a705bdebbff35d3f84f941019da697dd4f  frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts
- sha256:407d96825c9675ef9c823166665943b2d64d2125e1f003e06bc7c11b1ab816a9  frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts
- sha256:e8890ecf0333b48d9a5a1ba0b9b6d9eedf88e9b354015b78cab7026250d12487  frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts
- sha256:47477a81eb4e7b23c6a0a10425fb53d3da676d5691a502e0b5bbce515fc1663e  tests/fixtures/einstellung_gleich_mail/fallliste_editor.json
- sha256:59f535f7d8e6b1dc9051fc8ce0835d5a08d5e9db0fb5ecd4d740f2b8f4974b13  tests/unit/test_i18n_katalog_paritaet.py

## Prüfbasis

- base: 195390981c1d3145f1e6035f0931a0474a8ae4c6
- blob:8525d7381ad946bcc0749f8c3dd4693c89723f57  docs/artifacts/rework-3385-waisen-s3/adversary-test-output.txt
- blob:0396a65820e28afcf8bf6c74fef6bbd4f4817ee5  docs/artifacts/rework-3385-waisen-s3/test-green-output.txt
- blob:170ade69c5da98d0c94589cd0f38fd953f1b1b9b  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:8dd4980e258bc2e07119bb63621657baf489a0e3  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:9829f42f0a9d50c8090709d62f2b22b008ca6403  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- blob:7486de73070c4b920979d6defa02f02e55c02703  frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts
- blob:54559af234448f079d58461fc55eb048d3bc30d5  frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts
- blob:c05c8aad9f93a384cdf1251bc77ec1b3025ced2a  frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts
- blob:6583aaaca5fce209a65f767a113d0aaec4ca292d  tests/fixtures/einstellung_gleich_mail/fallliste_editor.json
- blob:8dd80286811c5cf54cce642541a4d8100c536f94  tests/unit/test_i18n_katalog_paritaet.py

### Runde 4
**Adversary:** Nach dem Merge von origin/main (#3391) geprueft. OutboxCard.svelte und ListTable.svelte existieren; OutboxCard steht im RESTBESTAND (nur ueber das Barrel organisms/index.ts referenziert, tot), ListTable ist lebend (routes/compare/+page.svelte), der Selbsttest behaelt seine Aussage tot vs. lebend. Summenregel: Restbestand zaehlt 2+4+1+6+6 = 19, plus 23 durch Waisen entfernt = 42 = SPEC_ANZAHL, sachlich richtig. Mutationen: RESTBESTAND_ANZAHL 19->20 rot, DURCH_WAISEN_ENTFERNT 23->16 rot (beide im rueckbau_waechter), OutboxCard aus RESTBESTAND gestrichen rot (4 Tests im probe_loeschung); nur das Ausschalten einer Einzelassertion im Selbsttest bleibt gruen (von anderen Assertions und Z.72 aufgefangen, LOW, nicht relevant). Fallliste nach Merge: TRIP gruen auf Karten-Test, ORTE-DE/EN ausnahme mit #3385 und #3390, test_einstellung_gleich_mail_fallliste.py 42 passed; probe_loeschung 30 passed, rueckbau_waechter 34 passed.
**Implementierer:** Merge-Folgeaenderungen gestaged.

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/__tests__/rework_3020_umfang.ts:35
  Evidence: RESTBESTAND_ANZAHL 19 plus DURCH_WAISEN_ENTFERNT 23 (Z.33) ergibt SPEC_ANZAHL 42 (Z.31); Mutation je Konstante rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/__tests__/rework_3020_probe_loeschung.test.ts:72
  Evidence: Selbsttest nutzt OutboxCard (tot) und ListTable (lebend); Mutation am Restbestand rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:1882
  Evidence: TRIP gruen, ORTE-DE (Z.1854) und ORTE-EN (Z.1868) ausnahme mit #3385/#3390 nach dem Merge unveraendert.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: docs/specs/modules/rework_3020_testtabelle.md:1
  Evidence: E017/E018 folgen den umbenannten Testnamen; rueckbau_waechter 34 passed.
  Status: CONFIRMED

VERDICT: VERIFIED
Runde 4 nach Merge: 0 failed in probe_loeschung (30), rueckbau_waechter (34), Fallliste (42).

## Geprüfte Dateien

- sha256:795fc1feaf29b67eac043302783d29c6d5925f4a9a289ef3221416772d625c8b  docs/artifacts/rework-3385-waisen-s3/adversary-test-output.txt
- sha256:44abeeecf6e5f1db905b7295fd5130071641a335caa2baf43c8c74d178acaf42  docs/artifacts/rework-3385-waisen-s3/test-green-output.txt
- sha256:d7d59710cb2a0b4731aa4a51d2b0954333cea2d5f4529c4e1a7592122927b3e6  docs/specs/modules/rework_3020_testtabelle.md
- sha256:6331e67b7f9d689736a631ced411d6ea9102bda9a806caab49dc90e5f3368f1d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:8443cc52c872b2f9c09d6e7e22841af5e1b0851e264d5a490923df0c22837e84  frontend/src/lib/__tests__/rework_3020_probe_loeschung.test.ts
- sha256:8d92bb62e5804ded4448ea29e51b081b079a1a78d4421df6a823a6b63d8ae99c  frontend/src/lib/__tests__/rework_3020_umfang.ts
- sha256:eaeed32281d49dbfcb9c1302551e4e040626cdf144061e72a5ac675edbfb2fa4  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:42fc38e5f0fe6e31a538d6a67057ffe7f21099fec9ddc159f700e9776a9e62dc  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- sha256:b83ada8ab689c753a3ef4aa9519e36a705bdebbff35d3f84f941019da697dd4f  frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts
- sha256:407d96825c9675ef9c823166665943b2d64d2125e1f003e06bc7c11b1ab816a9  frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts
- sha256:e8890ecf0333b48d9a5a1ba0b9b6d9eedf88e9b354015b78cab7026250d12487  frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts
- sha256:667f17b883603619e311a25be47ee9e6e4bf9e4b4936137d7c7cf3ed74cafd96  tests/fixtures/einstellung_gleich_mail/fallliste_editor.json
- sha256:59f535f7d8e6b1dc9051fc8ce0835d5a08d5e9db0fb5ecd4d740f2b8f4974b13  tests/unit/test_i18n_katalog_paritaet.py

## Prüfbasis

- base: 94c5d892e870575bafbf4b5248b0211993099344
- blob:8525d7381ad946bcc0749f8c3dd4693c89723f57  docs/artifacts/rework-3385-waisen-s3/adversary-test-output.txt
- blob:a3405e489c0fd74dcb08a568d1d749f2c4dba517  docs/artifacts/rework-3385-waisen-s3/test-green-output.txt
- blob:a6aa4939836b8ea8df9194915175c32e3bc83292  docs/specs/modules/rework_3020_testtabelle.md
- blob:170ade69c5da98d0c94589cd0f38fd953f1b1b9b  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:ce5dd355556c4353fb7eedcaed1df38712ad64d5  frontend/src/lib/__tests__/rework_3020_probe_loeschung.test.ts
- blob:a61d1afd9493f3c82565cb2d08b03d7ccb7bbb19  frontend/src/lib/__tests__/rework_3020_umfang.ts
- blob:8dd4980e258bc2e07119bb63621657baf489a0e3  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:9829f42f0a9d50c8090709d62f2b22b008ca6403  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- blob:7486de73070c4b920979d6defa02f02e55c02703  frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts
- blob:54559af234448f079d58461fc55eb048d3bc30d5  frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts
- blob:c05c8aad9f93a384cdf1251bc77ec1b3025ced2a  frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts
- blob:b093414ee64ede9421611f51037379a227b44b47  tests/fixtures/einstellung_gleich_mail/fallliste_editor.json
- blob:8dd80286811c5cf54cce642541a4d8100c536f94  tests/unit/test_i18n_katalog_paritaet.py
