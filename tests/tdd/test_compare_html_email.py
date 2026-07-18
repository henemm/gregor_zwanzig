"""
TDD: Tests fuer Compare-Email-Renderer + Versand-Integration (Issue #253, v2 #1110).

SPEC: docs/specs/modules/issue_1110_compare_mail_v2.md

An v2 angepasst (Issue #1110): Score/Winner-Card/winner_tags entfallen komplett
aus render_compare_html() -- die Assertions unten pruefen die v2-Aequivalente
(Uebersichtstabelle, Header-Stats Desktop/Mobile, Ort-Fehlerbehandlung,
dunkler Footer). Mocks sind in diesem Projekt VERBOTEN (CLAUDE.md). Echter
SMTP/IMAP wird in TestCompareEmailE2E genutzt.

Klassen:
- TestCompareHTMLRenderer   -- schnell, kein SMTP, prueft Renderer-Output (v2)
- TestHeartbeatIntegration  -- prueft Heartbeat-Verhalten im Scheduler
- TestCompareEmailE2E       -- echter SMTP-Send + IMAP-Verifikation (@pytest.mark.email)
"""
import os
import pytest
from datetime import date, datetime

from app.user import ComparisonResult, LocationResult, SavedLocation
from app.profile import ActivityProfile


# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------

def _make_location(loc_id: str, name: str, elevation_m: int = 2000) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.0, lon=11.0, elevation_m=elevation_m)


def _make_result(
    winner_score: int = 80,
    runner_score: int = 55,
) -> ComparisonResult:
    """Minimales ComparisonResult fuer Unit-Tests (kein Netzwerk)."""
    loc_win = _make_location("loc-win", "Schneepatrouille", elevation_m=2400)
    loc_run = _make_location("loc-run", "Talstation Gruen", elevation_m=1400)

    lr_win = LocationResult(
        location=loc_win,
        score=winner_score,
        snow_depth_cm=145.0,
        snow_new_cm=18.0,
        sunny_hours=6,
        wind_max=22.0,
        gust_max=38.0,
        cloud_avg=15,
        temp_max=-2.0,
        wind_chill_min=-8.0,
        above_low_clouds=True,
    )
    lr_run = LocationResult(
        location=loc_run,
        score=runner_score,
        snow_depth_cm=60.0,
        snow_new_cm=4.0,
        sunny_hours=2,
        wind_max=8.0,
        gust_max=15.0,
        cloud_avg=65,
        temp_max=3.0,
        wind_chill_min=-1.0,
        above_low_clouds=False,
    )
    return ComparisonResult(
        locations=[lr_win, lr_run],
        time_window=(9, 16),
        target_date=date.today(),
        created_at=datetime.now(),
    )


# ---------------------------------------------------------------------------
# v2-Renderer-Tests (kein SMTP)
# ---------------------------------------------------------------------------

