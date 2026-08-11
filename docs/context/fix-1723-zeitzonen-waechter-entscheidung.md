# Context: #1723 — Zeitzonen-Wächter auf die Entscheidungs-Schicht ausdehnen

**Workflow:** `fix-1723-zeitzonen-waechter-entscheidung` · **Issue:** #1723 (S1 von Epic #1722)
**Erhoben:** 2026-08-11 am Stand `e230977d` · Track: Full Process

## Request Summary

Der bestehende Zeitzonen-Wächter (#1402) bewacht die **Darstellung** einer Uhrzeit in
`src/output/**`. Die elf wiederkehrenden Zeitzonen-Bugs sitzen aber in der **Entscheidung**
(welcher Kalendertag, ist ein Versand fällig, gilt Ruhezeit, wann kippt ein Zähler) — dort gibt
es keinen Wächter. S1 dehnt den Geltungsbereich auf `src/services/**` + `api/**` aus, trägt den
Bestand als `KNOWN_VIOLATIONS` ein und blockt damit **nur Neuzugänge**. Es bewegt keine Zeile
Produktivcode.

## Papierlage: zwei Fehler im Dach-Issue

| Behauptung in #1722/#1723 | Befund |
|---|---|
| „ADR-0049" ist das Zeitzonen-ADR | **Falsch.** ADR-0049 = Premium-SMS (#1676), ADR-0050 = Metrik-Kaskade (#1719). Ein Zeitzonen-ADR existiert nicht; die freie Nummer ist **0051**. Die tragende Grundlage ist **ADR-0044** („Kalendertage folgen der Ortszeit", akzeptiert 2026-08-03). |
| `docs/analysis/zeitzonen-architektur-2026-08.md` | **Existiert nicht** — weder in `main` noch ungetrackt. |

