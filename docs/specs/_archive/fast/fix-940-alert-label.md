# Mini-Spec: fix-940-alert-label

## Was ändert sich

- `src/output/renderers/alert/render.py`: Neue Hilfsfunktion `_label(e)` gibt `get_metric(e.metric_id).label_de` zurück (z. B. "Sichtweite" statt "VS", "Nullgradgrenze" statt "NL")
- In **E-Mail und Telegram** wird überall `_code(e)` durch `_label(e)` ersetzt:
  - `_h1()` — Überschrift der Alert-Mail
  - `_email_line()` — Zeile pro Metrik im Mail-Body
  - `render_subject()` — Betreff (1 Metrik und Multi-Metrik-Fall)
  - `render_telegram()` — Telegram-Nachricht
- `_code(e)` bleibt unverändert und wird weiterhin ausschließlich in `render_sms()` und `_sms_token()` verwendet

## Was darf sich nicht ändern

- SMS-Rendering bleibt unverändert (kurze ASCII-Token sind dort Pflicht)
- Radar/Onset-Pfade (`msg.source is not None`) werden nicht berührt
- `get_sms_code()` und alle SMS-Codes im Metrik-Katalog bleiben unverändert

## Manuelle Test-Schritte

1. Alert-E-Mail auf Staging triggern (oder Unit-Test ausführen)
2. Betreff zeigt "Sichtweite" / "Nullgradgrenze" statt "VS" / "NL"
3. E-Mail-Body: gleiche lesbaren Label in jeder Metrik-Zeile
4. SMS-Vorschau (falls vorhanden) zeigt weiterhin kurze Codes

## Inline-Test

- [ ] `render_subject()` mit `metric_id="visibility"` → enthält "Sichtweite", nicht "VS"
- [ ] `render_subject()` mit `metric_id="freezing_level"` → enthält "Nullgradgrenze", nicht "NL"
- [ ] `render_sms()` mit `metric_id="visibility"` → enthält weiterhin "VS"
