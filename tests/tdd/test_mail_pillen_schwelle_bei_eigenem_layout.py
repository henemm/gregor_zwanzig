"""TDD RED — #2422 S3, AC-16: die Mail-Pillen folgen der eingestellten Schwelle
auch bei eigenem E-Mail-Layout.

SPEC: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md — AC-16, „Mail-
Pillen-Schwelle (Fix AC-16)", Mutation M10, verworfene-Befund Verdikt 2b.

Ausgangslage (Golden D): das E-Mail-Layout traegt KEINE ``sms_threshold``; die
GLOBALE Auswahl traegt Regen 0,1 mm / Regenwahrscheinlichkeit 10. ``trip_report``
kollabiert ``dc`` auf die E-Mail-Layout-Liste (Eintraege ohne Schwelle), danach
liest der Pillen-Bau die Schwelle aus DIESEM ``dc``. Ergebnis: Regen 0,15 mm
zeigt die Pille „Regen ges. 0.1 mm" statt des Ereignisses „Regen ab HH:00 · X mm"
— die SMS meldet Regen, die Mail nicht.

Drei Formen (= drei Renderer-Einstiege ``render_html``/``render_plain``/
``render_compact``), erreicht ueber den echten Trip-Report-Weg
(``TripReportFormatter.format_email``, ohne ihn koennte die Kollabierung in
``trip_report.py`` nie beobachtet werden):

* ``html``    — ``email_format=full``, ``TripReport.email_html``
* ``plain``   — ``email_format=full``, ``TripReport.email_plain``
* ``compact`` — ``email_format=compact`` (Golden D), ``TripReport.email_plain``
  (die kompakte Form hat KEIN HTML)

Zusaetzlich der Weg durch ``send_due_reports`` (Golden D, Morgen-Slot, echter
Scheduler, Wetter ueber die Fixture-Naht ``GZ_TEST_FIXTURE_DIR`` mit 0,15 mm,
Aufzeichner an den Kanal-Ausgaengen — nichts geht hinaus).

Erkennung der Regen-Pille: NUR im Pillenblock („Metriken-Überblick"; Klartext
``━━ Metriken-Überblick ━━``, Kompaktform ``== Metriken-Ueberblick ==``), Muster
``Regen ab HH:MM · X mm`` (Ereignisform; in der Kompaktform mit ASCII-``-``). Die Kurzzusammenfassung erzeugt eigene
„Regen …"-Texte und zaehlt nicht mit. Fallform ohne Schwellenueberschreitung:
``Regen ges. X mm`` / ``kein Regen``.

Fallzeilen (Gegenproben duerfen gruen sein, nur der Golden-D-Fall ist RED):

* ``golden_d``            — 0,15 mm, global 0,1 -> Pille (RED vor dem Fix)
* ``positivkontrolle``    — 0,3 mm, global 0,1 -> Pille (gruen: beweist, dass
  der Detektor greift und der Pillenblock da ist)
* ``ohne_globale_schwelle`` — 0,15 mm, keine Schwelle -> Standard 0,2, KEINE Pille
* ``layout_eigene_0_2_gegen_global_0_1`` — Layout-Eintrag 0,2 gewinnt -> KEINE
  Pille. Heute gruen, weil die Schwelle generell ignoriert wird; die
  Gegenmutation „globale ueberschreibt Layout-eigene" macht ihn rot (M10).
* ``layout_eigene_0_1_gegen_global_0_3`` — Layout-Eintrag 0,1 gewinnt -> Pille.

Keine Mocks: echter Loader, echte Kaskade, echter Renderer, echte Stundenreihe
(nur der Regenwert wird kontrolliert gesetzt). Bezugszeit des Scheduler-Wegs:
Ortstag + feste Stunde (06:00), nie die Uhrzeit des Laufs. Nutzerkennungen
ohne „test"/„tdd" (Herkunftssperre #2406).
"""
from __future__ import annotations

