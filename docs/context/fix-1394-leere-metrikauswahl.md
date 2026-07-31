# Context: fix-1394-leere-metrikauswahl

Issue: #1394 (bug) — Trip-Gegenstück zu #1366 (Ortsvergleich, ausgeliefert 2026-07-26/27).

## Request Summary

Wählt ein Nutzer im Trip alle Wettergrößen ab, zeigt das Briefing an drei Stellen
trotzdem Werte — teils Größen, die er nie ausgewählt hat. Die Regel „Feld fehlt =
Altbestand → alle; Feld vorhanden und leer = bewusste Nutzerwahl → keine" ist auf der
Vergleichs-Seite bereits gebaut und wird auf die Trip-Seite übertragen, nicht neu
erfunden (Issue-Kommentar 2026-07-29, Invariante 3 des Dach-Epics #1374).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/output/renderers/email/html.py:1338-1343` | **T1** — Ersatzliste aus sieben fest verdrahteten Größen, wenn die aktive Auswahl leer ist |
| `src/output/renderers/email/plain.py:155-160` | **T2** — wortgleiche Kopie derselben Ersatzliste |
| `src/output/renderers/email/compact.py:146-163` | **T2b (neu gefunden)** — keine Ersatzliste, aber die Überschrift `== Metriken-Ueberblick ==` wird unbedingt gesetzt → leerer Block statt kein Block |
| `src/services/day_comparison.py:156-181` | **T3** — `if not selected_metrics: return _summarize_legacy(...)`; Signatur trennt `None`/`[]` bereits sauber, nur der Check nicht |
| `src/output/renderers/email/html.py:1372-1376`, `plain.py:144-148` | Aufrufer der Vortagszeile — reichen die aktive Auswahl durch |
| `src/app/loader.py:792-801` | **T4** — `and any(raw_channel_layouts.values())` kippt „alle Kanal-Listen leer" auf `None` → globaler Rückfall |
| `src/app/models.py:603-606, 650-682` | Der dokumentierte Vertrag, den T4 verletzt: „Leere Liste pro Kanal = expliziter User-Wunsch, kein Fallback" — `get_metrics_for_channel()` setzt ihn bereits korrekt um |
| `src/app/loader.py:747` | `data.get("metrics") or []` — fehlt das Feld, entsteht eine leere Liste; **es gibt keine Katalog-Auffüllung** |

## Vorlage aus #1366 (übernehmen, nicht nachbauen)

- Spec: `docs/specs/modules/compare_empty_metric_selection.md`
- Commits: `bd8573ac`, `9aabba19`, `0c24eea0`, `9ae845d8`
- Bauart: `src/output/renderers/compare_hourly_metric_ids.py` — `if x is None: return None`
  statt Falsy-Check, `return resolved` statt `return resolved or None`.
- Drei Lehren, die dort erst nachträglich dazukamen und hier von Anfang an gelten:
  1. **Die Entscheidung fällt an genau einer Stelle** (`resolve_compare_render_options`),
     nicht in jedem Renderer erneut — sonst entsteht driftende Zweitlogik.
  2. **Maßgeblich ist, ob überhaupt etwas Sichtbares entsteht** (Nachtrag N-2), nicht
     die Länge einer aufgelösten Liste.
  3. **Überschriften ohne Inhalt sind derselbe Fehler** (Commit `9ae845d8`: „STUNDENVERLAUF
     nur noch mit Stundenzeilen") — betrifft hier direkt T2b.

## Existing Patterns

- Regel im Klartext bereits im Code: `src/services/compare_alert.py:237-248`.
- Trip macht es an anderer Stelle schon richtig: Stundentabellen zeigen bei leerer
  Auswahl keine Tabelle (`models.py:660-682`, `email/helpers.py:245-266`,
  `email/html.py:685-686`).
- `summarize_day_comparison()` ist bereits mit `Optional[List[str]] = None` und
  dokumentierter Bedeutung gebaut — nur der Zweig `if not selected_metrics` fängt beide
  Fälle zusammen. Der Fix ist dort ein Einzeiler.

## Entscheidender Unterschied zur Vergleichs-Seite

Der Trip speichert die Auswahl **nicht** als Liste aktiver Schlüssel, sondern als
vollständige Metrik-Liste mit `enabled`-Flags. „Leer" entsteht daher auf zwei Wegen,
die heute ununterscheidbar zusammenfallen:

| Fall | Datenlage | Zielverhalten |
|------|-----------|---------------|
| **A — Altbestand** | `display_config.metrics` fehlt ganz → `dc.metrics == []` | wie bisher: die sieben Standardgrößen zeigen |
| **B — bewusste Leerauswahl** | `dc.metrics` hat Einträge, alle mit `enabled=False` | nichts zeigen |

Beide liefern heute `[mc for mc in dc.metrics if mc.enabled] == []` und landen im
selben Ersatzlisten-Zweig. Die Unterscheidung ist über `len(dc.metrics) == 0` sauber
möglich und entspricht exakt AC-3 der Vorlage-Spec.

## Bestandsdaten (gemessen 2026-07-31 auf dem Produktivdatenstand, 19 Briefings)

| Befund | Zahl | Folge |
|--------|------|-------|
| `metrics` fehlt ganz (Fall A) | **13** — davon 5 echte Nutzer-Trips (`henning`: heimat, zillertal, zillertal-täglich, mallorca-, cp-eb6ba0b2) und 8 Validator-Trips | Diese dürfen sich **nicht** ändern. Ohne Fall-A-Unterscheidung verlören sie ihren Überblicksblock, obwohl nie etwas abgewählt wurde. |
| `metrics` vorhanden mit ≥10 aktiven Größen | 6 | unberührt |
| `channel_layouts` gesetzt | **0** | T4 ist heute rein vorbeugend — kein Bestandstrip ändert sein Verhalten. Risiko der T4-Korrektur damit praktisch null. |

## Dependencies

- **Upstream:** `UnifiedWeatherDisplayConfig` (`models.py`), Loader-Parser, Metrik-Katalog.
- **Downstream:** alle drei Briefing-Renderer (HTML, Klartext, Kompakt), Vortagszeile,
  und über `get_metrics_for_channel()` auch Telegram/SMS.

## Existing Specs

- `docs/specs/modules/compare_empty_metric_selection.md` — die Vorlage (#1366/#1361).
- `docs/specs/modules/weather_config.md` — Datenmodell der Metrik-Konfiguration.
- `docs/specs/modules/email_metrics_summary_664.md` — Herkunft des Überblicksblocks.

## Risks & Considerations

1. **Bestandsschutz Fall A** — der zentrale Punkt. Wird A nicht von B getrennt, ist der
   Fix eine Regression für 13 vorhandene Trips.
2. **`loader.py` ist eine schema-relevante Datei** (CLAUDE.md) — der Backup-Hook greift,
   Roundtrip-Verhalten muss unverändert bleiben.
3. **Renderer-Commit-Gate #811** greift zwingend: `email/html.py`, `email/plain.py`,
   `email/compact.py` sind Mail-Inhalts-Dateien. Vor dem Commit sind
   `tests/tdd/test_issue_811_mode_matrix.py` grün und ein erfolgreicher Lauf von
   `briefing_mail_validator.py` gegen eine echt zugestellte Staging-Mail Pflicht.
4. **Doppelte Ersatzliste zusammenführen** — T1/T2 sind wortgleich. Ein gemeinsamer
   Auflöser (analog `resolve_enabled_metrics()`) erfüllt zugleich Lehre 1 aus #1366 und
   die Trip/Compare-Teilungsinvariante.
5. **Bestandstests**, die „leer → sieben" bzw. den Legacy-Zweig festschreiben, müssen
   mitgezogen statt stillgelegt werden (Vorlage-Spec, Abschnitt „Bestandstests"). Kandidaten:
   `tests/tdd/test_issue_790_briefing_simplify.py:298-320` (ruft `summarize_day_comparison`
   ohne `selected_metrics` auf — bleibt korrekt, weil `None` ≠ `[]`).
6. **Kein Live-Wetter nötig** für die Kern-Tests; der Nachweis aus Nutzersicht braucht
   eine echte Staging-Mail (ein Versand, dann IMAP — Kontingent).
7. **Der Pflicht-Validator kann die Leerauswahl-Mail nicht abnehmen** (gemessen am Code,
   nicht vermutet): `briefing_mail_validator.py:399-400` verlangt eine sequenzielle
   Stundentabelle mit ≥2 Stundenzeilen, `:357-361` zusätzlich eine sichtbare
   Wetterdaten-Tabelle bei 390px und 1000px. Genau die entfällt bei bewusst leerer
   Auswahl korrekterweise. Dieselbe Falle führte in #1366 zur `hourly_enabled`-Lösung.
   **Folge für die Nachweis-Strategie:** Der Gate-Lauf (#811) wird mit einem *normalen*
   Briefing geführt (Regressionsnachweis), der Nutzersicht-Nachweis der Leerauswahl mit
   einer zweiten, separat per IMAP abgerufenen Mail und gesonderter Prüfung. Der
   Validator selbst wird hier **nicht** angefasst — Validator-Änderungen sind laut
   Projektregel ein eigener Workflow.
8. Tolerant und damit unkritisch sind `_check_layer_consistency` und
   `_check_metric_plausibility` — beide überspringen fehlende Pillen, statt sie zu
   beanstanden.
