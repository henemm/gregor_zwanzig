---
entity_id: feat_3102_phase3g_abschluss
type: feature
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: feat-3102-phase3g-abschluss
tags: [einstellung-gleich-mail, epic-3058, abschluss, tests, doku]
---

# Einstellung = Mail, Phase 3g: Abschluss (Issue #3102, Epic #3058)

## Approval

- [ ] Approved

## Purpose

Schliesst Phase 3 des Epics #3058 ab. Die drei im Issue genannten Teile (Migration, Orakel-Loeschung, Import-Sperre) sind bereits geliefert; offen sind nur fuenf falsch modellierte `offen_feature`-Faelle "P7 global nachtraeglich", der Doku-Nachzug und der Nachweis, dass keine Altfelder mehr in den Bestandsdaten stehen. Es gibt keine Aenderung am Produktionscode.

## Source

- **File:** `tests/tdd/test_einstellung_gleich_mail_fallliste.py` (Waechter), `tests/tdd/test_einstellung_gleich_mail_trip.py`, `tests/tdd/test_einstellung_gleich_mail_orte.py`
- **Identifier:** neuer Waechtertest "kein Phase-3-Verweis in offen_feature"; Helfer `_p7_faelle` (Trip) und das P7-Pendant im Orte-Test

> **Schicht-Hinweis:** Betroffen sind ausschliesslich Python-Tests, JSON-Fixtures und Doku (`tests/`, `docs/`). Kein Frontend, keine Go-API, kein Python-Core-Code (`src/`, `api/`).

> **Querschnitts-Pruefpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Beide Seiten (Trip und Orte) werden spiegelbildlich im selben Muster angepasst; kein neuer Baustein, keine neue Komponente.
> - **Mandantentrennung:** Die P7-Tests laufen mit frischen Testprofilen, nie mit `"default"`. Es werden keine produktiven Nutzerdaten bewegt; der Nachzaehllauf ist rein lesend.
> - **Kanaele:** Der Pruefkatalog laeuft fuer alle vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) und muss gruen sein. Der Mail-Inhalt selbst aendert sich nicht.

## Bereits erfuellt (Beleg, wird nicht erneut umgesetzt)

| Teil laut Issue | Stand | Beleg |
|---|---|---|
| (a) Migration der Bestandsdaten (Read-Modify-Write mit Merge, Pre-Snapshot) | erledigt durch #3157 und #3351 | `scripts/migrate_3277_altfelder.py` (`--nachzaehlen`), Spec `feat_3351_altfelder_datenlauf.md`, ADR-0124 Folgepflichten |
| (b) Differenztest-Orakel und Lese-Adapter loeschen | erledigt; die Orakel-Tests aus feat_3096 existieren nicht mehr, der Resolver liest nur `placements` | `src/services/channel_list_resolver.py`, `src/services/placements.py`; `placements_aus_grundauswahl` ist Anlage-Vorbelegung, kein Altfeld-Leser |
| (c) Import-Sperre gegen Rueckkehr der Altfunktionen | erledigt durch #3237 und #3277 | `tests/test_altpfad_import_sperre.py`, `tests/test_altfeld_namen_sperre.py` |

## Estimated Scope

