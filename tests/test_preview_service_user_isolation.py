"""Kern-Schicht: die Trip-Vorschau liest ausschliesslich den GPX-Bestand des
anfragenden Nutzers, nie den des Kontos ``default`` (#2151 Scheibe A, #2057).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_a.md (AC-1, AC-2)

Defekt: ``PreviewService._build_report`` baut
``TripReportSchedulerService(self.settings)`` OHNE ``user_id``. Der Scheduler
faellt intern auf ``"default"`` zurueck und ``backfill_stage_distances`` liest
die Wegstrecke aus ``users/default/gpx`` -- egal, fuer wen die Vorschau
angefragt wurde (ADR-0003: Rueckfall auf ``default`` = Cross-User-Datenleck).

Nachweisform (Zwei-Nutzer-Belegung, ADR-0003): beide Konten tragen einen
AUFLOESBAREN, aber verschieden langen Track fuer dieselbe Etappe --
``default`` den Original-Track (Wegpunkt G2 bei 2.9 km), ``nutzer`` eine
abgeleitete Kopie mit eingefuegtem Umweg (G2 bei 4.0 km). Die Vorschau zeigt
die km-Spanne je Segment (Telegram ``Segment 1 · 0.0–X km``, E-Mail
``SEG 1 · … · km 0.0–X``). Welche Zahl dort steht, verraet also, WESSEN GPX
gelesen wurde -- gemessen an der Stelle, an der das Leck wirkt (sichtbare
Ausgabe), nicht an einem internen Argument.

Die SMS-Vorschau zeigt keine km-Angabe; ihr AC-1-Nachweis liest die nach
Nutzer geschluesselte Fehlschlag-Daempfung der Track-Aufloesung (siehe
``test_ac1_sms_vorschau_...``).

Kein Mock: echte GPX-Aufloesung, echtes ``save_trip``, isolierte Datenwurzel
(``tests/conftest.py::_isolate_data_root``), Demo-Modus (``FixtureProvider``)
haelt den Lauf netzfrei.
"""
from __future__ import annotations

import dataclasses
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.loader import get_data_dir, get_data_root, load_trip_from_dict, save_trip
from services import track_resolution
from services.preview_service import PreviewService
from services.track_resolution import resolve_stage_track_km

_FIXTURE_ROOT = (
    Path(__file__).resolve().parent / "fixtures" / "data_root" / "users" / "default"
)
_TRIP_JSON = _FIXTURE_ROOT / "trips" / "gr221-mallorca.json"
_GPX_TAG1 = (
    _FIXTURE_ROOT / "gpx" / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx"
)

# Planwert ohne GPX-Messung (Schaetzung aus den Wegpunkten) -- erscheint, wenn
# GAR KEIN Track aufgeloest wurde. Dient als Testaufbau-Wache.
_PLANWERT_SEG1_KM = "1.7"


@pytest.fixture(autouse=True)
def _frische_fehlschlag_daempfung(monkeypatch):
    """``_failed_lookups`` ist prozessweit, Schluessel ``(user_id, trip, stage)``.
    Ohne frische Menge wuerde ein frueherer Fehlschlag desselben Schluessels die
    Aufloesung in diesem Test still ueberspringen."""
    monkeypatch.setattr(track_resolution, "_failed_lookups", set())


def _heute_utc() -> date:
    # Im Test berechnet (nicht auf Modulebene): der FixtureProvider stempelt ab
    # UTC-Mitternacht des LAUFTAGS -- Import und Lauf koennen sonst auf
    # verschiedene Tage fallen (Zeitbomben-Muster #2186).
    return datetime.now(timezone.utc).date()


def _umweg_gpx_text() -> str:
    """Original-Track Tag 1 mit eingefuegtem Abstecher (~0.55 km hin und
    zurueck) nach dem 6. Trackpunkt: Wegpunkt-Zuordnung bleibt, alle Distanzen
    ab G2 wachsen um ~1.1 km."""
    gpx = _GPX_TAG1.read_text(encoding="utf-8")
    punkte = list(re.finditer(
        r'<trkpt lat="([\d.]+)" lon="([\d.]+)">.*?</trkpt>', gpx, re.S,
    ))
    anker = punkte[5]
    lat, lon = float(anker.group(1)), float(anker.group(2))
    abstecher = (
        f'\n<trkpt lat="{lat + 0.005:.6f}" lon="{lon:.6f}"><ele>400</ele></trkpt>\n'
        f"{anker.group(0)}\n"
    )
    return gpx[: anker.end()] + abstecher + gpx[anker.end():]


