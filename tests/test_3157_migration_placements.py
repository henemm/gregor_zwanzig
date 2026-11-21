"""TDD RED: Issue #3157 -- Migration ``scripts/migrate_3157_placements.py`` (B6).

Spec: docs/specs/modules/feat_3157_migration_placements.md (AC-1 bis AC-10),
Mutter-Spec docs/specs/modules/feat_3122_was_steht_wo.md (Teil A Nr. 8).
Muster: ``scripts/migrate_3196_trip_tempo.py`` (``main(argv)``, ``--root
<data/users> [--backup-dir <p>] [--execute]``).

Vertrag des Berichts (stdout), je Abo EINE Zeile mit: Nutzer-Kennung,
Abo-Kennung, Flaeche (``Trip`` | ``Orte``), Status (``hat schon placements``
| ``wird umgerechnet`` | ``Fehler``) und je gefundener Aenderungsart
``<art>=<anzahl>`` (Anzahl = Eintraege der Umrechnung dieser Art). Bei
``Fehler`` steht der Grund in derselben Zeile.

Das Soll fuer ``placements`` kommt aus derselben Umrechnung
(``placements_from_legacy``) ueber den echten Lade-Weg des Abos (Loader,
wie die Tabellen-Ansicht), nie aus dem Skript. Briefings ueber den echten
Versandweg (Transport-Mitschrift als einzige Naht). Kern-Schicht, ohne Netz,
ohne Mocks; zwei Nutzer.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import tarfile
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

_HERE = Path(__file__).resolve().parent
_SKRIPT = _HERE.parent / "scripts" / "migrate_3157_placements.py"
_FULL_TRIP = json.loads((_HERE / "fixtures" / "trip_schema_full.json").read_text(encoding="utf-8"))
_ORTE_BASIS = json.loads((_HERE / "fixtures" / "compare_kette" / "basis.json").read_text(encoding="utf-8"))

U_A, U_B = "nutzer-anna", "nutzer-bert"


# ---------------------------------------------------------------------------
# Skript
# ---------------------------------------------------------------------------

def _modul():
    assert _SKRIPT.is_file(), f"Migrationsskript fehlt: {_SKRIPT}"
    spec = importlib.util.spec_from_file_location("migrate_3157_placements", _SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lauf(root: Path, backup: Path, *, execute: bool) -> tuple[int, str]:
    argv = ["--root", str(root), "--backup-dir", str(backup)]
    if execute:
        argv.append("--execute")
    puffer = io.StringIO()
    with redirect_stdout(puffer):
        rc = _modul().main(argv)
    return rc, puffer.getvalue()


def _zeile(bericht: str, uid: str, abo_id: str) -> str:
    treffer = [z for z in bericht.splitlines() if uid in z and abo_id in z]
    assert len(treffer) == 1, f"genau eine Berichtszeile fuer {uid}/{abo_id} erwartet:\n{bericht}"
    return treffer[0]


# ---------------------------------------------------------------------------
# Bestandsdaten (Altformat)
# ---------------------------------------------------------------------------

def _m(metric_id: str, i: int, **kw) -> dict:
    return {"metric_id": metric_id, "enabled": True, "bucket": "primary", "order": i, **kw}


GRUND_TRIP = ["wind", "gust", "precipitation", "cloud_total", "temperature"]


def _trip_alt(trip_id: str, *, dc_extra: dict | None = None, rc_extra: dict | None = None) -> dict:
    """Voll besetzter Trip (``trip_schema_full.json``) im Altformat: Grundauswahl,
    eigene Kanal-Listen (SMS fuehrt anders als die E-Mail), Ausblick-Altfelder."""
    d = copy.deepcopy(_FULL_TRIP)
    d["id"] = trip_id
    d["kind"] = "route"
    dc = d["display_config"]
    dc["trip_id"] = trip_id
    dc["metrics"] = [_m(x, i) for i, x in enumerate(GRUND_TRIP)]
    dc["channel_layouts"] = {
        "email": [{"metric_id": "wind", "use_friendly_format": False},
                  {"metric_id": "gust"}, {"metric_id": "cloud_total"}],
        "sms": [{"metric_id": "gust"}, {"metric_id": "wind"}],
        "telegram": [{"metric_id": "wind"}, {"metric_id": "gust"}],
    }
    dc["outlook_metrics"] = ["wind", "gust"]
    dc["outlook_metric_formats"] = {"gust": True}
    dc.update(dc_extra or {})
    d["report_config"]["trip_id"] = trip_id
    d["report_config"].update(rc_extra or {})
    return d


def _orte_alt(preset_id: str, *, extra: dict | None = None, dc_extra: dict | None = None) -> dict:
    """Orts-Vergleich im Altformat: Grundauswahl und eigene SMS-Liste."""
    p = copy.deepcopy(_ORTE_BASIS)
    p["id"] = preset_id
    p["name"] = f"Orte {preset_id}"
    p["display_config"]["channel_active_metrics"] = {
        "sms": ["gust_max_kmh", "temp_max_c"]}
    p["display_config"].update(dc_extra or {})
    p.update(extra or {})
    return p


def _mit_placements(d: dict) -> dict:
    """Abo, das die Tabelle schon traegt (gespeicherte Tabelle, kein Altpfad)."""
    d = copy.deepcopy(d)
    d["display_config"]["placements"] = {
        "version": 1, "outlook_reports": ["evening"],
        "rows": [{"metric_id": "gust"}, {"metric_id": "temperature"}]}
    return d


def _ablegen(root: Path, uid: str, abo: dict | str, name: str | None = None) -> Path:
    pfad = root / uid / "briefings" / f"{name or abo['id']}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = abo if isinstance(abo, str) else json.dumps(abo, ensure_ascii=False, indent=2)
    pfad.write_text(text, encoding="utf-8")
    return pfad


def _bestand(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    """Zwei Nutzer, je ein Trip und ein Orte-Abo im Altformat; Nutzer B hat
    zusaetzlich ein Abo, das schon ``placements`` traegt."""
    root = tmp_path / "data" / "users"
    pfade = {
        "a_trip": _ablegen(root, U_A, _trip_alt("anna-trip")),
        "a_orte": _ablegen(root, U_A, _orte_alt("anna-orte")),
        "b_trip": _ablegen(root, U_B, _trip_alt("bert-trip", dc_extra={
            "channel_layouts": {"sms": [{"metric_id": "precipitation"}, {"metric_id": "gust"}]}})),
        "b_orte": _ablegen(root, U_B, _orte_alt("bert-orte", dc_extra={
            "channel_active_metrics": {"sms": ["wind_max_kmh", "temp_max_c"]}})),
        "b_schon": _ablegen(root, U_B, _mit_placements(_orte_alt("bert-schon"))),
    }
    return root, pfade


def _baum(root: Path) -> dict[str, bytes]:
    """Byte-Abbild aller Dateien und Verzeichnisse unter ``root``."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        out[rel] = b"<dir>" if p.is_dir() else p.read_bytes()
    return out


