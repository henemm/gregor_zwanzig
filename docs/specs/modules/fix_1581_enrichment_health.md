---
entity_id: fix_1581_enrichment_health
type: module
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.0"
tags: [observability, providers, health]
---

# Health-Signal für Anreicherungs-Pfade (Gewitter-Direktquellen, Radar-Nowcast)

## Approval

- [ ] Approved

## Purpose

Zwei degradierbare Anreicherungs-Pfade — Gewitter-Direktquellen (`de_direct`/`fr_direct`
→ Vertretung `eu_direct`) und Radar-Nowcast — tragen zwar einen Marker in den
Ausgabedaten, aber ein **andauernder** Ausfall bleibt heute unbemerkt: es gibt kein
Journal und keinen Kanal in `/api/scheduler/status`. Das ist die von ADR-0018
geforderte, bislang fehlende zweite Hälfte („wachsendes Health-Signal") für beide
Pfade. Diese Spec deckt beide Scheiben von Issue #1581 in einem Workflow ab.

## Source

- **File:** `src/providers/enrichment_health.py` (neu), `src/providers/thunder_enrichment.py`
  (MODIFY, Scheibe 1), `src/services/radar_service.py` (MODIFY, Scheibe 2),
  `internal/scheduler/enrichment_health.go` (neu), `internal/scheduler/scheduler.go`
  (MODIFY, ein Schlüssel), `internal/scheduler/briefing_health_test.go`
  (MODIFY, Wächter-Test)
- **Identifier:** `providers.enrichment_health.log_enrichment_call` (neu),
  `providers.thunder_enrichment._fetch_primaerquelle` (Zeilen 377-441, MODIFY),
  `services.radar_service.RadarService.get_nowcast` (MODIFY, Miss-Zweig),
  `scheduler.aggregateEnrichmentCalls` / `scheduler.EnrichmentHealth` (neu),
  `scheduler.coreBriefingSources` (unverändert, nur zusätzlich bewacht)

**Schicht:** Python-Core (`src/providers/`, `src/services/`) für das Schreiben; Go-API
(`internal/scheduler/`) für das Lesen/Aggregieren und die Ausgabe über
`/api/scheduler/status`. Kein Frontend betroffen.

## Estimated Scope

- **LoC:** ~700-900 (überwiegend Tests). Der PO hat das Standard-Limit von 250 auf
  900 angehoben (`loc_limit_override`) — der Testumfang wird dadurch NICHT gekürzt.
- **Files:** 11 · **Acceptance Criteria:** 13
- **Effort:** high

| Datei | Aktion | LoC (ca.) | Scheibe |
|---|---|---|---|
| `src/providers/enrichment_health.py` | CREATE | 60-80 | 1 |
| `src/providers/thunder_enrichment.py` | MODIFY (5 Ausgänge) | 20-25 | 1 |
| `tests/tdd/test_thunder_enrichment_health_journal.py` | CREATE | 120-150 | 1 |
| `internal/scheduler/enrichment_health.go` | CREATE | 130-160 | 1 |
| `internal/scheduler/enrichment_health_test.go` | CREATE | 150-200 | 1 |
| `internal/scheduler/briefing_health_test.go` | MODIFY (Wächter über `coreBriefingSources`) | 20-30 | 1 |
| `internal/scheduler/scheduler.go` | MODIFY (ein Schlüssel) | 1-2 | 1 |
| `src/services/radar_service.py` | MODIFY (Miss-Zweig) | 15-25 | 2 |
| `tests/tdd/test_radar_nowcast_health_journal.py` | CREATE | 100-140 | 2 |
| `internal/scheduler/enrichment_health_test.go` | MODIFY (Radar-Fälle) | 60-80 | 2 |
| `docs/adr/0047-*.md`, `docs/adr/0018-*.md` | MODIFY (Addendum) | 30-45 | 1+2 |

Reihenfolge: Scheibe 1 liefert den **vollständigen** gemeinsamen Baustein (Journal-Modul,
Go-Aggregator, Endpoint-Anschluss, Gewitter-Aufrufer); Scheibe 2 fügt nur den zweiten
Aufrufer (Radar) und dessen Testfälle hinzu — kein zweiter Mechanismus.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.get_data_root()` | intern | Journalpfad wird bei JEDEM Aufruf frisch aufgelöst, nie über eine Modulkonstante (Falle #1633: Konstante bindet vor der Testfixture) |
| `providers.thunder_routing.thunder_vertretung_for()` | intern | Liefert die Ersatzquelle für `detail` bei `outcome="fallback"` |
| `services.official_alerts.warn_egress.log_warn_service_call` | Vorbild (Schreibseite) | fail-soft JSONL-Append, eigener innerer `try/except Exception: pass` |
| `internal.scheduler.warn_service_health.aggregateWarnServiceCalls` / `WarnServiceHealth` | Vorbild (Leseseite) | Schema 1:1 übernehmbar: `nilIfEmpty`, fehlende Datei ≠ Fehler, `journal_read_error` nur bei echtem Lesefehler |
| `internal.scheduler.briefing_health.coreBriefingSources` | intern, GESCHÜTZT | Darf durch diese Spec NICHT um eine Anreicherungsquelle erweitert werden — genau das bewacht AC-6 |
| ADR-0018 „Modell-Fallback ohne Kaschieren" | Architektur | Fordert das hier nachgelieferte Health-Signal für jeden degradierbaren Pfad |
| ADR-0047 „Gewitter-Vertretung zwischen Direktquellen" | Architektur | Bekommt das Addendum mit Entscheidungen 1-3 dieser Spec |
| `docs/specs/modules/feat_1492_s2a_thunder_vertretung.md` | Spec (Vorgänger) | Known Limitations 2 dort ist der ursprüngliche Vertagungsvermerk, den diese Spec einlöst |
| `services.radar_service.RadarService._budget_gate` (Feld `_budget_throttled_this_call`) | intern | Liefert die Unterscheidung `self_throttled` vs. `unavailable` — Radar trennt das bereits fachlich |

## Implementation Details

**1. Gemeinsamer Schreibbaustein (`src/providers/enrichment_health.py`, neu, Vorbild
`warn_egress.py:304-346`):**

```
def log_enrichment_call(path: str, outcome: str, detail: Optional[str] = None) -> None:
    """path: 'thunder' | 'radar_nowcast'
    outcome: 'ok' | 'fallback' | 'unavailable' | 'self_throttled'
    Fail-soft: jeder Fehler wird geschluckt, Diagnose darf den Abruf nie
    beeintraechtigen. Journalpfad wird bei JEDEM Aufruf ueber
    app.loader.get_data_root() aufgeloest (Falle #1633)."""
    try:
        root = get_data_root()
        jpath = root / "diagnostics" / "enrichment_calls.jsonl"
        jpath.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": path, "outcome": outcome, "detail": detail,
        })
        with jpath.open("a") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
