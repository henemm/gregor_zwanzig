# ADR-0036: Nebenlaeufigkeitsschutz ueber Inhalts-Fingerabdruck statt Versionsfeld

- **Status:** Akzeptiert
- **Datum:** 2026-07-27
- **Bezug:** GitHub-Issue #1395 (Scheiben S1/S2), Spec
  `docs/specs/modules/issue_1395_s2_etag_ifmatch.md`

## Kontext

`UpdateTripHandler` und die uebrigen Trip-Schreibpfade machen ein reines
Read-Modify-Write ohne jeden Versionsbegriff. Treffen zwei Schreibvorgaenge
zeitlich zusammen, gewinnt der, der ZULETZT ANKOMMT — nicht der, der zuletzt
abgeschickt wurde. Bei den vorangegangenen Kaskaden-Bugs (#1389/#1390/#1393)
wurden acht Fehler in sechs Pruefrunden gefunden, alle derselben Klasse: ein
Datenstand wird im Client festgehalten und spaeter verwendet, obwohl er
inzwischen veraltet ist. Jede Runde schloss eine Luecke in einer clientseitigen
Eigenkonstruktion, die es nur gibt, weil der Server keine Nebenlaeufigkeit
kennt.

Ein serverseitiger Schutz braucht einen Stempel, der zuverlaessig anzeigt: „das
ist noch derselbe Stand, den ich zuletzt gelesen habe". Zwei Rahmenbedingungen
schraenken die Wahl ein:

1. **Dieselbe Datei wird von zwei Sprachen geschrieben.** `briefings/<id>.json`
   wird sowohl vom Go-API (`internal/store`) als auch vom Python-Kern
   geschrieben (`src/app/loader.py:1581-1648` `save_trip`) — Telegram-/
   SMS-Kommandos (`src/app/trip_command_processor.py:852,928,1046,1069,1128,1142`),
   `skip_next`-Verbrauch (`src/app/trip_report_scheduler.py:517`),
   Migrationsskripte.
2. **Der Python-Kern bewahrt unbekannte Felder ausdruecklich**
   (`_deep_merge_preserve_unknown`, `loader.py:124-137`). Ein Feld, das nur Go
   pflegt, wird von Python beim Schreiben unveraendert durchgereicht — es
   erkennt die eigene Aenderung also nicht als Anlass, den Stempel
   fortzuschreiben.

## Entscheidung

Der Nebenlaeufigkeitsschutz beruht auf einem **sha256-Fingerabdruck ueber die
tatsaechlichen Bytes der Datei auf Platte**, nicht auf einem im Dokument
mitgefuehrten Zaehler- oder Zeitstempelfeld:

- `Store.BriefingFingerprint(id)` (S1, `internal/store/briefing_fingerprint.go`)
  liest `briefings/<id>.json` und liefert den sha256-Hex-Wert der Rohbytes.
  Fehlt die Datei, ist das ein gueltiger Zustand („noch kein Stand") und kein
  Fehler.
- Der Fingerabdruck wird per HTTP-Header transportiert: `ETag` in
  GET-Antworten, `If-Match` in PUT-Anfragen (S2). Er lebt AUSSERHALB des
  Dokuments, wird also nie mit ins JSON persistiert und kann daher keinen
  Namens- oder Schema-Konflikt mit bestehenden Feldern ausloesen.
- Da er aus den tatsaechlichen Bytes berechnet wird, aendert sich der
  Fingerabdruck bei JEDER Aenderung der Datei — unabhaengig davon, ob Go oder
  Python geschrieben hat. Der Python-Schreibpfad muss dafuer NICHT angepasst
  werden.

## Verworfene Alternativen

- **`version`-Zaehlfeld im Dokument.** Verworfen: braucht eine zweite,
  spiegelbildliche Umsetzung in `loader.save_trip` — ein weiterer
  Cross-Language-Wertekontrakt der Art, die bereits #802/#1000/#1250
  eingebrockt hat. Zusaetzlich eine Schema-Aenderung in Go, TypeScript und
  `openapi.yaml`, und eine Migration fuer 19 Bestandstouren.
- **`updated_at`-Zeitstempelfeld im Dokument.** Verworfen: alle Nachteile von
  „version" PLUS eine Namenskollision mit den bereits bestehenden
  `updated_at`-Feldern in `display_config`/`report_config`/`weather_config`
  (`loader.py:1259,1444,1459,1551`), die Python bei jedem Speichern ohnehin auf
  „jetzt" setzt — die schlechteste der drei Varianten.
- **Ein Rumpf-Feld statt eines HTTP-Headers.** Verworfen: scheidet strukturell
  aus, weil bei `PUT /api/trips/{id}/weather-config` der Rumpf DIE
  Konfiguration IST. Ein `"version"`-Feld darin wuerde ununterscheidbar in
  `display_config` persistiert und selbst zu einem unbekannten, aber
  gespeicherten Konfigurationswert.

## Konsequenzen

- **Positiv:** Keine Schema-Aenderung, keine Migration, keine Aenderung am
  Python-Kern. Jede Bestandsdatei hat automatisch ab dem ersten `GET` einen
  gueltigen Fingerabdruck. Der Schutz gilt gleichermassen fuer Go- und
  Python-Schreibvorgaenge, ohne dass Python je vom Vertrag wissen muss.
- **Negativ / Preis:** Der Fingerabdruck ist nicht menschenlesbar (kein
  fortlaufender Zaehler, keine Uhrzeit) und aendert sich bei JEDER
  Byte-Aenderung — auch bei reiner In-Memory-Heilung, die beim naechsten
  Speichern zurueckgeschrieben wird (gemessener S1-Befund: ein folgenloses
  Speichern aendert die Datei trotzdem, weil `LoadTrip` beim Lesen heilt, ohne
  zurueckzuschreiben). Ein Client, der einen `ETag` aus einer GET-Antwort
  festhaelt, MUSS nach dem eigenen erfolgreichen PUT den in der PUT-Antwort
  mitgelieferten NEUEN `ETag` uebernehmen — der alte aus dem GET ist ab dem
  ersten Speichern potenziell veraltet.
- **Folgepflichten:** Jeder neue Schreibpfad auf `briefings/<id>.json` (Go oder
  Python) muss sich bewusst sein, dass sein Schreibvorgang den Fingerabdruck
  fortschreibt und damit bestehende `If-Match`-Werte anderer Clients
  entwertet — das ist der gewuenschte Effekt, keine Nebenwirkung. Kuenftige
  Konsumenten des Fingerabdrucks (z. B. das Frontend in S3, der Ortsvergleich
  in S6) uebernehmen denselben Header-Vertrag (`ETag`/`If-Match`), statt einen
  eigenen Stempel-Mechanismus zu erfinden.
