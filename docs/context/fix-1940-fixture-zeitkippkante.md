# Context: fix-1940-fixture-zeitkippkante

Issue: #1940 — CI-Job `test` schlaegt taeglich 12:00–13:30 UTC fehl (Zeitkippkante in
`arrival_window_fixtures`). Track: Standard.

## Request Summary

Der gemeinsame Test-Hilfsbaustein `tests/helpers/arrival_window_fixtures.py` verschiebt ein
Ankunftsfenster still nach vorne, wenn der lokale Etappentag noch nicht weit genug
fortgeschritten ist. Dadurch liegt ein Wegpunkt, den der Aufrufer ausdruecklich in die
Vergangenheit gelegt hat, in Wahrheit in der Zukunft — die zugesicherte Segment-Konstellation
kippt und die CI-Ampel wird taeglich rot, unabhaengig vom PR-Inhalt.

## Der Mechanismus, nachgerechnet (nicht vermutet)

`fenster_minuten(minuten_jetzt, *offsets_min)` (`tests/helpers/arrival_window_fixtures.py:99`)
schiebt bei `roh[0] < 0` das GANZE Fenster nach vorne (`verschiebung = max(0, -roh[0])`,
Zeile 144). Die Verschiebung erhaelt die Abstaende, aber **nicht das Vorzeichen** der
gewuenschten Versaetze.

Gemessen ueber alle 1440 Ortsminuten je Offset-Familie — Kriterium: „jeder negativ gewuenschte
Wegpunkt muss bei/vor *jetzt* liegen":

| Offset-Familie | Aufrufer | kaputte Ortsminuten | UTC-Fenster |
|---|---|---|---|
| `(-120, -30, 90)` | `test_issue_822_...py:406` (AC-3, Neuseeland UTC+12) | 90 (0–89) | **12:00–13:30** |
| `(-120, -60, 60)` | `test_issue_822_...py:260` (AC-2, London UTC+1) | 60 (0–59) | **23:00–00:00** |
| `(-240, -120, 120)` | `test_issue_822_...py:194` (AC-1, Tirol UTC+2) | 120 (0–119) | 22:00–00:00 (latent) |
| `(-60, 120)` · `(-60, 180)` · `(-60, 60)` | die uebrigen 12 Dateien | **0** | — |

Belegt am Prueflingscode selbst:

```
jetzt=  30 -> wp=(0, 90, 210)  seg1_aktiv=True   <- falsch, seg1 sollte vorbei sein
jetzt=  90 -> wp=(0, 90, 210)  seg1_aktiv=False  <- richtig
```

**Zwei Befunde ueber das Ticket hinaus:**

