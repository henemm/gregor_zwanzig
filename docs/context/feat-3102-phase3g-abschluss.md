# Kontext: feat-3102-phase3g-abschluss

Issue #3102 („Einstellung = Mail, Phase 3g: Abschluss"), Teil von Epic #3058 (Phase 3 von #3047).
Grundlage: ADR-0121 Nr. 2, 7, 8 und Nachträge; ADR-0124 (Tabelle „Was steht wo", `display_config.placements`).

## Request Summary

Issue-Text (Stand Anlage 2026-11-16): (a) Bestandsdaten per Read-Modify-Write mit Merge auf die
kanonische Form migrieren (Pre-Snapshot, ADR-0101), (b) Differenztest-Orakel und überflüssige
Lese-Adapter löschen, (c) Import-Sperre (Test) gegen Rückkehr gelöschter Altfunktionen.
Abschlusskriterium Epic #3058: Prüfkatalog aller vier Kanäle grün, keine `offen_feature`-Fälle aus Phase 3.

## Ist-Stand 2026-11-26 (wichtigster Befund: (a)–(c) sind großteils erledigt)

| Teil | Stand | Beleg |
|---|---|---|
| (a) Migration | **erledigt durch #3157 und #3351** (beide CLOSED). ADR-0124 Folgepflichten: „Die schreibende Migration aus #3102 geht im Bau zu #3122 auf." | `docs/adr/0124-was-steht-wo-eine-tabelle.md:58`; Skript `scripts/migrate_3277_altfelder.py` (RMW+Merge, Backup, Lock, `--nachzaehlen`, Zeile 153/159); Spec `docs/specs/modules/feat_3351_altfelder_datenlauf.md` (sagt: #3102 erst schließen, wenn Orakel-Löschung, Import-Sperre, Prüfkatalog belegt) |
| (b) Orakel | Die in `feat_3096_mail_resolver.md:131,167` genannten Orakel-Tests (`test_3057_channel_list_resolver.py`, `test_3065_ausblick_stundenverlauf_resolver.py`) **existieren nicht mehr**. Das heutige `tests/helpers/einstellung_auslieferung_orakel.py` baut die Erwartung aus rohem JSON und importiert keinen Altpfad (kein Altpfad-Orakel im Sinne ADR-0121 Nr. 8). | grep tests/ |
| (b) Lese-Adapter | Resolver liest nur `placements` (`src/services/channel_list_resolver.py:61-84`, `src/services/placements.py:97`). Ohne gespeicherte Tabelle: `placements_aus_grundauswahl` (`placements.py:273-293`) + `_heute_ohne_einstellung` (`:311-342`) — das ist kein Altfeld-Leser, sondern die Anlage-Vorbelegung aus der Grundauswahl (liest `format_mode`/`use_friendly_format` der Grundauswahl-Einträge, die weiterhin das lebende Datenmodell der Trip-Grundauswahl sind, `src/app/models.py:683-689`, `src/app/loader.py:60-91`). Altfelder (`channel_layouts`, `channel_active_metrics`, `outlook_metrics`, `hourly_metrics` …) stehen nur noch in `ALTFELDER` (`src/app/loader.py:142-147`), kein Leser. | |
| (c) Import-Sperre | **existiert**: `tests/test_altpfad_import_sperre.py` (AST über src/api/hooks/scripts, `VERBOTEN` Zeile 28-46, leeres `ERLAUBT` mit Ablauf, Selbsttest) und `tests/test_altfeld_namen_sperre.py` (Altfeld-Namen, #3277). | |
| Prüfkatalog | Lokal 2026-11-26: Trip/Orte/Fallliste/Validatoren + beide Sperren: **741 passed, 5 xfailed**. | `uv run pytest tests/tdd/test_einstellung_gleich_mail_{trip,orte,fallliste,validatoren}.py tests/test_altpfad_import_sperre.py tests/test_altfeld_namen_sperre.py` |

## Was tatsächlich offen ist

1. **Fünf `offen_feature`-Fälle „P7 global nachträglich"** (Konzept §5 Punkt 6, #3047 Nachprüfung Punkt 7):
   - `fallliste_trip.json:2247-2268` — `trip-p7--global_nachtraeglich-trip_{stundentabelle,ausblick}--html`
   - `fallliste_orte.json:~1983-2007` — `O-p7--global_nachtraeglich-orte_{vergleichstabelle,stundenverlauf,ausblick}--html`
   - Tests: `tests/tdd/test_einstellung_gleich_mail_trip.py:998-1025` (`_p7_faelle`, xfail strict, Grund „#3065 Phase 2: Abwahl nicht persistiert" — veraltet), `tests/tdd/test_einstellung_gleich_mail_orte.py:757-790`.
   - **Befund:** Die Tests bauen das Szenario noch über Altfelder (Orte: `channel_active_metrics`, `hourly_metrics`, `outlook_metrics`; Trip: `channel_layouts.email`/`outlook_metrics`, die `_wunsch_als_tabelle` in `tests/tdd/_einstellung_gleich_mail_trip_fixtures.py:77-109` mit der END-Grundauswahl inkl. `uv_index` in eine Tabelle übersetzt → `uv_index` bekommt dort eine Zeile mit Haken aus). Damit modellieren sie „vor dem Einschalten gespeichert" falsch.
   - Das Datenmodell ADR-0124 Nr. 5 löst P7 fachlich: fehlende Zeile = angehakt; `_ordered_rows` (`placements.py:172-192`) hängt jede Grundauswahl-Metrik ohne Zeile hinten an, „überall an". Die Datenmodell-Entscheidung, die der Fall-Verweis fordert, ist mit ADR-0124 gefallen.
   - Zu klären in der Analyse: ob `hourly`/`outlook` für eine Metrik ohne Zeile tatsächlich „an" sind (`_cell` `placements.py:149-158`: an, außer `place is False`, `locked` oder E-Mail aus) und ob die Mail sie dann zeigt (Orte-Stundenverlauf, Ausblick-Spaltensatz).
2. **Rest-Fall `fallliste_editor.json:427`** `D-trip_vorlage-reihenfolge-frontend` → Verweis #3368 (OPEN, Widerspruch zweier freigegebener Regeln, PO-Thema). **Nicht Phase 3**, bleibt `offen_feature` mit Verweis.
3. **Doku-Nachzug:** Specs `feat_3096` (Orakel bleibt bis #3102), `feat_3097:164`, `feat_3098:47,82,175`, `feat_3099:48,178`, `feat_3059:33` verweisen Arbeit an #3102, die erledigt ist; ADR-0121 Nr. 7/8 und Kopf brauchen Nachtrag „eingelöst durch #3157/#3351/#3237/#3277".
4. **Nachweis Produktionsdaten:** `migrate_3277_altfelder.py --nachzaehlen` gegen Prod/Staging als Beleg „keine Altfelder übrig" (lesend).

## Related Files

- `src/services/channel_list_resolver.py`, `src/services/placements.py`, `src/services/placements_view_service.py`
- `src/app/loader.py` (`ALTFELDER`, `_resolve_format_mode`), `src/app/models.py`
- `src/output/renderers/compare_hourly_metric_ids.py` (`resolve_hourly_metrics`, `resolve_hourly_metric_ids` — lebend, Vorgabemenge, nicht löschbar)
- Tests: `tests/tdd/test_einstellung_gleich_mail_{trip,orte,fallliste}.py`, `tests/tdd/_einstellung_gleich_mail_trip_fixtures.py`, `tests/helpers/tabelle_aus_wunsch.py`, Fixtures `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte,editor}.json`
- Sperren: `tests/test_altpfad_import_sperre.py`, `tests/test_altfeld_namen_sperre.py`
- Fallliste-Validator: `tests/tdd/test_einstellung_gleich_mail_fallliste.py:41,54,505,572` (Status-Allowlist, Verweis-Regel)

## Existing Patterns

- `xfail(strict=True)` für `offen_feature`; bei Umsetzung Status auf `gruen`, xfail entfällt (#3047 J2).
- Testdaten im Tabellenformat über `tests/helpers/tabelle_aus_wunsch.py` (`tabelle(dc, surface, listen=…, folge=…)`).
- Migrationen: `scripts/migrate_*.py` mit `--nachzaehlen`; Pre-Snapshot-Hook `.claude/hooks/data_schema_backup.py` (SCHEMA_PATHS: `internal/model/`, `internal/store/store.go`, `src/app/models.py`, `src/app/trip.py`, `src/app/loader.py`).

## Dependencies / Dependents

- Abhängig: #3122 (OPEN, Bau der Tabelle; Migration darin aufgegangen), #3157/#3351/#3237/#3277 (CLOSED).
- Danach: Epic #3058 schließbar (alle Sub-Issues 3a–3g zu), dann #3047 prüfen.

## Risks

- **Scope-Falle:** Das Issue nennt Arbeit, die schon getan ist. Keine zweite Migration, kein erneutes Löschen; nur Restfälle + Nachweis + Doku.
- P7 könnte in einer Stelle (Orte-Stundenverlauf/Ausblick: feste Spaltensätze, `HOURLY_DEFAULT_METRIC_IDS`) echt rot bleiben → dann echte Code-Änderung im Resolver/Renderer nötig (Mail-Inhalt ⇒ Renderer-Commit-Gate, Mail-Validator).
- Fachlich: „global nachträglich eingeschaltet erscheint überall" ist Konzept §5 Punkt 6 + ADR-0124 Nr. 5 (PO-freigegeben); keine neue PO-Entscheidung, solange das Verhalten dem entspricht.
- Cross-User: P7-Tests bleiben mit frischem Profil; kein `"default"`.

## Analysis

**Type:** Feature-Abschluss (Nachweis + Aufräumen), keine Produktions-Code-Änderung.

**Kernbefund (lauffähig belegt, Scratch-Probe 2026-11-26):** Tabelle gespeichert OHNE `uv_index`, danach
`uv_index` in die Grundauswahl → Resolver und echte Mail zeigen `uv_index` in Trip E-Mail/Ausblick/Telegram/SMS
und Orte Vergleichstabelle/Stundenverlauf/Ausblick (Orte-Ausblick nur im Abendbriefing, weil
`outlook_reports`-Vorbelegung = Abend). Produktion erfüllt P7 also schon (ADR-0124 Nr. 5, `_ordered_rows`
`src/services/placements.py:172-192`, `_cell` `:149-158`; `uv_index` an keiner Stelle gesperrt,
`stellen_sperre` `src/app/metric_catalog.py:1343-1360`). Die 5 xfail sind falsch modelliert: die Übersetzer
`_wunsch_als_tabelle` (`tests/tdd/_einstellung_gleich_mail_trip_fixtures.py:77`) bzw.
`orte_wunsch_als_tabelle` (in `sende_orte_mail`, `tests/helpers/einstellung_gleich_mail_orte.py:~229`)
bauen die Tabelle aus der END-Grundauswahl → `uv_index` erhält eine Zeile mit Haken aus = bewusste Abwahl.

**Affected Files**

| Datei | Change | Grund |
|---|---|---|
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | RED-Wächter: kein `offen_feature`-Fall der echten Falllisten darf auf Phase 3 verweisen (`#3058`, `#3065`, `#3096`–`#3102`, „Phase 3", „ADR zu ADR-0050"); Selbsttest synthetisch. #3368 (Editor-Fall) bleibt erlaubt. |
| `tests/tdd/test_einstellung_gleich_mail_trip.py` | MODIFY | P7 (998-1025): Tabelle aus ALTER Grundauswahl speichern, dann `uv_index` dazu; Vorbedingung prüfen (`uv_index` hat keine Zeile); xfail weg. |
| `tests/tdd/test_einstellung_gleich_mail_orte.py` | MODIFY | P7 (757-790): dito; `sende_orte_mail` übersetzt nur ohne gespeicherte `placements` (prüfen!), Ausblick mit `briefing="evening"`; `_offen` nur entfernen, wenn unbenutzt. |
| `tests/fixtures/einstellung_gleich_mail/fallliste_trip.json`, `fallliste_orte.json` | MODIFY | 5 Fälle `offen_feature` → `gruen`, Verweis auf ADR-0124 Nr. 5 (Schema-Regeln der Fallliste beachten). |
| Doku (eigener `docs:`-Commit) | MODIFY | ADR-0121 Nachtrag (Nr. 7/8 eingelöst durch #3157/#3351/#3237/#3277), ADR-0124:58, Specs feat_3096/3097/3098/3099/3059/3122/3277/3351: Verweise „bis #3102" als erledigt markieren. |

**Scope/Risk:** ~120 LoC Tests + ~30 Zeilen Doku; Risiko niedrig (keine Mail-Änderung, kein Datenlauf).
Hauptfalle: falsch-grün, wenn die „alte" Tabelle doch `uv_index` enthält → Vorbedingungs-Assert Pflicht.

**Technical Approach:** Variante A (Plan-Agent): Wächter = RED, P7 neu auf gespeicherter Tabelle, Status grün.
Verworfen: B (zusätzlicher Altfeld-Schreib-Wächter für Tests: kollidiert mit den bewusst beschreibenden
Altfeldern der Fixtures, Fehlalarme), C (nur xfail entfernen: kein RED, Fixtures bleiben falsch),
D (Produktionsänderung: unnötig).

**Nachweis Produktion:** `scripts/migrate_3277_altfelder.py --nachzaehlen` (lesend) auf Staging/Prod im Deploy,
Zahl in den Abschluss-Kommentar von #3102; danach Epic #3058 prüfen/schließen. #3368 bleibt ausdrücklich draußen.

**Open Questions:** keine PO-Frage — Verhalten „später eingeschaltete Größe steht überall" ist Konzept §5
Punkt 6 / ADR-0124 Nr. 5 (freigegeben).
