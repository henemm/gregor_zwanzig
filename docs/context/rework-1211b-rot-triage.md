# Context: rework-1211b-rot-triage

## Request Summary
Scheibe 2b von #1211 (Kern von Sammelprojekt #1196): Vollständige Rot-Liste des deterministischen Standard-Laufs erheben und JEDEN roten Test in genau eine Kategorie triagieren (Veraltet→löschen · Echter Befund→Bug-Issue+xfail · Testfehler→minimal fixen · Live-Abhängig→Marker). Ziel: Standard-Lauf 0 rot. Setzt Scheibe 2a voraus (22 Staging-Dialer markiert, Commit `41eb5727` — LIVE auf origin/main).

## Messung (2026-07-18, dieser Workflow — erste vollständige, unverrauschte Erhebung)

**Methode:** 4 sequenzielle Etappen (A: alle Nicht-tdd-Verzeichnisse; B/C/D: tests/tdd gedrittelt), Standard-Selektion (addopts aktiv), globales `timeout=30` aus #1210, **in-process Netz-Sperre** (socket.connect gepatcht, localhost erlaubt): jeder Netzzugriffs-Versuch wird sofort roter Test mit Signatur `NETBLOCK:` statt echtem Traffic. JUnit-XML je Etappe; Rohdaten (`rotliste.json`, je Datei: rote Test-IDs, Netblock-Anteil, Fehler-Signaturen) im Session-Scratchpad, Kopie s. Artefakte.

**Ergebnis:** 5148 Tests · **387 failed + 3 errors = 390 rot** · 105 skipped · 98 Dateien mit Rot · davon **26 rote durch Netz-Sperre** (= real dialende, unmarkierte Tests; echter Traffic verhindert).