def _lies(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Soll: dieselbe Umrechnung ueber den echten Lade-Weg (wie die Tabellen-Ansicht)
# ---------------------------------------------------------------------------

def _umrechnung(pfad: Path):
    from app.loader import compare_preset_to_dict, load_compare_presets, load_trip
    from app.models import slot_aktiv
    from services.compare_slot_scheduler import resolve_preset_slots
    from services.placements import placements_from_legacy

    roh = _lies(pfad)
    if roh.get("kind") == "vergleich":
        uid = pfad.parent.parent.name
        data_root = pfad.parent.parent.parent.parent
        treffer = [p for p in load_compare_presets(user_id=uid, data_root=data_root)
                   if p.id == roh["id"]]
        assert len(treffer) == 1, f"Vorbedingung: Orte-Abo {roh['id']} ladbar"
        preset = compare_preset_to_dict(treffer[0])
        slots = resolve_preset_slots(preset)
        return placements_from_legacy(
            preset.get("display_config") or {}, "compare",
            enabled_reports=tuple(rt for rt, an in (("morning", slots.morning_enabled),
                                                    ("evening", slots.evening_enabled)) if an),
            outlook_enabled=preset.get("outlook_enabled"))
    trip = load_trip(str(pfad))
    assert trip is not None, f"Vorbedingung: Trip {pfad.name} ladbar"
    rc = trip.report_config
    return placements_from_legacy(
        trip.display_config, "trip", report_config=rc,
        enabled_reports=tuple(rt for rt in ("morning", "evening") if slot_aktiv(rc, rt)))


def _arten(pfad: Path) -> Counter:
    return Counter(c.kind for c in _umrechnung(pfad).changes)


# ---------------------------------------------------------------------------
# AC-1: Probelauf schreibt nichts, Bericht je Abo
# ---------------------------------------------------------------------------

def test_ac1_probelauf_schreibt_nichts_und_berichtet_je_abo(tmp_path):
    root, pfade = _bestand(tmp_path)
    soll = {k: _arten(p) for k, p in pfade.items() if k != "b_schon"}
    assert all(soll.values()), f"Vorbedingung: jedes Altabo hat Aenderungsarten: {soll}"
    vorher = _baum(tmp_path)

    rc, bericht = _lauf(root, tmp_path / "bak", execute=False)

    assert _baum(tmp_path) == vorher, "Probelauf hat Dateien oder Verzeichnisse veraendert"
    assert rc == 0
    faelle = {"a_trip": (U_A, "anna-trip", "Trip"), "a_orte": (U_A, "anna-orte", "Orte"),
              "b_trip": (U_B, "bert-trip", "Trip"), "b_orte": (U_B, "bert-orte", "Orte")}
    for key, (uid, abo_id, flaeche) in faelle.items():
        zeile = _zeile(bericht, uid, abo_id)
        assert flaeche in zeile and "wird umgerechnet" in zeile, zeile
        for art, anzahl in soll[key].items():
            assert f"{art}={anzahl}" in zeile, f"{abo_id}: {art}={anzahl} fehlt: {zeile}"
    assert "hat schon placements" in _zeile(bericht, U_B, "bert-schon")


# ---------------------------------------------------------------------------
# AC-2: Sicherung je Nutzer vor dem Schreiben
# ---------------------------------------------------------------------------

def _archive(backup: Path, uid: str) -> list[Path]:
    return sorted(backup.glob(f"migrate-3157-{uid}-*.tar.gz")) if backup.is_dir() else []


def _archiv_inhalt(archiv: Path) -> dict[str, bytes]:
    with tarfile.open(archiv, "r:gz") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}