```

**2. Gewitter-Seite — die fünf Ausgänge von `_fetch_primaerquelle()`
(`thunder_enrichment.py:377-441`), je Ausgang ein `outcome`:**

| # | Ausgang (Zeilen) | Bedingung | `outcome` | `detail` |
|---|---|---|---|---|
| 1 | Stiller Rückzug (407-409) | `except ThunderSourceUnavailableError`, `ersatz is None or ersatz == bereits_befragt` | `unavailable` | `None` |
| 2 | Leere Antwort (412-413) | `not any(werte for _feld, werte in eintraege)` | `ok` | `None` |
| 3 | Nichts gefüllt (415-417) | `gefuellt == 0` nach `_wende_eintraege_an` | `ok` | `None` |
| 4 | Erfolg mit Primärquelle (419-423) | `aktive_quelle == quelle` | `ok` | `None` |
| 5 | Erfolg über Vertretung (425-439) | `aktive_quelle != quelle` | `fallback` | `aktive_quelle` (z. B. `"eu_direct"`) |

Ausgänge 2-4 sind fachlich alle „die Primärquelle hat regulär geantwortet" (mit,
ohne oder trotz erfolglos angewendeter Werte) und teilen sich deshalb dasselbe
`outcome="ok"` — die Unterscheidung „leer vs. gefüllt" ist bereits über
`fallback_metrics`/die Signalfelder selbst sichtbar und braucht im Health-Journal
keine eigene Kategorie.

**Sechster Ausgang — ABGEDECKT (Korrektur des ersten Spec-Entwurfs):** Wirft die
Vertretung selbst `ThunderSourceUnavailableError` (zweiter
`_hole_eintraege(ersatz, ...)`-Aufruf, Zeile 410), propagiert die Ausnahme
unverändert zum bestehenden äußeren Fang in `enrich_thunder()` (Zeilen 279-281).
Der erste Entwurf wollte diesen Fall auslassen mit der Begründung, er trete in
der Produktion nie ein (Vertretung `eu_direct` wirft heute nicht — geprüft:
`ThunderSourceUnavailableError` wird nur in `dwd.py:511` und
`meteofrance.py:716` geworfen).

Das ist die falsche Abgrenzung: **genau dieser Ausgang ist der im Issue #1581
benannte einzige Beobachtungspunkt** („der einzige Beobachtungspunkt heute ist ein
`logger.warning`"). Ihn auszulassen hieße, den namensgebenden Fall des Tickets
ohne Health-Signal zu lassen. Dass er heute nicht eintritt, macht die Abdeckung
billig, nicht überflüssig — und schützt gegen den Tag, an dem eine künftige
Vertretung sehr wohl wirft.

Umsetzung: der äußere Fang in `enrich_thunder()` (Zeilen 279-281) schreibt
zusätzlich zum bestehenden `logger.warning` eine Journalzeile
`outcome="unavailable"`, `path="thunder"`. Er fängt jede Ausnahme aus
`_fetch_lightning_density()`, nicht nur Vertretungsausfälle — das ist korrekt, denn
in allen diesen Fällen hat die Anreicherung nicht geliefert. Siehe AC-12.

**Der Journal-Aufruf braucht einen EIGENEN inneren `try/except Exception: pass`
je Ausgang und darf NICHT im bestehenden äußeren Fang von `enrich_thunder()`
(Zeilen 279-281) mitlaufen** — sonst verschleiert ein Diagnosefehler einen echten
Anreicherungsfehler. Praktisch: `log_enrichment_call()` ist selbst schon fail-soft
(s. Punkt 1), der Aufruf an jedem der vier `return`-Punkte in
`_fetch_primaerquelle()` kann daher direkt erfolgen, ohne dass der Aufrufer noch
einmal absichern muss.

**3. Radar-Seite — Aufrufstelle in `get_nowcast()`, NICHT in `_derive_result()`:**

`_derive_result()` läuft sowohl beim Cache-Hit (Zeile 205) als auch beim
Cache-Miss (Zeile 219) — ein dort platzierter Journal-Aufruf würde jeden
Cache-Hit als lebendig buchen und einen aus dem Cache weiterbedienten
Dauerausfall verdecken (AC-9). Der Aufruf gehört deshalb in den Miss-Zweig von
`get_nowcast()` (nach Zeile 213, `frames, source = self._fetch_frames_with_fallback(...)`),
unmittelbar nach der Berechnung von `result = self._derive_result(...)`:

```
result = self._derive_result(frames, source, now=now)
if result.throttled:
    log_enrichment_call("radar_nowcast", "self_throttled")
