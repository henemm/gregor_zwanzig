# ADR-0096: Der Radar-/Onset-Alarm ist ein eigener Alarm-Typ mit absoluter Auslösung, eine Ausnahme zu ADR-0009

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — gelebter Stand seit #656, fortgeschrieben #883/#2009/#2020/#2261)
- **Datum:** 2026-10-21
- **Bezug:**
  - Issue #656 (Commit `c54fce8f7`, 2026-06-07, „proaktive Radar-Alerts"), Issue #883 (Commit `a7efb0aa1`, Sicherheits-Override), Issue #2009, Issue #2020, Issue #2261 Teil A
  - Specs: `docs/specs/modules/radar_nowcast.md`, `fix_2009_nowcast_vorlauf.md`, `feat_2261_a1_radar_vorlauf.md`
  - Code: `src/services/radar_service.py`, `src/services/trip_alert.py`, `src/services/compare_radar_alert.py`, `src/services/alert_urgency.py`
  - Bezug zu ADR-0009 (Ausnahme zu 0009:49), ADR-0021 (geteilter Code), ADR-0046/ADR-0095 (Kanäle), ADR-0082 (Takt/Budget)

## Kontext

ADR-0009 (2026-06-16) legt fest, dass Alarme **Abweichungs-Wächter** sind und keine absoluten
Schwellen haben. Die Folgepflicht 0009:49 sagt: „Neue Alert-Funktionen müssen am
Abweichungs-Modell andocken …, nicht absolute Schwellen einführen."

Der Radar-Alarm passt nicht in dieses Schema, und er ist älter als ADR-0009. Er kam mit #656 am
2026-06-07, neun Tage vor ADR-0009. Er meldet bevorstehenden Niederschlag aus dem
Radar-Nowcast. Ausgelöst wird er nicht durch eine Abweichung vom Briefing-Snapshot, sondern durch
einen **absoluten** Zustand: Laut Radar beginnt am Messort Niederschlag, oder es regnet dort
schon. ADR-0009 erwähnt ihn nicht, und kein ADR hält die Ausnahme fest (Doku-Audit 2026-10,
Punkt 1e).

Der Unterschied zum 2026-08-03 abgelösten Schwellen-Alarm (ADR-0040 → ADR-0043) ist dieser: Der
Radar-Alarm hat **keine nutzerkonfigurierte Wertgrenze**. Er ist ein eingebauter Kurzfrist-Wächter
auf einer Datenquelle, die das Briefing nicht hat. Ein Radar-Nowcast reicht nur 3 Stunden voraus.
Ein Snapshot-Vergleich ergibt dafür keinen sinnvollen Bezugspunkt.

## Entscheidung

1. **Der Radar-/Onset-Alarm ist ein eigener Alarm-Typ neben dem Abweichungs-Wächter.** Er hat
   eigene Jobs im 5-Minuten-Takt (ADR-0082). Trip und Ortsvergleich teilen ihn: `radar_alert_due()`
   (`trip_alert.py:227`) wird aus `trip_alert.py:307/:2497` und aus `compare_radar_alert.py`
   aufgerufen (ADR-0021).