def test_ac2_sicherung_je_nutzer_gleich_den_originalen(tmp_path):
    root, pfade = _bestand(tmp_path)
    original = {p: p.read_bytes() for p in pfade.values()}
    backup = tmp_path / "bak"

    rc, _ = _lauf(root, backup, execute=True)

    assert rc == 0
    for uid, keys in ((U_A, ("a_trip", "a_orte")), (U_B, ("b_trip", "b_orte"))):
        archive = _archive(backup, uid)
        assert len(archive) == 1, f"genau eine Sicherung fuer {uid} erwartet: {archive}"
        inhalt = _archiv_inhalt(archive[0])
        namen = {Path(n).name: b for n, b in inhalt.items()}
        for k in keys:
            assert namen.get(pfade[k].name) == original[pfade[k]], \
                f"{uid}: {pfade[k].name} fehlt in der Sicherung oder weicht ab"


def test_ac2_sicherung_scheitert_nichts_geschrieben(tmp_path):
    root, pfade = _bestand(tmp_path)
    backup = tmp_path / "bak"
    backup.mkdir()
    os.chmod(backup, 0o500)
    vorher = {p: p.read_bytes() for p in pfade.values()}
    try:
        rc, _ = _lauf(root, backup, execute=True)
    finally:
        os.chmod(backup, 0o700)
    assert rc != 0, "gescheiterte Sicherung muss mit Exit ungleich 0 enden"
    for p, b in vorher.items():
        assert p.read_bytes() == b, f"{p.name} geschrieben, obwohl die Sicherung scheiterte"


# ---------------------------------------------------------------------------
# AC-3 / AC-4: nur placements neu, gleich der Umrechnung
# ---------------------------------------------------------------------------

def _ohne_neue_stellen(d: dict) -> dict:
    d = copy.deepcopy(d)
    d.get("display_config", {}).pop("placements", None)
    return d


@pytest.mark.parametrize("key", ["a_trip", "a_orte", "b_trip", "b_orte"])
def test_ac3_ac4_nur_placements_neu_und_gleich_der_umrechnung(tmp_path, key):
    root, pfade = _bestand(tmp_path)
    pfad = pfade[key]
    vorher = _lies(pfad)
    soll = _umrechnung(pfad)
    assert soll.show_stability_off is False, "Vorbedingung: ohne Grosswetterlage-Folge"

    rc, _ = _lauf(root, tmp_path / "bak", execute=True)

    assert rc == 0
    nachher = _lies(pfad)
    assert "placements" not in vorher["display_config"]
    assert nachher["display_config"].get("placements") == soll.placements, \
        f"{pfad.name}: gespeicherte Tabelle != placements_from_legacy"
    assert _ohne_neue_stellen(nachher) == vorher, \
        f"{pfad.name}: ausser display_config.placements wurde etwas veraendert"


