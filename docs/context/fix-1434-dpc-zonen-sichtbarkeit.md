# Context: fix-1434-dpc-zonen-sichtbarkeit

Issue: [#1434](https://github.com/henemm/gregor_zwanzig/issues/1434) — „Zonen-Neuschnitt beim DPC kann
gewarnte Gebiete lautlos verschwinden lassen". Herkunft: Adversary-Befund F002 aus
`feat-1427-s2-dpc-quelle`, bewusst nicht in #1427 behoben (dortige Spec, Known Limitations
Zeile 346–348).

## Request Summary

Die italienische Warnquelle (DPC) ordnet einen Ort seiner Warnzone über eine **eingecheckte,
statische Geometrie** zu (`data/dpc_zones.json`, 187 Zonen, Stand Juli 2026), während die
Warnstufen **tagesaktuell** aus dem Bulletin kommen. Driften beide auseinander — der DPC
schneidet Zonen neu — können amtliche Hochwasser-/Erdrutsch-/Gewitterwarnungen still aus dem
Ergebnis fallen. Gesucht ist **Betriebs-Sichtbarkeit** dieses Auseinanderdriftens, nicht die
automatische Korrektur.

## Kernfund der Analyse: es sind ZWEI Verlustpfade, nicht einer

Das Issue beschreibt nur den ersten. Der zweite ist der nutzerwirksame — und der ist **komplett
ungeloggt**.

| # | Richtung | Wo im Code | Heute sichtbar? | Wirkung |
|---|---|---|---|---|
| **A** | Bulletin trägt Zonencode, den die **Geometrie** nicht kennt | `dpc.py:114-119` `_records_by_zone()` | `logger.warning` je unbekanntem Code, je Abruf | Zeile wird verworfen. Kein Ort kann sie erreichen — die Geometrie kennt die Zone ja nicht. |
| **B** | Geometrie trägt Zonencode, den das **Bulletin** nicht mehr kennt | `dpc.py:227-229` `fetch()`, `row = day_records.get(zone_code); if row is None: return []` | **nein — kein Log, keine Spur** | Der Ort wird einer *veralteten* Zone zugeordnet; das Bulletin hat unter diesem Code nichts → stille Rückgabe „keine Warnung". |

Beim Zonen-Neuschnitt treten **beide gleichzeitig** auf: `Vene-A` (alt, in unserer Geometrie)
verschwindet aus dem Bulletin ⇒ Pfad B für jeden Ort in Venetien; `Vene-A1…A2` (neu, im Bulletin)
fehlt unserer Geometrie ⇒ Pfad A. Der Wanderer merkt nur Pfad B, und genau der protokolliert
nichts.

Gegenprobe zum Belegstand: die eingecheckte Geometrie trägt heute die **25** Venetien-Zonen
`Vene-A1 … Vene-H6` (Juli-Schnitt), nicht die 8 aus Januar — aktuell also deckungsgleich.
Der Schaden ist latent, nicht akut.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/official_alerts/dpc.py` | Beide Verlustpfade (`_records_by_zone` 114-119, `fetch` 220-230). 230 Zeilen gesamt. |
| `src/services/official_alerts/data/dpc_zones.json` | Die statische Geometrie (187 Zonen), deren Alterung das Risiko erzeugt. Erzeugt durch Wegwerf-Skript außerhalb des Repos. |
| `src/services/official_alerts/warn_egress.py:212-254` | `log_warn_service_call()` — der einzige bestehende Diagnose-Kanal (`data/diagnostics/warn_service_calls.jsonl`). Additiv erweiterbar, Präzedenz #1422 S1 (`ok`, `self_throttled`). |
| `internal/scheduler/warn_service_health.go` | Go-Aggregation des Journals je Dienst → `WarnServiceHealth()`, 216 Zeilen. Hier müsste ein neues Signal aufgenommen werden. |
| `internal/scheduler/scheduler.go:533` | Einbindung als `warn_service_health` in den Status. |
| `internal/router/router.go:198` + `internal/middleware/auth.go:34` | `/api/scheduler/status`, bewusst **ohne Anmeldung** erreichbar — genau damit die Infra-Instanz ihn abfragen kann. |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:57-118` | Der einzige Konsument, der aus dem Status tatsächlich einen Alarm macht. |
| `tests/tdd/test_dpc_bulletin_source.py` | 12 Tests, darunter `test_ac5c_unbekannter_zonencode_wird_geloggt_kein_crash` (Pfad A). **Kein Test für Pfad B.** |
| `tests/tdd/test_warn_service_health_journal.py`, `internal/scheduler/warn_service_health_test.go` | Bestehende Nachweise für den Journal-/Status-Weg. |

