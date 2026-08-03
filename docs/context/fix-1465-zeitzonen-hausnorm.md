# Kontext: #1465 — 15 Tests prüfen veraltetes Zeitzonen-Verhalten

Stand 2026-08-03, HEAD `9305456e`. **Reine Testpflege nach einer dokumentierten Norm.**
Kein Produktfehler, kein Nutzer betroffen — die ursprüngliche Ticket-Diagnose ist widerlegt
(s. Korrektur-Kommentar in #1465).

## Die Norm

`src/app/models.py:151-158`, `ForecastDataPoint.__post_init__`:

```python
# Issue #1345: Hausnorm "naive UTC" an der Provider-Grenze erzwingen —
# aware Zeitstempel (z.B. von GeoSphere) werden nach UTC konvertiert
# und dann auf naiv gestrippt, damit `ts` provider-uebergreifend
# konsistent mit naiv/UTC-Vergleichen (z.B. segment_weather.py) bleibt.
if self.ts.tzinfo is not None:
    object.__setattr__(self, "ts", self.ts.astimezone(timezone.utc).replace(tzinfo=None))
```

**Das Produkt verhält sich korrekt.** Gemessen: Die Testvorlage erzeugt ihre Punkte mit
`tzinfo=timezone.utc` (`tests/tdd/test_weather_extractor.py:41`), und bereits **vor** dem
Speichern trägt das entstandene `ForecastDataPoint` einen naiven Zeitstempel. Die Norm
greift an der Grenze, nicht erst beim Speichern oder Laden.

## Warum die Tests rot sind

`tests/tdd/test_weather_extractor.py` und sein Prüfling stammen **beide** aus
`4a389c70` (#652, 2026-06-07) und wurden seither von **keinem** Commit angefasst. Die
Hausnorm aus #1345 kam später und hat sie nicht mitgezogen.

Der Fehler entsteht **im Test**, nicht im Prüfling — die ursprünglich vermutete Stelle
`weather_extractor.py:133` wirft nichts:

```
tests/tdd/test_weather_extractor.py:196
    assert result.points[-1].ts < datetime(2026, 2, 14, 13, 0, tzinfo=timezone.utc)
TypeError: can't compare offset-naive and offset-aware datetimes
```

Zwei Fehlerbilder aus derselben Ursache: `<` wirft `TypeError`, `==` liefert stillschweigend
`False` (AssertionError).

## Umfang — 15 Tests in 5 Dateien

| Datei | rot |
|---|---|
| `tests/tdd/test_weather_extractor.py` | 2 |
| `tests/tdd/test_command_reply_channel_emoji.py` | 5 |
| `tests/tdd/test_issue_654_telegram_thunder_drilldown.py` | 4 |
| `tests/tdd/test_issue_667_snapshot_hourly_clip_fix.py` | 1 |
| `tests/tdd/test_issue_704_telegram_interactive_navigation.py` | 3 |

Alle hängen am selben Extraktor und derselben Vorlage.

## Auflagen für die Sanierung

1. **Nicht per Suchen-und-Ersetzen.** Bei jedem Fall prüfen, ob außer der Zeitzone noch
   etwas anderes nicht mehr stimmt — sonst zieht man einen zweiten Fehler mit grün.
2. **Die Norm im Test benennen**, nicht nur die Erwartung ändern: ein Verweis auf #1345
   an der Vorlage, damit der nächste nicht wieder rätselt.
3. **Gegenprobe.** Nach der Sanierung eine Erwartung verfälschen ⇒ Test muss rot werden.
   Sonst ist „grün" nur Abwesenheit von Prüfung.

## Warum die Fehldiagnose zweimal passiert ist

Bei **#1449** derselbe Fall: „möglicher Datenverlust" vermutet, tatsächlich eine Vorlage,
die Werte behauptete, die der Prüfling gar nicht liest.

**Muster:** Ein roter Test mit Zeitangabe oder Zahlenvergleich *sieht aus* wie ein
Produktfehler. Erst messen, ob die Eingabe beim Prüfling ankommt **und in welcher Form** —
dann steht die Lesart fest. Zwei Minuten Messen sparen ein falsch zugeschnittenes Ticket.
