# Mini-Spec: Footer-Fallback-Konsistenz plain + html (#1145 + #1153)

Bündelt zwei Nebenbefunde aus der #1141-Planung (Cross-Provider-Fallback, ADR-0018 „Nicht-Kaschieren"):

- **#1145** — Plain-Text-Footer sollte bei **leerer** `fallback_metrics` sauber lesbar sein (kein `" : "`-Artefakt). *Faktisch bereits durch #1141 gelöst* (`plain.py:288–291` hat `if/else`); dieser Workflow sichert das per Regressionstest ab.
- **#1153** — HTML-Footer (`html.py::_render_footer`) zeigt **gar keinen** Fallback-Hinweis; das Wort `fallback` fehlt im gerenderten HTML komplett. Verstoß gegen Nicht-Kaschieren (ADR-0018). Das ist die eigentliche Implementierungsarbeit.

## Was ändert sich

- `src/output/renderers/email/html.py`: `_render_footer` bekommt einen Fallback-Hinweis-Block, **wenn** `segments[0].timeseries.meta.fallback_model` gesetzt ist. Inhalt spiegelt den Plain-Text-Footer:
  - mit Metriken: `Fallback <metrik, metrik>: <fallback_model>`
  - ohne Metriken (leere Liste): `Fallback: <fallback_model>` (kein `" : "`-Artefakt)
  - Styling passend zum bestehenden dunklen Footer (`FONT_DATA`, gedämpfte Footer-Farbe), als eigene Zeile — bricht das bestehende zweizeilige Footer-Layout (Brand-Zeile + Link-Zeile) nicht.

## Was darf sich nicht ändern

- Plain-Text-Footer (`plain.py`) bleibt inhaltlich unverändert — er ist bereits korrekt (#1145 dort schon gelöst).
- Kein Fallback-Hinweis, wenn `fallback_model` **nicht** gesetzt ist (Regelfall) — weder plain noch html. Kein neues Artefakt im Normalfall.
- Bestehendes Footer-Layout (Brand-Zeile, Link-Zeile, RISK-Legende, Deep-Links `trip_url`) bleibt intakt.
- Keine anderen Renderer-Pfade (compare, sms, compact).

## Manuelle Test-Schritte (Staging-E2E, vor Prod-Deploy)

1. Staging-Briefing mit gesetztem `fallback_model` auslösen, echt zugestellte Mail aus `gregor-test@henemm.com` (IMAP) prüfen.
2. HTML-Teil enthält sichtbaren Fallback-Hinweis mit Modellname; Plain-Teil unverändert korrekt.
3. `briefing_mail_validator.py` gegen die zugestellte Mail → Exit 0.
4. Regelfall-Briefing (kein Fallback) → weder plain noch html enthalten `fallback`.

## Inline-Test (wird während Implementierung geschrieben/aktiviert)

Bestehende Tests in `tests/unit/test_model_metric_fallback.py::TestFooterFallbackInfo`:

- [ ] `test_html_footer_shows_fallback` — grün (aktuell rot): `fallback` + `icon_eu` im `report.email_html`.
- [ ] `test_plain_footer_shows_fallback` — bleibt grün.
- [ ] Neuer Regressionstest: HTML- **und** Plain-Footer bei **leerer** `fallback_metrics` → enthält `fallback` + Modellname, aber **kein** `" : "`-Artefakt (deckt #1145 ab).
- [ ] Neuer Regressionstest: **ohne** `fallback_model` → weder plain noch html enthalten `fallback` (Regelfall, kein neues Artefakt).

Synthetische Testdaten, deterministisch (kein Live-API-Effekt).

## Gates (nicht überspringbar trotz Fast Track)

- Renderer-Commit-Gate #811 (`html.py` ist Mail-Content-Datei): `test_issue_811_mode_matrix.py` grün + frischer `briefing_mail_validator.py`-Lauf.
- Staging-E2E gegen echt zugestellte Mail vor Prod-Deploy.
