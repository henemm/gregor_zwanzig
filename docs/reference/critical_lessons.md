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
#1594 (`src/services/trip_alert.py:241` → `src/services/alert_gate.py:256` →
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

**Nachmessen lässt es sich aber** (seit #1709): `tests/helpers/wanduhr_matrix.py`
fährt eine Testdatei zu mehreren gestellten Uhrzeiten und meldet nur die
**Differenz** — eine nicht-leere Menge heißt „hängt an der Wanduhr".

```
uv run python3 -c "
import sys; sys.path.insert(0,'tests')
from datetime import datetime, timezone
from pathlib import Path
from helpers.wanduhr_matrix import matrix_differenz
zeiten=[datetime(2026,8,15,h,0,tzinfo=timezone.utc) for h in (5,12,18,23)]
print(matrix_differenz(Path('<testdatei>'), zeiten))"
```

Drei Fallen dabei, alle teuer gelernt: je Datenpunkt ein **eigener Prozess**
(mehrere Läufe im selben Prozess sind nicht reproduzierbar); nur **Differenzen**
auswerten (sitzungsweites `freezegun` zerstört pydantic-v1-Importe und erzeugt
Falsch-Positive); Uhrzeiten in der **Ortszone der Fixture** wählen, nicht in UTC.

**Gegenmittel, nicht nur Messgerät** (seit #2096): `wanduhr_matrix.py` *findet* die
Abhängigkeit, beseitigen lässt sie sich mit dem Uhr-Schalter. Die Session-Fixture
`_gestellte_wanduhr` (`tests/conftest.py`) stellt die Uhr auf den Wert der
Umgebungsvariablen `GZ_TEST_WALL_CLOCK_UTC`; die Ankerbestimmung liegt an **einer**
Stelle in `tests/helpers/wanduhr.py` (`anker_aus()`), ihr Selbsttest in
`tests/tdd/test_gestellte_wanduhr_schalter.py`.

```
GZ_TEST_WALL_CLOCK_UTC=23:55 uv run pytest <testdatei>   # HH:MM = heute, UTC
GZ_TEST_WALL_CLOCK_UTC=2026-08-15T23:55 uv run pytest <testdatei>   # oder ISO-Stempel
```

Der Rückgabewert ist **immer** UTC-behaftet — ein naiver Wert würde von `freezegun` als
Ortszeit gelesen und die Uhr auf einem Server in anderer Zone still um den Zonenversatz
daneben stellen, ohne dass ein Lauf rot würde. Unbrauchbare Eingaben lösen `ValueError`
aus, statt stillschweigend irgendeinen Zeitpunkt zu nehmen.

Die zugehörige Falle beim Prüfen: ein Test, der einen tagesbezogenen Wert gegen einen
nackten `HH:MM`-Anker hält, ist ab Mitternachtsüberlauf blind — er braucht den
**Tagesbezug** (Wochentagskürzel) im Soll. Wächter dafür:
`tests/tdd/test_tagesbezug_testwaechter.py`, `tests/tdd/test_tagesbezug_ueberlauf_spaetuhr.py`.

Quelle: #1851 / `docs/specs/modules/fix_1851_alarm_tests_vorlaufsperre.md`;
Werkzeug aus #1709 / `docs/specs/modules/fix_1709_wallclock_ratsche_indirekt.md`;
Uhr-Schalter und Tagesbezug aus #2096 /
`docs/specs/modules/fix_2096_tagesbezug_testwaechter.md`;
Nebenbefund gebucht in #1199.

## Fixture-Trips datieren nach dem Ortstag der Koordinaten, nie nach `date.today()`

Test-Fixtures, die Trips/Anker/Schnappschüsse datieren, müssen den **Ortstag der
Trip-Koordinaten** verwenden (`tests/helpers/ortstag.py` → `ortstag(lat, lon, *,
now_utc=None)`, delegiert an `utils.timezone.tz_for_coords`, ADR-0044) — die
Koordinaten des jeweils datierten Trips, nie pauschal irgendwelche. `date.today()`
liefert den Tag der **Prozesszone** (CI: America/St_Johns), nicht den Ortstag,
und weicht dort rund um Mitternacht UTC vom Produktverhalten ab. Ausnahme: Tests,
die die Tagesberechnung selbst prüfen, brauchen eine gestellte Uhr plus einen
Literal-Soll-Tag (sonst wird der Test tautologisch).

Messgrenze: Unter `GZ_TEST_WALL_CLOCK_UTC`/freezegun liefert `date.today()` den
**UTC-Tag**, nicht den St.-John's-Tag — lokal ist nur das Fenster 22:00–24:00 UTC
des echten Ausfalls nachstellbar; ein grüner Lauf um 01:00 oder 04:00 Uhr ist
kein Befund.

Falle: Modulweite Konstanten wie `NOW = datetime.now(...)` werden beim Laden des
Moduls gesetzt, also vor der gestellten Uhr — zwei Uhren laufen gegeneinander
(Beispiel #2314, `tests/tdd/test_official_alert_time_window.py`).

Die Wanduhr-Ratsche `tests/tdd/test_fixture_wallclock_ratchet.py` (#1667) wertet
`ortstag(...)`-Aufrufe ohne gepinntes `now_utc` ebenfalls als Wanduhr-Abhängigkeit.

Quelle: #2314 / `docs/specs/modules/fix_2314_ci_zeitzonen_riss.md`.
