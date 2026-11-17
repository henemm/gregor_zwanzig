"""Tabelle "Was steht wo": gespeichertes Format und Aufloesung im Resolver.

Issue #3122, Scheibe B1a. SPEC: docs/specs/modules/feat_3122_was_steht_wo.md,
Teil A Nr. 1 bis 7, AC-1 bis AC-7, AC-10 (auf Ebene des View-Models; die
Renderer lesen den neuen Eingang erst ab B1b/B3).

Kern-Schicht, ohne Netz, ohne Mock: echte ``display_config``-Dicts mit
``placements`` durch den echten ``resolve_channel_lists``. Die Erwartungen
stehen von Hand in den Tests.
"""
from __future__ import annotations

import copy

import pytest

from app.metric_catalog import get_all_metrics

REPORT_TYPEN = ("morning", "evening")


def _resolve(dc, surface, report_type="evening", **kw):
    from services.channel_list_resolver import resolve_channel_lists

    return resolve_channel_lists(dc, surface, report_type, **kw)


def _ids(vm, stelle):
    zeilen = getattr(vm, stelle)
    assert zeilen is not None, f"{stelle}: None darf im neuen Eingang nicht vorkommen"
    assert all(z.enabled for z in zeilen)
    assert [z.order for z in zeilen] == list(range(len(zeilen)))
    return [z.metric_id for z in zeilen]


def _formen(vm, stelle):
    return {z.metric_id: z.format for z in getattr(vm, stelle)}


def _zelle(vm, metric_id, stelle):
    zeile = next(z for z in vm.rows if z.metric_id == metric_id)
    return zeile.cell(stelle)


def _row(metric_id, places=None, formats=None):
    r = {"metric_id": metric_id}
    if places is not None:
        r["places"] = places
    if formats is not None:
        r["formats"] = formats
    return r


# Trip-Grundauswahl ohne Temperatur (die Temperatur leitet Fenstergroessen ab,
# s. eigener Test unten).
TRIP_GRUND = ["gust", "wind", "precipitation", "cloud_total", "sunshine", "rain_probability"]


def _trip(rows, grund=TRIP_GRUND, **extra):
    dc = {
        "trip_id": "t-3122",
        "metrics": [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
                    for i, m in enumerate(grund)],
        "placements": {"version": 1, "rows": rows, **extra},
    }
    return dc


ORTE_GRUND = ["temp_max_c", "temp_min_c", "wind_max_kmh", "gust_max_kmh", "precip_sum_mm",
              "pop_max_pct", "sunny_hours_h", "cloud_avg_pct"]
#: Katalog-ID -> Renderer-Kennungen (Aufweitung, Spec Nr. 2), von Hand.
ORTE_KENNUNG = {
    "temperature": ["temp_max", "temp_min"], "wind": ["wind_max"], "gust": ["gust_max"],
    "precipitation": ["precip_sum"], "rain_probability": ["pop_max"],
    "sunshine": ["sunny_hours"], "cloud_total": ["cloud_avg"],
}


def _orte(rows, grund=ORTE_GRUND, **extra):
    return {"active_metrics": list(grund), "placements": {"version": 1, "rows": rows, **extra}}


def _orte_ids(*kennungen):
    return [rid for k in kennungen for rid in ORTE_KENNUNG[k]]


# ---------------------------------------------------------------------------
# AC-1: je Stelle genau die angehakten Metriken in der einen Reihenfolge
# ---------------------------------------------------------------------------

AC1_ROWS = [
    _row("precipitation", {"email": False}),
    _row("wind", {"telegram": False}),
    _row("gust", {"sms": False, "telegram": True}),
    _row("cloud_total", {"email": True, "telegram": False, "sms": True}),
    _row("rain_probability", {"sms": False, "outlook": False}),
    _row("sunshine", {"email": False, "telegram": False, "sms": False}),
]