2. **Auslösung ist absolut.**
   - Beginn heißt: der erste Radar-Frame mit `precip_mm_h >= _DRY_THRESHOLD_MM_H`, das sind
     0,1 mm/h (`radar_service.py:135`, `:1132-1134`).
   - Der Alarm ist fällig, wenn `onset_minutes <= RADAR_ONSET_THRESHOLD_MIN` gilt oder das
     Ereignis bereits läuft (`radar_alert_due()`, `trip_alert.py:235-238`, laufend seit #2050 S2b).
3. **Die Vorlauf-Schwelle ist der Quell-Horizont.** `RADAR_ONSET_THRESHOLD_MIN = NOWCAST_HORIZON_MIN`,
   also 180 Minuten (`radar_service.py:80`, `:129`).
   - Das folgt aus dem PO-Entscheid A-1 vom 2026-08-21: „so früh wie möglich", keine künstliche
     Untergrenze (`feat_2261_a1_radar_vorlauf.md`).
   - Damit ist der frühere Wert 55 aus `fix_2009_nowcast_vorlauf.md` abgelöst. Weiter gilt dessen
     Drift-Schutz: eine einzige Konstante, gelesen über die Modul-Referenz.
   - Die Ortsschärfe jenseits von 60 Minuten wird nicht durch Schweigen behandelt. Sie erscheint
     als Gütekennzeichnung (`LOCATION_SHARPNESS_LIMIT_MIN = 60`, #2051 S3).
4. **Δ-Elemente bleiben im Trip-Pfad dort, wo das Briefing den Regen schon angekündigt hat.**
   Der Ortsvergleich-Radarpfad kennt diese Prüfung nicht und löst rein absolut aus
   (`compare_radar_alert.py:335`, `:430`).
   - Steht im Trip-Briefing für das Fenster schon Niederschlag (≥ 0,5 mm), wird nicht-konvektiver Regen
     unterdrückt (`trip_alert.py:2530`, `:2575-2577`).
   - Ausnahme 1, Sicherheits-Override (#883): Eine **durchgeführte** Gewitterprüfung meldet
     konvektive Gefahr (Gewitter/Hagel). Seit #2050 S4a zählt nur eine Prüfung, die
     stattgefunden hat.
   - Ausnahme 2, Überholung (#2020): Die Radar-Menge erreicht mindestens 2,0 × die angekündigte
     Menge **und** mindestens 2,0 mm. Die Menge muss außerdem vergleichbar sein, also einen Beginn
     unter 60 Minuten haben (`_BRIEFING_OVERTAKE_FACTOR`, `_OVERTAKE_MIN_ABSOLUTE_MM`,
     `trip_alert.py:108/:119/:2561-2566`).
   - Eine laufende Sperrzeit wird nur nach demselben Muster überholt
     (`alert_gate.radar_overtakes_cooldown()`, `alert_gate.py:436`).
5. **Die Dringlichkeit folgt dem Radarbild, nicht einer Δ-Größe.** Konvektiv oder stark heißt
   `HIGH`, mäßig heißt `MODERATE`, sonst `LOW` (`alert_urgency.urgency_from_radar()`,
   `alert_urgency.py:52`). Der Wert speist die Kanal-Schwelle (ADR-0046/ADR-0095). Der Radar-Alarm
   erreicht alle vier Kanäle über die geteilte Auflösung (#1752, #1701).
6. **ADR-0009 bleibt der Grundsatz für alle anderen Alarme.** Diese Ausnahme gilt nur für den
   Radar-/Onset-Alarm. Sie ist kein Präzedenzfall für neue absolute Schwellen auf
   Vorhersage-Daten.

## Verworfene Alternativen

- **Radar-Alarm in das Abweichungs-Modell zwingen, also Nowcast gegen Briefing-Snapshot:** Das
  wurde nur teilweise umgesetzt (Punkt 4). Ein reiner Δ-Vergleich würde bei Regen ohne
  Briefing-Ankündigung nie den Beginn melden, und genau das ist die Kernaussage des Alarms.
- **Feste Vorlauf-Untergrenze (20 bzw. 55 Minuten):** verworfen durch PO-Entscheid A-1
  (2026-08-21) und abgelöst durch `feat_2261_a1_radar_vorlauf.md`. Die Untergrenze führte zu
  einem praktisch konstanten Vorlauf von „8 Min" (#2009) und verschenkte die Reichweite der Quelle.
- **Nutzerkonfigurierte Radar-Wertgrenze:** nicht gebaut. Das wäre der von ADR-0043 abgelöste
  zweite Regler. Einziger Nutzer-Regler auf dem Weg ist die Kanal-Schwelle.

## Konsequenzen

- **Positiv:**
  - Der Wanderer erfährt bevorstehenden Regen und Gewitter auch dann, wenn das Briefing nichts
    angekündigt hat.
  - ADR-0009 bleibt für die Vorhersage-Alarme unverwässert.
- **Negativ / Preis:**
  - Zwei Auslöse-Logiken leben nebeneinander: Δ für Vorhersage-Alarme, absolut plus
    Briefing-Abgleich für den Radar-Alarm.
  - Die Unterdrückungs- und Überholungsregeln (Punkt 4) sind Sonderlogik im Trip-Radarpfad.
  - Der Ortsvergleich hat kein Pendant dazu, weil dort keine Briefing-Ankündigung geprüft wird.
    Ob das eine Paritätslücke ist, ist hier nicht entschieden.
- **Folgepflichten:**
  - Schwellen und Faktoren bleiben benannte Konstanten, die über die Modul-Referenz gelesen werden
    (Drift-Schutz #2009 AC-1).
  - Ein weiterer absoluter Alarm-Typ braucht ein eigenes ADR. Er kann sich nicht auf dieses
    berufen.