import copy
import dataclasses
import html as html_lib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_briefings_dir, load_trip  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from services.trip_report_scheduler import TripReportSchedulerService  # noqa: E402
from utils.timezone import tz_for_coords  # noqa: E402
from tests.tdd._einstellung_auslieferung_fixtures import (  # noqa: E402
    STAGE_NAME, TRANSPORT_ENV, TZ, frisches_profil, golden_dict, night_weather,
    segment,
)
from tests.helpers.transport_mitschrift import aufzeichner_installieren  # noqa: E402

#: Fixture-Wetter des Scheduler-Wegs (Innsbruck = Position von Golden D).
FIXTURE_INNSBRUCK = ROOT / "fixtures" / "openmeteo" / "innsbruck.json"

#: Ereignisform der Regen-Pille. Trenner je Form: HTML/Klartext „·", Kompaktform
#: ASCII „-" (``_ascii``). Nur im Pillenblock gesucht (siehe ``_pillenblock``).
_PILLE = re.compile(r"Regen ab \d{2}:\d{2} [·-] [\d.]+ mm")

#: (id, Layout-Schwelle, globale Schwelle, mm je Stunde, Pille erwartet)
SZENARIEN = [
    ("golden_d", None, 0.1, 0.15, True),
    ("positivkontrolle_0_3_mm", None, 0.1, 0.3, True),
    ("ohne_globale_schwelle_standard_0_2", None, None, 0.15, False),
    ("layout_eigene_0_2_gegen_global_0_1", 0.2, 0.1, 0.15, False),
    ("layout_eigene_0_1_gegen_global_0_3", 0.1, 0.3, 0.15, True),
]
SZENARIO_IDS = [s[0] for s in SZENARIEN]

FORMEN = ["html", "plain", "compact"]


# ─────────────────────────── Aufbau ─────────────────────────────────────────


def _dict_mit_schwellen(layout_schwelle, globale_schwelle) -> dict:
    """Golden D (rohes Persistenzformat) mit kontrollierten Schwellen.

    ``globale_schwelle=None`` entfernt Regen- UND Regenwahrscheinlichkeits-
    Schwelle der globalen Auswahl (-> Standardwerte 0,2 / 20). Eine
    ``layout_schwelle`` wird am Regen-Eintrag JEDES E-Mail-Layouts gesetzt
    (Kanal-Layout und je-Bericht-Layout): so gilt sie fuer Morgen und Abend.
    """
    d = copy.deepcopy(golden_dict("golden_d"))
    for m in d["display_config"]["metrics"]:
        if m["metric_id"] == "precipitation":
            if globale_schwelle is None:
                m.pop("sms_threshold", None)
            else:
                m["sms_threshold"] = globale_schwelle
        elif m["metric_id"] == "rain_probability" and globale_schwelle is None:
            m.pop("sms_threshold", None)
    if layout_schwelle is not None:
        layouts = [d["display_config"]["channel_layouts"]["email"]]
        layouts += [
            je_bericht["email"]
            for je_bericht in d["display_config"]["channel_layouts_per_report"].values()
            if "email" in je_bericht
        ]
        for liste in layouts:
            for m in liste:
                if m["metric_id"] == "precipitation":
                    m["sms_threshold"] = layout_schwelle
    return d


def _wetter(mm: float):
    """Synthetische Stundenreihe: an JEDEM Datenpunkt (Segment UND Nacht)
    ``mm`` Regen, niedrige Regenwahrscheinlichkeit. Das Maximum ist damit
    unabhaengig von Stunde, Zeitzone und Tagesfenster."""
    seg = segment()
    nacht = night_weather()
    for dp in list(seg.timeseries.data) + list(nacht.data):
        dp.precip_1h_mm = mm
        dp.pop_pct = 5
    return seg, nacht


def _pillenblock(form: str, text: str) -> str:
    """Nur der Metriken-Ueberblick (Pillen), nicht die Kurzzusammenfassung."""
    if form == "html":
        m = re.search(r"Metriken-Überblick</p><div[^>]*>(.*?)</div>", text, re.S)
        assert m, "Vorbedingung: HTML enthaelt keinen Pillenblock 'Metriken-Überblick'"
        return html_lib.unescape(re.sub(r"<[^>]+>", "|", m.group(1)))
    ueberschrift = (
        "== Metriken-Ueberblick ==" if form == "compact" else "━━ Metriken-Überblick ━━"
    )
    m = re.search(re.escape(ueberschrift) + r"\n((?:  .*\n)+)", text)
    assert m, (
        f"Vorbedingung: Text enthaelt keinen Pillenblock {ueberschrift!r}"
        f" (Anfang: {text[:200]!r})"
    )
    return m.group(1)