elif result.data_unavailable:
    log_enrichment_call("radar_nowcast", "unavailable")
else:
    log_enrichment_call("radar_nowcast", "ok")
return result
```

Die Unterscheidung `throttled` (eigene Budget-Drosselung, `radar_service.py:559`)
vs. `data_unavailable` (echter Anbieterausfall, `radar_service.py:567-571`)
existiert bereits im Feldpaar von `NowcastResult` — sie wird hier nur auf
`outcome` abgebildet, nicht neu erfunden.

**4. Go-Leseseite (`internal/scheduler/enrichment_health.go`, neu):**
`aggregateEnrichmentCalls()` und `EnrichmentHealth()`, Schema 1:1 wie
`WarnServiceHealth()` (`warn_service_health.go:262-310`): Journal lesen, nach
`path` gruppieren, je Gruppe `last_attempt_at` (`nilIfEmpty`, nie `""`),
`last_success_at`, `last_fallback_at`, `self_throttled` (Flag: mindestens ein
`self_throttled`-Eintrag beobachtet). Fehlende Journal-Datei ist **kein** Fehler
(leere Map); nur ein echter Lesefehler setzt `journal_read_error: true`. Anschluss
in `scheduler.go:830f` als eigener, zu `briefing_health` und `warn_service_health`
gleichrangiger Top-Level-Schlüssel `enrichment_health`.

**5. Grenzwächter (`internal/scheduler/briefing_health_test.go`, MODIFY):** ein
neuer Test iteriert `coreBriefingSources` und vergleicht sie auf Gleichheit mit
genau `{"briefing": true, "briefing_nacht": true}` — s. AC-6 und Known
Limitations.

## Expected Behavior

- **Input:** jeder Abruf einer der beiden Anreicherungsquellen (Gewitter-Direktquelle
  via `_fetch_primaerquelle()`, Radar-Nowcast via `get_nowcast()`), unabhängig vom
  Ausgang (Erfolg, Vertretung, Ausfall, Selbstdrosselung, Cache-Treffer).
- **Output:** eine JSONL-Zeile in `data/diagnostics/enrichment_calls.jsonl` je
  tatsächlichem Abrufversuch (Cache-Treffer erzeugen KEINE Zeile); ein neuer
  Top-Level-Schlüssel `enrichment_health` in `/api/scheduler/status`, gegliedert
  nach `path` (`thunder`, `radar_nowcast`), mit den Rohdaten `last_attempt_at`,
  `last_success_at`, `last_fallback_at`, `self_throttled`.
- **Side effects:** keine auf den fachlichen Datenfluss — Gewitter-Signalwerte und
  Radar-Nowcast-Ergebnisse bleiben unverändert, auch wenn das Journal nicht
  beschreibbar ist (Fail-soft, AC-4). `briefing_health` bleibt in Struktur und
  Werten unverändert (AC-7).

## Acceptance Criteria

- **AC-1:** Given eine Gewitter-Primärquelle fällt mit `ThunderSourceUnavailableError`
  aus (`thunder_enrichment.py:377-441`) UND eine benannte Vertretung liefert
  erfolgreich Daten / When `_fetch_primaerquelle()` durchläuft / Then wird eine
  Journalzeile mit `outcome="fallback"` und `path="thunder"` geschrieben, `detail`
  nennt die Ersatzquelle (z. B. `"eu_direct"`).
  - Test: Journal nach einem Vertretungsfall (Fake-Provider analog feat_1492 AC-1)
    auslesen und die letzte Zeile für `path="thunder"` auf `outcome` UND `detail`
    prüfen — nicht nur auf Existenz einer Zeile.

- **AC-2:** Given die Primärquelle fällt aus, aber es ist KEINE Vertretung
  verfügbar bzw. sie wurde bereits befragt (`thunder_enrichment.py:406-409`, der
  stille Rückzug) / When `_fetch_primaerquelle()` durchläuft / Then wird eine
  Journalzeile mit `outcome="unavailable"` und `path="thunder"` geschrieben.
  Heute hinterlässt genau dieser Fall NICHTS, nicht einmal einen Log-Eintrag —
  das ist der Kern des Tickets.
  - Test: Fake-Provider ohne verfügbare Vertretung (bzw. `ersatz == bereits_befragt`)
    auslösen und danach das Journal auf genau diese Zeile prüfen; die Gegenprobe
    zeigt, dass vor dieser Implementierung überhaupt keine Zeile entsteht.

- **AC-3:** Given die Primärquelle liefert normal (einer der drei Nicht-Fehler-
  Ausgänge von `_fetch_primaerquelle()`: leere-aber-gültige Antwort, nichts
  gefüllt, oder Erfolg mit Primärquelle) / When der Abruf ohne Ausnahme und ohne
  Vertretung durchläuft / Then wird eine Journalzeile mit `outcome="ok"` und
  `path="thunder"` geschrieben.
  - Test: Drei getrennte Testfälle (leere Antwort, nichts gefüllt, Erfolg mit
    Primärquelle) erzeugen je eine `ok`-Zeile — keiner erzeugt `fallback` oder
    `unavailable`.

- **AC-4:** Given das Journal ist nicht beschreibbar (z. B. der Zielpfad ist ein
  Verzeichnis statt einer Datei) / When die Gewitter-Anreicherung (`enrich_thunder()`)
  läuft / Then liefert sie unverändert dieselben Daten wie ohne Journalfehler,
  und es propagiert KEINE Ausnahme. Diagnose darf den Abruf nie beeinträchtigen.
  - Test: Journalpfad vorab auf ein Verzeichnis zeigen lassen, denselben
    Erfolgsfall wie AC-1 durchlaufen lassen und die Signalfelder (nicht das
    Journal) auf Gleichheit mit dem fehlerfreien Fall prüfen.

- **AC-5:** Given über einen längeren Zeitraum stehen im Journal ausschließlich
  Einträge mit `outcome="unavailable"` für `path="thunder"` / When
  `/api/scheduler/status` abgefragt wird / Then liefert `enrichment_health.thunder`
  ein aktuelles `last_attempt_at` und ein `last_success_at`, das entsprechend alt
  bzw. `null` ist, wenn es nie einen Erfolg gab. Der Dauerausfall ist damit als
  wachsender Abstand ablesbar.
  - Test: Journal mit synthetischen `unavailable`-Zeilen über mehrere simulierte
    Tage befüllen (manipulierte Zeitstempel, Muster `briefing_health_test.go`),
    Endpoint per `httptest` real durchlaufen und beide Felder auslesen — der
    Abstand zwischen `jetzt` und `last_success_at` wächst sichtbar mit der
    simulierten Ausfalldauer.

- **AC-6:** Given die Map `coreBriefingSources` in
  `internal/scheduler/briefing_health.go` / When sie ausgelesen wird / Then
  enthält sie GENAU die Einträge `briefing` und `briefing_nacht` — kein weiterer
  Schlüssel. Ersetzt das ursprüngliche AC „Anreicherungs-Ausfall meldet keinen
  Briefing-Ausfall" (PO-Entscheid): in der gewählten Bauart (getrennte Journale,
  getrennte Aggregatoren, kein gemeinsamer Codepfad) wäre dieser Test strukturell
  trivial wahr und würde nichts bewachen. Der Wächter über die Map selbst ist die
  Mutation, die im Betrieb tatsächlich wehtut.
  - Test: Ein Wächter-Test iteriert die Map und vergleicht sie auf Gleichheit mit
    `{"briefing": true, "briefing_nacht": true}`; trägt jemand künftig eine
    Anreicherungsquelle (z. B. `"thunder"`) dort ein, wird der Test rot.

- **AC-7:** Given der neue Aggregator ist verdrahtet / When `/api/scheduler/status`
  abgefragt wird / Then enthält die Antwort einen eigenen Top-Level-Schlüssel
  `enrichment_health`, und der bestehende Schlüssel `briefing_health` bleibt in
  Struktur und Werten identisch zum Stand vor dieser Änderung.
  - Test: Ein Endpoint-Test ruft `/api/scheduler/status` auf und prüft die
    Anwesenheit von `enrichment_health` als eigenständigen Geschwister-Schlüssel
    (nicht verschachtelt in `briefing_health`) plus eine unveränderte
    `briefing_health`-Struktur gegen einen Referenzlauf ohne die Änderung.

- **AC-8:** Given der Radar-Nowcast läuft in einen echten Anbieterausfall
  (`data_unavailable=True`, `radar_service.py:567-571`) / When `get_nowcast()`
  den Miss-Zweig durchläuft / Then wird eine Journalzeile mit
  `outcome="unavailable"` unter `path="radar_nowcast"` geschrieben.
  - Test: Die Fetch-Fallback-Kette so faken, dass alle Quellen einen echten
    Fehler werfen (kein Cache-Treffer), danach das Journal auf die Zeile prüfen.

- **AC-9:** Given eine Anfrage wird vollständig aus dem Cache bedient
  (`radar_service.py:201-205`) / When `get_nowcast()` läuft / Then entsteht KEINE
  Journalzeile für diesen Aufruf. Begründung: `_derive_result()` läuft bei
  Cache-Hit UND -Miss; ein dort platzierter Aufruf würde einen Dauerausfall, der
  aus dem Cache weiterbedient wird, als lebendig ausweisen.
  - Test: Cache vorab mit einem gültigen Eintrag befüllen, `get_nowcast()`
    zweimal hintereinander aufrufen und das Journal nach dem zweiten
    (Cache-Hit-)Aufruf auf unveränderte Zeilenzahl prüfen.

- **AC-10:** Given der Abruf unterbleibt wegen eigener Budget-Drosselung
  (`radar_service.py:559`) / When `get_nowcast()` den Miss-Zweig durchläuft /
  Then wird eine Journalzeile mit `outcome="self_throttled"` geschrieben,
  unterscheidbar von `outcome="unavailable"`. Eigene Drosselung ist kein
  Anbieterausfall.
  - Test: Budget-Gate vorab erschöpfen (bestehendes Drosselungs-Testmuster),
    Journal auf `self_throttled` statt `unavailable` prüfen — beide Fälle in
    derselben Testdatei einander gegenübergestellt, damit eine Vertauschung
    sichtbar würde.

- **AC-11:** Given beide Pfade (Gewitter, Radar) nutzen denselben Schreibweg
  (`log_enrichment_call`) und denselben Go-Aggregator (`aggregateEnrichmentCalls`/
  `EnrichmentHealth`) / When ein gemeinsamer Baustein gezielt verfälscht wird
  (z. B. das Journalfeld `outcome` in der Schreibfunktion umbenannt) / Then
  werden die Tests BEIDER Pfade (`test_thunder_enrichment_health_journal.py` UND
  `test_radar_nowcast_health_journal.py`) rot, nicht nur die eines Pfades.
  - Test: Mutations-Gegenprobe (Pflicht, s. `.claude/agents/implementation-validator.md`
    Sektion „Step 3b") — Feldname per String-Ersetzung in `log_enrichment_call`
    testweise ändern (externe Sicherungskopie, kein `git checkout`), beide
    Testdateien laufen lassen und prüfen, dass beide rot werden.

- **AC-12:** Given die Primärquelle fällt aus UND die Vertretung wirft beim eigenen
  Versuch ebenfalls `ThunderSourceUnavailableError` (Ausnahme propagiert bis in den
  äußeren Fang `enrich_thunder()`, Zeilen 279-281) / When die Anreicherung
  durchläuft / Then wird eine Journalzeile mit `outcome="unavailable"` und
  `path="thunder"` geschrieben, und die Vorhersage selbst bleibt unbeschädigt
  (Fail-soft bleibt gewahrt). Dieser Ausgang ist der im Issue #1581 als „einziger
  Beobachtungspunkt" benannte Fall.
  - Test: Beide Quellen (Primär und Vertretung) werfen lassen, danach prüfen, dass
    (a) die Journalzeile existiert, (b) `enrich_thunder()` keine Ausnahme nach außen
    gibt und (c) die übrigen Vorhersagewerte identisch zum Lauf ohne Gewitterquelle
    sind.

- **AC-13:** Given die Gewitter-Anreicherung scheitert (Ausnahme im äußeren Fang) /
  When `enrich_thunder()` durchläuft / Then wird die bestehende Warnmeldung
  „Gewitter-Anreicherung fehlgeschlagen" tatsächlich ausgegeben und ist per
  Log-Mitschnitt nachweisbar. Löst Punkt 5 des Issues ein (Nebenbefund F003 aus
  #1199: der Log-Aufruf war bislang selbst unbewacht).
  - Test: `caplog` auf Level WARNING, Ausnahme im Anreicherungspfad auslösen und den
    Meldungstext im Mitschnitt nachweisen — der Test wird rot, wenn jemand den
    `logger.warning` entfernt oder auf ein niedrigeres Level absenkt.

## Known Limitations

- **`enrichment_calls.jsonl` ist append-only ohne Rotation**, wie
  `warn_service_calls.jsonl`. Größe/Rotation ist nicht Teil dieser Spec.
- **Der Health-Pfad unterscheidet bei Radar bewusst NICHT, welche der fünf
  Quellen ausfiel** (Radar-DWD, INCA/GeoSphere AT, AROME-FR, ICON-D2, ARPAE-2I) —
  ADR-0018 verlangt „Ausfall sichtbar", nicht „welche Quelle". Das ist ein
  Nicht-Ziel dieser Spec, damit der Scope am Umsetzungstag nicht wächst.
- **Die Auswerteregel in `henemm-infra/scripts/check-gregor20.sh` ist NICHT
  Teil dieser Spec.** Empfohlen dort: ein langes Frischefenster (24-48 h statt
  der 3 h des Warn-Dienstes — Anreicherung ist nicht briefing-kritisch), EXT-FAIL
  statt CORE für `outcome="unavailable"`-Dauerbefunde, CORE nur bei
  `journal_read_error` (unser eigener Fehler, analog `warn_service_health`).
  Diese Änderung geht per MQ an die `infra`-Instanz, inhaltlich nach Scheibe 1
  abgestimmt, final nach Scheibe 2.
- **Der scheinbare Widerspruch im Issue-Text ist bewusst zugunsten von Rohdaten
  aufgelöst** (s. ADR-Abschnitt) — dieser Punkt ist keine offene Frage mehr,
  sondern eine getroffene Entscheidung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** Addendum zu ADR-0047 (`docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md`);
  ADR-0018 wird nach Abschluss beider Scheiben auf „erfüllt" nachgezogen.
- **Rationale:**
  1. **Eigener Top-Level-Kanal `enrichment_health`, nicht innerhalb von
     `briefing_health`.** `check-gregor20.sh` liest `briefing_health` als
     „ist das Briefing gesund". Zusätzliche Schlüssel dort zwingen jeden
     künftigen Leser, briefing-kritische und nicht-kritische Schlüssel
     innerhalb desselben Objekts zu unterscheiden — genau die Vermengung, vor
     der ADR-0018 warnt. Ein eigenes Objekt macht die Trennung strukturell
     statt konventionell (Präzedenzfall: `warn_service_health`).
  2. **Rohdaten statt Streak-Berechnung in Go.** Der scheinbare Widerspruch
     zwischen dem Issue-Text („analog `provider_error_streak_since`") und der
     Forderung „Schwellen bleiben außerhalb des Repos" löst sich auf, wenn man
     „mit der Ausfalldauer wachsen" als Aussage über die **Wirkung** liest,
     nicht über die **Bauart**: `last_success_at` wächst automatisch, sobald
     außen `jetzt − last_success_at` gebildet wird — genau das tut
     `check-gregor20.sh` bereits für `warn_service_health`. Eine eigene
     Streak-Berechnung in Go hätte eine feste Lücken-Schwelle fest im Code
     verankert (wie `briefing_health.go:404`, 2 h), die beim Briefing
     sinnvoll ist, beim Radar mit seinem Cache aber schwer zu wählen und nur
     per Deploy korrigierbar wäre. Der Preis: „wächst mit der Dauer" ist damit
     keine in diesem Repo testbare Eigenschaft mehr, sondern eine der externen
     Auswertung — das ist die getroffene Entscheidung, kein offener Punkt.
  3. **Eigenes Journal, kein Ausbau von `call_log.py`.** `call_log.py` ist an
     HTTP-Abrufe gegen Open-Meteo gebunden und schreibt nach
     `openmeteo_calls.jsonl` — derselben Datei, die `briefing_health` liest.
     Ein Ausbau dort würde `coreBriefingSources` berühren und die zu
     vermeidende Vermengung erzeugen. Stattdessen ein neues Modul
     (`enrichment_health.py`) mit eigenem Journal
     (`data/diagnostics/enrichment_calls.jsonl`).

## Changelog

- 2026-08-19: Initial spec created (Issue #1581, beide Scheiben in einem
  Workflow, Analyse `docs/context/fix-1581-anreicherung-health.md`).
- 2026-08-19: AC-12 und AC-13 ergänzt. Der erste Entwurf hatte den sechsten
  Ausgang („Vertretung wirft ebenfalls") als Nicht-Ziel abgegrenzt — das ist
  aber genau der im Issue benannte einzige Beobachtungspunkt. AC-13 löst
  zusätzlich Punkt 5 des Issues ein (unbewachter `logger.warning`, F003 aus
  #1199), der im ersten Entwurf ganz fehlte.
