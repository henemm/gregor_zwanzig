"""TDD RED — Issue #1106: Ortsvergleich C — Metriken im Stundenverlauf konfigurierbar.

Spec: docs/specs/modules/issue_1106_hourly_metrics_config.md (AC-1 .. AC-8)
Kontext: docs/context/fix-1106-hourly-metrics-config.md

Die Stundentabelle jeder Ort-Sektion in der Compare-Mail zeigt aktuell 7 fest
verdrahtete Wetter-Spalten (Temp, Gef., Wind, Böen, Regen, Wolken, UV) ohne
dass der Nutzer beeinflussen kann, welche davon erscheinen. Dieses Modul
deckt die fehlenden Bausteine auf:

  1. Der kanonische ID-Resolver ``resolve_hourly_metrics()``
     (``src/output/renderers/compare_hourly_metric_ids.py``) existiert noch
     nicht -> ImportError bei jedem Testfall in ``TestResolveHourlyMetrics``.
  2. ``render_compare_html()``/``_render_hour_table()`` kennen noch keinen
     ``hourly_metrics``-Parameter und rendern weiterhin die alten 7 Spalten
     (inkl. "Wolken", ohne Gewitter/Regenwahrscheinlichkeit/Sicht) ->
     TypeError (unbekanntes Kwarg) bzw. AssertionError (falscher
     Spalten-Bestand) in ``TestHourMetricsRendererUnit``.
  3. ``send_one_compare_preset()`` liest ``display_config.hourly_metrics``
     noch NICHT und übergibt ``hourly_metrics`` nicht an
     ``render_compare_email()`` -> die real zugestellte Mail zeigt immer noch
     den alten 8-Spalten-Vertrag, unabhängig von der Preset-Konfiguration ->
     AssertionError in ``TestHourMetricsE2E`` (echter SMTP-Versand + echter
     IMAP-Abruf aus ``gregor-test@henemm.com``, kein Mock).
  4. ``.claude/hooks/email_spec_validator.py::_HOUR_COLUMNS_V2`` ist noch ein
     Exakt-Vertrag (8 alte Spalten) statt einer Teilmengen-mit-Reihenfolge-
     Prüfung mit Mindestspalten-Regel -> AssertionError in
     ``TestValidatorHourlyColumns``.

KEINE Mocks (Projektkonvention CLAUDE.md):
- ``TestResolveHourlyMetrics`` ist reines Unit-Testing einer pure function
  (kein Mock nötig).
- ``TestHourMetricsRendererUnit`` prüft ``render_compare_html()`` als pure
  function gegen synthetische ``ComparisonResult``-Fixtures (kein Netzwerk,
  kein E-Mail-/API-Mock).
- ``TestHourMetricsE2E`` sendet real per SMTP (Stalwart-Testkonto via
  ``Settings().with_user_profile()`` + Test-User-Präfix "test1106-") und
  ruft die zugestellte Mail real per IMAP aus ``gregor-test@henemm.com`` ab
  — analog ``tests/tdd/test_compare_html_email.py::TestCompareEmailE2E``.
  Die vorgelagerte ``ComparisonEngine`` läuft dabei über die Offline-
  Fixture-Provider-autouse-Fixture aus ``tests/conftest.py`` (kein Netzwerk-
  Call zu Open-Meteo, aber echter SMTP-Versand + echter IMAP-Abruf).
- ``TestValidatorHourlyColumns`` lädt ``.claude/hooks/email_spec_validator.py``
  als isoliertes Modul (analog ``tests/tdd/test_issue_1046_...``) und prüft
  ``validate_structure()`` gegen HTML, das aus dem ECHTEN Renderer
  (``render_compare_html()``) erzeugt und per gezielter String-Splice (kein
  Handbau der gesamten Mail) manipuliert wird.

Bekannte Abweichung (dokumentiert statt stillschweigend übersprungen): AC-4
verlangt laut Spec-Testbeschreibung den Nachweis von "mittel"/"hoch"-Wortlaut
für Gewitter-Risiko in einer ECHT zugestellten Mail. Die 3 vorhandenen
Offline-Fixtures (``fixtures/openmeteo/{innsbruck,stubai,zillertal}.json``)
liefern aber ausschließlich ``thunder_level="NONE"`` — es gibt keine
Fixture-Stunde mit MED/HIGH. Ein Ändern der geteilten Fixtures wäre ein
Seiteneffekt außerhalb des Scopes dieses Slices (andere Tests verlassen sich
auf die bestehenden Werte). Der kategoriale Gewitter-Wortlaut wird daher
zusätzlich als reiner Renderer-Unit-Test mit synthetischem
``ForecastDataPoint(thunder_level=ThunderLevel.HIGH/MED)`` abgedeckt
(``TestHourMetricsRendererUnit.test_ac4_gewitter_kategorial_mittel_hoch_wortlaut``,
kein Mock — echte Objekte, echter Renderer-Aufruf). Die E2E-Klasse deckt für
AC-4 die real zugestellten Werte für Regenwahrscheinlichkeit (``pop_pct=20``
in allen 3 Fixtures) und Sicht (``visibility_m=9000`` in der
Innsbruck-Fixture) ab.
"""
from __future__ import annotations