# ---------------------------------------------------------------------------
# AC-5: Trip mit show_outlook=false -> Ausblick aus, Grosswetterlage aus
# ---------------------------------------------------------------------------

#: Grosswetterlage-Zeile (von Hand, ``mail.stabilitaet.stabil``).
_GROSSWETTERLAGE = "Wetterlage: STABIL"


def _render_trip_alt(show_outlook: bool) -> dict:
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import trip_json

    d = trip_json(["gust", "temperature", "wind"], outlook_metrics=["gust", "temperature"],
                  report_config={"show_outlook": show_outlook, "show_stability": True,
                                 "multi_day_trend_reports": ["evening"]},
                  trip_id=f"ausblick-{str(show_outlook).lower()}")
    d["kind"] = "route"
    return d


def _trip_briefing(monkeypatch, data: dict) -> tuple[str, str]:
    from app.models import StabilityResult
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
        mail_teile, render_trip_mit_ausblick,
    )

    mit, _trip, _uid = render_trip_mit_ausblick(
        monkeypatch, data, report_type="evening", ausblick_nach_zeitplaner=True,
        stability_result=StabilityResult(label="STABIL", confidence_pct=82))
    html, plain = mail_teile(mit)
    return html, plain


def _migriert(tmp_path: Path, uid: str, abo: dict) -> dict:
    root = tmp_path / "data" / "users"
    pfad = _ablegen(root, uid, abo)
    rc, bericht = _lauf(root, tmp_path / "bak", execute=True)
    assert rc == 0, bericht
    return _lies(pfad)


def test_ac5_trip_show_outlook_false_ausblick_und_grosswetterlage_aus(tmp_path, monkeypatch):
    nachher = _migriert(tmp_path, U_A, _render_trip_alt(show_outlook=False))

    assert nachher["display_config"]["placements"]["outlook_reports"] == []
    assert nachher["report_config"]["show_stability"] is False
    html, plain = _trip_briefing(monkeypatch, nachher)
    for teil, text in (("HTML", html), ("Nur-Text", plain)):
        assert _GROSSWETTERLAGE not in text, f"{teil}: Grosswetterlage trotz show_outlook=false"
        assert "3-Tages-Ausblick" not in text, f"{teil}: Ausblick trotz show_outlook=false"


def test_ac5_gegenprobe_trip_show_outlook_true_zeigt_beides(tmp_path, monkeypatch):
    nachher = _migriert(tmp_path, U_A, _render_trip_alt(show_outlook=True))

    assert nachher["display_config"]["placements"]["outlook_reports"] == ["evening"]
    assert nachher["report_config"].get("show_stability") is True
    html, plain = _trip_briefing(monkeypatch, nachher)
    for teil, text in (("HTML", html), ("Nur-Text", plain)):
        assert _GROSSWETTERLAGE in text, f"{teil}: Grosswetterlage fehlt"
        assert "3-Tages-Ausblick" in text, f"{teil}: Ausblick fehlt"


# ---------------------------------------------------------------------------
# AC-6: Orte-Abo mit outlook_enabled=false -> kein Ausblick
# ---------------------------------------------------------------------------

_WIEN = ZoneInfo("Europe/Vienna")


