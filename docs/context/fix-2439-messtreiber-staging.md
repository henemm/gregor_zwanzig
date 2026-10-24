# Context: fix-2439-messtreiber-staging

## Request Summary
Der Staging-Messtreiber `.claude/tools/staging_messlauf.py` (PR #2596) kommt auf echtem Staging nicht über den Probelauf hinaus. Drei Defekte, die die Fake-Transport-Tests nicht sehen konnten. Ziel: Treiber so reparieren, dass die Live-Serie laufen kann und die Zusicherungen ehrlich auf dem Weg gemessen werden, auf dem sie wirken.

## Befunde (Beleg: Lauf 21.10. 16:02 UTC, Journal `gregor-python-staging`, Kommentar in #2439)
| # | Defekt | Beleg |
|---|--------|-------|
| 1 | `STANDARD_BASIS = http://127.0.0.1:8091` (`staging_messlauf.py:59`): Cookie `gz_session` ist `Secure`, über http kommt es nie zurück → `staging-token` 401. | Probe-Skript: https → `/api/trips` 200, 8091 → 401. `staging_befehl_pruefen.py:580` nutzt https. |
| 2 | Probelauf (`probelauf()`, Z. 355–373) sendet HEUTE dann MORGEN auf demselben Trip/Ort. HEUTE wärmt beide Tage vor (`phase=vorwaermen` 26 s, 32/143/114 Downloads), MORGEN liest nur Cache (`downloads=0 cache_treffer=217`, 1,1 s) → Probe meldet immer „warm". | Journal 16:03:44–47 |
| 3 | Korsika (`fr_direct`) ist auf Staging nicht kalt messbar: `src/app/egress_guard.py:48` sperrt `public-api.meteofrance.fr` (BLOCKED, #1337/#1348, seit 22.07.). `fr_direct_fenster downloads=0 cache_treffer=0`, Gewitter aus Ersatzquelle `eu_direct`. | Journal 16:03:57ff. |

Nebenbefund: Die „Korsika max 37,8 s" aus dem Kommentar vom 19.10. lief über `eu_direct`, nicht über Météo-France.

## Related Files
| File | Relevanz |
|------|----------|
| `.claude/tools/staging_messlauf.py` | Treiber: `STANDARD_BASIS`, `probelauf`, `serien`, `sende_korsika`, `setze_ort` |
| `.claude/tools/staging_befehl_pruefen.py` | Gemeinsame Staging-API (`StagingApi`, https-Default Z. 580) |
| `.claude/tools/befehl_messlogik.py` | `kalt_laeufe` (Kalt = Fensterzeile `downloads>0` im Befehlsfenster) |
| `tests/e2e/test_push_eingang_befehle_staging.py` | Live-Test; `test_ac5_…korsika…` verlangt ≥3 kalte `fr_direct_fenster`-Läufe auf Staging → kann dort nie grün werden |
| `tests/tdd/test_staging_messlauf.py` | Kerntests des Treibers (Fake-Transporte, sehen keinen der 3 Defekte) |
| `docs/specs/modules/feat_2439_staging_messtreiber.md` | Spec (AC-1 Probelauf, AC-3 Korsika-Abstand, AC-9 Env-Ausgabe) |
| `docs/specs/modules/feat_2439_befehle_antwortzeit.md` | AC-5 (Korsika `fr_direct`, kalt, <60 s „auf Staging") — Quelle der unerfüllbaren Zusicherung; Z. 172: „erste Messung auf Staging" |
| `src/app/egress_guard.py` | Sperrliste; bewusst NICHT lockern (würde #1348 kippen, bräuchte ADR) |

## Existing Patterns
- Serie DE wechselt vor jedem Lauf den Ort (`setze_ort`, Read-Modify-Write) → jeder Lauf kalt. Nur der Probelauf tut das nicht.
- Prod-Messungen laufen über `.claude/tools/befehl_antwortzeit.py` (Lese-Werkzeug, kein Test).

## Dependencies
- Upstream: Staging-Go-API (https), Stalwart-Testpostfach, Journal `gregor-python-staging`, `GZ_*` aus `/home/hem/gregor_zwanzig_staging/.env`.
- Downstream: Live-Test `test_push_eingang_befehle_staging.py`; Schließbarkeit von #2439 (AC-3/4/5/12 antwortzeit, AC-12/15 prod_scharf).

## Existing Specs
- `feat_2439_staging_messtreiber.md` (Treiber), `feat_2439_befehle_antwortzeit.md` (Zielgrößen), `feat_2439_push_eingang_prod_scharf.md` (Prod-Hooks, Messwerkzeug).

## Risks & Considerations
- **Korsika-Zusicherung (AC-5 antwortzeit) ist auf Staging strukturell unerfüllbar.** Optionen: (a) Korsika-Kaltmessung auf Prod verlegen (Lese-Werkzeug / ein echter Korsika-Befehl), Staging misst nur die Ersatzquelle ehrlich als solche; (b) Sperre lockern — verworfen. Das ist eine Spec-/AC-Änderung ⇒ PO-Freigabe der Neufassung auf Deutsch.
- Probelauf-Fix: vor MORGEN Ort wechseln (eigener Probe-Ort), sonst bleibt die Probe zwangsläufig warm. Serie prüfen: HEUTE→MORGEN auf gleichem Ort innerhalb Cache-TTL wäre derselbe Defekt (Serie wechselt schon pro Lauf).
- Neuer AC: echter Probelauf gegen Staging endet in Exit 0 (die drei Defekte existieren nur gegen echtes Staging).
- Aufräumen Lauf 2: kein BEFUND ausgegeben → vermutlich sauber, Datenbestand für `hem` nicht lesbar (nicht belegt). Verwaister Nutzer `gzp-211602-803fe7ae` steht in #1199.
- Im Worktree: Test per benannter Datei, `--disable-socket`.

## Analysis

### Type
Bug (Werkzeug-Defekt im Staging-Messtreiber, nutzersichtbar nur indirekt: blockiert die Schließbarkeit von #2439). Alle drei Befunde am Code gegengelesen (21.10.): `STANDARD_BASIS` http://127.0.0.1:8091 (`staging_messlauf.py:59`); `probelauf()` sendet HEUTE→MORGEN auf demselben Trip (Z. 355–373); Probelauf verlangt `fr_direct_fenster`-Kaltlauf für Korsika (`quellen=("fr_direct_fenster",)`) — auf Staging wegen `egress_guard` nie erfüllbar, also scheitert der Probelauf auch nach Fix 1+2 weiterhin.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/tools/staging_messlauf.py` | MODIFY | Basis auf https-Staging-Host; Probe: Ort-Wechsel vor MORGEN (`setze_ort`); Korsika-Probe nicht mehr auf `fr_direct`-Kaltlauf, sondern ehrlich als Ersatzquelle (`eu_direct`) klassifizieren; Serie Korsika prüfen |
| `tests/tdd/test_staging_messlauf.py` | MODIFY | Tests für alle drei Defekte (Basis-Schema Secure-Cookie-tauglich, Probe wechselt Ort, Korsika-Probe ohne fr_direct-Pflicht) |
| `tests/e2e/test_push_eingang_befehle_staging.py` | MODIFY | `test_ac5` Korsika: Staging misst nur Ersatzquelle; `fr_direct` kalt nicht mehr gefordert |
| `docs/specs/modules/feat_2439_staging_messtreiber.md` | MODIFY | AC-1 (Probelauf) neu fassen; neuer AC: echter Probelauf gegen Staging endet Exit 0 |
| `docs/specs/modules/feat_2439_befehle_antwortzeit.md` | MODIFY | AC-5 Korsika: Kaltmessung `fr_direct` nach Prod verlegen (Lese-Werkzeug `befehl_antwortzeit.py`), Staging nur Ersatzquelle |
| `src/app/egress_guard.py` | KEIN CHANGE | Sperre bewusst nicht lockern (#1348, bräuchte ADR) |

### Scope Assessment
- Files: 3 Code/Test + 2 Specs
- Estimated LoC: +90/-30 (ohne Specs)
- Risk Level: LOW — reines Messwerkzeug, kein Produktpfad; Korsika-Teil ist Spec-Änderung (PO-Freigabe)

### Technical Approach
1. `STANDARD_BASIS` = `https://staging.gregor20.henemm.com` (wie `staging_befehl_pruefen.py:580`); Env-Override bleibt.
2. Probe: vor MORGEN mit `setze_ort` auf zweiten Probe-Ort wechseln, damit der Lauf wirklich kalt ist (Serie wechselt schon pro Lauf — unverändert).
3. Korsika auf Staging: Probe prüft `Dauerzeile vorhanden` + Gewitterquelle `eu_direct` (Ersatz) statt `fr_direct`-Kaltlauf; Korsika-Kaltmessung <60 s mit `fr_direct` ist Prod-Aufgabe.
4. Neuer AC: Probelauf gegen echtes Staging (Live-Schicht) → Exit 0; Fake-Transport-Tests allein sahen die Defekte nicht (Mock-Theater-Lücke).

### Dependencies
- Upstream: Staging-Go-API (https), Stalwart-Testpostfach, Journal `gregor-python-staging`, `/home/hem/gregor_zwanzig_staging/.env`.
- Downstream: Live-Test AC-5/AC-3 Befehle-Antwortzeit; Schließbarkeit #2439 (Rechenzeit-Scheibe b).
- Parallelsitzungen: keine mit #2439 (`sessions` geprüft); kein weiterer #2439-Commit auf origin/main nach #2596.

### Open Questions
- [ ] PO-Freigabe (Phase 3, auf Deutsch): AC-5 Korsika-Kaltmessung `fr_direct` von Staging nach Prod verlegen — Staging misst nur die Ersatzquelle `eu_direct` und kennzeichnet das offen.
