"""AC-1/2/3/5/6 (#1765 Scheibe B1): ``run_comparison_parallel`` berechnet die
Orte eines Vergleichs GLEICHZEITIG und fuehrt sie POSITIONSTREU zusammen.

Spec: docs/specs/modules/fix_1765_b1_compare_vorschau_parallel.md

RED-Grund: ``src/services/comparison_parallel.py`` existiert nicht
(ModuleNotFoundError in jedem Test).

Kein Mock-Theater: substituiert wird ausschliesslich die teure Naht
``ComparisonEngine.run`` (braucht Live-Wetter, in der Kern-Schicht verboten) --
durch eine echte Subklasse, die ihr Ergebnis AUS den uebergebenen Orten baut
(Haus-Muster: tests/tdd/test_compare_preview_service.py:112-162). Die
Gleichzeitigkeit wird ueber eine Treffpunkt-Sperre nachgewiesen, NICHT ueber
Wanduhr-Zeitmessung (Muster: tests/unit/test_timezone_singleton_threadsicher.py:72-124).
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.user import SavedLocation

WORKTREE = Path(__file__).resolve().parents[2]
ZIELDATUM = date(2026, 7, 8)
ZEITSCHRANKE = 5.0  # Sekunden -- grosszuegig, aber endlich: ein serieller Lauf
#                     laeuft in die Sperre statt den Testlauf haengen zu lassen.


def _jetzt() -> datetime:
    """Schranken-Zeitbasis fuer AC-5: naive UTC, wie die Hausnorm #1345 sie fuer
    ``ComparisonResult.created_at`` vorschreibt (``utils.timezone._as_utc``
    deutet naive Werte als UTC, die Renderer rechnen sie darueber in Ortszeit
    um). NICHT ``datetime.now()``: die Root-conftest fixiert die Prozesszone auf
    ``America/St_Johns`` (-2:30), eine Schranke aus der Prozessuhr wuerde also
    die ZEITZONE messen statt die Zusicherung -- und der Pruefling darf sie
    nicht benutzen (tests/test_output_timezone_guard.py verbietet die nackte
    Umgebungsuhr im Entscheidungs-/Ausgabepfad)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ort(nummer: int) -> SavedLocation:
    return SavedLocation(
        id=f"loc-{nummer}", name=f"Ort {nummer}",
        lat=47.0 + nummer, lon=11.0 + nummer, elevation_m=1000,
    )


class _Protokoll:
    """Aufrufprotokoll der Engine-Naht (uebergebene Orte + Keyword-Argumente
    je Aufruf), threadsicher gesammelt."""

    def __init__(self) -> None:
        self.aufrufe: list[tuple[list[SavedLocation], dict]] = []
        self._sperre = threading.Lock()

    def vermerke(self, orte, kwargs) -> None:
        with self._sperre:
            self.aufrufe.append((orte, kwargs))

    def ids_je_aufruf(self) -> list[list[str]]:
        return [[o.id for o in orte] for orte, _ in self.aufrufe]