def _bestandstrip(user_id: str, heute: date):
    """GR221-Etappe 1, UNVERMESSEN, auf ``heute`` gezogen, beim Nutzer abgelegt."""
    trip = load_trip_from_dict(json.loads(_TRIP_JSON.read_text(encoding="utf-8")))
    stage1 = dataclasses.replace(trip.stages[0], date=heute)
    trip = dataclasses.replace(trip, stages=[stage1] + list(trip.stages[1:]))
    assert all(wp.distance_from_start_km is None for wp in trip.stages[0].waypoints)
    save_trip(trip, user_id=user_id)
    return trip


def _gpx_ablegen(user_id: str, name: str, text: str) -> Path:
    gpx_dir = get_data_dir(user_id) / "gpx"
    gpx_dir.mkdir(parents=True, exist_ok=True)
    ziel = gpx_dir / name
    ziel.write_text(text, encoding="utf-8")
    return gpx_dir


def _seg1_endkm(gpx_dir: Path, trip) -> str:
    """Erwartete Segment-1-Endmarke aus der ECHTEN Aufloesung des Bestands."""
    km = resolve_stage_track_km(trip.stages[0], gpx_dir)
    assert km is not None, f"Testaufbau: Track in {gpx_dir} nicht aufloesbar"
    return f"{km['G2']:.1f}"


def _seg1_endkm_telegram(bubbles: list[str]) -> str:
    treffer = [
        m.group(1) for b in bubbles
        for m in [re.search(r"Segment 1 · 0\.0–([\d.]+) km", b)] if m
    ]
    assert treffer, (
        "Testaufbau: keine Segment-1-km-Angabe in den Telegram-Bubbles -- "
        f"Wetterlauf leer? Bubbles: {[b[:60] for b in bubbles]}"
    )
    return treffer[0]


def _seg1_endkm_email(html: str) -> str:
    m = re.search(r"SEG 1 · [^<]*?km 0\.0–([\d.]+)", html)
    assert m, "Testaufbau: keine 'SEG 1 · … km 0.0–X'-Angabe in der E-Mail-Vorschau"
    return m.group(1)


def _zwei_konten_mit_verschiedenen_tracks(nutzer: str, heute: date):
    """``nutzer`` hat den Umweg-Track, ``default`` den Original-Track."""
    trip = _bestandstrip(nutzer, heute)
    eigen_dir = _gpx_ablegen(nutzer, "tag1-umweg.gpx", _umweg_gpx_text())
    fremd_dir = _gpx_ablegen("default", _GPX_TAG1.name, _GPX_TAG1.read_text(encoding="utf-8"))
    eigen_km, fremd_km = _seg1_endkm(eigen_dir, trip), _seg1_endkm(fremd_dir, trip)
    assert len({eigen_km, fremd_km, _PLANWERT_SEG1_KM}) == 3, (
        f"Testaufbau: Marken muessen unterscheidbar sein "
        f"(eigen={eigen_km}, fremd={fremd_km}, plan={_PLANWERT_SEG1_KM})"
    )
    return trip, eigen_km, fremd_km


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_ac1_telegram_vorschau_misst_mit_dem_gpx_des_anfragenden_nutzers():
    """AC-1 (Telegram).

    GIVEN ``nutzer-a`` und ``default`` mit je eigener, verschieden langer GPX
    WHEN  die Telegram-Vorschau fuer ``user_id="nutzer-a"`` gerendert wird
    THEN  stammt die Segment-km-Angabe aus der GPX von ``nutzer-a``.

    RED heute: der Scheduler liest ``users/default/gpx`` -- die Vorschau zeigt
    die Distanz des fremden Kontos.
    """
    heute = _heute_utc()
    trip, eigen_km, fremd_km = _zwei_konten_mit_verschiedenen_tracks("nutzer-a", heute)

    _subject, _body, bubbles = PreviewService().render_telegram_preview(
        trip.id, user_id="nutzer-a", report_type="morning",
        target_date=heute.isoformat(), demo=True,
    )

    gezeigt = _seg1_endkm_telegram(bubbles)
    assert gezeigt != fremd_km, (
        f"AC-1: die Vorschau fuer nutzer-a zeigt {gezeigt} km -- das ist die "
        f"Wegstrecke aus users/default/gpx (Cross-User-Leck, ADR-0003)"
    )
    assert gezeigt == eigen_km, (
        f"AC-1: erwartet die Messung aus dem GPX von nutzer-a ({eigen_km} km), "
        f"gezeigt wird {gezeigt} km"
    )


