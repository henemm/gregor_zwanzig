# Kontext: warnmail — Darstellungsfehler Warn-/Alarm-Mail (Trips)

Gebündelter Bug-Fix für vier GitHub-Issues zur Darstellung amtlicher Warnungen in
Trip-Mails. Bündel `bundle:G-mail-darstellung`.

- #1326 — amtliche Warn-Mail: 63-Segment-Route-Gitter + doppelte Hazard-Benennung
- #1248 — Betreff nennt Segment der führenden Warnung, als gälte es für alle
- #1251 — Quelle global statt pro Warnung bei zusammengefasster Warnung (2 Behörden)
- #1338 — Abweichungs-Alarm: interne Herkunfts-/Versionszeile durchgesickert + Warn-Block bricht aus Format

## Analysis

### Type
Bug (gebündelt, 5 Einzel-Befunde)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/alert/official_alerts.py | MODIFY | Befund 1 (Builder free_chips=[]), 2 (_display_label else-Zweig), 3 (Betreff-Umfang _uniform_scope) |
| src/services/notification_service.py | MODIFY | Befund 4b (_dispatch_alert_message: geteilter render_warn_block statt roher Plain-Embed); Befund #1251 (source_label pro Warnung) |
| src/output/renderers/email/helpers.py | MODIFY | Befund 4a (Origin-Footer Zeile 2 aus Produktions-Mail entfernen) |
| src/output/renderers/alert/render.py | MODIFY | Befund 4a (Aufrufkette _with_origin) |
| tests/tdd/test_official_alert_template_render.py | MODIFY | AC-Assertions Befund 1+3 mitziehen |
| tests/tdd/test_mail_origin_footer.py | MODIFY | #1241-Tests für Befund 4a mitziehen |

### Root Causes (file:line, aus Plan-Analyse)
- **Befund 1 (#1326a) — 63-Segment-Gitter:** `official_alerts.py:1737-1747` `_trip_total_segment_ids` erzeugt Vollliste; `build_official_alert_notices:1788-1794` befüllt `free_ids`/`free_chips` mit allen nicht-betroffenen. Render an `:1009-1018`, `:1045-1046`, `:1364-1365`. Compare-Builder setzt `free_chips=[]` bereits (`:1853`) — Vorbild.
- **Befund 2 (#1326b) — Doppelname:** `official_alerts.py:605-608` else-Zweig `display = f"{typ} — {label}"` konkateniert deutschen Typ + rohen englischen Quell-Titel (nur gemappte hazards mit divergierendem Label, primär Vigilance/MeteoAlarm).
- **Befund 3 (#1248) — Betreff-Umfang:** `render_official_alert_subject:746-749`; F006-uniform-Prüfung greift nur für `scope_kind=="locations"`, Route-Pfad nimmt immer `_scope_display(leading)`. Helper `_uniform_scope:1062-1081`.
- **Befund 4a (#1338 Footer):** `render.py:372-383` `_with_origin`; `helpers.py:431` baut Zeile 2 `renderer_name · _DEPLOYED_COMMIT`; `"unknown"` aus Git-Fallback `helpers.py:389`. Bewusstes #1241-Feature auf allen Mail-Renderern.
- **Befund 4b (#1338 Format):** `notification_service.py:945-960` `_dispatch_alert_message` kippt HTML-escaped Plaintext roh in `<p>`; korrekt wäre geteilter `render_warn_block(variant="embedded")` wie `send_official_alert:574-584`. `_dispatch_alert_message` bekommt kein `trip` → optional durchreichen.
- **#1251 — Quelle pro Warnung:** `source_label`/`source_url` sind mail-globale Werte des führenden Alarms; zusammengefasste Karte aus zwei Behörden nennt nur eine Quelle. Vorbild: `OfficialAlertNotice.regions`-Aggregation aus #1238/#1239.

### PO-Entscheidungen (2026-07-23)
- **Befund 1:** Warn-Karte zeigt NUR betroffene Segmente ("Betrifft: Segment 5, Ziel"), kein Voll-Gitter, keine durchgestrichenen Segmente. → **Kehrt #1233/#1216 zurück (neues ADR nötig, Status „Abgelöst").**
- **Befund 4a (präzisiert 2026-07-23):** Die Herkunftszeile soll die **echte Datenquelle** anzeigen (woher Wetter/Warnung stammt, z.B. Provider-/Behördenname), statt des internen Renderer-Pfads (`alert/render.py`) und des Git-Versions-Fallbacks (`unknown`). Also: technischen Slot durch die tatsächliche Quelle ersetzen, nicht bloß entfernen. Betrifft alle Mail-Typen. → **Kehrt #1241 (Zeile 2 = Renderer+Commit) zurück (neues ADR nötig, Status „Abgelöst").**
  - OFFEN für Spec: exakte Quell-Semantik. Abweichungs-Alarm speist sich aus Wetter-Provider (`weather_snapshot.provider`, kann selbst `"unknown"` sein → muss befüllt werden). Eingebetteter amtlicher Warn-Block hat eigene Quelle pro Warnung (siehe #1251). Spec muss festlegen, welcher Quell-String je Mail-Typ erscheint und wie `"unknown"`-Fälle vermieden werden.

### Scope Assessment
- Files: 4 Produktiv + 2 Test
- Estimated LoC: ~50-75 Produktiv + ~40-50 Test
- Risk Level: MEDIUM (geteilte Funktionen `render_warn_block`/`_display_label`; Golden-Email-Fixtures prüfen; 4a ist Feature-Rücknahme mit breiter Test-Auswirkung)

### Empfohlene Reihenfolge
3 (Betreff) → 2 (Doppelname) → 1 (Chips) → #1251 (Quelle) → 4b (Format) → 4a (Footer, breiteste Test-Auswirkung).

### Risiko-Notizen
- `_display_label`-Fix (2) betrifft nur else-Zweig (gemappte hazards mit englischem Roh-Label); access_ban/„Extreme Hitze" laufen über andere Zweige → unberührt. Golden-Fixtures vor Merge prüfen.
- Befund 1 greift nur im Trip-Builder; Compare unberührt (setzt free_chips bereits leer). SMS/Telegram nutzen scope_label, nicht free_chips → unberührt.
- Befund 4a wirkt auf ALLE Mail-Typen (Trip-Briefing, Compare, official-alert) — konsistent gewollt, aber #1241-Rücknahme.

### Open Questions
- [ ] LoC-Limit 250: aktuell ~90-125 gesamt — im Rahmen. Falls 4a die Test-Nachzüge sprengt, ggf. eigener Folge-Workflow (PO-Freigabe).
