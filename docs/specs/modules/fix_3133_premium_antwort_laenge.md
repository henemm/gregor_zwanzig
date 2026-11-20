---
entity_id: fix_3133_premium_antwort_laenge
type: bugfix
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.1"
workflow: fix-3133-premium-antwort-laenge
tags: [premium-sms, befehle, kanal-paritaet, i18n, issue-3133]
---

# Premium-SMS-Befehlsantworten seitenweise, je Nachricht höchstens 153 Zeichen (#3133)

## Approval

- [ ] Approved

## Purpose

Befehlsantworten an die Premium-SMS (Garmin inReach, Grenze 153 Zeichen) gehen heute ungekürzt raus (HILFE Trip 456, HILFE Vergleich 158, CODES 761, unbekannter Befehl 185 Zeichen). PO-Entscheidung vom 2026-11-20: jede Premium-Antwort ist genau eine Nachricht von höchstens 153 Zeichen; lange Texte (HILFE, KÜRZEL/CODES) werden seitenweise abgefragt, am Ende steht ein Verweis wie „mehr: HILFE 2". Alles Übrige wird zentral gefaltet und mit Kennzeichen gekürzt.

Verworfen (PO): automatische 1/n-Aufteilung (Kontingent 15 Antworten/Tag, ADR-0116) und Kurzfassung plus Rest per Mail (verletzt Kanal-Parität, ADR-0095).

## Source

- **File:** `src/services/premium_sms_pages.py` (neu), `src/services/trip_command_processor.py`, `src/services/notification_service.py`
- **Identifier:** `paginate(...)`, `TripCommandProcessor._show_help` / `_show_help_for_kind` / `_show_codes`, `NotificationService.send_command_reply_premium_sms`

> **Schicht-Hinweis:** Reiner Python-Core (`src/services/`, `src/i18n/`). Kein Frontend, keine Go-API. Der Eingang läuft über `src/services/inbound_sms_reader.py` (unverändert bis auf Durchreichen der Seitenzahl, falls nötig).
>
> **Trip/Orte-Teilung:** HILFE gilt für Trip (route) und Orts-Vergleich (vergleich); beide gehen durch dieselbe Seitenfunktion. Kein neues Komponenten-Paar.
>
> **Mandantentrennung:** Es entsteht kein neuer Zustand je Nutzer. Die Antwort geht wie bisher nur an die Absendernummer des Nutzers; Test mit zwei Nutzern (AC-15).
>
> **Kanäle:** Nur Premium-SMS ändert sich. Telegram, E-Mail und SMS behalten ihren Wortlaut. Alle Hilfe- und Codes-Inhalte bleiben auf Premium erreichbar (ADR-0095).

## Estimated Scope

