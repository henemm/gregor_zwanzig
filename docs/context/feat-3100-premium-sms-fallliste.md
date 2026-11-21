# Context: feat-3100-premium-sms-fallliste

## Request Summary
Issue #3100 (Epic #3058, Phase 3e von #3047), **gekürzter Umfang laut PO-Freigabe 17.11.** (ADR-0124 Nr. 8): Die Premium-SMS folgt vorerst der SMS und hat keine eigene Spalte. Zu bauen ist nur der Nachweis „Premium-SMS = SMS-Text“ als **eigene Fallliste** `fallliste_premium_sms.json` im Prüfkatalog, vom Wächter mitgezählt, geprüft über den **echten Empfangsweg**. Die Auswertung eines eigenen Resolver-Schlüssels `premium_sms` gehört zu #2801 und wird hier **nicht** gebaut.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/fixtures/einstellung_gleich_mail/fallliste_sms.json` | Vorbild (#3099); enthält schon 3 Premium-Fälle (`sms-premium-gleich-sms-text`, `sms-orte-versand-roh/einfach`, Format `sms+premium_sms`) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_trip.json` / `fallliste_orte.json` | verstreute Premium-Fälle: `R7-KAT-trip-premium-matrix`, `R7-KAT-trip-premium-gleich-sms-kuerzung`, `R7-KAT-orte-premium-gleich-sms`, `orte_premium_sms`-Fälle, `test_t3_premium_sms_folgt_sms_liste` |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | Wächter: `TEILDATEIEN` (trip, orte, validatoren, editor, telegram, sms), `PY_TEST_GLOBS`, Kanal-Abdeckung (f) mit `premium_sms` je Kontext × Aspekt |
| `tests/tdd/test_3099_sms_resolver.py` | Muster: damaliger AC-6-Test Premium = SMS (Trip, echter Versand, zwei Nutzer; seit #3208 ersetzt durch `test_3100_premium_sms_fallliste.py::test_ac1_trip_eingang_premium_gleich_sms`), `test_ac7_orte_sms_versand_folge_und_format` (Orte), AC-11-Wächtertest |
| `tests/tdd/test_3047_r7_kanaele_trip.py::_zwei_nutzer` | Trip-Versandkette mit Aufzeichner an den Kanal-Ausgängen (kein Mock) |
| `src/services/channel_list_resolver.py:158-162` | `premium_sms` fällt ohne eigene Ebene auf `sms` zurück (bleibt so) |
| `src/services/inbound_sms_reader.py`, `trip_command_processor.py` | echter Eingangsweg der Premium-SMS (Garmin-Befehl → Antwort per Premium-SMS) |
| `tests/tdd/test_premium_sms_kommandopfad.py` | Muster für Prüfung über den echten Reader (Außengrenzen: Journal-GET, Learn-POST, vier Kanal-Ausgänge) |
| `tests/tdd/test_premium_sms_empfang_live.py` | Live-Dialog Prod ↔ zweite seven.io-Nummer (Opt-in, nach Prod-Deploy) |
| `src/services/trip_alert.py`, `compare_alert_channels.py` | Alarme an Premium-SMS (Kanalparität #1701) |

## Existing Patterns
- Fallliste je Kanal als eigene Teildatei, Wächter registriert sie in `TEILDATEIEN` und `PY_TEST_GLOBS` (#3098 Telegram, #3099 SMS).
- Fälle tragen `merkmale` als Achsen (Kontext, Report-Typ, Format, Kanal-Ebene nie/leer/gesetzt).
- Prüfung am Wirkort: Aufzeichner an den vier Kanal-Ausgängen des NotificationService, zwei Nutzer.

## Dependencies
- Upstream: Resolver, Trip-/Orte-Versandkette, Inbound-Reader, Kommandoverarbeiter.
- Downstream: nur Prüfkatalog/Wächter; keine Produktionsänderung erwartet (reine Nachweis-Arbeit).

## Existing Specs
- `docs/specs/modules/feat_3099_sms_resolver.md` (AC-6, AC-7, AC-11)
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md`
- `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md`, `feat_2417_befehle_e2e_echter_eingang.md`
- ADR-0049, ADR-0121 (Nr. 5), ADR-0124 (Nr. 8)

## Offene Analysefragen
1. „Echter Empfangsweg“: (a) Versandkette bis Kanal-Ausgang (Briefing Trip + Orte, morning/evening), (b) Eingang per `inbound_sms_reader` → Befehlsantwort per Premium = SMS-Antwort, (c) Alarme. Empfehlung in der Analyse festlegen; voraussichtlich (a)+(b), Alarme prüfen.
2. Bestehende verstreute Premium-Fälle: verschieben in die neue Liste oder nur verweisen? (IDs müssen global eindeutig bleiben; Kanal-Abdeckung darf nicht sinken.)
3. Kürzung 153 statt 160 bei langem Text (Premium hängt evtl. Hinweise an) – ist „gleich“ dann „gleich bis auf Limit“?

## Risks & Considerations
- Nicht versehentlich #2801 vorwegnehmen (keine eigene Premium-Auswahl auswerten).
- Wächter-Abdeckung (f) darf nicht sinken, wenn Fälle umziehen.
- Live-Empfangstest (zweite seven.io-Nummer) kostet Geld und läuft nur Prod nach Deploy; Absender-Thema `InfoSMS` (siehe Memory) beachten.

## Analysis

### Type
Feature (reine Nachweis-Arbeit im Prüfkatalog; Produktionscode bleibt voraussichtlich unverändert, ADR-0124 Nr. 8)

### Befunde (17.11., direkt im Code gemessen)
- Premium-Grenze ist 153 Zeichen (`src/output/renderers/channel_layout.py:57`), SMS 160. „Gleich“ heißt: Premium-Text == SMS-Text, solange dieser in 153 passt; darüber kürzt Premium nach derselben Regel (vom Listenende, amtliche Warnung bleibt), bereits belegt durch `R7-KAT-trip-premium-gleich-sms-kuerzung`.
- **Versandkette** ist schon belegt: Trip damals 3099 AC-6, seit #3208 `test_3100_premium_sms_fallliste.py::test_ac1_trip_eingang_premium_gleich_sms` (Premium-Ebene weicht ab, Text trotzdem gleich, ≤153), Orte `test_ac7_orte_sms_versand_folge_und_format`, `test_compare_channel_layouts_3039.py::test_ac10_premium_sms_text_gleich_sms_text_mit_kanal_einstellungen`.
- **Lücke = echter Empfangsweg:** Kein Test vergleicht die Antwort auf einen Garmin-Befehl (Eingang über `inbound_sms_reader`, Journal-GET → `trip_command_processor` → Premium-Antwort) mit dem SMS-Text desselben Trips/Vergleichs. `test_premium_sms_kommandopfad.py` prüft nur Kanal und Empfänger, nicht den Inhalt. Für Orte gibt es den Eingangsweg ebenfalls (`inbound_sms_reader.py:406-463`, `resolved_kind="vergleich"`).
- Alarme: Premium-Alarmtext = SMS-Alarmtext ist durch Kanalparität (#1701, `test_compare_alert_channel_equivalence.py`, `test_onset_ende_kanalparitaet.py`) abgedeckt; Alarme lesen keine Metrikauswahl → nur als Verweis-Fall aufnehmen, keinen neuen Test.

### Entscheidungen zu den offenen Analysefragen
1. Empfangsweg = (a) Versandkette (vorhandene Tests, als Fälle referenziert) + **(b) Eingangsweg neu** (Trip und Orte, Premium-Ebene weicht bewusst ab, zwei Nutzer, Aufzeichner an den Kanal-Ausgängen wie in `test_premium_sms_kommandopfad.py`, kein Mock-Theater) + (c) Alarm als Verweis-Fall.
2. Verstreute Premium-Fälle **bleiben**, wo sie sind (Muster #3099: IDs global eindeutig, Abdeckung (f) sinkt nicht). Die neue Liste nennt sie im `hinweis`; neue Fälle bekommen Präfix `psms-`.
3. Kürzung: „gleich bis auf 153er-Grenze, gleiche Kürzungsregel“; ein Eingangsweg-Fall mit langem Text (>153) prüft Präfix-Gleichheit und Warnung hinten.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/fixtures/einstellung_gleich_mail/fallliste_premium_sms.json` | CREATE | Fallliste Premium-SMS (~12–16 Fälle: Trip/Orte × Eingang/Versand × morning/evening × Kanal-Ebene nie/leer/abweichend × Roh/Einfach × Kürzung × Alarm-Verweis) |
| `tests/tdd/test_3100_premium_sms_fallliste.py` | CREATE | Eingangsweg-Tests Trip + Orte (Premium-Antwort == SMS-Text, Premium-Ebene ungelesen, zwei Nutzer), Kürzungsfall, Wächter-Selbsttest |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | `TEILDATEIEN` + `premium_sms`, `PY_TEST_GLOBS` + `tests/tdd/test_3100_*.py`, Selbsttest „fehlende Premium-Teildatei scheitert klar“ |
| `docs/reference/…` Ausgabe-Matrix / Prüfkatalog-Doku | MODIFY | Premium-Zeile verweist auf neue Fallliste |
| `src/…` | — | keine Änderung erwartet; scheitert ein Eingangsweg-Test fachlich, ist das ein Befund (eigenes Issue bzw. Fix im Rahmen) |

### Scope Assessment
- Files: 4–5
- Estimated LoC: +350/-5 (davon ~200 Test, ~120 JSON)
- Risk Level: LOW (nur Tests und Prüfkatalog; Produktionsverhalten unverändert)

### Technical Approach
Muster #3099 übernehmen: eigene Teildatei, vom Wächter geladen und gezählt. Neue Tests treiben den echten Reader (Journal-GET-Außengrenze, `_Journal`/`_HttpSchicht`-Muster aus `test_premium_sms_kommandopfad.py`), legen je Nutzer einen Trip bzw. Vergleich mit abweichender `channel_layouts.premium_sms` an, lösen „heute/morgen“ per Garmin-Nachricht aus und vergleichen den an `PremiumSmsOutput.send` gebuchten Text mit dem SMS-Text desselben Ziels (Versandkette `send_on_demand_report(..., restrict_to_channel="sms")`). Kein Auswerten eines eigenen `premium_sms`-Schlüssels (#2801).

### Dependencies
Inbound-Reader, Kommandoverarbeiter, Trip-/Orte-Renderer, Resolver (unverändert); Wächter `test_einstellung_gleich_mail_fallliste.py`.

### Open Questions
- keine Produktfrage offen (Umfang durch PO-Kommentar 17.11. und ADR-0124 Nr. 8 festgelegt). Live-Empfang über die zweite seven.io-Nummer bleibt Teil von `/e2e-verify`/Deploy, nicht der Kern-Schicht.

## TDD RED (17.11.)

Testdatei `tests/tdd/test_3100_premium_sms_fallliste.py`, Fallliste `fallliste_premium_sms.json` (13 Fälle, Präfix `psms-`). RED-Beleg: `docs/artifacts/feat-3100-premium-sms-fallliste/test-red-output.txt` (6 rot, 11 grün).

- **Rot, Wächter (erwartet):** `test_ac5_*`, `test_ac6_*`, `test_ac7_*` – `premium_sms` fehlt in `TEILDATEIEN`, `tests/tdd/test_3100_*.py` fehlt in `PY_TEST_GLOBS`. GREEN: beides ergänzen; `_syn_daten()` im Wächter um `"fallliste_premium_sms.json": {"faelle": []}` erweitern (sonst bricht `test_selbsttest_vollstaendige_liste_ist_gruen`).
- **Rot, fachlicher Befund (AC-4):** Trip-Premium-SMS über den Eingangsweg sendet den 160er-SMS-Text unverändert (156 Zeichen gemessen) statt auf 153 zu kürzen. Ursache: `NotificationService` übergibt `sms_text` (gerendert mit `max_length=160`, `trip_report.py`) direkt an `PremiumSmsOutput.send`; dort keine Kürzung. Fix im Rahmen (Spec: „Befund statt Aufweichen“): Premium-Text mit derselben Kürzungsregel (vom Listenende, Warnblock bleibt hinten) auf 153 rendern, nicht hart abschneiden. Bei SMS-Text ≤ 153 muss Premium == SMS bleiben (AC-1).
- **Grün (Nachweis heutigen Verhaltens):** AC-1/AC-8 (Trip, Premium-Ebene abweichend/leer/nie, heute/morgen), AC-2 (Orte Roh/Einfach), AC-3 (zwei Nutzer, ab/ba), AC-5-Selbsttest „Fall ohne Test“.
