"""TDD RED — Issue #2051 S3: `LOCATION_SHARPNESS_LIMIT_MIN` wird zur
LAUFZEIT ueber die Modulreferenz gelesen, nicht beim Import gebunden.

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-16.

Fachlicher Kern (E2, Muster `RADAR_ONSET_THRESHOLD_MIN`): Downstream-Leser
(render.py, starkregen_hint.py, project.py) muessen die Konstante ueber die
MODUL-Referenz (`radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN`) lesen, NIE
per `from ... import LOCATION_SHARPNESS_LIMIT_MIN` -- ein Import zur
Bindezeit wuerde ein spaeteres Monkeypatchen der Konstante nicht mehr sehen
(Laufzeit-Drift-Schutz).

Die Erwartung in diesem Test wird bewusst NICHT als fest getippte Zahl
dupliziert (`limit = 60`), sondern aus DERSELBEN Modulvariable gelesen
(`limit = radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN`) -- nur so wuerde
ein hart getippter Erwartungswert im Produktivcode (statt der
Modulreferenz) hier auffliegen: wird die Konstante auf 90 gepatcht, aber der
Produktivcode liest weiterhin `60` (Bindung beim Import oder hart
kopierter Wert), kippt die Guete-Zeile bei 61 Minuten -- nach dem NEUEN Wert
(90) duerfte sie dort noch nicht erscheinen, und DIESER Test wuerde es
merken.

RED heute: `radar_service` kennt `LOCATION_SHARPNESS_LIMIT_MIN` noch nicht
-> `monkeypatch.setattr(..., raising=True)` scheitert mit `AttributeError`
(Modul hat das Attribut nicht).

Mock-frei: echtes `NowcastResult`/`OnsetEvent` durch die echte Projektion
und den echten Renderer, `monkeypatch.setattr` patcht nur die Konstante,
kein Verhalten wird durch `Mock()`/`patch()` vorgetaeuscht. Die Uhr steht
per `freeze_time`.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email
from services.radar_service import NowcastResult

import services.radar_service as radar_service_mod

_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"

# Ein von 60 ABWEICHENDER Wert -- die Spec verlangt ausdruecklich einen Wert
# ungleich dem heutigen Default, damit ein hart getippter "60" im
# Produktivcode auffliegt.
_NEUER_GRENZWERT_MIN = 90


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Projektion und Renderer werden RELATIV ZU
    DIESER Testdatei aufgeloest."""
    from output.renderers.alert import project as project_module
    from output.renderers.alert import render as render_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (project_module, render_module, radar_service_mod):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


@freeze_time(_FROZEN_UTC)
def test_ac16_guete_zeile_kippt_am_gepatchten_grenzwert_nicht_am_alten(monkeypatch):
    """AC-16 GIVEN einen Testfall, der `LOCATION_SHARPNESS_LIMIT_MIN` zur
    Laufzeit auf einen von 60 abweichenden Wert setzt (`90`, per
    Monkeypatch auf `radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN`)
    WHEN die Guete-Pruefung fuer eine Ereigniszeit knapp UEBER dem NEUEN
    Wert (91 Min) laeuft
    THEN greift die Guete-Zeile nach dem NEUEN Wert (Grenzzeit `now + 90
    Min`) -- UND bei einer Ereigniszeit knapp UNTER dem NEUEN, aber
    UEBER dem ALTEN Wert (61 Min) greift sie NICHT (sonst laese der
    Produktivcode weiterhin die alte 60-Grenze statt der gepatchten
    Modulvariable).

    Die Erwartung wird aus DERSELBEN Modulreferenz gelesen
    (`radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN`), nicht als `60` oder
    `90` im Test dupliziert.

    RED heute: `radar_service` kennt `LOCATION_SHARPNESS_LIMIT_MIN` nicht
    (`AttributeError` beim Monkeypatchen)."""
    monkeypatch.setattr(
        radar_service_mod, "LOCATION_SHARPNESS_LIMIT_MIN", _NEUER_GRENZWERT_MIN,
    )
    limit = radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN
    assert limit == _NEUER_GRENZWERT_MIN, (
        "Vorbedingung: das Monkeypatchen muss die Modulvariable tatsaechlich "
        f"aendern, gelesen wurde {limit!r}"
    )

    def _text_fuer(minuten: int) -> str:
        nc = NowcastResult(
            onset_minutes=minuten, intensity_label="Mäßiger Regen", source="radar",
            is_convective=False,
        )
        msg = to_multi_location_onset_alert_message(
            [("Sillian", nc)], tz=_TZ, stand_at="17:55",
        )
        _html, plain = render_email(msg)
        return plain

    knapp_ueber_altem_wert = _text_fuer(limit - 29)  # 61 bei limit=90
    knapp_ueber_neuem_wert = _text_fuer(limit + 1)   # 91 bei limit=90

    assert "Ortsangabe ab" not in knapp_ueber_altem_wert, (
        f"RED/AC-16: bei {limit - 29} Minuten (jenseits der ALTEN, aber "
        f"diesseits der GEPATCHTEN Grenze von {limit}) darf die Guete-Zeile "
        f"NICHT erscheinen -- sonst liest der Produktivcode weiterhin den "
        f"alten Wert 60 statt der Modulvariable: {knapp_ueber_altem_wert!r}"
    )
    assert "Ortsangabe ab" in knapp_ueber_neuem_wert, (
        f"RED: bei {limit + 1} Minuten (jenseits der GEPATCHTEN Grenze von "
        f"{limit}) muss die Guete-Zeile erscheinen: {knapp_ueber_neuem_wert!r}"
    )