@pytest.mark.parametrize("report_type", REPORT_TYPEN)
def test_ac1_trip_je_stelle_genau_die_haken_in_einer_folge(report_type):
    vm = _resolve(_trip(copy.deepcopy(AC1_ROWS)), "trip", report_type)
    assert _ids(vm, "email") == ["wind", "gust", "cloud_total", "rain_probability"]
    assert _ids(vm, "telegram") == ["precipitation", "gust", "rain_probability"]
    assert _ids(vm, "sms") == ["precipitation", "wind", "cloud_total"]
    assert vm.premium_sms == vm.sms
    assert [z.metric_id for z in vm.rows] == [r["metric_id"] for r in AC1_ROWS]
    assert [z.position for z in vm.rows] == list(range(len(AC1_ROWS)))


@pytest.mark.parametrize("report_type", REPORT_TYPEN + (None,))
def test_ac1_orte_je_stelle_genau_die_haken_mit_aufweitung(report_type):
    rows = [_row("temperature", {"sms": False})] + copy.deepcopy(AC1_ROWS)
    vm = _resolve(_orte(rows), "compare", report_type)
    assert _ids(vm, "email") == _orte_ids("temperature", "wind", "gust", "cloud_total",
                                          "rain_probability")
    assert _ids(vm, "telegram") == _orte_ids("temperature", "precipitation", "gust",
                                             "rain_probability")
    assert _ids(vm, "sms") == _orte_ids("precipitation", "wind", "cloud_total")
    assert vm.premium_sms == vm.sms
    # Zeilen der Tabelle tragen Katalog-IDs (#3101), nie Renderer-Kennungen.
    assert [z.metric_id for z in vm.rows][:2] == ["temperature", "precipitation"]


def test_ac1_aufweitung_nur_auf_auswertungen_der_grundauswahl():
    """Temperatur mit nur dem Hoechstwert in der Grundauswahl: die Zeile
    'temperature' ergibt nur ``temp_max``."""
    vm = _resolve(_orte([_row("temperature")], grund=["temp_max_c", "wind_max_kmh"]), "compare")
    assert _ids(vm, "email") == ["temp_max", "wind_max"]


# ---------------------------------------------------------------------------
# AC-2: Zeile ausserhalb der Grundauswahl ohne Wirkung
# ---------------------------------------------------------------------------

def test_ac2_trip_zeile_ausserhalb_der_grundauswahl_wirkungslos():
    rows = [_row("uv_index"), _row("gibt_es_nicht"), _row("wind"), _row("gust")]
    vm = _resolve(_trip(rows, grund=["wind", "gust"]), "trip")
    for stelle in ("email", "telegram", "sms", "premium_sms", "outlook"):
        assert "uv_index" not in _ids(vm, stelle), stelle
    assert _ids(vm, "email") == ["wind", "gust"]
    assert _ids(vm, "outlook") == ["wind", "gust"]
    assert [z.metric_id for z in vm.rows] == ["wind", "gust"]


def test_ac2_orte_zeile_ausserhalb_der_grundauswahl_wirkungslos():
    rows = [_row("uv_index"), _row("visibility"), _row("wind")]
    vm = _resolve(_orte(rows, grund=["wind_max_kmh", "precip_sum_mm"]), "compare",
                  hourly_enabled=True)
    for stelle in ("email", "telegram", "sms", "premium_sms"):
        assert set(_ids(vm, stelle)) == {"wind_max", "precip_sum"}, stelle
    assert _ids(vm, "outlook") == ["wind", "precipitation"]
    assert _ids(vm, "hourly") == ["wind", "precipitation"]


# ---------------------------------------------------------------------------
# AC-3: neue Metrik hinten und ueberall an, bewusste Abwahl bleibt
# ---------------------------------------------------------------------------

