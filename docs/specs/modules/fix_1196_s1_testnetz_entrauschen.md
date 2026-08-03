---
entity_id: fix_1196_s1_testnetz_entrauschen
type: bugfix
created: 2026-08-03
updated: 2026-08-03
status: draft
version: "1.2"
tags: [testing, tdd, cleanup, issue-1196]
---

<!-- Issue #1196 Scheibe 1 — Testsuite-Sanierung, deterministischer Kern -->

# Fix #1196 Scheibe 1 — Testnetz entrauschen

## Approval

- [ ] Approved

## Purpose

21 rote Kern-Tests reparieren, die **nichts über das Produkt aussagen** (fehlende
Aufzeichnungen, veraltete Wächter-Erwartungen, ein Doku-Rückstand, eine stale
Textprüfung nach einer Umbenennung, ein fest verdrahtetes Datum, ein
Import-Präfix-Fehler). Kein Produktivcode wird geändert — für den einzig in
Frage kommenden Fall (#872) ist gemessen, dass die Lücke rein im Test liegt
(AC-7). Nach dieser Scheibe ist der deterministische `uv run pytest`-Kern um
diese 21 Fehlschläge ärmer und wieder als Regressionssignal brauchbar.

Drei weitere Tests (Gruppe „#586 Design-Fidelity") bleiben **bewusst außerhalb**
dieser Spec — Begründung in Implementation Details/Known Limitations.

## Source

- **File:** `tests/tdd/test_dpc_bulletin_source.py` (11 Tests — Gruppe A)
- **File:** `tests/fixtures/dpc/*.zip` (NEU, 4 Dateien — s. AC-1/AC-2)
- **File:** `.gitignore` (Zeile 107 `*.zip` — Ausnahme ergänzen)
- **File:** `docs/reference/frontend_components.md` (Doku-Update — Gruppe B1)
- **File:** `tests/tdd/test_issue_316_docs_cleanup.py` (Code-Änderung: `NAMED_COMPONENTS`-Liste + Datumsvergleich — Gruppe B1)
- **File:** `tests/tdd/test_issue_1165_adr_index_cleanup.py:82` (ein Pfad-Literal korrigieren)
- **File:** `tests/tdd/test_issue_457_email_per_recipient.py:25-66` (zwei Tests löschen)
- **File:** `tests/tdd/test_mail_transport_dial_behaviour.py:192` (Kommentar-Querverweis ergänzen)
- **File:** `tests/tdd/test_issue_872_threshold_ux.py:39-54` (Test umbauen)
- **File:** `tests/tdd/test_shared_outlook_renderer.py:224` (Import-Präfix entfernen)
- **File:** `tests/tdd/test_issue_346_fixture_provider.py:92-105` (Sollwert naives UTC)
- **File:** `tests/tdd/conftest.py` (NEU-Abschnitt: `_load_prod_selftest_module`, `_head_sha`, `_make_e2e_verified`, `_init_evidence_free_repo`, `PROD_SELFTEST`/`REPO_DIR` — aus `test_prod_selftest_564.py` ausgelagerter, geteilter Ort)
- **File:** `tests/tdd/test_fix_853_842_837_tooling_gates.py:98-126` (`test_ac3_fail_when_not_ancestor` bleibt hier, importiert die Helfer aus `tests/tdd/conftest.py`)
- **File:** `tests/tdd/test_prod_selftest_564.py:40-51` (importiert dieselben Helfer aus `tests/tdd/conftest.py` statt sie selbst zu definieren — sonst unverändert, bleibt bei 23 Tests)
- **Nicht Teil dieser Spec:** `tests/tdd/test_issue_586_alert_config_fidelity.py` (3 Tests, Begründung s.u.)

> **Schicht-Hinweis:** Diese Scheibe berührt ausschließlich Testcode
> (`tests/`), Test-Fixtures (`tests/fixtures/dpc/`) und ein Referenz-Doc
> (`docs/reference/`). Kein Go-, kein SvelteKit-, kein FastAPI-Produktivcode
> wird verändert.

## Estimated Scope

- **LoC:** ~160-210 Zeilen geänderter Testcode (Details je Gruppe unten);
  Binär-Fixtures (`*.zip`) und `docs/*.md`/`.gitignore` zählen laut
  Regel-Budget nicht mit. **Passt** unter das 250-Zeilen-Limit — größte
  Posten sind der `#316`-Datumsvergleich (neue Parse-Logik), der `#872`-Umbau
  und die conftest-Auslagerung für `#853` (Helfer-Verschiebung
  `test_prod_selftest_564.py` → `conftest.py`, Re-Import an zwei Stellen).
- **Files:** 10 Testdateien (davon `tests/tdd/conftest.py` als Träger der
  ausgelagerten Helfer neu betroffen) + 1 Doku-Datei + 1 `.gitignore`-Zeile +
  4 neue Binär-Fixtures.
- **Effort:** medium (Gruppe A ist Fleißarbeit + Recherche, Gruppe B/D
  enthalten echte Testumbauten; D3/#853 zusätzlich eine bereits einmal
  korrigierte Refactoring-Entscheidung, s. Implementation Details).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/dpc.py:86-106` (`_parse_dbf`) | Modul | liest die DBF zur Laufzeit per `struct.unpack` — Fixture-Feldschema muss exakt passen (Grundlage AC-2) |
| `tests/fixtures/dpc/README.md` | Doku | dokumentiert Beschaffung der echten Zips + Bauplan der synthetischen Fail-soft-Zips; bereits vollständig, keine Änderung nötig |
| `src/services/official_alerts/__init__.py:36-42` | Modul | Registrierungsreihenfolge — Grundlage für AC-3 |
| `src/services/official_alerts/meteoalarm_feed.py:274-286` | Modul | `MeteoAlarmFeedSource.name == "meteoalarm_feed"` (Issue #1445-Umbenennung) — Grundlage für AC-3 |
| `docs/reference/frontend_components.md` | Doku | Ziel-Dokument für AC-4 |
| `tests/tdd/test_mail_transport_dial_behaviour.py:192-217` | Test (#1412 S3a) | trägt nach AC-6 die Abdeckung von #457 mit |
| `src/output/renderers/email/outlook.py:387-396` | Modul | `build_outlook_row(..., sms_thresholds=...)` — Zielort für AC-7, **liest, ändert nicht** |
| `tests/tdd/conftest.py` (`_load_prod_selftest_module`, `_head_sha`, `_make_e2e_verified`, `_init_evidence_free_repo`) | Test-Helfer, geteilter Ort | Wegwerf-Repo-Muster — Grundlage für AC-10, importiert von BEIDEN `test_fix_853_842_837_tooling_gates.py` UND `test_prod_selftest_564.py` |
| `tests/tdd/test_prod_selftest_564.py:26` (`pytestmark = pytest.mark.staging`) | Test-Modul-Marker | **Grund, warum der Test NICHT dorthin verschoben werden darf** (`pytest.ini` `addopts` deselektiert `staging` im Standardlauf) — zentrale Erkenntnis für AC-10 |
| `.claude/hooks/prod_selftest.py:668-746` (`run_selftest`) | Skript | `REPO_DIR`-Konstante (Z.56) steuert sowohl Ancestor-Suche (Z.736) als auch Report-Pfad (Z.682) — beides wird durch `monkeypatch.setattr(mod, "REPO_DIR", root)` isoliert |

## Implementation Details

### Gruppe A — DPC-Fixtures (AC-1, AC-2, AC-3) — 11 Tests in `test_dpc_bulletin_source.py`

**Vier Zips nötig, nicht zwei (gemessen):** Neben den zwei echten Aufzeichnungen
(`ruhetag_20260730_1511.zip`, `unwettertag_20260118_1515.zip`) fehlen auch die
zwei *synthetischen* Fail-soft-Zips (`synthetic_unknown_stufe_pattern.zip`,
Zeile 365; `synthetic_unknown_zone_code.zip`, Zeile 389). `tests/fixtures/dpc/README.md`
(ab Zeile 63) beschreibt beide als bereits erzeugt, per `Glob` bestätigt aber:
`tests/fixtures/dpc/` enthält **nur die README** — keines der vier Zips liegt
vor. Ohne die zwei synthetischen bleiben AC-5b/AC-5c weiterhin rot.

Die zwei synthetischen Zips müssen mit dem exakten dBase-III-Feldschema
gebaut werden, das `_parse_dbf` (`dpc.py:86-106`, reines `struct.unpack`, keine
Bibliothek) erwartet: Felder `Zona_all`/`Nome_zona`/`Criticita`/`Idrogeo`/
`Temporali`/`Idraulico`. `synthetic_unknown_stufe_pattern.zip`: ein Datensatz
für die reale Zone `Abru-A`, `Temporali` = `"Formato sconosciuto / STATO
IMPREVISTO"` (Freitext außerhalb des Musters `<Kritikalität> / ALLERTA
<FARBE>`). `synthetic_unknown_zone_code.zip`: `Temporali` =
`"Ordinaria / ALLERTA GIALLA"` bei Zonencode `"Xyz-9"` (kein Eintrag in
`dpc_zones.json`). **`pyshp`/`dbfread` sind keine Projektabhängigkeit** —
Erzeugung über ein Wegwerf-Skript (z.B. `uv run --with pyshp -- python
<scratch>.py`), das Ergebnis-DBF gegen `_parse_dbf` verifizieren (Feldnamen/
-längen exakt), bevor es ins Zip gepackt wird.

**Von den 12 Tests der Datei brauchen nur 10 eine Fixture-Datei**
(`_read_fixture_bytes(...)`): `test_ac2` (Z.137), `test_ac3` (Z.178),
`test_zwei_zonen_gleichzeitig` (Z.225), `test_stufen_abbildung_rossa` (Z.257),
`test_stufen_abbildung_arancione` (Z.279), `test_ac4_source_label` (Z.308),
`test_ac5b` (Z.355), `test_ac5c` (Z.378), `test_ac6_gewitter_ueberschneidung`
(Z.429), `test_ac7_unavailable` (Z.534). `test_ac5a_kaputtes_zip` (Z.339) baut
die kaputten Bytes inline und braucht keine Datei — geprüft gegen `dpc.py`:
`_parse_bulletin_zip` wirft bei ungültigem Zip, `warn_egress.cached_fetch`
fängt das fail-soft ab, dieser Test läuft unabhängig von den fehlenden
Fixtures.

`test_ac6_reale_paket_registrierungsreihenfolge_meteoalarm_vor_dpc` (Z.469)
liest **ebenfalls keine Fixture-Datei** — er lädt `services.official_alerts`
frisch und prüft `"meteoalarm" in names` sowie
`names.index("meteoalarm") < names.index("dpc")` (Z.495/499). Gemessen gegen
`src/services/official_alerts/__init__.py:36-42`: `MeteoAlarmSource` (die
Klasse mit `name == "meteoalarm"`) wird **seit Issue #1445 S3 nicht mehr
registriert**; registriert ist nur `MeteoAlarmFeedSource("IT")`/`("AT")`, deren
`.name`-Property `"meteoalarm_feed"` liefert (`meteoalarm_feed.py:285-286`,
country-unabhängig). Die Registrierungsreihenfolge selbst ist korrekt
(`GeoSphereWarnSource`, dann beide `MeteoAlarmFeedSource`, dann `DpcSource`) —
der Test scheitert **nicht** mit `FileNotFoundError`, sondern mit
`AssertionError`, weil er den alten Namen sucht. Das ist die 11. rote
Testfunktion der Datei und hat **nichts mit fehlenden DPC-Fixtures zu tun**.

**Umsetzung:**
1. Zwei echte Zips gemäß README beschaffen (Quelle verifiziert erreichbar),
   nur `*_today.dbf`/`*_tomorrow.dbf`/`Cap_<ts>.xml` behalten, neu packen,
   Werte unverändert.
2. Zwei synthetische Zips per Wegwerf-Skript erzeugen (Feldschema wie oben,
   exakte Werte laut README), Schema gegen `_parse_dbf` verifizieren.
3. `.gitignore`: nach Zeile 107 (`*.zip`) die Zeile `!tests/fixtures/dpc/*.zip`
   ergänzen — ausschließlich die vier kleinen Auswahl-Zips, nie die
   4,6-MB-Originale.
4. `test_ac6_reale_paket_registrierungsreihenfolge_meteoalarm_vor_dpc`:
   beide Vorkommen von `"meteoalarm"` (Z.495, Z.499) auf `"meteoalarm_feed"`
   ändern — die Testaussage (MeteoAlarm-Familie registriert sich vor DPC)
   bleibt unverändert, nur der Name folgt der #1445-Umbenennung.

### Gruppe B1 — `test_issue_316_docs_cleanup.py` (AC-4) — 3 Tests

**Drei getrennte Befunde, gemessen:**

1. `test_ac1_named_components_documented`: von den 11 in `NAMED_COMPONENTS`
   gelisteten Namen fehlen 10 komplett im Doc. Der 11., `NewLocationWizard`,
   ist selbst das Problem — `find frontend/src -iname "*NewLocationWizard*"`
   liefert **keinen Treffer**. Der Name existiert nur noch in
   `legacy_wizard_removed.test.ts` u.ä. — als Beweis, dass er **entfernt**
   wurde (Wizard-Abschaffung, CLAUDE.md „Wizards existieren nicht mehr").
   `NAMED_COMPONENTS` verlangt hier fälschlich den Nachweis einer nicht mehr
   existierenden Komponente.
2. `test_ac5_updated_date_bumped` (Z.111-116) prüft exakt den Teilstring
   `"**Updated:** 2026-05-25"`. Das Doc steht auf `2026-07-21` (Doku-Audit
   #1341, Z.3) — eine **fest verdrahtete Datumszusage**, die bei jeder
   legitimen Folge-Doku-Pflege erneut bricht.
3. `test_ac5_wordmark_props_documented`: erwartet `"WordmarkProps"` — im Doc
   kommt nur `Wordmark` als Textbestandteil vor (Z.490 ff., `BrandWordmark`),
   kein Props-Interface dazu.
4. `test_ac1_all_component_category_dirs_documented`: **bereits grün** — alle
   Unterverzeichnisse sind im Component-Organization-Baum bereits genannt.
   Nicht Teil dieser Scheibe.

**Umsetzung:**
1. `NAMED_COMPONENTS` (Z.30-43): `"NewLocationWizard"` entfernen, mit
   Kommentar an der Zeile (Begründung: Wizard-Abschaffung, Nachweis in
   `legacy_wizard_removed.test.ts`). Die verbleibenden 10 Namen unverändert
   lassen.
2. `test_ac5_updated_date_bumped` (Z.111-116) auf eine **monotone** Prüfung
   umstellen: das erste Datum nach `"**Updated:**"` per Regex/`strptime`
   extrahieren und `>= date(2026, 5, 25)` prüfen, statt einen fixen
   String-Teilausschnitt zu fordern. **Das Doc-Datum bleibt unverändert**
   (`2026-07-21` ist bereits `>=`) — kein Zurückschreiben, keine
   Falschdokumentation.
3. `docs/reference/frontend_components.md`: `WordmarkProps`-Interface bei der
   bestehenden Wordmark-Erwähnung ergänzen (analog `BtnProps`/`GCardProps`);
   die 10 real existierenden Komponenten (`MapCanvas`, `WaypointPin`,
   `PauseStageView`, `ProfileEditor`, `StageCard`, `WaypointCard`,
   `LocationPreviewMap`, `AlertRulesEditor`, `AlertRuleRow`, `ModeCard`) an
   geeigneter Stelle nennen (je im passenden Abschnitt: `edit/` bzw.
   `alert-rules-editor/`/`compare/`). Bestehende History-Kette in der
   `**Updated:**`-Zeile nicht löschen.

Punkt 3 ist reine `docs/`-Änderung (zählt nicht gegen das LoC-Limit); Punkt 1
und 2 sind Testcode-Änderungen (zählen mit, aber klein).

### Gruppe B2 — `test_issue_1165_adr_index_cleanup.py` (AC-5) — 1 Test

`_SELF_REFERENTIAL_EXCLUDES` (Z.80-83) listet bereits explizit
`_REPO_ROOT / "docs" / "specs" / "modules" / "issue_1165_adr_index_cleanup.md"`
als Selbstzitat-Ausnahme. Gemessen: **diese Datei existiert dort nicht mehr**
— sie liegt seit dem Archivieren unter
`docs/specs/_archive/modules/issue_1165_adr_index_cleanup.md`. Der
Ausnahme-Eintrag wurde beim Verschieben nicht nachgezogen, weshalb
`_find_adr_mentions()` (Z.87-98) die 5 alten Fundstellen dort jetzt wieder als
echte Treffer zählt.

**Umsetzung:** Nur den einen Pfad in `_SELF_REFERENTIAL_EXCLUDES` (Z.82)
korrigieren auf `_REPO_ROOT / "docs" / "specs" / "_archive" / "modules" /
"issue_1165_adr_index_cleanup.md"`. **Kein** pauschaler Ausschluss von
`docs/specs/_archive/` als Verzeichnis — das würde den Wächter über einen
ganzen Ordner hinweg blind machen. `_SELF_REFERENTIAL_EXCLUDE_DIRS` (Z.84,
nur `docs/artifacts`) bleibt unverändert. Der Scanner wird durch die exakte
Pfadkorrektur **enger** (folgt dem tatsächlichen Ort des einen erlaubten
Selbstzitats), keine Erwartung wird gelockert.

### Gruppe B3 — `test_issue_457_email_per_recipient.py` (AC-6) — 2 Tests

`test_ac5_source_enthält_per_recipient_loop` und
`test_ac5_source_enthält_per_recipient_try_except` (Z.25-66) prüfen
`inspect.getsource(EmailOutput.send)` auf Teilstrings. Verhalten existiert,
ist aber umgezogen: `src/output/channels/email.py:485` (`for recipient in
recipients:`) und `:489`/`:511` (`sendmail(from_addr, [recipient], ...)`) in
`_dial_and_send(..., isolate_per_recipient)`. **PO-Entscheidung 2026-08-03:**
löschen statt umbauen, weil bereits ein Verhaltensnachweis existiert:
`tests/tdd/test_mail_transport_dial_behaviour.py::test_ac2_primaerweg_stellt_trotz_einer_ablehnung_an_die_uebrigen_zu`
(Z.192-210) — echte Attrappe am Transportrand, beweist wortwörtlich "der
Primärweg versucht jeden Empfänger einzeln" (Z.210) und dass ein abgelehnter
Empfänger die übrigen nicht blockiert (Z.211-214).

**Umsetzung:** Die zwei Quelltext-Tests aus `test_issue_457_email_per_recipient.py`
entfernen (die übrigen zwei Tests der Klasse — `test_ac5_return_type_none_unveraendert`,
`test_ac5_echter_mehrfach_versand_kein_absturz` — bleiben unverändert). In
`test_mail_transport_dial_behaviour.py` bei `test_ac2_…` (Z.192) einen
Kommentar ergänzen, dass dieser Test die Abdeckung von #457 mitträgt.

### Gruppe B4 — `test_issue_872_threshold_ux.py` (AC-7) — 1 Test

`test_ac4_scheduler_source_contains_sms_threshold_thunder` (Z.39-54) prüft
`inspect.getsource(trip_report_scheduler)` auf den String
`"sms_threshold_thunder"`. Der Schlüssel wird heute nicht mehr im Scheduler
gesetzt, sondern im geteilten Ausblick-Renderer:
`src/output/renderers/email/outlook.py:394`
(`"sms_threshold_thunder": _sms.get("thunder")`, innerhalb von
`build_outlook_row`, Signatur mit `sms_thresholds`-Kwarg ab Z.387).

**Echte Lücke, gemessen:** `test_shared_outlook_renderer.py:260` prüft nur den
Negativfall (`"sms_threshold_thunder" not in row2`, wenn die Schwelle `None`
ist). Kein Test beweist, dass eine **gesetzte** Schwelle tatsächlich ankommt
(`grep -rn "sms_threshold_thunder" tests/` → nur die Negativzeile + der zu
ersetzende Textprüfer).

**Umsetzung:** `test_ac4_scheduler_source_contains_sms_threshold_thunder`
ersetzen durch einen echten Aufruf: `build_outlook_row(summary, points,
weekday, tz, sms_thresholds={"thunder": <Wert>, ...})` und Assertion
`row["sms_threshold_thunder"] == <Wert>`. Kein Produktivcode nötig — die
Funktion liefert den Wert bereits korrekt (gelesen, nicht angenommen).

### Gruppe D1 — `test_shared_outlook_renderer.py` (AC-8) — 1 Test

`test_build_outlook_row_pure_function` (Z.211-260) importiert Z.224
`from src.output.tokens.dto import HourlyValue`, der Renderer
(`outlook.py:338`) importiert `from output.tokens.dto import HourlyValue`.
Wegen `pythonpath = ["src", "."]` (pyproject.toml) sind das zwei getrennte
Klassenobjekte — `isinstance(hv, HourlyValue)` (Z.249) schlägt strukturell
immer fehl, obwohl `build_outlook_row` echte `HourlyValue`-Instanzen liefert.

**Umsetzung:** Z.224 auf `from output.tokens.dto import HourlyValue` ändern
(Produktpfad, ohne `src.`-Präfix).

**Bekannter Nebenbefund (nicht Teil dieser Scheibe):** Jede `isinstance`-Prüfung
über diese Import-Grenze scheitert strukturell gleich — gehört als
Sammel-Eintrag in #1199 (Kategorie „fälschlich blockierendes Gate").

### Gruppe D2 — `test_issue_346_fixture_provider.py` (AC-9) — 1 Test

`test_ac5_timestamps_restamped_to_today` (Z.92-105) vergleicht gegen
`today0 = datetime.now(timezone.utc).replace(hour=0, ...)` — **aware**.
`FixtureProvider.fetch_forecast` liefert seit Issue #1345
(`src/app/models.py:151-158`, `ForecastDataPoint.__post_init__`) ausschließlich
**naive UTC**-Zeitstempel an der Provider-Grenze. Gemessen: gleiche Wanduhr,
`==`-Vergleich liefert `False` allein wegen der `tzinfo`-Differenz.

**Umsetzung:** `today0` naiv bilden (z.B. `datetime.now(timezone.utc)
.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)`). Die
Hausnorm „naive UTC an der Provider-Grenze" (#1345) bleibt unangetastet —
diese Scheibe korrigiert nur den veralteten Testsollwert.

### Gruppe D3 — `test_fix_853_842_837_tooling_gates.py` (AC-10) — 1 Test

**Ursprüngliche Ursache (unverändert gültig):**
`TestAC2AC3ProdSelftestAncestor::test_ac3_fail_when_not_ancestor` rief
`run_selftest()` ohne Isolation gegen das im Skript fest verdrahtete
`REPO_DIR` (`.claude/hooks/prod_selftest.py:56`, echtes Hauptrepo) auf. Ohne
`explicit_path` greift bei fehlendem exaktem Treffer der `else`-Zweig
(Z.735-746): `_e2e_paths._nearest_verified_ancestor(head, REPO_DIR, REPO_DIR)`
sucht einen Vorfahren-Nachweis **im Git-Verlauf des echten Hauptrepos** — für
den erfundenen Commit `"deadbeef" * 5` müsste das `rc == 1` liefern, hing
aber vom dortigen Attestations-Bestand ab (Zufallsrauschen, PO-Befund
2026-07-26). Zusätzlicher Nebenbefund: der Test schrieb seinen Bericht dabei
ins **echte Hauptrepo** (`REPO_DIR / "docs" / "artifacts" / workflow /
"prod-selftest.md"`, Z.682), auch aus einem Worktree heraus.

**`REPO_DIR` selbst ist kein Pfadverstoß:** Die feste Konstante ist laut
CLAUDE.md (Pfadregel #1409) für die **geteilte Ablage** — HEAD-Ermittlung,
Attestation — ausdrücklich vorgesehen. Zu reparieren war nicht
`prod_selftest.py`, sondern dass **dieser eine Test** sie ohne Isolation
gegen den echten Bestand laufen ließ.

**Erster Lösungsversuch — VERWORFEN, Erkenntnis dokumentiert:** Die
Testfunktion nach `tests/tdd/test_prod_selftest_564.py` zu verschieben (dort
liegt bereits `_init_evidence_free_repo` neben `TestAC5NoE2EFile`) schien
naheliegend, war aber ein **Rückschritt**: `test_prod_selftest_564.py` trägt
modulweit `pytestmark = pytest.mark.staging` (Z.26), und `pytest.ini`
(`addopts = -m 'not email and not live and not staging'`) deselektiert den
gesamten Standardlauf davon. Gemessen: `--collect-only` zeigt für die Datei
„0 collected / 24 deselected" — der verschobene Test lief **nie mehr**, war
also nicht grün, sondern **unsichtbar**. Der ursprünglich geforderte
Determinismus-Nachweis („zweimal hintereinander grün") war dabei wertlos,
weil ein deselektierter Test immer als grün durchgeht, ohne je zu laufen —
genau die Gate-Erosion, die diese ganze Scheibe verhindern soll.

**Tatsächlich umgesetzter Weg:** Die vier Bausteine
`_load_prod_selftest_module`, `_head_sha`, `_make_e2e_verified`,
`_init_evidence_free_repo` (plus die Konstanten `PROD_SELFTEST`/`REPO_DIR`)
wurden aus `test_prod_selftest_564.py` **nach `tests/tdd/conftest.py`**
verschoben — ein geteilter Ort, keine Kopie. `test_prod_selftest_564.py`
importiert sie von dort zurück und ist ansonsten unverändert (bleibt bei 23
gesammelten Tests, weiterhin komplett `staging`-deselektiert im
Standardlauf — das ist für diese Datei korrekt, sie dialt real).
`test_ac3_fail_when_not_ancestor` **bleibt** in
`test_fix_853_842_837_tooling_gates.py` (keine Modul-Markierung, läuft im
Standardlauf) und importiert dieselben Helfer per
`from tests.tdd.conftest import ...`. Die Wegwerf-Repo-Isolation
(`_init_evidence_free_repo` + `monkeypatch.setattr(mod, "REPO_DIR", root)`,
Muster von `TestAC5NoE2EFile`) bleibt inhaltlich unverändert — nur ihr
Wohnort ändert sich.

**Fallstrick beim Import (selbst gefunden, in der Umsetzung behoben):** Ein
bloßes `from conftest import ...` löst wegen `tests/tdd`s eigenem
`conftest.py` mehrdeutig auf und kann stattdessen gegen das übergeordnete
`tests/conftest.py` greifen. Der vollqualifizierte Pfad
`from tests.tdd.conftest import (...)` ist Pflicht.

**Umsetzung (final):**
1. In `tests/tdd/conftest.py` einen neuen Abschnitt mit den vier Bausteinen +
   Konstanten ergänzen (Kommentar: geteilter Ort, Issue #1196 S1 AC-10).
2. `test_prod_selftest_564.py`: eigene Definitionen der vier Bausteine
   entfernen, stattdessen `from tests.tdd.conftest import
   _init_evidence_free_repo, _load_prod_selftest_module,
   _make_e2e_verified` (vollqualifiziert). Datei bleibt sonst unverändert.
3. `test_fix_853_842_837_tooling_gates.py`:
   `test_ac3_fail_when_not_ancestor(self, tmp_path, monkeypatch)` bleibt in
   der Datei, importiert dieselben drei Bausteine vollqualifiziert, baut
   `_init_evidence_free_repo(tmp_path / "repo")`, lädt das Modul über
   `_load_prod_selftest_module()`, biegt `mod.REPO_DIR` per `monkeypatch` auf
   das isolierte Repo um, schreibt die Fake-Attestation über
   `_make_e2e_verified(tmp_path, verified_commit="deadbeef"*5)`, ruft
   `mod.run_selftest(e2e_path, "test-tooling-853", scope="backend")` auf,
   `assert rc == 1`.

**Verifiziert (gemessen, nicht nur behauptet):**
```
uv run pytest tests/tdd/test_fix_853_842_837_tooling_gates.py -p no:randomly --collect-only
  -> ...::test_ac3_fail_when_not_ancestor collected, 1 deselected (nur test_ac2, @pytest.mark.live)

uv run pytest tests/tdd/test_fix_853_842_837_tooling_gates.py -p no:randomly -v
  -> 1 passed, 1 deselected   (dreimal hintereinander: 1 passed / 1 passed / 1 passed)

stat auf REPO_DIR/docs/artifacts/test-tooling-red/prod-selftest.md:
  Zeitstempel vor und nach den Läufen identisch — kein Schreibzugriff mehr ins Hauptrepo
```

### Gruppe C (bewusst ausgeschlossen) — `test_issue_586_alert_config_fidelity.py` — 3 Tests

Erwartet `docs/artifacts/issue-586-fidelity-gate/{live-alert-config.png,
reference-alert-config.png, design-diff-K-alert-config-list.json}` — keines
existiert. Braucht Staging-Screenshot + JSX-Referenz-Rendering + Gate-Bericht,
eine andere Arbeitsart als der Rest dieser Scheibe. Wichtiger: der
Pixel-Diff-Test kann nach der Messung **berechtigt rot bleiben** (>10 %
Layout-Abweichung) — dann ist er ein echter Produktbefund und gehört gerade
**nicht** in eine Scheibe für „Tests, die nichts über das Produkt aussagen".
Kein AC in dieser Spec; eigenes Ticket je nach Messergebnis.

## Expected Behavior

- **Input:** `uv run pytest` (Standardfilter: `live`/`email`/`staging`
  deselektiert) auf dem Stand nach dieser Scheibe.
- **Output:** alle 21 in dieser Spec behandelten Tests sind grün und
  **erscheinen im Standardlauf als `passed`, nicht `deselected`** (Gruppe A:
  11, Gruppe B: 7, Gruppe D: 3 — `test_ac3_fail_when_not_ancestor` bleibt in
  `test_fix_853_842_837_tooling_gates.py`, nur seine Helfer wandern nach
  `tests/tdd/conftest.py`).
- **Side effects:** vier neue kleine Binär-Fixtures unter `tests/fixtures/dpc/`,
  eine `.gitignore`-Ausnahmezeile, ein Doku-Update in
  `docs/reference/frontend_components.md`, vier Helferfunktionen wandern aus
  `test_prod_selftest_564.py` nach `tests/tdd/conftest.py`. Kein
  Produktivcode geändert.

## Acceptance Criteria

- **AC-1:** Given die zwei echten DPC-Zip-Aufzeichnungen fehlen unter
  `tests/fixtures/dpc/` / When `ruhetag_20260730_1511.zip` und
  `unwettertag_20260118_1515.zip` gemäß `tests/fixtures/dpc/README.md`
  beschafft und abgelegt werden / Then sind die 8 fixture-abhängigen Tests
  `test_ac2`, `test_ac3`, `test_ac4_source_label`,
  `test_zwei_zonen_gleichzeitig_thunderstorm_gelb_und_flood_orange`,
  `test_stufen_abbildung_rossa_liefert_level_4_flood`,
  `test_stufen_abbildung_arancione_ohne_temporali_liefert_nur_flood`,
  `test_ac6_gewitter_ueberschneidung_kollabiert_auf_hoehere_stufe`,
  `test_ac7_unavailable_bleibt_true_wenn_meteoalarm_ausfaellt_dpc_liefert`
  in `tests/tdd/test_dpc_bulletin_source.py` grün, ohne dass ein Wert in den
  Fixtures verändert wurde.
  - Test: `uv run pytest tests/tdd/test_dpc_bulletin_source.py -k "ac2 or ac3 or ac4_source_label or zwei_zonen or stufen_abbildung or ac6_gewitter or ac7_unavailable"`
    war vorher rot (FileNotFoundError), ist danach grün.

- **AC-2:** Given die zwei synthetischen Fail-soft-Fixtures
  (`synthetic_unknown_stufe_pattern.zip`, `synthetic_unknown_zone_code.zip`)
  fehlen ebenfalls / When beide per Wegwerf-Skript mit dem Feldschema aus
  `_parse_dbf` (`dpc.py:86-106`) erzeugt und abgelegt werden / Then sind
  `test_ac5b_unbekanntes_stufen_freitextmuster_liefert_keine_warnung` und
  `test_ac5c_unbekannter_zonencode_wird_geloggt_kein_crash` grün.
  - Test: `uv run pytest tests/tdd/test_dpc_bulletin_source.py -k "ac5b or ac5c"`
    war vorher rot (FileNotFoundError), ist danach grün.

- **AC-3:** Given `test_ac6_reale_paket_registrierungsreihenfolge_meteoalarm_vor_dpc`
  sucht den Literal-Namen `"meteoalarm"` (Z.495/499), der seit Issue #1445 S3
  durch `MeteoAlarmFeedSource` mit `.name == "meteoalarm_feed"` ersetzt wurde
  / When beide Vorkommen auf `"meteoalarm_feed"` geändert werden / Then ist
  der Test grün und beweist weiterhin, dass die MeteoAlarm-Familie vor
  `DpcSource` registriert wird.
  - Test: `uv run pytest tests/tdd/test_dpc_bulletin_source.py -k test_ac6_reale_paket`
    war vorher rot (AssertionError, nicht FileNotFoundError — kein
    Fixture-Bezug), ist danach grün.

- **AC-4:** Given (a) `NAMED_COMPONENTS` verlangt den Nachweis der nicht mehr
  existierenden `NewLocationWizard`, (b) `test_ac5_updated_date_bumped`
  fordert einen fest verdrahteten Datums-Teilstring statt eines
  Mindestdatums, (c) `WordmarkProps` fehlt im Doc / When `NewLocationWizard`
  mit Begründung aus der Liste entfernt, die Datumsprüfung monoton (`>=
  2026-05-25`) gemacht und `WordmarkProps` + die 10 real existierenden
  Komponenten im Doc ergänzt werden / Then sind alle drei Tests grün, OHNE
  dass das `**Updated:**`-Datum im Doc zurückgeschrieben wurde.
  - Test: `uv run pytest tests/tdd/test_issue_316_docs_cleanup.py` war vorher
    3 rot / 4 grün, ist danach 7/7 grün.

- **AC-5:** Given `_SELF_REFERENTIAL_EXCLUDES` (Z.82) verweist auf
  `docs/specs/modules/issue_1165_adr_index_cleanup.md`, eine Datei, die seit
  dem Archivieren unter `docs/specs/_archive/modules/` liegt, wodurch
  `_find_adr_mentions()` deren 5 Selbstzitate wieder als echte Treffer zählt
  / When der eine Pfad-Literal auf den Archiv-Ort korrigiert wird (kein
  pauschaler `_archive/`-Ausschluss) / Then ist
  `test_no_adr_0013_reference_in_node_test_context` grün, UND ein neuer,
  echter `ADR-0013`-Treffer außerhalb dieser einen Datei würde weiterhin
  anschlagen.
  - Test: `uv run pytest tests/tdd/test_issue_1165_adr_index_cleanup.py` war
    vorher 1 rot / 2 grün, ist danach 3/3 grün.

- **AC-6:** Given `test_issue_457_email_per_recipient.py` enthält zwei
  Quelltext-Textprüfungen, deren Aussage bereits durch
  `test_mail_transport_dial_behaviour.py::test_ac2_primaerweg_stellt_trotz_einer_ablehnung_an_die_uebrigen_zu`
  (Z.192-210) verhaltensbasiert bewiesen wird / When die zwei Textprüfungen
  gelöscht werden und bei `test_ac2_…` ein Kommentar-Querverweis auf #457
  ergänzt wird / Then bleiben `test_ac5_return_type_none_unveraendert` und
  `test_ac5_echter_mehrfach_versand_kein_absturz` unverändert bestehen, UND
  kein Verhaltensnachweis zu #457 geht verloren.
  - Test: `uv run pytest tests/tdd/test_issue_457_email_per_recipient.py`
    (ohne `email`-Marker) war vorher 2 rot / 2 grün, ist danach 0/2 (2
    entfernt) — voller Lauf hat 2 rote Tests weniger.

- **AC-7:** Given kein Test beweist, dass eine gesetzte Gewitterschwelle über
  `build_outlook_row(..., sms_thresholds={"thunder": X})` tatsächlich als
  `row["sms_threshold_thunder"] == X` ankommt (nur der Negativfall bei `None`
  ist getestet, `test_shared_outlook_renderer.py:260`) / When
  `test_issue_872_threshold_ux.py::test_ac4_scheduler_source_contains_sms_threshold_thunder`
  durch einen echten Aufruf mit gesetzter Schwelle ersetzt wird / Then ist der
  neue Test grün, OHNE dass `src/output/renderers/email/outlook.py` geändert
  werden musste (Lücke war rein testseitig).
  - Test: `uv run pytest tests/tdd/test_issue_872_threshold_ux.py` war vorher
    1 rot / 1 grün, ist danach 2/2 grün, UND deckt jetzt den Positivfall ab,
    den vorher kein Test prüfte.

- **AC-8:** Given `test_shared_outlook_renderer.py:224` importiert
  `HourlyValue` über `src.output.tokens.dto`, während `outlook.py:338` über
  `output.tokens.dto` importiert, wodurch `isinstance` strukturell immer
  `False` liefert / When der `src.`-Präfix im Test entfernt wird / Then ist
  `test_build_outlook_row_pure_function` grün.
  - Test: `uv run pytest tests/tdd/test_shared_outlook_renderer.py -k
    test_build_outlook_row_pure_function` war vorher rot (AssertionError bei
    `isinstance`), ist danach grün.

- **AC-9:** Given `test_ac5_timestamps_restamped_to_today` vergleicht gegen
  einen zeitzonen-bewussten (`tzinfo=timezone.utc`) Sollwert, während
  `ForecastDataPoint.__post_init__` (`src/app/models.py:151-158`, Hausnorm
  seit #1345) ausschließlich naive UTC-Zeitstempel liefert / When der
  Sollwert `today0` naiv gebildet wird / Then ist der Test grün, UND
  `src/app/models.py` bleibt unverändert.
  - Test: `uv run pytest tests/tdd/test_issue_346_fixture_provider.py -k
    test_ac5_timestamps_restamped_to_today` war vorher rot (Werte gleich,
    Vergleich `False` wegen `tzinfo`-Differenz), ist danach grün.

- **AC-10:** Given `test_ac3_fail_when_not_ancestor` ruft `run_selftest()`
  ohne Isolation gegen das im Skript fest verdrahtete `REPO_DIR` (echtes
  Hauptrepo) auf, wodurch sowohl das Ergebnis vom dortigen
  Attestations-Bestand abhängt als auch ein Bericht ins Hauptrepo geschrieben
  wird / When die vier Wegwerf-Repo-Helfer nach `tests/tdd/conftest.py`
  ausgelagert werden (geteilter Ort statt Duplikat) und
  `test_ac3_fail_when_not_ancestor` **in `test_fix_853_842_837_tooling_gates.py`
  bleibt** und sie von dort vollqualifiziert importiert
  (`from tests.tdd.conftest import ...`), dabei `_init_evidence_free_repo` +
  `monkeypatch.setattr(mod, "REPO_DIR", root)` nutzt / Then erscheint der
  Test im **Standardlauf** von `tests/tdd/test_fix_853_842_837_tooling_gates.py`
  als **`passed`, nicht `deselected`**, ist bei jedem Lauf grün unabhängig
  vom Attestations-Bestand des echten Hauptrepos, UND schreibt keinen
  Bericht mehr ins Hauptrepo (Zeitstempel von `prod-selftest.md` unverändert
  vor/nach dem Lauf).
  - Test: `uv run pytest tests/tdd/test_fix_853_842_837_tooling_gates.py -p
    no:randomly --collect-only` zeigt `test_ac3_fail_when_not_ancestor` in
    der **Sammelliste** (nicht deselektiert — nur `test_ac2`,
    `@pytest.mark.live`, ist es). `uv run pytest
    tests/tdd/test_fix_853_842_837_tooling_gates.py -p no:randomly -v`
    liefert `1 passed, 1 deselected`, dreimal hintereinander reproduzierbar.
    **Ein deselektierter Test zählt hier ausdrücklich NICHT als Erfolg** —
    das war der Fehler des ersten, verworfenen Lösungswegs (Umzug nach
    `test_prod_selftest_564.py`, das modulweit `pytest.mark.staging` trägt).

- **AC-11 (Gesamtwirkung, Pflicht):** Given der volle `uv run pytest`-Lauf
  (Standardfilter) zeigt vor dieser Scheibe die 21 in AC-1 bis AC-10
  beschriebenen roten Tests / When alle Maßnahmen aus AC-1 bis AC-10
  umgesetzt sind / Then zeigt derselbe volle Lauf genau 21 rote Tests
  weniger als vorher, UND keinen neu roten Test, der vorher grün war, UND
  keinen Test, der vorher lief und jetzt nur noch `deselected` erscheint.
  - Test: voller `uv run pytest`-Lauf (nicht nur die einzelnen Dateien),
    Vorher-/Nachher-Zählung roter Tests UND Vorher-/Nachher-Zählung
    gesammelter (nicht deselektierter) Tests.

## Known Limitations

- **`#586` (Design-Fidelity, 3 Tests) ist bewusst NICHT Teil dieser Spec.**
  `test_issue_586_alert_config_fidelity.py` erwartet drei Artefakte unter
  `docs/artifacts/issue-586-fidelity-gate/` (Staging-Screenshot @1440px,
  JSX-gerenderte Referenz, Gate-Bericht) — keines existiert, Erzeugung
  braucht Staging + Playwright, eine andere Arbeitsart als der Rest dieser
  Scheibe. Wichtiger: der Pixel-Diff-Test **kann nach der Messung berechtigt
  rot bleiben** (> 10 % Layout-Abweichung zwischen Live und bindender JSX) —
  in diesem Fall ist er ein echter Produktbefund und gehört gerade **nicht**
  in eine Scheibe für „Tests, die nichts über das Produkt aussagen". Er
  bekommt daher kein AC in dieser Spec und wird als eigener Punkt (Folge-Scheibe
  oder eigenes Issue, je nach Messergebnis) behandelt.
- **Externe Beschaffung (AC-1):** Bleibt der GitHub-Archiv-Abruf erfolglos,
  ist der Rückfall ein Erzeugungs-Skript + `skipif` auf Vorhandensein, als
  **übersprungen** markiert, nie als Fehlschlag (verhindert eine neue Falle
  für den nächsten Lauf).
- **`test_issue_1014_live_optin` (2 Tests):** isoliert grün, im Gesamtlauf rot
  (Testreihenfolge-Verschmutzung). Nicht Teil dieser Scheibe — bleibt
  unangetastet, als offener Befund an #1196 gemeldet.
- **Isinstance-Import-Falle (aus AC-8):** strukturelles Risiko für jede
  weitere `isinstance`-Prüfung über die `src.`/`""`-Präfix-Grenze — als
  Sammel-Eintrag in #1199 zu melden, nicht Teil dieser Scheibe.
- **`REPO_DIR`-Konstante in `prod_selftest.py` bleibt unverändert** (AC-10) —
  sie ist laut CLAUDE.md/Pfadregel #1409 für die geteilte Ablage
  (HEAD-Ermittlung, Attestation) ausdrücklich vorgesehen; repariert wird nur
  die fehlende Isolation in diesem einen Test.
- **Verworfener Lösungsweg für AC-10, als Lehre festgehalten:** Tests NICHT
  in eine Datei mit modulweitem `pytestmark = pytest.mark.staging`,
  `pytest.mark.live` o.ä. verschieben, um sie an ein bestehendes Muster
  anzuschließen — der Standardlauf (`pytest.ini` `addopts`) deselektiert die
  ganze Datei, der Test wird dadurch nicht grün, sondern unsichtbar (0
  Ausführungen, aber kein Fehlschlag = fälschlich unauffällig). Vor jedem
  Testumzug den Ziel-Datei-Kopf auf modulweite Marker prüfen (`pytestmark =`)
  und `--collect-only` gegenprüfen, dass der Test danach tatsächlich
  gesammelt (nicht deselektiert) wird. Gehört als generischer Hinweis in eine
  künftige Testpflege-Checkliste (Sammel-Eintrag #1199).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testpflege und ein Doku-Update, keine
  Entscheidungsfläche (kein Kanal, kein Provider, kein Datenmodell, keine
  Auth, kein Editor-Paradigma, keine Test-/Deploy-Strategie-Änderung)
  betroffen. Die Wegwerf-Repo-Musterwahl (AC-10) ist bereits durch
  Präzedenzfall (`test_prod_selftest_564.py`, Fix #1382) gedeckt; die
  Helfer-Auslagerung nach `conftest.py` ist reines Test-Refactoring.

## Changelog

- 2026-08-03: Initial spec created
- 2026-08-03: Überarbeitung nach zwei Team-Lead-Korrekturen — Gruppe C (#586)
  komplett aus dem Umfang genommen (21 statt 24 Tests), #1165-Fix auf
  Pfad-Literal statt Verzeichnisausnahme präzisiert, #316-Fix um
  `NewLocationWizard`-Entfernung + monotone Datumsprüfung erweitert,
  #853-Fix auf Testumzug nach `test_prod_selftest_564.py` festgelegt
  (statt `explicit_path=True`).
- 2026-08-03 (v1.2): AC-10 korrigiert — der Umzug nach
  `test_prod_selftest_564.py` erwies sich bei der Umsetzung als Fehler
  (modulweiter `pytest.mark.staging`-Marker deselektiert die Datei komplett
  im Standardlauf; der Test wurde dadurch unsichtbar, nicht grün).
  Tatsächlicher Weg: die vier Helferfunktionen wandern nach
  `tests/tdd/conftest.py` (geteilter Ort), `test_ac3_fail_when_not_ancestor`
  bleibt in `test_fix_853_842_837_tooling_gates.py` und importiert sie
  vollqualifiziert von dort. AC-10 verlangt jetzt ausdrücklich den Nachweis
  „`passed`, nicht `deselected`" im Standardlauf; AC-11 entsprechend ergänzt.
