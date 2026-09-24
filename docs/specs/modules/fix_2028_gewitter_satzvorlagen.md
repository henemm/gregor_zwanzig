---
entity_id: fix_2028_gewitter_satzvorlagen
type: bugfix
created: 2026-09-24
updated: 2026-09-24
status: implementiert
version: "1.0"
workflow: fix-2028-gewitter-satzvorlagen
tags: [gewitter, satzvorlagen, thunder_scale, issue-2028, issue-1480]
---

# Gewitter-Satzvorlagen und Nacht-Wortliste kanonisch bündeln (#2028)

## Approval

- [ ] Approved

## Purpose

Die drei letzten geduldeten Altlasten des Gewitter-Skalen-Wächters (#1480) sanieren: Der
Trend-Weg (`_thunder_entry_from_trend_row`) und der Fetch-Weg (`_build_thunder_forecast`)
im Scheduler bauen den Gewitter-Vorschausatz je Stufe (NONE/MED/HIGH — LOW läuft seit
#2176 bereits über `thunder_low_statement_sentence`) unabhängig voneinander mit eigenen
Wort-Literalen, und `day_window.py` führt seine eigene Nacht-Adjektiv-Tabelle
(`_NIGHT_ADDENDUM_WORD`) statt eine kanonische Quelle zu lesen. Ziel ist EIN geteilter
Satzkopf-Baustein in `src/app/thunder_scale.py` plus eine kanonische Nacht-Adjektiv-Tabelle
dort, ohne den beim Nutzer sichtbaren Wortlaut zu verändern.

## Source

- **File:** `src/services/trip_report_scheduler.py`, `src/app/day_window.py`,
  `src/app/thunder_scale.py`
- **Identifier:** `_thunder_entry_from_trend_row`, `_build_thunder_forecast`,
  `_NIGHT_ADDENDUM_WORD` / `format_night_addendum` (bisher), neu:
  `thunder_headline_sentence`, `THUNDER_NIGHT_ADJECTIVE_DE` (Ziel)

**Schicht:** ausschließlich Python-Core, Domänenschicht (`src/app/`) und Service-Schicht
(`src/services/`). Kein Go, kein Frontend. Keine der drei Dateien steht auf der
Renderer-Commit-Gate-Dateiliste (`docs/reference/gates_und_ratschen.md`, #811 — die Liste
umfasst nur `src/output/renderers/email/*.py`,
`src/output/renderers/{trip_report,sms_trip,compact_summary}.py`,
`src/output/renderers/alert/*.py`, `src/output/channels/email.py`); das Gate greift hier
nicht.

## Estimated Scope

- **LoC:** ~+50/−45 produktiv (unter dem 250-LoC-Workflow-Limit)
- **Files:** 3 Produktivdateien geändert (`thunder_scale.py`, `trip_report_scheduler.py`,
  `day_window.py`), 2 Testdateien (`test_thunder_scale_local_copy_guard.py` geändert,
  `tests/tdd/test_thunder_headline_sentence.py` neu)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `THUNDER_LABEL_DE` (`thunder_scale.py:281`) | kanonische Quelle | liefert kein/leicht/mittel/hoch — Bezugsgröße, aber NICHT direkt für die Nacht-Adjektive nutzbar (siehe Implementation Details) |
| `thunder_low_statement_sentence()` (`thunder_scale.py:340`) | kanonische Quelle | wird vom neuen Satzkopf-Baustein für LOW unverändert delegiert aufgerufen (`("kurz", carriers)`, kein `cape_jkg`) |
| `tests/tdd/test_thunder_scale_local_copy_guard.py::ALTLASTEN` (Z. 290) | Wächter-Basislinie | muss um genau die drei hier sanierten Einträge auf eine leere Liste schrumpfen, sonst schlägt `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag` an |
| `tests/tdd/test_thunder_scale_local_copy_guard.py::_THUNDER_KWARGS["canonical_symbols"]` (Z. 130) | Whitelist kanonischer Quellen | neue `(Datei, Symbol)`-Paare für `thunder_headline_sentence` und `THUNDER_NIGHT_ADJECTIVE_DE` — nur eintragen, wenn sie tatsächlich einen Regel-Fund erzeugen, sonst meldet `test_whitelist_kanonischer_quellen_hat_keinen_leerlauf_eintrag` einen Leerlauf-Eintrag |
| `tests/tdd/test_thunder_scale_local_copy_guard.py::test_ac8_2010_2011_sechs_eintraege_sind_aus_altlasten_gestrichen` (Z. 1107) | Bestandsschutz, ANZUPASSEN | erwartet heute `erwartete_rest` mit genau den drei hier zu sanierenden Tripeln — wird auf `erwartete_rest = set()` (bzw. `ALTLASTEN == ()`) korrigiert, sobald die drei Einträge gestrichen sind |
| `test_ac12_echter_backend_baum_hat_ausser_den_drei_duldungsstufen_keinen_fund` (Z. 1055) | Wächter-Kerntest | muss nach dem Fix ohne die drei Altlasten grün bleiben und bei einer testweisen Rückdrehung (Kopie wieder einbauen) rot werden |
| `docs/specs/modules/thunder_scale_guard.md` | bindender Mechanismus | definiert Regel A (Literal-Katalog)/B (Verzweigungsketten)/C (Zahlen-Schwellen) und die drei Duldungsstufen (Whitelist / ALTLASTEN-Basislinie / Marker-Kommentar) |
| `docs/specs/modules/briefing_parity_night_thunder.md` | Bestandsschutz | verlangt Wortgleichheit von Trend-Weg und Fetch-Weg im Nacht-Halbsatz — bleibt durch die Zusammenführung unverändert erfüllt |
| Regressionsnetz (siehe Implementation Details, ca. 20 Testdateien) | Bestandsschutz | prüft heute den Satzwortlaut aller vier Stufen in Mail/Telegram/SMS/Vorschau — darf ohne eigene Änderung grün bleiben |

## Implementation Details

Neuer Baustein `thunder_headline_sentence(level, when, carriers)` in `thunder_scale.py`
baut den Satzkopf für NONE/LOW/MED/HIGH:

| Stufe | Satzkopf mit gesetztem `when` | Satzkopf ohne `when` (`when is None`) |
|---|---|---|
| NONE | `Kein Gewitter erwartet` | (kein `when`-Zweig, `when` wird ignoriert) |
| LOW | Delegiert an `thunder_low_statement_sentence("kurz", carriers)`, danach ` ab {when}` angehängt | nur der delegierte Kern, ohne Anhang |
| MED | `Gewitter möglich ab {when}` | `Gewitter möglich` |
| HIGH | `Starkes Gewitter erwartet ab {when}` | `Starkes Gewitter erwartet` |

Beide Scheduler-Funktionen ersetzen ihre if/elif-Kette durch einen Aufruf dieses
Bausteins; die `when`-Herleitung bleibt je Weg bestehen (Trend-Weg `f"{hour:02d}:00"`,
kann `None` sein; Fetch-Weg `strftime("%H:%M")`, ist im Fetch-Weg immer gesetzt — der
Fetch-Weg bekommt dadurch kein neues Verhalten). Die Anhänge-Kette (Herkunft `" · "`,
Hagel, Nacht-Halbsatz) ist bereits über geteilte Bausteine (`thunder_signal_label`,
`format_hail_note`, `format_night_addendum`) gebaut und wird nicht angefasst — es sei
denn, der Wächter meldet nach der Satzkopf-Extraktion dort selbst noch einen Regel-B-Fund
(siehe Acceptance Criteria, AC-1).

Nacht-Adjektive: neue Tabelle `THUNDER_NIGHT_ADJECTIVE_DE = {MED: "mittleres",
HIGH: "starkes"}` in `thunder_scale.py` (eigene kanonische Größe, NICHT aus
`THUNDER_LABEL_DE` abgeleitet — dort heißt HIGH „hoch", der Nacht-Halbsatz braucht aber
„starkes"; eine reine Flexion der Grundform trifft das nicht). `_NIGHT_ADDENDUM_WORD` in
`day_window.py` entfällt ersatzlos, `format_night_addendum` importiert die neue Tabelle.

## Expected Behavior

- **Input:** eine Tageszeile mit Gewitterstufe NONE/LOW/MED/HIGH, optional einer Uhrzeit
  (`when`) und einer Trägerliste (`carriers`), sowohl aus dem Trend-Weg als auch aus dem
  Fetch-Weg des Schedulers; ein Nacht-Halbsatz mit Stufe MED/HIGH.
- **Output:** Byte-identischer Wortlaut zu heute in `forecast[key]["text"]` für alle vier
  Stufen und beide Wege, sowie im Nacht-Halbsatz — konsumiert von Trip-Briefing-Mail
  (full/compact), Telegram, SMS-Umfeld und `/api/preview`. Der #1480-Wächter meldet für die
  drei hier behandelten Fundstellen keinen Fund mehr; `ALTLASTEN` ist leer.
- **Side effects:** keine — reine Konsolidierung der Satzbau-Logik, keine
  Datenmodell-Änderung, keine neuen Werte in `ThunderLevel`.

## Acceptance Criteria

- **AC-1:** Given die drei benannten Altlasten-Einträge (`day_window.py::_NIGHT_ADDENDUM_WORD`
  Regel A, `trip_report_scheduler.py::_thunder_entry_from_trend_row` Regel B,
  `trip_report_scheduler.py::_build_thunder_forecast` Regel B) sind aus dem Code entfernt /
  When der komplette Wächter-Testlauf (`tests/tdd/test_thunder_scale_local_copy_guard.py`,
  insbesondere `test_ac12_echter_backend_baum_hat_ausser_den_drei_duldungsstufen_keinen_fund`,
  `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag`,
  `test_whitelist_kanonischer_quellen_hat_keinen_leerlauf_eintrag`) läuft / Then ist er
  vollständig grün, `ALTLASTEN` ist leer. Das reine Teilen des Satzkopfs ist der Plan, keine
  Grenze: Meldet Regel B nach der Extraktion noch einen Fund in der Anhänge-Kette
  (Herkunft/Hagel/Nacht-Halbsatz), muss auch diese Stelle konsolidiert werden — dieses
  Fertig-Kriterium hat Vorrang vor der ursprünglich geplanten Scope-Grenze.
  - Test: vollständiger, benannter Lauf der drei genannten Testfunktionen plus des
    gesamten Wächter-Moduls; kein einzelner Fund mit Datei/Symbol aus den drei Altlasten
    mehr in der Fundliste.

- **AC-2:** Given der bestehende Test `test_ac8_2010_2011_sechs_eintraege_sind_aus_altlasten_gestrichen`
  erwartet heute `erwartete_rest` mit genau den drei hier zu sanierenden Tripeln als Rest
  von `ALTLASTEN` / When die drei Einträge gestrichen werden / Then wird dieser Test
  legitim auf `erwartete_rest = set()` (bzw. `ALTLASTEN == ()`) angepasst — der Ratschen-
  Mechanismus selbst (Duldungsstufe 2, `baseline`-Parameter des Scanners) bleibt bestehen
  und wird nicht entfernt, nur sein heutiger Erwartungswert war eine Momentaufnahme.
  - Test: `test_ac8_…` nach der Anpassung grün; struktureller Vergleich von `ALTLASTEN`
    vor/nach dem Fix (drei Tripel fehlen, keine neuen hinzugekommen).

- **AC-3:** Given die vier Gewitterstufen NONE/LOW/MED/HIGH, je einmal mit gesetztem
  `when` und einmal mit `when is None` (acht Fälle) / When
  `thunder_headline_sentence(level, when, carriers)` in `thunder_scale.py` aufgerufen wird
  / Then liefert sie exakt die heutigen Wortlaute: NONE stets „Kein Gewitter erwartet";
  LOW den von `thunder_low_statement_sentence("kurz", carriers)` gelieferten Satz, mit
  gesetztem `when` gefolgt von ` ab {when}`, ohne `when` ohne diesen Anhang; MED mit
  gesetztem `when` „Gewitter möglich ab {when}", ohne `when` „Gewitter möglich"; HIGH mit
  gesetztem `when` „Starkes Gewitter erwartet ab {when}", ohne `when` „Starkes Gewitter
  erwartet".
  - Test: neue Testdatei `tests/tdd/test_thunder_headline_sentence.py`, Matrix über die
    acht Fälle gegen fest verdrahtete Literal-Erwartungen (nicht durch Aufruf von
    `thunder_low_statement_sentence` berechnet — das würde die Delegation gegen sich
    selbst testen), mit einem konkreten `carriers`-Wert für LOW.

- **AC-4:** Given der Nacht-Halbsatz-Baustein `format_night_addendum()` für die Stufen
  MED und HIGH / When er nach dem Fix aufgerufen wird / Then verwendet er die neue
  kanonische Tabelle `THUNDER_NIGHT_ADJECTIVE_DE` (`{MED: "mittleres", HIGH: "starkes"}`)
  aus `thunder_scale.py` statt der bisherigen lokalen `_NIGHT_ADDENDUM_WORD` in
  `day_window.py`, und der sichtbare Wortlaut des Nacht-Halbsatzes bleibt für beide Stufen
  byte-identisch zu heute.
  - Test: `test_thunder_headline_sentence.py` prüft zusätzlich `THUNDER_NIGHT_ADJECTIVE_DE[MED]
  == "mittleres"` und `[HIGH] == "starkes"`; `_NIGHT_ADDENDUM_WORD` existiert in
    `day_window.py` nicht mehr (Attribut-Fehler bei Zugriff).

- **AC-5:** Given das bestehende Regressionsnetz für den Gewitter-Wortlaut (u. a.
  `tests/unit/test_thunder_night_addendum.py`,
  `tests/unit/test_thunder_night_addendum_parity.py`,
  `tests/unit/test_thunder_forecast_day_window.py`,
  `tests/unit/test_preview_night_block.py`,
  `tests/unit/test_trip_report_formatter_v2.py`,
  `tests/tdd/test_briefing_parity_night_thunder.py`,
  `tests/tdd/test_thunder_forecast_low_level.py`,
  `tests/tdd/test_thunder_low_no_event_claim.py`,
  `tests/tdd/test_thunder_origin_trip.py`, `tests/tdd/test_thunder_origin_preview.py`,
  `tests/tdd/test_hagel_im_nachthalbsatz.py`,
  `tests/tdd/test_hail_multiday_preview_and_sms_tomorrow.py`,
  `tests/tdd/test_preview_thunder_matches_sent.py`,
  `tests/tdd/test_issue_721_email_outlook.py`, `tests/tdd/test_issue_790_briefing_simplify.py`,
  `tests/tdd/test_issue_640_trend_threshold_times.py`,
  `tests/tdd/test_issue_816_alert_deviation.py`, `tests/tdd/test_bug_874_th_plus_sms.py`,
  `tests/tdd/test_th_plus_follows_thunder_metric_and_gap.py`, Fixture
  `tests/fixtures/trip_outlook_reference/telegram_bubble.txt` / When diese Suiten nach der
  Konsolidierung laufen / Then bleiben sie vollständig grün, **ohne dass eine dieser
  Testdateien selbst editiert werden muss** — muss eine davon geändert werden, damit sie
  wieder grün wird, ist das ein Wortlaut-Drift-Befund, kein akzeptierter Kollateralschaden.
  - Test: benannter Lauf aller aufgeführten Dateien vor und nach dem Fix, Diff der
    Testdateien selbst auf Null geprüft.

- **AC-6:** Given eine der drei sanierten Fundstellen wird testweise durch ihre
  ursprüngliche lokale Stufen-Literal-Kette ersetzt (String-Ersetzung mit externer
  Sicherungskopie, kein `git checkout`/`stash`/`reset`) / When der Wächter-Testlauf danach
  erneut ausgeführt wird / Then wird mindestens einer der Tests
  `test_ac12_echter_backend_baum_hat_ausser_den_drei_duldungsstufen_keinen_fund` oder
  `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag` (Zweig „unbekannt" bei leerer
  `ALTLASTEN`) rot — als Beleg, dass der Wächter die Rückdrehung tatsächlich fängt und
  nicht nur zufällig grün war.
  - Test: für jede der drei Stellen einzeln eine Mutations-Gegenprobe fahren, jeweils den
    konkret rot gewordenen Test benennen, danach die Sicherungskopie zurückspielen.

## Known Limitations

- **`_trend_note` (`trip_report_scheduler.py` ~Z. 215–231, `notes.append("Gewitter
  möglich")`) ist NICHT Teil dieser Arbeit.** Der Wächter sieht diese Stelle nicht (Expr-Call
  statt Assign), und sie hat andere Semantik (Kurzhinweis ohne Uhrzeit, MED+HIGH
  zusammengefasst) → Sammel-Eintrag #1199.
- **B2-63 (Go `internal/model/forecast.go` kennt `ThunderLow` nicht) gehört zu #2019** (OPEN,
  Rückbau Forecast-Endpunkt), nicht zu diesem Workflow.
- **B2-65 (Korridor-Editor-Kommentare „3-Stufen-Band")** ist keine Vorschausatz-Frage — der
  PO hat das 3-Stufen-Band am 2026-07-12 entschieden — und bleibt außerhalb dieses
  Workflows.
- **Kein „Trend vs. Fetch mit gleichem Input"-Vergleichstest.** Beide Wege erhalten in der
  Praxis verschiedene `when`-Formate aus verschiedenen Datenquellen; ein Test, der beide
  Wege künstlich mit identischem Input füttert, würde ein Szenario prüfen, das im Betrieb
  nicht vorkommt (Mock-Theater). Die Parität der beiden Wege ist durch die gemeinsame
  Funktion strukturell gegeben, nicht durch einen eigenen Test bewiesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Arbeit bewegt sich innerhalb ADR-0025 (Gewitter-Skala lebt zentral
  in der Domänenschicht, gilt für alle Briefing-Kanäle) und saniert die letzten drei durch
  den #1480-Wächter (`thunder_scale_guard.md`) benannten, bekannten Kopien. Die im
  Ticket-Kommentar als vorab zu klärende Produktfrage markierte Nachtwort-Form ist mit
  dieser Spec entschieden (eigene kanonische Tabelle `THUNDER_NIGHT_ADJECTIVE_DE`, da
  „hoch" ≠ „starkes" keine reine Flexion ist) und erfordert keine gesonderte
  PO-Rückfrage — der Wortlaut beim Nutzer ändert sich nicht.

## Changelog

- 2026-09-24: Initial spec created (Issue #2028).
