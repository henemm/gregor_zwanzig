# Context: rework-3207-tote-tests

## Request Summary
Issue #3207 (Teil von #1196): Tests, die Funktionen prüfen, die es im Produkt nicht mehr gibt, werden entfernt (je Datei mit Beleg: abgelöstes ADR/Issue/Spec). Zusätzlich eine Workflow-Regel „abgelöste Funktion ⇒ Tests im selben Umbau entfernen" mit Prüfdatum nach Regel-Budget (ADR-0100). Abschluss: Liste im PR, Kern-Schicht 100 % grün, keine noch geltende Zusicherung verloren (Mutations-Stichproben).

## Bestand (Stand origin/main 76e22ab83, 2026-11-21)
| Bereich | Anzahl |
|---|---|
| Python-Testdateien gesamt | 1.815 (davon `tests/tdd/` 1.327, `tests/unit/` 249, Wurzel `tests/` 180, `integration` 27, `golden` 16, `e2e` 8, `refactor` 5, `red` 1, `visual` 1) |
| Python-Dateien mit Ziffer im Namen | 445 (Issue sprach von 287 „nach Issue-Nummer") |
| Frontend `*.test.*` / Playwright `*.spec.ts` | 838 / 254 |
| Go `*_test.go` | 535 |
| Dateien mit `skip` | 127 |

## Bereits sichtbare Kandidaten (Belege im Code)
- `tests/e2e/test_trips_start_time_buttons.py`, `test_subscriptions_safari.py`, `test_safari_preventive_fix.py`, `test_locations_add_button.py`: modulweit `skip("NiceGUI E2E tests — decommissioned in M4b cutover")` — NiceGUI-Oberfläche existiert nicht mehr.
- `tests/tdd/test_issue_360_channel_renderer.py:159,217,228` und `tests/tdd/test_bug_397_output_localtime.py:397`: `skip("Signal-Kanal entfernt (Bug #610)")` — Signal per ADR-0004/#610 entfernt.
- `tests/tdd/test_issue_612_report_on_demand.py:179,184,195`: `skip("Superseded by #884 design …")` — Befehle HEUTE/MORGEN/HILFE abgelöst.
- `tests/red/test_issue_435_format_modes.py`, `tests/refactor/test_epic_129a_3_ui_removed.py`, `test_dead_code_scheibe*.py`: Altlast-Ordner, Stand prüfen.
- Aktivitäts-Chips (ADR-0108, #3196 entfernt), toter Layout-Reiter / alter Wizard (ADR-0109) — Python-/Frontend-Tests dazu suchen.

## Erkennungs-Heuristiken (für /20-analyse)
1. Modul- oder Funktions-`skip` mit Grund „entfernt/abgelöst/superseded/decommissioned".
2. Tests, die Module/Symbole importieren, die es auf `origin/main` nicht mehr gibt (Kollektionsfehler oder `importorskip`).
3. Tests gegen Endpoints/Routen/Komponenten, die nicht mehr existieren (grep auf Pfad/Komponentenname im Produktcode).
4. Tests zu ADRs mit Status „Abgelöst durch" (README-Index), sofern die abgelöste Regel nicht mehr gilt.
5. Abgrenzung: rote/wackelnde Tests (#3108, #2911, #3053, #2898, #3054, #2889, #2940) und Umgebungs-Skips (SMTP/Staging/Playwright fehlt) sind NICHT „tot".

## Existing Patterns
- Playwright-Löschscheibe #2243 (geschlossen) ist das Vorbild: tote Specs gegen abgeschaffte Reiter/Wizard entfernt, Beleg je Datei.
- Ratschen-Listen: `.github/ci_tdd_excludes.txt` (darf nur schrumpfen, 1 Eintrag), `.github/ci_e2e_specs.txt` (Playwright-Positivliste) — beim Löschen Einträge mitpflegen.
- Regel-Budget: `docs/reference/workflow_und_agenten.md:92` + Prüfdaten-Tabelle `docs/reference/gates_und_ratschen.md`; `tests/test_regel_budget_pruefdatum_einstellung_auslieferung.py` prüft das.
- Namens-Hook `.claude/hooks/test_naming_gate.py`; Touched-Tests-Gate; `uv run pytest` ohne Dateiliste gesperrt (#1477).

## Dependencies
- Upstream: Produktcode `src/`, `api/`, `internal/`, `frontend/src/` — Maßstab „existiert auf origin/main".
- Downstream: CI-Jobs `test`, `go-test`, `frontend-test`, `e2e` (Positivliste), Meta-Tests, die Testdateien namentlich referenzieren (z. B. `test_pytest_collection_and_timeout_safety`, `test_stillgelegte_testdateien.py`, Doku-Verweise in Specs/ADRs) — vor dem Löschen per grep nach Dateinamen prüfen.

## Existing Specs / Docs
- `docs/reference/gates_und_ratschen.md` (Test-Politik), `docs/reference/workflow_und_agenten.md` (Regel-Budget), `docs/adr/README.md` (Abgelöst-Status), ADR-0094 (Test-Schichten), ADR-0100 (Regel-Budget).

## Risks & Considerations
- Teil-Datei vs. ganze Datei: gemischte Dateien nur um die toten Tests kürzen, geltende Zusicherungen behalten.
- Ein Test kann eine alte Issue-Nummer im Namen tragen und trotzdem geltendes Verhalten bewachen — Name allein ist kein Kriterium.
- Mutations-Gegenprobe an Stichproben: das bewachte Verhalten muss nach dem Löschen weiterhin von einem anderen Test gefangen werden.
- Umfang riesig (≈3.400 Dateien über drei Sprachen): Inventur per Heuristik + Stichproben, nicht Datei für Datei von Hand; ggf. in Scheiben (Python / Frontend / Go) teilen, je Scheibe eigenes Kind-Issue unter #1196 (PO-Regel: Epic mit Sub-Issues).
- Neue Regel braucht Prüfdatum +90 Tage (2027-02-19) oder ersetzt eine bestehende.

> Korrektur nach Inventur: `tests/refactor/test_epic_129a_3_ui_removed.py` und `test_dead_code_scheibe*.py` sind **Abwesenheits-Wächter** (bewachen, dass Entferntes entfernt bleibt) und bleiben. Ziffern im Dateinamen sind kein Totkriterium. Go-Teil braucht keine Scheibe (keine toten Tests), daher eine Scheibe statt drei.

## Analysis

### Type
Rework (Testsuite-Sanierung, Teil von Epic #1196). Kein nutzersichtbares Verhalten ändert sich.

### Inventur-Ergebnis (drei Explore-Agenten + Plan-Bewertung, 2026-11-21)
Rohfunde waren teils falsch (z. B. `frontend/e2e/bug-274-safe-area-insets.spec.ts` als „tot“ gemeldet, die testid steht dort nur im Kommentar, der Test prüft lebendes Viewport-Meta). **Jede Datei wird in der Umsetzung einzeln neu belegt; die Inventur ist nur Kandidatenliste.**

**Go:** keine toten Tests. 24 `t.Skip` alle Umgebungsgründe; Routen-404-Tests (`legacy_subscription_routes_removed_test.go`, `briefing_vorschau_route_entfernt_test.go`, `preview_proxy_targets_test.go:145` …) sind Abwesenheits-Wächter; Migrationstests bewachen lebenden Migrationscode (Bestandsdaten-Pflicht). Kosmetisch veraltete Pfadstrings in Handler-Direktaufrufen (`konto_mails_sprache_test.go:220`, `login_email_log_ohne_adresse_test.go:68`, `auth_traversal_test.go`) sind nicht tot.

**Python – Kandidaten tot (ganze Datei):**
| Datei | Beleg |
|---|---|
| `tests/tdd/test_issue_635_telegram_weather.py` | modulweit skip „OBSOLET (#1001)“, `render_narrow` fehlt in src/ |
| `tests/e2e/test_safari_preventive_fix.py`, `test_locations_add_button.py`, `test_subscriptions_safari.py`, `test_trips_start_time_buttons.py` | modulweit skip „NiceGUI decommissioned (M4b)“, `src/web/` weg |
| `tests/tdd/test_issue_496_layout.py` (staging) | testids `channel-preview-block`, `channel-fidelity-email`: 0 Treffer in frontend/src, internal, src, api (ADR-0109/0124) |
| `tests/tdd/test_701_alerts_metrik_sync.py` (staging) | testid `alerts-add-rule`: 0 Treffer |
| `tests/tdd/test_issue_934_wizard_schedule.py` (staging) | **unklar**: alter Wizard-Aufbau (ADR-0109), Route `/trips/new` existiert noch – nur löschen, wenn je Selektor fehlend belegt, sonst behalten |

**Python – Kandidaten tot (Einzeltests mit Ablöse-Skip):** `test_issue_612_report_on_demand.py` Z.179/184/195 (#884), `test_issue_360_channel_renderer.py` Z.159/217/228 (Signal #610), `test_bug_397_output_localtime.py:397` (Signal), `test_issue_397_segment_timezone.py:186` (Signal/#1001), `test_issue_887_report_inkonsistenz.py` Z.145/160/175/262 (`_tg_*_line` weg, #1001), `test_issue_614_telegram_kurzform.py` Z.166/185 (#1001 AC-10), `tests/test_trip.py:98` (Waypoint-Validierung entfernt). Achtung 397/887: Zeitzonen-/Konsistenz-Zusicherungen sind kanalunabhängig – nur den toten Testfall entfernen, nicht die Datei.

**Python – bleibt:** Abwesenheits-Wächter (`tests/unit/test_daylight_removed.py`, `*_removed.py`, `*dead*`, `tests/refactor/*`, `test_issue_610_signal_backend_red.py`, `assert not hasattr`-Wächter), `use_friendly_format`-Tests (Rückwärtskompatibilität lebt in `src/app/models.py:685`/loader), ~215 Umgebungs-Skips, ~30 Bug/xfail-Skips.

**Frontend – Kandidaten tot (ganze Spec, alle NICHT auf `.github/ci_e2e_specs.txt`, laufen nie):** `e2e/weather.spec.ts` (Route `/weather` fehlt), `issue-407-waypoint-editor-screen.spec.ts` (alle Tests skip, RED-Entwurf nie gebaut), `issue-294-home-kachel.spec.ts`, `startseite.spec.ts`, `trip-detail-overview-left.spec.ts`, `layout-tab-vergleich.spec.ts` (Layout-Reiter #3154/ADR-0124), `orts-gruppen-c2.spec.ts` (GroupSection gelöscht), `issue-88-report-config-dialog.spec.ts` (ReportConfigDialog gelöscht), `accent-ctas.spec.ts`.

**Frontend – teilweise tot (einzelne Fälle mit fehlenden testids / Skip „Superseded“):** `issue-302-trip-detail-redesign.spec.ts` (4 Skips „Superseded by #409“), `trip-detail-tabs.spec.ts`, `layout-tab-route.spec.ts`, `compare-layout-tab-dissolution.spec.ts`, `issue-343-horizon-chips`, `issue-452-smart-import-step2` (`compare-wizard-open-btn`), `mobile-stages-listen-only`, `issue-609-sms-profil`, `issue-313-design-showcase`, `anlege-rahmen-paritaet`, `issue-682-compare-editor-mobile`, `compare-editor-fidelity-s8d` (staging). Unit: `src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts` 3× `test.skip` „obsolet durch #439“. **Auf der Positivliste:** `hub-anlegen-ablauf.spec.ts` nennt entfernte testids – prüfen, ob es Abwesenheits-Zusicherungen (`toHaveCount(0)`) sind; nur echte Totfälle entfernen. Dynamisch gebaute testids (`trip-detail-tab-${v}` usw.) sind kein Totbeweis.
Löschwächter in Unit-Tests (`no_native_draggable_guard`, `versand_speichern_erhaelt_report_config`, `trip_new_alarme_reiter`, `subscription_kachel_paritaet`) bleiben.

### Affected Files (with changes)
| File | Change Type | Description |
|---|---|---|
| ~8 Python-Testdateien (s. o.) | DELETE | belegt tot |
| ~7 Python-Testdateien | MODIFY | einzelne tote Testfälle entfernen |
| ~9 Playwright-Specs | DELETE | belegt tot |
| ~12 Playwright-Specs + 1 Unit-Test | MODIFY | tote Fälle entfernen |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` (Z.98/108/132 nennen 701/496/934) | MODIFY | Namenslisten mitpflegen |
| `docs/reference/workflow_und_agenten.md` (Abschnitt Regel-Budget) | MODIFY | neue Regel „abgelöste Funktion ⇒ Tests im selben Umbau entfernen, Beleg im PR“ |
| `docs/reference/gates_und_ratschen.md` (Prüfdaten-Tabelle) | MODIFY | Zeile mit Prüfdatum 2027-02-19 |
| neuer Meta-Test `tests/test_regel_tote_tests_mitentfernen_pruefdatum.py` | CREATE | `# doc-compliance-test`: Regel + Prüfdatum stehen in Doku und Tabelle |
| ggf. `.github/ci_e2e_specs.txt` | MODIFY | nur falls eine gelistete Spec ganz entfällt (E2E_MIN_SPECS mitziehen) |

### Scope Assessment
- Dateien: ~45; LoC: ca. −2.500 bis −3.500 (reine Löschungen), +~60 (Regel, Meta-Test, Listenpflege)
- LoC-Limit-Override nötig (Löschungen), im PR begründen
- Risk Level: **LOW–MEDIUM** — kein Produktcode; Risiko ist der Verlust einer noch geltenden Zusicherung in gemischten Dateien und rote Meta-Tests mit Namensbindung.

### Technical Approach (Tech-Lead-Entscheidung)
1. **Beweis „tot“ je Datei/Fall, alle drei Kriterien im PR-Beleg:** (a) Ziel fehlt auf origin/main – grep auf Symbol/Route/Komponente/testid in src, api, internal, frontend/src mit Befehl und 0 Treffern, Kommentar-Treffer zählen nicht; (b) Ablöse-Beleg (ADR/Issue/Spec); (c) keine geltende Zusicherung allein dort – Nachfolgetest benennen (635→`test_issue_1001_telegram_bubbles`, Signal→E-Mail/Telegram-Renderer-Tests, 612→#884-Tests, 887/614→Bubble-Tests). Fehlt ein Kriterium ⇒ bleibt.
2. **Erhalt geltender Zusicherungen:** (i) Collect-Diff vor/nach je betroffener Datei: es verschwinden genau die gelisteten Tests; (ii) Mutations-Stichproben am Nachfolger-Produktcode (mind. 3: Telegram-Bubble-Zeile, Zeitzonen-Anzeige 397, Befehlsblock #884) – der Nachfolgetest muss rot werden.
3. **Abgrenzung:** Abwesenheits-Wächter, Umgebungs-Skips, Bug-/xfail-Skips, Migrationstests bleiben unangetastet.
4. **Regel:** reine Prozessregel im Regel-Budget-Abschnitt + Prüfdaten-Zeile (2027-02-19; Fang-Maß am Prüfdatum: Zahl der seither neu entstandenen toten Tests bzw. im selben Umbau mitentfernten Tests). Maschinell nur als Doku-Compliance-Meta-Test. Kein neues Gate (unscharf wegen Abwesenheits-Wächtern, kein belegter Fang).
5. Teilweise tote Specs gehören thematisch zu diesem Issue und bleiben in der Scheibe (PO-Regel: themenweise abschließen, nicht abspalten).

### Out of Scope (Nebenbefunde → Kommentar in #1196, kein neues loses Issue)
- 168 von 254 Playwright-Specs stehen nicht auf der Positivliste (128 davon nicht staging) und laufen nirgends – Frage „verdrahten oder löschen“ ist Governance, nicht „abgelöste Funktion“.
- `tests/red/test_issue_435_format_modes.py`: RED-Ablage einer gebauten Funktion (nicht abgelöst), in CI per `--ignore` ausgeschlossen.

### Dependencies
CI-Jobs `test`, `frontend-test`, `e2e` (Positivliste), Meta-Test `test_pytest_collection_and_timeout_safety.py`; Doku-Verweise in `docs/specs/_archive/…` und `.claude/red_issue_635.txt` sind reiner Text, unkritisch.

### Open Questions
- keine Produktfrage; alle Abgrenzungen sind Tech-Lead-Entscheidungen nach Issue-Text und PO-Regeln.