class TestCompareHTMLRenderer:
    """
    Prueft render_compare_html() als Pure Function (v2, Issue #1110).
    Kein Netzwerk, kein SMTP.
    """

    def test_ac1_uebersichtstabelle_zeigt_alle_orte(self):
        """
        v2: Given ComparisonResult mit 2 Orten / When render_compare_html() /
        Then HTML enthaelt beide Ortsnamen und keine Score-/Winner-Referenz.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "<!DOCTYPE html>" in html, "HTML muss mit DOCTYPE beginnen"
        assert "Schneepatrouille" in html, "Erster Ortsname muss im HTML erscheinen"
        assert "Talstation Gruen" in html, "Zweiter Ortsname muss im HTML erscheinen"
        for forbidden in ("Score", "Bester Standort", "🏆"):
            assert forbidden not in html, f"'{forbidden}' darf im v2-HTML nicht vorkommen"

    def test_ac2_media_query_fuer_mobile_vorhanden(self):
        """
        AC-8 (v2): @media-Block schaltet zwischen Header-Stats Desktop/Mobile
        um; kein CSS-Grid/Flexbox im Mail-Body (Outlook-Kompatibilitaet).
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "@media" in html, "HTML muss @media-Block fuer Mobile-Layout enthalten"
        assert "480px" in html, "Breakpoint 480px muss im @media-Block stehen"
        assert "header-stats-desktop" in html and "header-stats-mobile" in html, (
            "Zwei unterscheidbare Markup-Container (Desktop/Mobile) fuer Header-Stats erwartet"
        )
        compact = html.replace(" ", "")
        assert "display:flex" not in compact, "Kein CSS display:flex (Outlook-Kompatibilitaet)"
        assert "display:grid" not in compact, "Kein CSS display:grid (Outlook-Kompatibilitaet)"

    def test_ac5_warnings_parameter_kein_string_replace(self):
        """
        Given warnings=['Lückenhafter Forecast'] /
        When render_compare_html() / Then HTML enthaelt orangenen Warnungs-Banner.
        """
        from output.renderers.email.compare_html import render_compare_html

        warning_text = "Lückenhafter Forecast fuer Location X"
        result = _make_result()
        html = render_compare_html(
            result,
            profile=ActivityProfile.WINTERSPORT,
            warnings=[warning_text],
        )

        assert warning_text in html, \
            "Warning-Text muss direkt im gerenderten HTML erscheinen"
        assert "#c8882a" in html or "warning" in html.lower(), \
            "Warnungs-Banner muss orangene G_WARNING-Farbe verwenden"

    def test_ac6_fehlerhafte_location_zeigt_strich(self):
        """
        v2: Given Location mit error gesetzt /
        When Renderer die Uebersichtstabelle baut /
        Then zeigen deren Zellen '—' (SPEC §4 Known Limitation).
        """
        from output.renderers.email.compare_html import render_compare_html

        loc_err = _make_location("loc-err", "Ausgefallener Ort")
        lr_err = LocationResult(
            location=loc_err,
            score=0,
            error="Provider-Timeout: OpenMeteo nicht erreichbar",
        )
        result = ComparisonResult(
            locations=[_make_result().locations[0], lr_err],
            time_window=(9, 16),
            target_date=date.today(),
            created_at=datetime.now(),
        )

        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "—" in html, \
            "Fehlerhafte Location muss Strich-Symbol in Uebersichtstabellen-Zellen zeigen"
        assert "Ausgefallener Ort" in html, "Fehlerhafter Ort muss trotzdem als Spalte erscheinen"

    def test_struktur_dunkler_footer(self):
        """
        Renderer muss dunklen App-Footer mit G_INK (#1a1a18) als Hintergrund enthalten.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert "#1a1a18" in html, \
            "Footer muss Hintergrundfarbe G_INK (#1a1a18) haben"

    def test_profil_eyebrow_in_header(self):
        """
        Renderer muss Profil-Eyebrow via profile_signature() im Header zeigen.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        for profile in [
            ActivityProfile.WINTERSPORT,
            ActivityProfile.WANDERN,
            ActivityProfile.SUMMER_TREKKING,
            ActivityProfile.ALLGEMEIN,
        ]:
            html = render_compare_html(result, profile=profile)
            assert len(html) > 500, \
                f"Profil {profile}: HTML muss nicht-trivial sein (> 500 Zeichen)"

    def test_render_ohne_profil_kein_absturz(self):
        """
        render_compare_html() muss auch mit profile=None funktionieren (Fallback).
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=None)
        assert "<!DOCTYPE html>" in html

    def test_header_label(self):
        """
        Given ein beliebiges ComparisonResult /
        When render_compare_html() / Then HTML enthält 'ORTS-VERGLEICH'.

        Issue #1268: Die Erwartung hat sich gedreht. Dieser Test prüfte zuvor
        zusätzlich '09:00'/'16:00' im Header (Bewertungs-Zeitfenster). Das
        Zeitfenster ist seit #1268 kein Editor-Feld mehr und verschwindet aus
        der Kopfzeile (AC-5) — die beiden Uhrzeit-Assertions widersprachen dem
        direkt und sind hier entfallen. Der Nachweis, dass KEINE Uhrzeit mehr
        erscheint, liegt in TestCompareMailZeitfensterUndHorizont (s.u.);
        hier bleibt nur die weiterhin gültige Label-Erwartung.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "ORTS-VERGLEICH" in html, "Profil-Label-Prefix 'ORTS-VERGLEICH' muss im Header erscheinen"

    def test_winner_tags_feature_entfernt_v2(self):
        """
        Issue #1110: Score/Winner-Tags-Feature (#457/#460) wurde vollstaendig
        entfernt -- render_compare_html() kennt weder 'winner_tags' noch
        'top_n_details'/'enabled_metrics' mehr, _generate_winner_tags() existiert
        nicht mehr im Modul. Regressionsschutz statt der 10 alten
        TestWinnerTags-Tests (Ersatz fuer entfallenes Feature, kein 1:1-Aequivalent
        moeglich, da das Feature selbst per PO-Entscheidung gestrichen wurde).
        """
        from output.renderers.email import compare_html as mod

        assert not hasattr(mod, "_generate_winner_tags"), (
            "_generate_winner_tags() muss mit v2 entfernt sein (kein Score/Winner mehr)"
        )
        result = _make_result()
        with pytest.raises(TypeError):
            mod.render_compare_html(result, profile=ActivityProfile.WINTERSPORT, winner_tags=[])


