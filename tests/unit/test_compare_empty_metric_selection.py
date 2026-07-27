"""Leerauswahl heisst leer — Issue #1366 + #1361 Befund 3, S3 Scheibe B (#1372).

Spec: docs/specs/modules/compare_empty_metric_selection.md
Kontext: docs/context/fix-1366-leerauswahl-heisst-leer.md

Kern-Tests (Test-Politik "Zwei Schichten", CLAUDE.md): kein Netz, keine echten
Mail-Versendungen, kein Mock/patch. Der Live-Nachweis (echte Staging-Mail) ist
nicht Teil dieser Datei (s. Spec Test Plan, Abschnitt Live-E2E).
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from app.models import ForecastDataPoint
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.channels.email import build_mime_message
from output.renderers.comparison import render_compare_email, render_compare_telegram
from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from services.report_config_resolver import resolve_compare_render_options


# ---------------------------------------------------------------------------
# Fixture (analog test_compare_metric_order.py::_result) — mind. 1 Ort reicht
# fuer die reinen Auflöser-Tests, die Mail-Wirkung braucht keine drei Orte.
# ---------------------------------------------------------------------------


def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.0, lon=11.0, elevation_m=600)


def _loc_result(loc_id: str, name: str) -> LocationResult:
    return LocationResult(
        location=_loc(loc_id, name), score=1,
        temp_max=20.0, wind_max=15.0, cloud_avg=40, sunny_hours=5,
        official_alerts=[],
    )


def _result() -> ComparisonResult:
    return ComparisonResult(
        locations=[_loc_result("a", "Aachen"), _loc_result("b", "Bremen")],
        time_window=(0, 23), target_date=date(2026, 7, 24),
        created_at=datetime(2026, 7, 24, 4, 0),
    )


# Staging-Fund AC-4 (2026-07-26): der Klartext-Teil zeigte den Stundenblock
# bislang UNABHAENGIG von Auswahl/Schalter -- kein Kern-Test deckte ihn ab,
# weil _loc_result() oben keine hourly_data traegt. Eigene Fixture MIT
# hourly_data fuer den Klartext-Stundenverlauf-Nachweis.
def _result_mit_stunden(*, mit_ausblick: bool = False) -> ComparisonResult:
    dp = ForecastDataPoint(ts=datetime(2026, 7, 24, 8, 0), t2m_c=18.0, wind10m_kmh=12.0)
    loc = _loc_result("a", "Innsbruck")
    loc.hourly_data = [dp]
    if mit_ausblick:
        # Zweiter Staging-Fund (2026-07-26): OHNE Ausblicksdaten verschwand der
        # Abschnittskopf zusammen mit der Tabelle, die Luecke blieb unsichtbar.
        # Drei Folgetage a zwei Punkten = genau der Ausblick, den die echte Mail
        # traegt (_build_location_outlook_rows cappt auf 3 Kalendertage).
        loc.outlook_hourly_data = [
            ForecastDataPoint(
                ts=datetime(2026, 7, 25 + tag, stunde, 0),
                t2m_c=14.0 + stunde, wind10m_kmh=10.0,
            )
            for tag in range(3)
            for stunde in (9, 15)
        ]
    return ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=date(2026, 7, 24),
        created_at=datetime(2026, 7, 24, 4, 0),
    )


class TestUebersichtsAufloeserAC2:
    def test_komplett_unbekannte_auswahl_ergibt_leere_liste_nicht_alle(self):
        """AC-2: Given eine gespeicherte Auswahl, die sich auf KEINE bekannte
        Wettergroesse mehr abbilden laesst / When resolve_enabled_metrics()
        aufgerufen wird / Then liefert es [] (keine Zeile), nicht None (alle)."""
        result = resolve_enabled_metrics(["voellig_unbekannte_id_xyz", "noch_eine"])
        assert result == [], (
            f"Komplett unmappbare, aber nicht-leere Auswahl muss [] ergeben "
            f"(AC-2), nicht None (= alle), erhalten {result!r}"
        )


class TestStundenverlaufAufloeserAC5AC6:
    def test_ac5_komplett_unbekannte_auswahl_ergibt_leere_liste_und_nur_protokollvermerk(self, caplog):
        """AC-5: Given mehrere Stundenverlauf-Kennungen, die ALLE unmappbar
        sind / When resolve_hourly_metrics() aufgerufen wird / Then liefert
        es [], nicht None (bisher: Rueckfall auf alle 9 Spalten).

        PO-Entscheidung: eine ausschliesslich unbekannte Auswahl wird wie eine
        bewusst leere behandelt — die Mail zeigt dort nichts, der Hinweis auf
        die verworfenen Kennungen steht NUR im Protokoll."""
        with caplog.at_level(logging.WARNING):
            result = resolve_hourly_metrics(["unbekannt_a", "unbekannt_b"])
        assert result == [], (
            f"Komplett unmappbare Stundenauswahl muss [] ergeben (AC-5), "
            f"erhalten {result!r}"
        )
        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("unbekannt_a" in msg and "unbekannt_b" in msg for msg in warnings), (
            f"Die verworfenen Kennungen muessen im Protokoll vermerkt sein "
            f"(einziger Ort, an dem sie noch auftauchen), Warnungen: {warnings!r}"
        )

    def test_ac6_teilweise_unbekannt_behaelt_reihenfolge_und_protokolliert(self, caplog):
        """AC-6: Given eine Stundenverlauf-Auswahl mit mind. einer mappbaren
        und mind. einer unmappbaren Kennung / When resolve_hourly_metrics()
        aufgerufen wird / Then enthaelt das Ergebnis nur die auflösbaren
        Spalten in Auswahl-Reihenfolge UND es entsteht eine Protokollwarnung
        mit den unauflösbaren Kennungen."""
        with caplog.at_level(logging.WARNING):
            result = resolve_hourly_metrics(["wind_kmh", "unbekannt_x", "temp_c"])
        assert result == ["wind10m_kmh", "t2m_c"], (
            f"Erwartet nur die auflösbaren Spalten in Auswahl-Reihenfolge, "
            f"erhalten {result!r}"
        )
        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("unbekannt_x" in msg for msg in warnings), (
            f"Erwartet eine Protokollwarnung mit der unauflösbaren Kennung "
            f"'unbekannt_x' (#1361 Befund 3), Warnungen: {warnings!r}"
        )


class TestReportConfigResolverAC4AC5:
    def test_leere_stundenauswahl_schaltet_stundenblock_ab_trotz_gespeichertem_true(self):
        """AC-4/AC-5 auf Config-Ebene: Given ein Preset mit bewusst leerer
        hourly_metrics-Auswahl und gespeichertem hourly_enabled=True (bzw.
        Feld fehlt = Default True) / When resolve_compare_render_options()
        aufgerufen wird / Then ist hourly_enabled trotzdem False."""
        preset = {"id": "p-leer", "display_config": {"hourly_metrics": []}}
        options = resolve_compare_render_options(preset)
        assert options.hourly_enabled is False, (
            "Leere Stundenauswahl muss den Stundenblock abschalten, auch "
            "wenn hourly_enabled nicht gesetzt (Default True) ist"
        )

    def test_nur_windrichtung_schaltet_stundenblock_ab_statt_zeit_only_geruest(self):
        """Nachtrag-Luecke 2: Given eine Stundenauswahl, die AUSSCHLIESSLICH
        die Windrichtung enthaelt (aufloesbar, aber reines Merge-Signal ohne
        eigene Spalte, s. compare_hourly_metric_ids.py:26-30) / When
        resolve_compare_render_options() aufgerufen wird / Then ist
        hourly_enabled False.

        Die aufgeloeste Liste ist hier NICHT leer (['wind_direction_deg']) --
        die reine Leer-Pruefung greift also nicht. Sichtbar wuerde trotzdem
        nur eine Tabelle mit der Zeit-Spalte, was die PO-Entscheidung vom
        2026-07-26 ausschliesst und der Pflicht-Validator zurueckweist
        (.claude/hooks/email_spec_validator.py:379-383)."""
        preset = {
            "id": "p-nur-windrichtung",
            "display_config": {"hourly_metrics": ["wind_dir_deg"]},
            "hourly_enabled": True,
        }
        options = resolve_compare_render_options(preset)
        assert options.hourly_metrics == ["wind_direction_deg"], (
            f"Voraussetzung: die Windrichtung ist aufloesbar, die Liste also "
            f"nicht leer — erhalten {options.hourly_metrics!r}"
        )
        assert options.hourly_enabled is False, (
            "Eine Auswahl ohne jede sichtbare Wert-Spalte muss den "
            "Stundenblock abschalten statt ein Zeit-only-Geruest zu rendern"
        )

    def test_komplett_unbekannte_stundenauswahl_schaltet_stundenblock_ab(self):
        preset = {
            "id": "p-unbekannt",
            "display_config": {"hourly_metrics": ["voellig_unbekannt"]},
            "hourly_enabled": True,
        }
        options = resolve_compare_render_options(preset)
        assert options.hourly_enabled is False, (
            "Komplett unauflösbare Stundenauswahl muss hourly_enabled trotz "
            "gespeichertem True auf False verunden"
        )


class TestMailWirkungAC1AC9:
    def test_leere_uebersichtsauswahl_zeigt_nur_warnzeile_in_html_und_keine_zeile_in_plain_und_telegram(self):
        """AC-1/AC-9: Given ein Ortsvergleich mit bewusst leerer Übersichts-
        Auswahl (display_config.active_metrics: []) / When die Vergleichs-
        Mail (HTML+Klartext) und die Telegram-Nachricht ueber
        resolve_compare_render_options() gerendert werden / Then zeigt HTML
        nur die Warn-Zeile, Klartext und Telegram zeigen keine
        Wettergroessen-Zeile."""
        preset = {"id": "p-ac1", "display_config": {"active_metrics": []}}
        options = resolve_compare_render_options(preset)
        assert options.enabled_metrics == [], (
            f"Bewusste Leerauswahl muss als [] aufgeloest werden (AC-1-"
            f"Voraussetzung), erhalten {options.enabled_metrics!r}"
        )

        result = _result()
        html, plain = render_compare_email(
            result,
            enabled_metrics=options.enabled_metrics,
            hourly_metrics=options.hourly_metrics,
            hourly_enabled=options.hourly_enabled,
        )
        assert "Amtliche Warnungen" in html, "Warn-Zeile muss trotz Leerauswahl stehen bleiben"
        for label in ("Temp max", "Wind", "Sonne", "Wolken"):
            assert f">{label}<" not in html, (
                f"HTML darf bei Leerauswahl keine Wettergroessen-Zeile '{label}' zeigen"
            )
            assert f"{label}:" not in plain, (
                f"Klartext darf bei Leerauswahl keine Wettergroessen-Zeile '{label}' zeigen"
            )

        msg = render_compare_telegram(result, enabled_metrics=options.enabled_metrics)
        assert " · " not in msg.split("\n")[0], "Telegram darf keine Metrik-Zellen zeigen"
        for label in ("Temp", "Wind", "Sonne", "Wolken"):
            assert f"{label} " not in msg, (
                f"Telegram darf bei Leerauswahl keine Wettergroessen-Zelle '{label}' zeigen"
            )


class TestKlartextStundenverlaufAC4:
    """Staging-Fund (2026-07-26, IMAP-ID 12330): der Klartext-Teil zeigte den
    Stundenblock bislang unabhaengig von Auswahl/Schalter. Ueber
    resolve_compare_render_options() mit einem Preset-Dict, nicht mit direkt
    gesetzten Parametern -- genau der Weg, der beim Versand tatsaechlich
    durchlaufen wird und den kein bisheriger Kern-Test abdeckte."""

    def test_leere_stundenauswahl_und_abgeschalteter_schalter_zeigen_keinen_stundenblock(self):
        """Mit Ausblicksdaten -- genau die Lage der echten Staging-Mail. Ohne
        sie fiel der Kopf zufaellig mit der Tabelle weg (leerer
        `section_lines`-Puffer), mit ihnen blieb er stehen und beschriftete
        den 3-Tages-Ausblick falsch."""
        preset = {"id": "p-ac4", "display_config": {"hourly_metrics": []}}
        options = resolve_compare_render_options(preset)
        assert options.hourly_enabled is False  # Voraussetzung, s. TestReportConfigResolverAC4AC5

        _, plain = render_compare_email(
            _result_mit_stunden(mit_ausblick=True),
            hourly_metrics=options.hourly_metrics,
            hourly_enabled=options.hourly_enabled,
            outlook_enabled=True,
        )
        assert "Nächste Etappen" in plain, (
            "Voraussetzung: der 3-Tages-Ausblick steht im Klartext (nur dann "
            "kann der Kopf ohne Stundenzeilen ueberhaupt haengenbleiben)"
        )
        assert "STUNDENVERLAUF" not in plain, (
            "AC-4: bewusste Leerauswahl (-> hourly_enabled=False) darf im Klartext "
            "weder Ueberschrift noch Geruest zeigen -- auch dann nicht, wenn "
            f"darunter noch der 3-Tages-Ausblick steht. Klartext:\n{plain}"
        )

    def test_gesetzte_auswahl_zeigt_nur_die_gewaehlten_werte_in_der_gewaehlten_reihenfolge(self):
        """Gegenprobe: bei nicht-leerer Auswahl bleibt alles wie es war --
        Ueberschrift, Stundenzeilen UND Ausblick."""
        preset = {
            "id": "p-ac4-auswahl",
            "display_config": {"hourly_metrics": ["wind_kmh", "temp_c"]},
            "hourly_enabled": True,
        }
        options = resolve_compare_render_options(preset)

        _, plain = render_compare_email(
            _result_mit_stunden(mit_ausblick=True),
            hourly_metrics=options.hourly_metrics,
            hourly_enabled=options.hourly_enabled,
            outlook_enabled=True,
        )
        assert "STUNDENVERLAUF" in plain
        hour_line = next(line for line in plain.splitlines() if "08:00" in line)
        assert hour_line.index("Wind") < hour_line.index("Temp"), (
            f"Reihenfolge der Auswahl muss die Spaltenfolge bestimmen, erhalten: {hour_line!r}"
        )
        assert "Gef." not in hour_line, "nicht gewaehlte Spalten duerfen nicht erscheinen"
        assert "Nächste Etappen" in plain, (
            "Der 3-Tages-Ausblick bleibt unveraendert erhalten"
        )
        assert plain.index("STUNDENVERLAUF") < plain.index("08:00") < plain.index("Nächste Etappen"), (
            f"Reihenfolge Kopf -> Stundenzeilen -> Ausblick muss bleiben:\n{plain}"
        )

    def test_ausblick_bleibt_ohne_stundenzeilen_erhalten(self):
        """Gegenprobe zur Kopf-Bedingung: der Ausblick selbst darf NICHT mit
        dem Kopf verschwinden -- er haengt nicht am Stundenverlauf-Schalter
        (Issue #1323)."""
        preset = {"id": "p-ausblick-solo", "display_config": {"hourly_metrics": []}}
        options = resolve_compare_render_options(preset)

        _, plain = render_compare_email(
            _result_mit_stunden(mit_ausblick=True),
            hourly_metrics=options.hourly_metrics,
            hourly_enabled=options.hourly_enabled,
            outlook_enabled=True,
        )
        assert "Nächste Etappen" in plain, f"Ausblick muss stehen bleiben:\n{plain}"
        assert "Innsbruck" in plain.split("Nächste Etappen")[0], (
            "Der Ausblick behaelt seinen heutigen Aufbau samt Orts-Zeile "
            "(die fehlende eigene Ausblick-Ueberschrift ist Issue #1368)"
        )
        assert "08:00" not in plain, "keine Stundenzeilen bei leerer Auswahl"


class TestNurMergeSignalGewaehlt:
    """Nachtrag-Luecke 2 aus Nutzersicht: hakt jemand im Stundenverlauf NUR
    die Windrichtung an, entstuende ein Geruest mit ausschliesslich der
    Zeit-Spalte -- die Windrichtung hat keine eigene Spalte, sie wird nur in
    die Wind-Zelle gemergt. Der Marker-Header behauptete dabei bisher eine
    vorhandene Stundensektion."""

    def test_nur_windrichtung_zeigt_keinen_stundenblock_in_html_und_klartext(self):
        preset = {
            "id": "p-nur-windrichtung-mail",
            "display_config": {"hourly_metrics": ["wind_dir_deg"]},
            "hourly_enabled": True,
        }
        options = resolve_compare_render_options(preset)

        html, plain = render_compare_email(
            _result_mit_stunden(),
            hourly_metrics=options.hourly_metrics,
            hourly_enabled=options.hourly_enabled,
        )
        assert "STUNDENVERLAUF" not in plain, (
            "Klartext darf keinen Stundenverlauf-Abschnitt zeigen, wenn keine "
            "einzige Wert-Spalte gewaehlt ist"
        )
        assert "STUNDEN" not in html, (
            "HTML darf keinen STUNDEN-Sektionskopf zeigen, wenn keine einzige "
            "Wert-Spalte gewaehlt ist (sonst Tabelle mit nur der Zeit-Spalte)"
        )

    def test_nur_windrichtung_meldet_marker_header_false(self):
        """Der Versandweg setzt X-GZ-Compare-Hourly-Enabled aus
        `opts.hourly_enabled` (scheduler_dispatch_service.py:399) -- derselbe
        Aufruf hier, damit der Header nicht eine Stundensektion behauptet, die
        die Mail gar nicht enthaelt."""
        preset = {
            "id": "p-nur-windrichtung-header",
            "display_config": {"hourly_metrics": ["wind_dir_deg"]},
            "hourly_enabled": True,
        }
        options = resolve_compare_render_options(preset)
        html, plain = render_compare_email(
            _result_mit_stunden(),
            hourly_metrics=options.hourly_metrics,
            hourly_enabled=options.hourly_enabled,
        )
        msg = build_mime_message(
            subject="Ortsvergleich", body=html,
            from_addr="gregor_zwanzig@henemm.com", to_header="gregor-test@henemm.com",
            reply_to=None, html=True, plain_text_body=plain,
            mail_type="compare",
            compare_hourly_enabled=options.hourly_enabled,
        )
        assert msg["X-GZ-Compare-Hourly-Enabled"] == "false", (
            f"Marker-Header muss die tatsaechlich gerenderte Mail beschreiben, "
            f"erhalten {msg['X-GZ-Compare-Hourly-Enabled']!r}"
        )
