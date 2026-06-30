# Context: feat-919-radar-alert-canonical

## Request Summary
Radar-/Nowcast-Alert soll denselben kanonischen Renderer-Weg (AlertMessage → render_subject/email/telegram/sms) nutzen wie der Abweichungs-Alert aus #917. `outputs/radar_alert.py` entfällt danach.

## Aktueller Radar-Alert-Pfad

`check_radar_alerts` → `build_radar_alert_subject/body` (plain-text only) → EmailOutput + TelegramOutput

**Aktuelles Format:**
- Betreff konvektiv: `[KHW 403] ⚠️ Gewitter – Segment 3, km 12–24`
- Betreff Regen: `[KHW 403] Regen zieht auf – Segment 3, km 12–24`
- Body: `<onset_text>\nauf <segment_label>.\n\nQuelle: <source>.\nDu erhältst diese Warnung höchstens einmal in <cooldown>.`
- **Nur plain-text, kein HTML**

## Related Files

| Datei | Relevanz |
|-------|---------|
| `src/outputs/radar_alert.py` | Zu ersetzender Renderer (45 LoC, wird gelöscht) |
| `src/output/renderers/alert/model.py` | AlertMessage + AlertEvent; `source`-Feld für Radar reserviert |
| `src/output/renderers/alert/project.py` | `to_alert_message` als Vorlage für neue `to_radar_alert_message` |
| `src/output/renderers/alert/render.py` | Generische Renderer; brauchen Onset-Zweig |
| `src/services/trip_alert.py` | `check_radar_alerts` (Zeilen 604–800) — Migration-Ziel |
| `src/services/radar_service.py` | `NowcastResult` + `source_label`-Mapping |

## NowcastResult Felder
- `onset_minutes: int | None` — Minuten bis erster Regenframe
- `intensity_label: str` — "Leichter Regen", etc.
- `source: str` — "radar"/"INCA"/"AROME-FR"/"ICON-D2"/"minutely_15"
- `is_convective: bool` — Gewitter/Hagel (WMO 95/96/99)

## Kern-Problem: AlertEvent-Inkompatibilität

Radar-Onset hat **kein** `value_from`/`value_to`/`threshold`/`delta_pct` — das sind Abweichungs-Konzepte.

| Feld | Deviation | Radar-Onset |
|------|-----------|-------------|
| value_from / value_to | ✓ Alter/neuer Wert | ✗ bedeutungslos |
| threshold | ✓ Empfindlichkeitsschwelle | ✗ Onset ist binär |
| delta_pct | ✓ relative Änderung | ✗ sinnlos |
| km_from / km_to | ✓ Event-Segment | ✓ aktives Segment |
| occurred_at | ✓ Peak-Stunde | ✓ Onset-Zeit |

→ Renderer müssen einen **Onset-Zweig** bekommen (erkennbar z.B. an `source != None` oder `metric_id == "radar_onset"`).

## Versand aktuell vs. Ziel

| Kanal | Aktuell | Ziel |
|-------|---------|------|
| Email | plain-text via `build_radar_alert_body` | HTML via `render_email` (wie Deviation) |
| Telegram | onset_text (kurz) | `render_telegram(msg)` |
| SMS | ❌ nicht implementiert | `render_sms(msg)` falls konfiguriert |

## Bestehende Tests (dürfen nicht brechen)

- `test_issue_830_radar_alert_validator.py` — Mail-Struktur-Validierung
- `test_issue_827_radar_throttle_recording.py` — Throttle + alert_log
- `test_issue_822_radar_nowcast_segment.py` — Segment-Auswahl
- `test_issue_818_radar_briefing_integration.py` — Briefing-Unterdrückung
- `test_feature_660_convective_stage.py` — Convective-Override (#883)

## Analysis

### Technischer Ansatz (Plan-Agent Empfehlung)

**Neuer `OnsetEvent`-Dataclass** in `model.py` neben `AlertEvent` (Union-Typ laut Spec `issue_917_alert_renderer.md` Zeile 122):
- Felder: `onset_minutes`, `intensity_label`, `is_convective`, `occurred_at`, `km_from`, `km_to`, `source_label`, `cooldown_display`
- `AlertMessage.events` wird zu `tuple[AlertEvent | OnsetEvent, ...]`
- `msg.source is not None` als einziger Schalter in allen 4 Renderern

Jeder Renderer bekommt einen privaten `_render_*_onset`-Zweig (~5 LoC je Renderer), aufgerufen wenn `msg.source is not None`.

### Betroffene Dateien

| Datei | Typ | Was ändert sich |
|-------|-----|----------------|
| `src/output/renderers/alert/model.py` | MODIFY | `OnsetEvent` hinzufügen; `events` → Union-Tuple |
| `src/output/renderers/alert/render.py` | MODIFY | 4× Branch + 4× `_render_*_onset` privat (~60 LoC) — **Gate-geschützt** |
| `src/services/trip_alert.py` | MODIFY | `check_radar_alerts`: `build_radar_alert_*` → `AlertMessage(OnsetEvent)` + 4 Renderer |
| `src/outputs/radar_alert.py` | DELETE | 46 LoC entfallen |
| `.claude/hooks/renderer_mail_gate.py` | MODIFY | `radar_alert.py`-Eintrag entfernen |
| Tests | CREATE | Onset-Renderer-Tests für alle 4 Kanäle (~80 LoC) |

### Scope

- ~170 LoC geändert/neu, 6 Dateien + 1 gelöscht
- LoC-Limit: Standard 250 reicht

### Gates die greifen

- **Renderer-Mail-Gate**: `render.py` ist in `_MAIL_PATTERNS` → Commit blockiert bis Radar-Alert-Validator grün
- **Radar-Alert-Validator** (`radar_alert_mail_validator.py`): prüft Plain-Part der zugestellten Staging-Mail
- **Kein** Briefing-Matrix-Test nötig (Briefing-Renderer-Dateien werden nicht berührt)

## Risiken

1. **AlertEvent-Modell muss Onset-Fall sauber tragen** — klare Lösung nötig vor Spec
2. **Renderer-Mail-Gate greift** — Änderungen an `render.py` brauchen Modus-Matrix-Test + briefing_mail_validator grün
3. **test_issue_830** prüft Mail-Struktur — wird nach Migration auf HTML-Rendering angepasst werden müssen
4. **Convective-Override (#883) + Cooldown (#818/#822) müssen erhalten bleiben** — nur Render-Pfad ändert sich, Logik nicht
