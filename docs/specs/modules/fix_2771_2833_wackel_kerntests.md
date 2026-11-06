---
entity_id: fix_2771_2833_wackel_kerntests
type: module
created: 2026-11-06
updated: 2026-11-06
status: draft
version: "1.0"
tags: [tests, stabilitaet, kern-schicht, epic-1196]
issues: [2771, 2833]
epic: 1196
---

# Wackel-Kerntests stabilisieren (#2771, #2833)

## Approval

- [ ] Approved

## Purpose

Der CI-Job `test` auf `main` wird zufaellig rot, weil drei Kerntests der deterministischen Schicht (Epic #1196) von Wanduhr bzw. Drossel-Buchhaltung abhaengen. Diese Spec macht die drei Tests robust, ohne ihre Zusicherung zu entwerten. Es wird ausschliesslich Testcode geaendert, kein Produktionscode.

## Source

- **File:** `tests/tdd/test_alert_preview_compare_paritaet.py`, `tests/test_meteofrance_fenster_zeile.py`, `tests/tdd/test_provider_request_deadline.py`
- **Identifier:** `_Wire.settings` (Z. 224), `_abruf` (Z. 89) mit `test_ac14_warmer_abruf_aus_dem_zwischenspeicher_hat_null_downloads`, die zwei Fristtests mit `timeout=5.0, frist=0.45` (`_request`-Test Z. ~1723/1732 und `fetch_combined`-Test Z. ~1863/1869)

Schicht: Python-Core, nur Testcode (`tests/`). Kein Frontend, keine Go-API, keine Kanal-/Briefing-Inhalte, keine Nutzerdaten (Trip/Ortsvergleich-Teilung, Mandantentrennung und Kanalparitaet nicht beruehrt).

## Scope

- **In Scope:** die drei Wackler aus #2771 (Météo-France-Zwischenspeicher, GeoSphere-Fristtest `fetch_combined` samt gleichförmigem `_request`-Geschwister) und #2833 (Vorschau-Sprachtest, Drossel), nur Testcode.
- **Out of Scope:** #2744, übrige Wanduhr-Grenzen in `test_provider_request_deadline.py` (→ #1199), globale pytest-timeout-Grenze, Produktionscode.
- **LoC:** ca. +60 / -10
- **Files:** 3 MODIFY, 2 CREATE (RED-Tests)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/conftest.py::_reset_telegram_rate_limit` | Fixture | Setzt die Drossel vor jedem Test zurueck (bleibt unveraendert) |
| `tests/helpers/kanal_fake_transporte.py:132` | Praezedenz | Setzt `telegram_rate_limit_max_per_window: 10_000` in Test-Settings |
| `src/providers/meteofrance.py:717-739` | Prueflingslogik | `base = max(start, run)`, `time_str` mit Sekunden im Cache-Schluessel (unveraendert) |
| `src/providers/thunder_enrichment.py:94-97` | Referenz | `_bezugszeitpunkt` kuerzt produktiv auf volle Stunde |
| pytest-timeout (30 s global, #2806) | Infrastruktur | Bleibt unveraendert |

## Implementation Details

Ursachen (Analyse, gemessen):

1. **#2833:** Fall `[abweichung]` in `test_compare_alert_preview_sprache_je_nutzer.py` verbraucht allein 18 Drossel-Plaetze am Chat 99999 (3 Sprachdurchlaeufe x 2 Referenz-Sendungen je `_stable` x 3 Blasen) = Standardgrenze `telegram_rate_limit_max_per_window`. Eine `_stable`-Wiederholung (Minutenwechsel, `_stable` Z. 134, bis 3x) kostet 6 weitere Plaetze, die 19. Sendung wartet in `_reserve_send_slot` bis zu 30 s, pytest-timeout schlaegt zu. Der globale Reset existiert bereits; die Intake-Hypothese "Buchhaltung wird nie geleert" ist widerlegt. Die Drossel ist in diesen Paritaetstests nicht Pruefgegenstand.
2. **#2771 (1):** `_abruf()` bildet `start = datetime.now(timezone.utc)` je Aufruf. Ein Sekundenwechsel zwischen erstem und zweitem Abruf ergibt einen anderen Cache-Schluessel, der warme Abruf geht ans Netz. Kein Produktionsbefund, da produktiv die volle Stunde uebergeben wird.
3. **#2771 (2):** Grenze `< 0,9 s` bei Frist 0,45 s laesst unter Runner-Last zu wenig Luft (CI-Ausreisser 1,12 s; unbelastet 0,64-0,77 s). Ohne Frist dauert der Aufruf >= 5 s je Versuch.

Aenderungen:

1. `tests/tdd/test_alert_preview_compare_paritaet.py`: in `_Wire.settings` `"telegram_rate_limit_max_per_window": 10_000` setzen. `_stable` und der Reset werden nicht angefasst.
2. `tests/test_meteofrance_fenster_zeile.py`: `start` einmal je Test bilden (`datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)`, spiegelt `_bezugszeitpunkt`) und an beide `_abruf`-Aufrufe uebergeben. `_abruf` erhaelt `start` als Parameter: `def _abruf(provider, start=None, **kw)`; ohne Angabe gilt `datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)` (der RED-Test `..._sekundenwechsel.py` ruft `_abruf(provider)` ohne `start` auf und wird nur so gruen).
3. `tests/tdd/test_provider_request_deadline.py`: bei den beiden `timeout=5.0, frist=0.45`-Tests Obergrenze `< 0.9` auf `< 3.0` (Untergrenze 0,2 bleibt), Assert-Meldung und Docstring ("Wanduhr < 3,0s") angleichen. Alle anderen Wanduhr-Grenzen der Datei bleiben unveraendert (Nebenbefund an Sammel-Issue #1199, je Test eigene Abwaegung, weil bei kleinen Timeouts eine lockere Grenze die Mutation "Frist fehlt" verschluckt).

RED-Tests (neu, vor der Implementierung rot):

- `tests/tdd/test_alert_preview_compare_paritaet_drossel_frei.py`: faehrt ueber die echte `wire`-Pruefstrecke die `[abweichung]`-Sendefolge mit einer zusaetzlich erzwungenen Sendefolge (Gesamtbedarf > 18 Plaetze am selben Chat, ohne `_stable` zu mocken) unter `@pytest.mark.timeout(10)`. Heute haengt der Test in `_reserve_send_slot` und ist rot; nach Fix gruen.
- `tests/test_meteofrance_fenster_zeile_sekundenwechsel.py`: warmer Abruf mit erzwungenem Sekundenwechsel (zwischen den Abrufen bis zum naechsten Sekundenbeginn warten, <= 1 s), Zusicherung wie der bestehende AC-14-Test (null Downloads, Zeile `(0, geladen)`). Heute immer rot; nach Fix gruen. Ein RED-Test fuer #2771 (2) ist nicht moeglich (siehe AC-3).

## Expected Behavior

- **Input:** CI-Lauf bzw. lokaler Lauf der benannten Testdateien.
- **Output:** Alle drei Tests bestehen reproduzierbar, auch bei Minuten-/Sekundenwechsel und unter Runner-Last bis knapp 3 s.
- **Side effects:** keine; Produktionscode, globale 30-s-Grenze und Drossel-Verhaltenstests bleiben unveraendert.

## Acceptance Criteria

- **AC-1:** Given der Paritaets-/Sprach-Vorschautest laeuft ueber die echte `wire`-Pruefstrecke und die Sendefolge erzwingt mehr als 18 Telegram-Sendungen an denselben Chat (zusaetzliche `_stable`-Wiederholung) / When der Test unter einer engen Zeitgrenze von 10 s laeuft / Then ist er gruen und deutlich unter 30 s, ohne Hang in `_reserve_send_slot`.
  - Test: `tests/tdd/test_alert_preview_compare_paritaet_drossel_frei.py` (heute rot durch Hang in der Drossel), plus Bestandstests `tests/tdd/test_compare_alert_preview_sprache_je_nutzer.py[abweichung]` und `[acht-orte-sms-gekuerzt]` gruen.

- **AC-2:** Given ein Meteo-France-Provider mit gefuelltem Zwischenspeicher nach dem ersten Abruf / When zwischen erstem und zweitem Abruf ein Sekundenwechsel erzwungen wird / Then hat der warme Abruf null Downloads und die Fensterzeile lautet `(0, geladen)`.
  - Test: `tests/test_meteofrance_fenster_zeile_sekundenwechsel.py` (heute immer rot) und der bestehende AC-14-Test `..._null_downloads` gruen, auch wiederholt (>= 20 Laeufe ohne Rot).

- **AC-3:** Given die beiden Fristtests mit `timeout=5.0, frist=0.45` laufen auf einem belasteten Runner / When der Aufruf bis knapp 3 s braucht / Then besteht der Test (Untergrenze 0,2 s bleibt), und bei der Mutation "Frist entfernt" (>= 5 s je Versuch) bleibt er rot.
  - Test: Fristtests `tests/tdd/test_provider_request_deadline.py` (beide Faelle) gruen; Nachweis der Mutation per Mutationsprobe im Adversary (String-Ersetzung mit externer Sicherungskopie), da kein natuerlich roter Test moeglich ist.

- **AC-4:** Given die Drossel-Zusicherungen sind nicht entwertet / When `test_telegram_rate_limit.py` und `test_send_slot_and_fetch_deadline.py` laufen und im Paritaetstest die Blasenzahl verglichen wird / Then bleiben die Drossel-Verhaltenstests unveraendert gruen und der Vergleich `telegram_bubbles` bleibt bestehen.
  - Test: beide Drossel-Testdateien (`tests/tdd/test_telegram_rate_limit.py`, `tests/tdd/test_send_slot_and_fetch_deadline.py`) unveraendert gruen (Diff dort leer); `telegram_bubbles`-Vergleich im Paritaetstest weiterhin vorhanden und aktiv.

- **AC-5:** Given die Aenderung ist ausgeliefert / When der Diff geprueft wird / Then ist kein Produktionscode (`src/`, `api/`, `internal/`, `cmd/`, `frontend/`) geaendert, die globale pytest-timeout-Grenze von 30 s ist unveraendert, und es gibt kein neues skip/xfail und keine Mocks.
  - Test: `git diff --stat origin/main` listet nur Dateien unter `tests/` und `docs/`; `pytest.ini`/`pyproject.toml` timeout-Wert unveraendert.

## Test Plan

- **RED (vor der Implementierung rot):** `tests/tdd/test_alert_preview_compare_paritaet_drossel_frei.py` (AC-1, Hang in der Drossel), `tests/test_meteofrance_fenster_zeile_sekundenwechsel.py` (AC-2, erzwungener Sekundenwechsel).
- **GREEN-Regression:** `tests/tdd/test_compare_alert_preview_sprache_je_nutzer.py`, `tests/tdd/test_alert_preview_compare_paritaet.py`, `tests/test_meteofrance_fenster_zeile.py` (AC-14-Test >= 20 Läufe ohne Rot), `tests/tdd/test_provider_request_deadline.py`, `tests/tdd/test_telegram_rate_limit.py`, `tests/tdd/test_send_slot_and_fetch_deadline.py`, `tests/tdd/test_telegram_post_is_single_guarded_exit.py`.
- **Mutationsproben (Adversary):** (a) Frist in GeoSphere entfernt → beide Fristtests rot trotz Grenze 3,0 s; (b) `start` in `_abruf` wieder je Aufruf mit Sekunden → Sekundenwechsel-Test rot; (c) Drossel-Grenze im `wire` zurück auf Standard → Drossel-frei-Test rot.
- Ohne Netz, ohne Mocks, ohne skip/xfail; nur benannte Testdateien (`uv run pytest <dateien>`).

## Definition of Done

- AC-1 bis AC-5 erfüllt, RED-Tests vorher rot und nachher grün belegt.
- Alle drei Mutationsproben vom Adversary rot nachgewiesen.
- Alle 6 CI-Checks am PR grün, `test`-Job ohne die drei Wackler.
- Nebenbefund (übrige Wanduhr-Grenzen) in #1199 eingetragen; #2771 und #2833 nach Merge geschlossen.

## Known Limitations

- Weitere Wanduhr-Grenzen in `test_provider_request_deadline.py` (`< 0.9` an Z. 357, 425, 527, 562, 1081, 1144, 1313, 1375, 1441, 1772, 1955; Z. 1761 mit `timeout=0.5`; Z. 2021 mit `timeout=0.2`) bleiben unveraendert und gehen als Nebenbefund an #1199.
- Out of scope: #2744 (uhrzeitabhaengige Tests vor UTC-Mitternacht), globale pytest-timeout-Grenze, skip/xfail, Mocks.
- Grenze 10 000 im `wire` verdeckt keine Blasen-Regression, weil die Blasenzahl ueber `telegram_bubbles` verglichen wird, nicht ueber die Drossel.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Stabilisierung ohne Aenderung an Entscheidungsflaechen; Praezedenz (`kanal_fake_transporte.py:132`) wird wiederverwendet.

## Changelog

- 2026-11-06: Erstfassung (Issues #2771, #2833, Epic #1196).
- 2026-11-06: Phase 5: Vorgabewert von `start` in `_abruf` (volle Stunde) festgelegt, damit der RED-Test aus Nutzersicht (Netzabruf nach Sekundenwechsel) statt per Signaturfehler rot ist.