def test_ac3_trip_neue_metrik_hinten_ueberall_an_abwahl_bleibt():
    rows = [_row("gust", {"telegram": False}), _row("wind")]
    vm = _resolve(_trip(rows, grund=["wind", "gust", "precipitation"]), "trip")
    assert _ids(vm, "email") == ["gust", "wind", "precipitation"]
    assert _ids(vm, "telegram") == ["wind", "precipitation"]
    assert _ids(vm, "sms") == ["gust", "wind", "precipitation"]
    assert _ids(vm, "outlook") == ["gust", "wind", "precipitation"]
    assert [z.metric_id for z in vm.rows] == ["gust", "wind", "precipitation"]
    assert _zelle(vm, "gust", "telegram").state == "off"
    assert _zelle(vm, "precipitation", "telegram").state == "on"


def test_ac3_orte_neue_metrik_hinten_ueberall_an_abwahl_bleibt():
    rows = [_row("gust", {"telegram": False}), _row("wind")]
    vm = _resolve(_orte(rows, grund=["wind_max_kmh", "gust_max_kmh", "precip_sum_mm"]),
                  "compare")
    assert _ids(vm, "email") == ["gust_max", "wind_max", "precip_sum"]
    assert _ids(vm, "telegram") == ["wind_max", "precip_sum"]
    assert _ids(vm, "hourly") == ["gust", "wind", "precipitation"]
    assert _ids(vm, "outlook") == ["gust", "wind", "precipitation"]


def test_ac3_doppelte_zeile_die_erste_zaehlt():
    rows = [_row("wind", {"sms": False}), _row("gust"), _row("wind", {"sms": True})]
    vm = _resolve(_trip(rows, grund=["wind", "gust"]), "trip")
    assert _ids(vm, "sms") == ["gust"]
    assert _ids(vm, "email") == ["wind", "gust"]


# ---------------------------------------------------------------------------
# AC-4: Stundenverlauf und Ausblick nur mit E-Mail, Haken bleiben erhalten
# ---------------------------------------------------------------------------

def test_ac4_orte_ohne_email_kein_stundenverlauf_und_ausblick_mit_wiederkehr():
    gespeichert = {"email": True, "hourly": True, "outlook": True}
    aus = _resolve(_orte([_row("wind", {**gespeichert, "email": False}), _row("gust")],
                         grund=["wind_max_kmh", "gust_max_kmh"]), "compare")
    assert "wind" not in _ids(aus, "hourly")
    assert "wind" not in _ids(aus, "outlook")
    assert "wind_max" not in _ids(aus, "email")
    assert "wind_max" in _ids(aus, "telegram")
    assert _zelle(aus, "wind", "hourly").state == "not_in_email"
    assert _zelle(aus, "wind", "outlook").state == "not_in_email"
    assert _zelle(aus, "wind", "email").state == "off"

    wieder = _resolve(_orte([_row("wind", gespeichert), _row("gust")],
                            grund=["wind_max_kmh", "gust_max_kmh"]), "compare")
    assert _ids(wieder, "hourly") == ["wind", "gust"]
    assert _ids(wieder, "outlook") == ["wind", "gust"]
    assert _zelle(wieder, "wind", "hourly").state == "on"


def test_ac4_trip_ohne_email_kein_ausblick_mit_wiederkehr():
    aus = _resolve(_trip([_row("wind", {"email": False, "outlook": True}), _row("gust")],
                         grund=["wind", "gust"]), "trip")
    assert _ids(aus, "outlook") == ["gust"]
    assert _zelle(aus, "wind", "outlook").state == "not_in_email"
    wieder = _resolve(_trip([_row("wind", {"outlook": True}), _row("gust")],
                            grund=["wind", "gust"]), "trip")
    assert _ids(wieder, "outlook") == ["wind", "gust"]


def test_ac4_ausblick_haken_aus_bleibt_aus_bei_email_an():
    vm = _resolve(_trip([_row("wind", {"outlook": False}), _row("gust")],
                        grund=["wind", "gust"]), "trip")
    assert _ids(vm, "outlook") == ["gust"]
    assert _zelle(vm, "wind", "outlook").state == "off"


