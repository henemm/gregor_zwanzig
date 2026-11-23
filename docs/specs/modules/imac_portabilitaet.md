---
entity_id: imac_portabilitaet
type: bugfix
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
workflow: fix-3294-imac-portabel
tags: [portabilitaet, go, hooks, macos]
---

# Gregor portabel für den iMac (Issue #3294)

## Approval

- [ ] Approved

## Purpose

Gregor-Sitzungen sollen auf dem iMac (macOS, ggf. Go 1.27) ohne Sonderhandgriffe laufen (Teil von henemm-infra#487). Drei Stellen setzen bisher die Server-Umgebung voraus: ein Go-Versionsunterschied bei der Fehlererkennung, eine nur unter Linux vorhandene Loopback-Adresse im Test und ein Start-Hook mit Server-Pfad.

## Source

- **File:** `internal/handler/trip.go`
- **Identifier:** `writeTripDecodeError`
- **Weitere Stellen:** `internal/resolver/link_abruf_haertung_ergaenzung_test.go` (`TestLinkAbruf_EgressWaechterWirdJeAbrufGefragt`), `.claude/hooks/mq_check_messages.sh` (neu), `.claude/settings.json` (SessionStart-Hook)

> **Schicht-Hinweis:** Go-API (`internal/handler`, `internal/resolver`) und Claude-Werkzeugschicht (`.claude/`). Kein Python-Core, kein Frontend.
> **Trip/Ortsvergleich-Teilung:** nicht betroffen (kein UI-Baustein). **Mandantentrennung:** nicht betroffen (keine Nutzerdaten bewegt; 422/400-Verhalten gilt unabhängig vom Nutzer). **Kanäle:** nicht betroffen (kein Briefing-/Alarm-Inhalt).

## Scope

Hinweis zur Herkunft: Issue #3294 ist ein technischer Befundbericht aus der iMac-Einrichtung (henemm-infra#487), keine Produktvorgabe des PO. Der Vorschlag `toolchain go1.25.x` war ein Lösungsvorschlag dieser Einrichtung; die Abweichung davon ist eine dokumentierte Tech-Lead-Entscheidung (Kommentar in #3294), das Ziel des Issues (Test grün unabhängig von der Go-Version, kein Sonderhandgriff) wird vollständig erfüllt.

Im Scope: die drei Befunde aus #3294 (JSON-Feldpfad Go-versionsunabhängig, Loopback-Test plattformneutral, Start-Hook ohne festen Server-Pfad). Nicht im Scope: Pull-Deploy (#3289), `toolchain`-Zeile in `go.mod` (wirkungslos, siehe Implementation Details), der Last-Flake im Google-Link-Test.

## Estimated Scope

- **LoC:** ca. +150 / -10 (davon etwa zwei Drittel Tests)
- **Files:** 6 (4 Produktiv-/Konfig-Dateien, 2 neue Testdateien)
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/trip.go` | MODIFY | Feldpfad ohne numerische Segmente vergleichen (Hilfsfunktion) |
| `internal/handler/trip_decode_feldpfad_test.go` | CREATE | Unit-Test der versionsunabhängigen Feldpfad-Erkennung |
| `internal/resolver/link_abruf_haertung_ergaenzung_test.go` | MODIFY | Loopback-Adresse 127.0.0.2, sonst `[::1]`, sonst Skip mit Begründung |
| `.claude/hooks/mq_check_messages.sh` | CREATE | Portabler Aufruf der Nachrichtenprüfung, blockiert nie |
| `.claude/settings.json` | MODIFY | SessionStart-Hook ruft das Repo-Skript statt des Server-Pfads |
| `tests/test_mq_check_messages_hook.py` | CREATE | Führt Skript und Hook-Kommando real aus |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `encoding/json` (Go) | stdlib | `UnmarshalTypeError.Field`, dessen Format sich zwischen Go 1.25 und 1.27 unterscheidet |
| `internal/egress/guard.go` | module | Wächter-Freigabe kennt nur `localhost`/`127.0.0.1`; bestimmt, welche Loopback-Adresse der Test braucht |
| `/home/hem/claude-mq/check-messages.sh` | Server-Skript | Nachrichtenprüfung, leitet die Instanz aus `$PWD` ab, hält das Secret nur auf dem Server |
| `ssh` (Alias `henemm`) | Werkzeug | Aufruf des Server-Skripts vom iMac aus |

## Implementation Details

**1. Go 1.27: 422 statt 400.** Go 1.27 setzt in `UnmarshalTypeError.Field` den Array-Index mit (`stages.1.grundtempo_kmh`), Go 1.25 nicht (`stages.grundtempo_kmh`). Der exakte Stringvergleich in `writeTripDecodeError` greift unter 1.27 nicht, die API antwortet 400 statt 422 (betrifft `TestStageTempo3197_Ungueltig422` für `"3"` und `true`). Fix: kleine Hilfsfunktion, die aus dem Feldpfad alle rein numerischen Segmente entfernt und das Ergebnis mit `stages.grundtempo_kmh` vergleicht. Andere Felder (z. B. `stages.1.name`) bleiben 400.

**Bewusste Abweichung vom Issue-Text:** Das Issue schlug eine `toolchain`-Zeile in `go.mod` vor. Laut Go-Regeln ist sie nur eine Mindestversion; eine lokal neuere Go-Version (1.27) wird trotzdem benutzt, die Zeile würde also nichts festnageln. Festnageln ginge nur per `GOTOOLCHAIN=go1.25.0` je Rechner, also genau der Sonderhandgriff, der wegfallen soll. Entscheidung: Ursache beheben, Code versionsunabhängig machen, `go.mod` unverändert. CI und Server bleiben auf 1.25.

**2. Resolver-Test unter macOS.** `lo0` kennt nur 127.0.0.1 und `::1`. Der Test braucht eine Loopback-Adresse, die der Wächter nicht freigibt; 127.0.0.1 scheidet aus, weil der Wächter es freigibt. Ablauf: zuerst auf `127.0.0.2:0` lauschen, sonst auf `[::1]:0`; nur wenn beides fehlt, `t.Skip` mit Begründung. Der verwendete Host (statt fest `127.0.0.2`) geht an `resolver.ErlaubeTestHosts` und in die Link-URL.

**3. SessionStart-Hook.** Neues `.claude/hooks/mq_check_messages.sh`:
- Existiert das Server-Skript (Pfad per `GZ_MQ_CHECK_SCRIPT`, Standard `/home/hem/claude-mq/check-messages.sh`), wird es direkt aufgerufen und seine Ausgabe durchgereicht.
- Sonst Aufruf per `ssh -o ConnectTimeout=3 -o BatchMode=yes -o ServerAliveInterval=2 -o ServerAliveCountMax=2 "${GZ_MQ_SSH_HOST:-henemm}" 'cd ~/gregor_zwanzig && bash ~/claude-mq/check-messages.sh'` (die Instanz wird auf dem Server aus `$PWD` abgeleitet).
- Server nicht erreichbar oder jeder Fehler: keine Ausgabe, `exit 0`. Der Sitzungsstart blockiert nie.
- Kein Secret auf dem iMac (henemm-security#219): die Abfrage läuft auf dem Server.
- In `settings.json` lautet der Eintrag `bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/mq_check_messages.sh"`.

## Expected Behavior

- **Input:** (1) Trip-Anfrage mit falschem Typ für `stages[].grundtempo_kmh`; (2) Go-Testlauf auf Rechner mit/ohne 127.0.0.2; (3) Sitzungsstart auf Server oder iMac.
- **Output:** (1) 422 `invalid_params` unter Go 1.25 und 1.27; (2) Test grün oder begründet übersprungen; (3) offene Nachrichten erscheinen, sonst keine Ausgabe.
- **Side effects:** keine; `go.mod` bleibt unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Go-Unit-Test (`internal/handler`): GIVEN ein `UnmarshalTypeError` mit Feld `stages.grundtempo_kmh` bzw. `stages.1.grundtempo_kmh` WHEN `writeTripDecodeError` läuft THEN 422; mit `stages.1.name` THEN 400. RED vor dem Fix für die Variante mit Index.
- [ ] Bestehender Test `TestStageTempo3197_Ungueltig422` bleibt grün, auch mit `GOTOOLCHAIN=go1.27.0`.
- [ ] Resolver-Test: läuft grün mit der neuen Adressauswahl; Skip nur, wenn weder 127.0.0.2 noch `[::1]` verfügbar sind.
- [ ] `tests/test_mq_check_messages_hook.py`: Fake-Skript per `GZ_MQ_CHECK_SCRIPT` -> dessen Ausgabe erscheint.
- [ ] `tests/test_mq_check_messages_hook.py`: nicht vorhandener Skriptpfad und `GZ_MQ_SSH_HOST=gz-nicht-vorhanden.invalid` -> Exit 0, leere Ausgabe, unter 10 s.
- [ ] `tests/test_mq_check_messages_hook.py`: das SessionStart-Kommando aus `settings.json` wird real ausgeführt (`CLAUDE_PROJECT_DIR` = Worktree) und nutzt das Repo-Skript.

## Acceptance Criteria

- **AC-1:** Given eine Trip-Anfrage, bei der `grundtempo_kmh` einer Etappe als Text `"3"` oder als `true` gesendet wird / When die API sie unter Go 1.25 oder Go 1.27 verarbeitet / Then antwortet sie mit 422 `invalid_params`.
  - Test: Echte Anfrage an den Trip-Endpunkt mit `"3"` und `true`, Läufe unter beiden Go-Versionen.

- **AC-2:** Given eine Trip-Anfrage mit einem anderen Dekodierfehler (z. B. falscher Typ bei `stages[1].name`) / When die API sie verarbeitet / Then antwortet sie weiterhin mit 400 `bad_request`.
  - Test: Unit-Test der Feldpfad-Erkennung mit `stages.1.name` und Anfrage an den Endpunkt.

- **AC-3:** Given ein Rechner ohne Loopback-Adresse 127.0.0.2 (macOS) / When der Resolver-Test zum Egress-Wächter läuft / Then weicht er auf `[::1]` aus und prüft weiterhin, dass der Wächter einen nicht freigegebenen Host je Abruf blockiert.
  - Test: Testlauf auf Rechner mit 127.0.0.2 (Server) grün; Auswahllogik nimmt `[::1]`, wenn 127.0.0.2 fehlt; Skip mit Begründung nur, wenn beides fehlt.

- **AC-4:** Given auf dem Rechner liegt das Server-Skript zur Nachrichtenprüfung (Server) / When der Sitzungsstart-Hook läuft / Then erscheinen die offenen Nachrichten unverändert in der Ausgabe.
  - Test: Hook-Skript real ausgeführt mit einem Fake-Skript über `GZ_MQ_CHECK_SCRIPT`; dessen Ausgabe erscheint.

- **AC-5:** Given der Rechner hat das Server-Skript nicht und der Server ist nicht erreichbar (iMac unterwegs) / When der Sitzungsstart-Hook läuft / Then endet er in unter 10 Sekunden mit Exit-Code 0 und ohne Ausgabe, der Start wird nie blockiert.
  - Test: Hook-Skript real ausgeführt mit nicht vorhandenem Skriptpfad und `GZ_MQ_SSH_HOST=gz-nicht-vorhanden.invalid`; Exit 0, leere Ausgabe, Laufzeit gemessen.

- **AC-6:** Given der SessionStart-Eintrag in `.claude/settings.json` / When sein Kommando mit `CLAUDE_PROJECT_DIR` auf den Projektordner ausgeführt wird / Then ruft es das Repo-Skript auf (kein fester Server-Pfad) und liefert die Ausgabe des Fake-Skripts.
  - Test: Kommando-String aus `settings.json` per Shell ausgeführt; Verhalten wie AC-4, kein reiner Dateiinhalt-Check.

## Definition of Done

- AC-1 bis AC-6 durch die genannten Tests grün belegt (Go-Handler-Test zusätzlich mit `GOTOOLCHAIN=go1.27.0`)
- alle sechs CI-Checks grün, ausgeliefert, Issue #3294 mit Ergebnis kommentiert und geschlossen

## Known Limitations

- `go.mod` bleibt ohne `toolchain`-Zeile; welche Go-Version ein Rechner nutzt, bleibt seine Sache. Der Code läuft mit 1.25 und 1.27.
- Der SSH-Weg setzt voraus, dass auf dem iMac der Alias `henemm` mit Schlüsselanmeldung eingerichtet ist; fehlt er, bleibt die Nachrichtenprüfung still aus.
- Nebenbefund (nicht im Scope): `TestGoogleLink_AC3_BestaetigterInhaberWirdVerknuepft/exakt` war einmal im Volllauf unter Last rot, einzeln unter 1.25 und 1.27 grün (Lastflake, nicht versionsbedingt).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Portabilitätskorrektur ohne Änderung einer Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Deploy). Die Abweichung vom Issue-Text (keine `toolchain`-Zeile) ist oben begründet.

## Changelog

- 2026-11-23: Initial spec created (Issue #3294)