def test_ac1_email_vorschau_misst_mit_dem_gpx_des_anfragenden_nutzers():
    """AC-1 (E-Mail): wie oben, gemessen an der Segment-Zeile der HTML-Mail."""
    heute = _heute_utc()
    trip, eigen_km, fremd_km = _zwei_konten_mit_verschiedenen_tracks("nutzer-a", heute)

    html = PreviewService().render_email_preview(
        trip.id, user_id="nutzer-a", report_type="morning",
        target_date=heute.isoformat(), demo=True,
    )

    gezeigt = _seg1_endkm_email(html)
    assert gezeigt != fremd_km, (
        f"AC-1: die E-Mail-Vorschau fuer nutzer-a zeigt {gezeigt} km aus "
        f"users/default/gpx (Cross-User-Leck, ADR-0003)"
    )
    assert gezeigt == eigen_km, (
        f"AC-1: erwartet {eigen_km} km aus dem GPX von nutzer-a, gezeigt {gezeigt} km"
    )


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


def test_ac2_vorschau_ohne_konto_default_liefert_die_daten_des_angefragten_nutzers():
    """AC-2.

    GIVEN im Datenbestand existiert KEIN Konto ``default`` (kein Verzeichnis),
          ``nutzer-b`` hat Trip und passende GPX
    WHEN  SMS- und Telegram-Vorschau fuer ``user_id="nutzer-b"`` gerendert werden
    THEN  laufen beide fehlerfrei, die Messung stammt aus dem GPX von
          ``nutzer-b`` und unter ``users/default`` entsteht nichts.

    RED heute: der Scheduler sucht die GPX unter ``users/default/gpx``, findet
    dort nichts und faellt auf den Planwert zurueck -- die GPX des angefragten
    Nutzers wird nie gelesen.
    """
    heute = _heute_utc()
    default_dir = get_data_root() / "users" / "default"
    shutil.rmtree(default_dir, ignore_errors=True)
    assert not default_dir.exists(), "Testaufbau: Konto default darf nicht existieren"

    trip = _bestandstrip("nutzer-b", heute)
    eigen_dir = _gpx_ablegen("nutzer-b", _GPX_TAG1.name, _GPX_TAG1.read_text(encoding="utf-8"))
    eigen_km = _seg1_endkm(eigen_dir, trip)

    service = PreviewService()
    sms_subject, sms_text = service.render_sms_preview(
        trip.id, user_id="nutzer-b", report_type="morning",
        target_date=heute.isoformat(), demo=True,
    )
    assert "GR221" in sms_subject and sms_text, (
        f"AC-2: SMS-Vorschau fuer nutzer-b liefert nicht den Trip von nutzer-b: "
        f"{sms_subject!r} / {sms_text!r}"
    )

    _subject, _body, bubbles = service.render_telegram_preview(
        trip.id, user_id="nutzer-b", report_type="morning",
        target_date=heute.isoformat(), demo=True,
    )
    gezeigt = _seg1_endkm_telegram(bubbles)
    assert gezeigt == eigen_km, (
        f"AC-2: erwartet die Messung aus dem GPX von nutzer-b ({eigen_km} km), "
        f"gezeigt wird {gezeigt} km -- der Vorschau-Pfad hat den GPX-Bestand "
        f"des angefragten Nutzers nicht gelesen (sucht unter users/default)"
    )
    assert not default_dir.exists(), (
        "AC-2: die Vorschau fuer nutzer-b hat unter users/default etwas angelegt"
    )


