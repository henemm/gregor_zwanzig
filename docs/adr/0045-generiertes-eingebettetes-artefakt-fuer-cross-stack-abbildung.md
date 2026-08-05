# ADR-0045: Generiertes, kompilierzeit-eingebettetes Artefakt löst Cross-Stack-Duplikate — nicht nur ein Paritätstest

- **Status:** Akzeptiert (PO-Entscheidung 2026-08-05)
- **Datum:** 2026-08-05
- **Bezug:** Issue #1435 Etappe E5, ADR-0015 (Dual-Stack-Zielarchitektur, Regel 3 — ergänzt, nicht abgelöst), Issue #1387 (Vorläufer-Vorfall, Python↔TS-Paritätstest), `docs/specs/modules/fix_1435_e5_alert_mapping_unify.md`

## Kontext

ADR-0015 Regel 3 fordert „keine Logik-Duplizierung zwischen den Stacks — pro Fall
EINE Seite als Owner bestimmen, andere abbauen", benennt aber keinen Mechanismus
dafür. Die Zuordnung „Katalog-Metrik-ID → alarmfähige AlertMetric(s)" existierte
dreifach handgepflegt: als Go-Literal (`internal/model/trip.go`), als
Python-Master-Dict (`src/services/weather_change_detection.py`) und als
TS-Literal (`corridorEditorState.ts`). Nach dem Vorläufer-Vorfall #1387 war nur
Python↔TS gegeneinander automatisiert geprüft (Regex-Parität); die Go-Kopie blieb
unbewacht, ihr eigener Kommentar behauptete fälschlich, geprüft zu sein.

Ein reiner erweiterter Paritätstest (Go-Kopie zusätzlich per Regex geprüft) hätte
drei Handkopien belassen — mehr Prüfung, aber keine echte Konsolidierung.

## Entscheidung

> **Python bleibt einzige Quelle. Ein Erzeuger-Skript generiert daraus
> eingecheckte JSON-Artefakte; Go bindet sein Artefakt per `go:embed` beim
> Kompilieren fest ein; das Frontend importiert dieselbe generierte Datei
> direkt (Vite `resolveJsonModule`). Ein Ratchet-Test hält Quelle und
> generierte Dateien in Deckung.**

`catalog_id_to_alert_metrics()` (`weather_change_detection.py`) bleibt der
Domain-Owner. `scripts/generate_alert_metric_mapping.py` serialisiert ihre
Ausgabe deterministisch in zwei Zieldateien (`internal/model/alert_metric_mapping.generated.json`,
`frontend/src/lib/generated/alertMetricMapping.generated.json` — zwei physische
Dateien, weil `go:embed` keine Datei außerhalb seines Verzeichnis-Teilbaums
referenzieren kann). Go parst die eingebetteten Bytes einmalig beim
Package-Init (`mustParseAlertMetricMapping`, fail-loud bei kaputtem JSON). Das
Frontend leitet seine Konstante aus dem JSON-Import ab, minus zwei benannter,
weiterhin bewachter Ausnahmen. `tests/tdd/test_alert_metric_mapping_parity.py`
vergleicht die frisch berechnete Python-Abbildung gegen beide generierten
Dateien (`check()`) — Drift, egal ob durch geänderte Python-Quelle ohne
Neu-Generierung oder durch von Hand verfälschte generierte Datei, wird konkret
mit Katalog-ID benannt.

Damit gibt es strukturell keine Go-Handkopie mehr, die driften könnte — Go
bekommt keinen eigenen Python-seitigen Prüfschritt mehr, weil es nichts mehr zu
vergleichen gibt.

## Alternativen, die verworfen wurden

**Laufzeit-HTTP-Call im synchronen Persistenzpfad.** `ActiveAlertableMetricIDs()`
läuft innerhalb `store.SaveTrip`/`LoadTrip` — kein Async-Offload. Ein Live-Abruf
beim Python-Core an dieser Stelle wäre ein neues Ausfallrisiko (Python-Core down
beim Trip-Speichern), abweichend vom bisherigen Nur-Proxy-Muster für
GET-Endpunkte.

**Reiner erweiterter Paritätstest ohne echte Konsolidierung.** Hätte die
Go-Kopie zusätzlich geprüft, aber drei Handkopien wären bestehen geblieben —
jede Änderung hätte weiterhin drei manuelle Nachzieh-Schritte gebraucht.

## Konsequenzen

**Neues, im Projekt bisher unbelegtes Muster:** kein bestehendes `go:embed`,
kein Codegen-Schritt aus Python-Quelltext vor dieser Etappe. Als Vorbild für
strukturell ähnliche Cross-Stack-Duplikate gedacht (z. B. das in
`fix_1435_e5_alert_mapping_unify.md` unter „Known Limitations" benannte
`AlertableMetrics`-Vokabular selbst, oder der in Issue #1000 dokumentierte
Fall) — dort jeweils neu zu entscheiden, ob dieses Muster passt.

**Zwei physische generierte Dateien statt einer.** Go-Embed-Teilbaum-Regel und
Vite-`server.fs.allow`-Sicherheitsgrenze verhindern einen einzelnen Dateiort für
beide Toolchains. Mechanisch so dicht wie eine einzelne Datei (beide werden aus
einem Lauf eines Skripts erzeugt und gegeneinander sowie gegen die Quelle
geprüft), aber zwei Dateien auf der Platte.

**Ein defektes Embed führt zum sofortigen Programmabsturz beim Go-Start**
(fail fast), nicht zu einer schleichend leeren Map, die alle Alarmregeln
stillschweigend abschaltet — bewusste Entscheidung gegen ein stilles
Fehlermodell an dieser Stelle.