@pytest.fixture
def orte_kette(monkeypatch):
    """Echter Orte-Versandweg; einzige Naehte: Wetter-Engine (echte Subklasse,
    feste Werte inkl. Ausblick-Stunden) und Transport-Mitschrift."""
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from tests.helpers.einstellung_gleich_mail_orte import _ausblick_fuer
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd._compare_kette_fixtures import TARGET_DATE, _WERTE, _dp, transport_einrichten

    def _ergebnis(locations, kwargs):
        from app.models import ThunderLevel
        from app.user import ComparisonResult, LocationResult

        res = []
        for i, loc in enumerate(list(locations)):
            w = _WERTE[loc.id]
            res.append(LocationResult(
                location=loc, score=90 - 7 * i, temp_max=w["temp_max"], temp_min=w["temp_min"],
                wind_max=w["wind_max"], gust_max=w["gust_max"], cloud_avg=w["cloud_avg"],
                sunny_hours=w["sunny_hours"], snow_depth_cm=w["snow_depth_cm"],
                snow_new_cm=w["snow_new_cm"], wind_direction_avg=250, precip_sum_mm=3.5,
                pop_max_pct=40, uv_index_max=6.0, thunder_level_max=ThunderLevel.NONE,
                visibility_min_m=8000, official_alerts=[],
                hourly_data=[_dp(9, w), _dp(12, w), _dp(15, w)],
                outlook_hourly_data=_ausblick_fuer(0 if loc.id == "loc-ibk" else 1)))
        return ComparisonResult(locations=res, time_window=kwargs.get("time_window", (9, 16)),
                                target_date=kwargs.get("target_date", TARGET_DATE),
                                created_at=datetime(2026, 7, 8, 4, 0, tzinfo=_WIEN))

    original = ce_mod.ComparisonEngine

    class Engine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations") or (args[0] if args else [])
            return _ergebnis(locations, kwargs)

    transport_einrichten(monkeypatch)
    monkeypatch.setattr(ce_mod, "ComparisonEngine", Engine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    return aufzeichner_installieren(monkeypatch)


def _orte_briefing(mit, preset: dict) -> list[str]:
    """Migriertes Orte-Abo bei einem frischen Nutzer ablegen und ueber den echten
    Weg versenden; Texte von HTML-, Nur-Text-Mail und Telegram."""
    from tests.tdd._compare_kette_fixtures import (
        briefing_senden, nutzer_anlegen, orte_anlegen, preset_ablegen, settings_fuer,
    )

    uid = nutzer_anlegen("premium")
    orte_anlegen(uid)
    preset_ablegen(uid, copy.deepcopy(preset))
    mit.leeren()
    briefing_senden(uid, preset["id"], settings_fuer(uid))
    mails, tg = mit.sendungen("email"), mit.sendungen("telegram")
    assert mails and tg, f"Vorbedingung: Mail und Telegram versendet: {mit!r}"
    return [mails[-1]["body"], mails[-1].get("plain_text_body") or "", tg[-1]["body"]]


def _orte_ausblick_alt(preset_id: str, **extra) -> dict:
    return _orte_alt(preset_id, extra={"send_telegram": True, **extra},
                     dc_extra={"outlook_metrics": ["gust", "temperature", "wind"]})


def test_ac6_orte_outlook_enabled_false_kein_ausblick(tmp_path, orte_kette):
    nachher = _migriert(tmp_path, U_B, _orte_ausblick_alt("orte-ohne", outlook_enabled=False))

    assert nachher["display_config"]["placements"]["outlook_reports"] == []
    for text in _orte_briefing(orte_kette, nachher):
        assert "3-Tages-Ausblick" not in text, "Orte-Briefing zeigt Ausblick trotz outlook_enabled=false"


def test_ac6_gegenprobe_orte_ausblick_an_bleibt(tmp_path, orte_kette):
    nachher = _migriert(tmp_path, U_B, _orte_ausblick_alt("orte-mit"))

    assert nachher["display_config"]["placements"]["outlook_reports"], "Ausblick muss an bleiben"
    texte = _orte_briefing(orte_kette, nachher)
    assert all("3-Tages-Ausblick" in t for t in texte), "Ausblick fehlt in Mail oder Telegram"


# ---------------------------------------------------------------------------
# AC-7 / AC-8: vorhandene Tabelle unangetastet, zweiter Lauf aendert nichts
# ---------------------------------------------------------------------------

def test_ac7_abo_mit_placements_bleibt_bytegleich(tmp_path):
    root, pfade = _bestand(tmp_path)
    vorher = pfade["b_schon"].read_bytes()

    rc, bericht = _lauf(root, tmp_path / "bak", execute=True)

    assert rc == 0
    assert pfade["b_schon"].read_bytes() == vorher, "Abo mit placements wurde geschrieben"
    assert "hat schon placements" in _zeile(bericht, U_B, "bert-schon")


def test_ac8_zweiter_lauf_aendert_nichts(tmp_path):
    root, _pfade = _bestand(tmp_path)
    rc1, _ = _lauf(root, tmp_path / "bak1", execute=True)
    assert rc1 == 0
    nach_erstem = _baum(root)

    rc2, bericht = _lauf(root, tmp_path / "bak2", execute=True)

    assert rc2 == 0
    assert _baum(root) == nach_erstem, "zweiter Lauf hat Daten veraendert"
    assert "wird umgerechnet" not in bericht, bericht
    for archiv in (tmp_path / "bak2").glob("*.tar.gz") if (tmp_path / "bak2").is_dir() else []:
        assert not _archiv_inhalt(archiv), f"zweiter Lauf legte Sicherung mit Inhalt an: {archiv}"


# ---------------------------------------------------------------------------
# AC-9: zwei Nutzer getrennt
# ---------------------------------------------------------------------------

def test_ac9_kein_datenuebertrag_zwischen_nutzern(tmp_path):
    root, pfade = _bestand(tmp_path)
    original = {U_A: {p.name: p.read_bytes() for p in (root / U_A / "briefings").glob("*.json")},
                U_B: {p.name: p.read_bytes() for p in (root / U_B / "briefings").glob("*.json")}}
    soll = {k: _umrechnung(p).placements for k, p in pfade.items()}

    rc, _ = _lauf(root, tmp_path / "bak", execute=True)

    assert rc == 0
    for uid in (U_A, U_B):
        dateien = sorted(p.name for p in (root / uid / "briefings").glob("*.json"))
        assert dateien == sorted(original[uid]), f"{uid}: Abo-Dateien veraendert/vermischt"
        for name, bytes_ in original[uid].items():
            assert _lies(root / uid / "briefings" / name)["id"] == json.loads(bytes_)["id"]
    for k, p in pfade.items():
        assert _lies(p)["display_config"]["placements"] == soll[k], f"{k}: fremde Tabelle"
    for uid, fremd in ((U_A, U_B), (U_B, U_A)):
        (archiv,) = _archive(tmp_path / "bak", uid)
        for name, inhalt in _archiv_inhalt(archiv).items():
            assert fremd not in name, f"Sicherung {uid} enthaelt Datei von {fremd}: {name}"
            assert inhalt in original[uid].values(), f"Sicherung {uid}: fremder Inhalt {name}"


# ---------------------------------------------------------------------------
# AC-10: fail-closed bei unerklaert und unlesbarer Datei
# ---------------------------------------------------------------------------

def _trip_unerklaert(trip_id: str) -> dict:
    """Doppelte SMS-Eintraege: die Umrechnung meldet ``unerklaert`` (SMS, Abend)."""
    return _trip_alt(trip_id, dc_extra={"channel_layouts": {"sms": [
        {"metric_id": "wind"}, {"metric_id": "wind"}, {"metric_id": "gust"}]}})


def test_ac10_problem_abos_bleiben_gesundes_wird_migriert(tmp_path):
    root = tmp_path / "data" / "users"
    raetsel = _ablegen(root, U_A, _trip_unerklaert("raetsel"))
    kaputt = _ablegen(root, U_A, '{"id": "kaputt", "kind": "route", "display_config": {',
                      name="kaputt")
    gesund = _ablegen(root, U_A, _trip_alt("gesund"))
    assert "unerklaert" in _arten(raetsel), "Vorbedingung: Umrechnung meldet unerklaert"
    vorher = {p: p.read_bytes() for p in (raetsel, kaputt)}
    soll_gesund = _umrechnung(gesund).placements

    rc, bericht = _lauf(root, tmp_path / "bak", execute=True)

    assert rc != 0, "Problem-Abos muessen den Lauf mit Exit ungleich 0 beenden"
    for p, b in vorher.items():
        assert p.read_bytes() == b, f"{p.name} wurde trotz Problem geschrieben"
    assert _lies(gesund)["display_config"].get("placements") == soll_gesund, \
        "gesundes Abo nicht (richtig) migriert"
    z_raetsel = _zeile(bericht, U_A, "raetsel")
    assert "Fehler" in z_raetsel and "unerklaert" in z_raetsel, z_raetsel
    z_kaputt = _zeile(bericht, U_A, "kaputt")
    assert "Fehler" in z_kaputt, z_kaputt
    grund = z_kaputt.split("Fehler", 1)[1].strip(" :-()")
    assert len(grund) >= 3, f"Grund fehlt: {z_kaputt}"
