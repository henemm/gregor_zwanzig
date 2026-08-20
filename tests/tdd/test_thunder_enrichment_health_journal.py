"""TDD RED -- Issue #1581 Scheibe 1: Health-Journal der Gewitter-Direktquellen.

Spec: docs/specs/modules/fix_1581_enrichment_health.md (AC-1..AC-4, AC-12, AC-13).
Kontext: docs/context/fix-1581-anreicherung-health.md.

Deckt hier ab: AC-1 (Vertretung -> `fallback` + Ersatzquelle im `detail`),
AC-2 (stiller Rueckzug -> `unavailable`, DER Kern des Tickets), AC-3 (drei
getrennte Nicht-Fehler-Ausgaenge -> je eine `ok`-Zeile), AC-4 (defektes
Journal beeintraechtigt die Anreicherung nicht), AC-12 (auch die Vertretung
wirft -> `unavailable` aus dem aeusseren Fang), AC-13 (die bestehende
Warnmeldung ist tatsaechlich nachweisbar).

===========================================================================
Kein Mock-Theater
===========================================================================
Die Gewitterquellen werden durch FAKE-Provider vertreten, die
`providers.base.ThunderSignalProvider` strukturell erfuellen (Muster
tests/unit/test_thunder_source_substitution.py) -- kein `Mock()`, kein
`patch()`, kein `MagicMock`. Das Journal wird ECHT geschrieben (durch den
Prueflingspfad) und ECHT gelesen (JSONL geparst, Felder geprueft) -- kein
Substring-Test auf einen Dateiinhalt: hier IST die Datei das Verhalten.

Der gemeinsame Schreibbaustein `providers.enrichment_health.
log_enrichment_call` wird bewusst NICHT importiert und NICHT direkt gerufen.
Jede Zusicherung laeuft ueber den echten Anreicherungspfad in die echte
Journaldatei -- damit macht eine Verfaelschung des Bausteins (AC-11,
Mutations-Gegenprobe) sowohl DIESE Datei als auch
test_radar_nowcast_health_journal.py rot.

===========================================================================
Erwartete Rotfaerbung -- was rot ist und warum
===========================================================================
Rot sind alle Tests, die eine Journalzeile verlangen: AC-1, AC-2 (beide
Varianten), AC-3 (alle drei), AC-12 sowie der Datenwurzel-Waechter. Heute
existiert weder `src/providers/enrichment_health.py` noch ein Aufruf davon --
die Journaldatei entsteht nie, jede dieser Zusicherungen scheitert an
"keine Zeile fuer path='thunder'".

BEWUSST von Anfang an gruen sind zwei Waechter ueber bestehenden Code:
* AC-4 (Fail-soft): die Anreicherung schluckt heute schon jede Ausnahme --
  ohne Journal gibt es auch keinen Journalfehler. Der Test wird rot, sobald
  eine kuenftige Implementierung den Journal-Aufruf NICHT fail-soft haelt.
* AC-13 (Warnmeldung): `logger.warning("Gewitter-Anreicherung
  fehlgeschlagen")` steht bereits in `enrich_thunder()` -- er war bisher nur
  von keinem Test bewacht (F003 aus #1199). Der Test wird rot, sobald jemand
  ihn entfernt oder das Level absenkt.

Ausfuehrung:
    uv run pytest tests/tdd/test_thunder_enrichment_health_journal.py \
        --disable-socket --allow-unix-socket -v
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)
from providers import base, thunder_enrichment, thunder_routing  # noqa: E402

_ORT = Location(latitude=46.40, longitude=12.52, name="Testort")

# Journalpfad-Bestandteile -- bewusst als Bausteine, damit jeder Test den
# Pfad FRISCH aus der aktuellen Datenwurzel bildet (s. Falle #1633 unten).
_JOURNAL_UNTERPFAD = ("diagnostics", "enrichment_calls.jsonl")


# ---------------------------------------------------------------------------
# Fakes -- erfuellen providers.base.ThunderSignalProvider strukturell
# (uebernommen aus tests/unit/test_thunder_source_substitution.py, dort das
# Vorbild fuer #1492 S2a AC-1)
# ---------------------------------------------------------------------------

class _FakeBenannteQuelle:
    """Analog dwd.py/dwd_eu.py: bietet `fetch_thunder_signals_named`."""

    def __init__(
        self, name: str, *, wirft: bool = False,
        signale: Optional[Dict[str, Dict[int, float]]] = None,
    ) -> None:
        self._name = name
        self._wirft = wirft
        self._signale = signale or {}
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def fetch_thunder_signals(self, location, start=None, end=None):
        return {}

    def fetch_thunder_signals_named(self, location, start=None, end=None):
        self.call_count += 1
        if self._wirft:
            raise base.ThunderSourceUnavailableError(self._name, 1)
        return self._signale


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reihe(stunden: int = 4) -> NormalizedTimeseries:
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    data = [
        ForecastDataPoint(ts=start + timedelta(hours=h), t2m_c=12.3, wind10m_kmh=18.0)
        for h in range(1, stunden + 1)
    ]
    meta = ForecastMeta(provider=Provider.DWD, model="TEST", grid_res_km=2.2)
    return NormalizedTimeseries(meta=meta, data=data)


def _patch_provider(monkeypatch, mapping: dict) -> None:
    def _get(name):
        if name not in mapping:
            raise base.ProviderNotFoundError(name)
        return mapping[name]
    monkeypatch.setattr(base, "get_provider", _get, raising=True)


def _patch_quellen(monkeypatch, *namen: str) -> None:
    """Zwingt die Zustaendigkeitsaufloesung auf eine feste Quellenliste.

    Bewusst auf `thunder_providers_for` (die Liste, die
    `_fetch_lightning_density` wirklich liest) statt auf
    `thunder_provider_for` -- so kann keine ECHTE Zusatzquelle der Region
    (GeoSphere) unbemerkt mitfahren und eine zusaetzliche, im Test nicht
    erwartete Journalzeile erzeugen. Die Vertretungstabelle
    (`thunder_vertretung_for`, de_direct -> eu_direct) bleibt ECHT.
    """
    monkeypatch.setattr(
        thunder_routing, "thunder_providers_for",
        lambda lat, lon: tuple(namen), raising=True,
    )


def _journalpfad() -> Path:
    """Journalpfad, FRISCH aus der aktuell gesetzten Datenwurzel gebildet.

    Absichtlich eine Funktion und keine Modulkonstante: die
    Test-Isolationsfixture (`tests/conftest.py::_isolate_data_root`) biegt
    `app.loader._DATA_ROOT` erst pro Test um. Eine hier gebundene Konstante
    zeigte auf die falsche Wurzel -- dieselbe Falle #1633, die der Prueflingcode
    vermeiden muss.
    """
    from app.loader import get_data_root
    return get_data_root().joinpath(*_JOURNAL_UNTERPFAD)


def _zeilen(pfad: Optional[Path] = None) -> List[dict]:
    """Alle Journalzeilen als geparste Objekte (JSONL, keine Substring-Suche)."""
    pfad = pfad or _journalpfad()
    if not pfad.is_file():
        return []
    return [
        json.loads(zeile)
        for zeile in pfad.read_text().splitlines()
        if zeile.strip()
    ]


def _thunder_zeilen(pfad: Optional[Path] = None) -> List[dict]:
    return [z for z in _zeilen(pfad) if z.get("path") == "thunder"]


def _letzte_thunder_zeile(pfad: Optional[Path] = None) -> dict:
    zeilen = _thunder_zeilen(pfad)
    assert zeilen, (
        f"Keine Journalzeile mit path='thunder' in {pfad or _journalpfad()} -- "
        f"vorhandene Zeilen: {_zeilen(pfad)}. Ohne den Health-Schreibweg "
        f"(providers.enrichment_health.log_enrichment_call) entsteht die Datei "
        f"gar nicht erst."
    )
    return zeilen[-1]


# ---------------------------------------------------------------------------
# AC-1: Vertretung greift -> outcome="fallback", detail nennt die Ersatzquelle
# ---------------------------------------------------------------------------

def test_ac1_vertretung_schreibt_fallback_zeile_mit_ersatzquelle(monkeypatch):
    """AC-1: Primaerquelle `de_direct` wirft `ThunderSourceUnavailableError`,
    die echte Vertretungstabelle fuehrt auf `eu_direct`, der Ersatz-Fake
    liefert. Danach traegt die LETZTE thunder-Zeile `outcome="fallback"` UND
    `detail="eu_direct"`.

    Geprueft werden beide Felder, nicht bloss die Existenz einer Zeile: eine
    Implementierung, die zwar protokolliert, aber `fallback` nicht von `ok`
    unterscheidet (oder die Ersatzquelle nicht benennt), waere sonst nicht
    von einer korrekten zu trennen -- und genau die Ersatzquelle ist die
    Information, die aussen den Unterschied "laeuft noch, aber degradiert"
    traegt.

    Vorbedingung im Test: das Journal ist vorher LEER. Das ist zugleich die
    von der Spec verlangte Gegenprobe -- vor der Implementierung entsteht
    ueberhaupt keine Zeile.
    """
    assert _thunder_zeilen() == [], (
        "Testaufbau: Journal muss vor dem Abruf leer sein, sonst waere nicht "
        "unterscheidbar, ob die geprueft Zeile aus DIESEM Abruf stammt."
    )

    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: 42.0 for h in range(1, 5)}},
    )
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    # Vorbedingung: die Vertretung hat wirklich gegriffen (sonst pruefte der
    # Test unten eine Zeile zu einem Vorgang, der gar nicht stattfand).
    assert any(dp.lightning_potential_lpi_jkg == 42.0 for dp in reihe.data), (
        "Testaufbau: die Vertretung hat keine Werte geliefert -- die "
        "Journalzeile unten wuerde einen anderen Ausgang beschreiben."
    )

    zeile = _letzte_thunder_zeile()
    assert zeile.get("outcome") == "fallback", (
        f"AC-1: erwartet outcome='fallback' nach erfolgreicher Vertretung, "
        f"bekommen {zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )
    assert zeile.get("detail") == "eu_direct", (
        f"AC-1: `detail` muss die tatsaechlich verwendete Ersatzquelle "
        f"nennen ('eu_direct'), bekommen {zeile.get('detail')!r} "
        f"(ganze Zeile: {zeile})"
    )


# ---------------------------------------------------------------------------
# AC-2: stiller Rueckzug -> outcome="unavailable" (Kern des Tickets)
# ---------------------------------------------------------------------------

def test_ac2_stiller_rueckzug_ohne_vertretung_schreibt_unavailable(monkeypatch):
    """AC-2: `eu_direct` faellt aus und hat laut echter Vertretungstabelle
    KEINE Ersatzquelle (`thunder_vertretung_for('eu_direct') is None`) --
    `_fetch_primaerquelle` kehrt still zurueck.

    Heute hinterlaesst genau dieser Ausgang NICHTS: kein Journal, nicht
    einmal ein Log-Eintrag. Das ist der namensgebende Fall von Issue #1581.
    """
    # Vorbedingung: der Fall ist wirklich der stille Rueckzug, nicht ein
    # verkappter Vertretungsfall.
    assert thunder_routing.thunder_vertretung_for("eu_direct") is None, (
        "Testaufbau: fuer 'eu_direct' ist inzwischen eine Vertretung "
        "eingetragen -- dieser Test prueft dann nicht mehr den stillen Rueckzug."
    )

    reihe = _reihe()
    primaer = _FakeBenannteQuelle("eu_direct", wirft=True)
    _patch_quellen(monkeypatch, "eu_direct")
    _patch_provider(monkeypatch, {"eu_direct": primaer})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert primaer.call_count == 1, (
        f"Testaufbau: Primaerquelle wurde {primaer.call_count}x gerufen, "
        f"erwartet genau einmal."
    )
    assert all(dp.lightning_potential_lpi_jkg is None for dp in reihe.data), (
        "Testaufbau: es wurden Werte gefuellt -- dann war es kein Ausfall."
    )

    zeile = _letzte_thunder_zeile()
    assert zeile.get("outcome") == "unavailable", (
        f"AC-2: der stille Rueckzug (kein Ersatz verfuegbar) muss "
        f"outcome='unavailable' hinterlassen, bekommen "
        f"{zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )
    assert zeile.get("detail") is None, (
        f"AC-2: `detail` bleibt leer -- es gab keine Ersatzquelle zu nennen. "
        f"Bekommen: {zeile.get('detail')!r}"
    )


def test_ac2_ersatz_bereits_befragt_schreibt_unavailable(monkeypatch):
    """AC-2, zweite Auspraegung des stillen Rueckzugs: die Vertretung
    EXISTIERT (`de_direct` -> `eu_direct`), wurde diese Reihe aber schon
    befragt (`bereits_befragt='eu_direct'`) -- ein zweiter Abruf derselben
    Stunden waere Doppellast, also kehrt der Pfad ebenfalls still zurueck.

    Fachlich derselbe Befund wie oben: die Anreicherung hat nicht geliefert.
    Getrennt gefuehrt, weil er einen ANDEREN Zweig derselben Bedingung
    (`ersatz == bereits_befragt` statt `ersatz is None`) durchlaeuft -- eine
    Implementierung, die nur einen der beiden Zweige protokolliert, faellt
    sonst nicht auf.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: 7.0 for h in range(1, 5)}},
    )
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, "eu_direct")

    assert ersatz.call_count == 0, (
        f"Testaufbau: die bereits befragte Ersatzquelle wurde erneut gerufen "
        f"({ersatz.call_count}x) -- dann liegt kein stiller Rueckzug vor."
    )

    zeile = _letzte_thunder_zeile()
    assert zeile.get("outcome") == "unavailable", (
        f"AC-2: auch der Rueckzug 'Ersatz bereits befragt' muss "
        f"outcome='unavailable' hinterlassen, bekommen "
        f"{zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )


# ---------------------------------------------------------------------------
# AC-3: die drei Nicht-Fehler-Ausgaenge -> je genau eine "ok"-Zeile
# ---------------------------------------------------------------------------

def _pruefe_genau_eine_ok_zeile(ausgang: str) -> None:
    zeilen = _thunder_zeilen()
    assert len(zeilen) == 1, (
        f"AC-3 ({ausgang}): erwartet GENAU eine thunder-Zeile, bekommen "
        f"{len(zeilen)}: {zeilen}"
    )
    zeile = zeilen[0]
    assert zeile.get("outcome") == "ok", (
        f"AC-3 ({ausgang}): die Primaerquelle hat regulaer geantwortet, "
        f"erwartet outcome='ok', bekommen {zeile.get('outcome')!r} "
        f"(ganze Zeile: {zeile})"
    )
    assert zeile.get("detail") is None, (
        f"AC-3 ({ausgang}): `detail` bleibt leer ohne Vertretung, bekommen "
        f"{zeile.get('detail')!r}"
    )


def test_ac3_leere_antwort_schreibt_ok_zeile(monkeypatch):
    """AC-3, Ausgang 2 (`thunder_enrichment.py:412-413`): die Primaerquelle
    antwortet gueltig, aber ohne einen einzigen Wert ("kein Gewitter in
    Sicht"). Das ist ein ERFOLG, kein Ausfall -- `outcome='ok'`.

    Die Gegenprobe steckt in der Zusicherung selbst: waere hier
    `unavailable` gebucht, meldete jede ruhige Wetterlage einen Dauerausfall.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", signale={})
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert primaer.call_count == 1
    _pruefe_genau_eine_ok_zeile("leere, aber gueltige Antwort")


def test_ac3_nichts_gefuellt_schreibt_ok_zeile(monkeypatch):
    """AC-3, Ausgang 3 (`thunder_enrichment.py:415-417`): die Primaerquelle
    liefert Werte, aber zu Zeitpunkten ausserhalb der Reihe (`gefuellt == 0`).
    Auch das ist eine regulaere Antwort -- `outcome='ok'`.
    """
    reihe = _reihe()
    # Offset 99 liegt weit hinter dem letzten Datenpunkt (Offset 4) --
    # `_wende_eintraege_an` findet keinen passenden Zeitpunkt.
    primaer = _FakeBenannteQuelle("de_direct", signale={"lpi": {99: 55.0}})
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert all(dp.lightning_potential_lpi_jkg is None for dp in reihe.data), (
        "Testaufbau: es wurde doch ein Wert gesetzt -- dann ist es der "
        "Erfolgs-Ausgang und nicht der 'nichts gefuellt'-Ausgang."
    )
    _pruefe_genau_eine_ok_zeile("nichts gefuellt")


def test_ac3_erfolg_mit_primaerquelle_schreibt_ok_zeile(monkeypatch):
    """AC-3, Ausgang 4 (`thunder_enrichment.py:419-423`): die Primaerquelle
    liefert und fuellt -- der Normalfall. `outcome='ok'`, und ausdruecklich
    NICHT `fallback`: es war keine Vertretung im Spiel.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle(
        "de_direct", signale={"lpi": {h: 13.0 for h in range(1, 5)}},
    )
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert any(dp.lightning_potential_lpi_jkg == 13.0 for dp in reihe.data), (
        "Testaufbau: die Primaerquelle hat nichts gefuellt -- dann prueft "
        "dieser Test den falschen Ausgang."
    )
    _pruefe_genau_eine_ok_zeile("Erfolg mit Primaerquelle")


# ---------------------------------------------------------------------------
# AC-4: defektes Journal darf die Anreicherung nicht beeintraechtigen
# ---------------------------------------------------------------------------

def test_ac4_defektes_journal_laesst_signalwerte_unveraendert(monkeypatch):
    """AC-4: Derselbe Vertretungsfall wie AC-1 laeuft zweimal -- einmal mit
    beschreibbarem Journal, einmal mit einem Journalpfad, der ein
    VERZEICHNIS ist (jeder Schreibversuch scheitert mit IsADirectoryError).

    Geprueft werden die SIGNALFELDER, nicht das Journal: die Vorhersage muss
    zeichengleich dieselbe sein, und es darf keine Ausnahme nach aussen
    dringen. Diagnose darf den Abruf nie beeintraechtigen.

    Hinweis zur Rotfaerbung: dieser Waechter ist heute gruen -- ohne
    Journal-Aufruf gibt es keinen Journalfehler. Er wird rot, sobald eine
    Implementierung den Schreibweg NICHT fail-soft haelt (fehlendes
    try/except in `log_enrichment_call` oder ein Aufruf ausserhalb davon).
    """
    def _lauf() -> tuple:
        reihe = _reihe()
        primaer = _FakeBenannteQuelle("de_direct", wirft=True)
        ersatz = _FakeBenannteQuelle(
            "eu_direct", signale={"lpi": {h: 42.0 for h in range(1, 5)}},
        )
        _patch_quellen(monkeypatch, "de_direct")
        _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})
        thunder_enrichment.enrich_thunder(reihe, _ORT, None)
        return (
            tuple(dp.lightning_potential_lpi_jkg for dp in reihe.data),
            tuple(dp.thunder_level for dp in reihe.data),
            reihe.meta.fallback_model,
            reihe.meta.fallback_reason,
            tuple(reihe.meta.fallback_metrics),
        )

    referenz = _lauf()
    assert 42.0 in referenz[0], (
        f"Testaufbau: der fehlerfreie Lauf hat keine Ersatzwerte gefuellt "
        f"({referenz[0]}) -- der Vergleich unten waere dann nichtssagend."
    )

    # Journalpfad in ein Verzeichnis verwandeln: jeder Anhaenge-Versuch
    # scheitert ab jetzt hart.
    pfad = _journalpfad()
    if pfad.exists():
        pfad.unlink()
    pfad.mkdir(parents=True)
    assert pfad.is_dir()

    mit_defekt = _lauf()  # darf nicht werfen

    assert mit_defekt == referenz, (
        f"AC-4: bei defektem Journal weichen die Vorhersagewerte ab.\n"
        f"  ohne Journalfehler: {referenz}\n"
        f"  mit  Journalfehler: {mit_defekt}"
    )


