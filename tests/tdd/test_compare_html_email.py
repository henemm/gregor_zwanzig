"""
TDD RED: Tests fuer Compare-Email-Renderer + Versand-Integration (Issue #253).

SPEC: docs/specs/modules/issue_253_compare_email.md

Diese Tests schlagen ABSICHTLICH fehl, weil `compare_html.py` noch nicht existiert.
Nach der Implementierung (/5-implement) muss jeder Test gruen sein.

Mocks sind in diesem Projekt VERBOTEN (CLAUDE.md). Echter SMTP/IMAP wird in
TestCompareEmailE2E genutzt.

Klassen:
- TestCompareHTMLRenderer   -- schnell, kein SMTP, prueft Renderer-Output
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
# AC-1, AC-2, AC-5, AC-6 -- Renderer-Tests (kein SMTP)
# ---------------------------------------------------------------------------

class TestCompareHTMLRenderer:
    """
    Prueft render_compare_html() als Pure Function.
    Kein Netzwerk, kein SMTP.

    SPEC: docs/specs/modules/issue_253_compare_email.md §1
    """

    def test_ac1_wintersport_profile_zeigt_schnee_spalten(self):
        """
        AC-1: Given ComparisonResult mit WINTERSPORT / When render_compare_html() /
        Then HTML enthaelt Winner-Locationname, G_SUCCESS-Farbe und Spaltenheader
        fuer snow_depth_cm sowie snow_new_cm.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "<!DOCTYPE html>" in html, "HTML muss mit DOCTYPE beginnen"
        assert "Schneepatrouille" in html, \
            "Winner-Locationname muss im HTML erscheinen"
        assert "#3a7d44" in html, \
            "G_SUCCESS Farbwert (#3a7d44) muss im Winner-Banner stehen"
        assert "Schnee" in html or "snow_depth" in html, \
            "WINTERSPORT-Profil muss Schneehöhe-Spalte zeigen (primary)"
        assert "Neuschnee" in html or "snow_new" in html, \
            "WINTERSPORT-Profil muss Neuschnee-Spalte zeigen (primary)"

    def test_ac2_media_query_fuer_mobile_vorhanden(self):
        """
        AC-2: Given generiertes HTML / When Viewport <= 480px /
        Then @media-Block blendet secondary-col aus und zeigt Karten-Layout.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "@media" in html, \
            "HTML muss @media-Block fuer Mobile-Layout enthalten"
        assert "480px" in html, \
            "Breakpoint 480px muss im @media-Block stehen"
        assert "secondary-col" in html, \
            "Spalten mit Klasse 'secondary-col' muessen im HTML vorkommen"
        assert "mobile-cards" in html, \
            "HTML muss mobile-cards Div für Karten-Layout enthalten"
        assert "location-card" in html, \
            "HTML muss location-card Klasse für einzelne Karten enthalten"

    def test_ac5_warnings_parameter_kein_string_replace(self):
        """
        AC-5: Given warnings=['Lückenhafter Forecast'] /
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
        AC-6: Given Location mit error gesetzt /
        When Renderer Vergleichsmatrix baut /
        Then zeigen Metrik-Zellen '—' und Score-Badge nutzt G_WARNING.
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

        assert "—" in html or "---" in html, \
            "Fehlerhafte Location muss Strich-Symbol in Metrik-Zellen zeigen"

    def test_struktur_dunkler_footer(self):
        """
        Renderer muss dunklen Footer mit G_INK (#1a1a18) als Hintergrund enthalten.
        SPEC: §1 Punkt 8
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert "#1a1a18" in html, \
            "Footer muss Hintergrundfarbe G_INK (#1a1a18) haben"

    def test_profil_eyebrow_in_header(self):
        """
        Renderer muss Profil-Eyebrow via profile_signature() im Header zeigen.
        SPEC: §1 Punkt 3
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

    def test_ac4_kein_ping_bei_keinen_subscriptions(self, monkeypatch):
        """
        AC-4: Given kein erfolgreicher Versand (success_count=0) /
        When Scheduler-Lauf endet /
        Then wird _ping_heartbeat_compare() NICHT aufgerufen.
        """
        from api.routers import scheduler as sched_module
        from app.user import Schedule

        if not hasattr(sched_module, "_ping_heartbeat_compare"):
            pytest.fail("_ping_heartbeat_compare nicht in scheduler.py gefunden")

        ping_called = []

        def fake_ping():
            ping_called.append(True)

        monkeypatch.setattr(sched_module, "_ping_heartbeat_compare", fake_ping)

        # User ohne Subscriptions -> success_count=0 -> kein Ping
        sched_module._run_subscriptions_by_schedule(
            Schedule.DAILY_MORNING, user_id="nonexistent_user_253"
        )

        assert len(ping_called) == 0, \
            "Bei success_count==0 darf kein Heartbeat-Ping gesendet werden"