Beides in #1722 als Kommentar gebucht. Für S1 ist keines davon ein Blocker: der Wächter ändert
kein Verhalten und wird von ADR-0044 bereits getragen. ADR-0051 wird vor S2 (#1724) fällig, wo
die Grundsatzentscheidung erstmals verhaltenswirksam wird (PO-Entscheid 2026-08-11).

## Related Files

| Datei | Relevanz |
|---|---|
| `tests/test_output_timezone_guard.py` (702 Z.) | **Der Prüfling.** Wird ausgedehnt. Scanfläche heute: `src/output/**` (Z. 87) + 7 einzeln gelistete Messaging-Dateien (`_MESSAGING_SERVICE_FILES`, Z. 89–103). `KNOWN_VIOLATIONS` ab Z. 463. |
| `tests/test_success_status_guard.py` | **Das nähere Vorbild.** Scannt bereits **exakt** `api/routers/**` + `src/services/**` (Z. 197f.) — die Scanfläche, die S1 sucht, ist im Repo erprobt. |
| `tests/test_guard_findings_survive_line_shifts.py` | **Meta-Wächter.** Lädt alle drei großen Wächter und prüft, dass Funde Zeilenverschiebungen überleben. Bestimmt den Prüfträger **zur Laufzeit** aus `_scan_files()` des Wächters — trägt eine ausgedehnte Scanfläche automatisch mit, kann aber den Prüfträger wechseln. |
| `tests/test_resolution_loss_guard.py` | Dritter großer Wächter, scannt `src/output/**` + `src/services/**`. |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | Die inhaltliche Grundlage der Regel. |
| `.github/ci_tdd_excludes.txt` | `test_output_timezone_guard.py` steht **nicht** darin → läuft in CI. Gilt für alle sieben AST-Wächter. |

## Existing Patterns — sieben AST-Ratschen im Repo

| Wächter | Scanfläche | Ausnahme-Mechanik |
|---|---|---|
| `test_success_status_guard.py` | `api/routers/**` + `src/services/**` | `KNOWN_VIOLATIONS` + `_APPROVED_EXCEPTIONS` + Shrink-Test |
| `test_resolution_loss_guard.py` | `src/output/**` + `src/services/**` | `KNOWN_VIOLATIONS` + Shrink-Test |
| `test_output_timezone_guard.py` | `src/output/**` + 7 Dateien | `KNOWN_VIOLATIONS` + Shrink-Test |
| `test_guard_findings_survive_line_shifts.py` | die drei oberen (Meta) | — |
| `tests/tdd/test_data_root_hardcoding_ratchet.py` | `src/**` + `api/**` | Inline-Marker `# gz-data-path: <Grund>` (≥15 Z.) |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | `tests/**` | Inline-Marker `# gz-main-path: <Grund>` (≥15 Z.) |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | `tests/**` | `KNOWN_VIOLATIONS` frozenset + Shrink-Test |

**Zwei etablierte Ausnahme-Formen:** zentrale schrumpfende Liste (Bestandsaufnahme) versus
Inline-Marker (Einzelfall-Begründung im Code). Die drei großen Wächter nutzen die erste.

**Schlüssel-Format (Issue #1466 AP2):** `"pfad::funktion::ordinal"` — nicht `"pfad:zeile"`.
Zeilennummern wandern; der Meta-Wächter erzwingt die stabile Form. Ein neuer Detektor muss
dieses Format bedienen, sonst bricht `test_guard_findings_survive_line_shifts.py`.

**Bekannte Falle im Prüfling selbst (#1465):** `_scan_files()` filtert mit `if p.exists()` und
ließ einen falsch geschriebenen Pfad **wortlos** fallen — der Wächter sah den Drilldown-Formatter
nie. Gegenmittel ist `test_scan_list_paths_all_exist()` (Z. 522). Wird die Scanfläche auf ganze
Verzeichnisse umgestellt, muss die entsprechende Zusicherung mitwandern: ein Verzeichnis, das
nicht existiert, darf nicht still zu „null Funde" führen.

## Gemessener Bestand im Geltungsbereich (AST, Stand `e230977d`)

93 Dateien gescannt (`src/services/**` + `api/**`), **18 betroffen**:

| Muster | AST-Funde | grep-Funde (Issue) |
|---|---|---|
| Umgebungsuhr (`.today()`, `.now()`, `.utcnow()` ohne Argument) | **30** | „40 + 10" |
| Festes Zonen-Literal `ZoneInfo("…")` | **9** | „12" |

Die Differenz ist erklärt: das Issue zählt per `grep` über ganz `src/` + `api/` und trifft dabei
**Kommentare und Docstrings** mit — bei `datetime.now()` sind 5 von 10 grep-Treffern reine
Prosa. Ein AST-Scanner sieht sie nicht. Die Größenordnung des Issues stimmt, die exakte Zahl für
die Bestandsliste ist **30 + 9 = 39**, nicht ~52.

**Verteilung Umgebungsuhr** (Auszug, Schwerpunkte): `trip_report_scheduler.py` 6 ·
`scheduler_dispatch_service.py` 5 (davon 3 × `.utcnow()`) · `gpx_processing.py` 3 ·
`api/routers/compare.py` 3 · `trip_command_processor.py` 2 · je 1 in
`alert_briefing_anchor.py`, `comparison_engine.py`, `compare_preview_service.py`,
`dispatch_orchestrator.py`, `inbound_telegram_reader.py`, `notification_service.py`,
`preview_service.py`, `massif_closure.py` (2), `meteo_forets.py`, `api/routers/debug.py`.

**Alle 9 Zonen-Literale namentlich:**

| Fundstelle | Literal | Bewertung |
|---|---|---|
| `src/services/alert_daily_limit.py:23` | `Europe/Vienna` | im Issue genannt |
| `src/services/deviation_alert_engine.py:31` | `Europe/Vienna` | im Issue genannt |
| `src/services/scheduler_dispatch_service.py:164` | `Europe/Vienna` | im Issue genannt |
| `api/routers/scheduler.py:34` | `Europe/Vienna` | im Issue genannt |
| `src/services/notification_service.py:773, 821, 1061, 1063` | `UTC` | **vom Issue nicht erfasst** |
| `src/services/trip_report_scheduler.py:1820` | `UTC` | **vom Issue nicht erfasst** |

## Risks & Considerations

1. **🔴 `ZoneInfo("UTC")` ist die halbe Fundmenge und vermutlich legitim.** Das Issue formuliert
   das Muster als „`ZoneInfo("Europe/Vienna")` **und jedes andere feste Zonen-Literal**". Wörtlich
   angewandt fängt es die 5 UTC-Stellen mit — die nach Hausnorm #1345 („naive Zeitstempel sind
   UTC") gerade die *richtige* Schreibweise sein können. Sie landeten dann als gebuchte „Schuld"
   in einer Liste, die per Ratsche nur schrumpfen darf, aber nie schrumpfen *wird*. Klärungsbedarf
   in der Spec: fängt das Muster jedes Literal, nur Nicht-UTC-Literale, oder Literale außerhalb
   eines Hausnorm-Kontexts? Vergleichbares Kollateral-Muster:
   `selectable=False`-Gate (#1719), das alle non-selectable Metriken traf.

2. **🔴 `.utcnow()` ist möglicherweise korrekt, nicht falsch.** Drei Fundstellen in
   `scheduler_dispatch_service.py` (Z. 69, 213, 240). `datetime.utcnow()` liefert einen **naiven**
   Zeitstempel — exakt die Hausnorm aus #1345. Das Issue nennt `.utcnow()` gar nicht; es kam erst
   durch meine Messung dazu. Ob es ins Muster gehört, ist eine Spec-Frage, keine
   Implementierungs-Entscheidung.

3. **Provider-Ausnahme im Issue geht ins Leere.** #1723 nimmt `src/providers/geosphere.py:372`
   ausdrücklich aus („API-Parameter, keine Entscheidung"). Die Datei liegt in `src/providers/` und
   damit **außerhalb** des Geltungsbereichs `src/services/**` + `api/**` — die Ausnahme wird nie
   gebraucht. Nebenbefund: `geosphere.py:405` deutet die Antwort mit
   `replace(tzinfo=ZoneInfo("Europe/Vienna"))`, was *keine* reine Parameterübergabe ist; relevant
   erst, wenn S5 die Fläche weitet.

4. **Der Meta-Wächter kann kippen.** `test_guard_findings_survive_line_shifts.py` wählt „die
   Datei mit den meisten Funden" als Prüfträger. Ver­dreifacht sich die Fundmenge, wechselt der
   Prüfträger — der Test muss danach noch grün sein, was nicht selbstverständlich ist.

5. **Wächter, der nichts fängt, ist die gefährlichste Form von Grün.** Das Issue fordert die
   Mutations-Gegenprobe ausdrücklich: neu eingefügtes `date.today()` in `src/services/` → rot;
   neu eingefügtes Zonen-Literal → rot; Entfernen eines `KNOWN_VIOLATIONS`-Eintrags, dessen
   Fundstelle noch existiert → rot. Erfahrungswerte im Repo: eine Typ-Aufzählung in einem
   AST-Wächter wiederholt gern denselben Klassenfehler, den sie verhindern soll.

6. **Test-Kern muss grün bleiben.** Der Prüfling läuft in CI (`test`-Job). Eine unvollständige
   `KNOWN_VIOLATIONS`-Liste macht `main` rot und blockt jede parallele Session.

## Dependencies

- **Upstream:** `ast` (stdlib), `Path`; ADR-0044 als inhaltliche Grundlage; Schlüsselformat aus #1466 AP2.
- **Downstream:** `test_guard_findings_survive_line_shifts.py` (lädt den Prüfling direkt);
  CI-Job `test`; jeder künftige Commit in `src/services/**` + `api/**`.

## Existing Specs

- `docs/specs/modules/fix_1465_zeitzonen_hausnorm.md` — Hausnorm naive UTC
- `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` — „heute"/„morgen" nach Ortszeit
- `docs/specs/modules/fix_1409b_repo_path_ratchet.md` — Ratschen-Bauform + „Known Limitations"

## Nicht in dieser Scheibe (aus #1723)

- Muster 3 der Analyse: `.hour`/`.date()` auf einem Zeitstempel ohne nachweisliche Zonen-Auflösung
  (der eigentliche Fehler von #1470/#1697) — eigene Scheibe.
- Go-Seite (`time.Now()`, ~225 Fundstellen) — Go führt die Zone im Typ mit, andere Fehlerklasse.
- Jede Änderung an Produktivcode.
