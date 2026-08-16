"""AC-1..AC-6/AC-8 (#1765 Scheibe B1b): Der VERSAND eines Vergleichs-Presets
verarbeitet seine Orte GLEICHZEITIG und liefert dabei dieselbe Mail wie zuvor.

Spec: docs/specs/modules/fix_1765_b1b_versand_sofortvergleich_parallel.md

RED-Grund: ``send_one_compare_preset`` ruft ``ComparisonEngine.run()`` mit der
VOLLEN Ortsliste auf (scheduler_dispatch_service.py:451) -- ein Aufruf,
nacheinander abgearbeitet. AC-1 (Treffpunkt) und AC-5 (ein Ort scheitert
systemisch) sind damit heute rot.

Pruefort = Wirkort: es laeuft der ECHTE ``send_one_compare_preset`` mit dem
ECHTEN Renderer; ersetzt sind nur die teuren Naehte -- Wetter-Engine (echte
Subklasse, kein Mock), Δ-Anker-Schnappschuss (holt Live-Nowcast) und Transport
(die im Bestand etablierte ``mail_sink``-Naht, Vorbild
tests/tdd/test_compare_dispatch_channel_fanout.py). Geprueft wird der
ZUGESTELLTE Mailkoerper, nicht das ``ComparisonResult``-Zwischenobjekt.
Gleichzeitigkeit ueber ``threading.Barrier``, NIE ueber Wanduhr-Dauer (Muster:
tests/unit/test_comparison_parallel.py:110-137).
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import date, datetime
from html import unescape
from pathlib import Path

import pytest

from app.config import Settings
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

WORKTREE = Path(__file__).resolve().parents[2]
ZIELDATUM = date(2026, 7, 8)
# Endlich, damit ein serieller Lauf in die Sperre laeuft statt den Testlauf
# haengen zu lassen -- und gross genug fuer echte Parallelitaet.
ZEITSCHRANKE = 5.0
PRESET_ID = "cp-1765-b1b"
ORTE = [
    SavedLocation(id="ort-a", name="Alphastadt", lat=47.2, lon=11.0, elevation_m=1000),
    SavedLocation(id="ort-b", name="Bravoberg", lat=46.5, lon=11.3, elevation_m=1100),
    SavedLocation(id="ort-c", name="Charliedorf", lat=46.0, lon=12.0, elevation_m=1200),
]
# Unverwechselbare, sonst nirgends vorkommende Werte: so ist die Zuordnung
# Ort->Wert im gerenderten Mailkoerper eindeutig nachweisbar (AC-4).
TEMP_JE_ORT = {"ort-a": 31.0, "ort-b": 42.0, "ort-c": 53.0}
MARKER_JE_ORT = {"ort-a": "31", "ort-b": "42", "ort-c": "53"}
# Fertigstellung gegen die Einreichung gedreht: der ZUERST konfigurierte Ort
# braucht am laengsten. Ohne diese Drehung waere auch ein Anhaengen bei
# Fertigstellung zufaellig richtig.
VERZOEGERUNG = {"ort-a": 0.30, "ort-b": 0.15, "ort-c": 0.0}


def _stundenpunkt(stunde: int) -> ForecastDataPoint:
    """Fuer alle Orte identisch -- die Stundentabellen duerfen die
    Wert-Zuordnung der Uebersicht (AC-4) nicht verrauschen."""
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, stunde, 0), t2m_c=20.0, wind_chill_c=19.0,
        wind10m_kmh=8.0, gust_kmh=19.0, precip_1h_mm=0.0, cloud_total_pct=35,
        uv_index=5.0, thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


def _settings() -> Settings:
    """E-Mail sendefaehig ohne Netz -- die Sink-Naht ersetzt den Transport
    vollstaendig. ``_env_file=None`` haelt den Test vom Zufallsinhalt einer
    lokalen .env fern (#1477)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid", _env_file=None,
    )


def _preset(user_id: str) -> dict:
    return {
        "id": PRESET_ID, "name": "Urlaubsorte", "user_id": user_id,
        "location_ids": [o.id for o in ORTE], "schedule": "daily",
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "forecast_hours": 48, "created_at": "2026-07-01T00:00:00Z",
        "kind": "vergleich",
    }