# ---------------------------------------------------------------------------
# AC-12: auch die Vertretung wirft -> unavailable aus dem aeusseren Fang
# ---------------------------------------------------------------------------

def test_ac12_auch_vertretung_wirft_schreibt_unavailable(monkeypatch):
    """AC-12: Primaerquelle UND Vertretung werfen
    `ThunderSourceUnavailableError`. Die Ausnahme propagiert bis in den
    aeusseren Fang von `enrich_thunder()` (Zeilen 279-281) -- der im Issue
    #1581 als "einziger Beobachtungspunkt" benannte Ausgang.

    Drei Zusicherungen: (a) die Journalzeile existiert mit
    `outcome='unavailable'`, (b) `enrich_thunder()` gibt keine Ausnahme nach
    aussen, (c) die uebrigen Vorhersagewerte sind identisch zu einem Lauf
    ganz OHNE zustaendige Gewitterquelle -- die Anreicherung hat die
    Vorhersage also nicht beschaedigt.
    """
    # (c) Referenz: derselbe Aufbau, aber gar keine zustaendige Quelle.
    referenz_reihe = _reihe()
    _patch_quellen(monkeypatch)  # leere Quellenliste
    thunder_enrichment.enrich_thunder(referenz_reihe, _ORT, None)
    referenz = [
        (dp.t2m_c, dp.wind10m_kmh, dp.thunder_level,
         dp.lightning_potential_lpi_jkg, dp.lightning_density_per_km2_3h)
        for dp in referenz_reihe.data
    ]
    assert _thunder_zeilen() == [], (
        "Testaufbau: der Referenzlauf ohne zustaendige Quelle darf keine "
        "Journalzeile erzeugen (kein Abrufversuch = kein Eintrag)."
    )

    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle("eu_direct", wirft=True)
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    # (b) kein Wurf nach aussen -- ein Fehler hier ist die Aussage selbst.
    thunder_enrichment.enrich_thunder(reihe, _ORT, None)

    assert primaer.call_count == 1 and ersatz.call_count == 1, (
        f"Testaufbau: erwartet je ein Abrufversuch, bekommen primaer="
        f"{primaer.call_count}, ersatz={ersatz.call_count} -- ohne den "
        f"zweiten Wurf laeuft der geprueft Ausgang nicht an."
    )

    # (c) Vorhersage unbeschaedigt
    ergebnis = [
        (dp.t2m_c, dp.wind10m_kmh, dp.thunder_level,
         dp.lightning_potential_lpi_jkg, dp.lightning_density_per_km2_3h)
        for dp in reihe.data
    ]
    assert ergebnis == referenz, (
        f"AC-12: die gescheiterte Anreicherung hat die Vorhersage veraendert.\n"
        f"  ohne Gewitterquelle: {referenz}\n"
        f"  nach Doppelausfall:  {ergebnis}"
    )

    # (a) Journalzeile
    zeile = _letzte_thunder_zeile()
    assert zeile.get("outcome") == "unavailable", (
        f"AC-12: wirft auch die Vertretung, muss der aeussere Fang eine "
        f"Zeile mit outcome='unavailable' hinterlassen, bekommen "
        f"{zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )


# ---------------------------------------------------------------------------
# AC-13: die bestehende Warnmeldung ist nachweisbar
# ---------------------------------------------------------------------------

def test_ac13_warnmeldung_bei_gescheiterter_anreicherung(monkeypatch, caplog):
    """AC-13 (Punkt 5 des Issues, F003 aus #1199): scheitert die
    Anreicherung, MUSS `enrich_thunder()` die Warnmeldung
    "Gewitter-Anreicherung fehlgeschlagen" auf Level WARNING ausgeben.

    Hinweis zur Rotfaerbung: der `logger.warning` existiert bereits -- der
    Test ist heute gruen. Er war bisher nur von keinem Test bewacht, genau
    das ist der Nebenbefund. Er wird rot, wenn jemand den Aufruf entfernt
    oder auf DEBUG/INFO absenkt.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle("eu_direct", wirft=True)
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    with caplog.at_level(logging.WARNING, logger="thunder_enrichment"):
        thunder_enrichment.enrich_thunder(reihe, _ORT, None)

    treffer = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING
        and "Gewitter-Anreicherung fehlgeschlagen" in r.getMessage()
    ]
    assert treffer, (
        f"AC-13: keine WARNING-Meldung 'Gewitter-Anreicherung fehlgeschlagen' "
        f"im Mitschnitt. Aufgezeichnet wurde: "
        f"{[(r.levelname, r.name, r.getMessage()) for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# Falle #1633: der Journalpfad muss bei JEDEM Aufruf frisch aufgeloest werden
# ---------------------------------------------------------------------------

def test_journalpfad_folgt_der_datenwurzel_bei_jedem_aufruf(monkeypatch, tmp_path):
    """Spec, Dependencies: "Journalpfad wird bei JEDEM Aufruf frisch
    aufgeloest, nie ueber eine Modulkonstante (Falle #1633)".

    Der Test verlegt die Datenwurzel MITTEN im Test -- nach einem bereits
    erfolgten Abruf -- und verlangt, dass die naechste Zeile in der NEUEN
    Wurzel landet und die alte Datei nicht mehr waechst.

    Eine Implementierung mit Modulkonstante (`_JOURNAL = get_data_root() /
    ...` auf Modulebene, ausgewertet beim Import) bekommt diesen Test NICHT
    gruen: sie schriebe beide Zeilen an dieselbe, beim Import gebundene
    Stelle. Dasselbe gilt fuer jede Form von Zwischenspeicherung
    (`lru_cache`, Modulvariable, Vorberechnung im Konstruktor).
    """
    from app import loader

    def _abruf():
        reihe = _reihe()
        primaer = _FakeBenannteQuelle(
            "de_direct", signale={"lpi": {h: 21.0 for h in range(1, 5)}},
        )
        _patch_quellen(monkeypatch, "de_direct")
        _patch_provider(monkeypatch, {"de_direct": primaer})
        thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    _abruf()
    erste_wurzel_pfad = _journalpfad()
    assert len(_thunder_zeilen(erste_wurzel_pfad)) == 1, (
        f"Testaufbau/Vorbedingung: erwartet eine Zeile in der ersten "
        f"Datenwurzel {erste_wurzel_pfad}, bekommen "
        f"{_thunder_zeilen(erste_wurzel_pfad)}"
    )

    zweite_wurzel = tmp_path / "zweite-datenwurzel"
    zweite_wurzel.mkdir()
    monkeypatch.setattr(loader, "_DATA_ROOT", str(zweite_wurzel), raising=False)
    zweiter_pfad = _journalpfad()
    assert zweiter_pfad != erste_wurzel_pfad, (
        "Testaufbau nicht diskriminierend: beide Wurzeln ergeben denselben "
        "Pfad."
    )

    _abruf()

    assert len(_thunder_zeilen(zweiter_pfad)) == 1, (
        f"Falle #1633: nach dem Umbiegen der Datenwurzel muss die neue Zeile "
        f"unter {zweiter_pfad} liegen -- gefunden: "
        f"{_thunder_zeilen(zweiter_pfad)}. Eine beim Import gebundene "
        f"Modulkonstante schreibt stattdessen weiter in die alte Wurzel."
    )
    assert len(_thunder_zeilen(erste_wurzel_pfad)) == 1, (
        f"Falle #1633: die alte Journaldatei {erste_wurzel_pfad} ist "
        f"weitergewachsen ({_thunder_zeilen(erste_wurzel_pfad)}) -- der Pfad "
        f"wird also nicht bei jedem Aufruf frisch aufgeloest."
    )


# ---------------------------------------------------------------------------
# Struktur der Journalzeile -- gemeinsames Schema beider Pfade
# ---------------------------------------------------------------------------

def test_journalzeile_traegt_zeitstempel_pfad_und_ausgang(monkeypatch):
    """Die Go-Leseseite (`aggregateEnrichmentCalls`) gruppiert nach `path`
    und sortiert nach `ts`. Fehlt eines der beiden Felder, liefert sie
    stillschweigend ein leeres bzw. falsch sortiertes Aggregat -- deshalb
    hier die Feldstruktur einer echten, vom Prueflingspfad geschriebenen
    Zeile, geparst statt per Substring gesucht.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle(
        "de_direct", signale={"lpi": {h: 8.0 for h in range(1, 5)}},
    )
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    zeile = _letzte_thunder_zeile()
    for feld in ("ts", "path", "outcome", "detail"):
        assert feld in zeile, (
            f"Journalzeile ohne Feld {feld!r}: {zeile}. Die Go-Leseseite "
            f"gruppiert nach 'path' und sortiert nach 'ts'."
        )
    ts = datetime.fromisoformat(zeile["ts"])
    assert ts.tzinfo is not None, (
        f"Zeitstempel {zeile['ts']!r} traegt keine Zeitzone -- die "
        f"Go-Leseseite vergleicht RFC3339-Werte lexikografisch, ein naiver "
        f"Stempel sortiert dabei falsch."
    )
    abstand = abs((datetime.now(timezone.utc) - ts).total_seconds())
    assert abstand < 300, (
        f"Zeitstempel {zeile['ts']!r} liegt {abstand:.0f}s von jetzt entfernt "
        f"-- erwartet der Zeitpunkt des Abrufs."
    )