**Messgrenzen:** (a) Etappen-Grenzen ≠ Voll-Lauf-Reihenfolge — Reihenfolge-Verschmutzung (#1180) ist explizit Nicht-Scope; (b) Subprozess-Netzzugriffe (curl in Skripten) blockt die Sperre nicht (bekannte Fälle sind seit 2a markiert); (c) Lauf fand im Worktree statt — gitignorierte Datenbestände (z. B. GPX-Dateien) können fehlen → Cluster K2 braucht Gegenprobe.

## Rot-Cluster (Hypothesen, je mit Kandidaten-Kategorie — Verifikation via Analyse-Agenten)

| Cluster | Dateien (rote) | Hypothese | Kandidat |
|---|---|---|---|
| **K1 Workflow-Tooling/Hook-Drift** | ~30 Dateien, ~185 rote: test_session_singleton_guard (24), test_issue_258_hook_arch (17), test_issue_828_express_path (16), test_edit_verify_hook (13), test_bug_565_compact_to_clear (12), test_issue_384_hook_fail_open (11), test_issue_508_workflow_gate_none_verdict (11), test_bug_563_deploy_gate (7), test_issue_465 (7), test_issue_826 (7), test_bug_548 (6), test_fix_853_842_837 (6), test_issue_603 (5), test_issue_895 (5), test_epic_191_* (6), test_issue_960 (4), test_issue_829 (3), Hygiene-/Docs-Checks (test_765, test_753_746, test_issue_316, test_issue_1165, test_bug_567, test_e2e_path_helper, test_worktree_state_routing, test_622, test_issue_668, test_bug_600, test_bug_405) | prüfen ALTE Workflow-/Hook-Infrastruktur (pre-Plugin-v3); Referenzobjekte existieren teils nicht mehr im Repo (Plugin ausgelagert nach agent-os-openspec) | **Veraltet → löschen** |
| **K2 GPX/Höhen/Etappen** | 8 Dateien, ~44 rote: test_gpx_parser (13), test_elevation_analysis (8), test_hybrid_segmentation (8), test_segment_builder (6), test_gpx_import_in_trip_dialog (5), test_gpx_upload_page (5), test_etappen_config (4), test_gpx_proxy (4), integration/test_weather_snapshot (2) | fehlende (gitignorierte?) GPX-/Daten-Fixtures im Worktree → evtl. Mess-Artefakt, NICHT echtes Rot | **Testfehler/Umgebung → Gegenprobe, dann fixen (Fixture) oder skip-if-missing** |
| **K3 Netz-Dialer (NETBLOCK)** | 14 Dateien, 26 rote: test_account_page (8/8), test_issue_1069 (3/3), test_feature_770 (2/2), test_issue_1037 (2/2), test_issue_1142 (2/2), test_issue_645 (2/2), test_issue_731 (2/2), test_scheduler_triggers (2/2), test_channel_test_button (1/1), test_issue_608 (1/1), test_fix_853 (1/6, gemischt), test_e2e_telegram_pipeline/test_637/… (Anteile) | dialen real (Mail/API/Telegram), ungemarkt — 2a-Nachzügler jenseits der Staging-URL | **Live-Abhängig → Marker (email/live/staging), Muster 2a** |
| **K4 Mail-/Renderer-Design-Drift** | ~15 Dateien, ~40 rote: test_email_profile_pipeline (11), test_issue_623_trend_channels (7), test_imap_stalwart_migration (5), test_issue_561_trend_v4 (4), test_issue_669_outlook (4), test_722 (2), test_884 (2), test_906_907/911/613/952/997/visual_956 (je 1-2), test_issue_236/255/257 (je 2) | Rest der #984-42er-Liste: Tests prüfen alte Farben/Strukturen, Renderer wurde über #911/#956+ weiterentwickelt | **überwiegend Veraltet → löschen; Einzelfälle echter Befund** |
| **K5 Telegram** | ~7 Dateien, ~15 rote: test_issue_697 (6), test_637/655/744 (je 3), test_653/670/1077/572 (je 1) | Mischung: Verhaltens-Drift vs. Netz-Reste | **einzeln prüfen** |
| **K6 Einzelfälle** | Rest (~20 Dateien, je 1-6): test_epic_404 (16, Löschkandidat aus 2a-Validierung), tests/red/test_issue_435 (1 von 19), test_issue_934_wizard_schedule (6), test_feature_574 (3), test_feature_734 (3), test_alert_log/test_briefing_log (je 4), diverse | heterogen | **einzeln triagieren** |

## Related Files
| File | Relevance |
|------|-----------|
| Scratchpad `rotliste.json` + `chunk{A..D}.xml/.log` | Rohdaten der Messung (Test-IDs, Signaturen) |
| `docs/context/rework-1211a-staging-marker.md` | 2a-Klassifikation (Muster für K3) |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | Wächter — wird bei Marker-Nachzügen (K3) erneut erweitert |
| Issue #984 (42er-Liste 2026-07-02) | historische Basis, deckt K4 |
| Issues #1132/#1139/#1140/#1149/#1156/#1177/#1062/#1075 | alle CLOSED — Abgleich, ob deren Tests noch rot sind |

## Existing Patterns
- Test-Politik zwei Schichten (CLAUDE.md): rot im Kern = sofort fixen ODER löschen; nie liegenlassen. xfail nur mit Bug-Issue (`xfail(reason='#NNNN')`).
- 2a-Marker-Muster für K3; Löschungen müssen im PR/Artefakt tabellarisch begründet sein (Issue-AC-2: „kein Test verschwindet unbegründet").

## Risks & Considerations
- **Löschungen sind endgültig** — jede Löschung braucht Kategorie-Begründung in der Triage-Tabelle (AC-2 des Issues).
- **K2 zuerst gegenprüfen** (Mess-Artefakt-Verdacht) — sonst würden ~44 „rote" Tests fälschlich behandelt.
- **K1-Löschungen sind groß** (~30 Dateien): LoC-Limit betrifft nur Additions? Löschungen klären; ggf. Scheiben-Schnitt der Umsetzung.
- **Nicht anfassen:** Compare-/Provider-Tests paralleler Sessions (#1301): test_model_metric_fallback, test_provider_merge_contract, test_compare_provider_routing, Compare-Tests. `test_compare_dispatch_channel_fanout.py` (1 rot) → nur dokumentieren, Triage mit #1301-Session abstimmen.
- **tests/red/** (#435): „bewusst dauerhaft rot"-Konzept kollidiert mit Kern-Politik → Grundsatzentscheid in Spec (Verschieben hinter Marker o. löschen).
- Messlauf nie ohne Netz-Sperre wiederholen; `-m staging/email/live` bleibt als Ausführungslauf verboten.

## Analysis (Cluster-Verifikation, 4 Sonnet-Agenten, 2026-07-18)

### K1 Tooling — BESTÄTIGT veraltet (bis auf 4 Ausnahmen)
**12 Dateien komplett löschen** (Testobjekte nachweislich bei Plugin-Migration gelöscht, Commits `33da201c`/`465380c1`/`f1e3acc1`): test_session_singleton_guard (24), test_issue_258_hook_arch (17), test_issue_828_express_path (16), test_edit_verify_hook (13), test_bug_565_compact_to_clear (12), test_issue_508_workflow_gate_none_verdict (11), test_bug_563_deploy_gate (7), test_issue_826_complete_verdict_gate (7), test_bug_548_workflow_output_readability (6), test_issue_895_singleton_guard_lifecycle (5), test_epic_191_state_migration (4), test_issue_960_complete_gate (4) = **126 rote**.
**Ausnahmen:** test_issue_384_hook_fail_open (GEMISCHT: 10 rote prüfen 5 EXISTIERENDE, aktiv verdrahtete Hooks ohne Fail-open-Wrapping = ECHTER BEFUND Kategorie c „Lockout-Falle"; nur Count-Test veraltet) · test_issue_465 (GEMISCHT: 7 rote veraltet löschen, 2 grüne email_spec_validator-Tests behalten) · test_fix_853_842_837 (GEMISCHT: AC-1/AC-4 veraltet; AC-2 grün/stale-Messung) · test_issue_603_design_fidelity_gate (NOCH-RELEVANT: echter Bug — pre_issue_close_design_gate.py Exit 2 trotz gültigem Pass-Artefakt = fälschlich blockierendes Gate, Kategorie c).

### K2 GPX — BESTÄTIGT Mess-Artefakt mit dauerhaftem Fix (Kategorie Testfehler)
8 Dateien (~42 rote) zeigen auf gitignorierte lose `data/*.gpx`; **byte-identische Dateien liegen versioniert unter `data/users/default/gpx/`** (md5-geprüft). Fix: Pfad-Konstanten (`DATA_DIR`/`GPX_TAGx`/`_SAMPLE_GPX`) umstellen — deterministisch in jedem Checkout, keine neuen Fixtures nötig. `test_gpx_import_in_trip_dialog` macht das Muster mit `REAL_GPX_DIR` bereits vor. **test_weather_snapshot (2) ist ECHT-ROT** (Assertion inkompatibel mit #1133-Isolation): Assertion auf `get_data_root()`-relativ umstellen.

### K4 Mail-Drift — überwiegend veraltet, DREI ECHTE BEFUNDE
**Veraltet → löschen** (je mit datiertem Beleg #911/#912/#956/#995/#1003/#731/#1022): test_issue_623 (7), test_issue_561 (4), test_issue_669 (4), test_722 (2), test_884 (2), test_236 (2), test_906_907 (1), test_613 (1), test_997 (1). **Testfehler → Locator minimal fixen** (AC gültig UND erfüllt, nur Test-Locator kaputt): test_issue_911 (1), tests/visual/test_issue_956 (1).
**ECHTE BEFUNDE:**
1. **Profil-Signatur nie in HTML verdrahtet:** `src/output/renderers/email/html.py:782` nimmt `profile=` an, referenziert es nie — Eyebrow/SVG/Accent fehlen in jeder HTML-Mail (plain.py:103 macht es korrekt vor). Dreifach unabhängig bestätigt: test_email_profile_pipeline (11), test_issue_255 (2), test_issue_257 AC-8. Nutzersichtbar → Bug-Issue [triage:a] + xfail.
2. **Dual-Modul-Leck `app.loader` vs `src.app.loader`** (pythonpath src+.): #1133-Isolation patcht nur `app.loader`; `api/routers/validator.py:23` liest via `src.app.loader` UNISOLIERT echte Daten (test_952 rot; 4 weitere api/routers-Dateien mischen Importe). Isolation unterlaufbar = Datenrisiko → Bug-Issue [triage:b] + xfail.
3. **Gmail-Default vergessen:** `.claude/tools/output_validator.py:106` (`imap.gmail.com`, alte Env-Var-Namen) — Stalwart-Migration übersehen. test_imap_stalwart_migration GEMISCHT (Teil veraltet: referenziert gelöschtes test_html_email.py).

### K5 Telegram — KOMPLETT veraltet (22 rote, 9 Dateien)
Alle durch datierte Architektur-Entscheidungen erklärt (#1019 Registrierungs-Gate, #1250-S7a trips/→briefings/-Cutover, #697 On-Demand-Fetch, #731 CONFIG-Entfernung, #1133-Fixture). Kein NETBLOCK in K4/K5 — „Live-Abhängig" dort leer.

### Konsolidierte Kategorien-Bilanz (Stand vor K3/K6-Detail)
| Kategorie | rote Tests (ca.) | Aktion |
|---|---|---|
| Veraltet → löschen | ~200 (K1 126 + K4 24 + K5 22 + epic_404 16 + Teile) | Dateien/Testteile löschen, tabellarisch begründet |
| Testfehler → minimal fixen | ~48 (K2 42 + weather_snapshot 2 + 2 Locator + Einzelne) | Pfad-Konstanten, Assertions, Locator |
| Echter Befund → Issue + xfail | ~30 (Profil 13 + 384er 10 + 603er 5 + 952 1 + Gmail-Teil) | 4-5 Bug-Issues [triage:a/b/c], Tests xfail(reason='#N') |
| Live-Abhängig → Marker | 26 (K3, NETBLOCK-bestätigt) | email/live/staging-Marker, Muster 2a, Wächter erweitern |
| Rest K6 | ~60 | Detail-Triage läuft (4. Agent) |

### K3 Netz-Dialer — Marker-Zuordnung (Detail, Code-belegt)
| Datei | Ziel | Marker | Ebene |
|---|---|---|---|
| test_account_page.py | Prod-Domain (Go-API) | live | Modul (8/8, Konvention der Sibling-Files) |
| test_issue_1069_tier_channel_gating.py | Staging (Playwright) | staging | Teil: nur TestAC4/5/6; Rest offline (lokaler Stub) |
| test_feature_770_inca_nowcast_fix.py | GeoSphere INCA | live | Modul |
| test_issue_1037_massif_closure.py | Präfektur-API (FR) | live | Teil: nur _live_massifs/fetch-Tests |
| test_issue_1142_geosphere_direct_fallback.py | GeoSphere | live | Teil: AC-1/AC-2; AC-3/4 lokaler HTTP-Server |
| test_issue_645_telegram_outputerror_arity.py | Telegram-API | live | Teil: 2 rote; 3. Test dialt 127.0.0.1 |
| test_issue_731_unified_commands.py | Live-Nowcast-Kette | live | Teil: nur TestAC3HeuteMorgen |
| test_scheduler_triggers.py | IMAP-Polling | email | Teil: 2 inbound_commands-Tests |
| test_channel_test_button.py | echter SMTP-Versand | email | Teil: 1 von 6 |
| test_issue_608_sms_seven_io.py | seven.io | live | Teil: 1 Test |
| test_fix_853_842_837 (1 NETBLOCK-Test) | prod_selftest → Prod-Health | live | Teil: nur test_ac2 |
| test_issue_934_wizard_schedule.py (K6) | lokaler Stack 3001/8091 + Login | staging | Modul (ungemarkt, braucht laufende Umgebung) |
| test_issue_1035_vigilance_source.py (K6) | reale Vigilance-Lage | live | Teil/Modul (wetterlagenabhängig lt. Docstring) |

### K6 — Urteile (Detail siehe Agenten-Bericht; Kernpunkte)
**Veraltet → löschen:** test_bug_405 (6, Audit-Ordner weg), test_issue_892 (3, phase_listener weg), test_issue_403 (2, atoms.test.ts weg), test_bug_567 (1), test_bug_600 (1), test_epic_191_adversary_verschaerfung (1), test_epic_191_zeilenlimit (1), test_worktree_state_routing (1), test_epic_404 (16).
**Testfehler → minimal fixen:** test_alert_log (4) + test_briefing_log (4) (#1133-Fixture-Kollision), test_issue_829 (3, Env-Var-Rename GZ_→OPENSPEC_), test_622 (2, fehlender timeout-Override), test_914_slice4 (1, smtp.invalid ohne Timeout), test_utc_localtime (1, Formatdetail prüfen).
**Echte Befunde (Issue + xfail bzw. Direkt-Fix wo trivial/doku):** Profil-HTML (13) · 384-Fail-open (10) · 603-Design-Gate (5) · horizon_filter thunder-Spalte (1) · stage_weather_endpoint null-Serialisierung (1) · bug_497 SMS-Präfix (1) · report_config_render_contract (1) · issue_816 deviation-alert-Validator (1) · issue_883 nie implementiert (1) · feature_574 km-Header nie implementiert (3) · feature_734/761 Nowcast-Routing nie implementiert (5 → Epic #1127, existierende Issues #1143ff statt neuer) · 952/Dual-Modul-Leck (1) · issue_668 staging_gate-Dedup-Regression (2, Ex-#1132) · e2e_path_helper (1) · imap_stalwart Gmail-Rest (Teil) · Doku-Drift direkt fixbar: issue_316 (3), issue_1165 ADR-Duplikat (1), 753_746 + external_validator_auth (3, Plugin-Update d821e7c9 überschrieb Repo-Agent-Docs → wiederkehrende Regression, Plugin-Repo-Issue) · issue_277 CSS-Fallbacks (1) · test_765 Hygiene (3).
**tests/red/-Konzept:** dokumentiertes Known-Red-Backlog, laut Doku via `--ignore=tests/red/` vom Standard-Lauf ausgeschlossen — aber addopts enthält dieses ignore NICHT (Doku-Realitäts-Lücke). Behandlung: der 1 rote Test → xfail(reason auf Spec-Restpunkt), keine addopts-Änderung.
**Nicht anfassen:** test_compare_dispatch_channel_fanout (1) — #1301-Session, nur dokumentiert.

## Abschluss-Status (2026-07-18, Umsetzung komplett)

**AC-1 bewiesen:** Abschlussmessung (4 Etappen, Netz-Sperre): A=716 · B2=1708 · C2=950 · D=1257 = **4631 Tests, 0 failed, 0 errors** (JUnit-XMLs in docs/artifacts/rework-1211b-rot-triage/). Ausgangslage war 390 rot.

**Bilanz der 390:** 40 Dateien gelöscht (39 Batch 1 + je Teil-Löschungen in 465/384/fix_853/imap_stalwart/829) · ~50 Testfehler minimal gefixt (Batch 2 + Nachtriage + 4 Folge-Korrekturen: 734-live-Marker, 729-Inline-Helfer, 1014-Listen-Update, compare_fanout-xfail lt. AC-1) · 16 Dateien markiert (13 Batch 3 + 734 + 2a-Bestand) · 45+ xfail auf #1306–#1310/#1143/#1144/Spec-Restpunkt · Direkt-Fixes: frontend_components.md, ADR-Renumbering 0018→0027/0025→0028, test_765-Hygiene (3 Dateien auf Verhaltens-Assertions), Agent-Docs-Restaurierung (external-validator, user-story-planner; Ursache: agent-os-openspec#72).

**Spec-Wahrheits-Korrekturen:** trip_alert_stage_name hatte 5 (nicht 1) stale Wizard-Einträge (alle d7703708) · 23. Metrik kam mit #1135 (nicht #1278/#1296) · 603-Symptomatik invertiert (Gate blockt fälschlich NICHT — Nachtrag in #1307) · 257-AC-5 ist eigenständiger 6. Befund (Nachtrag in #1306) · 734 dialt real (live-Marker statt xfail; K6-Urteil korrigiert) · epic_404-Eintrag aus 2a-Wächter-Liste entfernt (Datei in 2b gelöscht).

**Adversary:** VERIFIED (HOLDS), 2 Runden, 0 Findings, 6/6 ACs.