# ---------------------------------------------------------------------------
# AC-5: Format je Stelle unabhaengig
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("surface", ["trip", "compare"])
def test_ac5_format_je_stelle_unabhaengig(surface):
    gust = "gust" if surface == "trip" else "gust_max"

    def _vm(formats):
        rows = [_row("gust", formats=formats), _row("wind")]
        dc = (_trip(rows, grund=["gust", "wind"]) if surface == "trip"
              else _orte(rows, grund=["gust_max_kmh", "wind_max_kmh"]))
        return _resolve(dc, surface)

    vm = _vm({"telegram": "raw", "email": "simplified", "outlook": "raw"})
    assert _formen(vm, "telegram")[gust] == "raw"
    assert _formen(vm, "email")[gust] == "simplified"
    assert _formen(vm, "outlook")["gust"] == "raw"
    umgeschaltet = _vm({"telegram": "simplified", "email": "simplified", "outlook": "raw"})
    assert _formen(umgeschaltet, "telegram")[gust] == "simplified"
    assert _formen(umgeschaltet, "email") == _formen(vm, "email")
    assert _formen(umgeschaltet, "outlook") == _formen(vm, "outlook")
    if surface == "compare":
        st = _vm({"hourly": "simplified"})
        assert _formen(st, "hourly")["gust"] == "simplified"
        assert _formen(st, "email")["gust_max"] == "raw", "Katalog-Standard Wind/Boeen: Roh"


@pytest.mark.parametrize("surface", ["trip", "compare"])
def test_ac5_fehlendes_format_ist_katalog_standard_fuer_beide_flaechen_gleich(surface):
    """Ohne gespeichertes Format: Bewoelkung Einfach (Symbol), Boeen Roh --
    Trip und Orte gleich."""
    rows = [_row("cloud_total"), _row("gust")]
    dc = (_trip(rows, grund=["cloud_total", "gust"]) if surface == "trip"
          else _orte(rows, grund=["cloud_avg_pct", "gust_max_kmh"]))
    vm = _resolve(dc, surface)
    cloud, gust = ("cloud_total", "gust") if surface == "trip" else ("cloud_avg", "gust_max")
    for stelle in ("email", "telegram"):
        assert _formen(vm, stelle) == {cloud: "simplified", gust: "raw"}, stelle
    assert _formen(vm, "outlook") == {"cloud_total": "simplified", "gust": "raw"}
    assert _formen(vm, "sms") == {cloud: None, gust: None}


# ---------------------------------------------------------------------------
# AC-6: Format ohne zwei Formen und in der SMS ohne Wirkung
# ---------------------------------------------------------------------------

def _orte_schluessel(metric_id):
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

    return [e["key"] for e in COMPARE_METRIC_CATALOG if e["metric_id"] == metric_id]


@pytest.mark.parametrize("form", ["raw", "simplified"])
@pytest.mark.parametrize("metric_id", [m.id for m in get_all_metrics()])
@pytest.mark.parametrize("surface", ["trip", "compare"])
def test_ac6_format_wirkt_nur_an_stellen_mit_zwei_formen(surface, metric_id, form):
    from app.metric_catalog import zwei_formen_stellen

    alle = {s: form for s in ("email", "telegram", "sms", "hourly", "outlook", "premium_sms")}
    if surface == "trip":
        dc = _trip([_row(metric_id, formats=alle)], grund=[metric_id])
    else:
        schluessel = _orte_schluessel(metric_id)
        if not schluessel:
            pytest.skip("Metrik hat bei Orten keine Zeile")
        dc = _orte([_row(metric_id, formats=alle)], grund=schluessel)
    vm = _resolve(dc, surface)
    zwei = zwei_formen_stellen(metric_id)
    for stelle in ("email", "telegram", "sms", "premium_sms", "outlook", "hourly"):
        for z in getattr(vm, stelle):
            erwartet = form if stelle in zwei else None
            assert z.format == erwartet, (stelle, z)
    for stelle in ("email", "telegram", "sms", "hourly", "outlook"):
        zeile = next(z for z in vm.rows if z.metric_id == metric_id)
        if stelle not in {s for s, _c in zeile.cells}:
            continue
        zelle = zeile.cell(stelle)
        if zelle.state == "locked" or stelle not in zwei:
            assert zelle.format is None, (stelle, zelle)
        else:
            assert zelle.format == form, (stelle, zelle)


