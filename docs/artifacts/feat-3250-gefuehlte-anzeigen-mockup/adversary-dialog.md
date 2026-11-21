# Adversary Dialog — feat-3250-gefuehlte-anzeigen-mockup
Spec: docs/specs/modules/feat_3250_gefuehlte_anzeigen_mockup.md
Datum: 2026-11-21 17:56

## Checkliste
- [x] **Input:** Mockup Fassung 4, Staging-Seite Reiter Wetter (Trip), Prüfkonto-Seed.
- [x] **Output:** Abgleich meldet die drei gefühlten Metriken (DE und EN) samt Untertitel, Zeilenmitte und Zähler ohne Abweichung; keine herrenlosen Einträge dieser Metriken.
- [x] **Side effects:** Wechsel `zusaetzlich`→`gefunden` in verwandten Einträgen (Kürzel-Legende, Beispiel) ist erlaubt; eine neue Abweichung ohne Besitzer ist es nicht. Produktverhalten unverändert.
- [x] **AC-1:** Given der Trip-Reiter Wetter in Deutsch / When der Nutzer die Gruppe Temperatur liest / Then stehen dort nach „Gefühlte Temperatur“ die Zeilen „Gefühlte Tiefsttemperatur Nacht“, „Gefühlte Tages-Tiefsttemperatur (Gehzeit)“ und „Gefühlte Tages-Höchsttemperatur (Gehzeit)“, und das Mockup Fassung 4 zeigt dieselbe Reihenfolge.
- [x] **AC-2:** Given der Trip-Reiter Wetter in Englisch / When der Nutzer die Gruppe Temperatur liest / Then erscheinen „Feels-like night low“, „Feels-like daytime low (walking hours)“ und „Feels-like daytime high (walking hours)“ und stimmen mit dem Mockup überein.
- [x] **AC-3:** Given eine der drei gefühlten Metriken im Trip-Reiter Wetter / When der Nutzer die Zeile betrachtet / Then zeigt sie den Untertitel „°C · nur Anzeige, keine Ampel“ und in der Mitte „keine Ampel, nur Anzeige“, ohne Ampel-Grenzen und ohne Alarm-Auswahl, wie Windrichtung und die Gehzeit-Zeilen.
- [x] **AC-4:** Given der Trip mit aktiver „Gefühlte Temperatur“ / When der Nutzer den Zähler über der Metrikliste liest / Then lautet er „9 von 18 Metriken lösen einen Alarm aus. 8 können keinen auslösen“ im Mockup und auf Staging gleich.
- [x] **AC-5:** Given der Orts-Vergleich / When der Nutzer dort die Metrikliste öffnet / Then erscheinen die drei gefühlten Anzeige-Metriken weiterhin nicht (ADR-0011), und das Mockup der Orte bleibt unverändert.
- [x] **AC-6:** Given der Staging-Abgleich des Reiters Wetter in Deutsch und Englisch / When er nach der Änderung läuft / Then enthalten die Berichte keine `zusaetzlich`-Einträge mehr für die drei gefühlten Metriken, keine neue Abweichung ohne Besitzer, und der Zählwächter der Besitzerliste bleibt grün.
- [x] **AC-7:** Given Bestandstrips mit aktiver gefühlter Temperatur / When der Nutzer seinen Trip öffnet / Then bleiben Auswahl, SMS-Kürzel FN/FL/FD und Briefing unverändert, denn nur Mockup und Prüflisten ändern sich.
- [x] **AC-8:** Given der Trip-Reiter Wetter als Mockup und als Staging-Seite / When der Product Owner das Soll/Ist-Bild der Gruppe Temperatur ansieht / Then stimmen beide in den drei neuen Zeilen und im Zähler sichtbar überein.

## Dialog

### Runde 1
**Adversary:** Behauptung: drei gefühlte Zeilen aktiv, Nur-Anzeige, Reihenfolge/Namen wie live, Zähler 9 von 18 / 8, Orte unverändert, herrenlose Einträge weg. Live-Abgleich Staging (Prüfkonto, Scope wetter) selbst gelaufen, Ablage scratchpad/adv3250/de und en. DE: gefunden 1473 (vorher 1437), abweichend 483 (453), zusaetzlich 142 (145). EN: gefunden 1427 (1391), abweichend 427 (397), zusaetzlich 168 (171). Diff der zusaetzlich-Listen DE und EN: genau 3 verschwunden (DE: Gefühlte Tiefsttemperatur Nacht, Gefühlte Tages-Tiefsttemperatur (Gehzeit), Gefühlte Tages-Höchsttemperatur (Gehzeit); EN: Feels-like night low, Feels-like daytime low (walking hours), Feels-like daytime high (walking hours)), 0 neu. Die 14 Metriken-Einträge (Name, Untertitel, Zeilenmitte, Erklärsatz, kein Alarm, Entfernen, Zähler, je Zustand normal/luecken) sind gefunden. Orte: keine neue Abweichung, ORTE_METRICS (docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:338) unverändert. Frage (c): bleiben FN/FL/FD und FN12/FD12/16 herrenlos?
**Implementierer:** Ja, unverändert wie im Vorher-Bericht: Live-Einträge FN, N gefühlt, FL, L gefühlt, FD, D gefühlt, FN12, FD12/16 und die SMS-Beispielzeile bleiben zusaetzlich ohne Besitzer (nicht neu). Das Mockup hat keine Kürzel-Legende (Kürzel erklärt, RA, Beispielwarnung stehen ebenso herrenlos), die SMS-Beispielwerte hängen am Prüf-Datensatz (Mockup TF- FN7 FD7/12, docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:561). Eine Mockup-Ergänzung müsste eine ganze Legende erfinden, außerhalb des Spec-Scopes. Siehe F001.