def test_ac2_build_report_ohne_user_id_liest_nie_gpx_aus_konto_default():
    """AC-2 (direkter Pipeline-Aufruf ohne Nutzerbezug).

    GIVEN eine aufloesbare GPX liegt NUR unter ``users/default/gpx``
    WHEN  ``PreviewService._build_report`` OHNE ``user_id`` gerufen wird
    THEN  erscheint deren Messung nicht in der Vorschau -- ohne Nutzerbezug
          wird kein Nutzerordner gelesen (Planwert statt fremder GPX).
    """
    heute = _heute_utc()
    trip = _bestandstrip("nutzer-c", heute)
    fremd_dir = _gpx_ablegen("default", _GPX_TAG1.name, _GPX_TAG1.read_text(encoding="utf-8"))
    fremd_km = _seg1_endkm(fremd_dir, trip)
    assert fremd_km != _PLANWERT_SEG1_KM, "Testaufbau: Marken nicht unterscheidbar"

    report, _seg, _stage, _tz = PreviewService()._build_report(
        trip, heute, "morning", now_utc=datetime.now(timezone.utc), demo=True,
    )

    gezeigt = _seg1_endkm_email(report.email_html)
    assert gezeigt != fremd_km, (
        f"AC-2: _build_report ohne user_id zeigt {gezeigt} km -- das ist die "
        f"Messung aus users/default/gpx (verdeckter Rueckfall, ADR-0003)"
    )
    assert gezeigt == _PLANWERT_SEG1_KM, (
        f"AC-2: ohne Nutzerbezug erwartet der Planwert {_PLANWERT_SEG1_KM} km, "
        f"gezeigt {gezeigt} km"
    )


def test_ac1_sms_vorschau_sucht_die_gpx_im_ordner_des_anfragenden_nutzers():
    """AC-1 (SMS).

    GIVEN eine aufloesbare GPX liegt NUR unter ``users/default/gpx``,
          ``nutzer-a`` hat den Trip, aber keine passende GPX
    WHEN  die SMS-Vorschau fuer ``user_id="nutzer-a"`` gerendert wird
    THEN  wurde die Track-Aufloesung fuer ``nutzer-a`` gefuehrt (Fehlschlag-
          Daempfung traegt den Schluessel ``("nutzer-a", trip, stage)``) und
          nie fuer ``default``.

    Signal-Wahl: die SMS-Tokenzeile haengt im Demo-Modus nachweislich nicht
    von der Etappendistanz ab (gemessen: identischer Text bei 4 km und 43 km),
    daher wird die echte, nach Nutzer geschluesselte Daempfungsmenge
    ``track_resolution._failed_lookups`` gelesen -- sie haelt fest, WESSEN
    GPX-Ordner der SMS-Pfad durchsucht hat.
    """
    heute = _heute_utc()
    trip = _bestandstrip("nutzer-a", heute)
    _gpx_ablegen("default", _GPX_TAG1.name, _GPX_TAG1.read_text(encoding="utf-8"))
    stage_id = trip.stages[0].id

    _subject, sms_text = PreviewService().render_sms_preview(
        trip.id, user_id="nutzer-a", report_type="morning",
        target_date=heute.isoformat(), demo=True,
    )

    assert sms_text, "Testaufbau: SMS-Vorschau leer"
    gesucht = set(track_resolution._failed_lookups)
    assert ("default", trip.id, stage_id) not in gesucht, (
        "AC-1: die SMS-Vorschau fuer nutzer-a hat die GPX unter users/default "
        "gesucht (Cross-User-Leck, ADR-0003)"
    )
    assert ("nutzer-a", trip.id, stage_id) in gesucht, (
        f"AC-1: die SMS-Vorschau fuer nutzer-a hat den GPX-Ordner von nutzer-a "
        f"nie durchsucht (Nutzerbezug im SMS-Pfad verloren); gesucht: {gesucht}"
    )