- **LoC:** ca. +120 bis +150 Tests/Fixtures (Schritt 1), ca. +30 bis +40 Doku-Zeilen (Schritt 2)
- **Files:** Schritt 1 (`test:`-Commit): 5 Test-/Fixture-Dateien, kein Produktionscode. Schritt 2 (eigener `docs:`-Commit, reine Doku, je Datei ein bis drei Zeilen Nachtrag): ADR-0121, ADR-0124, 8 Specs. Die Datei-Grenze von 4–5 gilt je Code-Änderung; der Doku-Nachzug ist bewusst getrennt, damit jeder Commit für sich prüfbar bleibt.
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0124 Nr. 5 | ADR | Fachliche Regel: fehlende Zeile in der gespeicherten Tabelle = angehakt, "überall an" |
| `src/services/placements.py` (`_ordered_rows`, `_cell`) | module | Verhalten, das die neuen Tests beweisen (unveraendert) |
| `tests/helpers/tabelle_aus_wunsch.py` | test helper | Aufbau gespeicherter Tabellen im Tabellenformat |
| `tests/tdd/_einstellung_gleich_mail_trip_fixtures.py`, `tests/helpers/einstellung_gleich_mail_orte.py` | test helper | Mailversand der Trip-/Orte-Szenarien |
| `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte,editor}.json` | fixture | Falllisten mit Statuswerten und Schema-Regeln |
| `scripts/migrate_3277_altfelder.py` | script | Nachzaehlung der Altfelder (`--nachzaehlen`, lesend) |
| #3368 | Issue (OPEN) | Bleibt ausserhalb; Fall `D-trip_vorlage-reihenfolge-frontend` ist nicht Phase 3 |

## Implementation Details

1. **RED-Waechter** in `test_einstellung_gleich_mail_fallliste.py`: laeuft ueber alle echten Falllisten und schlaegt fehl, wenn ein Fall mit Status `offen_feature` Phase 3 referenziert (`#3058`, `#3065`, `#3096` bis `#3102`, "Phase 3", "ADR zu ADR-0050"). Ein synthetischer Selbsttest belegt, dass der Waechter bei einem solchen Fall wirklich rot wird. Der Fall #3368 (Editor) bleibt erlaubt.
2. **P7 neu modelliert** (Trip und Orte): Die gespeicherte Tabelle wird aus der ALTEN Grundauswahl ohne `uv_index` gebaut. Danach folgt ein Vorbedingungs-Assert (in der gespeicherten Tabelle gibt es fuer `uv_index` keine Zeile). Erst dann wird `uv_index` zur Grundauswahl hinzugefuegt und die echte Mail gesendet. Erwartung: `uv_index` erscheint in Trip Stundentabelle und Trip Ausblick sowie in Orte Vergleichstabelle, Stundenverlauf und Ausblick. Der Orte-Ausblick wird im Abendbriefing geprueft, weil `outlook_reports` standardmaessig auf Abend steht. Die xfail-Markierung entfaellt; die Testprofile sind frisch.
3. **Fixtures:** Die fuenf Faelle (`trip-p7--global_nachtraeglich-trip_{stundentabelle,ausblick}--html`, `O-p7--global_nachtraeglich-orte_{vergleichstabelle,stundenverlauf,ausblick}--html`) wechseln von `offen_feature` auf `gruen`, mit Verweis auf ADR-0124 Nr. 5. Die Schema-Regeln der Fallliste (Status-Allowlist, Verweis-Regel) bleiben eingehalten.
4. **Doku (eigener `docs:`-Commit):** ADR-0121 Nachtrag (Nr. 7 und 8 eingeloest durch #3157/#3351/#3237/#3277); ADR-0124 Zeile 58 Folgepflicht als erledigt; in den Specs feat_3096, 3097, 3098, 3099, 3059, 3122, 3277 und 3351 werden Verweise "bis #3102" als erledigt markiert.
5. **Deploy-Nachweis:** `scripts/migrate_3277_altfelder.py --nachzaehlen` (lesend) auf Staging und Prod; die Zaehlung "0 uebrig" kommt in den Abschlusskommentar von #3102. Danach wird Epic #3058 geprueft und geschlossen.

## Expected Behavior

- **Input:** Gespeicherte Tabelle ohne Zeile fuer `uv_index`; `uv_index` wird spaeter in die Grundauswahl aufgenommen.
- **Output:** Die naechste echte Mail zeigt `uv_index` an allen Stellen, an denen die Metrik angeboten wird (Trip: Stundentabelle, Ausblick; Orte: Vergleichstabelle, Stundenverlauf, Ausblick).
- **Side effects:** Keine Produktionscode-Aenderung, keine Datenmigration, keine neue Mail-Ausgabe. Der Mail-Validator und das Renderer-Gate sind nicht betroffen.

## Acceptance Criteria

- **AC-1:** Given die echten Falllisten enthalten keinen `offen_feature`-Fall mit Phase-3-Verweis / When der neue Waechtertest laeuft / Then ist er gruen, und sein synthetischer Selbsttest wird rot, sobald ein `offen_feature`-Fall auf #3058 oder "Phase 3" verweist.
  - Test: Waechter in `test_einstellung_gleich_mail_fallliste.py` plus synthetische Fallliste mit Phase-3-Verweis; der Waechter lehnt sie ab.

- **AC-2:** Given ein Trip mit gespeicherter Tabelle ohne Zeile fuer `uv_index` / When `uv_index` nachtraeglich in die Grundauswahl aufgenommen und die echte Trip-Mail gesendet wird / Then zeigt die Mail `uv_index` in der Stundentabelle und im Ausblick.
  - Test: P7-Tests in `test_einstellung_gleich_mail_trip.py` ohne xfail, Mail-Inhalt aus Nutzersicht geprueft, frisches Testprofil (nicht "default").

- **AC-3:** Given ein Ortsvergleich mit gespeicherter Tabelle ohne Zeile fuer `uv_index` / When `uv_index` nachtraeglich in die Grundauswahl aufgenommen und die echte Orte-Mail gesendet wird (Ausblick im Abendbriefing) / Then zeigt die Mail `uv_index` in Vergleichstabelle, Stundenverlauf und Ausblick.
  - Test: P7-Tests in `test_einstellung_gleich_mail_orte.py` ohne xfail, drei Listen geprueft, frisches Testprofil.

- **AC-4:** Given ein P7-Test, dessen gespeicherte Tabelle faelschlich bereits eine Zeile fuer `uv_index` enthaelt / When der Test laeuft / Then schlaegt er an der Vorbedingung fehl und wird nicht gruen, weil die Mail "zufaellig" `uv_index` zeigt.
  - Test: Vorbedingungs-Assert (keine Zeile fuer `uv_index` vor dem Nachtragen) in Trip und Orte; ein Negativ-Lauf mit einer Tabelle, die `uv_index` enthaelt, wird abgelehnt.

- **AC-5:** Given die Falllisten sind umgestellt / When der Pruefkatalog fuer alle vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) laeuft / Then sind alle Faelle gruen ohne xfail aus Phase 3, die fuenf P7-Faelle stehen auf `gruen` mit Verweis auf ADR-0124 Nr. 5, und der Fall `D-trip_vorlage-reihenfolge-frontend` bleibt `offen_feature` mit Verweis auf #3368.
  - Test: Lauf von `test_einstellung_gleich_mail_{trip,orte,fallliste,validatoren}.py`: 0 xfail aus Phase 3, Fallliste-Schema-Pruefung gruen.

