# Context: fix-1196-s1-testnetz-entrauschen

Scheibe 1 von #1196 („Sammelprojekt: Testsuite-Sanierung — deterministischer Kern 100 % grün").

## Request Summary

Der deterministische Kern-Testlauf ist rot und damit als Regressionssignal wertlos. Diese Scheibe
repariert die 23 roten Tests, die **nichts über das Produkt aussagen** (fehlende Aufzeichnungen,
veraltete Wächter-Erwartungen, fehlende Messbilder, Umgebungsabhängigkeit). Die 14 Tests, die auf
echte Produktfehler deuten, folgen in Scheibe 2 und 3.

## Messung (Grundlage, 2026-08-03 auf `7d6963ff` = origin/main)

Voller `uv run pytest` (Standardfilter: `live`/`email`/`staging` deselektiert), Lauf vollständig
bis 100 %: **39 rote Tests**. Jede rote Datei anschließend **einzeln** nachgeprüft:

- `tests/tdd/test_issue_1014_live_optin.py` (2 Tests) ist **isoliert grün** → Verschmutzung durch
  Testreihenfolge, kein Befund. Bleibt vorerst unangetastet (siehe „Risiken").
- **37 Tests sind echt rot**, in 17 Dateien.

Belege im Session-Scratchpad: `full_run.txt` (Gesamtlauf), `causes.txt` (Fehlerzeile je Datei).

### Bereits erledigt — drei offene Tickets sind gegenstandslos

Gegen `7d6963ff` gemessen (55 Tests, alle grün):

| Issue | Behauptung | Messung |
|---|---|---|
| #1454 | `test_success_status_guard` + `test_resolution_loss_guard` dauerhaft rot (Zeilennummern-Drift) | **grün** — beide Wächter führen ihre Ausnahmelisten seit `9305456e` (#1466) über `datei::funktion::ordinal`. Auch Teil B (`test_scanner_finds_every_spec_listed_finding`) besteht. |
| #1413 | `test_radar_nowcast_cache_sharing` tageszeitabhängig rot | **grün** |
| #1365 | `test_notification_service::test_scheduler_has_no_output_imports` rot | **grün** |

→ Alle drei schließen (Aufgabe dieser Scheibe, Abschnitt „Nebenarbeit").

## Umfang dieser Scheibe: 23 Tests in 8 Dateien

### Gruppe A — Aufzeichnungen fehlen (11 Tests, 1 Datei)

| Datei | Relevanz |
|---|---|
| `tests/tdd/test_dpc_bulletin_source.py` | Alle 11 Tests scheitern mit `FileNotFoundError` vor jeder Code-Logik |
| `tests/fixtures/dpc/README.md` | Dokumentiert Beschaffung beider Zips vollständig: öffentliche, auth-freie Quelle `raw.githubusercontent.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica/master/files/all/<YYYYMMDD>_<HHMM>_all.zip`, exakte Dateinamen, welche Teildateien behalten wurden und warum |
| `.gitignore:107` | `*.zip` — Ursache: die Zips wurden nie eingecheckt |

Benötigt: `20260730_1511_all.zip` → `ruhetag_20260730_1511.zip`, `20260118_1515_all.zip` →
`unwettertag_20260118_1515.zip`. Jeweils nur `*_today.dbf`, `*_tomorrow.dbf`, `Cap_<ts>.xml`
behalten (Laufzeit liest nur die DBF), neu packen. **Werte unverändert** — reine Dateiauswahl.

Auf `git ls-files` und im Hauptrepo geprüft: nur `README.md` vorhanden, die Zips existieren
nirgends. Also kein Worktree-Artefakt, sondern auf **jedem** frischen Checkout rot.

### Gruppe B — Wächter misst Veraltetes (7 Tests, 4 Dateien)

| Datei | Rot | Befund |
|---|---|---|
| `tests/tdd/test_issue_316_docs_cleanup.py` | 3 | Doku-Wächter (`# doc-compliance-test`): 11 Komponenten fehlen im Doc, Stand-Datum nicht auf 2026-05-25, `WordmarkProps` nicht dokumentiert. Das Doc ist der Doku-Drift, nicht der Test. |
| `tests/tdd/test_issue_1165_adr_index_cleanup.py` | 1 | Sucht den alten ADR-Dateinamen `0013-node-test-frontend-unit-runner.md` in `docs/**/*.md`. **Alle 5 Treffer liegen in `docs/specs/_archive/modules/issue_1165_adr_index_cleanup.md`** — der archivierten Spec genau dieses Umbaus, die den alten Namen zwangsläufig zitiert. Fehlalarm: der Scanner muss `_archive/` ausnehmen. |
| `tests/tdd/test_issue_457_email_per_recipient.py` | 2 | **Quelltext-Textprüfung** (`inspect.getsource(EmailOutput.send)` + `assert "for recipient in recipients" in src`). Verhalten ist intakt, nur verschoben: die Schleife steht heute in `_dial_and_send(..., isolate_per_recipient)`, `src/output/channels/email.py:485`/`:511`. |
| `tests/tdd/test_issue_872_threshold_ux.py` | 1 | **Quelltext-Textprüfung** (`assert "sms_threshold_thunder" in inspect.getsource(trip_report_scheduler)`, „Erwartet: Zeile ~1067"). Verhalten ist intakt, nur verschoben: der Schlüssel wird heute im geteilten Ausblick-Renderer gesetzt, `src/output/renderers/email/outlook.py:394`. |

**PO-Entscheidung 2026-08-03:** Die beiden Textprüfer werden **in echte Verhaltenstests
umgebaut**, nicht gelöscht.

### Gruppe C — Messbilder fehlen (3 Tests, 1 Datei)

| Datei | Relevanz |
|---|---|
| `tests/tdd/test_issue_586_alert_config_fidelity.py` | Erwartet drei Artefakte unter `docs/artifacts/issue-586-fidelity-gate/`: `live-alert-config.png` (Alarme-Tab @1440px von Staging), `reference-alert-config.png` (aus bindender JSX gerendert), `design-diff-K-alert-config-list.json`. Keines existiert — „Phase 6 Messung nie durchgeführt". Test rechnet den Pixel-Diff selbst (Schwelle 30, Grenze 10 %). |

Braucht **Staging-Zugriff + Playwright** — andere Arbeitsart als der Rest der Scheibe.

### Gruppe D — hängt an Uhr/Umgebung (2 Tests, 2 Dateien)

| Datei | Befund |
|---|---|
| `tests/tdd/test_issue_346_fixture_provider.py::test_ac5_timestamps_restamped_to_today` | **Ursache gemessen (s.u.):** Der Test ist veraltet, das Produkt ist korrekt. |
| `tests/tdd/test_fix_853_842_837_tooling_gates.py::TestAC2AC3ProdSelftestAncestor::test_ac3_fail_when_not_ancestor` | **Ursache gemessen (s.u.), weicht vom #1196-Kommentar ab.** |

## Analysis — eigene Messungen (2026-08-03)

### D1: `test_issue_346` — Ursache belegt, Test ist veraltet

Zwei Fehler in einem Test, beide gemessen:

**(a) Der Fixture-Pfad im Test zeigt woandershin, als die Fehlermeldung vermuten lässt.**
`REPO_ROOT = Path(__file__).resolve().parents[2]` (Zeile 20) ⇒ `FIXTURE_DIR = <repo>/fixtures/openmeteo`
— **nicht** `tests/fixtures/openmeteo`. Das Verzeichnis existiert auf Repo-Ebene und ist versioniert
(`git ls-files fixtures/openmeteo/` → `innsbruck.json`, `stubai.json`, `zillertal.json`). Kein Defekt,
nur eine Stolperstelle beim Nachstellen.

**(b) Der eigentliche Fehlschlag: Zeitzonen-Angabe.** Direkt gemessen:

```
IST : datetime.datetime(2026, 8, 3, 0, 0)                          | tzinfo = None
SOLL: datetime.datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)     | tzinfo = UTC
gleich? False        gleiche Wanduhr? True
```

Gleiche Uhrzeit, gleicher Tag — der Vergleich scheitert **allein** an der Zeitzonen-Angabe.

**Wer hat recht?** Das Produkt. `src/app/models.py:151-158` (`ForecastDataPoint.__post_init__`)
erzwingt seit **Issue #1345** die Hausnorm **„naive UTC" an der Provider-Grenze**: jeder aware
Zeitstempel wird nach UTC konvertiert und dann auf naiv gestrippt, damit `ts` provider-übergreifend
vergleichbar bleibt. `src/providers/fixture.py:110` setzt korrekt `datetime.now(timezone.utc)` —
die Norm greift danach.

⇒ **Der Test stammt aus der Zeit vor #1345.** Fix: Sollwert auf naives UTC umstellen. **Kein
Produktivcode.** Die Hausnorm wird nicht angetastet — das wäre Gate-Erosion an einer Stelle, an der
laut Speicher bereits Abstürze durch naiv/aware-Vermischung aufgetreten sind (#1465).

### D2: `test_fix_853_842_837_tooling_gates` — Ursache gemessen, #1196-Kommentar war ungenau

Der Kommentar vom 2026-07-26 sagt: „läuft per Unterprozess gegen das echte Hauptrepo, Fix:
Wegwerf-Repo, Muster in `TestAC5NoE2EFile` derselben Datei". **Zwei Punkte davon stimmen nicht:**

- `TestAC5NoE2EFile` liegt in `tests/tdd/test_prod_selftest_564.py:382` — **nicht** in dieser Datei.
- Der Test läuft **nicht** per Unterprozess; `_run_with_verified_commit` ruft `run_selftest()` direkt.

**Tatsächliche Ursache (gemessen):**

```
Signatur: run_selftest(e2e_path, workflow, scope=None, explicit_path: bool = False)
Aufruf im Test: run_selftest(e2e_path, "test-tooling-red", scope="backend")   # ohne explicit_path
REPO_DIR = /home/hem/gregor_zwanzig                                            # das echte Hauptrepo
```

Ohne `explicit_path=True` greift **nicht** der Zweig `elif explicit_path:` (der bei unpassendem
`verified_commit` deterministisch `return 1` liefert), sondern `else:` mit
`_nearest_verified_ancestor(head, REPO_DIR, REPO_DIR)`. Existiert im **Hauptrepo** ein frischer
bestandener Vorgänger, kommt `PASS` (rc 0) statt der erwarteten 1. Das Ergebnis hängt damit am
Zustand eines fremden Ordners — Zufallsrauschen, wie im Kommentar richtig erkannt.

**Fix:** `explicit_path=True` mitgeben. Eine Zeile, kein Wegwerf-Repo, kein Produktivcode. Der Test
prüft danach exakt die in `CLAUDE.md` dokumentierte Zusage: *„Ein ausdrücklich übergebener
`--e2e-path` ist maßgeblich (keine Vorgänger-Suche)."* Also **kein** Aufweichen, sondern die
Prüfung des richtigen Vertrags.

**Kein Fehlalarm bei `REPO_DIR`:** Dass es fest aufs Hauptrepo zeigt, ist laut Pfadregel #1409 für
die **geteilte Ablage** (HEAD-Ermittlung, Attestation) ausdrücklich gewollt.

### A1: Beschaffungsquelle erreichbar — verifiziert

`curl` gegen `raw.githubusercontent.com/.../files/all/20260730_1511_all.zip` →
**HTTP 200, 4 615 372 Bytes**. Die im README dokumentierte Quelle ist auth-frei und lebt. Gruppe A
ist reine Fleißarbeit, kein Risiko eines Sackgassen-Ergebnisses.

### B1/B2: Beide Textprüfer messen intaktes Verhalten an der falschen Stelle

| Test | sucht in | Verhalten liegt heute in |
|---|---|---|
| `test_issue_457` | `inspect.getsource(EmailOutput.send)` | `src/output/channels/email.py:485`/`:511` — Schleife `for recipient in recipients` mit `sendmail(from_addr, [recipient], ...)`, im Hilfsbaustein `_dial_and_send(..., isolate_per_recipient)` |
| `test_issue_872` | `inspect.getsource(trip_report_scheduler)` | `src/output/renderers/email/outlook.py:394` — `"sms_threshold_thunder": _sms.get("thunder")`, im geteilten Ausblick-Renderer (#1301) |

In beiden Fällen ist die Funktion umgezogen, nicht verschwunden. Genau das ist die Schwäche der
Quelltext-Textprüfung: sie bindet an den Ort statt an die Wirkung.

**Randnotiz für S2, nicht für diese Scheibe:** `_dial_and_send` wird mit
`isolate_per_recipient=False` (Zeile 573, 874) **und** `True` (Zeile 810) aufgerufen — die im Code
kommentierte „heutige Asymmetrie". Das ist genau der offene Befund aus **#1426**
(„Sammelversand: Ersatzweg ist alles-oder-nichts"). Beim Umbau von `test_issue_457` nicht
stillschweigend mit-„reparieren" — der Test soll den **Ist**-Vertrag beweisen, die Asymmetrie
gehört in #1426.

### B3: Für den Umbau existiert bereits ein Muster — und für #457 sogar der fertige Test

`tests/tdd/test_mail_transport_dial_behaviour.py` (aus #1412 S3a) ist der Referenz-Nachweis am
Versandrand: **echte Attrappe statt Mock**, zeichnet jeden Schritt in Reihenfolge auf, kann gezielt
ablehnen, baut keine Verbindung auf und verschickt keine Mail. Der Dateikopf nennt zwei weitere
Vorbilder (`test_telegram_test_mode_guard.py:278-303`, `test_mail_recipient_parity.py:185-194`).

**Entscheidend:** `test_ac2_primaerweg_stellt_trotz_einer_ablehnung_an_die_uebrigen_zu`
(Zeile 192-210) prüft bereits verhaltensbasiert *„der Primärweg versucht jeden Empfänger einzeln"* —
**exakt die Aussage, die die zwei Quelltext-Prüfungen in `test_issue_457` treffen wollen.**

⇒ Ein Umbau von `test_issue_457` erzeugt eine **Dublette**. Löschen verliert hier keine Abdeckung.

**PO-Entscheidung 2026-08-03 (nach Vorlage des Belegs):** Die zwei Textprüfungen in
`test_issue_457` werden **gelöscht**; im vorhandenen Verhaltenstest
(`test_mail_transport_dial_behaviour.py`, bei `test_ac2_…`) wird ein Zeilenverweis ergänzt, dass er
die Abdeckung von #457 mitträgt. Die frühere Vorgabe „umbauen statt löschen" gilt damit **nur noch
für #872**, wo eine echte Lücke besteht.

**Bei #872 liegt es anders — dort ist eine echte Lücke:**
`test_shared_outlook_renderer.py:260` prüft nur den **Negativfall**
(`"sms_threshold_thunder" not in row2`, wenn die Schwelle `None` ist). Dass eine **gesetzte**
Gewitterschwelle tatsächlich in der Zeile ankommt, prüft **kein einziger Test**
(`grep -rn "sms_threshold_thunder" tests/` → nur die Negativzeile und der Textprüfer selbst).
⇒ Der Umbau von `test_issue_872` schließt eine echte Lücke und ist zu machen.

### E→B: `test_shared_outlook_renderer` ist KEIN Produktfehler — Einordnung korrigiert

In der ersten Sichtung als Gruppe E („vermutlich Produktfehler") geführt. **Falsch.** Gemessen:

```
tests/tdd/test_shared_outlook_renderer.py:249
  assert all(isinstance(hv, HourlyValue) for hv in row["hourly_gust"])   → False
```

Zur Laufzeit liefert `build_outlook_row` sehr wohl `HourlyValue`-Objekte:
`(HourlyValue(hour=16, value=42.0), HourlyValue(hour=17, value=38.0))`. Der Test scheitert, weil
**dieselbe Klasse unter zwei Importpfaden geladen** wird:

```
Test     (Zeile 224): from src.output.tokens.dto import HourlyValue   → <class 'src.output.tokens.dto.HourlyValue'>
Renderer (outlook.py:338): from output.tokens.dto import HourlyValue  → <class 'output.tokens.dto.HourlyValue'>
identisch? False
```

Ursache ist `pytest.ini` → `pythonpath = ["src", "."]`: beide Präfixe lösen auf, Python legt zwei
getrennte Klassenobjekte an, `isinstance` schlägt über die Grenze hinweg immer fehl.

**Fix:** Im Test den `src.`-Präfix entfernen (Produktpfad benutzen). **Kein Produktivcode.**

**Strukturelle Gefahr, größer als dieser eine Test:** Jede `isinstance`-Prüfung über diese Grenze
scheitert still. Als Befund melden (Sammelstelle #1199 oder eigenes Issue — Kategorie „fälschlich
blockierendes Gate"), nicht in dieser Scheibe lösen.

⇒ Dieser Test wandert **in** Scheibe 1 (Gruppe B). Gruppe E schrumpft von 14 auf 13.

## Nicht in dieser Scheibe (Gruppe E, 14 Tests) — folgt in S2/S3

| Bereich | Tests | Kurz |
|---|---|---|
| SMS-Falschentwarnung | 5 | `segments_have_gap()` kennt `night_weather` nicht → bei Datenlücke steht `-` („nichts los") statt `?` („unbekannt"). Fix-Ort: `src/output/renderers/day_window.py`. |
| Versand meldet Erfolg ohne Wirkung | 2 | `test_trip_report_test_send_past_stage_clamp`: `sent`/200 statt `no_weather`/422 |
| Sammelversand schickt null | 3 | `test_compare_dispatch_failed_tally` (2), `test_telegram_test_mode_guard` (1) |
| Ortsvergleich-Prüfer | 1 | `test_compare_vergleich_cutover`: `api/routers/validator.py:56` verwirft `kind==vergleich` — unfertige Arbeit (S7b/AC-37), kein Defekt |
| Ausblick-Renderer | 1 | `test_shared_outlook_renderer::test_build_outlook_row_pure_function` |
| Kurzfassung | 1 | `test_compact_summary`: Temperaturbereich stimmt nicht (`'8' in '17–24°C'`) |

## Existing Patterns

- **Aufräum-Regel #1196 Nr. 3:** Ein Test über längst verändertes Verhalten wird **gelöscht**, nicht
  repariert. Hier per PO-Entscheidung überstimmt für die zwei Textprüfer (Umbau statt Löschung).
- **Test-Politik (CLAUDE.md, „Zwei Schichten"):** Dateiinhalt-Checks als Verhaltensnachweis sind
  verboten — Ausnahme nur mit `# doc-compliance-test`. `test_issue_316` und `test_issue_1165`
  tragen diesen Marker zu Recht (sie prüfen Doku, nicht Verhalten). `test_issue_457` und
  `test_issue_872` tragen ihn **nicht** und verstoßen gegen die Regel.
- **Wegwerf-Repo statt Hauptrepo:** `TestAC5NoE2EFile` in `test_fix_853_842_837_tooling_gates.py`
  zeigt das Muster bereits (mit #1382 umgestellt).
- **Pfadregel #1409:** Prüfling relativ zur Testdatei auflösen (`Path(__file__).resolve().parents[2]`),
  nie über den festen Hauptrepo-Pfad. Durchgesetzt via `tests/tdd/test_repo_path_hardcoding_ratchet.py`.

## Dependencies

- **Upstream:** `src/services/official_alerts/dpc.py` (liest die DPC-Zips), `src/providers/fixture.py`
  (Zeitstempel-Verankerung), `.claude/hooks/prod_selftest.py` (Selbsttest-Prüfling)
- **Downstream:** kein Produktivcode hängt an diesen Tests — sie sind das Netz, nicht das Produkt.
  Ausnahme: die zwei Umbauten (Gruppe B) berühren beim Neuschreiben `src/output/channels/email.py`
  und `src/output/renderers/email/outlook.py` **lesend**, nicht ändernd.

## Existing Specs

- `docs/specs/modules/fix_1409b_repo_path_ratchet.md` — Pfadregel + Known Limitations
- `docs/reference/mail_validators.md` — Mail-Gates (relevant, falls der #457-Umbau eine Mail baut)
- `tests/fixtures/dpc/README.md` — vollständige Beschaffungsanleitung Gruppe A

## Risks & Considerations

1. **Externe Beschaffung (Gruppe A):** Die Quelle ist ein öffentliches GitHub-Archiv. Bleibt der
   Abruf erfolglos, ist der Rückfall ein Erzeugungs-Skript plus `skipif` auf Vorhandensein — aber
   als **übersprungen**, nie als Fehlschlag, damit der nächste nicht in dieselbe Falle läuft.
2. **`.gitignore`-Ausnahme:** `!tests/fixtures/dpc/*.zip` nach Zeile 107. Nur die neu gepackten
   Auswahl-Zips (klein), nie die 4,6-MB-Originale.
3. **Gate-Erosion vermeiden:** Kein Wächter wird aufgeweicht, keine Schwelle angehoben. Beim
   #1165-Fix wird der Scanner **enger** (Archiv aus), nicht die Erwartung lockerer.
4. **Gruppe C braucht Staging:** Screenshot-Erfassung kostet Zeit und Staging-Verfügbarkeit. Falls
   Staging klemmt, wandert C in eine eigene Scheibe — der Rest bleibt lieferbar.
5. **Suite-Verschmutzung (`test_issue_1014_live_optin`):** Isoliert grün, im Gesamtlauf rot. Ursache
   ungeklärt. Nicht Teil dieser Scheibe; als Befund an #1196.
6. **Parallelsitzungen (gemessen 2026-08-03):** `intake-1394` baut #1457 (`src/providers/*`),
   `intake-1465` baut #1450 (`src/output/tokens/*`, `sms_trip.py`). **Keine Überschneidung mit
   dieser Scheibe.** Überschneidung entstünde erst in S3 (SMS-Vergleichsbilder) — deshalb liegt
   SMS bewusst am Ende.
7. **Zeilen-Obergrenze:** 250 pro Workflow. Gruppe A ist fast reine Datenbeschaffung, B/D sind
   Testumbauten. Falls die zwei Verhaltenstest-Neubauten (Gruppe B) den Rahmen sprengen, wird das
   dem PO vorgelegt — kein stiller Override.