def _hat_regen_pille(form: str, text: str) -> tuple[bool, str]:
    block = _pillenblock(form, text)
    return bool(_PILLE.search(block)), block


def _rendern(form: str, d: dict, mm: float, report_type: str) -> str:
    trip = load_trip(d, user_id="default")
    assert trip is not None
    rc = trip.report_config
    if form in ("html", "plain"):
        rc = dataclasses.replace(rc, email_format="full")
    else:
        assert rc.email_format == "compact", "Golden D ist die kompakte Form"
    seg, nacht = _wetter(mm)
    bericht = TripReportFormatter().format_email(
        [seg], trip.name, report_type,
        display_config=trip.display_config, report_config=rc, tz=TZ,
        night_weather=nacht, stage_name=STAGE_NAME,
    )
    return bericht.email_html if form == "html" else bericht.email_plain


# ─────────────────── drei Renderer-Einstiege ────────────────────────────────


@pytest.mark.parametrize("report_type", ["morning", "evening"])
@pytest.mark.parametrize("form", FORMEN)
@pytest.mark.parametrize(
    "szenario", SZENARIEN, ids=SZENARIO_IDS,
)
def test_regen_pille_folgt_der_eingestellten_schwelle_in_allen_drei_formen(
    szenario, form, report_type,
):
    """AC-16: E-Mail-Layout ohne eigene Schwelle + globale Schwelle 0,1 mm +
    Stundenwert 0,15 mm -> die Regen-Pille (Ereignisform ``Regen ab HH:MM ·``)
    erscheint in HTML, Klartext UND Kompaktform, morgens wie abends.

    Ein Layout-Eintrag mit EIGENER Schwelle behaelt Vorrang vor der globalen;
    ohne globale Schwelle bleibt der Standardwert 0,2 (0,15 mm -> keine Pille).
    """
    name, layout_thr, global_thr, mm, erwartet = szenario
    d = _dict_mit_schwellen(layout_thr, global_thr)
    text = _rendern(form, d, mm, report_type)
    da, block = _hat_regen_pille(form, text)
    assert da is erwartet, (
        f"AC-16 [{name}] Form={form} report_type={report_type}: "
        f"Regen {mm} mm, Layout-Schwelle={layout_thr}, global={global_thr} -> "
        f"Regen-Pille {'erwartet' if erwartet else 'NICHT erwartet'}, "
        f"{'gefunden' if da else 'nicht gefunden'}. Pillenblock: {block!r}"
    )


# ─────────────── je Metrik: Wind, Böen, Regen, Regenwahrscheinlichkeit ───────

#: (metric_id, Wetterfeld, Stundenwert, eingestellte Schwelle, hohe Schwelle,
#:  Label-Muster, Ereignis-Muster). Der Stundenwert liegt ZWISCHEN der
#: eingestellten Schwelle und dem Standardwert (``builder.DEFAULTS``: W 10,
#: G 20, R 0,2, PR 20) -- nur so unterscheidet die Pille "eingestellt" von
#: "Standard". Die hohe Schwelle liegt ueber dem Stundenwert.
_BOEEN = r"B(?:ö|oe|o)en"
METRIK_FAELLE = [
    ("wind", "wind10m_kmh", 7.0, 5.0, 20.0,
     r"\bWind (?:>|max)", r"\bWind >5 km/h ab \d{2}:\d{2}"),
    ("gust", "gust_kmh", 15.0, 10.0, 30.0,
     _BOEEN + r" (?:>|max)", _BOEEN + r" >10 km/h ab \d{2}:\d{2}"),
    ("precipitation", "precip_1h_mm", 0.15, 0.1, 0.3,
     r"Regen (?:ab|ges\.)|kein Regen", r"Regen ab \d{2}:\d{2}"),
    ("rain_probability", "pop_pct", 15.0, 10.0, 30.0,
     r"Regen-W\. (?:>|max)", r"Regen-W\. >10% ab \d{2}:\d{2}"),
]