# ---------------------------------------------------------------------------
# AC-3, AC-4, AC-7 -- Heartbeat / Scheduler-Tests
# ---------------------------------------------------------------------------

class TestHeartbeatIntegration:
    """
    Prueft Heartbeat-Verhalten in api/routers/scheduler.py.
    SPEC: docs/specs/modules/issue_253_compare_email.md §3
    """

    def test_ac7_kein_heartbeat_ohne_env_var(self):
        """
        AC-7: Given GZ_HEARTBEAT_COMPARE nicht gesetzt /
        When _ping_heartbeat_compare() / Then keine Exception, kein Error-Log.
        """
        from api.routers.scheduler import _ping_heartbeat_compare

        env_backup = os.environ.pop("GZ_HEARTBEAT_COMPARE", None)
        try:
            _ping_heartbeat_compare()  # Darf keine Exception werfen
        finally:
            if env_backup is not None:
                os.environ["GZ_HEARTBEAT_COMPARE"] = env_backup


# Issue #1250 Scheibe 0: TestCompareEmailE2E (AC-8) entfernt — basierte auf dem
# stillgelegten Legacy-Drittstack CompareSubscription (#1131),
# services.compare_subscription/load_compare_subscriptions existieren nicht
# mehr. Live-E2E-Abdeckung fuer den Compare-Mail-Versand laeuft ueber den
# aktiven ComparePreset-Pfad (briefing_mail_validator.py / email_spec_validator.py,
# CLAUDE.md "Mail-Validatoren & Renderer-Gate").


# ---------------------------------------------------------------------------
# Issue #1268 -- Zeitfenster raus aus der Mail, Horizont konsistent
# Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md
# ---------------------------------------------------------------------------

import re