- **AC-6:** Given Import-Sperre und Altfeld-Namen-Sperre bestehen bereits / When beide Sperrtests laufen / Then sind sie gruen und unveraendert, und eine Rueckkehr gelöschter Altfunktionen oder Altfeld-Namen wuerde sie rot machen (Beleg fuer Teil (c)).
  - Test: Lauf von `tests/test_altpfad_import_sperre.py` und `tests/test_altfeld_namen_sperre.py` ohne Aenderung an diesen Dateien (inklusive ihrer Selbsttests).

- **AC-7:** Given die Migration aus #3157/#3351 ist ausgefuehrt / When `scripts/migrate_3277_altfelder.py --nachzaehlen` lesend gegen Staging und Prod laeuft / Then meldet es 0 verbleibende Altfelder, und die Zahl steht im Abschlusskommentar von #3102 (Beleg fuer Teil (a)).
  - Test: Nachzaehllauf auf beiden Umgebungen, Exit 0 und Zaehlstand 0; es werden keine Daten veraendert.

- **AC-8:** Given ADR-0121, ADR-0124 und die Specs feat_3096/3097/3098/3099/3059/3122/3277/3351 / When ein Leser nach offener Arbeit fuer #3102 sucht / Then ist jede Stelle, die Arbeit auf "bis #3102" verschiebt, als erledigt markiert und ADR-0121 verweist auf #3157/#3351/#3237/#3277.
  - Test: Doku-Pruefung per Suche ueber die genannten Dokumente; als `# doc-compliance-test` gekennzeichnet, weil nur Doku-Inhalt betroffen ist.