#: (id, Schwelle global, Schwelle am Layout-Eintrag, Ereignisform erwartet).
#: "set"/"hoch" werden je Metrik aus METRIK_FAELLE eingesetzt.
SCHWELLEN_FAELLE = [
    ("global_eingestellt", "set", None, True),
    ("ohne_schwelle_standardwert", None, None, False),
    ("layout_hoch_gewinnt_gegen_global", "set", "hoch", False),
    ("layout_eingestellt_gewinnt_gegen_global_hoch", "hoch", "set", True),
]


def _dict_metrik_schwellen(metric_id: str, global_thr, layout_thr) -> dict:
    """Golden D mit kontrollierter Schwelle fuer EINE Metrik: global in
    ``display_config.metrics``, am Layout-Eintrag in JEDEM E-Mail-Layout."""
    d = copy.deepcopy(golden_dict("golden_d"))
    for m in d["display_config"]["metrics"]:
        if m["metric_id"] == metric_id:
            if global_thr is None:
                m.pop("sms_threshold", None)
            else:
                m["sms_threshold"] = global_thr
    layouts = [d["display_config"]["channel_layouts"]["email"]]
    layouts += [
        je_bericht["email"]
        for je_bericht in d["display_config"]["channel_layouts_per_report"].values()
        if "email" in je_bericht
    ]
    for liste in layouts:
        for m in liste:
            if m["metric_id"] == metric_id:
                if layout_thr is None:
                    m.pop("sms_threshold", None)
                else:
                    m["sms_threshold"] = layout_thr
    return d


@pytest.mark.parametrize("form", FORMEN)
@pytest.mark.parametrize("fall", SCHWELLEN_FAELLE, ids=[f[0] for f in SCHWELLEN_FAELLE])
@pytest.mark.parametrize("metrik", METRIK_FAELLE, ids=[m[0] for m in METRIK_FAELLE])
def test_pille_je_metrik_folgt_der_eingestellten_schwelle(metrik, fall, form):
    """#2422 S3 (AC-16, Adversary F001): Wind, Böen, Regen und
    Regenwahrscheinlichkeit folgen in den Mail-Pillen der im Editor
    eingestellten Erwaehnungsschwelle -- wie die SMS.

    GIVEN ein Stundenwert zwischen eingestellter Schwelle und Standardwert.
    WHEN  die Mail (HTML, Klartext, Kompaktform) gerendert wird.
    THEN  zeigt die Pille die Ereignisform ("… >Schwelle ab HH:00"), wenn die
          eingestellte Schwelle gilt; ohne Schwelle gilt der Standardwert
          (keine Ereignisform); eine Schwelle am Layout-Eintrag gewinnt in
          beide Richtungen gegen die globale.
    """
    metric_id, feld, wert, eingestellt, hoch, label, ereignis = metrik
    name, global_thr, layout_thr, erwartet = fall
    einsetzen = {"set": eingestellt, "hoch": hoch, None: None}
    d = _dict_metrik_schwellen(metric_id, einsetzen[global_thr], einsetzen[layout_thr])

    trip = load_trip(d, user_id="default")
    rc = trip.report_config
    if form != "compact":
        rc = dataclasses.replace(rc, email_format="full")
    seg, nacht = segment(), night_weather()
    for dp in list(seg.timeseries.data) + list(nacht.data):
        setattr(dp, feld, wert)
    bericht = TripReportFormatter().format_email(
        [seg], trip.name, "morning",
        display_config=trip.display_config, report_config=rc, tz=TZ,
        night_weather=nacht, stage_name=STAGE_NAME,
    )
    text = bericht.email_html if form == "html" else bericht.email_plain
    block = _pillenblock(form, text)

    assert re.search(label, block), (
        f"Vorbedingung [{metric_id}/{name}/{form}]: Pille fehlt im Block: {block!r}"
    )
    da = bool(re.search(ereignis, block))
    assert da is erwartet, (
        f"F001 [{metric_id}/{name}/{form}]: Wert {wert}, global={einsetzen[global_thr]}, "
        f"Layout={einsetzen[layout_thr]} -> Ereignisform "
        f"{'erwartet' if erwartet else 'NICHT erwartet'}. Pillenblock: {block!r}"
    )


