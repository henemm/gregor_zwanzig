---
entity_id: fix_1767_nowcast_mehrort_kurzform
type: bugfix
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
workflow: fix-1767-nowcast-mehrort-kurzform
issue: 1767
tags: [alarm, nowcast, radar, sms, premium-sms, telegram, ortsvergleich, kanal-paritaet]
---

# Nowcast-/Radar-Onset-Alarm im Ortsvergleich: alle Orte in jeder Kurzform (#1767, inkl. B2-51)

## Approval

- [ ] Approved

## Purpose

Löst ein Regen- oder Gewitter-Anmarsch im Ortsvergleich an mehreren Orten gleichzeitig aus, nennen heute nur Betreff und E-Mail alle Orte. SMS, Premium-SMS und Telegram-Kurzstil werten nur den ersten Ort aus, die Telegram-Langform zeigt alle Ortsnamen im Kopf, aber Wert und Zeit nur des ersten Ortes (irreführend, dazu `km 0–0`). Nach PO-Entscheid 2026-11-09 (Variante A') nennt jeder Kanal alle auslösenden Orte mit demselben Inhalt (ADR-0095 Kanal-Parität).

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_render_sms_onset` (Z. 1173), `_render_telegram_onset` (Z. 981), `_render_sms_body` (Z. 1823, Greedy-Budget wird in Helfer ausgelagert)

## Abgelöster Produkt-Entscheid (ausdrücklich)

**Entscheid 3b aus #1948 S4 (PO 2026-08-19) wird abgelöst.** Wortlaut damals (`docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md`, Known Limitations, Z. 285-288): „kein `+N`-Zähler — die Nachricht wertet nur den führenden Ort aus; Verschweigen der übrigen Orte ist gewollt."

- **Ablösung durch:** diese Spec (#1767), PO-Entscheid 2026-11-09 („Alle Orte überall", Variante A').
- **Begründung:** ADR-0095 (2026-10-21, jünger als 3b): jeder Kanal beantwortet jede Frage mit demselben Inhalt, die Empfangslage unterwegs ist unvorhersehbar, Premium-SMS ist eventuell der einzige Kanal. Der Grund von 3b („ein Zähler verspräche Vollständigkeit, die er nicht einlöst") entfällt: die neue Form nennt jeden Ort mit eigenem Token (echte Vollständigkeit); `+k` erscheint nur bei Platzmangel und zählt exakt die nicht genannten Orte.
- **Folgepflichten dieser Spec (Teil des Scopes):**
  1. `fix_1948_s4_nowcast_sms_zielbild.md` Known Limitation Z. 285-288 bekommt den Vermerk „Abgelöst durch #1767 (PO 2026-11-09, ADR-0095)".
  2. 3b steht in **keinem ADR** (Prüfung `docs/adr/`: nur Specs/Kontext). Es braucht daher kein neues ADR; ADR-0095 erhält einen kurzen **Nachtrag** („Nachtrag #1767, 2026-11-09": Radar-Onset im Ortsvergleich nennt in allen Kurzformen alle Orte, löst 3b aus #1948 S4 ab). Status bleibt „Akzeptiert", Indexzeile in `docs/adr/README.md` bleibt konsistent (`tests/test_adr_index_drift.py`).
  3. `rework_1467_s2_aenderungsalarm.md` Z. 161/179/379-380 („Radar-Onset bewusst gebündelt") bleibt gültig: es bleibt EINE gebündelte Nachricht; nur ihr Inhalt wird vollständig. Kurzer Vermerk dort.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `to_multi_location_onset_alert_message` (`project.py:547`) | function | baut je auslösendem Ort ein `OnsetEvent`; trägt `location_label` nur bei >1 Ort; hier wird die Reihenfolge (s. Entscheidung 1) festgelegt |
| `_render_email_onset_multi` (`render.py:919`) | function | Vorbild Telegram-Langform (eine Zeile je Ort), bleibt inhaltlich unverändert |
| `_sms_token` / `location_positions` (`render.py:1698`, `compare_alert.py:575`) | Muster | Änderungsalarm-Muster `pos:token`, ohne Namenskopf (PO #1467 S2 AG3b) |
| `_location_positions` (`compare_alert.py:575`) | staticmethod | wird zur freien, geteilten Funktion; Position = 1-basierter Platz in `preset["location_ids"]` über auflösbare Orte |
| `send_multi_location_radar_alert` (`notification_service.py:1262`) | method | bekommt optionalen Parameter `location_positions`, reicht ihn an `_dispatch_alert_message` (SMS-Rendering Z. 2053-2058, Telegram-Kurzstil Z. 2160-2176) |
| `CompareRadarAlertService` (`compare_radar_alert.py:431`) | Aufrufer | hat `preset` und `all_locations` (Z. 155/252), berechnet die Positionen |
| `compare_alert_preview_service._onset` (`:162-187`) | Vorschau | muss denselben Positionsweg gehen wie der Versand (Parität Vorschau = Versand) |
| i18n-Katalog `src/i18n/messages/{de,en}/alarm.json` | Katalog | Telegram-Langform-Texte (`alarm.regen.buendel` existiert; fehlende Zeilen-Bausteine als neue Schlüssel in DE und EN) |
| ADR-0095, ADR-0104 | ADR | Kanal-Parität; Protokoll-Token nie übersetzen |

## Scope

### Affected Files

Schicht: Python-Core (`src/output/`, `src/services/`); kein Frontend, keine Go-API.

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/render.py` | MODIFY | Mehrort-Zweig (`len(events) > 1`) in `_render_sms_onset` und `_render_telegram_onset`; Budget-Helfer `_fit_tokens_with_overflow` aus `_render_sms_body` ausgelagert |
| `src/output/renderers/alert/project.py` | MODIFY | Events nach Beginn sortiert (stabil), Entscheidung 1 |
| `src/services/compare_alert.py` | MODIFY | `_location_positions` als freie Funktion teilbar (staticmethod delegiert) |
| `src/services/compare_radar_alert.py` | MODIFY | Positionen berechnen, an `send_multi_location_radar_alert` reichen |
| `src/services/notification_service.py` | MODIFY | optionaler Parameter `location_positions` in `send_multi_location_radar_alert` und bis ins SMS-Rendering |
| `src/services/compare_alert_preview_service.py` | MODIFY | Vorschau mit Positionen (identisch zum Versand) |
| `src/i18n/messages/de/alarm.json`, `.../en/alarm.json` | MODIFY | ggf. neue Schlüssel Telegram-Zeile |
| `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` | MODIFY | „Abgelöst durch #1767"-Vermerk |
| `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` | MODIFY | Klarstellungsvermerk |
| `docs/adr/0095-kanal-paritaet-jeder-kanal-jede-frage.md` | MODIFY | Nachtrag #1767 |
| `docs/reference/sms_format.md`, `premium_sms_format.md`, `telegram_format.md` | MODIFY | Mehrort-Onset-Form dokumentieren |
| `tests/tdd/test_fix_1767_nowcast_mehrort_kurzform.py` | CREATE | neue Tests (s. Testplan) |
| `tests/tdd/test_alert_sms_location_positions.py` (:1028), `test_alert_sms_onset_zeitpunkt.py` (:253), `test_onset_menge_kanalparitaet.py` (:174), `test_compare_alert_telegram_per_location.py` (:584, nur bei Berührung der Telegram-Auffächerung), `test_alert_preview_compare_paritaet.py` (:412) | MODIFY | Erwartung auf neue Mehrort-Form nachziehen (bewusste Formatänderung, nicht Regression) |

Unberührt (Gegenprobe): `tests/tdd/test_multi_location_onset_alert.py:275` (Ein-Event), Golden `tests/golden/abweichungs_radar_alarm/regen_buendel.*` (nur E-Mail; siehe Risiko Reihenfolge).

## Estimated Scope

- **LoC:** Code ~+100/-20, Tests ~+200
- **Files:** 14 Code/Doku (6 Code, 2 i18n, 6 Doku) + 6 Tests
- **Effort:** medium

## Implementation Details

**Mehrort-Weiche:** greift nur bei `msg.source == COMPARE_RADAR_SOURCE` und `len(msg.events) > 1`. Trip-Onset (immer genau ein Event) und Ein-Ort-Compare (ein Event, `location_label=None`) laufen den unveränderten Zweig, byte-identisch.

**Kurzform (SMS, Premium-SMS, Telegram-Kurzstil):** ein Token je Ort in der bestehenden Token-Form aus `_render_sms_onset` (Beginn `R@14:05`, mit Menge `R2.5@14:05`, Gewitter `TH@14:05 R2.5`, laufend `R now`, inklusive Ende-/Güte-/Prüfmarker), davor `pos:`; Token durch Leerzeichen getrennt; kein Namenskopf, kein `km0-0`. Beispiel: `1:R@14:05 2:R@14:40`. Position = 1-basierter Platz im Preset über auflösbare Orte (Regel wie Änderungsalarm, inkl. Nachrücken bei gelöschten Orten). Ein Verschärfungs-Token (`_sms_verschaerfung_token`), falls vorhanden, steht einmal vorn und zählt gegen das Budget. Fehlt für einen Ort die Position (z. B. Aufrufer ohne `location_positions`), steht statt der Zahl der auf 12 Zeichen gekappte ASCII-Ortsname (`Zermatt:R@14:05`) — nie eine geratene Zahl.

**Budget-Helfer:** die Greedy-Schleife aus `_render_sms_body` (Z. 1896-1910) wird zu `_fit_tokens_with_overflow(head, tokens, limit, keep_first=False)` ausgelagert; der Änderungsalarm ruft ihn mit `keep_first=False` und bleibt byte-identisch. Der Onset-Zweig nutzt ihn mit `keep_first=True`.

**Telegram-Langform:** EINE Nachricht: Kopf `<b>{alarm.regen.buendel, n=Anzahl}</b>` (z. B. „Regen-Alarm: 2 Orte"), danach eine Zeile je Ort mit Ortsname, Art, Beginn, Ende, Suffixen und Intensität (Bausteine wie `_render_email_onset_multi`: `_onset_wann_kopf`, `_onset_wann_zeile`, `_onset_suffixes`, `_intensity`), Quelle einmal am Ende. Kein Namens-Join-Kopf, kein `km 0–0`. Bezugs-/Verschärfungszeilen wie im Einzelzweig. Alle Texte über den Katalog DE/EN. Die Langform hat kein Zeichenbudget, daher kein `+k`.

**Vorschau:** `compare_alert_preview_service._onset` ruft `render_sms` mit denselben Positionen aus derselben freien Funktion wie der Versand; ein Test belegt Gleichheit Vorschau = Versandtext.

## Tech-Lead-Entscheidungen

1. **Reihenfolge der Orte:** Für alle Kanäle einheitlich: nach Beginn aufsteigend (laufend = Minute 0 zuerst), Gleichstand nach Position im Preset (stabile Sortierung, weil die Eingangsreihenfolge bereits `preset["location_ids"]` folgt). Sortiert wird einmal in `to_multi_location_onset_alert_message`; Betreff, E-Mail, Telegram, SMS und Premium-SMS lesen dieselbe `events`-Reihenfolge (echte Parität). Begründung: bei Budget-Überlauf fallen die Orte mit spätestem Beginn weg, die dringendsten bleiben. Der Änderungsalarm sortiert nach Schwere (`_sorted`) — für Onset ist der Beginn das Dringlichkeitsmaß; die Ortsnummer macht die Reihenfolge unabhängig vom Lesen lesbar. Die E-Mail steht heute in Positionsreihenfolge: das Golden `regen_buendel.*` ist beim Umsetzen zu prüfen; weicht seine Fixture von der Beginn-Reihenfolge ab, wird es bewusst neu erzeugt.
2. **Überlauf:** Tokens ganz oder gar nicht (nie mitten im Token schneiden); passen nicht alle, steht am Ende ` +k` mit k = Anzahl nicht genannter Orte (Marker-Länge wird in das Budget einkalkuliert, wie `_render_sms_body`). Gilt identisch für SMS, Premium-SMS (wird ohnehin mit 140 gerendert, also derselbe Text wie SMS) und Telegram-Kurzstil. Der erste (dringendste) Ort bleibt immer erhalten (`keep_first=True`): ein Token ist maximal rund 30 Zeichen, das Limit 140, der Fall „erster Token passt nicht" ist praktisch ausgeschlossen; als Sicherheitsnetz bleibt der harte Endschnitt `body[:limit]`. Es gibt keine Ortsobergrenze; ab ca. 13 Orten erscheint `+k`.
3. **Abgrenzung #2598** (Compare-Änderungsalarm, Telegram-Kopf): Nicht-Scope sind der Änderungsalarm-Pfad, dessen Telegram-Kopf/Sammelbezeichnung, die Telegram-Auffächerung des Änderungsalarms (`notification_service.py:2177-2238`) und die Sammelbezeichnung bei reiner Beginn-Verschiebung (`render.py:1293/1650`). Diese Spec berührt nur den Radar-Onset-Pfad; gemeinsame Dateien werden an getrennten Stellen geändert. (Gegen den Issue-Text geprüft 2026-11-09: #2598 betrifft `to_multi_point_alert_message` → `render_telegram` im Änderungsalarm — doppelter Ortsname und `km 0–0` im Telegram-Kopf; der Onset-Pfad `to_multi_location_onset_alert_message` → `_render_telegram_onset` ist dort nicht genannt. Das `km 0–0` im Onset-Telegram behebt diese Spec selbst, ohne den Änderungsalarm-Pfad anzufassen.)
4. **B2-51:** kein Codefix. Der Rückfall `e.location_label or msg.location_label` (`render.py:1525`) ist nach `project.py:493-524` nicht erreichbar (bei mehreren Gruppen trägt jedes Event seinen Namen). Nachweis nur per Beleg-Test (AC-9).

## Expected Behavior

- **Input:** Compare-Preset mit 2+ Orten, mehrere lösen einen Nowcast-/Radar-Onset aus.
- **Output:** SMS/Premium-SMS/Telegram-Kurzstil z. B. `1:R@14:05 2:R@14:40`; Telegram-Langform eine Nachricht, eine Zeile je Ort; E-Mail unverändert (eine Zeile je Ort).
- **Side effects:** keine neuen Persistenzdaten, keine neuen Endpunkte.

## Test Plan

Tests aus Nutzersicht über den echten Versandpfad (`send_multi_location_radar_alert` mit echter Preset-/Ort-Struktur und dem Test-Transport, der die gerenderte Nachricht festhält) und über den Vorschau-Service; kein Mock-Theater, keine Dateiinhalt-Checks (Ausnahme: Doku mit `# doc-compliance-test`).

### Automated Tests (TDD RED)
- [ ] GIVEN Preset mit Orten A, B, C und Onset an A (14:05) und C (14:40) WHEN Versand THEN SMS-Text `1:R@14:05 3:R@14:40`, ohne Ortsname und ohne `km0-0` (RED heute: `Zermatt: R@14:05`)
- [ ] GIVEN dieselbe Lage WHEN Premium-SMS und Telegram-Kurzstil gesendet THEN beide Texte identisch zur SMS
- [ ] GIVEN dieselbe Lage WHEN Telegram-Langform THEN genau eine Nachricht mit Kopf „Regen-Alarm: 2 Orte" und je einer Zeile für A und C, Wert und Zeit je Ort korrekt, kein `km 0–0`, kein Namens-Join-Kopf
- [ ] GIVEN dieselbe Lage in Nutzersprache `en` WHEN Telegram-Langform THEN Kopf und Zeilentexte englisch, SMS-Token unverändert
- [ ] GIVEN 20 auslösende Orte WHEN Versand THEN SMS-Länge <= 140, endet auf ` +k` mit k = nicht genannte Orte, kein abgeschnittenes Token, früheste Orte zuerst
- [ ] GIVEN Orte mit unsortierter Beginnzeit im Preset WHEN Versand THEN SMS, Telegram-Langform und E-Mail führen die Orte in derselben Reihenfolge (Beginn, Gleichstand Position)
- [ ] GIVEN ein Preset und derselbe Alarm WHEN Vorschau gerendert wird THEN SMS-Text der Vorschau == Versandtext
- [ ] GIVEN Ein-Ort-Compare und Trip-Onset WHEN gerendert THEN Ausgabe byte-identisch zu den bisherigen Goldstrings
- [ ] GIVEN zwei Nutzer mit gleichnamigen Orten, aber verschiedener Preset-Reihenfolge WHEN Vorschau je Nutzer THEN jeweils die Positionen des eigenen Presets
- [ ] GIVEN Mehr-Gruppen-Projektion WHEN `render_email` THEN jedes Event trägt seinen eigenen Ortsnamen, der Rückfall `msg.location_label` wird nie benutzt (B2-51-Beleg)
- [ ] Bestandstests der Scope-Tabelle nachgezogen und grün.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit den Orten Zermatt, Chamonix, Verbier (Positionen 1-3), bei dem Zermatt (Beginn 14:05) und Verbier (Beginn 14:40) einen Regen-Anmarsch auslösen / When der Alarm per SMS versendet wird / Then lautet der Text `1:R@14:05 3:R@14:40`, ohne Ortsnamen-Kopf und ohne `km0-0`.
  - Test: Versand über `send_multi_location_radar_alert` mit echtem Preset, gerenderte SMS prüfen.

- **AC-2:** Given dieselbe Lage / When der Alarm per Premium-SMS und per Telegram im Kurzstil versendet wird / Then ist der Text jeweils identisch zur SMS (`1:R@14:05 3:R@14:40`), und beide sind höchstens 140 Zeichen lang.
  - Test: alle drei Kanäle im selben Versandlauf, Texte vergleichen.

- **AC-3:** Given dieselbe Lage, Telegram im ausführlichen Stil / When der Alarm gesendet wird / Then kommt genau EINE Nachricht mit dem Kopf „Regen-Alarm: 2 Orte" und je einer Zeile für Zermatt (ab 14:05) und Verbier (ab 14:40) mit deren eigener Intensität, ohne Aufzählung aller Ortsnamen im Kopf und ohne `km 0–0`.
  - Test: gerenderte Telegram-Nachricht im Versandpfad, Zeilenzahl und Inhalt je Ort.

- **AC-4:** Given ein Nutzer mit Sprache Englisch und dieselbe Lage / When der Alarm per Telegram ausführlich und per SMS kommt / Then sind Kopf und Zeilentexte der Telegram-Nachricht englisch aus dem Katalog, die SMS-Tokens (`R`, `@`, Ortsnummer) bleiben unübersetzt wie im Deutschen.
  - Test: Versand mit `language=en`, Telegram-Text auf englische Bausteine, SMS auf gleichen Text wie AC-1.

- **AC-5:** Given 20 gleichzeitig auslösende Orte / When der Alarm per SMS, Premium-SMS und Telegram-Kurzstil versendet wird / Then ist der Text höchstens 140 Zeichen lang, nennt die Orte mit frühestem Beginn zuerst und vollständig (kein halbes Token) und endet mit ` +k`, wobei k genau die Zahl der nicht genannten Orte ist.
  - Test: Länge, letztes Token, Summe genannter Orte + k == 20.

- **AC-6:** Given Orte, deren Beginnzeiten nicht der Preset-Reihenfolge folgen, und zwei Orte mit gleichem Beginn / When der Alarm über alle Kanäle gesendet wird / Then stehen die Orte in SMS, Premium-SMS, Telegram und E-Mail in derselben Reihenfolge: früherer Beginn zuerst (laufend vor kommend), bei Gleichstand die kleinere Ortsnummer zuerst.
  - Test: Reihenfolge der Orte je Kanal aus den gerenderten Texten extrahieren und vergleichen.

- **AC-7:** Given derselbe Preset und dieselbe Lage / When der Nutzer die Alarm-Vorschau öffnet und danach der echte Alarm versendet wird / Then ist der SMS-Text der Vorschau zeichengleich zum versendeten.
  - Test: Vorschau-Service und Versandpfad mit identischen Eingaben, Textgleichheit.

- **AC-8:** Given ein Trip-Radar-Alarm (immer ein Ort) und ein Ortsvergleich mit genau einem auslösenden Ort / When der Alarm auf allen vier Kanälen gerendert wird / Then ist die Ausgabe byte-identisch zur bisherigen (z. B. `Zermatt: R@14:05`), ohne Ortsnummer und ohne `+k`.
  - Test: bestehende Goldstrings von Trip- und Ein-Ort-Fall unverändert (`test_multi_location_onset_alert.py`, `test_alert_sms_onset_zeitpunkt.py`).

- **AC-9:** Given ein Mehr-Orte-Onset-Alarm mit mehreren Gruppen (B2-51) / When die E-Mail gerendert wird / Then trägt jede Datenzeile den Namen ihres eigenen Ortes, und der Rückfall auf den Nachrichten-Ortsnamen greift nie auf einen fremden Ort (kein Codefix nötig).
  - Test: Projektion mit 2 und 3 Gruppen, E-Mail-Rendering, Ortsname je Zeile; Ein-Gruppen-Fall liefert denselben Ort.

- **AC-10:** Given zwei Nutzer mit gleichnamigen Orten, aber unterschiedlicher Reihenfolge im jeweiligen Preset / When für jeden Nutzer die Vorschau (mit `user_id` aus dem Auth-Kontext) gerendert wird / Then trägt jede SMS die Ortsnummern des EIGENEN Presets, nie die des anderen Nutzers und nie eine Standard-Nutzerkennung.
  - Test: zwei Nutzerverzeichnisse, Vorschau je Nutzer, Ortsnummern vergleichen. Die Änderung selbst bewegt keine Nutzerdaten (kein neuer Endpunkt, keine Persistenz), die Positionen werden nur aus dem Preset des Nutzers gelesen.

## Definition of Done

- AC-1 bis AC-10 sind erfüllt, jedes AC hat einen grünen Test; keine Zusicherung gelockert, die nachgezogenen Bestandstests ändern nur die Mehrort-Erwartung.
- Ablösungsvermerke in `fix_1948_s4_nowcast_sms_zielbild.md` und `rework_1467_s2_aenderungsalarm.md`, Nachtrag in ADR-0095 und die drei Format-Dokus sind im selben PR.
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0; B2-51 im Issue #1767 abgehakt.

## Known Limitations

- Ortsnummer-Schlüssel ist der Ortsname; zwei Orte gleichen Namens im selben Preset sind nicht unterscheidbar (bestehende Grenze des Änderungsalarms, hier geerbt).
- Kein Gewähr-Limit der Ortszahl je Ortsvergleich; bei sehr vielen Orten lesen SMS/Premium-SMS/Telegram-Kurzstil `+k`, nur die Telegram-Langform und E-Mail nennen alle.
- Langer Ortsname im Fallback (fehlende Position) wird auf 12 Zeichen gekappt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** kein neues ADR; Nachtrag in ADR-0095.
- **Rationale:** Entscheid 3b steht nur in Specs, nicht in einem ADR. Die Ablösung ist eine Anwendung von ADR-0095 (Kanal-Parität); ein Nachtrag hält sie dort fest, damit sie nicht still erfolgt.

## Changelog

- 2026-11-09: Initial spec created (PO-Entscheid Variante A', löst 3b aus #1948 S4 ab)
- 2026-11-09 (TDD RED): Die Beispieltexte in AC-1/2/4 zeigen die Token ohne Ende-Marker. Über den echten Radar-Versandpfad trägt jedes Token sein Ende (Spec „inklusive Ende-Marker"), dort prüfen die Tests `1:R@14:05@14:15 3:R@14:40@14:50`; die wörtliche Form ohne Ende prüfen AC-7/AC-10 über die Vorschau. Ohne Position lautet der Ersatz `Zermatt:R@13:08 Chamonix:R@13:15` (kein Leerzeichen nach dem Doppelpunkt).