import importlib.util
import re
import uuid
from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import ForecastDataPoint, ThunderLevel
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "email_spec_validator.py"


# ---------------------------------------------------------------------------
# Class 1 — Resolver (analog TestResolveEnabledMetrics aus #1104)
# ---------------------------------------------------------------------------


class TestResolveHourlyMetrics:
    """Reiner Unit-Test fuer den (noch nicht existierenden) kanonischen
    ID-Resolver ``resolve_hourly_metrics()``.

    RED: ``src/output/renderers/compare_hourly_metric_ids.py`` existiert noch
    nicht -> ImportError bei jedem Testfall dieser Klasse.

    Frontend-ID-Vokabular gemaess Spec Implementation Details (Sketch;
    Known Limitation: exakte Namen sind Implementierungsdetail, muessen aber
    mit ``compareHourlyMetricDefs.ts`` UND diesen Tests uebereinstimmen).
    """

    def test_known_frontend_ids_resolve_to_renderer_ids(self):
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        result = resolve_hourly_metrics(["temp_c", "wind_kmh", "thunder_level"])
        assert result == {"t2m_c", "wind10m_kmh", "thunder_level"}, (
            f"Erwartet {{'t2m_c', 'wind10m_kmh', 'thunder_level'}}, erhalten {result!r}"
        )

    def test_new_metrics_pop_und_visibility_resolve(self):
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        result = resolve_hourly_metrics(["pop_pct", "visibility_m"])
        assert result == {"pop_pct", "visibility_m"}, (
            f"Erwartet {{'pop_pct', 'visibility_m'}}, erhalten {result!r}"
        )

    def test_none_returns_none(self):
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        result = resolve_hourly_metrics(None)
        assert result is None, f"None muss None ergeben (kein Filter, alle 9 sichtbar), erhalten {result!r}"

    def test_empty_list_returns_none(self):
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        result = resolve_hourly_metrics([])
        assert result is None, f"Leere Liste muss None ergeben (Default alle 9), erhalten {result!r}"

    def test_unknown_ids_are_dropped_leads_to_none(self):
        """Bildet eine Auswahl komplett auf nichts Mappbares ab -> None
        (keine leere Stundentabelle statt Default 'alle')."""
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        result = resolve_hourly_metrics(["voellig_unbekannte_id_xyz"])
        assert result is None, (
            f"Unbekannte ID muss verworfen werden -> Ergebnis None (nicht leeres "
            f"Set, nicht Absturz), erhalten {result!r}"
        )

    def test_scalar_string_input_returns_none_not_crashed(self):
        """Adversary-Analogie F001 (#1104): ein einzelner String darf nicht
        ueber seine Zeichen iteriert werden."""
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        result = resolve_hourly_metrics("temp_c")
        assert result is None, f"Scalar-String-Input muss defensiv zu None fuehren, erhalten {result!r}"

    def test_dict_input_returns_none_not_crashed(self):
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        result = resolve_hourly_metrics({"a": 1})
        assert result is None, f"Dict-Input muss defensiv zu None fuehren, erhalten {result!r}"

    def test_int_input_returns_none_not_typeerror(self):
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        result = resolve_hourly_metrics(5)
        assert result is None, f"Int-Input muss defensiv zu None fuehren (kein TypeError), erhalten {result!r}"