## Existing Patterns

1. **Zweiteilung Kern ↔ Infra (etabliert, #1422 / henemm-infra#150, live seit 30.07.):**
   Der Kern liefert **rohe Beobachtungswerte** über `/api/scheduler/status`; die
   Schwellen- und Alarmlogik lebt in `check-gregor20.sh` in der Infra-Instanz, beauftragt per
   Inter-Instanz-Nachricht an `infra`. Nicht der Kern entscheidet, wann Alarm ist.
2. **Rein additive Journal-Felder:** #1422 S1 hat `ok` und `self_throttled` ergänzt, ohne
   bestehende Leser zu brechen; Go liest fehlende Felder als „keine Evidenz", nicht als Fehler
   (`Ok *bool`).
3. **Fail-soft in Warnquellen (ADR-0018):** ein Datenproblem darf nie das Briefing killen und
   nie eine Warnung erfinden. Gilt auch hier — Diagnose darf den Abruf nicht beeinflussen
   (`log_warn_service_call` schluckt jeden Fehler).
4. **„Nicht abrufbar" ≠ „keine Warnung" (#1348, #1346):** die begriffliche Trennung, die dieses
   Issue auf den Fall „nicht zuordenbar" ausdehnt.
5. **Statische Geo-Dateien:** `massif_polygons.json`, `department_polygons.json` — dasselbe
   Muster, dieselbe latente Alterung, bisher ohne Auffrischungs-Turnus.

## Dependencies

- **Upstream:** `warn_egress.cached_fetch()` (Abruf + Cache + Journal), `geo_ray_cast._point_in_ring`,
  `data/dpc_zones.json`, das öffentliche DPC-Zip.
- **Downstream:** `official_alerts/base.py` (Registry, Zwei-Pass-Partitionierung), alle
  Briefing-/Alarm-Renderer; Go-`WarnServiceHealth()` → `/api/scheduler/status` →
  `check-gregor20.sh` → BetterStack/Telegram.

## Existing Specs

- `docs/specs/modules/feat_1427_dpc_warn_fallback.md` (Fassung 2.0) — AC-5 (Fail-soft/Logging),
  Known Limitations Zeile 341–348 verweist ausdrücklich auf dieses Issue.
- `docs/specs/modules/fix_1422_warn_ausfall_alarm.md` — Journal-Felder, `WarnServiceHealth()`,
  Abschnitt „Schnittstelle für Teil B" (Vertrag mit `infra`).
- `docs/specs/modules/warn_unavailable_hint.md` (#1348) — „nicht abrufbar"-Hinweis.
- `docs/adr/` — ADR-0016 (additive Quellen), ADR-0018 (Fail-soft).

## Risks & Considerations

- **🔴 Ein Zähler, den niemand liest, ist Sicherheits-Theater.** `check-gregor20.sh` wertet heute
  `briefing_health` aus, `warn_service_health` **nicht** — der #1422-Zustand liegt im Status,
  aber die Auswertung dort deckt ihn nicht ab. Ein neues Feld ohne Auftrag an `infra` ändert
  faktisch nichts. Das ist genau die Falle, vor der die Heartbeat-Regel in `~/.claude/CLAUDE.md`
  warnt (Readiness statt Liveness).
- **Pfad B ist ortsabhängig, nicht bulletinweit.** Pfad A lässt sich beim Parsen einmal je Abruf
  zählen; Pfad B tritt nur auf, wenn ein *beobachteter* Ort in einer verwaisten Zone liegt.
  Beide in einer Kennzahl zu vermischen wäre irreführend.
- **Rauschen vermeiden:** Ein Bulletin ohne Warnung (`NESSUNA`) unter unbekanntem Code ist
  harmlos; ein Bulletin **mit** echter Warnung unter unbekanntem Code ist der gefährliche Fall.
  Ohne diese Trennung erzeugt jeder DPC-Zuschnittwechsel Dauerrauschen (vgl. Code-Drift-Schwelle
  in `check-gregor20.sh`: zu enge Schwelle war dort die häufigste Ursache für abgeschaltete
  Heartbeats).
- **Kontingent/Egress:** keiner. Die Diagnose fällt beim ohnehin stattfindenden Abruf ab, kein
  zusätzlicher Netzzugriff.
- **Kein Selbstheilungs-Versprechen:** Die Geometrie automatisch zur Laufzeit nachzuziehen wäre
  ein anderer, deutlich größerer Umbau (Shapefile-Geometrie-Parsing zur Laufzeit — in #1427
  bewusst verworfen, Präzedenz rasterio/#1162 legte Staging 14 Min lahm). Nicht Gegenstand.
- **Datei-Rechte:** `data/diagnostics/warn_service_calls.jsonl` ist nur als `claude-gregor`
  lesbar — Nachweisführung entsprechend planen.

## Lösungsraum (Entscheidung steht beim PO, s. Spec-Phase)

| Variante | Inhalt | Aufwand | Wirkung |
|---|---|---|---|
| **V1 „Nur zählen"** | Beide Pfade im Journal sichtbar machen, Go aggregiert, Status zeigt es an | klein | Nachweisbar erst, wenn jemand hinsieht — heute niemand |
| **V2 „Zählen + alarmieren" (empfohlen)** | V1 **plus** Auftrag an `infra`, `check-gregor20.sh` auszuwerten (Schwelle: unbekannter Code **mit** echter Warnung, bzw. Ort in verwaister Zone) | klein + eine MQ-Nachricht | Erreicht tatsächlich jemanden — exakt das Muster #1422 Teil A/B |
| **V3 „V2 + Auffrischungs-Turnus"** | zusätzlich dokumentierter Wartungsschritt für `dpc_zones.json` | + Doku | Behebt die Ursache statt nur zu melden; ohne Alarm aber unbegründet getaktet |

## PO-Entscheide (2026-07-31, beide erteilt)

1. **Variante V2** — beide Pfade erfassen, im Systemzustand sichtbar machen **und** die
   Auswertung/Alarmierung per Inter-Instanz-Nachricht bei `infra` beauftragen
   (`check-gregor20.sh`). Ein Zähler ohne Konsument reicht ausdrücklich nicht.
2. **Pfad B wird nutzersichtbar** — ein Ort in einer verwaisten Zone löst die bestehende
   Kennzeichnung „amtliche Warnungen aktuell nicht abrufbar" (#1348) aus, statt stumm
   „keine Warnung" zu liefern. Konsistent zu #1348, das dieselbe Verwechslung für Ausfälle
   bereits beseitigt hat.

## Zwei Befunde, die den Bau verbilligen bzw. absichern

**(1) Der Haken für Pfad B existiert bereits.** `warn_egress.mark_fetch_incomplete()`
(`warn_egress.py:69-81`, eingeführt für #1397 S1c) ist der öffentliche Weg, einen Abruf als
„nicht vollständig abrufbar" zu markieren, **ohne** dass `cached_fetch()` selbst fehlschlug —
er markiert den `observe_fetch_failure()`-Kontext, den `base.py:135-146` bereits auswertet.
Ein Aufruf an der `row is None`-Stelle in `dpc.py:227-229` genügt, damit `unavailable=True`
wird und der #1348-Hinweis erscheint. Kein neuer Mechanismus nötig.

**(2) Ein fehlender Bulletin-Eintrag ist nachweislich eine Anomalie, kein Normalfall.**
Live-Messung 2026-07-31 gegen das echte Bulletin `20260730_1511`
(Prüfskript einmalig, nicht im Repo):

| Datensatz | Zeilen | eindeutige Codes | Pfad B (Geometrie ohne Bulletin) | Pfad A (Bulletin ohne Geometrie) |
|---|---|---|---|---|
| `..._today.dbf` | 187 | 187 | **0** | **0** |
| `..._tomorrow.dbf` | 187 | 187 | **0** | **0** |

Das Bulletin trägt also *jede* der 187 Zonen, auch die ohne Warnung (`NESSUNA ALLERTA`).
Ein fehlender Eintrag kann folglich nicht „normales Schweigen" bedeuten — die
Rausch-Sorge aus „Risks & Considerations" entfällt für Pfad B. Für Pfad A bleibt die
Trennung „unbekannter Code **mit** echter Warnung" vs. „mit `NESSUNA`" trotzdem sinnvoll,
weil nur ersterer echten Verlust bedeutet.

## Voraussichtlicher Schnitt (Detaillierung in der Spec)

Grobschätzung ~250 LoC inkl. Tests über Python **und** Go — an der Obergrenze. Wahrscheinlich
zwei Scheiben:

- **S1 (Kern/Python):** Pfad B erkennen → `mark_fetch_incomplete()` + Protokoll; Pfad A
  nach „mit/ohne echte Warnung" trennen; Journal-Feld additiv. Nutzersichtbare Wirkung
  vollständig hier.
- **S2 (Zustand/Go + Infra):** Aggregation in `WarnServiceHealth()`, Feld in
  `/api/scheduler/status`, danach Auftrag an `infra` für die Alarmschwelle.
