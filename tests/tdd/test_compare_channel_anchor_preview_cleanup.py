"""TDD RED -- Issue #1987 Scheibe S2: Alarm-Vorschau, Preset-Loeschen und
Briefing-Fehlerpfad mit kanalscharfen Compare-Merkern.

SPEC: ``docs/specs/modules/fix_1987_s2_compare_kanal_anker.md`` -- AC-10,
AC-11, AC-13.

* AC-10: ``alert_preview_hours.compare_preview_point`` nutzt exakt dieselbe
  Basis wie der Alarm desselben Laufs und schreibt nichts.
* AC-11: ``CompareWeatherSnapshotService.delete(preset)`` entfernt auch die
  Kanal-Merker (Praefix ``{preset}__``), laesst ``cp-10__`` bei ``cp-1`` und
  Dateien anderer Nutzer stehen. (Go-Seite hier bewusst nicht beruehrt.)
* AC-13: ein Briefing-Lauf mit Ausnahme schreibt den Briefing-Anker trotzdem
  (#1629); der folgende Alarmlauf findet eine nichtleere Basis, und das
  Briefing schreibt KEINE Kanal-Merker (die gehoeren allein dem Alarm).

Kein Mock-Theater: echte Dateien in der isolierten ``get_data_dir()``-Basis,
echte Aufrufpfade; die Basis wird ueber den aufzeichnenden Wrapper um
``DeviationAlertEngine.evaluate`` bzw. den Rueckgabewert der Vorschau
beobachtet.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import settings_email_and_failing_telegram, settings_email_only
from tests.helpers.compare_briefings import write_compare_briefings
from tests.tdd._compare_channel_anchor_fixtures import (
    ALLE_KANAELE,
    ORT_A,
    alarmlauf,
    basis_mm,
    basis_spion,
    briefing_anker,
    kanal_merker,
    lege_vergleich_an,
    merker,
    nutzer,
    punkt,
    snapshot_dir,
    verzeichnis_stand,
)
from tests.tdd.test_compare_briefing_anchor_survives_dispatch_failure import (  # noqa: F401
    TARGET_DATE,
    _install_anchor_weather_seam,
    _install_comparison_engine_seam,
    _location,
    _preset,
    _ScriptedWeatherSource,
    _settings_email_broken,
    compare_env,
)

LOC = ORT_A[0]


# ═════════════════════════════════ AC-10 ═════════════════════════════════════


def _vorschau_abruf(point_id, lat, lon, start_hour=None, end_hour=None, **kw):
    """Netzfreier Frisch-Abruf der Vorschau (echtes DTO mit Stundenreihe)."""
    return punkt(point_id, 1.5, target_date=kw.get("target_date"), mit_reihe=True)


def test_ac10_vorschau_nutzt_dieselbe_basis_wie_der_alarm_und_schreibt_nichts(monkeypatch):
    """AC-10.

    GIVEN E-Mail + Telegram; Briefing-Anker 8 h alt (1.0 mm), E-Mail-Merker
          2 h alt (2.0 mm), Telegram-Merker 5 h alt (3.0 mm).
    WHEN  erst die Alarm-Vorschau und danach der Alarmlauf die Basis bilden.
    THEN  liefert die Vorschau denselben Stand (3.0 mm, aelteste Kanal-Basis)
          wie die an ``evaluate`` uebergebene Basis, und der Snapshot-Ordner
          ist nach der Vorschau unveraendert.

    HEUTE ROT: ``save_alarm_anchor`` fehlt; fachlich liest die Vorschau nur
    den Briefing-Anker (1.0 mm).
    """
    from services.alert_preview_hours import compare_preview_point

    uid, pid = nutzer("ac10"), "cp-s2-ac10"
    preset = lege_vergleich_an(uid, pid, send_telegram=True)
    briefing_anker(uid, pid, LOC, 1.0, alter=timedelta(hours=8))
    kanal_merker(uid, pid, LOC, "email", 2.0, alter=timedelta(hours=2))
    kanal_merker(uid, pid, LOC, "telegram", 3.0, alter=timedelta(hours=5))
    vorher = verzeichnis_stand(uid)
    loc = SavedLocation(id=LOC, name=ORT_A[1], lat=ORT_A[2], lon=ORT_A[3], elevation_m=800)

    frisch, anker = compare_preview_point(preset, pid, loc, user_id=uid, fetch=_vorschau_abruf)

    assert frisch is not None and anker is not None, "Fixtur-Schutz: Vorschau muss Zeilen liefern."
    assert verzeichnis_stand(uid) == vorher, "AC-10: die Vorschau darf nichts schreiben."
    gesehen = basis_spion(monkeypatch)
    alarmlauf(uid, settings_email_and_failing_telegram(), {LOC: 1.5})
    assert anker.aggregated.precip_sum_mm == pytest.approx(basis_mm(gesehen)), (
        f"AC-10: Vorschau-Basis {anker.aggregated.precip_sum_mm} mm weicht von der "
        f"Alarm-Basis {basis_mm(gesehen)} mm ab."
    )
    assert anker.aggregated.precip_sum_mm == pytest.approx(3.0), (
        "AC-10: beide muessen die aelteste Kanal-Basis (3.0 mm) nutzen."
    )


# ═════════════════════════════════ AC-11 ═════════════════════════════════════


def _preset_mit_merkern(uid: str, pid: str, mm: float) -> None:
    briefing_anker(uid, pid, LOC, mm, alter=timedelta(hours=3))
    kanal_merker(uid, pid, LOC, "email", mm + 0.1, alter=timedelta(hours=1))
    kanal_merker(uid, pid, LOC, "telegram", mm + 0.2, alter=timedelta(hours=1))


def test_ac11_loeschen_entfernt_kanal_merker_nur_des_gewaehlten_presets_und_nutzers():
    """AC-11.

    GIVEN zwei Nutzer mit je zwei Presets ``cp-1`` und ``cp-10``, jeweils
          Briefing-Anker plus E-Mail- und Telegram-Merker.
    WHEN  Nutzer A sein Preset ``cp-1`` loescht (Python ``delete``).
    THEN  sind bei A alle drei ``cp-1__``-Dateien entfernt (inkl. Merker),
          ``cp-10`` von A und ``cp-1`` von B bleiben samt Merkern erhalten.

    HEUTE ROT: ``save_alarm_anchor`` fehlt (der Praefix-Teil ist Bestand).
    """
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid_a, uid_b = nutzer("ac11a"), nutzer("ac11b")
    for uid in (uid_a, uid_b):
        _preset_mit_merkern(uid, "cp-1", 1.0)
        _preset_mit_merkern(uid, "cp-10", 5.0)

    removed, failed = CompareWeatherSnapshotService(user_id=uid_a).delete("cp-1")

    assert (removed, failed) == (3, 0), f"AC-11: erwartet (3, 0), erhalten {(removed, failed)}."
    rest_a = {p.name for p in snapshot_dir(uid_a).iterdir()}
    assert not any(n.startswith("cp-1__") for n in rest_a), f"AC-11: Reste von cp-1: {rest_a!r}."
    for channel in ("email", "telegram"):
        assert merker(uid_a, "cp-1", LOC, channel) is None
    assert merker(uid_a, "cp-10", LOC, "email").aggregated.precip_sum_mm == pytest.approx(5.1)
    assert merker(uid_a, "cp-10", LOC, "telegram").aggregated.precip_sum_mm == pytest.approx(5.2)
    assert merker(uid_b, "cp-1", LOC, "email").aggregated.precip_sum_mm == pytest.approx(1.1), (
        "AC-11: der Merker von Nutzer B darf nicht mitgeloescht werden."
    )
    assert merker(uid_b, "cp-1", LOC, "telegram").aggregated.precip_sum_mm == pytest.approx(1.2)


# ═════════════════════════════════ AC-13 ═════════════════════════════════════


def test_ac13_briefing_ausnahme_hinterlaesst_basis_aber_keine_kanal_merker(
    compare_env, monkeypatch,
):
    """AC-13.

    GIVEN ein Ortsvergleich mit zwei Orten, dessen Briefing-Versand mit einer
          Ausnahme scheitert (echter SMTP-Konfigurations-Guard).
    WHEN  danach ein Alarmlauf (ohne Ausloesen) die Basis bestimmt.
    THEN  ist die Basis jedes Ortes der Briefing-Stand (nichtleer), und das
          Briefing hat fuer keinen Kanal einen Alarm-Merker geschrieben.

    HEUTE ROT: ``load_alarm_anchor`` fehlt (die Briefing-Haelfte ist #1629-
    Bestand und gruen). Mutation Spec Nr. 5 (Briefing-Write an Zustellung
    gekoppelt) liesse die Basis leer -> rot.
    """
    from app.loader import get_data_root, save_location
    from output.channels.base import OutputConfigError
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid, pid = nutzer("ac13"), "cp-s2-ac13"
    orte = [_location("loc-s2-13a", "Alpenort", 47.0, 11.0),
            _location("loc-s2-13b", "Bergort", 47.5, 11.5)]
    for loc in orte:
        save_location(loc, user_id=uid)
    write_compare_briefings(get_data_root() / "users" / uid, [_preset(pid, [o.id for o in orte])])
    _install_comparison_engine_seam(monkeypatch)
    werte = {loc.id: 12.0 + i for i, loc in enumerate(orte)}
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource(
        werte, {loc.id: loc.name for loc in orte}))

    with pytest.raises(OutputConfigError):
        send_one_compare_preset(
            _preset(pid, [o.id for o in orte]), _settings_email_broken(), uid,
            str(compare_env / "data"), all_locations_cache=list(orte),
            target_date=TARGET_DATE, tage_ab_ortstag=0,
        )

    gesehen = basis_spion(monkeypatch)
    alarmlauf(uid, settings_email_only(), werte)
    assert len(gesehen) == len(orte), f"AC-13: erwartet {len(orte)} Auswertungen, {len(gesehen)}."
    assert sorted(c[0].aggregated.precip_sum_mm for c in gesehen if c) == sorted(werte.values()), (
        "AC-13: nach dem Fehlerlauf muss jeder Ort den Briefing-Stand als Basis haben."
    )
    for loc in orte:
        for channel in ALLE_KANAELE:
            assert merker(uid, pid, loc.id, channel) is None, (
                f"AC-13: das Briefing darf keinen Alarm-Merker ({channel}) schreiben."
            )