## Scope

- **Drin:** RED-Wächter Fallliste (AC-1), P7 neu auf gespeicherter Tabelle für Trip und Orte (AC-2 bis AC-4), Status der fünf Fälle (AC-5), Beleg der bestehenden Sperren (AC-6), Nachzählung Staging/Prod (AC-7), Doku-Nachzug (AC-8).
- **Draußen:** jede Produktionscode-Änderung, jeder schreibende Datenlauf, #3368, ein Altfeld-Schreib-Wächter für Test-Fixtures.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN echte Falllisten mit fünf P7-Fällen `offen_feature` (Verweis #3047/#3065, ADR zu ADR-0050) WHEN Wächter läuft THEN rot; nach Umstellung grün; synthetischer Selbsttest mit Phase-3-Verweis immer abgelehnt, #3368-Fall erlaubt (AC-1)
- [ ] Test 2: GIVEN Trip, Tabelle aus alter Grundauswahl WHEN `uv_index` dazu und echte Mail THEN `uv_index` in Stundentabelle und Ausblick (AC-2, AC-4)
- [ ] Test 3: GIVEN Ortsvergleich, Tabelle aus alter Grundauswahl WHEN `uv_index` dazu und echte Mail (Ausblick abends) THEN `uv_index` in Vergleichstabelle, Stundenverlauf, Ausblick (AC-3, AC-4)
- [ ] Test 4: Katalog-Lauf `tests/tdd/test_einstellung_gleich_mail_{trip,orte,fallliste,validatoren}.py` plus beide Sperrtests: 0 xfail aus Phase 3 (AC-5, AC-6)

### Nachweise ohne Kern-Test

- Nachzählung `--nachzaehlen` auf Staging und Prod im Deploy (AC-7); Doku-Suche (AC-8).

## Definition of Done

- AC-1 bis AC-6 durch benannte Kern-Tests grün; der Wächter war vor der Umstellung nachweislich rot.
- Adversary mit Mutations-Gegenprobe (u. a. Tabelle doch mit `uv_index`-Zeile, Wächter-Regex entschärft) ohne offenes Finding.
- Nachzählung Staging und Prod 0, Zahl im Abschlusskommentar von #3102; Epic #3058 geprüft.
- Doku-Commit getrennt; keine Änderung an Produktionscode, Gate-Konfiguration oder Sperr-Testdateien.

## Known Limitations

- #3368 (Widerspruch zweier freigegebener Regeln zur Vorlagen-Reihenfolge) ist PO-Thema und bleibt ausdruecklich ausserhalb.
- Ein zusaetzlicher Schreib-Waechter gegen Altfelder in Test-Fixtures (Variante B) wurde verworfen: Die Fixtures beschreiben Altfelder bewusst und wuerden Fehlalarme ausloesen.
- Falls ein P7-Test wider Erwarten rot bleibt, waere doch eine Code-Aenderung im Resolver oder Renderer noetig (Renderer-Commit-Gate, Mail-Validator). Eine Probe vom 2026-11-26 zeigt, dass die Produktion P7 bereits erfuellt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue ADR
- **Rationale:** Es aendert sich keine Entscheidung. P7 ist durch ADR-0124 Nr. 5 gefallen, und ADR-0121 Nr. 7 und 8 werden nur als eingeloest nachgetragen.

## Changelog

- 2026-11-26: Initial spec created