1. Das Ticket nennt nur AC-3 (12:00–13:30 UTC). **AC-2 traegt dieselbe Ursache und bricht
   taeglich 23:00–00:00 UTC** — bisher nicht zugeordnet. Der Umzug der AC-3-Koordinaten nach
   Neuseeland (#1667 S1) hat AC-2 in London stehen lassen; dort ist die Zusicherung nie
   robust gewesen.
2. AC-1 verliert die Konstellation ebenfalls (22:00–00:00 UTC), **faellt aber nicht auf**,
   weil der Test nur Bit-Identitaet und Monotonie prueft, nicht die Vergangenheit des ersten
   Segments. Latenter Fall derselben Klasse.

## Related Files

| Datei | Relevanz |
|---|---|
| `tests/helpers/arrival_window_fixtures.py` | Prüfling: `fenster_minuten` (Z. 99–153), `active_window_offsets` (Z. 176), `past_window_offsets` (Z. 220), `stage_date` (Z. 156) |
| `tests/unit/test_arrival_window_fixtures.py` | Waechter des Bausteins, 11 Testfunktionen; iteriert `ALLE_MINUTEN = range(-1440, 2880)` (Z. 86) ueber `FAMILIEN` (Z. 64) |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | Einzige Datei mit „erstes Segment muss vorbei sein"-Bedarf: AC-1 (Z. 194), AC-2 (Z. 260), AC-3 (Z. 406) |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | Ratsche gegen Wanduhr-Fixtures — **rein statischer AST-Scanner**, prueft kein Laufzeitverhalten |

## Dependents — vollstaendig ausgezaehlt

14 Testdateien importieren aus dem Baustein. Nur **drei Aufrufstellen** (alle in
`test_issue_822_radar_nowcast_segment.py`) verlangen ein bereits vergangenes erstes Segment;
die uebrigen brauchen lediglich „ein Segment ist jetzt aktiv" und sind von der Verschiebung
nachweislich nicht betroffen (0 kaputte Minuten). Der Aenderungsdruck ist damit eng begrenzt.

Fan-out innerhalb der Dateien beachten: `_trip()` in
`test_briefing_anchor_survives_dispatch_failure.py` wird 37× aus 25 Testfunktionen gerufen,
`_radar_trip()` in `test_alert_channel_premium_sms.py` 6× aus 10 — eine Verhaltensaenderung
des Bausteins schlaegt dort breit durch, auch wenn die Offsets harmlos sind.

## Existing Patterns

- `past_window_offsets` (Z. 220–277) macht bereits genau das Richtige: reicht der Platz auf
  dem Etappentag nicht, **scheitert es laut** mit `ValueError` (Z. 256) statt still ein
  Fenster zu liefern, das die Zusicherung nicht traegt. Die geforderte Haltung existiert im
  selben Modul — nur `fenster_minuten` folgt ihr nicht.
- Der Docstring von `active_window_offsets` (Z. 189–199) warnt bereits schriftlich: „Das
  Vorzeichen eines Versatzes ist keine Zusicherung." Eine Warnung im Text ist kein Waechter.
- `freezegun` ist im Waechter-Test bereits im Einsatz (`test_arrival_window_fixtures.py:47`,
  Randzeit-Faelle Z. 323/352) — eine gestellte Uhr ist in diesem Bereich etabliertes Mittel.

## Risks & Considerations

- **Der Waechter selbst wird rot.** `test_arrival_window_fixtures.py` Z. 91/111/129 rufen
  `fenster_minuten` ueber `range(-1440, 2880)` × `FAMILIEN` ohne `try/except` auf. Faellt der
  Baustein kuenftig laut aus, muessen diese drei Tests auf den neuen Vertrag umgestellt
  werden — sonst blockiert die eigene Ratsche den Fix.
- **Domaene ausserhalb 0–1439.** `minuten_jetzt` ist im echten Betrieb immer 0–1439
  (`_tagesbezug`, Z. 208). Der Waechter prueft absichtlich weit darueber hinaus; der neue
  Vertrag muss fuer diesen erweiterten Bereich definiert sein, nicht nur fuer den realen.
- **Trivial-gruen-Falle.** Ein lautes Scheitern allein macht die beiden Tests nicht gruen —
  es tauscht nur „falsch rot" gegen „laut rot". Ohne eine zweite Massnahme, die die
  Konstellation zu jeder Uhrzeit herstellbar macht, bleibt die Ampel taeglich rot.
- **Positivkontrolle ist Pflicht** (Ticket ausdruecklich): ein Test muss beweisen, dass die
  Konstellation ausserhalb des Bruchfensters tatsaechlich hergestellt wird. Sonst bewacht der
  neue Waechter die leere Menge.
- **Kein Produktivcode betroffen.** `src/services/trip_segments.py` verhaelt sich korrekt —
  die Fehlermeldung des CI-Laufs belegt das (gewaehlte Koordinaten = `WP0`, also Segment-1,
  zutreffend gewaehlt). Reine Test-Infrastruktur.
- **Die Ratsche stoert nicht.** `test_fixture_wallclock_ratchet.py` scannt nur Quelltextmuster
  (`KNOWN_VIOLATIONS_INDIREKT` ist erzwungen leer, Z. 1261) und reagiert nicht auf
  Verhaltensaenderungen des Bausteins. Keine Ausnahmeliste zu pflegen.

## Loesungsrichtung (Analyse, noch nicht freigegeben)

Zwei Massnahmen, die zusammengehoeren:

1. **Waechter:** `fenster_minuten` liefert kein Fenster mehr, in dem ein negativ gewuenschter
   Wegpunkt nach *jetzt* landet — es scheitert laut, wie `past_window_offsets` es bereits tut.
   Das schliesst die **Klasse**, nicht nur den einen Fall.
2. **Reparatur:** Die drei Aufrufstellen mit „vergangenes erstes Segment"-Bedarf bekommen eine
   gestellte Uhr auf eine sichere Ortszeit (Tagesmitte), damit die Konstellation zu jeder
   Wanduhrzeit darstellbar ist. Danach ist der laute Fehler aus (1) nie erreichbar — er
   bewacht kuenftige Aufrufer.

Alternative aus dem Ticket (Etappentag auf „morgen" legen) scheidet aus: der Produktivpfad
sucht die Etappe ueber `trip_local_today` (Ortstag), eine Etappe am Folgetag wuerde gar nicht
gefunden.
