---
entity_id: fix_1697_radar_waechter_in_ci
type: bugfix
created: 2026-08-16
updated: 2026-08-16
status: draft
workflow: fix-1697-radar-waechter-in-ci
---

# Radar-Wächter-Tests zurück in die CI-Ampel (#1697)

## Approval

- [ ] Approved

## Purpose

Zwei Wächter-Testdateien für die Radar-Alarm-Kette (#818, #822) sind aktuell in
`.github/ci_tdd_excludes.txt` von der CI-Kollektion ausgeschlossen und laufen dadurch bei
keinem `test`-Check mit. Der eigentliche Bug aus #1697 ("Alarm-Pfad fragt den Server-Tag
statt den Ortstag ab") ist bereits am 2026-08-11 behoben — offen ist nur noch der im Issue
geforderte Nachweis, dass beide Regressionswächter dauerhaft in der CI-Ampel laufen, ohne
dabei reale E-Mails an Produktiv-Empfänger zu versenden.

## Source

- **File:** `tests/tdd/test_issue_818_radar_briefing_integration.py`
- **Identifier:** `def test_ac7_mandantentrennung_isolated`
- **File:** `.github/ci_tdd_excludes.txt`
- **Identifier:** Zeilen 77-78 (Ausschlusseinträge für beide Dateien)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_alert.py::TripAlertService` | module | Stellt die `mail_sink`-DI-Naht bereit, die den Egress-Fix trägt |
| `src/services/notification_service.py` | module | Baut ohne `mail_sink` einen echten `EmailOutput(...).send(...)` auf realer SMTP-Konfiguration |
| `.github/workflows/*` (`test`-Check) | ci | Kollektiert `tests/tdd/` abzüglich der Excludes-Liste — Zielort dieses Fixes |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `tests/tdd/test_issue_818_radar_briefing_integration.py` | MODIFY | `mail_sink`-Parameter in `test_ac7_mandantentrennung_isolated()` (Zeile ~585-589) ergänzen, exakt nach dem Muster von `test_ac6_radar_throttle_via_alert_state_cooldown()` (Zeile 500-553): ein `lambda subject, body: captured.append((subject, body))` als Callable, kein `unittest.mock` |
| `.github/ci_tdd_excludes.txt` | MODIFY | Beide Einträge (Zeilen 77-78) entfernen |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | keine Code-Änderung | wird durch das Entfernen aus der Excludes-Liste automatisch mit-kollektiert; `test_ac8_mandantentrennung_isolated()` (799-868) setzt bereits `send_email=False, send_telegram=False, alert_on_changes=False` — kein Egress-Risiko |

### Estimated Changes
- Files: 2 (Code + Excludes-Liste), 1 Datei ohne Änderung
- LoC: +3/-2

## Implementation Details

`test_ac7_mandantentrennung_isolated()` konstruiert aktuell `TripAlertService(...)` ohne den
`mail_sink`-Parameter, den `trip_alert.py:140` bereits vorsieht ("Optional
callable(subject, body) — captures mail calls in tests"). Da der zugrundeliegende Trip
`report_config.send_email=True` und `alert_channels=None` hat, liefert
`_effective_alert_channels()` (`trip_alert.py:1553-1591`) den Legacy-Default `{"email"}`, und
`notification_service.py:1432-1440` baut ohne Sink einen echten `EmailOutput(...).send(...)`
auf — Egress-Risiko der Klasse #1477.

Fix: `mail_sink=lambda subject, body: captured.append((subject, body))` an beiden
`TripAlertService(...)`-Konstruktionsstellen in dieser Testfunktion ergänzen (Zeile ~585-589),
identisch zur bereits korrekten Bauform in `test_ac6_...`. Danach die zwei Zeilen aus
`.github/ci_tdd_excludes.txt` streichen. Keine Produktivcode-Änderung nötig.

`test_issue_822_radar_nowcast_segment.py` benötigt keine Code-Änderung — die Streichung aus
der Excludes-Liste genügt, da das Datei-Äquivalent bereits ohne aktive Kanäle testet.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1 (Egress-Guard, Erweiterung von `test_ac7_mandantentrennung_isolated`): GIVEN eine `TripAlertService`-Instanz mit gesetztem `mail_sink`-Callable und einem Trip mit `send_email=True` WHEN `check_radar_alerts()` einen Alert für `uid_a` auslöst THEN landet der Versand ausschließlich im `captured`-Callback (Egress-Nachweis über den DI-Seam), es wird kein `smtplib`/`EmailOutput`-Sende-Call gegen echte SMTP-Konfiguration ausgelöst.
- [ ] Test 2 (Collector-Nachweis, `--collect-only`): GIVEN beide Zeilen für #818 und #822 sind aus `ci_tdd_excludes.txt` entfernt WHEN `uv run pytest tests/tdd/test_issue_818_radar_briefing_integration.py tests/tdd/test_issue_822_radar_nowcast_segment.py --collect-only -q` läuft THEN meldet der Collector eine Testanzahl > 0 für beide Dateien (keine stille Marker-Deselektion, da beide Dateien modulweit markerlos sind).

## Acceptance Criteria

- **AC-1:** Given `test_ac7_mandantentrennung_isolated()` läuft mit gesetztem `mail_sink`-Callable (Muster von `test_ac6_...` übernommen) / When `check_radar_alerts()` für `uid_a` einen Radar-Alert auslöst / Then wird der Mailversand ausschließlich über den DI-Callback abgefangen — es entsteht kein realer `EmailOutput(...).send(...)`-Aufruf gegen die produktive SMTP-Konfiguration der Host-`.env` (Egress-Nachweis, nicht bloß „Test besteht grün").
- **AC-2:** Given `.github/ci_tdd_excludes.txt` enthält nach dem Fix keine Zeile mehr für `test_issue_818_radar_briefing_integration.py` und `test_issue_822_radar_nowcast_segment.py` / When `uv run pytest tests/tdd/test_issue_818_radar_briefing_integration.py tests/tdd/test_issue_822_radar_nowcast_segment.py --collect-only -q` ausgeführt wird / Then zeigt die Ausgabe für beide Dateien zusammen eine Testanzahl größer 0 — kein modulweiter Marker deselektiert die Dateien still aus der CI-Kollektion.
- **AC-3:** Given beide Dateien sind aus der Excludes-Liste entfernt und der Egress-Fix in AC-1 ist umgesetzt / When `uv run pytest tests/tdd/test_issue_818_radar_briefing_integration.py tests/tdd/test_issue_822_radar_nowcast_segment.py -v` lokal läuft / Then bestehen alle 15 Tests beider Dateien grün (bereits vorab gemessen: 15/15), sodass die Dateien im nächsten CI-`test`-Check ohne Exclude-Eintrag mitlaufen.

## Known Limitations

- Bei einem lokalen Vorab-Lauf mit `--allow-hosts=127.0.0.1,::1` blieb `test_ac7_mandantentrennung_isolated` trotz geblockter Netzwerkverbindung grün — die Socket-Connect-Exception wird offenbar irgendwo im Versandpfad verschluckt statt sichtbar zu scheitern. Das ist ein separater, kleinerer Fund und kein Teil dieses Fixes: Der hier umgesetzte Fix behebt die Egress-**Ursache** (kein realer Versandaufbau mehr durch die `mail_sink`-Naht), nicht die verschluckte Exception selbst. Der Fund gehört in das rollierende Sammel-Issue #1199.
- Diese Scheibe schließt #1697 vollständig ab: Der Kern-Bug (Server-Tag statt Ortstag), der Briefing-Pfad und die Muster-A-Restliste des Zeitzonen-Wächters sind bereits vor diesem Workflow erledigt (siehe `docs/context/fix-1697-radar-waechter-in-ci.md`). Mit Umsetzung dieser Spec kann Issue #1697 geschlossen werden. Alle weiteren, nicht hier abgedeckten Zeitzonen-/Radar-Themen gehören zu #1727 S5e.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur-Änderung (DI-Naht-Nutzung + CI-Excludes-Pflege), keine Entscheidungsfläche im Sinne der ADR-Pflicht (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie bleiben unverändert).

## Changelog

- 2026-08-16: Initial spec created
