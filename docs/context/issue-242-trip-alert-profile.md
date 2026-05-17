# Context: Issue #242 — Trip-Alert-Mail: ActivityProfile durchreichen

Sub-Issue 4 von Epic #236. Setzt #241 (ActivityProfile durch Mail-Pipeline) voraus.

## Request Summary

`src/services/trip_alert.py:405` ruft `format_email` heute ohne `profile`-kwarg auf — jeder Trip-Alert fällt damit auf ALLGEMEIN-Grau zurück, obwohl die Render-Infrastruktur das Profil sofort visualisieren würde. **Eine einzige Zeile** ergänzen: `profile=trip.aggregation.profile`.

## Aktuelle Situation (Post #241)

```python
# src/services/trip_alert.py:405-411
report = self._formatter.format_email(
    segments=weather,
    trip_name=trip.name,
    report_type="alert",
    display_config=trip.display_config,
    changes=changes,
)
```

`format_email` aus `src/formatters/trip_report.py` akzeptiert seit #241 `profile: Optional[ActivityProfile] = None`. Trip-Briefing-Mails übergeben `trip.aggregation.profile` korrekt; Trip-Alert nicht.

## Was geändert wird

| Datei | Funktion | Änderung |
|-------|----------|----------|
| `src/services/trip_alert.py:~405` | `_send_email_alert` (Helper) | `profile=trip.aggregation.profile` als kwarg ergänzen |
| `tests/tdd/test_email_profile_pipeline.py` ODER neue Datei | Source-Inspection-Test | `assert "profile=trip.aggregation.profile" in trip_alert.py` |

## Datenmodell (unverändert, aus #241)

| Pfad | Wert |
|------|------|
| `Trip.aggregation.profile` | `ActivityProfile` (Default WINTERSPORT) |
| `format_email(profile=...)` | akzeptiert seit #241 |
| `render_html(profile=...)` | rendert Header-Eyebrow + profilspez. Akzent |

## LoC-Schätzung

| Datei | Δ |
|-------|---|
| `src/services/trip_alert.py` | +1 |
| Test (Source-Inspection oder integriert in bestehende Suite) | +15 |
| Spec + Test-Manifest (Doku zählt nicht) | 0 |

Total ~16 Code-LoC. Trivial unter 250-Budget.

## Tests

- **Source-Inspection** (analog AC-5 aus #241): `tests/tdd/test_email_profile_pipeline.py` oder neue Datei mit Substring-Check
- **In-Process-Render** (analog AC-3 aus #241): Alert-Pipeline mit WINTERSPORT-Trip → HTML enthält `#4a7fb5` und `Wintersport`
- **Bestehende Suiten** bleiben grün

## Out of Scope

- Inhalt der Alert-Mail (welche Daten, welcher Wortlaut)
- Service-Error-Mail (Sub-Issue 5)
- Inbound-Reply-Mail (Sub-Issue 6)
- Refactor von `trip_alert.py`

## Risiken

- **Default WINTERSPORT** (aus `AggregationConfig`): bestehende Trips ohne explizites Profil bekommen Wintersport-Akzent — dasselbe Verhalten wie bei Briefing-Mails seit #241. Akzeptabel.
- **Real-Gmail-Test** weiterhin deferred — MQ 20834 (Gmail→Stalwart-Relay) noch offen. In-Process-Verifikation reicht.
- **Trip-Alert-Pipeline ist deutlich kleiner als Briefing** — kein iframe-Preview, kein Plain-Renderer-Pfad gesondert: format_email ruft render_email → render_html + render_plain — alle drei sind seit #241 profil-aware.

## Verwandte Specs

- `docs/specs/modules/issue_241_email_profile_pipeline.md` — Pattern und Pipeline-Logik
- `docs/specs/modules/output_channel_renderers.md` — β3-Renderer-Spec
- Epic #236 Body — Übersicht aller Sub-Issues