# ─────────────────── Weg durch send_due_reports ─────────────────────────────


def _fixture_mit_regen(pfad_dir: Path, mm: float) -> None:
    """Kopie der aufgezeichneten Innsbruck-Fixture, Regen an JEDEM Punkt = mm.
    ``pop_pct`` niedrig. Nur diese zwei Felder werden ueberschrieben."""
    roh = json.loads(FIXTURE_INNSBRUCK.read_text())
    for p in roh["data"]:
        p["precip_1h_mm"] = mm
        p["pop_pct"] = 5
    pfad_dir.mkdir(parents=True, exist_ok=True)
    (pfad_dir / "innsbruck.json").write_text(json.dumps(roh))


@pytest.mark.parametrize("szenario", SZENARIEN, ids=SZENARIO_IDS)
def test_regen_pille_folgt_der_schwelle_auch_im_scheduler_weg(
    szenario, monkeypatch, tmp_path,
):
    """AC-16 (Weg durch ``send_due_reports``): dasselbe Golden-D-Briefing, vom
    echten Scheduler zur Morgen-Slot-Stunde (06:00 Ortszeit am Ortstag)
    ausgeloest und vom Aufzeichner abgegriffen (kompakte Form, ``mail_format
    == "compact"``), traegt die Regen-Pille — bzw. nicht — je Fallzeile.
    """
    name, layout_thr, global_thr, mm, erwartet = szenario
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mitschrift = aufzeichner_installieren(monkeypatch)
    fixture_dir = tmp_path / "wetter"
    _fixture_mit_regen(fixture_dir, mm)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(fixture_dir))

    uid = frisches_profil()
    d = _dict_mit_schwellen(layout_thr, global_thr)
    # Golden-D-Dict ist bereits auf den Ortstag datiert (golden_dict). Als
    # Persistenzformat-Datei ablegen, damit der Scheduler den Trip wie
    # produktiv per load_all_trips findet.
    ordner = get_briefings_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{d['id']}.json").write_text(
        json.dumps({**d, "kind": "route"}), encoding="utf-8",
    )

    wp = d["stages"][0]["waypoints"][0]
    ort = tz_for_coords(wp["lat"], wp["lon"])
    slot_stunde = int(d["report_config"]["morning_time"].split(":")[0])
    jetzt = datetime.now(timezone.utc).astimezone(ort).replace(
        hour=slot_stunde, minute=0, second=0, microsecond=0,
    ).astimezone(timezone.utc)

    gesendet, fehlgeschlagen = TripReportSchedulerService(
        user_id=uid,
    ).send_due_reports(jetzt)

    assert (gesendet, fehlgeschlagen) == (1, 0), (
        f"Vorbedingung [{name}]: der Morgen-Slot muss genau ein Briefing "
        f"versenden, erhalten sent={gesendet}, failed={fehlgeschlagen} "
        f"({mitschrift!r})"
    )
    mails = mitschrift.sendungen("email")
    assert len(mails) == 1, f"Vorbedingung [{name}]: genau eine E-Mail, erhalten {mails!r}"
    assert mails[0]["mail_format"] == "compact", (
        f"Vorbedingung [{name}]: Golden D stellt die kompakte Form ein, "
        f"zugestellt wurde mail_format={mails[0]['mail_format']!r}"
    )
    text = (mails[0]["plain_text_body"] or "") + (mails[0]["body"] or "")
    da, block = _hat_regen_pille("compact", text)
    assert da is erwartet, (
        f"AC-16 [{name}] Scheduler-Weg: Regen {mm} mm, Layout-Schwelle="
        f"{layout_thr}, global={global_thr} -> Regen-Pille "
        f"{'erwartet' if erwartet else 'NICHT erwartet'}, "
        f"{'gefunden' if da else 'nicht gefunden'}. Pillenblock: {block!r}"
    )
