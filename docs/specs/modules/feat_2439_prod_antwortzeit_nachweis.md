---
entity_id: feat_2439_prod_antwortzeit_nachweis
type: module
created: 2026-10-25
updated: 2026-10-25
status: draft
version: "1.0"
workflow: fix-2439-prod-antwortzeit-nachweis
tags: [tooling, prod, befehle, antwortzeit, messung, korsika, fr_direct, 2439, epic-2506]
---

# Prod-Nachweis der Befehls-Antwortzeit (Korsika, Premium-SMS, Telegram) (#2439)

## Approval

- [ ] Approved

## Purpose

Der Live-Nachweis der Befehls-Antwortzeit (Epic #2506, Rest von #2439) ist auf Staging etwa zu zwei Dritteln erbracht (Messlauf 24.10., Treiber v1.1, PR #2600: 13 PASS / 4 FAIL / 4 SKIP). Offen ist, was Staging strukturell nicht messen kann: Korsika mit `fr_direct` (Haupt-Spec AC-5), echte Premium-SMS und Telegram-Wetterbefehle (AC-4). Diese Delta-Spec (1) beseitigt den Widerspruch zwischen Test und Haupt-Spec AC-5, (2) macht das Prod-Lese-Werkzeug fähig, die Zielgröße (jeder kalte Lauf unter 60 s, Median unter 45 s) selbst zu prüfen und „nicht belegt“ ehrlich von „bestanden“ zu trennen, und (3) legt das Protokoll fest, mit dem der Nachweis auf Produktion erbracht wird. Die 60-Sekunden-Grenze wird nicht gelockert, die Sperre `egress_guard` für Météo-France auf Staging bleibt bestehen (bräuchte ein ADR).

## Source

- **Files:**
  - `tests/e2e/test_push_eingang_befehle_staging.py` (ändern: `test_ac5_wetterbefehle_kalt_auf_korsika_route_jeder_lauf_unter_60s`)
  - `.claude/tools/befehl_antwortzeit.py` (ändern: Kaltheit/Quelle je Lauf, `--trip`, Zielgrößen-Prüfung `--ziel`)
  - `tests/test_befehl_antwortzeit_zielpruefung.py` (neu, deterministischer Kern-Test)
  - `tests/fixtures/befehl_antwortzeit/prod_korsika_kalt_laeufe.log` (neu, aufgezeichnete Journalzeilen im Format `journalctl -o short-iso-precise`)
- **Identifier:** `test_ac5_wetterbefehle_kalt_auf_korsika_route_jeder_lauf_unter_60s`; neue Funktionen `kaltheit_je_lauf(...)` und `pruefe_ziel(...)` in `befehl_antwortzeit.py`, `main()` um `--trip`/`--ziel` erweitert.
- **Wiederverwendet (unverändert):** `befehl_messlogik.kalt_laeufe(laeufe, fenster_zeilen, quellen=…)`, `dauerzeilen`, `lese_journal`.

> Schicht-Hinweis: Reine Test- und Werkzeug-Schicht (`tests/`, `.claude/`, Doku). `src/`, `api/`, `internal/`, `frontend/`, `cmd/` bleiben unverändert. **Tooling-/Test-Ausnahme:** kein Produktcode, daher entfällt der Prod-Deploy für Scheibe A (CLAUDE.md, Ausnahme reine Doku-/Tooling-Änderungen); Scheibe B ist Betriebsarbeit auf Produktion ohne Codeänderung.

> Querschnitts-Prüfpunkte: **Trip/Ortsvergleich-Teilung** nicht berührt (Befehle laufen am Trip; kein Editor-Baustein). **Mandantentrennung:** das Werkzeug liest nur das Journal und filtert optional auf eine Trip-ID; der Prod-Test-Trip gehört einem Test-Nutzer-Konto (nicht dem Konto des PO), Empfänger sind ausschließlich Test-Empfänger. **Kanäle:** alle vier Kanäle sind gleichrangig; der Nachweis deckt E-Mail, Premium-SMS und Telegram auf Produktion ab, der vierte Kanal (SMS-Befehlseingang) läuft technisch über denselben seven.io-Rückkanal wie die Premium-SMS (`_KANAL_GRUPPEN` im Test).

## Estimated Scope

- **LoC:** ca. +120 / −20 (Werkzeug ca. +70, Kern-Test ca. +50 Code plus Fixture, AC-5-Test ca. +15/−20)
- **Files:** 3 Code-/Testdateien plus 1 Fixture (Spec zählt nicht)
- **Effort:** low (Scheibe A); Scheibe B ist Betriebsarbeit
- **Risk:** NIEDRIG für Scheibe A (Test und Lese-Werkzeug, kein Produktpfad). Bei Scheibe B liegt das Risiko im Versand an echte Empfänger; es wird durch Test-Trip, Test-Empfänger und das Verbot des Sammel-Versands über alle Trips begrenzt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/tools/befehl_messlogik.py` (`kalt_laeufe`, `dauerzeilen`, `lese_journal`) | Upstream (unverändert) | Kaltheit über Fensterzeilen `fr_direct_fenster`/`dwd_fenster` mit `downloads>0` im Befehlsfenster |
| `src/providers/meteofrance.py` (Zeile `fr_direct_fenster … downloads=N`), `src/providers/dwd.py` (Zeile `dwd_fenster …`) | Upstream (nur gelesen) | Quelle der Kaltheits-Ableitung; kein neues Quellenfeld in der Dauerzeile |
| `src/app/egress_guard.py` | Upstream (nur gelesen) | Sperrt Météo-France auf Staging; Grund, warum `fr_direct` dort nie kalt läuft |
| `docs/specs/modules/feat_2439_befehle_antwortzeit.md` AC-4/AC-5 | Eltern-Spec | Zielgrößen und Mindestläufe; diese Spec ist Delta und ändert sie nicht |
| `docs/specs/modules/feat_2439_staging_messtreiber.md` | Eltern-Spec | Treiber und Env-Vertrag des Staging-Tests |
| seven.io-Journal, Prod-Journal `gregor-python` | Daten | Nur lesend |

## Implementation Details

```
Scheibe A1 -- AC-5-Test auf Staging an die Haupt-Spec angleichen
  Der Test liest wie bisher Dauerzeilen (Trip = GZ_STAGING_TRIP_KORSIKA) und das
  Staging-Journal. Neu:
   - Antwort vorhanden: mindestens eine Dauerzeile des Korsika-Trips je Befehl
     (HEUTE, MORGEN) im Messlauf-Zeitraum. Die Dauerzeile wird nur geschrieben, wenn
     die Antwort an den Versand-Provider uebergeben wurde (Haupt-Spec AC-1); sie ist
     der Nachweis "Antwort vorhanden". Keine neue Produktzeile.
   - Quelle ehrlich: kalt_laeufe(..., quellen=("fr_direct_fenster",)) ist LEER
     (Staging holt nichts ueber fr_direct), und der Test gibt die Zeile aus:
     "AC-5 <befehl> Korsika: Quelle eu_direct (Ersatz, egress_guard sperrt Meteo-France)".
     Die Ersatzquelle eu_direct steht in keiner Journalzeile; sie folgt aus der
     Konstellation "Dauerzeile vorhanden, fr_direct_fenster nie kalt". Wuerde doch ein
     fr_direct-Download im Fenster stehen, meldet der Test das als Befund
     (Sperre wirkungslos) und nicht als Bestehen.
   - fr_direct-Kaltlauf-Teil: pytest.skip("NOT_MEASURABLE_ON_STAGING: public-api.meteofrance.fr
     ist auf Staging durch egress_guard gesperrt -- Prod-Messweg:
     .claude/tools/befehl_antwortzeit.py --trip <id> --ziel"), nach den Pruefungen
     davor, nie als bestanden. Vorbild: _nicht_messbar_premium_sms (Z. 183) und die
     Ausgabezeile in test_ac4 (Z. 253).
   - Die Konstanten GRENZE_MIT_WETTER_MS (60 s) und MIN_LAEUFE_KORSIKA (3) bleiben
     unveraendert und werden im Werkzeug (A2) wiederverwendet bzw. gleichlautend gefuehrt.

Scheibe A2 -- befehl_antwortzeit.py (weiterhin nur lesend)
  _prod_journal liefert zusaetzlich die rohen Journalzeilen (ml.lese_journal), damit
  die Fensterzeilen verfuegbar sind.
  kaltheit_je_lauf(dauerzeilen, journal) -> je Lauf {..., "quelle": "fr_direct" | "dwd" | "warm"}:
    "fr_direct" wenn kalt_laeufe(quellen=("fr_direct_fenster",)) den Lauf enthaelt,
    sonst "dwd" wenn kalt_laeufe(quellen=("dwd_fenster",)) ihn enthaelt, sonst "warm".
    Ableitung statt neuem Quellenfeld in der Dauerzeile (kein Produktcode).
  Ausgabe je Lauf: Zeit, Befehl, Kanal, Trip, Dauer, Quelle/Kaltheit.
  --trip <id>: filtert Dauerzeilen auf diese Trip-ID (Mandanten-/Test-Trip-Eingrenzung).
  --ziel: Zielgroessen-Pruefung nur fuer HEUTE und MORGEN und nur fuer KALTE Laeufe,
    getrennt je (Befehl, Quelle):
      verfehlt     : irgendein kalter Lauf >= 60 000 ms ODER (ab Mindestzahl kalter Laeufe)
                     Median >= 45 000 ms -- unter der Mindestzahl sagt ein Median nichts aus,
                     dort gilt "nicht belegt" (Test-Vertrag Fixture kors-duenn)
      nicht belegt : weniger als die Mindestzahl kalter Laeufe
                     (fr_direct/Korsika: 3 -- Haupt-Spec AC-5; dwd/DE: 5 -- Haupt-Spec AC-4)
      bestanden    : sonst
    Warme Laeufe und Laeufe anderer Befehle zaehlen nicht mit. Die Grenze ist strikt
    (59 999 ms besteht, 60 000 ms verfehlt). Ausgegeben werden alle Einzelwerte und
    die Kanalverteilung der kalten Laeufe.
    Exit-Code: 0 nur wenn jede geprueften Gruppe "bestanden" ist; 1 bei "verfehlt";
    2 bei "nicht belegt" (sofern keine Gruppe verfehlt). Ohne --ziel bleibt der
    Exit-Code 0 wie bisher.
  Die Median-Grenze 45 s gilt hier einheitlich fuer alle kalten Gruppen (Haupt-Spec AC-4);
  fuer Korsika ist sie eine zusaetzliche, strengere Pruefung ueber AC-5 hinaus und wird
  als solche ausgewiesen.

Scheibe A3 -- Kern-Test tests/test_befehl_antwortzeit_zielpruefung.py
  Echte aufgezeichnete Journalzeilen als Fixture (Dauerzeilen + Fensterzeilen im Format
  von journalctl -o short-iso-precise), kein Mock/patch. Ruft kaltheit_je_lauf und
  pruefe_ziel direkt auf.

Scheibe B -- Prod-Nachweis (kein Code), Protokoll
  1. Test-Trip "Korsika" auf Produktion anlegen, Besitzer: Test-Nutzer-Konto (nicht das
     Konto des PO), Route auf Korsika (fr_direct). Die Trip-Konfiguration des PO wird
     weder gelesen noch geaendert. Empfaenger = ausschliesslich Test-Empfaenger.
  2. Kaltheit ohne Prod-Neustart: Datum, das auf Produktion nie abgerufen wurde (z. B.
     Trip-Startdatum frisch, jeder Lauf mit einem neuen, noch nie angefragten Datum bzw.
     jeweils neuer Trip-Anlage). gregor-python wird NICHT neu gestartet; es gibt KEINEN
     Sammel-Versand ueber alle Trips.
  3. Ausloesen ueber den ECHTEN Eingang, mindestens 3 kalte Laeufe je Befehl (HEUTE,
     MORGEN) und je Kanal:
       - E-Mail (Pflicht): Test-Absender mit Nutzerbindung an die Prod-Befehlsadresse.
       - Premium-SMS: die zweite seven.io-Nummer sendet den Befehl an die Prod-Nummer;
         der Agent prueft den Empfang selbst (Journal inbound/outbound).
       - Telegram: Prod-Testchat, falls gebunden. Ist keiner gebunden, wird das als Befund
         im Ticket benannt (siehe Offene Punkte), nicht verschwiegen und nicht als
         bestanden gebucht.
  4. Messung: `uv run python3 .claude/tools/befehl_antwortzeit.py --since <Datum>
     --trip <test-trip-id> --ziel` je Kanal; Einzelwerte, Quelle (fr_direct) und
     Exit-Code ins Issue #2439 kopieren (Beleg-Protokoll).
  5. Verfehlt fr_direct die 60 s: Befund im selben Ticket (Abrufpfad fr_direct
     beschleunigen), keine Ausnahme, kein Schliessen.
  6. Aufraeumen: Test-Trip und Test-Konto entfernen; Pruefung, dass kein Test-Trip im
     Bestand bleibt. Zusaetzlich AC-15 (Haupt-Spec) mit einem echten Prod-Befehl
     (received_total steigt, Sofort-Antwort) belegen, soweit noch nicht erbracht.
```

## Expected Behavior

- **Input:** (A) Staging-Journal des Messlaufs bzw. Prod-Journal `gregor-python` und seven.io-Journal; Aufruf `--since`, optional `--kanal`, `--trip <id>`, `--ziel`. (B) Echte Prod-Befehle an den Test-Trip.
- **Output:** (A) Staging-Test: grün für „Antwort vorhanden, `fr_direct` nicht kalt (Ersatzquelle)“, `skip` mit `NOT_MEASURABLE_ON_STAGING` für den `fr_direct`-Kaltlauf. Werkzeug: Lauflisten mit Quelle/Kaltheit und je Gruppe `bestanden`/`verfehlt`/`nicht belegt` mit Exit-Code 0/1/2. (B) Einzelwerte je Lauf und Kanal im Issue.
- **Side effects:** (A) keine; das Werkzeug liest nur. (B) Echte E-Mail, Premium-SMS und ggf. Telegram an Test-Empfänger; kurzzeitig ein zusätzlicher Test-Trip auf Produktion; seven.io-Kontingent für wenige SMS.

## Acceptance Criteria

- **AC-1:** Given der Staging-Messlauf hat HEUTE und MORGEN für den Korsika-Trip ausgelöst und `fr_direct` ist durch `egress_guard` gesperrt, When `test_ac5_wetterbefehle_kalt_auf_korsika_route_jeder_lauf_unter_60s` läuft, Then prüft der Test je Befehl, dass mindestens eine Dauerzeile des Korsika-Trips (Antwort übergeben) vorhanden ist und im Befehlsfenster kein `fr_direct_fenster` mit `downloads>0` steht (Ersatzquelle `eu_direct` ehrlich ausgewiesen), und meldet den `fr_direct`-Kaltlauf per `pytest.skip("NOT_MEASURABLE_ON_STAGING …")` mit Verweis auf `.claude/tools/befehl_antwortzeit.py` — niemals als bestanden.
  - Test: Staging-Live-Test gegen den Messlauf-Journalauszug. Gegenprobe: Ohne Korsika-Dauerzeile wird der Test rot (Befund „keine Antwort“, kein Skip); steht ein `fr_direct_fenster`-Download im Befehlsfenster, meldet der Test einen Befund statt zu bestehen.

- **AC-2:** Given der AC-5-Test wurde auf Staging angeglichen, When Konstanten und Grenzprüfungen des Tests gelesen und ausgeführt werden, Then gilt für jede Prod-Auswertung weiterhin die unveränderte Grenze von 60 s je Einzellauf und mindestens 3 kalte Läufe je Befehl; der Skip-Pfad kann die Grenze nicht umgehen, weil er den Messwert nicht ersetzt, sondern auf den Prod-Messweg verweist.
  - Test: Mutationsprobe auf `GRENZE_MIT_WETTER_MS` (z. B. 60 000 → 90 000) lässt `tests/test_befehl_antwortzeit_zielpruefung.py` rot werden (Kern-Test bindet das Werkzeug an dieselbe Grenze). Der Skip-Text enthält `NOT_MEASURABLE_ON_STAGING` und den Werkzeug-Pfad (Ausgabe des Testlaufs mit `-rs`).

- **AC-3:** Given Prod-Dauerzeilen und Fensterzeilen (`fr_direct_fenster`, `dwd_fenster`) im Journal, When das Werkzeug die Läufe ausgibt, Then trägt jeder Lauf die Angabe `fr_direct`, `dwd` oder `warm`, abgeleitet über `befehl_messlogik.kalt_laeufe` aus den Fensterzeilen im Befehlsfenster, ohne neues Quellenfeld in der Dauerzeile und ohne Produktcode.
  - Test: Kern-Test mit aufgezeichneter Fixture: ein Lauf mit `fr_direct_fenster downloads=3` im Fenster → `fr_direct`; ein Lauf mit nur `dwd_fenster downloads=2` → `dwd` (ein `dwd_fenster` zählt nie als `fr_direct`); ein Lauf mit `downloads=0` bzw. ohne Fensterzeile → `warm`; eine Fensterzeile außerhalb des Befehlsfensters macht den Lauf nicht kalt.

- **AC-4:** Given Dauerzeilen mehrerer Trips, Befehle und Kanäle, When das Werkzeug mit `--trip <id>` aufgerufen wird, Then erscheinen und zählen ausschließlich Läufe dieser Trip-ID; Läufe anderer Trips, auch mit identischem Befehl und Zeitfenster, fließen weder in die Ausgabe noch in die Zielgrößen-Prüfung ein.
  - Test: Kern-Test mit zwei Trips (Test-Trip und Fremd-Trip) in derselben Fixture: Mit `--trip` des Test-Trips hat die Prüfung nur dessen Läufe; ein Fremd-Trip mit 70-s-Lauf macht die Prüfung des Test-Trips nicht rot. Mutationsprobe: Filter entfernen → Test rot.

- **AC-5:** Given kalte HEUTE-/MORGEN-Läufe mit Quelle `fr_direct`, When die Zielgrößen-Prüfung (`--ziel`) läuft, Then lautet das Ergebnis je Befehl `bestanden`, wenn mindestens 3 kalte Läufe vorliegen, jeder Lauf unter 60 000 ms liegt und der Median unter 45 000 ms; `verfehlt`, sobald ein kalter Lauf 60 000 ms oder mehr hat oder (ab 3 kalten Läufen) der Median 45 000 ms oder mehr; `nicht belegt`, wenn weniger als 3 kalte Läufe vorliegen und kein Einzellauf die 60 s erreicht — warme Läufe zählen nicht mit.
  - Test: Kern-Test mit Fixture-Grenzfällen: 59 999 ms bestanden / 60 000 ms verfehlt; drei Läufe mit Median genau 45 000 ms → verfehlt, mit 44 999 ms → bestanden; nur 2 kalte Läufe → `nicht belegt` (nicht bestanden); 3 kalte + 5 warme Läufe zählen als 3; ein warmer 90-s-Lauf macht die Prüfung nicht rot. Mutationen (Grenze `<` → `<=`, Mindestzahl 3 → 2, warme Läufe mitzählen) lassen jeweils mindestens einen Test rot werden.

- **AC-6:** Given eine Prod-Auswertung mit `--ziel`, When das Werkzeug endet, Then ist der Exit-Code 0 nur, wenn jede geprüfte Gruppe `bestanden` ist; bei mindestens einer Gruppe `verfehlt` ist der Exit-Code 1, bei keiner `verfehlt` aber mindestens einer `nicht belegt` ist er 2; ohne `--ziel` bleibt der Exit-Code 0 wie bisher, und das Werkzeug löst weiterhin keinen Befehl aus und schreibt nichts.
  - Test: Kern-Test ruft `main()` bzw. die Exit-Code-Funktion mit Fixture-Journalen für alle vier Ausgänge auf (bestanden → 0, verfehlt → 1, nicht belegt → 2, ohne `--ziel` → 0). Ein Testfall bestätigt, dass kein Versandpfad importiert oder aufgerufen wird (kein Netz im Kern-Test, `--disable-socket`).

- **AC-7:** Given der Prod-Test-Trip „Korsika“ ist angelegt (Test-Konto, Test-Empfänger, nie abgerufene Daten, kein Neustart von `gregor-python`, kein Sammel-Versand), When HEUTE und MORGEN je mindestens 3-mal kalt über E-Mail (Pflicht), Premium-SMS (zweite seven.io-Nummer an die Prod-Nummer) und Telegram (Prod-Testchat, falls gebunden) gesendet werden, Then belegt `befehl_antwortzeit.py --trip <id> --ziel` für `fr_direct` Exit-Code 0 mit allen Einzelwerten je Lauf und Kanal im Issue #2439; ist Telegram nicht gebunden, steht das ausdrücklich als Befund im Issue (nicht als bestanden); verfehlt `fr_direct` die 60 s, steht ein Befund im selben Ticket (Abrufpfad `fr_direct` beschleunigen) und #2439 bleibt offen.
  - Test: Beleg-Protokoll im Issue #2439: Werkzeug-Ausgabe (Läufe mit Quelle `fr_direct`, Einzelwerte, Exit-Code) je Kanal, seven.io-Journal-Auszug für Premium-SMS, Prod-Push-Status vor/nach (AC-15 der Haupt-Spec); Rufnummern, Token und Nachrichtentext erscheinen nicht.

- **AC-8:** Given der Prod-Nachweis ist erbracht oder als Befund dokumentiert, When die Messung abgeschlossen ist, Then sind Test-Trip und Test-Konto auf Produktion entfernt, in den Trips der Produktion verbleibt kein Test-Trip, und die Trip-Konfiguration des PO ist unverändert (Vergleich der Trip-Liste vor und nach der Messung).
  - Test: Trip-Liste des Prod-Nutzers vor Anlage und nach Aufräumen identisch (Anzahl und IDs); Abfrage des Test-Kontos liefert nach dem Löschen keinen Trip mehr; der Nachweis steht im Issue-Beleg.

## Offene Punkte

- **(a) Zwei weitere FAIL vom 24.10.:** Der AC-5-Test erklärt 2 der 4 FAIL (HEUTE/MORGEN parametrisiert). Welche 2 weiteren Messtests rot waren, ist im Ticket nicht benannt und wird nicht geraten. Klärung in `/40` per Testlauf gegen das Treiber-Ergebnis (Staging-Messlauf mit exportiertem `GZ_STAGING_MESSLAUF_SEIT`). Ist die Ursache ein Produktdefekt, wird sie als eigenes Finding geführt (nutzersichtbar → eigenes Issue; sonst Sammel-Issue #1199 bzw. #1196), nicht stillschweigend in diese Spec aufgenommen.
- **(b) Prod-Telegram-Testchat:** Es ist offen, ob auf Produktion ein gebundener Telegram-Testchat existiert (das Staging-Konto ist verwaist). Ohne ihn wird Telegram nicht gemessen; das ist als Befund im Ticket zu benennen (alle vier Kanäle sind gleichrangig, also keine stille Auslassung). Die Anlage eines Prod-Testchats wäre Betriebsarbeit des Agenten, kein Auftrag an den PO.
- **(c) Quelle `eu_direct` nicht im Journal:** Keine Journalzeile weist `eu_direct` namentlich aus. Der Staging-Test leitet „Ersatzquelle“ aus der Konstellation Antwort vorhanden / kein `fr_direct`-Download ab. Eine direkte Ausweisung bräuchte Produktcode (Quellenfeld in der Dauerzeile) und ist hier bewusst nicht Teil des Scopes.

## Known Limitations

- Kaltheit wird aus Fensterzeilen im Befehlsfenster abgeleitet. Läuft ein anderer Bericht (Alarm, Scheduler) gleichzeitig im selben Prozess und erzeugt `downloads>0` im selben Fenster, kann ein warmer Lauf als kalt gelten. Die Prod-Messung begrenzt das, indem im Messfenster nur der Test-Trip läuft.
- Die Zielgrößen-Prüfung bewertet nur das Journal; sie beweist nicht, dass ein Lauf über den gewünschten Eingang kam (Kanalverteilung wird ausgegeben und im Beleg gegengelesen).
- Scheibe B hängt von externen Diensten ab (Météo-France, seven.io); ein Messfehler durch Dienstausfall wird wiederholt, erst ein reproduzierbares Verfehlen gilt als Befund.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test- und Messwerkzeug-Änderung ohne Eingriff in Entscheidungsflächen (Kanäle, Provider, Datenmodell, Auth, Deploy-Strategie). Die Sperre `egress_guard` auf Staging bleibt unverändert; deren Lockerung bräuchte ein ADR und ist hier ausgeschlossen.

## Changelog

- 2026-10-26: AC-5 und A2 klargestellt: Median-Grenze (45 s) gilt erst ab der Mindestzahl kalter Läufe; darunter „nicht belegt“, sofern kein Einzellauf 60 s erreicht (Adversary-Finding F005, Test-Vertrag Fixture kors-duenn).
- 2026-10-25: Initial spec created (Delta zu `feat_2439_befehle_antwortzeit` AC-5: Staging-Test angleichen, Prod-Werkzeug um Kaltheit/Quelle/`--trip`/Zielgrößen-Prüfung erweitern, Prod-Nachweis-Protokoll)