class _Postfach:
    """Zugestellte Mails (kein Mock): die Sink-Naht bekommt Betreff und den
    fertig gerenderten HTML-Koerper."""

    def __init__(self) -> None:
        self.zugestellt: list[dict] = []

    def __call__(self, **kwargs) -> None:
        self.zugestellt.append(kwargs)

    @property
    def koerper(self) -> str:
        assert self.zugestellt, "Es wurde keine Vergleichsmail zugestellt"
        return self.zugestellt[0]["body"]


@pytest.fixture
def versand_umgebung(tmp_path, monkeypatch):
    """Isolierter Daten-Root ueber BEIDE Zugriffsformen, damit kein Test am
    echten data/users/ vorbeischreibt (Muster
    tests/tdd/test_compare_dispatch_channel_fanout.py:113-138). Legt die
    Briefing-Datei an, in die ``save_compare_preset_status`` schreibt."""
    from app import loader as app_loader

    daten = tmp_path / "data"
    daten.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(daten))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(daten))
    except ImportError:  # pragma: no cover
        pass

    user_id = f"b1b-{uuid.uuid4().hex[:8]}"
    briefing = daten / "users" / user_id / "briefings" / f"{PRESET_ID}.json"
    briefing.parent.mkdir(parents=True, exist_ok=True)
    briefing.write_text(
        json.dumps({"id": PRESET_ID, "kind": "vergleich", "name": "Urlaubsorte"}),
        encoding="utf-8",
    )
    return user_id, daten, briefing


@pytest.fixture
def thread_fehler():
    """pytest meldet eine Ausnahme in einem Worker-Thread nur als WARNUNG -- ein
    Test kann gruen sein, waehrend ein Thread abstuerzt (in genau diesem
    Themenstrang schon passiert). Hier wird sie zum Testfehler."""
    gesammelt: list = []
    alt = threading.excepthook
    threading.excepthook = gesammelt.append
    yield gesammelt
    threading.excepthook = alt
    assert not gesammelt, (
        "Ausnahme(n) in Worker-Threads -- pytest haette sie nur als Warnung "
        f"gemeldet: {[(e.exc_type, e.exc_value) for e in gesammelt]}"
    )


