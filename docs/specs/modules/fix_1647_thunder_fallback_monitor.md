---
entity_id: fix_1647_thunder_fallback_monitor
type: module
created: 2026-09-17
updated: 2026-09-17
status: approved
version: "1.0"
tags: [observability, providers, health, monitoring]
---

# Betreiber-Alarm für dauerhaften Gewitter-Rückfall auf die Vertretung (`enrichment_health` in `check-gregor20.sh`)

## Approval

- [x] Approved — PO (Henning) am 2026-09-17

## Purpose

Spec #1581 hat das Health-Signal für degradierbare Anreicherungs-Pfade (Gewitter-Direktquellen,
Radar-Nowcast) gebaut und die Auswertung ausdrücklich an `henemm-infra/scripts/check-gregor20.sh`
delegiert (Known Limitation, Z. 347-353) — dort ist sie nie angekommen. Ein dauerhafter Rückfall
der Gewitter-Direktquelle auf die Vertretung `eu_direct` steht seither im Journal und im
Status-Endpunkt, löst aber keinen Betreiber-Alarm aus (Befund 17.09.2026, Issue #1647). Diese
Spec schließt genau diese letzte, fehlende Kettenglied: einen generischen Skript-Block, der
`enrichment_health` je Pfad auswertet, plus ein additives Go-Feld, das die Ersatzquelle der
jüngsten Vertretung in die Meldung trägt.

## Source

- **File (gregor, Go-API-Schicht):** `internal/scheduler/enrichment_health.go` (MODIFY),
  `internal/scheduler/enrichment_health_test.go` (MODIFY), `docs/reference/api_contract.md`
  (MODIFY, Feldbeschreibung)
- **File (henemm-infra, separates Repo):** `scripts/check-gregor20.sh` (MODIFY, neuer Block
  `2e-e`), `tests/test_check_gregor20_enrichment_health.py` (CREATE)
- **Identifier:** `scheduler.aggregateEnrichmentCalls` / `scheduler.EnrichmentHealth` (MODIFY,
  neues Feld `last_fallback_detail`); im Skript kein benannter Shell-Funktionsname — ein neuer
  Inline-Python-Block, markiert per Kommentar `# --- 2e-e enrichment_health ---`

**Schicht:** Go-API (`internal/scheduler/`) für die Leseseiten-Erweiterung. Die Auswerteregel
selbst liegt vollständig außerhalb dieses Repos, in `henemm-infra/scripts/check-gregor20.sh`
(Betreiber-Monitoring, kein Produktcode). Kein Python-Core, kein Frontend betroffen.

**Zwei Repos, eine Lieferung:** Die infra-Änderung wird von derselben Session/demselben Server-
User selbst umgesetzt (kein MQ, s. `~/.claude/CLAUDE.md` „Andere Sitzung im selben Projekt" gilt
hier nicht — es ist derselbe Zielserver, unmittelbarer Zugriff). Der gregor-Workflow-Gate
(LoC-Limit, Adversary, CI-Ampel) bewacht ausschließlich die gregor-Dateien; der infra-Commit
liegt außerhalb davon und wird über den eigenen pytest-Harness nachgewiesen.

## Estimated Scope

- **LoC:** gregor ~35 (Go + Test, additiv); henemm-infra ~80 Skript / ~110 Test (separates Repo,
  zählt nicht gegen das gregor-LoC-Limit)
- **Files:** 5 (3 gregor, 2 henemm-infra)
- **Effort:** medium (Alarmpfad, zwei Repos, aber additiv und ohne neue Schreibseite)

| Datei | Repo | Aktion | LoC (ca.) |
|---|---|---|---|
| `internal/scheduler/enrichment_health.go` | gregor | MODIFY | ~15 |
| `internal/scheduler/enrichment_health_test.go` | gregor | MODIFY | ~20 |
| `docs/reference/api_contract.md` | gregor | MODIFY | ~2 (Doku, zählt nicht) |
| `scripts/check-gregor20.sh` | henemm-infra | MODIFY | ~80 |
| `tests/test_check_gregor20_enrichment_health.py` | henemm-infra | CREATE | ~110 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal.scheduler.EnrichmentHealth()` / `aggregateEnrichmentCalls()` | intern (gregor) | Bestehendes Aggregat aus Spec #1581, wird um `last_fallback_detail` erweitert, nicht ersetzt |
| `internal.scheduler.nilIfEmpty` (`warn_service_health.go:163`) | intern (gregor), geteilter Helfer | Gibt `last_fallback_detail` als `null` statt leerem String aus |
| `henemm-infra/scripts/check-gregor20.sh` Block `2d` (`warn_service_health`-Auswertung, Z. 417-560) | Vorbild (infra) | CORE/EXT-Zuordnung, `age_hours()`, Zähler-Idiom `(( … )) || true`, try/except-Mantel — 1:1 auf `enrichment_health` übertragen |
| `henemm-infra/scripts/check-gregor20.sh` Blöcke `2e-b`/`2e-c`/`2e-d` (Z. 562-735) | Präzedenzfall (infra) | Belegen die Einschub-Konvention zwischen `2d` und dem bereits vorhandenen `2e` |
| `henemm-infra/tests/test_check_gregor20_logparse.py` | Muster (infra) | Extraktions-Idee (echte Skriptquelle statt Kopie); für Inline-Python-Blöcke aber NICHT direkt wiederverwendbar (s. Implementation Details, Punkt 3) |
| `docs/specs/modules/fix_1581_enrichment_health.md` | Vorgänger-Spec | Definiert Journal-Vokabular (`ok`/`fallback`/`unavailable`/`self_throttled`) und die Empfehlung „24-48h, EXT statt CORE" (Known Limitations, Z. 347-353), die diese Spec umsetzt |
| ADR-0018 „Modell-Fallback ohne Kaschieren" | Architektur | Fordert das hier fertiggestellte, bis zum Betreiber durchgehende Health-Signal |
| ADR-0047 + Addendum „Gewitter-Vertretung zwischen Direktquellen" | Architektur | Die Schwelle (48h) liegt bewusst außerhalb des Repos — Addendum-Entscheidung 2 aus #1581 |

## Implementation Details

**1. Go-Erweiterung (`internal/scheduler/enrichment_health.go`, additiv, keine bestehenden
Felder ändern):**

Neues Feld `lastFallbackDetail` im `enrichmentAgg`-Struct, gesetzt NUR innerhalb des
`case enrichmentOutcomeFallback:`-Zweigs und NUR gemeinsam mit der bestehenden
`lastFallbackAt`-Aktualisierung (`if entry.Ts > agg.lastFallbackAt`) — nie unabhängig davon:

```
case enrichmentOutcomeFallback:
    if entry.Ts > agg.lastFallbackAt {
        agg.lastFallbackAt = entry.Ts
        agg.lastFallbackDetail = entry.Detail
    }
```

Dieselbe Kopplung wie bei `lastAttemptAt`/`lastSuccessAt`: die jüngste `fallback`-Zeile gewinnt,
über den Zeitstempel entschieden, nicht über die Position in der Datei (Journal ist
append-only, aber nicht garantiert zeitlich sortiert). Eine jüngere `fallback`-Zeile mit leerem
`detail` überschreibt eine ältere mit gesetztem `detail` — „jüngster Fallback gewinnt" gilt
inklusive seines eigenen, ggf. leeren `detail`; es gibt bewusst keinen Rückfall auf das zuletzt
gesehene NICHT-leere `detail`.

Ausgabe in `EnrichmentHealth()`, additiv neben den vier Bestandsfeldern:

```
"last_fallback_detail": nilIfEmpty(agg.lastFallbackDetail),
```

`nilIfEmpty` ist bereits importiert/verfügbar (Vorbild `warn_service_health.go:163`, im selben
Package). Ohne jemals eine `fallback`-Zeile ist `lastFallbackDetail` der Go-Zero-Value `""` und
wird damit zu `null` — identisches Verhalten zu den drei bestehenden `nilIfEmpty`-Feldern.

**2. Skript-Block `2e-e` in `henemm-infra/scripts/check-gregor20.sh`:**

**Namenskorrektur zum Auftrag:** Der Arbeitsauftrag benennt den neuen Block als „2e". Das
Skript hat diesen Bezeichner aber bereits vergeben — Zeile 736 (`# 2e) Alarm-Job-Freshness`,
henemm-infra#167). Zwischen dem Vorbild-Block `2d` (Z. 417-560) und diesem `2e` sind bereits
drei Einschübe mit dem Muster `2e-<Buchstabe>` vorhanden: `2e-b` (Z. 562), `2e-c` (Z. 618),
`2e-d` (Z. 675). Diese Spec setzt die etablierte Einschub-Konvention fort und nennt den neuen
Block **`2e-e`**, eingefügt direkt nach dem Ende von `2e-d` (Z. 735) und direkt vor dem
bestehenden `2e` (Z. 736) — inhaltlich „direkt im Anschluss an den Anreicherungs-Themenblock",
technisch weiterhin klar vor dem Heartbeat-Gate (Z. 1266 ff.). Eine stillschweigende Umbenennung
auf den im Auftrag genannten Namen `2e` würde den bereits vergebenen Bezeichner doppelt belegen
und wäre beim nächsten `grep '^# 2'` nicht mehr eindeutig.

**Fenster als Shell-Variable**, Muster `ZONE_DRIFT_MAX_AGE_H` aus Block 2d:

```
ENRICHMENT_MAX_AGE_H=48
```

**Ausgabe-Kontrakt (fest, zwei Zeilen, feste Reihenfolge)** — kein SOFT-Kanal, anders als Block
2d, weil es hier keine „noch unkritische" Zwischenstufe gibt:

1. Zeile 1: `CORE_FAIL:<Text>` oder `CORE_OK`
2. Zeile 2: `EXT_FAIL:<Text>` oder `EXT_OK`

Die Shell liest `sed -n '1p'`/`'2p'`, genau wie bei Block 2d. Ein `except`-Zweig MUSS beide
Zeilen weiterhin liefern (Muster 2d: `print(f'CORE_FAIL: ... Parsing-Fehler: {e}')` gefolgt von
`print('EXT_OK')`) — ein Python-Absturz VOR den regulären `print`-Aufrufen liefert sonst eine
leere Variable, die von der Shell-Bedingung `[ "$X" != "CORE_OK" ] && [ -n "$X" ]` als „kein
Befund" durchgelassen wird: ein stiller Absturz sähe dann wie ein gesunder Zustand aus. Der
äußere `try/except Exception as e:` fängt das ab und macht daraus einen `CORE_FAIL`.

**Auswertelogik**, generisch über `for name, info in eh.items(): ` (`eh = d.get('enrichment_health')
or {}`, fehlender Schlüssel → stiller leerer Fall, kein Fehler — neue Pfade wie `snowgrid`/
`thunder_additive` erscheinen automatisch, Go-Aggregator ist bereits generisch, #1992 AC-8):

- `name == 'journal_read_error'` überspringen als Iterationsschlüssel, stattdessen VORAB
  separat prüfen: `if eh.get('journal_read_error'): core_issues.append(...)` — Muster 2d.
- Kein Dict (`isinstance(info, dict)` falsch) → überspringen.
- `attempt_age = age_hours(info.get('last_attempt_at'), now)`; ist er `None` oder
  `> ENRICHMENT_MAX_AGE_H` → `continue` (kein aktiver Trip in diesem Fenster = kein Alarm,
  AC-6).
- `success_age = age_hours(info.get('last_success_at'), now)`; ist er `None` oder
  `> ENRICHMENT_MAX_AGE_H`:
  - `age_str = 'nie' if success_age is None else f'{success_age:.0f}h'` (Muster 2d — es gibt
    kein `first_fallback_at`, `age_str` bezieht sich immer auf `success_age`, nie auf eine
    fiktive „Vertretungsdauer").
  - `fallback_age = age_hours(info.get('last_fallback_at'), now)`
  - Ist `fallback_age` nicht `None` und `<= ENRICHMENT_MAX_AGE_H`:
    `ext_issues.append(f"{name}: läuft seit {age_str} nur über Vertretung ({info.get('last_fallback_detail')})")`
  - Sonst: `reason = 'Gregor bremst sich selbst (Kontingent)' if info.get('self_throttled') else 'Anbieter nicht erreichbar'`;
    `ext_issues.append(f"{name}: kein Signal seit {age_str} ({reason})")`
- Ist `success_age` innerhalb des Fensters (auch bei älterem Fallback-Eintrag) → kein Eintrag,
  Pfad gilt als gesund (AC-5).

Ausgabe in der Shell (Muster 2d, Präfix „Anreicherung" statt „Warn-Dienst"):

```
if [ "$ENRICH_EXT" != "EXT_OK" ] && [ -n "$ENRICH_EXT" ]; then
    echo "FAIL[EXT]: Anreicherung — ${ENRICH_EXT#EXT_FAIL:}"
    ((EXT_ERRORS++)) || true
fi
if [ "$ENRICH_CORE" != "CORE_OK" ] && [ -n "$ENRICH_CORE" ]; then
    echo "FAIL: Anreicherung — ${ENRICH_CORE#CORE_FAIL:}"
    ((ERRORS++)) || true
fi
```

Platzierung: nach Block `2e-d`, vor Block `2e` (Alarm-Job-Freshness), also klar vor dem
Heartbeat-Gate (`# === Heartbeats ===`, Z. 1266 ff.).

**3. Testharness (`henemm-infra/tests/test_check_gregor20_enrichment_health.py`, CREATE):**

Der Vorgänger-Harness (`test_check_gregor20_logparse.py`) extrahiert eine benannte
Shell-**Funktion** per `re.search` auf einen eindeutigen Funktionsnamen — dieses Muster ist für
einen unbenannten Inline-Python-Block NICHT direkt übertragbar: das Skript enthält inzwischen
sechs `python3 -c "..."`-Blöcke (2c, 2d, 2e-b, 2e-c, 2e-d, 2e-e selbst); ein einfaches
`re.search(r'python3 -c "..."')` fände den ERSTEN Treffer (Block 2c), nicht den eigenen. Der
Harness MUSS deshalb:

- Mit `re.finditer(r'python3 -c "((?:[^"\\]|\\.)*)"', src, re.DOTALL)` über ALLE Inline-Blöcke
  iterieren,
- je Treffer auf den Marker-Kommentar `# --- 2e-e enrichment_health ---` prüfen (im
  extrahierten Python-Text muss diese Zeile als erste Kommentarzeile stehen),
- **genau einen** Treffer erwarten (`assert len(matches) == 1`) — kein Treffer oder mehr als
  einer ist ein harter Testfehler (Skript-Struktur hat sich unerwartet geändert), kein stilles
  Überspringen,
- innere `\"` im extrahierten Text zurück zu `"` ersetzen (wie im Analyse-Dokument
  vorgemerkt), dann per `subprocess.run(["python3", "-c", code], input=json.dumps(payload),
  capture_output=True, text=True, env=...)` ausführen.

**Fenster dynamisch aus der echten Skriptquelle, NICHT im Test hartkodiert:** Der Harness liest
den aktuellen Wert von `ENRICHMENT_MAX_AGE_H` per `re.search(r'ENRICHMENT_MAX_AGE_H=(\d+)', src)`
aus derselben Skriptquelle und übergibt ihn als Umgebungsvariable an `subprocess.run` (Muster:
das Skript selbst piped `ZONE_DRIFT_MAX_AGE_H` in Block 2d als Env-Variable in den
Python-Prozess — der Python-Block hier liest `ENRICHMENT_MAX_AGE_H` analog über
`os.environ.get(...)`). **Verboten:** der Harness setzt `ENRICHMENT_MAX_AGE_H` NICHT selbst fest
auf `48` — sonst bliebe eine Verfälschung des Skript-Werts (z. B. `48` → `1`) unbemerkt, weil
Skript-Wert und Test-Wert dann auseinanderlaufen könnten, ohne dass ein Test das je merkt. Mit
dynamischem Auslesen wird stattdessen der PROD-Wert getestet, und die AC-3-Testdaten (ein
Fallback von genau 47h Alter, siehe unten) fallen bei einer Mutation auf `1` aus dem Fenster —
das macht AC-3 rot (s. AC-9).

Fälle (mindestens sechs, den ACs 1:1 zugeordnet):
(a) frischer Versuch + kein frischer Erfolg + frischer Fallback → Vertretungstext mit Detail (AC-3);
(b) frischer Versuch + kein Erfolg + kein Fallback, je einmal mit/ohne `self_throttled` →
„kein Signal"-Text mit passendem Grund (AC-4);
(c) frischer Erfolg trotz altem Fallback → `EXT_OK` (AC-5);
(d) alter Versuch (kein aktiver Trip) trotz altem Fallback/Ausfall → `EXT_OK`, Blindheits-
Gegenbeweis (AC-6);
(e) `journal_read_error: true` → `CORE_FAIL`, nicht `EXT_FAIL` (AC-7);
(f) fehlender Schlüssel `enrichment_health` bzw. Pfad-Eintrag ohne `last_fallback_detail` →
Exit-Code 0, beide Ausgabezeilen vorhanden (AC-8).

KEIN Mock, KEIN Dateiinhalt-Check als Verhaltensnachweis — jeder Fall prüft das tatsächliche
`stdout`/`returncode` des laufenden Python-Prozesses gegen synthetisches JSON auf stdin.

## Expected Behavior

- **Input (Go):** ein Journal-Eintrag mit `outcome="fallback"` und gesetztem `detail`
  (`src/providers/thunder_enrichment.py`, unverändert seit #1581).
- **Output (Go):** `/api/scheduler/status.enrichment_health.<pfad>.last_fallback_detail` — die
  Ersatzquelle der jüngsten Vertretung, `null` ohne Fallback. Additiv, alle vier Bestandsfelder
  unverändert.
- **Input (Skript):** die Antwort von `/api/scheduler/status` (`SCHED_RESPONSE`, bereits
  vorhanden), Schlüssel `enrichment_health`.
- **Output (Skript):** bei anhaltendem Rückfall auf die Vertretung oder anhaltendem Ausfall
  ohne Vertretung eine `FAIL[EXT]:`-Zeile im Cron-Log, `EXT_ERRORS` erhöht, der EXT-Heartbeat
  bleibt aus → BetterStack schickt einen E-Mail-Alert an den PO. Bei gesundem oder tourlosem
  Zustand keine Ausgabe, EXT-Heartbeat pingt wie bisher.
- **Side effects:** keine auf den fachlichen Datenfluss — reine Leseseiten-/Monitoring-
  Erweiterung, kein Einfluss auf Briefing-Inhalte, keine neue Schreibseite.

## Acceptance Criteria

Die Doku-Änderung an `docs/reference/api_contract.md` (neue Feldzeile
`enrichment_health.<path>.last_fallback_detail`) bekommt bewusst KEINE eigene AC — ein
Dateiinhalt-Check wäre kein Verhaltensnachweis (CLAUDE.md „Mock-Theater"-Verbot analog). Sie
wird als Begleit-Änderung zu AC-1/AC-2 mitgeliefert.

- **AC-1:** Given ein Journal enthält für Pfad `thunder` zwei `outcome="fallback"`-Zeilen mit
  unterschiedlicher Ersatzquelle (`detail="eu_direct"` vs. `detail="fr_direct"`), wobei die
  zeitlich ÄLTERE Zeile in der Datei ZULETZT steht (append-only, aber nicht zwingend zeitlich
  sortiert) / When `EnrichmentHealth()` aggregiert / Then trägt
  `enrichment_health.thunder.last_fallback_detail` die Ersatzquelle der zeitlich JÜNGEREN
  Zeile — der Vergleich läuft über den Zeitstempel, nicht über die Position in der Datei.
  - Test: Journal mit den zwei Zeilen in absichtlich vertauschter Schreibreihenfolge aufbauen
    (Muster `enrichmentLine`/`writeEnrichmentJournal`), `EnrichmentHealth()` real aufrufen und
    `last_fallback_detail` gegen die jüngere Quelle prüfen. Eine Implementierung „letztes
    gesehenes NICHT-leeres detail" bestünde diesen Test nicht. Zusatzfall im selben Test: eine
    noch jüngere dritte Zeile mit `outcome="fallback"` und `detail=null` setzt
    `last_fallback_detail` auf `null` — der jüngste Fallback gewinnt inklusive seines eigenen,
    ggf. leeren `detail`.

- **AC-2:** Given ein Journal für einen Pfad enthält ausschließlich `outcome="ok"`/
  `"unavailable"`/`"self_throttled"`-Zeilen, keine einzige `fallback`-Zeile / When
  `EnrichmentHealth()` aggregiert / Then ist `last_fallback_detail` `null`, und
  `last_attempt_at`, `last_success_at`, `last_fallback_at`, `self_throttled` liefern denselben
  Wert wie vor dieser Änderung.
  - Test: einen bestehenden Testfall (Muster
    `TestEnrichmentHealthSelfThrottledNurBeiEigenerDrosselung`) um eine Prüfung
    `entry["last_fallback_detail"] == nil` erweitern, während die vier Bestandsfelder
    unverändert gegen ihre bisherigen Erwartungswerte laufen — additive Erweiterung, kein
    bestehender Test darf umgeschrieben werden müssen.

- **AC-3:** Given `/api/scheduler/status.enrichment_health.<pfad>` liefert `last_attempt_at`
  frisch (≤48h), `last_success_at` `null` oder älter als 48h, UND `last_fallback_at`/
  `last_fallback_detail` frisch (≤48h, konkret: 47h alt in der Testfixture) / When Block
  `2e-e` den Status auswertet / Then meldet das Skript
  `FAIL[EXT]: Anreicherung — <pfad>: läuft seit <Xh> nur über Vertretung (<last_fallback_detail>)`
  (X = Alter von `last_success_at`), zählt `EXT_ERRORS` hoch; der EXT-Heartbeat bleibt aus.
  - Test: synthetisches JSON mit obigem Muster über den echten, per Marker-Kommentar
    extrahierten Python-Block laufen lassen (Fenster-Umgebungsvariable `ENRICHMENT_MAX_AGE_H`
    dynamisch aus der echten Skriptquelle gelesen, nicht hartkodiert), die `EXT_FAIL:`-Zeile
    auf Vertretungstext UND die konkrete Ersatzquelle prüfen — Betreiber-Sicht: genau dieser
    Fehlertext (und nur er) löst das Ausbleiben des EXT-Heartbeats aus. Fehlt `last_fallback_detail`,
    steht `Ersatzquelle unbekannt` im Text, nie `None`.

- **AC-4:** Given frischer Versuch (≤48h), kein Erfolg seit >48h (oder nie), kein frischer
  Fallback / When Block `2e-e` läuft / Then meldet das Skript
  `FAIL[EXT]: Anreicherung — <pfad>: kein Signal seit <Xh> (Gregor bremst sich selbst (Kontingent))`
  bei `self_throttled=true`, sonst mit `(Anbieter nicht erreichbar)`; `EXT_ERRORS` steigt in
  beiden Fällen.
  - Test: zwei Fälle im selben Testmodul einander gegenüberstellen (`self_throttled=true` vs.
    `false`), jeweils den Grund-Text prüfen — eine Vertauschung der beiden Gründe (Muster AC-10
    aus Spec #1581) würde beide Testfälle gleichzeitig rot machen.

- **AC-5:** Given `last_success_at` liegt innerhalb 48h, gleichzeitig steht ein ÄLTERER (>48h)
  `last_fallback_at`/`last_fallback_detail`-Eintrag im Status / When Block `2e-e` läuft / Then
  meldet das Skript für diesen Pfad keinen Fehler (`EXT_OK`), `EXT_ERRORS` bleibt unverändert,
  der EXT-Heartbeat pingt.
  - Test: JSON mit frischem Erfolg und altem Fallback einspeisen, `EXT_FAIL:`-Zeile bleibt
    `EXT_OK` — Betreiber-Sicht: eine längst überwundene Vertretungsphase löst keinen
    nachträglichen Alarm mehr aus.

- **AC-6:** Given `last_attempt_at` liegt >48h zurück (kein aktiver Trip), unabhängig davon, ob
  ein alter Fallback- oder Dauerausfall-Eintrag im Status steht / When Block `2e-e` läuft /
  Then meldet das Skript keinen Fehler für diesen Pfad — ein tourloser Zeitraum darf niemals
  alarmieren.
  - Test: JSON mit `last_attempt_at` vor 60h und gleichzeitig altem `unavailable`/`fallback`-
    Verlauf einspeisen, `EXT_OK` erwarten — der Blindheits-Gegenbeweis zur eigentlichen
    Kernbedingung aus AC-3/AC-4.

- **AC-7:** Given der Status trägt `enrichment_health.journal_read_error: true` / When Block
  `2e-e` läuft / Then meldet das Skript einen `CORE_FAIL`-Befund
  („Anreicherungs-Journal nicht lesbar"), NICHT `EXT_FAIL` — das ist Gregors eigener Fehler,
  kein Anbieterausfall.
  - Test: JSON mit `journal_read_error: true` (und ansonsten leerem `enrichment_health`)
    einspeisen, `CORE_FAIL:`-Zeile auf den Befund prüfen und `EXT_OK` in derselben Ausführung
    bestätigen.

- **AC-8:** Given die Antwort enthält KEINEN Schlüssel `enrichment_health` (alter
  Scheduler-Stand) ODER ein Pfad-Eintrag ohne `last_fallback_detail` (Feld noch nicht
  ausgerollt) / When Block `2e-e` läuft / Then terminiert der Python-Block mit Exit-Code 0 und
  liefert exakt die zwei erwarteten Ausgabezeilen `CORE_OK`/`EXT_OK` in fester Reihenfolge —
  kein stiller Absturz, der als „kein Fehler" fehlinterpretiert würde.
  - Test: zwei Durchläufe — (a) JSON ganz ohne den Schlüssel `enrichment_health`, (b) JSON mit
    `enrichment_health`, aber ohne `last_fallback_detail` in einem Pfad-Eintrag; je Durchlauf
    `subprocess.run(...).returncode == 0` UND beide Ausgabezeilen in der festen Reihenfolge
    (`CORE_...` dann `EXT_...`) prüfen — ein `KeyError`/`AttributeError` im Block würde den
    Exit-Code auf ungleich 0 setzen und muss den Test rot machen.

- **AC-9:** Given die Mutations-Gegenprobe für den Alarmpfad ist Pflicht (CLAUDE.md) / When (1)
  `ENRICHMENT_MAX_AGE_H` im Skript testweise von `48` auf `1` gesetzt wird (String-Ersetzung mit
  externer Sicherungskopie, kein `git checkout`) UND (2) die Erfolgsbedingung in Block `2e-e`
  invertiert wird (z. B. `success_age > ENRICHMENT_MAX_AGE_H` → `success_age <
  ENRICHMENT_MAX_AGE_H`) / Then wird bei (1) der AC-3-Test rot (der Harness liest
  `ENRICHMENT_MAX_AGE_H` dynamisch aus der echten Skriptquelle — der mutierte Wert `1` lässt
  den 47h alten Fallback der AC-3-Testfixture aus dem Fenster fallen, der Vertretungstext
  bleibt aus) und bei (2) der AC-5-Test rot (ein frischer Erfolg würde fälschlich als
  Dauerausfall gemeldet).
  - Test: kein zusätzlicher automatisierter Test — Adversary-Auftrag (Step 3b): beide
    Mutationen einzeln durchführen, `tests/test_check_gregor20_enrichment_health.py` erneut
    laufen lassen, das Rot-Werden von genau AC-3 bzw. AC-5 protokollieren, danach die
    Sicherungskopie zurückspielen.

- **AC-10:** Given Issue #1647 trägt noch den alten Titel (MeteoFrance-401-fokussiert, durch
  die Messung vom 09.09.2026 überholt) / When diese Lieferung abgeschlossen ist / Then trägt
  das Ticket den neuen Titel „Dauerhafter Gewitter-Rückfall auf `eu_direct` bleibt ohne
  Betreiber-Alarm (check-gregor20.sh liest enrichment_health nicht)", und der Epic-#2257-Eintrag
  zu #1647 verweist auf den neuen Stand.
  - Test: `gh issue view 1647 --json title` nach Abschluss gegen den neuen Titelwortlaut
    prüfen — kein Dateiinhalt-Check, sondern der tatsächliche Ticket-Zustand auf GitHub.

## Known Limitations

- **Pfad-Aggregation kennt keine Region.** `thunder` mischt DE- und FR-Abrufe (ADR-0047). Ein
  DE-Trip mit Erfolg hält `last_success_at` frisch, während ein FR-Trip dauerhaft auf
  `eu_direct` läuft — der Alarm bliebe in diesem Fall stumm. Bereits in Spec #1581 als
  Nicht-Ziel dokumentiert („Ausfall sichtbar, nicht welche Quelle"); im Ein-Trips-Betrieb
  irrelevant, für künftigen Multi-Region-Betrieb eine offene Grenze.
- **`last_fallback_detail` ist die Ersatzquelle, nicht die ausgefallene Primärquelle.**
  `last_fallback_detail="eu_direct"` sagt „läuft auf DWD Europa", nicht ob `fr_direct` oder
  `de_direct` ausgefallen ist (`thunder_routing.py:176-186`). Reicht für den hier gebauten
  Alarm, beantwortet aber nicht „welche Direktquelle ist kaputt".
- **Prod kann den Fall aktuell nicht live zeigen.** `thunder.last_attempt_at` stand am
  17.09.2026 auf dem 05.09. (Tourende KHW, kein aktiver Trip). Der Nachweis ist deshalb rein
  synthetisch (Go-Testfixtures, JSON-Payload im Skript-Test) plus Mutationsprobe (AC-9), nicht
  durch einen beobachtbaren Prod-Vorfall.
- **Die Auswerteregel liegt strukturell außerhalb des gregor-Repos.** Der infra-Commit
  (`check-gregor20.sh` + neue Testdatei) durchläuft keinen gregor-Workflow-Gate (LoC-Limit,
  Adversary, CI-Ampel) — sein einziger Nachweis ist der eigene pytest-Harness im
  henemm-infra-Repo. Eine künftige Drift zwischen Go-Feldnamen und Skript-Auswertung würde
  dort, nicht hier, auffallen.
- **Kein SOFT-Kanal für diesen Block**, anders als Block 2d (`zone_drift` mit
  `unmapped_without_warning`). Es gibt bei der Anreicherung keine „noch harmlose"
  Zwischenstufe zwischen gesund und Vertretung/Ausfall — bewusst einfacher gehalten als das
  Vorbild.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue ADR. Diese Spec ändert keine ADR-Datei — sie löst die in Spec #1581
  dokumentierte, an `check-gregor20.sh` delegierte Auswerteregel ein (Known Limitation dort,
  Z. 347-353) und setzt damit die von ADR-0018 geforderte, bis zum Betreiber durchgehende
  Alarmkette sowie die Addendum-Entscheidung 2 zu ADR-0047 (Schwelle bewusst außerhalb des
  Repos, extern in `check-gregor20.sh` gebildet) fertig um.
- **Rationale:** Beide Grundsatzentscheidungen (eigener Top-Level-Kanal, Rohdaten statt
  Streak-Berechnung in Go) sind bereits in Spec #1581 getroffen und unverändert gültig; diese
  Spec fügt nur die additive Ersatzquellen-Ausgabe (Go) und die seit einem Monat fehlende
  externe Auswertung (infra) hinzu. Eine eigene ADR für eine reine Nachlieferung einer bereits
  entschiedenen Architektur wäre Regel-Inflation ohne neuen Entscheidungsgehalt.

## Changelog

- 2026-09-17: Initial spec created (Issue #1647, Analyse
  `docs/context/fix-1647-thunder-fallback-monitor.md`, Epic #2257, Dach #1419). Block-Name im
  Arbeitsauftrag lautete „2e" — dieser Bezeichner ist im Skript bereits seit henemm-infra#167
  (Z. 736, Alarm-Job-Freshness) vergeben; diese Spec benennt den neuen Block stattdessen `2e-e`
  gemäß der bereits etablierten Einschub-Konvention (`2e-b`/`2e-c`/`2e-d` zwischen `2d` und
  `2e`).
- 2026-09-18: Fix-Loop F001/F002 (Adversary Runde 2).
