# Mini-Spec: Hartkodierte Datenwurzeln auf die zentrale Aufloesung umstellen

Folgearbeit zu #1595. Die Produktivdaten liegen seit 2026-08-08 unter
`/var/lib/gregor`, gesteuert ueber `GZ_DATA_DIR`. Die hier genannten Stellen
ignorieren die Variable und zeigen auf einen leeren Ordner im Repo.

## Was sich aendert

- 12 Stellen im Python-Kern: Default `"data"` → `None`, Aufloesung im
  Funktionskoerper ueber `get_data_root()`. Ein Aufruf im Default-Argument
  waere frueh gebunden und wuerde die Testfixture `_DATA_ROOT` aushebeln.
- 2 Stellen in Go auf `config.DataDir` bzw. `GZ_DATA_DIR` zurueckfuehren.
  `calllog.go` wertet heute beim Paket-Import aus, also vor jeder Config.

Dateien: `loader.py`, `scheduler_dispatch_service.py`, `dispatch_orchestrator.py`,
`email.py`, `inbound_email_reader.py`, `inbound_telegram_reader.py`,
`sender.go`, `calllog.go`.

## Was sich NICHT aendern darf

- `get_data_root()` (loader.py:1083) bleibt unberuehrt — das ist das Ziel, auf
  das die anderen zeigen sollen.
- Verhalten ohne gesetztes `GZ_DATA_DIR`: unveraendert Fallback `"data"`.
- Keine Umbenennungen, kein Refactoring, keine neuen Features.

## Manuelle Test-Schritte

1. `uv run pytest tests/unit/test_data_root_switch.py -v` gruen
2. Tests der beruehrten Module (einzeln benannt) gruen
3. `go build ./...` fehlerfrei
4. Nach dem Deploy: Anmeldung in Produktion antwortet weiterhin im
   Millisekunden-Bereich (bcrypt laeuft = Nutzerdatei wird gefunden), nicht in
   Mikrosekunden.

## Acceptance Criteria

- **AC-1:** Given `GZ_DATA_DIR` zeigt auf einen anderen Ort, When einer der umgestellten Codepfade ausgefuehrt wird, Then liest und schreibt er unter diesem Ort und nicht mehr unter dem relativen Pfad `data`.
- **AC-2:** Given `GZ_DATA_DIR` ist nicht gesetzt, When derselbe Code laeuft, Then verhaelt er sich unveraendert zum Stand vorher (Fallback `data`).
- **AC-3:** Given der Prod-Deploy ist durch, When eine Anmeldung erfolgt, Then wird die Nutzerdatei gefunden — messbar an einer Antwortzeit im Millisekundenbereich statt im Mikrosekundenbereich.