- **LoC:** ca. +120 Produktiv, +190 Tests, Docs
- **Files:** 13 (4 Produktiv inkl. 1 neu, 2 i18n, 4 Tests inkl. 1 neu, 3 Doku)
- **Effort:** medium (Risiko MEDIUM: zentraler Versandweg der Premium-Antworten)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/inbound_sms_reader.py` | module | Eingang Premium-SMS, Ziellos-Zweig (`ZIELLOS_SCHLUESSEL`), Doppel-Parse |
| `src/services/trip_command_processor.py` | module | `_parse_command` liefert Seitenzahl als `value`; HILFE/CODES-Dispatch; Fassung unbekannter Befehl; Drilldown-Grenze |
| `src/services/notification_service.py` | module | `send_command_reply_premium_sms`: falten + harte Kürzung vor `send()` |
| `src/services/premium_sms_pages.py` | module (neu) | reine Seiten- und Kürzfunktion |
| `src/output/renderers/channel_layout.py` | module | `CHANNEL_LIMITS["premium_sms"].max_chars = 153`, `sms` 160 |
| `src/utils/ascii_fold.py` | module | `fold_ascii` (kann verlängern, daher erst falten, dann messen) |
| `src/i18n/messages/{de,en}/inbound.json` | i18n-Katalog | Verweis- und Bereichstexte (ADR-0104) |
| `tests/helpers/transport_mitschrift.py` | test-helper | Aufzeichner `mit.sendungen("premium_sms")` |

## Implementation Details

Ansatz: Seiten für statische, nebenwirkungsfreie Texte plus zentrales Sicherheitsnetz für alles Übrige.

1. **`paginate(zeilen, page, *, verweis_fn, limit=153) -> str`** in `src/services/premium_sms_pages.py`: jede Zeile erst `fold_ascii`, dann messen; Verweis zählt ins Budget; greedy ganze Einträge, nie mitten in einem Befehl oder Kürzel schneiden; Einzelzeile über dem Limit wird hart gekürzt; Seitenzahl N ergibt sich aus dem Gesamtlauf; letzte Seite ohne Verweis.
2. **Seiten-Weiche** nur bei `msg.channel == "premium_sms"` in `_show_help`, `_show_help_for_kind` (route und vergleich) und `_show_codes`. Die Seitenzahl kommt als `value` aus `_parse_command` („HILFE 2" liefert ("hilfe","2")); bisher wird `value` bei hilfe/kuerzel verworfen (Vergleichs-Dispatch eingeschlossen). Die Weiche hängt NIE an `self._en` und liegt nie in `hilfe_kurzform`/`codes_text`, damit Telegram- und E-Mail-Wortlaut gleich bleiben.
3. **Ungültige Seite:** nicht numerisch oder ≤ 0 → Seite 1; größer als N → kurze Antwort „HELP: pages 1-N" bzw. „CODES: pages 1-N" (für alle Konten englisch, ADR-0104 Nr. 5).
4. **Verweis** aus dem i18n-Katalog, Schlüssel `inbound.seite.*`: „more: HELP 2" / „more: CODES 2" für **alle** Konten (de und en byte-gleich, ADR-0104 Nr. 5, PO-Entscheidung 2026-11-20 in #3133). Deutsche Befehlswörter (`HILFE 2`, `KUERZEL 2`) werden weiterhin verstanden.
5. **Unbekannter Befehl (nur Premium):** keine Seiten; englische Fassung ≤ 153 Zeichen mit Verweis auf HELP und CODES, für alle Konten gleich. Telegram-Wortlaut unverändert.
6. **Sicherheitsnetz:** `send_command_reply_premium_sms` faltet jeden Body mit `fold_ascii`, kürzt bei > 153 hart mit Kennzeichen (z. B. Auslassungszeichen `~` als letztes Zeichen, im Budget) und sendet dann genau einmal. Das Kontingent-Gate (ADR-0116) läuft davor und bleibt unberührt.
7. **Drilldown-Grenze:** `_KURZFORM_MAX_ZEICHEN` (160) wird kanalabhängig aus `CHANNEL_LIMITS` gelesen: `premium_sms` 153, `sms` 160.
8. **Bewusst nicht in `_COMMAND_SPECS`:** das Seiten-Argument erscheint nicht im Hilfetext, sonst änderte sich der Telegram-HELP. Der Verweis am Seitenende ist die Erklärung.

## Expected Behavior

- **Input:** Premium-SMS-Befehl über den echten Eingang, z. B. `HILFE`, `HILFE 2`, `HELP 3`, `KUERZEL`, `CODES 2`, unbekanntes Wort, `STATUS`.
- **Output:** Genau eine Premium-SMS ≤ 153 Zeichen (nach `fold_ascii`), HILFE/CODES mit Seitenverweis, letzte Seite ohne Verweis.
- **Side effects:** Je Antwort ein Kontingentplatz (`premium_sms_reply`, ADR-0116). Kein neuer Nutzerzustand.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Trip-Kontext und deutscher Sprache / When er per Premium-SMS `HILFE` und danach `HILFE 2`, `HILFE 3` usw. bis zur letzten Seite sendet / Then ist jede Antwort genau eine Premium-SMS von höchstens 153 Zeichen nach `fold_ascii`, kein Eintrag ist mitten im Befehl abgeschnitten und alle Seiten zusammen enthalten jeden Trip-Befehl der Hilfe vollständig.
  - Test: Über den Premium-SMS-Eingang alle Seiten abfragen, `mit.sendungen("premium_sms")` prüfen: Länge je Seite, Vereinigung aller Seiten deckt die Befehlsliste ab.

- **AC-2:** Given ein Nutzer mit englischer Sprache und Trip-Kontext / When er `HELP` und die Folgeseiten abfragt / Then gelten dieselben Garantien wie in AC-1 (jede Seite ≤ 153, vollständig, nie mitten im Eintrag geschnitten) mit englischem Verweis „more: HELP n".
  - Test: Englischer Nutzer, alle Seiten über den Eingang, Längen- und Vollständigkeitsprüfung.

- **AC-3:** Given ein Nutzer im Kontext Orts-Vergleich / When er `HILFE` (bzw. `HELP`) mit und ohne Seitenzahl sendet / Then ist jede Antwort genau eine Nachricht ≤ 153 Zeichen, die Vergleichs-Befehle sind über die Seiten vollständig erreichbar und die Seitenzahl wird auch im Vergleichs-Dispatch ausgewertet.
  - Test: Vergleichs-Kontext über den Eingang, alle Seiten, Vollständigkeit gegen die Vergleichs-Befehlsliste.

- **AC-4:** Given ein Nutzer sendet `KUERZEL` oder `CODES` (de und en) / When er alle Seiten abfragt / Then ist jede Seite ≤ 153 Zeichen, kein Kürzel ist zerschnitten und die Vereinigung aller Seiten enthält jedes Kürzel der bisherigen Antwort.
  - Test: Eingang mit `KUERZEL`/`CODES` plus Folgeseiten, Vergleich der Kürzelmenge mit `codes_text`.

- **AC-5:** Given eine mehrseitige Antwort / When die letzte Seite abgefragt wird / Then enthält sie keinen „mehr:"/„more:"-Verweis, alle früheren Seiten enden dagegen mit dem Verweis auf die nächste Seite.
  - Test: Seite 1 und letzte Seite vergleichen: Verweis vorhanden bzw. abwesend, Seitenzahl im Verweis zählt hoch.

- **AC-6:** Given Nutzer mit deutscher bzw. englischer Sprache / When eine Seite mit Verweis gesendet wird / Then lautet der Verweis für beide Sprachen gleich englisch „more: HELP 2", bei Codes „more: CODES 2" (ADR-0104 Nr. 5, PO-Entscheidung 2026-11-20); die Seite ist für de und en byte-gleich.
  - Test: Je Sprache und Befehl Seite 1 abfragen, Verweistext zeichengenau prüfen.

- **AC-7:** Given ein Nutzer sendet eine ungültige Seitenzahl / When die Angabe `abc`, `0` oder eine negative Zahl lautet / Then antwortet Gregor mit Seite 1 (eine Nachricht ≤ 153), nicht mit einem Fehler.
  - Test: `HILFE abc` und `HILFE 0` über den Eingang, Antwort gleich der Seite-1-Antwort von `HILFE`.

- **AC-8:** Given eine Hilfe mit N Seiten / When der Nutzer eine Seite größer als N verlangt / Then lautet die Antwort für deutsche und englische Konten „HELP: pages 1-N" (bei Codes „CODES: pages 1-N"), genau eine Nachricht ≤ 153 Zeichen.
  - Test: `HILFE 99` und `HELP 99` über den Eingang, zeichengenauer Vergleich mit dem erwarteten Text.

- **AC-9:** Given ein Nutzer über Telegram oder E-Mail / When er `HELP`, `CODES`/`KUERZEL` oder ein unbekanntes Wort sendet / Then bleibt der Wortlaut zeichengenau wie vor dieser Änderung; weder Seiten noch Verweise erscheinen.
  - Test: Telegram-Eingang und E-Mail-Weg, Antwort gegen den bisherigen Wortlaut (bestehende Tests in `test_kurzform_befehle_englisch.py`).

- **AC-10:** Given ein Nutzer sendet über Premium-SMS ein unbekanntes Befehlswort (de und en) / When Gregor antwortet / Then ist die Antwort für beide Sprachen dieselbe englische Nachricht ≤ 153 Zeichen mit Verweis auf `HELP`, ohne Seitenmechanik.
  - Test: Unbekanntes Wort über den Eingang, Länge ≤ 153 und Verweiswort enthalten.

- **AC-11:** Given eine übrige Premium-Befehlsantwort länger als 153 Zeichen (z. B. `STATUS` mit sehr vielen Etappen, Mehrdeutig-Hinweis mit langer Namensliste) / When sie versendet wird / Then wird sie zentral gefaltet, auf höchstens 153 Zeichen gekürzt und mit einem Kürzungskennzeichen am Ende versehen; es geht genau eine Nachricht raus.
  - Test: Trip mit langer Etappenliste bzw. mehrdeutigen langen Namen, Eingang `STATUS`, Länge ≤ 153, Kennzeichen vorhanden, eine Sendung.

- **AC-12:** Given eine Premium-Antwort mit Zeichen, die `fold_ascii` verlängert oder ersetzt (z. B. Umlaute, ß, Sonderzeichen in Trip-Namen) / When die Antwort gesendet wird / Then ist die Länge nach dem Falten höchstens 153 und die Nachricht enthält nur GSM-taugliche Zeichen (kein Umschalten auf UCS-2).
  - Test: Trip-Name mit Umlauten und Sonderzeichen, Antwort über den Eingang, gesendeter Text ist ASCII/GSM und ≤ 153.

- **AC-13:** Given die Drilldown-Kurzform (z. B. Etappenwetter) / When sie für `premium_sms` bzw. `sms` erzeugt wird / Then gilt für Premium die Grenze 153, für SMS weiterhin 160.
  - Test: Drilldown-Antwort für beide Kanäle mit langem Inhalt, Längen ≤ 153 bzw. ≤ 160, SMS-Länge nicht verkürzt.

- **AC-14:** Given jede Seite oder gekürzte Antwort / When sie gesendet wird / Then verbraucht sie genau einen Kontingentplatz (`premium_sms_reply`, ADR-0116) und es gibt keine Mehrfachsendung (eine Anfrage = eine Sendung).
  - Test: Kontingentzähler und `mit.sendungen("premium_sms")` vor und nach `HILFE 2`: Zähler +1, Sendungen +1.

- **AC-15:** Given zwei verschiedene Nutzer mit je eigener Absendernummer / When beide `HILFE 2` senden / Then erhält jeder die Antwort nur an seine eigene Absendernummer; keine Antwort geht an die Nummer des anderen und es wird kein Fallback auf `"default"` verwendet.
  - Test: Zwei Nutzer über den Eingang, Empfängernummern der Sendungen getrennt prüfen.

- **AC-16:** Given ein Befehl ohne eindeutigen Trip (Ziellos-Zweig: `hilfe`, `columns`, `kuerzel`) / When er mit Seitenzahl gesendet wird (`HILFE 2`) / Then wird er im Ziellos-Zweig genauso aufgelöst wie ohne Seitenzahl und liefert die gewünschte Seite.
  - Test: Nutzer mit mehreren Trips, `HILFE 2` ohne Trip-Bezug über den Eingang, Antwort ist Seite 2 statt Mehrdeutig-Hinweis.

## Definition of Done

- AC-1 bis AC-16 durch Kern-Tests am echten Premium-SMS-Eingang belegt (Aufzeichner `mit.sendungen("premium_sms")`, DE und EN, zwei Nutzer), Kern-Schicht grün
- Telegram- und E-Mail-Wortlaut von HELP/CODES/unbekanntem Befehl nachweislich unverändert (bestehende Tests grün, nur Premium-Erwartungen umgestellt)
- Doku angepasst (`premium_sms_format.md`, `sms_format.md` §5a, Ablösungsvermerk in `feat_2417_kurzform_englisch.md`)
- Staging-E2E: HILFE, HILFE 2 und KUERZEL über den Premium-SMS-Eingang, Empfang an der zweiten seven.io-Nummer, jede Antwort ≤ 153 Zeichen
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe, alle 6 CI-Checks grün, Produktion ausgeliefert, Selftest grün

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_3133_premium_antwort_laenge.py` (neu), am echten Eingang nach Muster `test_3100_premium_sms_fallliste.py` mit `aufzeichner_installieren` und `mit.sendungen("premium_sms")`:
  - GIVEN Trip-Nutzer de/en WHEN HILFE/HELP alle Seiten THEN je ≤ 153, vollständig (AC-1, AC-2)
  - GIVEN Vergleichs-Kontext WHEN HILFE-Seiten THEN dasselbe (AC-3)
  - GIVEN KUERZEL/CODES WHEN alle Seiten THEN Kürzelmenge vollständig (AC-4)
  - GIVEN letzte Seite WHEN abgefragt THEN kein Verweis (AC-5), Verweis englisch für de und en (AC-6)
  - GIVEN abc/0 und > N WHEN HILFE gesendet THEN Seite 1 bzw. „pages 1-N" (AC-7, AC-8)
  - GIVEN Telegram/E-Mail WHEN HELP/CODES/unbekannt THEN Wortlaut unverändert (AC-9)
  - GIVEN unbekanntes Wort auf Premium WHEN gesendet THEN ≤ 153 mit Verweis (AC-10)
  - GIVEN langer STATUS/Mehrdeutig WHEN gesendet THEN gekürzt mit Kennzeichen (AC-11), Faltung (AC-12)
  - GIVEN Drilldown WHEN premium_sms/sms THEN 153/160 (AC-13)
  - GIVEN Kontingent WHEN Seite gesendet THEN +1 (AC-14); zwei Nutzer (AC-15); Ziellos-Zweig (AC-16)