### Runde 2
**Adversary:** Mutationen (String-Ersetzung, Sicherung scratchpad/adv3250/mockup.bak und liste.bak, Elementliste per Generator neu, danach zurückkopiert; sha256 vorher gleich nachher, sha_vorher.txt und sha_nachher.txt). (1) wind_chill_night auf on=false: 7 rot (AC-1/2, AC-3, AC-4, Hash). (2) Reihenfolge day_low/day_high getauscht: 3 rot (Reihenfolge-Test, Hash). (3) wind_chill_night in ORTE_METRICS ergänzt: AC-5 rot plus Hash. Alle drei vom neuen Test frontend/e2e/feat3250_elementliste_gefuehlte_anzeigen.test.ts gefangen, nicht nur vom Hash. Tests: node --test frontend/e2e/feat3250_elementliste_gefuehlte_anzeigen.test.ts und frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts: 15 pass, 0 fail; tests/test_2913_c2_besitzerliste.py: 35 Punkte grün (Zählwächter unverändert). Frage: Regression am Produktcode?
**Implementierer:** Änderungsliste: nur Mockup, Elementliste und Prüfsummen-Test geändert; kein Diff an src/app/metric_catalog.py oder Frontend-Produktcode (AC-7). Prüfsumme mit #3250-Kommentar begründet.

## Findings

Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:561
  Description: SMS-Beispiel TF- FN7 FD7/12 steht im Mockup; Live-Legende (FN/FL/FD, N/L/D gefühlt, Kürzel erklärt, RA) und SMS-Beispiel FN12/FD12/16 sind auf Staging zusaetzlich ohne Besitzer; identisch zum Vorher-Bericht.
  Spec requirement: AC-6 — keine NEUE Abweichung ohne Besitzer
  Conflict: bestehender, nicht neuer Rest; Mockup hat keine Kürzel-Legende, daher nicht ohne Erfindung zu beheben
  Remediation: nicht hier beheben; per Besitzerliste einem Folge-Issue zuordnen

## Confirmations

Confirmation:
  AC: Input
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:322
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: Output
  Code reference: docs/context/einstellungen_neu/elementliste.json:1
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: Side effects
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:561
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: AC-1
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:322
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: docs/context/einstellungen_neu/elementliste.json:1
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:322
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/e2e/feat3250_elementliste_gefuehlte_anzeigen.test.ts:1
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:338
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:76
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:76
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:322
  Evidence: Abgleich DE/EN Staging und Tests belegen den Punkt (Bericht scratchpad/adv3250)
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Tests: 15 node + 35 pytest bestanden, 0 fehlgeschlagen, 0 übersprungen. Mutationen 3/3 gefangen. Checklist 11/11. F001 (MEDIUM) Folge-Issue, nicht blockierend.

## Geprüfte Dateien

- sha256:626c081f63bc8671ec1c95e451486f574620bebd3c1231c2ae603d3cc611a771  docs/context/einstellungen_neu/elementliste.json
- sha256:c2347e0876a30710b2d56f6c1561b13668cb48089802558eaeaec0de30d8e6be  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:61cbab90611b81e1362df339771c51c650e10d9d020b0a22a95be141e5d6f239  frontend/e2e/feat3250_elementliste_gefuehlte_anzeigen.test.ts
- sha256:309309b5514dc37894e33d848dcfc368423366ba9ba6ae6bfea3e2689b97040a  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts

## Prüfbasis

- base: 76e22ab83913151e9334ab6eb1f17b67ed363714
- blob:ab1e1b42a39a2764542807b75a62ca64bd7b77f4  docs/context/einstellungen_neu/elementliste.json
- blob:20effdfe5552943b14cfe204592ca37a5980aeb0  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:671b8b9579887c3b6257ebc6ea80ec7473bb000c  frontend/e2e/feat3250_elementliste_gefuehlte_anzeigen.test.ts
- blob:98973c0451da67e7f6f6e742c3a31176ec554833  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
