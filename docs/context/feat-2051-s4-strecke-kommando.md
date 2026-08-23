# Context: feat-2051-s4-strecke-kommando

## Request Summary

Issue #2051 Scheibe S4: Ein neues Inbound-Kommando (Arbeitstitel `/strecke`), das die
Regen-Ereignisflaechen **entlang der Reststrecke der aktiven Etappe** ausgibt. Bestand:
alle Kommandos (`/jetzt`, `/heute`, `/morgen`, `/gewitter`, `/timeline_heute`, `/glance`)
liefern **Ortswetter an einem Punkt** — keins die Lage entlang der Strecke.

Die Datenbausteine liegen seit S2a/S2b live vor; S4 verdrahtet sie erstmals in einen
**abrufbaren** Pfad statt in den Alarm-Pfad.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py` | Channel-agnostischer Kommando-Kern. `_VALID_COMMANDS:83`, `_BARE_KEYWORD_MAP:87-102`, Dispatch `:512-546`, Hilfe `_show_help:1371-1391`, Vorbild-Handler `_show_now:1507-1582` |
| `src/services/inbound_telegram_reader.py` | Telegram-Eingang. `_VALID_COMMANDS:33-35`, `_SHORTCUT_MAP:37-57`, Parser `_parse_command:205`, Aufruf `process():245,274`, Antwort-Formatierung `:257-263` |
| `src/services/inbound_email_reader.py` | Zweiter Eingang, ruft `process()` auf `:153`, Antwort `:156` |
| `src/services/trip_segments.py` | `points_along_remaining_route():683-715`, Konstanten `RADAR_ZONE_POINT_SPACING_KM=2.0`, `RADAR_ZONE_MAX_POINTS=6` `:36-37`; `position_at_time`, `resolve_current_segment` |
| `src/services/rain_extent.py` | `RainZone:27-43` (km_from, km_to, onset_minutes, event_end_minutes), `derive_rain_zones():46-91` |
| `src/services/radar_service.py` | `RadarNowcastService.get_nowcast()`, `format_now_text():563-662` (Textvorlage der Kommando-Antwort mit S1-Ende und S3-Reichweite) |
| `src/services/trip_alert.py` | Referenz-Kette Punkte→Nowcasts→Zonen: `:1637-1639`, `:1720`, `:1738-1770` |
| `src/services/forecast_budget.py` | `ForecastBudgetGate:36`, `DAILY_BUDGET=9000`, `POLLING_THRESHOLD=0.80`, `BRIEFING_ONLY_THRESHOLD=0.95` `:40-42`, `allow():54-73` |
| `src/services/radar_cache.py` | Nowcast-Cache, Schluessel lat/lon/Region/Hoehe `:72-84`, TTL 300 s `:123`, prozessweites Singleton |
| `src/output/renderers/alert/render.py` | `_onset_extent_suffix():624-649` (Langform `· Nass km 8-12, km 19-21`), `_sms_onset_extent_suffix():945-976` (Kurzform ` km8-12,19-21`) |

## Existing Patterns

- **Kommando-Handler:** `_show_now` holt Etappe (`get_stage_for_date`), loest die Position
  ueber `resolve_current_segment` + `position_at_time` auf, ruft **einen** Nowcast mit
  `priority="user_briefing"` und gibt `CommandResult(confirmation_body=...)` zurueck.
- **Kommando-Registrierung ist zweistufig:** Telegram-Reader validiert Slash-Kommandos gegen
  seine eigene Liste, der Prozessor gegen `_BARE_KEYWORD_MAP` (Freitext). Beide muessen
  gepflegt werden, sonst ist das Kommando nur ueber einen Weg erreichbar.
- **Argument-Muster:** `/ruhetag N`, `/pause 2d`, `/startdatum YYYY-MM-DD` — Parser liefert
  `(key, value)`, der Handler interpretiert `value` selbst.
- **Zonen-Text ist heute ausschliesslich inline** (ein Suffix im Satz), es gibt **keinen**
  Renderer, der Zonen als mehrzeilige Liste oder Tabelle ausgibt.
- **Fail-soft bei Folgepunkten** (S2a, `trip_alert.py:1763-1770`): faellt ein Zonenpunkt aus,
  laeuft der Hauptpfad weiter, nur `logger.warning`.

## Dependencies

- **Upstream:** `points_along_remaining_route()`, `derive_rain_zones()`,
  `RadarNowcastService.get_nowcast()`, `ForecastBudgetGate`, `RadarNowcastCacheService`
- **Downstream:** `CommandResult` → `send_command_reply_telegram()` /
  `send_command_reply_email()`; die Hilfe-Ausgabe `_show_help`

## Existing Specs

- `docs/specs/modules/feat_2051_s1_dauer_und_ende.md` (approved v1.1) — Ende/Dauer, sieben
  Textstellen inkl. **Kommando-Antwort**
- `docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md` (approved v1.0) — `RainZone`,
  `derive_rain_zones`, Mehrpunkt-Abruf im Alarm-Pfad; benennt `/strecke` als S4-Nicht-Ziel
- `docs/specs/modules/feat_2051_s2b_ausdehnung_kanaele.md` — Kanal-Kaskade der Zonen-Angabe;
  haelt fest: getrennte Zonen bleiben getrennt, Budget-Drop statt Anschnitt
- `docs/specs/modules/feat_2051_s3_reichweite_und_guete.md` (approved v1.1) —
  `source_reach_minutes`, `location_sharpness_limit_minutes`, Wortwahl `unscharf`

## Risks & Considerations

1. **Budget-Kollision mit dem Alarm-Pfad (hoch).** Kommando und Alarm zaehlen gegen dasselbe
   Tageskontingent (9000). `/jetzt` faehrt `user_briefing` = **nie** gedrosselt, der
   Alarm-Pfad `polling` = ab 80 % abgewiesen. Ein `/strecke` mit 6 ungedrosselten Abrufen
   koennte also genau das Kontingent verbrauchen, das die Alarme brauchen — auf der Tour die
   sicherheitsrelevantere Flaeche.
2. **`RainZone` traegt heute weder Intensitaet noch Quelle.** Das Ticket verlangt fuer die
   E-Mail-Fassung km-Spanne, **Zeitspanne, Intensitaet, Quelle**. Zwei der vier Groessen
   muessten additiv an der Zone entstehen.
3. **Kein Zonen-Listen-Renderer im Bestand** — Neubau, und er muss die Kanal-Kaskade des
   Tickets tragen (E-Mail-Tabelle / Telegram eine Zeile je Flaeche / Kurzform eine Zeile).
4. **Zwei Eingangskanaele, ein Kern.** Wer das Kommando im Prozessor registriert, macht es
   automatisch auch per E-Mail-Inbound erreichbar. Das ist erwuenscht (Kanalgleichrangigkeit),
   muss aber bewusst gebaut und geprueft werden, nicht als Nebenwirkung.
5. **Unvermessene Etappe.** Ohne GPX-Kilometrierung gibt es keine km-Zahlen (S2b-Regel
   `km_measured`). Die Antwort braucht einen ehrlichen Zweig dafuer.
6. **Keine Rechnung ueber den Nutzer** (PO-Grundprinzip des Tickets): keine Ankunftszeit,
   kein "bei Planzeit bist du um ... bei km ...". Die Planposition darf die *Reststrecke*
   bestimmen, nicht eine Aussage ueber den Nutzer erzeugen.
7. **Wiederholtes Abrufen** ist nicht begrenzt — der Telegram-Rate-Limit (18/60 s) bremst nur
   den Versand, nicht den Kommando-Eingang. Der 300-s-Nowcast-Cache daempft das teilweise.
