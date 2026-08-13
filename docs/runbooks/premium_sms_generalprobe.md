# Runbook — Generalprobe Premium-SMS am Garmin inReach (Issue #1533)

Vier der sechs offenen Punkte aus #1533 brauchen den `premium_sms`-Kanal
**scharf geschaltet** — jede Aktivierung kostet echtes Geld. Aktivierung ist
laut CLAUDE.md eine **PO-Entscheidung**, keine Session schaltet sie
eigenmächtig. Dieses Runbook bündelt die vier Punkte in möglichst wenige
Fenster.

Spec: `docs/specs/modules/feat_1533_s4_generalprobe.md` (AC-6 bis AC-9).
Zwei Punkte (Zeichenbudget, Zeichensatz) sind **kostenlos** vorab über den
Vorab-Check automatisiert geprüft (AC-1 bis AC-5) — vor jeder Aktivierung
ausführen.

## Schritt 0 — Kostenloser Vorab-Check (vor jeder Aktivierung)

```bash
uv run python3 scripts/premium_sms_preflight_check.py \
  --trip-id <reale-KHW-Trip-ID> --user-id <PO-User-ID>
```

Prüft `report.sms_text` für `morning` UND `evening` gegen die reale
Trip-Konfiguration: Länge ≤ 160 Zeichen, GSM-7-rein. Exit-Code ≠ 0 bei
Verstoß — dann NICHT aktivieren, erst den Befund klären.

⚠️ „Sauber" heißt nur: Länge und Zeichensatz sind in Ordnung — NICHT, dass
der Text inhaltlich vollständig ist. Wirkt die Ausgabe ungewöhnlich kurz
oder besteht sie überwiegend aus Platzhaltern (`-`), erst die normale
Vorschau in der Oberfläche ansehen, bevor aktiviert wird.

## Schritt 1 — Aktivierung (PO)

Der PO schaltet den `premium_sms`-Kanal für den realen KHW-Trip ein
(Zeitfenster wählen, in dem sowohl ein regulärer Scheduler-Lauf ansteht als
auch das Gerät griffbereit ist, um die Ablesung nicht zu verzögern).

## Schritt 2 — Scheduler-getriebener Versand (AC-6)

- **Nicht** manuell auslösen — auf den regulären `trip_reports_hourly`-Lauf
  warten.
- Nach dem erwarteten Lauf: `GET /api/scheduler/status` prüfen, `last_run`
  für `trip_reports_hourly` muss einen erfolgreichen, aktuellen Lauf zeigen.
- **Parallel:** PO liest am Gerät ab, ob die Nachricht ankam. Status-Endpoint
  allein beweist nur „Job lief", nicht „SMS kam an" — beide Messpunkte
  zusammen sind der Nachweis.
- Anwendungslog-Zeitstempel notieren (`seven_io_base.py:185-187`,
  `journalctl` auf dem Server) — Grundlage für Schritt 3.

## Schritt 3 — Latenz (AC-7)

- PO notiert die am Gerät abgelesene Empfangszeit.
- Vergleich mit dem in Schritt 2 notierten Log-Zeitstempel — grober
  Soll-Ist-Vergleich, keine Millisekunden-Genauigkeit erwartet.
- Ergebnis hier im Runbook (Kopie dieser Datei mit Datum) oder im Issue
  #1533 festhalten.

## Schritt 4 — Alarm-Pfad am Gerät (AC-8)

PO wählt vor dem Fenster eine Option:

- **(i) Debug-Trigger:** falls vorab gebaut (analog
  `/api/debug/trigger-radar-alert`, s. Spec Known Limitations) — auslösen,
  Empfang am Gerät prüfen.
- **(ii) Alarmschwelle manuell senken:** am echten KHW-Trip eine Schwelle
  testweise so weit senken, dass ein echter (kleiner) Alarm natürlich
  auslöst. Schwelle nach dem Test **zurücksetzen** — nicht vergessen, sonst
  bleibt der Trip mit einer zu empfindlichen Schwelle live.

## Schritt 5 — Lesbarkeit (AC-9)

PO beschreibt oder fotografiert die Darstellung auf dem Display: Zeilenumbrüche, Reihenfolge, Vollständigkeit.

## Schritt 6 — Deaktivierung

Kanal nach Abschluss aller vier Punkte wieder abschalten (wie am
2026-08-11 bereits einmal praktiziert) — keine dauerhafte Scharfschaltung
ohne expliziten PO-Wunsch für die Tour selbst.

## Ergebnis-Protokoll

| Punkt | Ergebnis | Datum | Notiz |
|---|---|---|---|
| Scheduler-Versand (AC-6) | offen | | |
| Latenz (AC-7) | offen | | |
| Alarm-Pfad (AC-8) | offen | | Option gewählt: |
| Lesbarkeit (AC-9) | offen | | |