class TestCompareMailWithoutTimeWindow:
    """TDD RED — Issue #1268 (AC-5/AC-6): die Vergleichs-Mail zeigt kein
    Bewertungs-Zeitfenster mehr und einen konsistenten Horizont.

    Kein Netzwerk, kein SMTP — reine Renderer-Aufrufe mit In-Memory-Fixture.
    """

    # "09:00 – 16:00" / "09:00 - 16:00" — Halbgeviert ODER ASCII-Bindestrich.
    TIME_WINDOW_PATTERN = re.compile(r"\d{2}:00\s*[–-]\s*\d{2}:00")

    def test_ac5_html_header_zeigt_kein_zeitfenster(self):
        """GIVEN: ein ComparisonResult mit time_window=(9, 16)
        WHEN: render_compare_html() die Kopfzeile baut
        THEN: das HTML enthaelt keine "HH:00 – HH:00"-Zeitfenster-Angabe mehr.

        AC-5. Der Nutzer kann das Fenster nicht mehr einstellen (#1268), also
        darf die Mail auch keins mehr behaupten.

        RED vor Fix: _render_header() baut date_line aus Wochentag + Datum +
        time_str ("09:00 – 16:00").
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()  # time_window=(9, 16)
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        match = self.TIME_WINDOW_PATTERN.search(html)
        assert match is None, (
            f"RED: HTML enthaelt weiterhin eine Zeitfenster-Angabe {match.group(0)!r} — "
            "die Kopfzeile darf nur noch Wochentag + Datum zeigen (Spec #1268 AC-5)."
        )

    def test_ac5_html_zeigt_kein_zeitfenster_auch_bei_ganztags_fenster(self):
        """GIVEN: ein ComparisonResult mit dem neuen Ganztags-Fenster (0, 23)
        WHEN: render_compare_html() laeuft
        THEN: ebenfalls keine Uhrzeit-Angabe — auch nicht "00:00 – 23:00".

        AC-5. Ohne diesen Fall wuerde ein Fix, der nur (9, 16) unterdrueckt,
        faelschlich gruen; nach dem Dispatch-Fix (AC-4) ist (0, 23) der Normalfall.

        RED vor Fix: die Kopfzeile zeigt dann "00:00 – 23:00".
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        result.time_window = (0, 23)
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        match = self.TIME_WINDOW_PATTERN.search(html)
        assert match is None, (
            f"RED: HTML enthaelt weiterhin eine Zeitfenster-Angabe {match.group(0)!r} "
            "(Ganztags-Fenster). Die Uhrzeit gehoert ersatzlos aus der Kopfzeile."
        )

    def test_ac5_html_behaelt_datum_und_wochentag(self):
        """GIVEN: ein ComparisonResult fuer ein bekanntes Zieldatum
        WHEN: render_compare_html() laeuft
        THEN: Wochentag und Datum stehen weiterhin in der Kopfzeile.

        AC-5-Gegenprobe: entfernt werden soll NUR die Uhrzeit, nicht die
        ganze Datumszeile. Schuetzt gegen einen Ueber-Fix.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        result.target_date = date(2026, 7, 16)  # Donnerstag
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "16.07.2026" in html, "Das Zieldatum muss in der Kopfzeile erhalten bleiben"
        assert "Do" in html, "Der Wochentag muss in der Kopfzeile erhalten bleiben"

    def test_ac5_text_renderer_hat_keine_zeitfenster_zeile(self):
        """GIVEN: ein ComparisonResult mit time_window=(9, 16)
        WHEN: render_compare_email() den Klartext-Teil baut
        THEN: es gibt keine "Zeitfenster:"-Zeile mehr.

        AC-5 fuer den zweiten Renderer (Klartext-Teil der Mail). Ohne ihn
        wuerde der Text-Pfad die entfernte Angabe still weitertragen.

        RED vor Fix: comparison.py:74 haengt
        f"Zeitfenster: {time_window[0]:02d}:00 - {time_window[1]:02d}:00" an.
        """
        from output.renderers.comparison import render_compare_email

        result = _make_result()
        rendered = render_compare_email(result, profile=ActivityProfile.WINTERSPORT)
        text = rendered[1] if isinstance(rendered, tuple) else rendered

        zeitfenster_zeilen = [ln for ln in text.splitlines() if "Zeitfenster" in ln]
        assert zeitfenster_zeilen == [], (
            f"RED: Klartext-Teil enthaelt weiterhin {zeitfenster_zeilen!r} — "
            "die Zeile entfaellt ersatzlos (Spec #1268 AC-5)."
        )
        match = self.TIME_WINDOW_PATTERN.search(text)
        assert match is None, (
            f"RED: Klartext-Teil enthaelt weiterhin eine Uhrzeit-Spanne {match.group(0)!r}."
        )

    def test_ac6_header_zeigt_48h_horizont(self):
        """GIVEN: eine beliebige Vergleichs-Mail
        WHEN: der Nutzer die Kopfzeile liest
        THEN: es gibt keine Horizont-Kachel mehr — weder "Horizont" noch ein
              Wert wie "+48h"/"+96h" tauchen auf.

        Loest das alte #1268 AC-6 ("Kopf-Kachel zeigt +48h") bewusst ab:
        Issue #1305 hebt den Ortsvergleich-Horizont auf 96h an und laesst die
        Kachel ersatzlos entfallen (Spec docs/specs/modules/
        compare_forecast_horizon.md, Known Limitations) statt einen neuen
        Wert zu zeigen.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "Horizont" not in html, (
            "Die Horizont-Kachel entfaellt ersatzlos (Issue #1305)."
        )
        for stale in ("+24h", "+48h", "+72h", "+96h"):
            assert stale not in html, (
                f"'{stale}' darf nicht in der Mail stehen — es gibt keine Horizont-Kachel mehr."
            )
        for expected in ("Profil", "Orte", "Erstellt"):
            assert expected in html, (
                f"Kachel-Label '{expected}' muss weiterhin sichtbar sein."
            )