# ---------------------------------------------------------------------------
# AC-7: gesperrte Stelle
# ---------------------------------------------------------------------------

def _gesperrte_kombinationen():
    from app.metric_catalog import stellen_sperre

    for surface in ("trip", "compare"):
        stellen = ("email", "telegram", "sms", "outlook") + (("hourly",) if surface == "compare" else ())
        for m in get_all_metrics():
            for stelle in stellen:
                grund = stellen_sperre(m.id, stelle, surface)
                if grund:
                    yield surface, m.id, stelle, grund


@pytest.mark.parametrize("surface,metric_id,stelle,grund", list(_gesperrte_kombinationen()))
def test_ac7_gesperrte_stelle_wirkt_nicht_und_meldet_grund(surface, metric_id, stelle, grund):
    if surface == "trip":
        dc = _trip([_row(metric_id, {stelle: True})], grund=[metric_id])
    else:
        schluessel = _orte_schluessel(metric_id)
        if not schluessel:
            pytest.skip("Metrik hat bei Orten keine Zeile")
        dc = _orte([_row(metric_id, {stelle: True})], grund=schluessel)
    vm = _resolve(dc, surface, hourly_enabled=True)
    ziel = "email" if stelle == "email" else stelle
    assert metric_id not in [z.metric_id for z in getattr(vm, ziel)]
    zelle = _zelle(vm, metric_id, stelle)
    assert (zelle.state, zelle.reason) == ("locked", grund)


def test_ac7_sonnenstunden_orte_stundenverlauf_gesperrt():
    vm = _resolve(_orte([_row("sunshine", {"hourly": True}), _row("wind")],
                        grund=["sunny_hours_h", "wind_max_kmh"]), "compare")
    assert _ids(vm, "hourly") == ["wind"]
    assert "sunny_hours" in _ids(vm, "email")
    assert _zelle(vm, "sunshine", "hourly").reason == "kein_stundenwert"


# ---------------------------------------------------------------------------
# Spec Nr. 2: abgeleitete Groessen folgen ihrer Eltern-Zeile
# ---------------------------------------------------------------------------

def test_abgeleitete_groessen_folgen_der_eltern_zeile():
    """Ein Trip mit Temperatur bekommt beim Laden Nacht-/Tagesgroessen
    abgeleitet. Ohne eigene Zeile stehen sie direkt hinter 'temperature' und
    tragen deren Haken."""
    rows = [_row("wind"), _row("temperature", {"sms": False}), _row("gust")]
    vm = _resolve(_trip(rows, grund=["wind", "temperature", "gust"]), "trip")
    kinder = ["temperature_night", "temperature_day_low", "temperature_day_high"]
    assert _ids(vm, "telegram") == ["wind", "temperature", *kinder, "gust"]
    assert _ids(vm, "sms") == ["wind", "gust"]
    # Stundentabelle der Trip-Mail: Fenstergroessen haben keine eigene Spalte.
    assert _ids(vm, "email") == ["wind", "temperature", "gust"]


# ---------------------------------------------------------------------------
# AC-10: leer bleibt leer, kein Rueckfall
# ---------------------------------------------------------------------------

def test_ac10_spalte_leer_bleibt_leer_und_bloecke_entfallen():
    aus = {"email": False}
    vm = _resolve(_orte([_row("wind", aus), _row("gust", aus)],
                        grund=["wind_max_kmh", "gust_max_kmh"]), "compare", hourly_enabled=True)
    assert vm.email == ()
    assert vm.hourly == ()
    assert vm.outlook == ()
    assert _ids(vm, "telegram") == ["wind_max", "gust_max"]
    trip = _resolve(_trip([_row("wind", {"sms": False}), _row("gust", {"sms": False})],
                          grund=["wind", "gust"]), "trip")
    assert trip.sms == () and trip.premium_sms == ()
    assert _ids(trip, "email") == ["wind", "gust"]