def _baustein(monkeypatch, protokoll: _Protokoll, haken=None, stempel=None):
    """Pruefling laden und die Engine-Naht durch eine echte Subklasse ersetzen.
    ``haken(ort)`` erzwingt Gleichzeitigkeit, Verzoegerung oder Ortsfehler,
    ``stempel`` setzt ein abweichendes ``created_at`` je Teilergebnis."""
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    import services.comparison_parallel as modul  # RED: existiert noch nicht

    # Pfadregel #1409: aus einem Worktree darf nicht die Hauptrepo-Kopie
    # geprueft werden -- sonst meldet dieser Test falsches Gruen.
    assert Path(modul.__file__).resolve().is_relative_to(WORKTREE), modul.__file__

    class StubEngine(ce_mod.ComparisonEngine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            orte = list(kwargs["locations"] if "locations" in kwargs else args[0])
            protokoll.vermerke(orte, dict(kwargs))
            for ort in orte:
                if haken is not None:
                    haken(ort)
            return ComparisonResult(
                locations=[
                    LocationResult(location=o, score=50, temp_max=20.0) for o in orte
                ],
                time_window=kwargs.get("time_window", (4, 19)),
                target_date=kwargs.get("target_date", ZIELDATUM),
                created_at=stempel if stempel is not None else datetime.now(),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", StubEngine)
    if hasattr(modul, "ComparisonEngine"):  # Modul-Level-Import des Prueflings
        monkeypatch.setattr(modul, "ComparisonEngine", StubEngine)
    return modul


def _lauf(modul, orte, **extra):
    return modul.run_comparison_parallel(
        locations=orte, time_window=(4, 19), target_date=ZIELDATUM, **extra
    )


def test_ac1_alle_orte_werden_gleichzeitig_berechnet(monkeypatch):
    """AC-1: Drei Orte melden sich an einer Treffpunkt-Sperre an. Nacheinander
    verarbeitet erreicht der zweite Ort den Treffpunkt nie -- die Sperre laeuft
    in ihre Zeitschranke und KEIN Ort kommt durch. Uhrunabhaengig, kein
    Zwischenzustand, der zufaellig gruen werden koennte."""
    orte = [_ort(i) for i in range(3)]
    treffpunkt = threading.Barrier(len(orte))
    durch: list[str] = []
    sperre = threading.Lock()

    def am_treffpunkt(ort):
        treffpunkt.wait(timeout=ZEITSCHRANKE)
        with sperre:
            durch.append(ort.id)

    ergebnis = _lauf(_baustein(monkeypatch, _Protokoll(), haken=am_treffpunkt), orte)

    assert sorted(durch) == [o.id for o in orte], (
        f"Nur {sorted(durch)} von {[o.id for o in orte]} erreichten den Treffpunkt "
        "-- die Orte werden nacheinander statt gleichzeitig berechnet (AC-1). "
        "Erwartet: ThreadPoolExecutor, max_workers=min(len(locations), 4), "
        "Vorbild services/stage_weather.py:170-183."
    )
    assert [lr.location.id for lr in ergebnis.locations] == [o.id for o in orte]
    assert all(lr.error is None for lr in ergebnis.locations), (
        "AC-1 verlangt ein VOLLSTAENDIGES Ergebnis fuer alle Orte: "
        f"{[(lr.location.id, lr.error) for lr in ergebnis.locations]}"
    )


def test_ac2_reihenfolge_bleibt_bei_gedrehter_fertigstellung(monkeypatch):
    """AC-2: Der ZUERST konfigurierte Ort braucht am laengsten, der ZULETZT
    konfigurierte am kuerzesten -- die Fertigstellungsreihenfolge ist damit
    gezielt gegen die Einreichungsreihenfolge gedreht. Ohne diese Drehung waere
    auch ein Anhaengen bei Fertigstellung zufaellig richtig."""
    orte = [_ort(i) for i in range(3)]
    start = threading.Barrier(len(orte))
    verzoegerung = {"loc-0": 0.30, "loc-1": 0.15, "loc-2": 0.0}
    fertig: list[str] = []
    sperre = threading.Lock()

    def gedreht(ort):
        start.wait(timeout=ZEITSCHRANKE)  # alle starten gemeinsam
        time.sleep(verzoegerung[ort.id])
        with sperre:
            fertig.append(ort.id)

    ergebnis = _lauf(_baustein(monkeypatch, _Protokoll(), haken=gedreht), orte)

    assert fertig == ["loc-2", "loc-1", "loc-0"], (
        f"Vorbedingung verletzt: Fertigstellungsreihenfolge {fertig} ist nicht "
        "gegen die Einreichungsreihenfolge gedreht -- ohne Drehung prueft die "
        "eigentliche Zusicherung nichts."
    )
    assert [lr.location.id for lr in ergebnis.locations] == [o.id for o in orte], (
        "AC-2: Die Orte muessen in der konfigurierten Reihenfolge erscheinen, "
        f"nicht in Fertigstellungsreihenfolge -- geliefert wurde "
        f"{[lr.location.id for lr in ergebnis.locations]}. Erwartet: indexierte "
        "Vorbelegung (fetched[idx] = ...), kein Anhaengen."
    )


def test_ac3_ein_ortsfehler_reisst_die_anderen_nicht_mit(monkeypatch):
    """AC-3: Genau ein Ort scheitert unerwartet. Die uebrigen behalten ihre
    vollstaendigen Daten, der betroffene erscheint MIT Fehler AN SEINER
    POSITION -- die Listenlaenge bleibt gleich."""
    orte = [_ort(i) for i in range(3)]

    def scheitert_in_der_mitte(ort):
        if ort.id == "loc-1":
            raise RuntimeError("Wetterdaten nicht abrufbar")

    ergebnis = _lauf(
        _baustein(monkeypatch, _Protokoll(), haken=scheitert_in_der_mitte), orte
    )

    assert [lr.location.id for lr in ergebnis.locations] == [o.id for o in orte], (
        "AC-3: Der gescheiterte Ort muss an seiner Position erscheinen, nicht "
        f"ausgelassen werden -- geliefert: {[lr.location.id for lr in ergebnis.locations]}"
    )
    assert ergebnis.locations[1].error, "Der gescheiterte Ort braucht eine Fehlermeldung"
    assert [ergebnis.locations[0].error, ergebnis.locations[2].error] == [None, None], (
        "AC-3: Ein einzelner fehlerhafter Ort darf die anderen nicht mitreissen"
    )
    assert [ergebnis.locations[0].temp_max, ergebnis.locations[2].temp_max] == [20.0, 20.0], (
        "AC-3: Die uebrigen Orte muessen ihre VOLLSTAENDIGEN Daten behalten"
    )


def test_ac4_der_baustein_setzt_die_quelle_im_worker_des_ortes(monkeypatch):
    """AC-4 am WIRKORT statt nur am Mechanismus. Die Mutations-Gegenprobe zeigte:
    laesst man den Quellen-Override IM BAUSTEIN weg, bleibt jeder Test gruen --
    test_call_source_ueber_threadgrenze.py prueft ``override_call_source``
    isoliert, nicht seine Verdrahtung. Hier wird die Quelle genauso ausgelesen,
    wie das Diagnose-Journal sie sieht: aus dem Thread, der den Abruf ausfuehrt.
    Ohne Override steht dort keiner der 11 Bestandsmarker -> "unbekannt"."""
    from providers.call_log import resolve_call_source

    orte = [_ort(i) for i in range(2)]
    gesehen: dict[str, str] = {}
    sperre = threading.Lock()

    def merkt_die_quelle(ort):
        with sperre:
            gesehen[ort.id] = resolve_call_source()

    _lauf(
        _baustein(monkeypatch, _Protokoll(), haken=merkt_die_quelle),
        orte,
        call_source="vergleich",
    )

    assert gesehen == {o.id: "vergleich" for o in orte}, (
        f"AC-4: Im Worker-Thread jedes Ortes wurde {gesehen} als Quelle "
        "aufgeloest -- der Baustein muss ``override_call_source(call_source)`` "
        "IM JEWEILIGEN Thread setzen (ein ThreadPoolExecutor reicht den Kontext "
        "nicht weiter)."
    )


def test_ac5_genau_ein_zeitstempel_fuer_den_ganzen_lauf(monkeypatch):
    """AC-5: ``created_at`` wird EINMAL vor dem Start gesetzt -- weder aus einem
    Teilergebnis uebernommen (haenge sonst an der Fertigstellungsreihenfolge)
    noch je Ort bzw. nach dem Lauf berechnet."""
    orte = [_ort(i) for i in range(2)]
    teil_stempel = datetime(2000, 1, 1, 0, 0)
    erster_eintritt: list[datetime] = []
    sperre = threading.Lock()

    def bremst(ort):
        with sperre:
            if not erster_eintritt:
                erster_eintritt.append(_jetzt())
        time.sleep(0.2)

    modul = _baustein(monkeypatch, _Protokoll(), haken=bremst, stempel=teil_stempel)
    vorher = _jetzt()
    ergebnis = _lauf(modul, orte)

    assert ergebnis.created_at != teil_stempel, (
        "AC-5: created_at wurde aus einem Ortsergebnis uebernommen -- der Wert "
        "haengt dann an der Einreichungs-/Fertigstellungsreihenfolge."
    )
    assert vorher <= ergebnis.created_at <= erster_eintritt[0], (
        f"AC-5: created_at ({ergebnis.created_at}) muss EINMAL vor dem Start der "
        f"parallelen Verarbeitung gesetzt werden -- der erste Ortslauf begann "
        f"{erster_eintritt[0]}, der Aufruf startete {vorher}."
    )


def test_ac6_tagesfenster_und_horizont_kommen_bei_jedem_ort_an(monkeypatch):
    """AC-6: JEDER Ort rechnet mit demselben Tagesfenster und Vorhersage-
    Zeitraum -- geprueft je Ort, nicht aggregiert und nicht nur am ersten."""
    orte = [_ort(i) for i in range(3)]
    erwartet = {"time_window": (6, 20), "forecast_hours": 72, "official_alerts_enabled": False}
    protokoll = _Protokoll()
    modul = _baustein(monkeypatch, protokoll)

    modul.run_comparison_parallel(locations=orte, target_date=ZIELDATUM, **erwartet)

    assert sorted(protokoll.ids_je_aufruf()) == [[o.id] for o in orte], (
        "Jeder Ort braucht GENAU EINEN eigenen Engine-Lauf, gesehen wurde: "
        f"{protokoll.ids_je_aufruf()}"
    )
    gesehen = {
        ort_liste[0].id: {k: kw.get(k) for k in erwartet}
        for ort_liste, kw in protokoll.aufrufe
    }
    assert gesehen == {o.id: erwartet for o in orte}, (
        f"AC-6: nicht jeder Ort bekam {erwartet}, sondern {gesehen} -- beim "
        "Aufteilen der Ortsliste darf kein Parameter verloren gehen."
    )


@pytest.mark.parametrize("anzahl", [0, 1])
def test_leere_und_ein_ort_liste_laufen_ohne_sperre_durch(monkeypatch, anzahl):
    """Randfaelle: ``min(len(locations), 4)`` ist bei LEERER Liste ein
    ungueltiger ``max_workers``-Wert (ValueError) -- abzufangen wie im Vorbild
    (stage_weather.py:172 ``if flat:``). Ein Ort darf in keine Sperre laufen."""
    orte = [_ort(i) for i in range(anzahl)]
    protokoll = _Protokoll()

    ergebnis = _lauf(_baustein(monkeypatch, protokoll), orte)

    assert [lr.location.id for lr in ergebnis.locations] == [o.id for o in orte]
    assert len(protokoll.aufrufe) == anzahl, (
        f"{anzahl} Ort(e) -> {anzahl} Engine-Laeufe, gezaehlt: {len(protokoll.aufrufe)}"
    )
    assert ergebnis.time_window == (4, 19) and ergebnis.target_date == ZIELDATUM
