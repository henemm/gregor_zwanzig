# Context: Issue #638 — Alerts-Tab Karten-Modell + Severity-Falle + Kanal pro Alert

## Request Summary
Der Alerts-Tab im Trip-Bearbeiten wird auf das JSX-Karten-Modell (`TE2_AlertsTab`) umgebaut, die kosmetisch-aber-gefährliche Severity-Auswahl entfernt (Info-Alerts werden heute still verschluckt), und jeder Alert erhält **eigene Kanäle** (vorbelegt aus den Briefing-Kanälen, pro Alert überschreibbar) mit echtem kanalbewusstem Versand.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `docs/design-requests/trip-anlegen-2026-06-06/screen-trip-edit-v2-main.jsx` | **SOLL-Quelle** `TE2_AlertsTab` (Z.339–392): Karte = Label · Metrik · Bedingung · Switch · Kanal-Chips; Infozeile „Kanäle erben aus Wetter-Metriken, pro Alert überschreibbar"; „+ Neuen Alert hinzufügen" |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Aktueller Container (#180/#586): Tabellen-Paradigma `AlertMetricTable` + Modus-Picker → muss aufs Karten-Modell |
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | Aktuelle Tabelle (wird ersetzt/abgelöst) |
| `frontend/src/lib/types.ts` (Z.79–85) | TS `interface AlertRule` mit `severity` — `channels?: string[]` ergänzen |
| `internal/model/trip.go` (Z.39–47) | Go `AlertRule`-Struct (typisiert) — `Channels []string json:"channels,omitempty"` ergänzen; `Severity` bleibt (omitempty/abgeleitet) |
| `src/app/models.py` (Z.766–777) | Python `@dataclass AlertRule` — `channels: list[str]` ergänzen (default factory) |
| `src/app/loader.py` (Z.122–133, 1040–1052) | Parse `_alert_rule_from_dict` + Serialize alert_rules — `channels` rein, Migration severity→optional |
| `src/services/trip_alert.py` (Z.410–424, 631–720) | **Kern-Backend:** `_filter_significant_changes` (Severity-Falle) + `_send_alert` (heute nur `report_config`-Kanäle für ALLE Alerts) → pro-Alert-Routing |
| `src/services/weather_change_detection.py` (Z.67–71, 188–229, 282–296, 361–384) | Severity-Mapping + `from_alert_rules` + `_classify_severity` (Auto-Ableitung existiert bereits!) |
| `docs/reference/api_contract.md` (Z.352) | AlertRule-DTO Doku — severity/channels aktualisieren |

## Existing Patterns

- **Auto-Severity existiert schon:** `WeatherChangeDetectionService._classify_severity(delta, threshold)` klassifiziert per Verhältnis Delta/Schwelle in MINOR/MODERATE/MAJOR. Heute wird sie aber von `rule.severity` über `severity_overrides` *überschrieben* (#222). Für #638: Override entfernen → echte Ableitung, nur als Label.
- **Severity-Falle (Kern-Bug):** `trip_alert.py:423` `significant_severities = {MODERATE, MAJOR}` filtert MINOR raus. `AlertSeverity.INFO → ChangeSeverity.MINOR` (Mapping `weather_change_detection.py:68`). → Info-Alert wird erkannt, aber NIE versendet.
- **Kanal-Routing heute (zu grob):** `_send_alert` nutzt `trip.report_config.send_email/send_telegram` für *alle* Changes gemeinsam. Kein Bezug zur auslösenden Regel.
- **Briefing-Kanäle als Quelle der Vorbelegung:** `report_config.send_email/send_sms/send_telegram` (Python `TripReportConfig` `models.py:704–706`; Go `report_config`-Map). JSX nennt sie „aktive Kanäle aus Wetter-Metriken".
- **Schema-Migration sicher:** `_migrate_legacy_alert_rules` parst bestehende `alert_rules` 1:1; neues Feld muss `data.get("channels", <fallback>)` nutzen (kein KeyError auf Bestandsdaten). Datenverlust-Prinzip BUG-DATALOSS-GR221 beachten.

## Dependencies
- **Upstream (was Alerts nutzt):** `report_config` (Kanäle-Vorbelegung), `MetricCatalog`/`AlertMetric`, `WeatherChangeDetectionService`, `EmailOutput`/`TelegramOutput`.
- **Downstream (was Alerts konsumiert):** Trip-Persistenz (`loader.py` save/load), Go-`Trip`-Serialisierung (`internal/store`), Cockpit `_highest_severity`-Token (`#393`), `/api/trips/{id}` PUT (RMW-Merge).

## Existing Specs
- `docs/specs/modules/issue_205_alert_rules.md` — AlertRule-Grundmodell
- `docs/specs/modules/issue_180_alert_metric_table.md` — aktuelles Tabellen-Paradigma (wird abgelöst)
- `docs/specs/modules/issue_222_*` — rule.severity-Override (wird für #638 zurückgebaut)

## Risks & Considerations
- **Pro-Alert-Routing braucht Change→Rule-Zuordnung:** `WeatherChange` muss wissen, welche Regel(n) es auslösten, um nach deren `channels` zu gruppieren. Heute aggregiert `from_alert_rules` alles in einen Detektor ohne Rückbezug. → Entweder pro-Regel detektieren oder `WeatherChange` um `rule_id`/`channels` anreichern. **Meatiest piece.**
- **Severity-Falle beseitigen ohne Spam:** Wenn MINOR nicht mehr gefiltert wird, könnte Alarm-Müdigkeit entstehen. Best Practice (CAP): jeder *vom Nutzer explizit konfigurierte & aktive* Alert, dessen Schwelle gerissen wird, MUSS senden — Severity nur als Label. Throttle/Cooldown/Quiet-Hours bleiben als Spam-Schutz.
- **Multi-User-Pflicht:** Versand pro Alert/Kanal mit zwei Nutzern testen (mandantengetrennt).
- **Schema-Add an `internal/model/trip.go` + `models.py` + `loader.py`** → `data_schema_backup.py`-Hook greift; Roundtrip-Test Pflicht (Bestands-Alerts ohne `channels`/mit `severity` dürfen nicht brechen).
- **LoC:** Frontend-Redesign + Go-Schema + Python-Routing + Migration → klar > 250 LoC. Slicing oder LoC-Override nötig (PO-Abstimmung).
- **Pixel-Fidelity-Gate** gegen aus JSX gerendertes SOLL (Karten-Layout).
