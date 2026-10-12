# Context: #1430 — Lawinenwarnungen von MeteoAlarm (Typ 9) werden still verworfen

Epic: #2258 (erstes Ticket; Reihenfolge #1430 → #1441 S1 → #1473 → #1441 S2)

## Analysis

### Type
Bug (nutzersichtbar: „keine amtlichen Warnungen“ trotz vorliegender Lawinenwarnung) — technisch eine Vokabular-Erweiterung.

### Befunde (belegt am Code)
1. `_TYPE_HAZARD_MAP` (`src/services/official_alerts/meteoalarm.py:474-485`) kennt Typ 9 nicht; `_group_and_map_info_entries` (Zeile ~629) macht bei `hazard is None` ein `continue` — **ohne Log**.
2. Beide Eingangswege laufen durch dieselbe Stelle (CAP-XML-Weg und JSON-Feed-Weg `meteoalarm_feed`): eine Änderung genügt für IT, AT, DE.
3. **Stufen-Problem aus dem Ticket entfällt für #1430:** MeteoAlarm liefert auch bei Typ 9 die Awareness-Stufe 1–4 (Fixture: `3; orange; Severe`). Die 1–5-Skala (EAWS) betrifft erst #1441 (`AvalancheDanger`), nicht diese Warnart. `OfficialAlert.level` 1–4 bleibt unverändert.
4. Fixture vorhanden: `tests/fixtures/meteoalarm/cap_avalanche_plus_heat.xml` (echte Aufzeichnung, Typ 9, Stufe 3, GeoSphere AT).
5. **SMS-Kürzel-Kollision:** `AV` ist bereits für die Lawinen-*Stufe* (Wintersport-Token, `builder.py:56/314`, `sms_format.md:365`) belegt. Ein Kürzel = eine Bedeutung (#2417) ⇒ das Warn-Kürzel für `avalanche` darf NICHT `AV` heißen. Auch der Fallback `sms_symbol_for("avalanche")` würde `AV` liefern → genau diese Falle fängt ein Test.
6. Bonus: Nebel (4) und Küste (7) sind bewusst unbemappt, aber ebenfalls still. Ticket fordert „dokumentiert verworfen“ statt stillschweigend (ADR-0018 Nicht-Kaschieren).

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/services/official_alerts/meteoalarm.py` | MODIFY | `9: "avalanche"` ins Mapping; bewusst verworfene Typen 4/7 mit Debug-Log + Kommentar statt stillem `continue` |
| `src/output/tokens/hazard_symbols.py` | MODIFY | Katalog: SMS-Kürzel (≠ `AV`), Bedeutung EN/DE |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `_HAZARD_LABELS["avalanche"]` = „Lawine“ |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_warn_short()`: Zweig `avalanche` (Fallback `alert.label` zeigt sonst Rohtext) |
| `tests/tdd/test_meteoalarm_source.py` | MODIFY | Fixture-Test Typ 9 → `avalanche`, Stufe 3 |
| `tests/tdd/test_sms_official_alert_tokens.py` | MODIFY | Dupliziertes Spec-Symbol-Verzeichnis + Label-Liste erweitern; Kollisionstest gegen `AV` |
| `docs/reference/sms_format.md`, Spec `sms_official_alert_tokens.md` | MODIFY | Kürzel dokumentieren (zählt nicht ins LoC-Limit) |

### Scope Assessment
- Files: ~6 Code/Test + 2 Doku
- Estimated LoC: +60/-5 (innerhalb 250)
- Risk Level: LOW — additive Erweiterung; Hauptrisiko ist das Kürzel (Kollision) und dass alle vier Kanäle die Gefahr wirklich tragen.

### Technical Approach
Neue Gefahrenart `avalanche` als Katalog-Eintrag (SSOT `hazard_symbols.py`), danach folgen Labels/Renderer. Alle vier Kanäle (Mail, Telegram, SMS, Premium-SMS) laufen über dieselben Kataloge — Tests müssen pro Kanal zeigen, dass die Lawinenwarnung ankommt (Fixture → Alert → je Kanal-Rendering), und mit zwei Nutzern, soweit Endpoints berührt werden (hier voraussichtlich keine neuen Endpoints).
Nebel/Küste: dokumentiert verworfen (Kommentar + Debug-Log), nicht gemappt.

### Dependencies
- Davor: keine. Danach: #1441 S1 (nutzt `avalanche` als Gefahrenart und braucht die 1–5-Skala über `AvalancheDanger`), #1473 (Wintersport-Token `AV` — daher Kürzel-Abgrenzung jetzt).
- Berührt Abdeckung #1681 (DE-Feed) automatisch mit.

### Open Questions
- [ ] Warn-Kürzel für Lawine: Vorschlag `AW` (Avalanche Warning) bzw. `LW`; Kollisionsprüfung gegen alle Builder-Kürzel in der Spec. Entscheidung: Tech Lead (kein PO-Thema).
- [ ] Sortierposition im Katalog (Gleichstand bei Warnstufe): Vorschlag direkt nach `snow`.