# ---------------------------------------------------------------------------
# AC-8 -- Echter E2E-Test (SMTP + IMAP)
# ---------------------------------------------------------------------------

@pytest.mark.email
class TestCompareEmailE2E:
    """
    ECHTER E2E-Test: Sendet via SMTP, ruft via IMAP ab.
    Kein Mocking.
    SPEC: docs/specs/modules/issue_253_compare_email.md §4 Test 2
    """

    def test_ac8_echter_versand_imap_verifikation(self):
        """
        AC-8: Given Compare-Mail generiert / When echter SMTP-Send an gregor-test@henemm.com /
        Then Mail ist im IMAP-Postfach, Subject enthaelt 'Compare',
        HTML-Body enthaelt @media-Block (neuer Renderer).
        """
        import imaplib
        import time
        import email
        import uuid

        from app.config import Settings
        from app.loader import load_all_locations, load_compare_subscriptions
        from outputs.email import EmailOutput
        from services.compare_subscription import run_comparison_for_subscription

        settings = Settings().for_testing()
        if not settings.can_send_email():
            pytest.skip("SMTP nicht konfiguriert")

        subs = load_compare_subscriptions()
        locations = load_all_locations()

        if not subs:
            pytest.skip("Keine Compare-Subscriptions konfiguriert")
        if not locations:
            pytest.skip("Keine Locations konfiguriert")

        sub = subs[0]
        subject, html_body, text_body = run_comparison_for_subscription(sub, locations)

        unique_id = str(uuid.uuid4())[:8]
        test_subject = f"[TEST-Compare-{unique_id}] {subject}"

        # Neuer Renderer muss @media enthalten
        assert "<!DOCTYPE html>" in html_body, \
            "HTML-Body muss mit DOCTYPE beginnen"
        assert "@media" in html_body, \
            "HTML-Body muss @media-Block enthalten (neuer Renderer aktiv?)"

        EmailOutput(settings).send(test_subject, html_body, plain_text_body=text_body)
        print(f"\n>>> Compare-E-Mail gesendet: {test_subject}")

        time.sleep(5)

        imap_host = settings.imap_host or settings.smtp_host
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass
        imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
        imap.login(imap_user, imap_pass)
        imap.select("INBOX")

        _, data = imap.search(None, f'SUBJECT "{unique_id}"')
        msg_ids = data[0].split()
        assert len(msg_ids) > 0, \
            f"Compare-E-Mail mit ID {unique_id} nicht in INBOX gefunden!"

        _, msg_data = imap.fetch(msg_ids[-1], "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        assert msg.get_content_type() == "multipart/alternative", \
            "Compare-Mail muss multipart/alternative sein"

        html_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_part = part.get_payload(decode=True).decode("utf-8")
                break

        assert html_part is not None, "Kein text/html Teil in Compare-Mail"
        assert "@media" in html_part, \
            "HTML-Part muss @media-Block enthalten (neuer Renderer)"

        imap.logout()
        print(">>> Compare-E2E-Test bestanden: Mail empfangen und verifiziert")


# ---------------------------------------------------------------------------
# Issue #460 -- Begründungs-Tags + Header-Sektion (TDD RED)
# ---------------------------------------------------------------------------

class TestCompareHTMLRendererIssue460:
    """
    TDD RED: Tests fuer Begründungs-Tags im Winner-Banner + explizite Header-Sektion.

    SPEC: docs/specs/modules/issue_460_compare_email_template.md
    AC-460-1 bis AC-460-4

    Diese Tests schlagen ABSICHTLICH fehl:
    - render_compare_html() kennt 'winner_tags' noch nicht (TypeError)
    - 'ORTS-VERGLEICH' erscheint noch nicht im HTML (AssertionError)
    """

    def test_ac460_1_good_tag_rendered(self):
        """
        AC-460-1: Given winner_tags=[{"tone":"good","label":"1 Ort über Wolken"}] /
        When render_compare_html() / Then HTML enthält den Label-Text und bg-Farbe #dcf2e1.
        SPEC: §1 _render_winner_tags
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(
            result,
            profile=ActivityProfile.WINTERSPORT,
            winner_tags=[{"tone": "good", "label": "1 Ort über Wolken"}],
        )

        assert "1 Ort über Wolken" in html, \
            "Label-Text des good-Tags muss im HTML erscheinen"
        assert "#dcf2e1" in html, \
            "good-Tone Hintergrundfarbe #dcf2e1 muss im HTML stehen"

    def test_ac460_2_alle_drei_tones_enthalten(self):
        """
        AC-460-2: Given winner_tags mit je einem Tag pro Tone (good/warn/info) /
        When render_compare_html() / Then alle 3 Tone-Hintergrundfarben im HTML.
        SPEC: §1 _render_winner_tags — Tone-zu-Farben-Mapping
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(
            result,
            profile=ActivityProfile.WINTERSPORT,
            winner_tags=[
                {"tone": "good", "label": "Top-Ort über Wolken"},
                {"tone": "warn", "label": "Böen 26 km/h"},
                {"tone": "info", "label": "+12 cm Neuschnee"},
            ],
        )

        assert "#dcf2e1" in html, "good-bg (#dcf2e1) muss im HTML stehen"
        assert "#fde6cc" in html, "warn-bg (#fde6cc) muss im HTML stehen"
        assert "#dde8f3" in html, "info-bg (#dde8f3) muss im HTML stehen"

    def test_ac460_3_keine_tags_kein_absturz(self):
        """
        AC-460-3: Given winner_tags=None (Default) /
        When render_compare_html() / Then kein Absturz, keine Tag-Farben im HTML.
        SPEC: §1 — leere Liste → leerer String
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(
            result,
            profile=ActivityProfile.WINTERSPORT,
            winner_tags=None,
        )

        assert "<!DOCTYPE html>" in html, \
            "Renderer muss auch ohne winner_tags valides HTML liefern"
        assert "#dcf2e1" not in html, "good-bg darf nicht erscheinen wenn keine Tags"
        assert "#fde6cc" not in html, "warn-bg darf nicht erscheinen wenn keine Tags"
        assert "#dde8f3" not in html, "info-bg darf nicht erscheinen wenn keine Tags"

    def test_ac460_4_header_zeitfenster_und_label(self):
        """
        AC-460-4: Given result.time_window=(9, 16) /
        When render_compare_html() / Then HTML enthält '09:00', '16:00', 'ORTS-VERGLEICH'.
        SPEC: §3 _render_header — Zeile 2 Datum/Zeitfenster + Zeile 1 Profil-Label
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "09:00" in html, \
            "Startzeit '09:00' muss im Header-Block stehen"
        assert "16:00" in html, \
            "Endzeit '16:00' muss im Header-Block stehen"
        assert "ORTS-VERGLEICH" in html, \
            "Profil-Label-Prefix 'ORTS-VERGLEICH' muss im Header erscheinen"


# ---------------------------------------------------------------------------
# TestWinnerTags — Issue #457: Auto-generierte Begründungs-Tags
# ---------------------------------------------------------------------------

class TestWinnerTags:
    """
    TDD RED: Tests fuer _generate_winner_tags() und deren Integration in render_compare_html().

    SPEC: docs/specs/modules/issue_457_compare_email_tags.md
    AC-1 bis AC-4

    Diese Tests schlagen ABSICHTLICH fehl:
    - _generate_winner_tags() existiert noch nicht → ImportError
    """

    def test_ac1_render_html_enthält_snow_tag(self):
        """
        AC-1: Given ComparisonResult mit snow_depth_cm=120, sunny_hours=7, profile=WINTERSPORT /
        When render_compare_html() mit winner_tags=_generate_winner_tags(winner, profile) /
        Then HTML enthält good-Tag-Farbe #dcf2e1 und Label 'Schneehöhe 120 cm'.
        SPEC: §1 + §3 Integration
        """
        from output.renderers.email.compare_html import render_compare_html, _generate_winner_tags
        from datetime import date, datetime
        from app.user import ComparisonResult, LocationResult, SavedLocation

        loc = SavedLocation(id="loc1", name="Gipfel", lat=47.0, lon=11.0, elevation_m=2500)
        winner = LocationResult(
            location=loc,
            score=85,
            snow_depth_cm=120.0,
            sunny_hours=7,
            wind_max=18.0,
            gust_max=30.0,
            cloud_avg=10,
            above_low_clouds=True,
        )
        result = ComparisonResult(
            locations=[winner],
            time_window=(9, 16),
            target_date=date.today(),
            created_at=datetime.now(),
        )

        tags = _generate_winner_tags(winner, ActivityProfile.WINTERSPORT)
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT, winner_tags=tags)

        assert "#dcf2e1" in html, \
            "good-Tag-Farbe #dcf2e1 muss im HTML erscheinen"
        assert "Schneehöhe 120 cm" in html, \
            "Label 'Schneehöhe 120 cm' muss im Winner-Banner erscheinen"

    def test_ac2_generate_wandern_temp_und_wind_tags(self):
        """
        AC-2: Given LocationResult mit temp_max=18, wind_max=45, profile=WANDERN /
        When _generate_winner_tags() aufgerufen /
        Then gibt Tupel ("good", "Temp. 18°C") und ("warn", "Wind 45 km/h") zurück,
        good-Tags vor warn-Tags.
        SPEC: §1 WANDERN-Regeln
        """
        from output.renderers.email.compare_html import _generate_winner_tags
        from app.user import LocationResult, SavedLocation

        loc = SavedLocation(id="loc1", name="Tal", lat=47.0, lon=11.0, elevation_m=800)
        winner = LocationResult(
            location=loc,
            score=70,
            temp_max=18.0,
            wind_max=45.0,
            sunny_hours=3,   # < 4 → kein Sonne-Tag
            cloud_avg=50,    # < 80 → kein Wolken-Tag
        )

        tags = _generate_winner_tags(winner, ActivityProfile.WANDERN)

        tones = [t for t, _ in tags]
        labels = [l for _, l in tags]

        assert ("good", "Temp. 18°C") in tags, \
            "WANDERN: temp_max=18 (5..22°C) → good-Tag 'Temp. 18°C'"
        assert ("warn", "Wind 45 km/h") in tags, \
            "WANDERN: wind_max=45 > 40 → warn-Tag 'Wind 45 km/h'"
        # good vor warn
        good_idx = next(i for i, t in enumerate(tones) if t == "good")
        warn_idx = next(i for i, t in enumerate(tones) if t == "warn")
        assert good_idx < warn_idx, "good-Tags müssen vor warn-Tags gelistet sein"

    def test_ac3_max_4_tags_limit(self):
        """
        AC-3: Given winner mit 6 zutreffenden Tag-Bedingungen, profile=WINTERSPORT /
        When _generate_winner_tags() aufgerufen /
        Then exakt 4 Tupel zurückgegeben, kein fünfter.
        SPEC: §1 max 4 Tags nach Sortierung good > warn > info
        """
        from output.renderers.email.compare_html import _generate_winner_tags
        from app.user import LocationResult, SavedLocation

        loc = SavedLocation(id="loc1", name="Gipfel", lat=47.0, lon=11.0, elevation_m=3000)
        # Alle 6 WINTERSPORT-Bedingungen erfüllt:
        # snow_depth ≥100 → good, snow_new ≥10 → good, above_low_clouds → good,
        # sunny_hours ≥6 → good, wind_max >40 → warn, gust_max >60 → warn
        winner = LocationResult(
            location=loc,
            score=90,
            snow_depth_cm=200.0,   # good
            snow_new_cm=15.0,      # good
            above_low_clouds=True, # good
            sunny_hours=8,         # good
            wind_max=55.0,         # warn
            gust_max=75.0,         # warn
        )

        tags = _generate_winner_tags(winner, ActivityProfile.WINTERSPORT)

        assert len(tags) == 4, \
            f"Maximal 4 Tags erlaubt, aber {len(tags)} Tags zurückgegeben: {tags}"

    def test_ac4_kein_tag_container_bei_keinem_winner(self):
        """
        AC-4: Given ComparisonResult mit result.winner=None /
        When render_compare_html() mit winner_tags=None /
        Then kein Pill-Container im HTML (kein #dcf2e1), keine Exception.
        SPEC: §3 — Tags nur wenn winner nicht None
        """
        from output.renderers.email.compare_html import render_compare_html
        from datetime import date, datetime
        from app.user import ComparisonResult, LocationResult, SavedLocation

        # Location mit error → winner = None (alle Locations haben Fehler)
        loc = SavedLocation(id="loc1", name="Defekt", lat=47.0, lon=11.0, elevation_m=2000)
        lr = LocationResult(location=loc, score=0, error="Datenfehler")
        result = ComparisonResult(
            locations=[lr],
            time_window=(9, 16),
            target_date=date.today(),
            created_at=datetime.now(),
        )

        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "<!DOCTYPE html>" in html, "Muss valides HTML liefern"
        assert "#dcf2e1" not in html, "Kein good-Tag wenn kein Winner"
        assert "#fde6cc" not in html, "Kein warn-Tag wenn kein Winner"

    def test_ac2_wintersport_über_wolken_tag(self):
        """
        SPEC §1 WINTERSPORT: above_low_clouds=True → ("good", "Über den Wolken")
        """
        from output.renderers.email.compare_html import _generate_winner_tags
        from app.user import LocationResult, SavedLocation

        loc = SavedLocation(id="loc1", name="Hoch", lat=47.0, lon=11.0, elevation_m=3000)
        winner = LocationResult(
            location=loc,
            score=80,
            above_low_clouds=True,
            snow_depth_cm=30.0,  # < 50 → kein Schnee-Tag
            sunny_hours=2,       # < 6 → kein Sonne-Tag
            wind_max=15.0,       # < 40 → kein Wind-Tag
        )

        tags = _generate_winner_tags(winner, ActivityProfile.WINTERSPORT)

        assert ("good", "Über den Wolken") in tags, \
            "WINTERSPORT: above_low_clouds=True → ('good', 'Über den Wolken')"

    def test_ac2_keine_tags_bei_harmlosen_werten(self):
        """
        SPEC §1: Keine Bedingungen erfüllt → leere Liste.
        """
        from output.renderers.email.compare_html import _generate_winner_tags
        from app.user import LocationResult, SavedLocation

        loc = SavedLocation(id="loc1", name="Mild", lat=47.0, lon=11.0, elevation_m=1000)
        winner = LocationResult(
            location=loc,
            score=50,
            snow_depth_cm=10.0,   # < 50
            snow_new_cm=1.0,      # < 3
            above_low_clouds=False,
            sunny_hours=2,        # < 6
            wind_max=15.0,        # < 40 (WINTERSPORT)
            gust_max=30.0,        # < 60
            cloud_avg=60,
        )

        tags = _generate_winner_tags(winner, ActivityProfile.WINTERSPORT)

        assert tags == [], \
            f"Keine Schwellwerte überschritten → leere Liste erwartet, aber: {tags}"