def test_ac10_bewusst_leere_grundauswahl_ohne_rueckfall():
    trip = _trip([_row("wind")], grund=[])
    trip["metrics"] = [{"metric_id": "wind", "enabled": False},
                       {"metric_id": "gust", "enabled": False}]
    orte = _orte([_row("wind")], grund=[])
    for dc, surface in ((trip, "trip"), (orte, "compare")):
        for report_type in REPORT_TYPEN:
            vm = _resolve(dc, surface, report_type, hourly_enabled=True)
            for stelle in ("email", "telegram", "sms", "premium_sms", "outlook", "hourly"):
                assert getattr(vm, stelle) == (), (surface, stelle)
            assert vm.rows == ()


def test_ac10_nie_eingestellte_grundauswahl_bekommt_standardsatz():
    """Trip ohne ``metrics``: Trip-Anlege-Standard des Registers (wie der
    bisherige Pfad); Orte ohne ``active_metrics``: alle Zeilen der Orte-
    Uebersicht in der Standardfolge. Nie ``None``."""
    from output.renderers.trip_metric_ids import DEFAULT_TRIP_METRIC_IDS

    trip = _resolve({"trip_id": "t", "placements": {"rows": []}}, "trip")
    assert [z.metric_id for z in trip.rows][: len(DEFAULT_TRIP_METRIC_IDS)] == list(
        DEFAULT_TRIP_METRIC_IDS)
    assert _ids(trip, "sms")
    orte = _resolve({"placements": {"rows": []}}, "compare")
    assert _ids(orte, "email")[:4] == ["temp_max", "temp_min", "wind_max", "precip_sum"]
    assert _ids(orte, "hourly") and _ids(orte, "outlook")


def test_hourly_enabled_falsch_laesst_den_stundenverlauf_entfallen_trip_ohne_stundenverlauf():
    orte = _orte([_row("wind")], grund=["wind_max_kmh"])
    assert _resolve(orte, "compare", hourly_enabled=False).hourly == ()
    assert _ids(_resolve(orte, "compare"), "hourly") == ["wind"]
    trip = _resolve(_trip([_row("wind")], grund=["wind"]), "trip")
    assert trip.hourly == ()


def test_premium_sms_folgt_der_sms_auch_mit_altfeld():
    dc = _trip([_row("wind", {"sms": False}), _row("gust")], grund=["wind", "gust"])
    dc["channel_layouts"] = {"premium_sms": [{"metric_id": "wind"}]}
    vm = _resolve(dc, "trip")
    assert vm.premium_sms == vm.sms
    assert _ids(vm, "sms") == ["gust"]


# ---------------------------------------------------------------------------
# Ausblick: outlook_reports je Briefing-Typ (Spec Nr. 6, AC-9 auf Resolver-Ebene)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("surface", ["trip", "compare"])
@pytest.mark.parametrize("reports,morgens,abends", [
    (["evening"], False, True),
    (["morning"], True, False),
    (["morning", "evening"], True, True),
    ([], False, False),
    (["noon", 5, "evening"], False, True),
])
def test_outlook_reports_wirkt_je_briefing_typ(surface, reports, morgens, abends):
    dc = (_trip([_row("wind")], grund=["wind"], outlook_reports=reports) if surface == "trip"
          else _orte([_row("wind")], grund=["wind_max_kmh"], outlook_reports=reports))
    assert bool(_resolve(dc, surface, "morning").outlook) is morgens
    assert bool(_resolve(dc, surface, "evening").outlook) is abends
    assert set(_resolve(dc, surface, "evening").outlook_reports) == {
        r for r, an in (("morning", morgens), ("evening", abends)) if an}


