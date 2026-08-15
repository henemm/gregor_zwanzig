# Critical Lessons — dauerhafte Regeln ohne anderen Wächter

> Angelegt 2026-07-22 (Issue #1344, Marker-Sweep über das Spec-Archiv).
> Zweck: Regeln, die weder ein Test noch ein Hook noch CLAUDE.md/ADR absichert,
> aber dauerhaft gelten. Jeder Eintrag nennt die Quelle. Wenn eine Regel später
> mechanisch abgesichert wird (Test/Hook), den Eintrag hierher entfernen und am
> Wächter referenzieren — diese Datei soll klein bleiben.

## Visuelle Pixel-Diff-Tests: Schwellen nie anheben

Bei einem roten Pixel-Diff-Test (Design-Fidelity, `design_fidelity_diff.py`,
`SCREEN_THRESHOLD_MAP`) darf die Schwelle NIEMALS angehoben werden, um den Test
grün zu bekommen. Reihenfolge: erst das Diff-Bild ansehen, Ursache verstehen,
dann Design fixen (oder — nur bei bewusster Design-Änderung mit PO-go — die
Referenz aktualisieren). Threshold-Overrides sind temporär und werden wieder
gesenkt.
Quelle: `docs/specs/_archive/modules/issue_956_email_format.md` (§Known
Limitations); verwandt: CLAUDE.md Test-Politik (Schwellen-Manipulation-Verbot).

## Import-Richtung: `comparison_engine.py` importiert nie aus `user.py`-Konsumenten

`src/app/user.py` (bzw. dessen Lookup-Helfer) darf aus
`src/services/comparison_engine.py` heraus NICHT importiert werden — die
Import-Richtung bleibt Engine ← Aufrufer, sonst entsteht ein Zyklus über die
Official-Alerts-Kette. Kein `architecture_guard`-Wächter vorhanden; Regel gilt
per Konvention.
Quelle: `docs/specs/_archive/modules/issue_1034_official_alerts_foundation.md` (§189).

## Alarm-Tests: die Vorbedingung „kein Briefing fällig" gehört in die Fixture

Ein Test, der zusichert „Alarm wird zugestellt", muss den Trip so bauen, dass
**kein geplantes Briefing fällig ist** — sonst greift die Vorlaufsperre aus
#1594 (`src/services/trip_alert.py:241` → `src/services/alert_gate.py:200` →
`trip_briefing_due_at`), der Alarm wird planmäßig durch das Briefing **ersetzt**
(ADR-0009), und der Test scheitert an einer nirgends ausgesprochenen Annahme.
Weil die Vorgabezeiten 07:00/18:00 Ortszeit bei drei Stunden Fälligkeitsfenster
gelten, hängt das Ergebnis sonst an der Wanduhr: rot von 07–10 und 18–21 Uhr
Ortszeit, grün dazwischen.

Praktisch: `report_config.enabled = False` setzen (wird produktiv nur in
`trip_report_scheduler.py:171` und `:891` gelesen, beide im Briefing-Pfad, nie
im Alarmpfad). **Vor jeder solchen „Aus"-Flagge zählen, wo sie gelesen wird** —
sonst macht der Fix den Test grün, indem er ihn entkernt.

Gegenprobe, die etwas taugt: die Bedingung **herstellen** statt abwarten — eine
Variante mit fälligem Briefing (Briefingzeit aus der *aktuellen* Ortsstunde
abgeleitet) darf keinen Alarm liefern, die neutralisierte muss einen liefern.
Beide Varianten brauchen die aktuelle Ortsstunde; setzt nur eine sie, wacht die
Zusicherung nur drei von 24 Stunden.

Kein Wächter vorhanden: eine Verhaltensänderung im Alarmpfad kann bestehende
Alarm-Tests kippen, und die CI-Ampel misst das nur zu ihrer Laufzeit — #1594
kippte drei Tests, ohne dass es auffiel, weil die eigene Ampel abends lief.
Quelle: #1851 / `docs/specs/modules/fix_1851_alarm_tests_vorlaufsperre.md`;
Nebenbefund gebucht in #1199.