# ---------------------------------------------------------------------------
# Class 2 — Renderer Unit-Tests (kein Netzwerk, synthetische Fixtures)
# ---------------------------------------------------------------------------


def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.27, lon=11.39, elevation_m=574)


def _dp(hour: int, **overrides) -> ForecastDataPoint:
    defaults = dict(
        ts=datetime(2026, 7, 8, hour, 0),
        t2m_c=20.0,
        wind_chill_c=19.0,
        wind10m_kmh=10.0,
        gust_kmh=18.0,
        precip_1h_mm=0.0,
        cloud_total_pct=30,
        uv_index=4.0,
        thunder_level=ThunderLevel.NONE,
        pop_pct=15,
        visibility_m=9000,
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _make_hourly_result(name: str = "Testort", dps=None) -> ComparisonResult:
    dps = dps if dps is not None else [_dp(9), _dp(10)]
    location = LocationResult(
        location=_loc("testort", name),
        temp_max=22.0,
        wind_max=12.0,
        sunny_hours=4.0,
        cloud_avg=30,
        official_alerts=[],
        hourly_data=dps,
    )
    return ComparisonResult(
        locations=[location],
        time_window=(9, 10),
        target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 0),
    )


class TestHourMetricsRendererUnit:
    """Prueft ``render_compare_html()``/``_render_hour_table()`` direkt gegen
    synthetische ``ComparisonResult``-Fixtures. Kein Netzwerk, kein SMTP.

    RED: ``hourly_metrics``-Kwarg existiert auf ``render_compare_html()`` noch
    nicht -> TypeError bei den Tests, die ihn uebergeben. AC-5 braucht keinen
    neuen Kwarg (Default-Aufruf zeigt "Wolken" bereits heute) -> AssertionError.
    """

    def test_ac3_zeit_ist_immer_erste_spalte_bei_gefilterter_auswahl(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_hourly_result()
        html = render_compare_html(
            result,
            profile=ActivityProfile.ALLGEMEIN,
            hourly_metrics={"t2m_c", "wind10m_kmh"},
        )
        zeit_pos = html.find(">Zeit<")
        temp_pos = html.find(">Temp<")
        assert zeit_pos != -1, "RED: 'Zeit'-Spalte nicht gefunden -- hourly_metrics-Kwarg existiert noch nicht"
        assert zeit_pos < temp_pos, (
            "RED: 'Zeit' muss die erste Spalte jeder Stundentabelle sein, unabhaengig von "
            "der Metrik-Auswahl -- render_compare_html() kennt hourly_metrics noch nicht"
        )

    def test_ac5_wolken_spalte_ist_vollstaendig_entfernt_auch_im_default(self):
        """AC-5 bezieht sich explizit auf den Stundenverlauf (Spec Known
        Limitations: die Uebersichtstabelle/cloud_avg-Zeile aus #1104/#1105
        ist NICHT Teil dieses Slices und behaelt ihr 'Wolken'-Label, s.
        test_issue_1110_compare_mail_v2.py::test_enabled_metrics_none_zeigt_alle_zeilen).
        Deshalb wird die Pruefung auf die Stundentabelle des Ortes scoped
        statt auf die gesamte Mail."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_hourly_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        zeit_pos = html.find(">Zeit<")
        assert zeit_pos != -1, "Stundentabelle ('Zeit'-Spalte) nicht gefunden"
        table_start = html.rfind("<table", 0, zeit_pos)
        table_end = html.find("</table>", zeit_pos) + len("</table>")
        hour_table_html = html[table_start:table_end]

        assert ">Wolken<" not in hour_table_html, (
            "RED: 'Wolken'-Spalte muss aus der Stundentabelle vollstaendig entfernt sein "
            "(PO-Entscheidung), im heutigen Renderer (_HOUR_COLUMNS) ist sie noch fest "
            "verdrahtet vorhanden"
        )

    def test_ac8_kanonische_reihenfolge_unabhaengig_von_auswahl_konstruktion(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_hourly_result()
        # Set-Konstruktion in "falscher" Reihenfolge -- kanonische Reihenfolge
        # (Temp vor Sicht) muss trotzdem im Header erscheinen.
        html = render_compare_html(
            result,
            profile=ActivityProfile.ALLGEMEIN,
            hourly_metrics={"visibility_m", "t2m_c"},
        )
        temp_pos = html.find(">Temp<")
        sicht_pos = html.find(">Sicht<")
        assert temp_pos != -1 and sicht_pos != -1, (
            "RED: 'Temp'/'Sicht'-Spalten nicht gefunden -- hourly_metrics-Kwarg und/oder "
            "neue Metrik 'Sicht' existieren noch nicht im Renderer"
        )
        assert temp_pos < sicht_pos, (
            "RED: kanonische Reihenfolge (Temp vor Sicht) muss unabhaengig von der "
            "Set-Konstruktions-Reihenfolge gelten"
        )

    def test_ac4_gewitter_kategorial_mittel_hoch_wortlaut(self):
        """Deckt den Teil von AC-4 ab, der mit den bestehenden Offline-Fixtures
        (nur thunder_level=NONE) nicht real per E2E bewiesen werden kann (s.
        Modul-Docstring). Synthetisches ForecastDataPoint, kein Mock."""
        from output.renderers.email.compare_html import render_compare_html

        dps = [
            _dp(9, thunder_level=ThunderLevel.MED),
            _dp(10, thunder_level=ThunderLevel.HIGH),
        ]
        result = _make_hourly_result(dps=dps)
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert "mittel" in html, (
            "RED: Gewitter-Risiko MED muss als Wortlaut 'mittel' erscheinen -- "
            "Gewitter-Spalte existiert im Renderer noch gar nicht"
        )
        assert "hoch" in html, (
            "RED: Gewitter-Risiko HIGH muss als Wortlaut 'hoch' erscheinen -- "
            "Gewitter-Spalte existiert im Renderer noch gar nicht"
        )


# ---------------------------------------------------------------------------
# Class 3 — Echter E2E-Versand + IMAP-Verifikation (kein Mock)
# ---------------------------------------------------------------------------


def _fresh_test_user() -> str:
    return f"test1106-{uuid.uuid4().hex[:8]}"


_E2E_LOCATION_NAME = "Fixtureort1106"


def _fixture_location(loc_id: str = "loc-1106") -> SavedLocation:
    """WICHTIG: lon=25.0 liegt bewusst AUSSERHALB der GEOSPHERE_BOUNDS
    (``comparison_engine.py::_select_provider_for_location``, Alpenraum
    lat 45-50/lon 8-18) -- echte Alpen-Koordinaten (z.B. Innsbruck
    47.2692/11.4041) wuerden den GeoSphereProvider waehlen, der NICHT ueber
    ``GZ_TEST_FIXTURE_DIR`` geroutet wird (echter Netzwerk-Call, kein
    deterministisches pop_pct/thunder_level/visibility_m). Mit lon=25.0
    greift ``get_provider("openmeteo")`` -> Offline-FixtureProvider (autouse-
    Fixture in tests/conftest.py) -- nearest() bildet auf zillertal.json ab
    (pop_pct=20, thunder_level=NONE, visibility_m=8000 -> "8.0 km")."""
    return SavedLocation(id=loc_id, name=_E2E_LOCATION_NAME, lat=47.2692, lon=25.0, elevation_m=574)


def _hour_header_cols(html: str, location_name: str = _E2E_LOCATION_NAME) -> list:
    marker = re.compile(r">ORT</span>\s*<span[^>]*>" + re.escape(location_name) + r"</span>")
    m = marker.search(html)
    assert m is not None, f"RED/Fixture-Fehler: ORT-Kopf fuer '{location_name}' nicht im HTML gefunden"
    table_match = re.search(r"<table[^>]*>(.*?)</table>", html[m.end():], re.DOTALL)
    assert table_match is not None, f"RED/Fixture-Fehler: keine Tabelle nach ORT-Kopf '{location_name}' gefunden"
    header_row = re.search(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.DOTALL)
    assert header_row is not None, "RED/Fixture-Fehler: keine Kopfzeile in Stundentabelle gefunden"
    cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", header_row.group(1), re.DOTALL)
    return [re.sub(r"<[^>]+>", "", c).strip() for c in cells]


def _send_compare_preset_and_fetch_html(display_config, tag: str) -> str:
    """Sendet ein Compare-Preset ECHT per SMTP (kein Intercept, kein Mock)
    ueber den echten Preset-Versandpfad ``send_one_compare_preset()`` und
    ruft die zugestellte Mail ECHT per IMAP aus ``gregor-test@henemm.com``
    ab. ComparisonEngine laeuft ueber die Offline-Fixture-Provider-autouse-
    Fixture (tests/conftest.py) -- kein Netzwerk-Call zu Open-Meteo, aber
    echter SMTP-Versand + echter IMAP-Abruf (Projektregel: kein Mock)."""
    import email as email_mod
    import imaplib
    import tempfile
    import time as time_mod

    from app.config import Settings
    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id = _fresh_test_user()
    settings = Settings().with_user_profile(user_id)
    if not settings.can_send_email():
        pytest.skip("SMTP nicht konfiguriert (Test-Creds fehlen)")

    unique = uuid.uuid4().hex[:8]
    preset = {
        "id": f"cp-1106-{tag}",
        "name": f"AC1106-{tag}-{unique}",
        "location_ids": ["loc-1106"],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 10,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }
    if display_config is not None:
        preset["display_config"] = display_config

    location = _fixture_location("loc-1106")
    with tempfile.TemporaryDirectory() as tmp:
        send_one_compare_preset(preset, settings, user_id, tmp, all_locations_cache=[location])

    time_mod.sleep(5)

    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
    imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
    imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
    imap.login(imap_user, imap_pass)
    imap.select("INBOX")

    _, data = imap.search(None, f'SUBJECT "{unique}"')
    msg_ids = data[0].split()
    assert msg_ids, f"Compare-Mail mit ID {unique} nicht in INBOX gefunden"

    _, msg_data = imap.fetch(msg_ids[-1], "(RFC822)")
    msg = email_mod.message_from_bytes(msg_data[0][1])
    html_body = None
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html_body = part.get_payload(decode=True).decode("utf-8")
            break

    imap.close()
    imap.logout()

    assert html_body is not None, "Kein text/html-Teil in der zugestellten Compare-Mail gefunden"
    return html_body


_ALL_NINE_PLUS_ZEIT = [
    "Zeit", "Temp", "Gef.", "Wind", "Böen", "Regen", "UV", "Gew.", "Regen-W.", "Sicht",
]


@pytest.mark.email
class TestHourMetricsE2E:
    """ECHTER E2E-Test: sendet via SMTP, ruft via IMAP ab. Kein Mocking.

    RED: ``send_one_compare_preset()`` liest ``display_config.hourly_metrics``
    heute nicht -> die real zugestellte Mail zeigt immer den alten
    8-Spalten-Vertrag (inkl. 'Wolken', ohne die 3 neuen Metriken), unabhaengig
    von der Preset-Konfiguration.
    """

    def test_ac1_ohne_hourly_metrics_zeigt_alle_9_spalten_plus_zeit(self):
        html = _send_compare_preset_and_fetch_html(display_config=None, tag="ac1")
        header = _hour_header_cols(html)
        assert header == _ALL_NINE_PLUS_ZEIT, (
            f"RED: Default-Stundentabelle (kein hourly_metrics) zeigt {header}, erwartet "
            f"die vollstaendige 10-Spalten-Superset {_ALL_NINE_PLUS_ZEIT} -- Resolver/"
            "HOUR_METRICS/Versandpfad-Wiring existieren noch nicht, 'Wolken' ist noch "
            "vorhanden statt entfernt."
        )

    def test_ac2_teilauswahl_kommt_exakt_so_in_der_mail_an(self):
        html = _send_compare_preset_and_fetch_html(
            display_config={"hourly_metrics": ["temp_c", "wind_kmh", "thunder_level"]},
            tag="ac2",
        )
        header = _hour_header_cols(html)
        assert header == ["Zeit", "Temp", "Wind", "Gew."], (
            f"RED: erwartet exakt ['Zeit','Temp','Wind','Gew.'] bei Teilauswahl, bekommen "
            f"{header} -- send_one_compare_preset() liest display_config.hourly_metrics "
            "noch nicht (Feld wird komplett ignoriert)."
        )

    def test_ac3_ausschliesslich_unbekannte_ids_faellt_real_zugestellt_auf_alle_spalten_zurueck(self):
        """AC-3, dritter geforderter realer Versandlauf (Adversary F003): eine
        Auswahl aus ausschliesslich nicht-mappbaren IDs darf 'Zeit' als erste
        Spalte nicht verlieren -- resolve_hourly_metrics() bildet das komplett
        auf None (= alle 9 Spalten) ab, echt bewiesen ueber den vollen
        Versand-/IMAP-Pfad (nicht nur Resolver-Unit-Test)."""
        html = _send_compare_preset_and_fetch_html(
            display_config={"hourly_metrics": ["voellig_unbekannte_id_xyz", "noch_eine_unbekannte"]},
            tag="ac3unknown",
        )
        header = _hour_header_cols(html)
        assert header[0] == "Zeit", (
            f"RED: 'Zeit' muss auch bei ausschliesslich unbekannten IDs die erste Spalte "
            f"bleiben, bekommen {header}"
        )
        assert header == _ALL_NINE_PLUS_ZEIT, (
            f"RED: ausschliesslich unbekannte IDs muessen auf den vollen 10-Spalten-Default "
            f"zurueckfallen (kein Absturz, keine leere Tabelle), bekommen {header}"
        )

    def test_ac4_regenwahrscheinlichkeit_und_sicht_real_zugestellt_plausibel(self):
        """Deckt den mit den bestehenden Fixtures beweisbaren Teil von AC-4 ab
        (pop_pct/visibility_m); der Gewitter-Wortlaut-Teil ist als Renderer-
        Unit-Test in TestHourMetricsRendererUnit abgedeckt (s. Modul-Docstring
        fuer die Begruendung dieser Aufteilung)."""
        html = _send_compare_preset_and_fetch_html(
            display_config={"hourly_metrics": ["pop_pct", "visibility_m"]},
            tag="ac4",
        )
        header = _hour_header_cols(html)
        assert header == ["Zeit", "Regen-W.", "Sicht"], (
            f"RED: erwartet ['Zeit','Regen-W.','Sicht'], bekommen {header} -- "
            "hourly_metrics wird im Versandpfad noch nicht verarbeitet."
        )
        assert re.search(r"\b20\s*%", html), (
            "RED: Regenwahrscheinlichkeits-Prozentwert (Fixture pop_pct=20) fehlt in der "
            "zugestellten Mail -- Regen-W.-Spalte existiert im Renderer noch nicht"
        )
        # #1237 AC-2 (angepasst): die Sicht-ZELLE traegt die Einheit nicht mehr
        # (nur noch den Zahlenwert), die Einheit steht in der Einheiten-Legende
        # unter der Tabelle. Geprueft wird beides — Wert UND Einheiten-Nachweis.
        assert re.search(r"\b8[.,]0\b", html), (
            "RED: Sicht-Distanzwert (8.0 aus zillertal.json visibility_m=8000, "
            "nearest-fixture fuer lon=25.0) fehlt in der zugestellten Mail -- "
            "Sicht-Spalte existiert im Renderer noch nicht"
        )
        assert re.search(r"Einheiten:[^<]*Sicht[^<·]*km", html), (
            "Einheiten-Legende benennt die Sicht-Einheit 'km' nicht (#1237 AC-2)"
        )


# ---------------------------------------------------------------------------
# Class 4 — Validator (echtes HTML aus dem echten Renderer, kein Mock)
# ---------------------------------------------------------------------------


def _load_validator():
    """Laedt den Validator als isoliertes Modul (vermeidet sys.modules-
    Kontamination), analog tests/tdd/test_issue_1046_email_validator_table_contract.py."""
    spec = importlib.util.spec_from_file_location("esv1106", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _real_html_with_spliced_hour_table(new_table_html: str) -> str:
    """Rendert eine echte Compare-Mail (render_compare_html, 1 Ort) und
    ersetzt NUR die Stundentabelle dieses Ortes durch einen praeparierten
    Tabellen-String -- reiner String-Eingriff am echten Render-Output, kein
    Handbau der gesamten Mail (Muster aus test_issue_1046, AC-6-Test)."""
    from output.renderers.email.compare_html import render_compare_html

    result = _make_hourly_result(name="Testort")
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

    zeit_positions = [m.start() for m in re.finditer(r">Zeit<", html)]
    assert len(zeit_positions) == 1, f"Erwartet genau 1 Stundentabelle, gefunden: {len(zeit_positions)}"
    pos = zeit_positions[0]
    table_start = html.rfind("<table", 0, pos)
    table_end = html.find("</table>", pos) + len("</table>")
    return html[:table_start] + new_table_html + html[table_end:]


class TestValidatorHourlyColumns:
    """AC-6/AC-7: ``.claude/hooks/email_spec_validator.py`` muss von
    Exakt-Vergleich (``_HOUR_COLUMNS_V2``) auf Teilmengen-mit-Reihenfolge-
    Pruefung mit Mindestspalten-Regel umgestellt werden.

    RED: ``_HOUR_COLUMNS_V2`` ist noch der alte 8-Spalten-Exakt-Vertrag ->
    beide Tests schlagen fehl (AC-6 wegen fehlender spezifischer
    Mindestspalten-Fehlermeldung, AC-7 weil eine gueltige neue Teilmenge
    heute als Fremdspalten-Verstoss statt als OK gewertet wird).
    """

    def test_ac6_nur_zeit_ohne_wertspalte_wird_mit_mindestspalten_grund_abgelehnt(self):
        mod = _load_validator()
        only_zeit_table = (
            "<table><tr><th>Zeit</th></tr><tr><td>09:00</td></tr></table>"
        )
        html = _real_html_with_spliced_hour_table(only_zeit_table)

        errors = mod.validate_structure(html)

        assert errors, "RED: Stundentabelle ohne jede Wert-Spalte muss abgelehnt werden"
        assert any("mindestspalten" in e.lower() for e in errors), (
            "RED: Fehlermeldung muss die Mindestspalten-Regel (Zeit + mind. 1 "
            f"Wert-Spalte) explizit benennen, bekommen: {errors}"
        )

    def test_ac7_gueltige_teilmenge_mit_neuer_gewitter_spalte_passiert_gate(self):
        mod = _load_validator()
        subset_table = (
            "<table><tr><th>Zeit</th><th>Temp</th><th>Wind</th><th>Gew.</th></tr>"
            "<tr><td>09:00</td><td>20°</td><td>10</td><td>—</td></tr></table>"
        )
        html = _real_html_with_spliced_hour_table(subset_table)

        errors = mod.validate_structure(html)

        assert errors == [], (
            "RED: gueltige Teilmenge (Zeit+Temp+Wind+Gew.) muss den Validator "
            f"fehlerfrei passieren (Teilmengen-mit-Reihenfolge- statt "
            f"Exakt-Pruefung), bekommen: {errors}"
        )