@pytest.mark.parametrize("surface", ["trip", "compare"])
def test_ac9_vorbelegung_abends_bei_nur_morgen_morgens(surface):
    dc = (_trip([_row("wind")], grund=["wind"]) if surface == "trip"
          else _orte([_row("wind")], grund=["wind_max_kmh"]))
    beide = {"enabled_reports": ("morning", "evening")}
    assert _resolve(dc, surface, "morning", **beide).outlook == ()
    assert _ids(_resolve(dc, surface, "evening", **beide), "outlook") == ["wind"]
    assert _resolve(dc, surface, "evening", **beide).outlook_reports == ("evening",)
    nur_morgen = {"enabled_reports": ("morning",)}
    assert _ids(_resolve(dc, surface, "morning", **nur_morgen), "outlook") == ["wind"]
    assert _resolve(dc, surface, "morning", **nur_morgen).outlook_reports == ("morning",)
    ohne = _resolve(dc, surface, "evening")
    assert ohne.outlook_reports == ("evening",)


def test_ausblick_entfaellt_wenn_keine_metrik_dort_gilt():
    dc = _trip([_row("wind", {"outlook": False})], grund=["wind"], outlook_reports=["evening"])
    assert _resolve(dc, "trip", "evening").outlook == ()


# ---------------------------------------------------------------------------
# Robustheit und Reinheit
# ---------------------------------------------------------------------------

def _sauber():
    return _orte([_row("wind", {"sms": False}, {"email": "simplified"}), _row("gust")],
                 grund=["wind_max_kmh", "gust_max_kmh", "precip_sum_mm"],
                 outlook_reports=["evening"])


@pytest.mark.parametrize("kaputt", [
    lambda p: p["rows"].insert(0, "wind"),
    lambda p: p["rows"].insert(0, {"metric_id": 7}),
    lambda p: p["rows"].insert(0, {"places": {"email": False}}),
    lambda p: p["rows"].append(None),
    lambda p: p["rows"][1].update(places="alle"),
    lambda p: p["rows"][1].update(formats=["raw"]),
    lambda p: p["rows"][0]["places"].update(fax=False, email="nein", hourly=None),
    lambda p: p["rows"][0]["formats"].update(sms="raw", telegram="bunt", fax="raw"),
    lambda p: p.update(unbekannt={"x": 1}, version="zwei"),
    lambda p: p["rows"][0].update(extra=True),
])
def test_kaputte_eintraege_werfen_nicht_und_wirken_nicht(kaputt):
    sauber = _sauber()
    dc = copy.deepcopy(sauber)
    kaputt(dc["placements"])
    for report_type in REPORT_TYPEN:
        assert _resolve(dc, "compare", report_type) == _resolve(sauber, "compare", report_type)


@pytest.mark.parametrize("placements", ["x", 5, ["wind"], None, {"rows": "x"}, {"rows": None}])
def test_placements_ohne_lesbare_zeilen_laeuft_ueber_den_bisherigen_pfad(placements):
    basis = {"active_metrics": ["wind_max_kmh", "gust_max_kmh"],
             "channel_layouts": {"sms": [{"metric_id": "gust"}]}}
    mit = {**copy.deepcopy(basis), "placements": placements}
    assert _resolve(mit, "compare") == _resolve(basis, "compare")


def test_outlook_reports_falscher_typ_gilt_als_fehlend():
    dc = _trip([_row("wind")], grund=["wind"], outlook_reports="morning")
    assert _resolve(dc, "trip", "evening").outlook_reports == ("evening",)


def test_resolver_mutiert_die_eingabe_nicht():
    for dc, surface in ((_trip(copy.deepcopy(AC1_ROWS)), "trip"), (_sauber(), "compare")):
        vorher = copy.deepcopy(dc)
        for report_type in REPORT_TYPEN:
            _resolve(dc, surface, report_type, enabled_reports=("morning",), hourly_enabled=True)
        assert dc == vorher


def test_neue_felder_eingefroren_und_zeilen_unveraenderlich():
    import dataclasses

    vm = _resolve(_sauber(), "compare")
    assert isinstance(vm.rows, tuple) and isinstance(vm.outlook_reports, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.rows = ()  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.rows[0].metric_id = "x"  # type: ignore[misc]
