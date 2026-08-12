# ADR-0044: „Heute" und „morgen" bestimmen sich nach der Ortszeit der Tour, nicht nach Weltzeit

- **Status:** Akzeptiert (PO-Entscheidung 2026-08-03)
- **Datum:** 2026-08-03
- **Bezug:** Issue #1470, Issue #1465 (Ursprung), ADR-0035 (Tagesfenster als Zeitraum — ergänzt, nicht abgelöst), Issue #1345 (Hausnorm naive UTC), Issue #1402 (Ortszeit im `/jetzt`-Pfad), Spec `docs/specs/modules/fix_1470_drilldown_ortszeit.md`

## Kontext

Das Produkt beantwortet an mehreren Stellen die Frage „welcher Tag ist gemeint" — im
Telegram-Drilldown („Stunden heute", „Gewitter morgen"), bei den Befehlen `/heute` und
`/morgen`, beim Ruhetag-Vermerk, in der Statusanzeige.

Historisch wurde dieser Tag aus dem Zeitstempel der eingehenden Nachricht abgeleitet
(`msg.received_at.date()`) — und der trägt immer **UTC**. Auf Korsika begann „morgen"
damit um 02:00 Ortszeit: Die ersten zwei Stunden des Tages fehlten, die letzten zwei des
Vortages waren dabei. Kurz nach Ortsmitternacht meldete „heute" den Vortag. Bei einer Tour
in Neuseeland wären es zwölf Stunden Versatz gewesen.

Gefunden wurde das als Nebenbefund von #1465. Solange der Drilldown abstürzte, kam
niemand bis zu dieser Frage.

Die Sache ist **keine Fehlerbehebung, sondern eine Produktentscheidung**: Welche
24 Stunden „morgen" sind, muss jemand festlegen. Sie wurde dem PO ausdrücklich vorgelegt.

## Entscheidung

> **Kalendertage — „heute", „morgen" — bestimmen sich nach der Ortszeit der Tour.**

Die Zone wird aus den Koordinaten des Wegpunkts aufgelöst, mit dreistufigem Rückfall:
Etappe des Weltzeit-Tages → erste Etappe mit Wegpunkten → importierte UTC-Konstante.