- [ ] Reine Einheitstests für `paginate` (Grenzfälle: Einzelzeile > 153, Verweis im Budget, genau passende Seite).
- [ ] Anzupassen (Premium-Erwartung auf Seiten umstellen, Telegram bleibt): `tests/tdd/test_kurzform_befehle_englisch.py`, `tests/tdd/test_befehle_premium_sms_e2e.py` (Segment-Tests um Z. 331, 353, 399), `tests/tdd/test_befehlsangebot_vollstaendig.py` (Z. 79).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/premium_sms_pages.py` | CREATE | reine Seiten- und Kürzfunktion (~70 LoC) |
| `src/services/trip_command_processor.py` | MODIFY | Seiten-Weiche hilfe/kuerzel (route + vergleich), Premium-Fassung unbekannter Befehl, Drilldown-Grenze kanalabhängig (~40 LoC) |
| `src/services/notification_service.py` | MODIFY | `send_command_reply_premium_sms`: falten + harte Kürzung vor `send()` (~15 LoC) |
| `src/services/inbound_sms_reader.py` | MODIFY (falls nötig) | Seitenzahl im Ziellos-Zweig nicht verlieren |
| `src/i18n/messages/de/inbound.json`, `src/i18n/messages/en/inbound.json` | MODIFY | Verweis- und Bereichstexte (~6 Schlüssel) |
| `tests/tdd/test_3133_premium_antwort_laenge.py` | CREATE | Tests zu AC-1..AC-16 |
| `tests/tdd/test_kurzform_befehle_englisch.py`, `tests/tdd/test_befehle_premium_sms_e2e.py`, `tests/tdd/test_befehlsangebot_vollstaendig.py` | MODIFY | Premium-Erwartungen auf Seiten |
| `docs/reference/premium_sms_format.md` | MODIFY | Budget 153 vereinheitlichen, Seitenmechanik, Verweis-Wortlaut |
| `docs/reference/sms_format.md` | MODIFY | §5a: „genau eine Nachricht" bleibt für SMS, Premium-Seiten und Drilldown-Grenze 153 vermerken |
| `docs/specs/modules/feat_2417_kurzform_englisch.md` | MODIFY | Ablösungsvermerk: AC-8/AC-9 und Known Limitation (Segmentgrenze HELP/CODES) gelten für `premium_sms` nicht mehr, ersetzt durch #3133; Telegram/E-Mail unverändert |

## Doku-Anpassungen

- `premium_sms_format.md` §1, §4 und Sprache: 160-Budget auf 153 angleichen, Seitenbefehle und Verweis dokumentieren.
- `sms_format.md` §5a: Hinweis auf abweichende Premium-Regel.
- `feat_2417_kurzform_englisch.md`: Ablösungsvermerk bei AC-8, AC-9 und in Known Limitations (ca. Z. 352) für `premium_sms`.
  - **Stand 2026-11-20:** Die Spec von #2417 ist durch einen abgeschlossenen Workflow eingefroren (Spec-Freeze), ein Vermerk dort ist nicht zulässig. Die Ablösung gilt daher über diese Spec und `docs/reference/premium_sms_format.md` §4: Für `premium_sms` ersetzen die Seiten (je ≤ 153 Zeichen) die Segmentgrenzen aus #2417 AC-8 (HELP ≤ 3) und AC-9 (CODES ≤ 5); der Wortlaut gilt für die Vereinigung aller Seiten. Telegram und E-Mail unverändert.

## Known Limitations

- **Datenabhängige Antworten werden gekürzt, nicht geseitet:** Bei sehr langem STATUS, JETZT, STRECKE, Mehrdeutig-Hinweis o. Ä. gehen Inhalte verloren (Kürzungskennzeichen zeigt das an). Ein universelles `MEHR`/`MORE` über eine gespeicherte letzte Antwort je Nutzer (neuer Zustand, TTL, Isolation, neuer HELP-Eintrag in allen Kanälen) ist ein Folge-Ticket, nur bei Bedarf aus dem Betrieb.
- **Seiten-Argument bewusst nicht in `_COMMAND_SPECS`:** Der Hilfetext (auch Telegram) bleibt gleich; die Seitenfunktion ist nur über den Verweis am Seitenende auffindbar.
- Der generische Seiten-Wrapper für alle Befehle wurde verworfen: PAUSE/RUHETAG schreiben Daten erneut, „2" kollidiert mit PAUSE 2D/STRECKE km/STARTDATUM/REPORT, STATUS/JETZT sind wetter- und zeitabhängig und buchen `manueller_abruf` (ADR-0117).
- Der Kanal `sms` hat keinen produktiven Eingang; seine Grenze 160 bleibt unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neues ADR nicht nötig, bestehende Entscheidungen werden umgesetzt); berührt ADR-0049 (Premium-SMS), ADR-0095 (Kanal-Parität), ADR-0104 (i18n), ADR-0116 (Kontingent)
- **Rationale:** Setzt die PO-Entscheidung aus #3133 innerhalb bestehender ADRs um. Kanal-Parität bleibt gewahrt, weil jede Hilfe- und Codes-Information über Seiten erreichbar ist; Kontingent: jede Seite ist eine Antwort, ein Platz. Keine Abweichung von bestehenden Entscheidungen, daher kein neues ADR.

## Changelog

- 2026-11-20: Initial spec created (Issue #3133, PO-Entscheidung seitenweise)
- 2026-11-20 v1.1: AC-6, AC-8, AC-10 und Implementation Details 3–5 an ADR-0104 Nr. 5 angeglichen: Verweis, Bereichsantwort und Unbekannt-Hinweis auf Premium-SMS für alle Konten englisch (PO-Entscheidung 2026-11-20, Kommentar in #3133).
