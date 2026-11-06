# Context: fix-2771-2833-wackel-kerntests

## Request Summary
Der CI-Job `test` auf `main` wird zufällig rot (06.11.2026: zwei Läufe hintereinander, je ein anderer Test).
Ziel: die drei belegten Wackler im deterministischen Kern (Epic #1196) robust machen, ohne ihre Zusicherung zu entwerten.
#2744 (uhrzeitabhängige Tests kurz vor UTC-Mitternacht) ist bewusst NICHT Teil dieses Workflows (eigener Durchgang).

## Die drei Wackler

| Issue | Test | Beobachtung | Ursache (Stand Intake) |
|---|---|---|---|
| #2833 | `tests/tdd/test_compare_alert_preview_sprache_je_nutzer.py::test_vorschau_spricht_die_sprache_des_kontos[abweichung]` | CI-Lauf 42185451624 (`854dbfcde`): Timeout > 30 s | Stack endet in `TelegramOutput._reserve_send_slot` → `time.sleep` (`src/output/channels/telegram.py:399`). Die Drossel-Buchhaltung `TelegramOutput._rate_limit_stamps` ist ein **Klassenattribut** (prozessweit, 18 Sendungen je Chat / 60 s, `telegram.py:351-376`) und wird zwischen Tests nie geleert. Senden Tests im selben Worker binnen 60 s > 18× an denselben Chat-Schlüssel, wartet der nächste Versand bis zu 60 s Wanduhr. |
| #2771 (1) | `tests/test_meteofrance_fenster_zeile.py::test_ac14_warmer_abruf_aus_dem_zwischenspeicher_hat_null_downloads` | CI-Lauf 42179724862 (`5fb07bbc8`): „zweiter Abruf ging doch ans Netz“; lokal ~1 von 6 rot | `_abruf()` (Testdatei Z. ~88) bildet `start = datetime.now(timezone.utc)` **je Aufruf neu**. Im Provider ist `base = max(start, run)` (`src/providers/meteofrance.py:~716`), `time_str = (base + offset h).strftime("%Y-%m-%dT%H:%M:%SZ")` steht im Cache-Schlüssel (`speicher.get(coverage_id, time_str, bbox)`). Liegt zwischen erstem und zweitem Abruf ein Sekundenwechsel, unterscheiden sich die Schlüssel → Cache-Fehlgriff → Download. Hypothese, in der RED-Phase rot nachzuweisen. |
| #2771 (2) | `tests/tdd/test_provider_request_deadline.py::test_geosphere_fetch_combined_nwp_frist_bricht_ab_ohne_leeres_ergebnis` | `fetch_combined() brauchte 1.12s -- erwartet < 0.9s` | Wanduhr-Obergrenze `0.2 <= elapsed < 0.9` (Z. 1869) bei Frist 0,45 s. Die Grenze soll „Frist greift (~0,45 s)“ von „Frist fehlt (Timeout 5 s / Backoff 40 s+)“ trennen; 0,9 s lässt unter Runner-Last zu wenig Luft. |

## Related Files
| File | Relevance |
|------|-----------|
| `tests/conftest.py` | Root-Fixtures; enthält bereits autouse-Resets für Prozess-Singletons (`_reset_shared_radar_cache` Z. ~649, `_reset_thunder_window_cache` Z. ~664, `_reset_shared_weather_cache`). Ort für einen Reset der Telegram-Drossel. |
| `src/output/channels/telegram.py` | `_rate_limit_stamps` / `_rate_limit_lock` (Klassenattribute), `_reserve_send_slot`, `SEND_SLOT_MAX_WAIT_SECONDS = 30.0` |
| `tests/tdd/_befehl_e2e_fixtures.py:527` | Einzelner Test-Helfer setzt schon `monkeypatch.setattr(TelegramOutput, "_rate_limit_stamps", {})` — Präzedenz, aber nicht global |
| `tests/tdd/test_telegram_rate_limit.py` | Verhaltenstests der Drossel (setzen eigene Settings/Chats); dürfen durch einen globalen Reset nicht entwertet werden (Reset VOR jedem Test, innerhalb eines Tests bleibt die Buchhaltung erhalten) |
| `tests/tdd/test_telegram_post_is_single_guarded_exit.py:334` | prüft `_rate_limit_stamps == {}` — kompatibel mit Reset |
| `tests/test_meteofrance_fenster_zeile.py` | `_abruf` mit `datetime.now()` je Aufruf |
| `src/providers/meteofrance.py` | `_fetch_coverage_signals_multi` (Z. ~615–800), Cache-Schlüssel mit Sekunden |
| `src/providers/thunder_window_cache.py` | geteilter Fensterspeicher, Schlüssel `(groesse, zeitschritt, rechteck)`, TTL 600 s |
| `src/providers/thunder_enrichment.py:430` | produktiver Aufrufer `sammeln([location], von, bis)` — ob `von` Sekunden trägt, ist in der Analyse zu klären (mögliche Produktions-Folge: geteilter Speicher greift nicht über Orte hinweg) |
| `tests/tdd/test_provider_request_deadline.py` | viele weitere Wanduhr-Grenzen (`< 0.9`, `< 0.4`, …); nur der beobachtete Wackler ist im Umfang |

## Existing Patterns
- Prozess-Singletons werden je Test per autouse-Fixture in `tests/conftest.py` zurückgesetzt (vor und nach dem Test).
- Wanduhr-Zusicherungen trennen „Frist greift“ von „Frist fehlt“; die Fehlerwerte liegen um Größenordnungen höher (5 s, 40 s+).
- Testpolitik: keine Mocks der eigenen Annahme, kein skip/xfail, globale pytest-timeout-Grenze (30 s) bleibt unverändert (#2806).

## Dependencies
- Upstream: pytest-timeout (30 s global), pytest-xdist-Worker (Prozess-Singletons gelten je Worker), freezegun nicht im Spiel.
- Downstream: alle Tests, die Telegram senden (globaler Reset betrifft sie), alle CI-PRs (Merge-Regel: 6 Checks grün).

## Existing Specs
- `docs/specs/modules/feat_2439_push_eingang_prod_scharf.md` (AC-14, `fr_direct_fenster`)
- Telegram-Drossel: #1370 / #1448 (Spec-Verweise in `telegram.py`)

## Risks & Considerations
- Ein globaler Reset darf die Drossel-Tests nicht entwerten: Reset nur an Testgrenzen.
- Météo-France: Falls Produktionsaufrufer `start` mit Sekunden übergeben, ist es auch ein Produktionsbefund (Cache-Treffer über Orte hinweg selten). Dann eigenes Issue, nicht still mitfixen.
- Fristtest: Grenze so weit lockern, dass Runner-Last nicht trifft, aber deutlich unter 5 s bleibt (Mutation „Frist entfernt“ muss rot bleiben).
- #2744 bewusst außerhalb (eigener Durchgang).

## Analysis

### Type
Bug (Test-Stabilität, deterministische Kern-Schicht, Epic #1196). Kein Produktionscode-Fehler in allen drei Fällen.

### Vorgehen dieser Phase (Abweichung vermerkt)
Statt bug-intake- und Plan-Subagenten direkte Code-Lektüre plus Messungen im Hauptkontext (Umfang klein und lokalisiert, Kontext-Budget). Gegenprüfung durch den Advisor. Die Intake-Hypothese zu #2833 wurde dabei **widerlegt** (siehe unten).

### Befund je Wackler

**#2833 — Telegram-Drossel im Vorschau-Sprachtest (Intake-Hypothese widerlegt)**
- Ein globaler Reset der Drossel existiert bereits: `tests/conftest.py:693` `_reset_telegram_rate_limit` (autouse, #1370), nutzt `reset_telegram_rate_limit_for_tests()` (`telegram.py:744`). Gemessen: vor jedem Fall ist `_rate_limit_stamps == {}`.
- Tatsächliche Ursache: der Fall `[abweichung]` verbraucht **allein genau 18** Drossel-Plätze am Chat `99999` (gemessen per Hook-Plugin, serieller Lauf): 3 Sprachdurchläufe (en, de, en) × 2 Referenz-Sendungen je `_stable` × 3 Blasen (3 Orte) = 18 = Standardgrenze `telegram_rate_limit_max_per_window` (`config.py:265`).
- `_stable` (`tests/tdd/test_alert_preview_compare_paritaet.py:134`) wiederholt Referenz→Vorschau→Referenz bis zu 3×, wenn sich die Referenz zwischen den Läufen ändert (Minutenwechsel). Jede Wiederholung kostet 6 weitere Plätze → 19. Sendung → `_reserve_send_slot` wartet bis `SEND_SLOT_MAX_WAIT_SECONDS` (30 s) → pytest-timeout 30 s schlägt zu. Deckt sich mit dem CI-Stack (`time.sleep` in `_reserve_send_slot`).
- Geschwister nahe der Grenze: `test_compare_deviation_alert_preview_equals_dispatch_projection[acht-orte-sms-gekuerzt]` = 16 Plätze (eine `_stable`-Wiederholung → 24+ → gleicher Hänger).
- Die Drossel ist in diesen Paritätstests **nicht Prüfgegenstand** (eigene Drossel-Tests: `test_telegram_rate_limit.py`, `test_send_slot_and_fetch_deadline.py`).
- Präzedenz für die Lösung: `tests/helpers/kanal_fake_transporte.py:132` setzt `"telegram_rate_limit_max_per_window": 10_000` in den Test-Settings.

**#2771 (1) — Météo-France warmer Abruf**
- Bestätigt per Code-Lektüre: `_abruf()` (`tests/test_meteofrance_fenster_zeile.py:88`) bildet `start = datetime.now(timezone.utc)` je Aufruf neu; `base = max(start, run)` (`meteofrance.py:717`), `time_str` mit Sekunden im Cache-Schlüssel (`meteofrance.py:735-739`). Sekundenwechsel zwischen den beiden Abrufen ⇒ anderer Schlüssel ⇒ Download.
- **Kein Produktionsbefund:** der produktive Aufrufer übergibt eine volle Stunde (`thunder_enrichment.py:94-97`, `_bezugszeitpunkt` setzt `minute=0, second=0`). Kein eigenes Issue nötig.

**#2771 (2) — GeoSphere-Fristtest**
Messung (dieser Rechner, Testaufruf inkl. Server-Aufbau, 16 Läufe, je 8 parallel):

| Variante | Dauer | Quelle |
|---|---|---|
| Frist greift, unbelastet/8-fach parallel | 0,64–0,77 s (Median ~0,66 s) | Messung `--durations` |
| Frist greift, CI-Runner unter Last | 1,12 s (Ausreißer, rot) | CI-Log aus #2771 |
| Frist fehlt (Mutation) | ≥ 5,0 s je Versuch (`timeout=5.0`), mit Backoff 40 s+ | Docstring Z. 1857-1860, Test-Setup Z. 1863 |
| heutige Grenze | < 0,9 s | Z. 1869 |

Geschwister in derselben Datei mit derselben Form (`timeout=5.0, frist=0.45`, Grenze 0,9 s): Z. 1723/1732 (gleicher Fehlermodus). Weitere Wanduhr-Grenzen (`< 0.9` bei Z. 357, 425, 527, 562, 1081, 1144, 1313, 1375, 1441, 1772, 1955, Z. 1761 mit `timeout=0.5`, Z. 2021 mit `timeout=0.2`) haben teils kleine Timeouts, bei denen eine lockere Grenze die Mutation „Frist fehlt" verschlucken würde → je Test eigene Abwägung, **nicht** in diesem Workflow, sondern Eintrag in Nebenbefund-Triage #1199.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_alert_preview_compare_paritaet.py` | MODIFY | `_Wire`-Settings (Z. ~233): `telegram_rate_limit_max_per_window` hoch setzen (Präzedenz `kanal_fake_transporte.py:132`); wirkt für Paritäts- und Sprachtest, da beide `wire` nutzen |
| `tests/test_meteofrance_fenster_zeile.py` | MODIFY | `start` einmal je Test bilden (auf volle Stunde wie Produktion) und beiden Abrufen übergeben |
| `tests/tdd/test_provider_request_deadline.py` | MODIFY | Obergrenze für die beiden `timeout=5.0`-Fälle (Z. 1732, 1869) auf einen Wert klar zwischen Last-Messung und 5 s (Empfehlung < 3,0 s), Meldungstext/Docstring angleichen |
| RED-Testdatei(en) für #2833/#2771 | CREATE | deterministischer Nachweis (s. RED-Plan) |

### Scope Assessment
- Files: 3 MODIFY + 1–2 CREATE (nur Tests)
- Estimated LoC: +60/-10
- Risk Level: LOW (kein Produktionscode; Gefahr nur: Zusicherungen entwerten → durch Mutationsproben abgesichert)

### Technical Approach (Empfehlung)
1. **#2833:** Drossel-Grenze in der Paritäts-Prüfstrecke (`_Wire.settings`) auf 10 000 heben, nicht den Reset erweitern (der existiert schon) und nicht `_stable` umbauen. Begründung: die Drossel ist dort nicht Prüfgegenstand, die Präzedenz existiert, und die Lösung wirkt für alle `wire`-Nutzer (inkl. `acht-orte`-Fall).
2. **#2771 (1):** `start` einmal je Test, auf volle Stunde gekürzt (spiegelt `_bezugszeitpunkt`), an beide `_abruf`-Aufrufe übergeben.
3. **#2771 (2):** Grenze für die zwei `timeout=5.0`-Fristtests auf < 3,0 s (≈ 2,7× CI-Ausreißer, 40 % unter dem Mutationswert 5 s). Untergrenze 0,2 s bleibt.

### RED-Plan (für `/30-write-spec` und `/40-tdd-red`)
- **#2833:** deterministisch rot durch einen Test, der über die echte `wire`-Prüfstrecke eine `_stable`-Wiederholung erzwingt (z. B. Referenz, die beim ersten Paar abweicht) bzw. die `[abweichung]`-Sendefolge einmal zusätzlich ausführt, mit enger Zeitgrenze (z. B. `@pytest.mark.timeout(10)`); heute hängt er in der Drossel, nach Fix grün.
- **#2771 (1):** RED durch erzwungenen Sekundenwechsel zwischen den beiden Abrufen (warten bis zum nächsten Sekundenbeginn, ≤ 1 s) — heute immer rot („zweiter Abruf ging doch ans Netz"), nach Fix grün.
- **#2771 (2):** kein natürlich roter Test möglich. Nachweis = Messverteilung (Tabelle oben) + Mutationsprobe „Frist entfernt" muss mit neuer Grenze rot bleiben (Adversary-Pflicht).

### Befunde gegen den Plan
- Grenze 10 000 im `wire` könnte eine künftige Regression „Vorschau-Versand sendet zu viele Blasen" verdecken — nein: Blasenzahl wird über `telegram_bubbles` verglichen, nicht über die Drossel.
- Erzwungene `_stable`-Wiederholung im RED-Test darf nicht `_stable` selbst mocken (Testpolitik) — RED muss über die echte Sendefolge laufen.

### Dependencies
- pytest-timeout (30 s global, unverändert, #2806), xdist (Singletons je Worker), keine Produktionsabhängigkeit.

### Open Questions
- keine (alle Entscheidungen technisch; #2744 bleibt außerhalb)
