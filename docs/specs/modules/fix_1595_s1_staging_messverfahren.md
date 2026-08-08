---
entity_id: fix_1595_s1_staging_messverfahren
type: module
created: 2026-08-08
updated: 2026-08-08
status: draft
version: "1.0"
tags: [infrastructure, data-root, staging, measurement]
---

<!-- Issue #1595 — Scheibe 1 von 5: Staging-Messverfahren -->

# Fix 1595 S1 — Staging-Messverfahren für die Datenwurzel

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-08-08, Beleg als Kommentar in [#1595](https://github.com/henemm/gregor_zwanzig/issues/1595)

## Purpose

Vor dem Umzug der Produktivdaten belastbar feststellen, **welche Stellen tatsächlich auf die Datenwurzel zugreifen** — durch Messung am laufenden System, nicht durch Textsuche.

Die Inventur aus #1595 (14 Fundstellen) ist der Startpunkt, nicht der Nachweis. Sie stammt aus `grep`, und `grep` hat in diesem Vorgang bereits zweimal getrogen: ADR-0028 nannte eine blockierende Stelle, es waren vier; das erste Suchmuster dieser Messung verfehlte bekannte Treffer, weil es `Union[str, Path]` nicht erfasste. Ein Umzug von 79 MB Produktivdaten auf Grundlage einer Textsuche wäre fahrlässig.

Diese Scheibe ändert **keinen Produktcode** und berührt **keine Produktivdaten**.

## Source

- Issue [#1595](https://github.com/henemm/gregor_zwanzig/issues/1595)
- Kontext & Analyse: `docs/context/fix-1595-datenwurzel-umzug.md`
- Vorgeschichte: ADR-0028 (verwarf `GZ_DATA_DIR` auf falscher Tatsachengrundlage), ADR-0031

## Estimated Scope

- **Kein Produktcode.** Ein Umschalt-/Rückbau-Skript, ein Befund-Dokument.
- Betroffen: Staging-Umgebung (`gregor_zwanzig_staging`, vier Dienste)
- Geschätzt: +80 / −0 LoC (Skript), plus Befund-Dokument
- Risiko: niedrig für Produktion, **Staging fällt zeitweise absichtlich aus**

## Dependencies

- Staging muss laufen und deploybar sein
- Sicherung des Staging-Datenbaums vor Beginn (Verfahren wie bei Prod: als `root`, Einträge gezählt)
- Produktivsicherung liegt vor: `.backups/prod-data-pre-1595-20260808.tar.gz` (280/280 verifiziert)

## Implementation Details

### Stufe A — sanft (24 Stunden)

1. Staging-Datenbaum sichern, Vollständigkeit durch Zählvergleich belegen.
2. Daten nach `/var/lib/gregor-staging` verschieben; Besitzer `claude-gregor`, Modus `0750`.
3. `GZ_DATA_DIR=/var/lib/gregor-staging` für **alle vier** Staging-Dienste setzen (auch für die beiden, die heute keine Variable haben).
4. Alten Ordner `gregor_zwanzig_staging/data` nach `data.pre-1595` umbenennen.
5. 24 Stunden laufen lassen.

**Detektor:** Entsteht am alten Ort ein neuer `data/`-Ordner, benutzt jemand den relativen Pfad. Sein Inhalt benennt den Verursacher.

### Stufe B — scharf (kurz)

Am alten Ort eine **Datei** namens `data` anlegen (kein Verzeichnis). Jeder Zugriff auf `data/…` scheitert dann mit `ENOTDIR` — laut und im Log — statt still ins Leere zu laufen.

Stufe A findet nur Schreiber. Stufe B findet auch **Leser**, die sonst kommentarlos leere Ergebnisse liefern (Muster „leer ≠ unbekannt", #1492 — genau so fiel am 07.08. das Tier still von `premium` auf `free`).

### Auslöse-Liste (ohne sie ist die Messung wertlos)

Ein Codepfad, der im Messzeitraum nicht ausgeführt wird, kann sich nicht melden. Diese Vorgänge werden auf Staging **gezielt ausgelöst**, abgeleitet aus den Fundstellen der Inventur:

| Vorgang | deckt ab |
|---|---|
| Anmeldung + Profilabruf | `loader.py` Nutzerauflösung, Go-Store |
| Trip-Briefing versenden | `dispatch_orchestrator`, `email.py` Allowlist |
| Vergleichs-Briefing versenden | `scheduler_dispatch_service` (alle vier Stellen), `load_compare_presets` |
| Eingehende Mail an Staging | `inbound_email_reader.py:220` |
| Eingehende Telegram-Nachricht | `inbound_telegram_reader.py:378` |
| Kennwort-Vergessen anstoßen | `lookup_user_by_email` |
| Nächtliche Cronjobs abwarten (04:15, 04:30) | Validator-Setup, Staging-Sweep |
| Deploy auf Staging auslösen | `migrate_1250_briefings.py --root data/users` |
| Wetterabruf erzwingen | `calllog.go` → `data/diagnostics` |

Zwei davon (`inbound_email_reader`, `inbound_telegram_reader`) laufen **nur** bei eingehender Post — sie wären in einer reinen Wartezeit nie aufgefallen.

## Expected Behavior

Am Ende liegt eine Liste vor: jede gemessene Zugriffsstelle, mit Datei und Zeile, und der Vermerk, ob sie in der Inventur stand. Diese Liste — nicht die Inventur — bestimmt den Umfang von S2.

Staging läuft danach wieder normal.

## Acceptance Criteria

**AC-1:** Given Staging läuft mit der Datenwurzel unter `/var/lib/gregor-staging` und der alte Ordner ist umbenannt, When 24 Stunden vergangen sind und in dieser Zeit die Cronjobs um 04:15 und 04:30 sowie ein Briefing-Lauf stattgefunden haben, Then ist dokumentiert, ob am alten Ort etwas neu entstanden ist — und falls ja, welche Dateien es sind und welche Codestelle sie erzeugt hat.

**AC-2:** Given am alten Ort liegt eine Datei statt eines Verzeichnisses, When alle Vorgänge der Auslöse-Liste ausgeführt werden, Then ist jeder dadurch entstandene Fehler mit Datei und Zeile erfasst und einer Codestelle zugeordnet.

**AC-3:** Given der Befund aus AC-1 und AC-2, When er gegen die Inventur aus #1595 gehalten wird, Then ist für jede gemessene Zugriffsstelle vermerkt, ob die Inventur sie kannte, und jede zusätzlich gefundene Stelle ist als Kommentar in #1595 nachgetragen.

**AC-4:** Given die Messung ist abgeschlossen, When Staging zurückgestellt wird, Then arbeitet es wieder mit seinem ursprünglichen Datenbestand, eine Anmeldung gelingt und ein Briefing wird nachweislich zugestellt.

**AC-5:** Given die gesamte Messung von Anfang bis Ende, When sie durchgeführt wurde, Then ist der **Produktiv**-Datenbaum nachweislich unverändert — belegt durch Vergleich von Eintragszahl und Prüfsummen der Nutzerprofile vor und nach der Messung.

**AC-6:** Given ein Abbruch an beliebiger Stelle der Messung, When der Rückbau ausgeführt wird, Then ist Staging in höchstens zwei Minuten wieder im Ausgangszustand, ohne Rückgriff auf die Sicherung.

## Known Limitations

- **Die Messung sieht nur, was läuft.** Selten genutzte Pfade außerhalb der Auslöse-Liste bleiben unentdeckt. Die Liste ist aus den bekannten Fundstellen abgeleitet — für eine Stelle, die weder in der Inventur steht noch von einem gelisteten Vorgang berührt wird, gibt es in dieser Scheibe keinen Nachweis. Das ist die verbleibende Unschärfe; sie wird durch den befristeten Symlink in S4 abgefedert, nicht durch S1.
- Staging hat einen anderen Datenbestand als Produktion (Testnutzer, keine echten Alarm-Historien). Ein Pfad, der nur bei bestimmten Produktivdaten durchlaufen wird, kann hier fehlen.
- Stufe B macht Staging **absichtlich** kurzzeitig unbenutzbar.

## Architektur-Entscheidung (ADR)

Diese Scheibe trifft keine Architektur-Entscheidung. Das ADR zum Zielort (`/var/lib/gregor`, Steuerung über `GZ_DATA_DIR` aus zentraler env-Datei) entsteht in S3; ADR-0028 wird dort als abgelöst markiert, ADR-0031 um die nie getroffene Ortsentscheidung ergänzt.

## Changelog

| Datum | Version | Änderung |
|---|---|---|
| 2026-08-08 | 1.0 | Erstfassung (Scheibe 1 von 5 zu #1595) |