**Abgrenzung zu ADR-0035:** Jenes ADR regelt das Tagesfenster als **Zeitraum** („welche
Stunden zählen für die Bewertung"). Dieses hier regelt den **Kalendertag** („welcher Tag
ist gemeint"). Beide gelten nebeneinander.

**Nicht betroffen: Dauern.** „Die nächsten zwölf Stunden" ist eine Dauer ab jetzt, keine
Kalendertagsgrenze — sie wird in UTC addiert und bleibt es. Sie an der Ortsmitternacht zu
kappen würde die Vorschau kurz vor Mitternacht still auf Minuten schrumpfen lassen.

**Nicht betroffen: die Hausnorm aus #1345.** Wetterdaten tragen weiterhin zeitzonenlose
UTC-Zeitstempel. Die Ortszeit entsteht erst bei der Auswertung „welcher Tag" und bei der
Beschriftung — nicht in den Daten.

## Konsequenzen

**Ein Ortstag hat nicht immer 24 Stunden.** An den Umstellungstagen sind es 23 oder 25, in
Zonen mit halbstündigem Wechsel (Lord Howe Island) auch 23,5. Jedes Tagesfenster muss
seine Länge **berechnen** statt sie zu setzen. Eine Signatur mit `hours: int` ist damit
falsch.

**Wer eine Bezugsgröße von Weltzeit auf Ortszeit umstellt, holt sich die Sommerzeit-Frage
neu ins Haus.** Vorher war die Rechnung umstellungs-immun. Bei #1470 wäre der Fehler
**erst durch die Verbesserung** entstanden — er wurde nur gefunden, weil der Prüfer
ausdrücklich danach gesucht hat. **Immer beide Wechseltage testen**, und zwar auf die
Häufigkeit *jeder einzelnen Stunde*, nicht auf die Zeilenzahl.

**Die Falle beim Rechnen** (bei #1470 gemessen, bevor gebaut wurde):

```
2026-03-29: gleiche tzinfo-Subtraktion=24.0  über UTC=23.0
2026-10-25: gleiche tzinfo-Subtraktion=24.0  über UTC=25.0
```

Tragen zwei zeitzonenbehaftete Zeitpunkte **dasselbe `tzinfo`-Objekt**, rechnet Python auf
den nackten Wanduhr-Werten und ignoriert den Offset-Wechsel — an jedem Tag 24,0. Beide
Zeitpunkte müssen **erst nach UTC umgerechnet** werden, im Projekt über `local_dt(dt, UTC)`
(nicht `dt.astimezone(UTC)` — der Zeitzonen-Wächter flaggt rohes `.astimezone`).

**Bei Touren über mehrere Zeitzonen bleibt ein Rest.** Wechselt der Wanderer an genau
diesem Tag die Zone, kann die Etappe des Weltzeit-Tages eine andere Zone tragen als die des
Ortstages. Der Fehler ist dann die Differenz zweier benachbarter Etappen — in aller Regel
null. Eine Tour dieser Spannweite hat ohnehin keinen eindeutigen „Kalendertag".

### Wo die Zonen-Auflösung liegt (Stand 2026-08-12, Issue #1697, #1724)

Die drei Bausteine waren ursprünglich **private Methoden** auf `TripCommandProcessor`. Seit
#1697 liegen sie als Modulfunktionen in **`src/services/trip_day.py`** und werden von dort
geteilt; #1724 hat `trip_local_now` ergänzt:

| Funktion | Aufgabe |
|---|---|
| `trip_tz(trip)` | Rückfall 2: erste Etappe mit Wegpunkten |
| `display_tz(trip, day_date)` | Zone der Etappe dieses Tages, sonst `trip_tz` |
| `anchor_tz(trip, now_utc)` | Auflösung der Henne-Ei-Falle: Zone der Etappe des **Weltzeit**-Tages |
| `trip_local_now(trip, now_utc)` | Ortstag UND Ortsstunde der Tour aus EINER Zonen-Auflösung |
| `trip_local_today(trip, now_utc)` | **der Ortstag der Tour** — das, was `date.today()` ersetzt; dünne Sicht auf `trip_local_now` |

Wer nur den Kalendertag braucht, ruft `trip_local_today()`; wer zusätzlich die Ortsstunde
braucht — etwa eine Fälligkeitsprüfung wie in #1725 —, ruft `trip_local_now()` direkt, damit
Tag und Stunde aus derselben Auflösung kommen. Eine eigene Kopie der Zonen-Auflösung ist ein
Regelverstoß — genau das war der Zustand vor #1697.

### Umgesetzt

- **Drilldown** (#1470) — der ursprüngliche Anlass dieses ADR.
- **Alarm-Pfad** (#1697, live 2026-08-11): `src/services/trip_alert.py` an allen drei
  Stellen, die einen Kalendertag bestimmen (`:404` Ablauf-Filter, `:584` Schnappschuss-
  Anker, `:911` Segmentwahl). Dieser Pfad stand in der Restliste unten **nie drin** und war
  trotzdem der schwerwiegendste Verstoß: nicht eine falsche Anzeige, sondern **ausbleibende
  Alarme**. Gemessen für eine gewöhnliche Etappe 08:00–19:00 Ortszeit — Neuseeland verlor
  die ersten ~4 von 11 Stunden *jedes* Etappentags, Kalifornien die letzten ~2, Mitteleuropa
  zwei Stunden jede Nacht.
  **Hinweis, kein neuer Haken (Issue #1667 S3, live 2026-08-11):** Die Segmentwahl (`:911`)
  ruft seither `trip_segments.py::resolve_current_segment()` und fällt additiv auf das
  Ziel-Segment des unmittelbaren Vortags zurück, wenn heute nichts aktiv ist. Das ändert
  **nicht** die Zonen-Auflösung dieses ADR — `today`/`gestern` bleiben beide über
  `trip_local_today()` bestimmt —, sondern nur die Tages-**Tiefe** der Suche (ein Tag
  zusätzlich statt nur der eine bereits aufgelöste Ortstag). Details:
  `docs/specs/modules/fix_1667_s3_tagesuebergreifende_segmente.md`.
- **Briefing-/Versand-Pfad** (#1724, live 2026-08-11; Fälligkeitsfenster + Idempotenz #1725,
  live 2026-08-12): `_get_target_date` und `_get_active_trips` in
  `src/services/trip_report_scheduler.py` bestimmen den Zieltag jetzt über `trip_local_today`
  statt `date.today()`; `save_dated`/`load_dated` schreiben und lesen denselben
  Ortstag-Schlüssel, Schreiber und Leser sind also zusammen umgestellt. #1725 löst zusätzlich
  die in ADR-0051 beschriebene Stundengleichheits-Falle: Fälligkeit ist jetzt ein Fenster von
  drei Ortsstunden ab der konfigurierten Stunde, gegen Doppelversand abgesichert über den
  Vermerk-Speicher `services/briefing_slots.py` (Schlüssel `(trip_id, ortstag, slot)`).

**Lehre für die Pflege dieser Liste:** Sie war nicht falsch, sondern **unvollständig** — und
eine unvollständige Restliste liest sich wie eine vollständige. Wer hier etwas einträgt,
sucht vorher nach `date.today()`/`datetime.now().date()` im ganzen Produktivcode, statt nur
die Datei zu nennen, in der er gerade gearbeitet hat.

### Noch nicht umgesetzt (Stand 2026-08-12)

Der zuvor hier gelistete Briefing-/Versand-Pfad (`_get_target_date`, `_get_active_trips`,
`save_dated`) ist umgesetzt — s. „Umgesetzt" oben (#1724/#1725).

**Anzeige, Vorschau, Werkzeuge:** vier Stellen in `src/services/trip_command_processor.py`
(`_handle_query` — **löst einen Versand aus**, nicht nur eine Anzeige, eigene Abwägung nötig;
`command_date` für `### ruhetag`; `_show_status` und `_show_now`), dazu
`inbound_telegram_reader.py`, `preview_service.py`, `api/routers/debug.py` und
`tools/weather_validation.py`. Zeilennummern bewusst weggelassen — sie waren in der
Vorfassung dieser Liste binnen Tagen veraltet.

**Bewusst NICHT betroffen** (feste Zone ist dort Absicht, kein Verstoß):
`forecast_budget._today_utc` und `meteoalarm_budget._today_utc` (Kontingent-Tageswechsel in
UTC), `alert_daily_limit` und `deviation_alert_engine` (fest `Europe/Vienna`),
Slot-Stunde im Versand-Orchestrator.

Vollständige Fundstellen-Karte nach Wirkung sortiert:
`docs/context/fix-1697-ortstag-statt-servertag.md`.

Sie sind bewusst ausgegrenzt, nicht vergessen. Wer sie anfasst, richtet sich nach diesem ADR.

## Alternativen, die verworfen wurden

**Alles bei Weltzeit lassen.** Konsistent und sommerzeit-immun — aber für den Nutzer
falsch: Wer um 00:30 Ortszeit „heute" fragt, meint seinen Tag, nicht den in Greenwich.

**Die Zone aus der ersten Etappe der Tour nehmen.** War die erste Fassung von #1470. Bei
einer Tour Neuseeland → Korsika zehn Stunden daneben; die Etappe des Weltzeit-Tages liegt
höchstens einen Tag daneben und trifft praktisch immer die richtige.

**Die Zone aus der Nutzer-Einstellung nehmen.** Es gibt keine solche Einstellung, und sie
wäre falsch: Der Wanderer ist unterwegs, nicht zu Hause.
