# Context: fix-1697-radar-waechter-in-ci

## Request Summary

#1697 verlangt, dass der Ortstag-vs-Servertag-Fix für den Radar-/NowCast-Alarmpfad
in CI nachgewiesen wird. Der eigentliche Bug ist bereits behoben (Kern-Fix
2026-08-11, Briefing-Pfad via #1724, Muster-A-Restliste via #1727 S5d auf null).
Was fehlt: die beiden dafür geschriebenen Wächter laufen nicht in CI —

- `tests/tdd/test_issue_818_radar_briefing_integration.py`
- `tests/tdd/test_issue_822_radar_nowcast_segment.py`

stehen in `.github/ci_tdd_excludes.txt:77-78`. Ziel: beide Dateien aus der
Ausschlussliste holen, ohne dass CI dadurch flackert oder — schlimmer — real
Mail/Telegram/SMS versendet.

## Related Files

| File | Relevance |
|------|-----------|
| `tests/tdd/test_issue_818_radar_briefing_integration.py` | Ziel-Testdatei 1, 607 Zeilen, 8 AC-Tests (AC-1..AC-7) |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | Ziel-Testdatei 2, 868 Zeilen, 8 AC-Tests (AC-1..AC-8) |
| `.github/ci_tdd_excludes.txt` | Ratsche — Zeilen 77-78 sind der Eintrag, den es zu entfernen gilt |
| `src/services/trip_alert.py` | `check_radar_alerts()` (:909ff), `_effective_alert_channels()` (:1553-1591), Konstruktor mit `mail_sink`-DI-Naht (:140/150/164) |
| `src/services/notification_service.py` | `_dispatch_alert_message()` (:1429-1547) — Versand-Fanout, `mail_sink`-Prüfung (:1432) |
| `docs/specs/_archive/modules/issue_818_radar_briefing_integration.md` | Original-Spec, AC-7 fordert ausdrücklich "Kein Mock" (:132) |
| `docs/specs/_archive/modules/issue_822_radar_nowcast_segment.md` | Original-Spec zu Datei 2 |

## Existing Patterns

- **`mail_sink`-DI-Naht** (`trip_alert.py:140`, Docstring: *"Optional callable(subject, body) — captures mail calls in tests (DI seam for AC-4/AC-6; replaces SMTP when set)"*). Ein einfacher Callable, **kein** `unittest.mock`-Objekt — vereinbar mit der "Kein Mock"-Forderung der Original-Spec. Wird durchgereicht bis `notification_service.py:1432`: ist `mail_sink is not None`, wird `EmailOutput(...).send(...)` komplett umgangen.
- **Referenz-Vorlage im selben File**: `test_ac6_radar_throttle_via_alert_state_cooldown()` (818:500-553) setzt `mail_sink=lambda subject, body: captured.append((subject, body))` und ist damit sauber — kein Netzzugriff.
- **Referenz-Vorlage in Batch 4 bereits saniert**: `tests/tdd/test_feature_656_radar_nowcast.py:270-294` kombiniert Dummy-`Settings(smtp_host="test.invalid", ...)` **und** `mail_sink=...`.
- **`_effective_alert_channels()`** (`trip_alert.py:1553-1591`): liefert `{"email"}` als Legacy-Default, wenn `trip.alert_channels is None` und `report_config.send_email=True`. Genau dieser Legacy-Pfad löst in 818 den ungewollten Versand aus.
- **In 822 bereits sicher**: `test_ac8_mandantentrennung_isolated()` (822:799-868) setzt `report_config = TripReportConfig(..., send_email=False, send_telegram=False, alert_on_changes=False)` — kein Kanal aktiv, kein Egress-Risiko. Nur 818s AC-7 hat die Lücke.

## Konkreter Befund: der defekte Test

`test_ac7_mandantentrennung_isolated()` (818:560-608) konstruiert
`TripAlertService(throttle_hours=2, user_id=uid_a, radar_service=RadarNowcastService(frame_source=_wet_frames))`
**ohne** `mail_sink` und **ohne** Dummy-`settings=`. Der zugrundeliegende Trip
kommt aus `_make_active_trip()` (818:66-89) mit `report_config.send_email=True`
und `trip.alert_channels=None` → `_effective_alert_channels()` liefert `{"email"}`.
`self._settings = Settings().with_user_profile(user_id)` lädt die reale
Host-`.env`-Konfiguration; ist dort ein SMTP-Host hinterlegt, sendet
`EmailOutput(...).send(...)` real. Ziel-IP `178.104.143.19` in meinem
Testlauf (mit `--allow-hosts=127.0.0.1,::1` geblockt, Test blieb trotzdem
grün — die Verbindungs-Exception wird irgendwo verschluckt, das selbst ist
ein zweiter, kleinerer Fund, s. Risiken).

**Reparatur-Ansatz** (Muster aus AC-6 übernehmen): `mail_sink=lambda subject, body: None`
(oder sammelnd wie AC-6) im Konstruktor von `svc_a` ergänzen. Kein Dummy-`settings=`
nötig, da die Sink-Prüfung in `notification_service.py:1432` vor dem
`EmailOutput`-Aufbau greift.

**premium_sms-Risiko geprüft und ausgeschlossen**: `_dispatch_alert_message()`
sendet den premium_sms-Kanal ohne vorgeschaltetes `can_send_*()`-Gate
(`notification_service.py:1533-1547`) — der schärfste Kandidat für
ungewolltes Egress. Grep über beide Zieldateien zeigt: `alert_channels`
wird in keiner Fixture je explizit gesetzt, `premium_sms` kommt in keiner
der beiden Dateien vor. Das Risiko betrifft nur den Legacy-`{"email"}`-Default
in AC-7/818.

## Dependencies

- **Upstream:** `RadarNowcastService(frame_source=_wet_frames)` (Test-Stub für Wetterdaten, bereits injiziert) · `Settings` (SMTP/Telegram/SMS-Konfiguration, aus Host-`.env` wenn nicht überschrieben) · `TripReportConfig`/`Trip.alert_channels` (Kanalauswahl)
- **Downstream:** CI-Ampel (`test`-Check der 6 Pflicht-Checks) — sobald die Dateien aus der Ausschlussliste sind, laufen sie bei jedem PR mit.

## Existing Specs

- `docs/specs/_archive/modules/issue_818_radar_briefing_integration.md` (AC-7, "Kein Mock"-Klausel Zeile 132)
- `docs/specs/_archive/modules/issue_822_radar_nowcast_segment.md`
- `docs/specs/_archive/tests/issue_822_radar_nowcast_segment_tests.md`
- `docs/specs/modules/fix_1752_radar_folgt_alarm_kanaelen.md` — Kanal-Resolver-Kontext, gleicher Codepfad
- `docs/specs/modules/fix_1697_ortstag_statt_servertag.md` — der ursprüngliche Ortstag-Fix, referenziert direkt über dem Versand-Codeabschnitt (`trip_alert.py:931`)

## Warum ausgeschlossen — keine dokumentierte Einzelbegründung

`.github/ci_tdd_excludes.txt` nennt 818/822 nicht namentlich. Sie gehören zur
Pauschal-Charge "28 Runner-rote" aus Commit `2c7217ef` (2026-08-07): "haengen an
Server-Umgebung/.env/Creds — lokal im Haupt-Checkout kaschiert das der
Host-Zustand" — ohne Datei-Aufschlüsselung. `docs/analysis/1196-tdd-excludes-sanierung-2026-08-06.md`
enthält ebenfalls keinen 818/822-spezifischen Eintrag. Die oben gefundene
Egress-Lücke in AC-7/818 ist die einzige belastbare Spur und passt exakt zum
dokumentierten Muster von Batch 4 (`can_send_email()` nur mit Host-`.env` True).

## PR #1913 — bereits gemerged, keine Kollision

`origin/rework-1467-s4b-entdopplung` ist bereits Merge-Commit `edeb6ba3` auf
`origin/main` (Feature-Commit `99e65c7f`, `+110` in `trip_alert.py`). Fügt eine
neue Gate-Stufe `check_event_identity_gate()` + `record_event_identity(...)`
in `check_radar_alerts()` ein, zwischen Kanal-Split und `send_radar_alert(...)`
(~`trip_alert.py:1174-1206`). Berührt **nicht** den Versandpfad/die
`mail_sink`-Naht selbst. `git diff origin/main...origin/rework-1467-s4b-entdopplung -- src/services/trip_alert.py`
ist leer, weil main den Branch bereits enthält — der aktuelle Arbeitsstand
(`f9bc1a34`) ist also bereits die richtige Basis, kein Rebase nötig.

## Risks & Considerations

- **Der eigentliche Fund ist ein Egress-Risiko, kein reiner CI-Flake.** Der
  fehlende `mail_sink` in AC-7/818 hätte auf einem Runner ohne Socket-Sperre
  real gesendet, wenn dort produktive SMTP-Creds in der Umgebung lägen — das
  ist der Klasse #1477 zuzuordnen (Test-Gate für unbenannte/ungestubbte Sende-Tests).
- **Verschluckte Exception in meinem Vorab-Lauf**: `--allow-hosts` blockierte
  den Verbindungsversuch, der Test blieb trotzdem grün. Das deutet auf ein
  breites `try/except` im Versandpfad — sollte in der Spec/im Adversary-Dialog
  benannt werden (nicht Teil des Haupt-Fixes, aber beobachtungswürdig).
- **Marker/Deselektion**: Beide Dateien tragen **keine** Pytest-Marker
  (kein `pytest.mark.live`/`staging` modulweit) — Streichen aus der
  Ausschlussliste holt sie tatsächlich in die reguläre Kollektion.
  `--collect-only` nach der Änderung als Nachweis einplanen (Lehre aus #1708 B1:
  ungezählte Skips bleiben sonst unsichtbar grün).
- **#1708 B2 (`gregor-zwanzig-b4`)**: hatte dieselben zwei Dateien wegen
  `trips_dir`-Variablennamen/Kommentaren auf der Liste. Abgestimmt: b4 behält
  die reine Umbenennung in B2, dieser Workflow ändert nur, was für CI-Tauglichkeit
  nötig ist (die `mail_sink`-Ergänzung in AC-7).
- **CI-Runner ist Schiedsrichter, nicht der lokale Lauf.** Laut Kopf der
  Ausschlussliste waren 28 von 34 zuvor entfernten Einträgen auf dem Runner rot,
  obwohl sie lokal grün liefen. Der `/e2e-verify`- bzw. CI-Lauf nach dem Push
  ist der eigentliche Nachweis, nicht dieser Vorab-Lauf.
- **Zuschnitt-Frage:** Schließt diese Scheibe #1697? Empfehlung ja — der Kern-Bug,
  der Briefing-Pfad und die Muster-A-Restliste sind bereits erledigt; alles
  andere aus der ursprünglichen "Betroffene Stellen"-Tabelle ist inzwischen
  #1727 S5e zugeordnet.

## Analysis

### Type

**Bug** — ein Test-Gate ist unbewacht (fehlender CI-Nachweis) UND einer der
beiden ausgeschlossenen Tests hat einen eigenen Defekt (ungestubbter
Real-Versand). Keine neue Funktionalität, kein Feature.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_issue_818_radar_briefing_integration.py` | MODIFY | `mail_sink`-DI-Naht in `test_ac7_mandantentrennung_isolated()` (:560-608) ergänzen, Muster von `test_ac6_...` (:500-553) übernehmen |
| `.github/ci_tdd_excludes.txt` | MODIFY | Zeilen 77-78 (818/822-Einträge) entfernen |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | keine | bereits sicher (`send_email=False` explizit in AC-8), nur Aufnahme in CI |

### Scope Assessment

- Files: 2 geändert (818-Testdatei, Ausschlussliste), 1 unverändert mit-aufgenommen
- Geschätzt: +2/−2 LoC in `ci_tdd_excludes.txt`, +1 Zeile in der 818-Testdatei
- Risk Level: **LOW** — Änderung ist minimal und lokalisiert; das eigentliche Risiko (CI-Runner-Verhalten) liegt nicht in der Änderungsgröße, sondern darin, ob der Runner die Dateien tatsächlich grün durchlässt (Host-Zustand kaschiert das lokal laut Kopf der Ausschlussliste)

### Technical Approach

1. `test_ac7_mandantentrennung_isolated()` in 818 bekommt `mail_sink=lambda subject, body: None` (oder sammelnd analog AC-6) an der `TripAlertService(...)`-Konstruktion — verhindert den realen `EmailOutput`-Versand, ohne die "Kein Mock"-Klausel der Original-Spec zu verletzen (Callable, keine Mock-Library).
2. Beide Dateizeilen aus `.github/ci_tdd_excludes.txt` entfernen.
3. Nachweis: `--collect-only` auf beiden Dateien (Marker-Deselektion ausschließen, Lehre aus #1708 B1), dann lokaler Lauf, dann — als eigentlicher Schiedsrichter — der CI-Runner nach Push.
4. Spec-AC muss explizit die Egress-Freiheit als Zusicherung benennen (nicht nur "Test läuft grün"), sonst prüft der Adversary am falschen Ort (Lehre: Barriere muss am Gefahrenpunkt liegen).

### Dependencies

Keine Produktivcode-Abhängigkeiten. Downstream ausschließlich die CI-Ampel
(`test`-Check). Kein Rebase nötig (PR #1913 bereits in `main` enthalten,
Versandpfad unberührt).

### Open Questions

- [x] Kollidiert #1913 mit dem Versandpfad? — Nein, geprüft, gemergt, unberührt.
- [x] Kollidiert #1708 B2? — Nein, abgestimmt mit `gregor-zwanzig-b4`.
- [ ] Schließt diese Scheibe #1697? — Empfehlung ja, PO-Entscheidung in Spec-Freigabe einholen.