def _engine_naht(monkeypatch, haken):
    """Die teure Wetter-Naht durch eine echte Subklasse ersetzen. ``haken(ort)``
    erzwingt Treffpunkt, Verzoegerung oder Ortsfehler. Die Werte kommen ueber
    ``loc.id`` -- NICHT ueber den Aufrufindex (AC-4): ein index-basierter Stub
    saehe nach dem Umbau bei jedem Aufruf nur noch Index 0 und verloere die
    Orts-Staffelung still."""
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from app.user import ComparisonResult, LocationResult

    # Pfadregel #1409: aus dem Worktree darf nicht die Hauptrepo-Kopie geprueft
    # werden -- sonst meldet dieser Test falsches Gruen.
    assert Path(sds_mod.__file__).resolve().is_relative_to(WORKTREE), sds_mod.__file__

    class _StubEngine(ce_mod.ComparisonEngine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            orte = list(kwargs["locations"] if "locations" in kwargs else args[0])
            teile = []
            for ort in orte:
                haken(ort)
                teile.append(LocationResult(
                    location=ort, score=50, temp_max=TEMP_JE_ORT[ort.id],
                    temp_min=5.0, wind_max=8.0, gust_max=19.0, cloud_avg=35,
                    sunny_hours=6, official_alerts=[],
                    hourly_data=[_stundenpunkt(9), _stundenpunkt(12)],
                ))
            return ComparisonResult(
                locations=teile, time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", ZIELDATUM),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _StubEngine)
    # Δ-Anker-Schnappschuesse holen echtes Nowcast-Wetter (Netz) -- im Kern
    # neutralisiert, nicht Pruefgegenstand (#1169, best-effort Nachlauf).
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


def _versand(user_id: str, daten: Path, postfach: _Postfach) -> tuple:
    from services.scheduler_dispatch_service import send_one_compare_preset

    return send_one_compare_preset(
        _preset(user_id), _settings(), user_id, str(daten),
        all_locations_cache=list(ORTE), target_date=ZIELDATUM, tage_ab_ortstag=0,
        mail_sink=postfach,
    )


def _drehung(fertig: list[str], erreicht: list[str]):
    """Haken: alle Orte starten gemeinsam, danach gestaffelt fertig. Seriell
    kann der Treffpunkt nicht zustande kommen und die Drehung entsteht nicht --
    sie wird deshalb erst gefordert, wenn sie moeglich ist (``erreicht``)."""
    treffpunkt = threading.Barrier(len(ORTE))
    sperre = threading.Lock()

    def haken(ort):
        try:
            treffpunkt.wait(timeout=ZEITSCHRANKE)
            with sperre:
                erreicht.append(ort.id)
        except threading.BrokenBarrierError:
            pass
        time.sleep(VERZOEGERUNG[ort.id])
        with sperre:
            fertig.append(ort.id)

    return haken


_TAG = re.compile(r"<[^>]+>")


def _tabellenzeilen(html: str) -> list[list[str]]:
    """Zellinhalte je Tabellenzeile des ZUGESTELLTEN Mailkoerpers."""
    zeilen = []
    for roh in re.findall(r"<tr\b.*?</tr>", html, re.S):
        zellen = [
            unescape(_TAG.sub(" ", z)).replace("\xa0", " ").strip()
            for z in re.findall(r"<t[dh]\b.*?</t[dh]>", roh, re.S)
        ]
        if zellen:
            zeilen.append(zellen)
    return zeilen


def _kopfzeile(html: str) -> list[str]:
    """Die Zeile der Uebersichtstabelle, die ALLE Ortsnamen fuehrt -- ihre
    Spaltenfolge ist die im Mailkoerper sichtbare Ortsreihenfolge."""
    for zellen in _tabellenzeilen(html):
        if all(o.name in " ".join(zellen) for o in ORTE):
            return zellen
    raise AssertionError(
        "Keine Tabellenzeile im zugestellten Mailkoerper fuehrt alle Orte "
        f"{[o.name for o in ORTE]}"
    )


def _spalte_je_ort(html: str) -> dict[str, int]:
    kopf = _kopfzeile(html)
    return {o.id: min(i for i, z in enumerate(kopf) if o.name in z) for o in ORTE}


def test_ac1_versand_verarbeitet_die_orte_gleichzeitig(
    versand_umgebung, monkeypatch, thread_fehler
):
    """AC-1: Drei Orte melden sich an einer Treffpunkt-Sperre an. Nacheinander
    verarbeitet erreicht der zweite Ort den Treffpunkt nie -- die Sperre laeuft
    in ihre Zeitschranke und KEIN Ort kommt durch. Uhrunabhaengig.
    Pflichtmutation: ``MAX_PARALLEL_LOCATIONS = 1`` muss den Test rot machen."""
    user_id, daten, _ = versand_umgebung
    treffpunkt = threading.Barrier(len(ORTE))
    durch: list[str] = []
    sperre = threading.Lock()

    def am_treffpunkt(ort):
        try:
            treffpunkt.wait(timeout=ZEITSCHRANKE)
        except threading.BrokenBarrierError:
            return
        with sperre:
            durch.append(ort.id)

    _engine_naht(monkeypatch, am_treffpunkt)
    postfach = _Postfach()
    _versand(user_id, daten, postfach)

    assert sorted(durch) == [o.id for o in ORTE], (
        f"Nur {sorted(durch)} von {[o.id for o in ORTE]} erreichten den "
        "Treffpunkt -- der Versand berechnet die Orte nacheinander statt "
        "gleichzeitig (AC-1). Erwartet: send_one_compare_preset ruft "
        "run_comparison_parallel(..., call_source='vergleich') statt "
        "ComparisonEngine.run (scheduler_dispatch_service.py:451)."
    )
    assert all(o.name in postfach.koerper for o in ORTE), (
        f"AC-1 verlangt eine VOLLSTAENDIGE Mail: {postfach.koerper[:400]!r}"
    )


def test_ac2_mail_zeigt_die_konfigurierte_ortsreihenfolge(
    versand_umgebung, monkeypatch, thread_fehler
):
    """AC-2: Bei gedrehter Fertigstellungsreihenfolge stehen die Orte im
    ZUGESTELLTEN Mailkoerper trotzdem in der konfigurierten Reihenfolge."""
    user_id, daten, _ = versand_umgebung
    fertig: list[str] = []
    erreicht: list[str] = []

    _engine_naht(monkeypatch, _drehung(fertig, erreicht))
    postfach = _Postfach()
    _versand(user_id, daten, postfach)

    if len(erreicht) == len(ORTE):  # gleichzeitig -- erst dann gibt es Drehung
        assert fertig == ["ort-c", "ort-b", "ort-a"], (
            f"Vorbedingung verletzt: Fertigstellung {fertig} ist nicht gegen "
            "die Einreichung gedreht -- ohne Drehung prueft die Zusicherung nichts."
        )
    spalten = _spalte_je_ort(postfach.koerper)
    assert sorted(spalten, key=spalten.get) == [o.id for o in ORTE], (
        "AC-2: Die Vergleichsmail muss die Orte in der KONFIGURIERTEN "
        f"Reihenfolge zeigen, geliefert wurden die Spalten {spalten} bei "
        f"Fertigstellung {fertig}."
    )


def test_ac3_persistierter_top_ort_ist_der_erste_konfigurierte(
    versand_umgebung, monkeypatch, thread_fehler
):
    """AC-3: ``top_ort`` stammt aus ``result.locations[0]``
    (scheduler_dispatch_service.py:460) -- auch bei gedrehter Fertigstellung
    muss der ERSTE KONFIGURIERTE Ort in ``briefings/<preset_id>.json`` landen."""
    user_id, daten, briefing = versand_umgebung
    fertig: list[str] = []

    _engine_naht(monkeypatch, _drehung(fertig, []))
    top_ort, _ = _versand(user_id, daten, _Postfach())

    gespeichert = json.loads(briefing.read_text(encoding="utf-8"))
    assert gespeichert.get("top_ort_letzter_versand") == ORTE[0].name, (
        "AC-3: persistiert wurde top_ort_letzter_versand="
        f"{gespeichert.get('top_ort_letzter_versand')!r}, erwartet der erste "
        f"konfigurierte Ort {ORTE[0].name!r} (Fertigstellung war {fertig})."
    )
    assert top_ort == ORTE[0].name, f"Rueckgabewert top_ort={top_ort!r}"


def test_ac4_jeder_ort_traegt_in_der_mail_seine_eigenen_werte(
    versand_umgebung, monkeypatch, thread_fehler
):
    """AC-4: Jeder Ort bekommt seinen EIGENEN Wert (nachgeschlagen ueber
    ``loc.id``) -- geprueft wird die Zuordnung Ort->Wert im zugestellten
    Mailkoerper. Schliesst die gemessene Luecke, dass KEIN Bestands-Test die
    Orts-Staffelung des Versandpfads bewacht."""
    user_id, daten, _ = versand_umgebung
    fertig: list[str] = []

    _engine_naht(monkeypatch, _drehung(fertig, []))
    postfach = _Postfach()
    _versand(user_id, daten, postfach)

    spalten = _spalte_je_ort(postfach.koerper)
    breite = len(_kopfzeile(postfach.koerper))
    treffer = [
        z for z in _tabellenzeilen(postfach.koerper)
        if len(z) == breite
        and all(any(m in zelle for zelle in z[1:]) for m in MARKER_JE_ORT.values())
    ]
    assert treffer, (
        f"Keine Uebersichtszeile fuehrt die Ortswerte {list(MARKER_JE_ORT.values())} "
        f"-- gerenderte Zeilen: {_tabellenzeilen(postfach.koerper)[:6]}"
    )
    zuordnung = {
        ort_id: MARKER_JE_ORT[ort_id] in treffer[0][spalte]
        for ort_id, spalte in spalten.items()
    }
    assert all(zuordnung.values()), (
        "AC-4: In der zugestellten Mail traegt nicht jeder Ort seinen eigenen "
        f"Wert. Spalten {spalten}, erwartet {MARKER_JE_ORT}, gerenderte Zeile "
        f"{treffer[0]}, Treffer je Ort {zuordnung}."
    )


def test_ac5_ein_gescheiterter_ort_reisst_die_mail_nicht_mit(
    versand_umgebung, monkeypatch, thread_fehler
):
    """AC-5: Genau ein Ort scheitert mit einer Ausnahme. Die Mail geht trotzdem
    raus und die beiden anderen Orte tragen ihre Werte.

    RED heute: seriell laeuft EIN Engine-Aufruf ueber alle drei Orte -- die
    Ausnahme des mittleren Orts reisst den gesamten Versand mit, es wird gar
    keine Mail zugestellt."""
    user_id, daten, _ = versand_umgebung

    def scheitert_in_der_mitte(ort):
        if ort.id == "ort-b":
            raise RuntimeError("Wetterdaten nicht abrufbar")

    _engine_naht(monkeypatch, scheitert_in_der_mitte)
    postfach = _Postfach()
    _versand(user_id, daten, postfach)

    assert len(postfach.zugestellt) == 1, (
        "AC-5: Ein einzelner gescheiterter Ort darf den Versand nicht "
        f"verhindern -- zugestellt wurden {len(postfach.zugestellt)} Mails."
    )
    for ort in (ORTE[0], ORTE[2]):
        assert ort.name in postfach.koerper and MARKER_JE_ORT[ort.id] in postfach.koerper, (
            f"AC-5: {ort.name} muss seine Werte behalten "
            f"({MARKER_JE_ORT[ort.id]} fehlt): {postfach.koerper[:400]!r}"
        )


def test_ac6_systemischer_ausfall_behaelt_fehlerform_und_schreibt_nichts(
    versand_umgebung, monkeypatch, thread_fehler
):
    """AC-6: Scheitern ALLE Orte, schlaegt der Versand mit derselben Fehlerform
    fehl wie vor der Umstellung (die Ausnahme erreicht den Aufrufer) und
    ``letzter_versand`` wird NICHT geschrieben."""
    user_id, daten, briefing = versand_umgebung

    def scheitert_immer(ort):
        raise RuntimeError("Wetterdienst nicht erreichbar")

    _engine_naht(monkeypatch, scheitert_immer)
    postfach = _Postfach()

    with pytest.raises(RuntimeError, match="nicht erreichbar"):
        _versand(user_id, daten, postfach)

    assert not postfach.zugestellt, (
        f"AC-6: Ohne jeden Ortswert darf keine Mail rausgehen, es waren "
        f"{len(postfach.zugestellt)}."
    )
    gespeichert = json.loads(briefing.read_text(encoding="utf-8"))
    assert "letzter_versand" not in gespeichert, (
        "AC-6: Nach einem systemischen Ausfall darf kein letzter_versand "
        f"persistiert werden, gefunden: {gespeichert.get('letzter_versand')!r}"
    )


def test_ac8_jeder_ortsabruf_traegt_die_quelle_vergleich(
    versand_umgebung, monkeypatch, thread_fehler
):
    """AC-8: Die Diagnose-Quelle wird dort ausgelesen, wo das Journal sie sieht
    -- im Thread, der den Abruf ausfuehrt. Nach dem Umbau taucht dort keiner der
    11 Stack-Marker mehr auf; nur ein ausdrueckliches ``call_source='vergleich'``
    ueberlebt den Threadwechsel. Pflichtmutation: ``call_source`` am Aufruf
    weglassen muss den Test rot machen."""
    from providers.call_log import resolve_call_source

    user_id, daten, _ = versand_umgebung
    gesehen: dict[str, str] = {}
    sperre = threading.Lock()

    def merkt_die_quelle(ort):
        with sperre:
            gesehen[ort.id] = resolve_call_source()

    _engine_naht(monkeypatch, merkt_die_quelle)
    _versand(user_id, daten, _Postfach())

    assert gesehen == {o.id: "vergleich" for o in ORTE}, (
        f"AC-8: Im Verarbeitungs-Thread jedes Ortes wurde {gesehen} als Quelle "
        "aufgeloest -- erwartet ueberall 'vergleich'. Der Versand muss "
        "call_source='vergleich' ausdruecklich setzen (ein ThreadPoolExecutor "
        "reicht den ContextVar-Kontext nicht an seine Arbeiter weiter)."
    )
