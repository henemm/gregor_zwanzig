# Mini-Spec: #1310 — Akut-Override sagt „jetzt akut"

**Issue:** #1310 (Akut-Override, Rest aus #883 Slice 4)
**Track:** Fast Track · **Erstellt:** 2026-08-07
**PO-Freigabe Wortlaut:** 2026-08-07 (Beleg als Issue-Kommentar)

## Ausgangslage (gemessen 2026-08-07, Stand `de3127b0`)

Der Sicherheits-Override selbst **ist gebaut** (`trip_alert.py:788-794`): konvektive Gefahr
durchbricht die Briefing-Unterdrückung. `tests/tdd/test_issue_883_acute_danger_override.py`
läuft 5 grün / 1 xfail — offen ist **allein AC-4**, das Wording.

Die Alarm-Mail führt seit #952 eine eigene Datenzeile „Briefing"
(`renderers/alert/render.py:235-236`). Sie kennt heute zwei Zustände
(`trip_alert.py:834`):

```
_briefing_context = "bereits angekündigt" if _briefing_announced else "nicht angekündigt"
```

Im Override-Fall — angekündigter Regen, der laut Radar konvektiv wird — steht dort
„bereits angekündigt". Das ist wahr, verschweigt aber die Zuspitzung, wegen der der Alarm
überhaupt gesendet wurde.

Der **Ortsvergleich ist nicht betroffen**: `compare_radar_alert.py` vergleicht nicht gegen
ein Briefing, `radar_alert_service.py:67` setzt `briefing_context=None`. Es gibt dort keinen
Override-Fall — also keine Teilungs-Lücke (Trip/Compare-Invariante geprüft).

## Was ändert sich

- `src/services/trip_alert.py:834` — dritter Zustand, wenn angekündigt **und** konvektiv:
  `"bereits angekündigt — jetzt akut"`
- `tests/tdd/test_issue_883_acute_danger_override.py:319` — `xfail`-Marker entfällt (AC-4 wird scharf)
- `docs/specs/_archive/modules/issue_883_acute_danger_override.md` → zurück nach
  `docs/specs/modules/`, Status auf `implemented`

## Was darf sich nicht ändern

- Die beiden bestehenden Zustände „bereits angekündigt" (angekündigt, nicht konvektiv —
  dieser Fall sendet ohnehin keinen Alarm) und „nicht angekündigt".
- Die Override-Logik selbst, der Doppel-Alarm-Schutz, Cooldown, Ruhezeiten, Kanal-Schwelle.
- Der Ortsvergleichs-Pfad (`briefing_context` bleibt dort `None`).
- Kein Renderer wird angefasst — die Zeile wird bereits generisch gerendert.

## Acceptance Criteria

- **AC-1:** Given ein Briefing hat Regen für die Onset-Stunde angekündigt und der Radar meldet
  konvektive Gefahr / When der Radar-Alarm gebaut wird / Then enthält die Nachricht „jetzt akut"
  und **nicht** „nicht angekündigt".

- **AC-2:** Given der Radar meldet konvektiven Regen, den das Briefing **nicht** angekündigt hat
  / When der Alarm gebaut wird / Then steht dort unverändert „nicht angekündigt" und **kein**
  „jetzt akut".

- **AC-3:** Given jemand entfernt die Fallunterscheidung später wieder
  / When `tests/tdd/test_issue_883_acute_danger_override.py` läuft
  / Then schlägt AC-4 fehl (kein `xfail` mehr, der das verdeckt).

## Manuelle Test-Schritte

1. Auf Staging den ausgelieferten Code mit gesteuerten Radar-Frames ausführen
   (konvektiv + Briefing-Regen) — die abgefangene Mail enthält „bereits angekündigt — jetzt akut".
2. Gegenprobe ohne Briefing-Regen: „nicht angekündigt", kein „jetzt akut".

## Inline-Test

- [x] `tests/tdd/test_issue_883_acute_danger_override.py::test_ac4_override_mail_wording_not_unannounced`
      (bestehender Test, `xfail` fällt)
- [ ] Gegenprobe für AC-2 (nicht angekündigt → kein „jetzt akut")
