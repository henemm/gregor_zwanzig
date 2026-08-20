"""TDD-RED (#1759): Radar-Beobachtung hebt die Vorhersage-Gewitterstufe im
engen Zeitfenster um ``now()`` an ("Beobachtung schlaegt Vorhersage").

SPEC: docs/specs/modules/feat_1759_radar_vorhersage_fusion.md (AC-1..AC-7)

RED-Grund: ``providers.thunder_enrichment`` kennt noch keinen
``_apply_radar_override()``. ``enrich_thunder()`` endet nach
``_fuse_thunder_levels()``; die Radar-Beobachtung erreicht ``dp.thunder_level``
nicht. Alle Tests, die eine Anhebung erwarten (AC-1, AC-4, AC-6, AC-7),
scheitern an der Stufen-Assertion; die Nicht-Wirkungs-Tests (AC-2, AC-3, AC-5)
sind Gegenproben, die nach der Implementierung gruen BLEIBEN muessen.

MOCK-FREI: injiziert wird ueber die BESTEHENDE DI-Seam
``RadarNowcastService(frame_source=...)`` (Vorbild
``tests/tdd/test_radar_capture_is_convective.py``) mit ECHTEN
``RadarFrame``-Objekten und einer echten ``RadarNowcastCacheService``-Instanz.
``is_convective`` entsteht dadurch aus der echten Ableitung in
``_derive_result()``, es wird nicht behauptet. Kein ``Mock``/``patch``/
``MagicMock``, kein Quelltext-String-Check.

BLITZDICHTE-EINGANG (AC-4) -- bewusste Praezisierung der Spec: ``NowcastResult``
traegt heute KEINE Blitzdichte (``services/radar_service.py``, Felder
``onset_minutes``/``intensity_label``/``source``/``frames``/``is_convective``/
``convective_checked``/``throttled``/``data_unavailable``). Der Test speist die
Blitzdichte daher ueber die real existierende Groesse
``ForecastDataPoint.lightning_density_per_km2_3h``. Die Override-Schwelle ist
laut Spec ("Known Limitations") noch nicht kalibriert und steht deshalb als
benannter PLATZHALTER hier im Test, getrennt von der Fusions-Leiter
``_LIGHTNING_*_MIN`` in ``output/metric_format.py``.

ZEITSTEMPEL-FALLE: ``ForecastDataPoint.__post_init__`` (``app/models.py:230``)
erzwingt die Hausnorm "naive UTC" -- ``dp.ts`` ist NIE tz-behaftet, auch wenn
man einen aware Wert uebergibt. Ein Fenster-Vergleich gegen
``datetime.now(timezone.utc)`` wirft deshalb ``TypeError``; der Prueflings-Code
muss ``_naiv_utc()`` (``thunder_enrichment.py:73``) benutzen.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import Location
from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel,
)
from output.metric_format import thunder_ordinal

# Ort in der Gewitter-Region EU_REST (``providers/thunder_routing.py``), damit
# der Test in jeder Zustaendigkeit dieselbe, quellenlose Ausgangslage hat.
# Je Test eine EIGENE Koordinate -- der Radar-Frame-Cache ist koordinatenbasiert,
# geteilte Koordinaten koennten Frames zwischen Tests verschleppen.
_EU_REST_LAT = 60.0

# Name der fuer EU_REST primaer zustaendigen Gewitterquelle. Als
# ``bereits_befragt`` uebergeben, damit ``_fetch_lightning_density()`` gar nicht
# erst abruft -- die Tests pruefen die Fusion/den Override, nicht den Abruf.
_PRIMAERQUELLE_EU_REST = "eu_direct"

# Blitzdichte-Werte gegen die Fusions-Leiter in ``output/metric_format.py``
# (``_LIGHTNING_LOW_MIN=0.003`` / ``_LIGHTNING_MED_MIN=0.015`` /
# ``_LIGHTNING_HIGH_MIN=0.075``), Blitze/km2/3h:
# _DICHTE_ERGIBT_LOW liegt zusaetzlich UNTER der Override-Schwelle weiter
# unten -- sonst loeste in AC-1/2/3/5/6/7 schon die Blitzdichte den Override
# aus und keiner dieser Tests wuerde die Auswertung von `is_convective`
# ueberhaupt noch bewachen.
_DICHTE_ERGIBT_LOW = 0.004     # >= LOW, < MED  -> Fusion allein: LOW
_DICHTE_ERGIBT_HIGH = 0.100    # >= HIGH        -> Fusion allein: HIGH

# PLATZHALTER (Spec "Known Limitations", noch nicht kalibriert): eigene
# Override-Schwelle, BEWUSST getrennt von der Fusions-Leiter oben. Der Testwert
# liegt zwischen LOW und MED der Fusion -- dadurch ist der Test diskriminierend:
# ohne Override bleibt die Stunde LOW, mit Override wird sie MED.
_OVERRIDE_BLITZDICHTE_SCHWELLE_PLATZHALTER = 0.005
_DICHTE_UEBER_OVERRIDE_SCHWELLE = 0.008


# ---------------------------------------------------------------------------
# Echte Bausteine (keine Mocks)
# ---------------------------------------------------------------------------

def _reihe(*dps: ForecastDataPoint) -> NormalizedTimeseries:
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=11.0),
        data=list(dps),
    )


def _dp(ts: datetime, *, blitzdichte: float | None = None) -> ForecastDataPoint:
    """Datenpunkt, dessen einziges Fusionssignal die Blitzdichte ist.

    ``cape_jkg``/Blitzpotenzial bleiben ``None`` -- deren Leitern haengen am
    Gebiet und wuerden das Ergebnis vom Routing abhaengig machen; die
    Blitzdichte-Leiter ist gebietsunabhaengig.
    """
    return ForecastDataPoint(ts=ts, lightning_density_per_km2_3h=blitzdichte)


def _konvektive_frames(now: datetime) -> list:
    from providers.brightsky import RadarFrame

    return [
        RadarFrame(timestamp=now + timedelta(minutes=10), precip_mm_h=6.0,
                   is_convective=True),
        RadarFrame(timestamp=now + timedelta(minutes=25), precip_mm_h=4.0,
                   is_convective=True),
    ]


def _nasse_aber_nicht_konvektive_frames(now: datetime) -> list:
    from providers.brightsky import RadarFrame

    return [
        RadarFrame(timestamp=now + timedelta(minutes=10), precip_mm_h=1.5,
                   is_convective=False),
    ]


def _radar_injizieren(monkeypatch, frames_fn) -> list:
    """Haengt ``frames_fn`` ueber die bestehende ``frame_source``-DI-Seam in den
    ECHTEN ``RadarNowcastService`` ein und liefert eine Aufrufliste zurueck.

    ``frames_fn(lat, lon) -> list[RadarFrame]`` darf auch werfen (AC-5).
    """
    from services import radar_service
    from services.radar_cache import RadarNowcastCacheService
    from services.radar_service import RadarNowcastService

    instanziierungen: list = []

    class _RadarMitEingespeistenFrames(RadarNowcastService):
        def __init__(self, *_args, **_kwargs):
            instanziierungen.append(1)
            super().__init__(
                frame_source=frames_fn,
                cache=RadarNowcastCacheService(),  # leer -> garantierter Cache-Miss
            )

    monkeypatch.setattr(
        radar_service, "RadarNowcastService", _RadarMitEingespeistenFrames,
    )
    # Falls der Prueflings-Code den Namen beim Import in sein eigenes Modul
    # gezogen hat, muss dort dieselbe Klasse stehen -- sonst liefe der Test
    # gegen die echte Quelle und waere kein Nachweis.
    from providers import thunder_enrichment

    if hasattr(thunder_enrichment, "RadarNowcastService"):
        monkeypatch.setattr(
            thunder_enrichment, "RadarNowcastService", _RadarMitEingespeistenFrames,
        )
    return instanziierungen


def _anreichern(reihe: NormalizedTimeseries, lon: float) -> None:
    from providers.thunder_enrichment import enrich_thunder

    enrich_thunder(
        reihe,
        Location(latitude=_EU_REST_LAT, longitude=lon, name="EU-REST-Testort"),
        bereits_befragt=_PRIMAERQUELLE_EU_REST,
    )


def _mindestens(level, schranke: ThunderLevel) -> bool:
    return level is not None and thunder_ordinal(level) >= thunder_ordinal(schranke)


# ---------------------------------------------------------------------------
# AC-1 bis AC-7
# ---------------------------------------------------------------------------

def test_ac1_konvektives_radar_hebt_niedrige_stunde_auf_mindestens_med(monkeypatch):
    now = datetime.now(timezone.utc)
    _radar_injizieren(monkeypatch, lambda la, lo: _konvektive_frames(now))
    reihe = _reihe(_dp(now, blitzdichte=_DICHTE_ERGIBT_LOW))

    _anreichern(reihe, lon=25.10)

    dp = reihe.data[0]
    assert _mindestens(dp.thunder_level, ThunderLevel.MED), (
        f"AC-1: Radar meldet Konvektion im Fenster um now(), die Fusion hatte "
        f"nur {ThunderLevel.LOW.value} -- erwartet mindestens "
        f"{ThunderLevel.MED.value}, ist aber {dp.thunder_level}."
    )


def test_ac2_konvektives_radar_senkt_eine_hohe_stunde_nicht(monkeypatch):
    now = datetime.now(timezone.utc)
    _radar_injizieren(monkeypatch, lambda la, lo: _konvektive_frames(now))
    reihe = _reihe(_dp(now, blitzdichte=_DICHTE_ERGIBT_HIGH))

    _anreichern(reihe, lon=25.20)

    dp = reihe.data[0]
    # Ohne diesen Nachweis waere die Assertion darunter trivial wahr: sie ist
    # heute schon erfuellt, weil ueberhaupt kein Override existiert. Erst der
    # Beleg, dass der Override gelaufen IST, macht "und hat nichts gesenkt"
    # zu einer Aussage.
    assert "radar" in (dp.thunder_level_signals or []), (
        f"AC-2: Der Override muss auch bei einer bereits hohen Stunde gelaufen "
        f"sein und seine Herkunft eintragen -- Herkunft ist "
        f"{dp.thunder_level_signals!r}."
    )
    assert dp.thunder_level == ThunderLevel.HIGH, (
        f"AC-2: Der Override ist ein Deckel nach UNTEN ('mindestens MED') und "
        f"darf eine bereits als {ThunderLevel.HIGH.value} fusionierte Stunde "
        f"weder senken noch veraendern -- ist {dp.thunder_level}."
    )


def test_ac3_konvektives_radar_wirkt_nicht_auf_datenpunkt_ausserhalb_des_fensters(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    zaehler = _radar_injizieren(monkeypatch, lambda la, lo: _konvektive_frames(now))
    # ZWEI Datenpunkte in EINER Reihe: der erste liegt im Fenster, der zweite
    # weit davor. Ohne den Nachbarn im Fenster waere "der ferne bleibt LOW"
    # trivial wahr (er ist es auch ganz ohne Override). Erst der Kontrast
    # bewacht die Fenstergrenze: faellt sie weg, kippt der ferne Punkt mit.
    im_fenster = _dp(now, blitzdichte=_DICHTE_ERGIBT_LOW)
    fern = _dp(now + timedelta(hours=6), blitzdichte=_DICHTE_ERGIBT_LOW)
    reihe = _reihe(im_fenster, fern)

    _anreichern(reihe, lon=25.30)

    assert _mindestens(im_fenster.thunder_level, ThunderLevel.MED), (
        f"AC-3-Kontrolle: der Datenpunkt IM Fenster muss angehoben sein, sonst "
        f"sagt der Vergleich mit dem fernen Punkt nichts -- ist "
        f"{im_fenster.thunder_level}."
    )
    assert fern.thunder_level == ThunderLevel.LOW, (
        f"AC-3: Der Datenpunkt liegt 6 h entfernt, also weit ausserhalb des "
        f"+/-90-Min-Fensters -- er muss beim Fusionsergebnis "
        f"{ThunderLevel.LOW.value} bleiben, ist aber {fern.thunder_level}."
    )
    assert "radar" not in (fern.thunder_level_signals or []), (
        f"AC-3: Auch die Herkunft des fernen Datenpunkts darf der Override "
        f"nicht anfassen -- ist {fern.thunder_level_signals!r}."
    )
    assert len(zaehler) == 1, (
        "AC-3/Performance-Gate: der Radar-Abruf laeuft 1x je Reihe, nicht je "
        f"Datenpunkt -- er lief {len(zaehler)}x."
    )


def test_ac4_blitzdichte_ueber_override_schwelle_loest_ohne_konvektionsflag_aus(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    _radar_injizieren(
        monkeypatch, lambda la, lo: _nasse_aber_nicht_konvektive_frames(now),
    )
    reihe = _reihe(_dp(now, blitzdichte=_DICHTE_UEBER_OVERRIDE_SCHWELLE))

    _anreichern(reihe, lon=25.40)

    dp = reihe.data[0]
    assert _DICHTE_UEBER_OVERRIDE_SCHWELLE >= _OVERRIDE_BLITZDICHTE_SCHWELLE_PLATZHALTER
    assert _mindestens(dp.thunder_level, ThunderLevel.MED), (
        f"AC-4: Radar meldet is_convective=False, aber die Blitzdichte "
        f"{_DICHTE_UEBER_OVERRIDE_SCHWELLE} liegt ueber der Override-Schwelle "
        f"{_OVERRIDE_BLITZDICHTE_SCHWELLE_PLATZHALTER} (Platzhalter, unkalibriert) "
        f"-- erwartet mindestens {ThunderLevel.MED.value}, ist {dp.thunder_level}. "
        f"Die reine Fusion ergibt bei dieser Dichte nur {ThunderLevel.LOW.value}."
    )


def test_ac5_fehlschlagender_radar_abruf_laesst_fusionsergebnis_stehen(monkeypatch):
    now = datetime.now(timezone.utc)

    def _wirft(_lat, _lon):
        raise RuntimeError("Radar-Quelle nicht erreichbar (AC-5)")

    zaehler = _radar_injizieren(monkeypatch, _wirft)
    reihe = _reihe(_dp(now, blitzdichte=_DICHTE_ERGIBT_LOW))

    _anreichern(reihe, lon=25.50)  # darf NICHT werfen

    dp = reihe.data[0]
    # Ohne diesen Nachweis waere "bleibt LOW" trivial wahr -- heute passiert
    # gar nichts. Erst der Beleg, dass der Abruf ueberhaupt versucht wurde,
    # macht "und wurde fail-soft aufgefangen" zu einer Aussage.
    assert len(zaehler) == 1, (
        "AC-5: Der Radar-Abruf muss versucht worden sein, sonst prueft der "
        f"Test kein Fail-soft-Verhalten -- er lief {len(zaehler)}x."
    )
    assert dp.thunder_level == ThunderLevel.LOW, (
        f"AC-5: Bei fehlschlagendem Radar-Abruf muss das Fusionsergebnis "
        f"{ThunderLevel.LOW.value} unveraendert stehen bleiben, ist aber "
        f"{dp.thunder_level}."
    )
    assert "radar" not in (dp.thunder_level_signals or []), (
        f"AC-5: Ein fehlgeschlagener Abruf darf keine Radar-Herkunft "
        f"vortaeuschen -- Herkunft ist {dp.thunder_level_signals!r}."
    )


def test_ac6_override_ergaenzt_radar_herkunft_ohne_bestehende_zutat_zu_loeschen(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    _radar_injizieren(monkeypatch, lambda la, lo: _konvektive_frames(now))
    reihe = _reihe(_dp(now, blitzdichte=_DICHTE_ERGIBT_LOW))

    _anreichern(reihe, lon=25.60)

    signale = reihe.data[0].thunder_level_signals or []
    assert "blitzdichte" in signale, (
        f"AC-6: Die von der 4-Signal-Fusion eingetragene Zutat 'blitzdichte' "
        f"darf der Override nicht ersetzen -- Herkunft ist {signale!r}."
    )
    assert "radar" in signale, (
        f"AC-6: Der Override muss seine eigene Herkunft 'radar' ZUSAETZLICH "
        f"eintragen -- Herkunft ist {signale!r}."
    )


def test_ac7_ortsvergleich_pfad_zeigt_dieselbe_anhebung_wie_der_trip_pfad(monkeypatch):
    """AC-7: Trip UND Ortsvergleich laufen ueber DENSELBEN Anschluss
    ``OpenMeteoProvider._enrich_thunder()`` (``providers/openmeteo.py:1089`` bzw.
    ``:1209``). Geprueft wird deshalb das Ergebnis dieses geteilten Anschlusses
    gegen das des direkten ``enrich_thunder()``-Aufrufs aus AC-1 -- gleiche
    Ausgangslage, gleiches Ergebnis, kein zweiter Codepfad.
    """
    from providers.openmeteo import OpenMeteoProvider

    now = datetime.now(timezone.utc)
    _radar_injizieren(monkeypatch, lambda la, lo: _konvektive_frames(now))

    reihe_trip = _reihe(_dp(now, blitzdichte=_DICHTE_ERGIBT_LOW))
    _anreichern(reihe_trip, lon=25.70)

    reihe_vergleich = _reihe(_dp(now, blitzdichte=_DICHTE_ERGIBT_LOW))
    OpenMeteoProvider()._enrich_thunder(
        reihe_vergleich,
        Location(latitude=_EU_REST_LAT, longitude=25.80, name="Vergleichsort"),
        bereits_befragt=_PRIMAERQUELLE_EU_REST,
    )

    stufe_vergleich = reihe_vergleich.data[0].thunder_level
    assert _mindestens(stufe_vergleich, ThunderLevel.MED), (
        f"AC-7: Der Ortsvergleichs-Lauf muss dieselbe Anhebung auf mindestens "
        f"{ThunderLevel.MED.value} zeigen wie der Trip-Pfad, ist aber "
        f"{stufe_vergleich}."
    )
    assert stufe_vergleich == reihe_trip.data[0].thunder_level, (
        f"AC-7: Trip- und Ortsvergleichs-Pfad muessen bei identischer "
        f"Ausgangslage identisch entscheiden -- Trip "
        f"{reihe_trip.data[0].thunder_level}, Vergleich {stufe_vergleich}."
    )


# ---------------------------------------------------------------------------
# Spec "Expected Behavior" / "Side effects": EIN zusaetzlicher Live-Abruf je
# Reihe -- nicht je Datenpunkt, und keiner ohne betroffenen Datenpunkt.
#
# Die Zaehler-Asserts in AC-3/AC-5 decken das NICHT ab: dort liegt jeweils
# genau EIN Datenpunkt im Fenster, dann sind "1x je Reihe" und "1x je
# Datenpunkt" zahlengleich und der Zaehler kann nicht unterscheiden. Beide
# Tests unten erzeugen die fehlende Varianz.
# ---------------------------------------------------------------------------

def test_ohne_datenpunkt_im_fenster_findet_gar_kein_radar_abruf_statt(monkeypatch):
    now = datetime.now(timezone.utc)
    zaehler = _radar_injizieren(monkeypatch, lambda la, lo: _konvektive_frames(now))
    # Beide Datenpunkte liegen weit ausserhalb des +/-90-Min-Fensters -- einer
    # davor, einer danach, damit der Test nicht nur eine Fensterkante trifft.
    reihe = _reihe(
        _dp(now - timedelta(hours=5), blitzdichte=_DICHTE_ERGIBT_LOW),
        _dp(now + timedelta(hours=5), blitzdichte=_DICHTE_ERGIBT_LOW),
    )

    _anreichern(reihe, lon=25.90)

    assert not zaehler, (
        "Liegt KEIN Datenpunkt im Fenster, darf der Radar-Abruf gar nicht "
        f"erst stattfinden (unnoetige Last je Briefing) -- er lief "
        f"{len(zaehler)}x."
    )
    assert [dp.thunder_level for dp in reihe.data] == [ThunderLevel.LOW] * 2, (
        f"Kontrolle: ohne Abruf darf sich keine Stufe aendern -- ist "
        f"{[dp.thunder_level for dp in reihe.data]}."
    )


def test_zwei_datenpunkte_im_fenster_loesen_nur_einen_radar_abruf_aus(monkeypatch):
    now = datetime.now(timezone.utc)
    zaehler = _radar_injizieren(monkeypatch, lambda la, lo: _konvektive_frames(now))
    # ZWEI Datenpunkte im Fenster (+0 und +60 Min, beide < 90 Min): erst damit
    # unterscheiden sich "je Reihe" (1) und "je Datenpunkt" (2) ueberhaupt.
    frueh = _dp(now, blitzdichte=_DICHTE_ERGIBT_LOW)
    spaet = _dp(now + timedelta(minutes=60), blitzdichte=_DICHTE_ERGIBT_LOW)
    reihe = _reihe(frueh, spaet)

    _anreichern(reihe, lon=26.00)

    assert _mindestens(frueh.thunder_level, ThunderLevel.MED) and _mindestens(
        spaet.thunder_level, ThunderLevel.MED
    ), (
        f"Kontrolle: BEIDE Datenpunkte muessen im Fenster liegen und angehoben "
        f"sein, sonst zaehlt der Test einen Abruf, den es nur fuer einen "
        f"Datenpunkt gab -- Stufen sind {frueh.thunder_level} / "
        f"{spaet.thunder_level}."
    )
    assert len(zaehler) == 1, (
        "Der Radar-Abruf laeuft EINMAL je Reihe, nicht je Datenpunkt (Spec "
        f"'Side effects') -- bei 2 Datenpunkten im Fenster lief er "
        f"{len(zaehler)}x."
    )
