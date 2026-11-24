"""TDD RED -- Issue #3059: E-Mail-Format "Kompakt" fuer Orte.

SPEC: docs/specs/modules/feat_3059_orte_kompakt_mail.md
(AC-1, AC-2, AC-4, AC-5 Mail-Teil, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12).
Frontend (AC-3, AC-5 Editor, AC-13) und Pruefkatalog/Validator (AC-14, AC-15)
stehen in eigenen Testdateien.

Kette wie im Betrieb: rohes Preset-JSON im Nutzerverzeichnis einer isolierten
Datenwurzel -> echter Loader -> ``send_one_compare_preset`` OHNE ``mail_sink``,
also ueber ``NotificationService.send_compare_report`` bis an ``EmailOutput.send``.
Dort zeichnet ``tests/helpers/transport_mitschrift`` auf (echte Klasse mit der
echten Signatur, ersetzt nur die Naht zum Netz). Aus der Aufzeichnung baut die
reine Produktfunktion ``build_mime_message`` die MIME-Nachricht -- dieselbe,
die ``EmailOutput.send`` an SMTP gibt. So ist ``X-GZ-Format`` am Wirkort
beobachtbar. Wetter offline (echte Engine-Subklasse), kein Mock()/patch().

Vertrag fuer die Implementierung (Tech-Lead-Festlegung, aus der Spec):

* Kompakt-Signal = leeres HTML aus ``compare_email_rendern``; der Versand
  ruft ``EmailOutput.send(..., html=False, mail_format="compact",
  mail_type="compare")`` mit dem Kompakttext als ``body``.
* Eine Zeile je Ort: sie enthaelt den ASCII-gefalteten Ortsnamen und je fuer
  die E-Mail gewaehlter Groesse deren unuebersetztes Kuerzel
  (``compact_label`` des Metrik-Katalogs, z. B. ``T``/``W``/``R``) mit Wert.
* Ausblick je Ort: eine Zeile, die mit dem Katalognamen
  ``mail.ausblick.name`` ("3-Tages-Ausblick" / "3-day outlook") beginnt.
* Kuerzung: Gesamttext <= 2048 Byte; letzte Inhaltszeile "+N Orte nicht
  gezeigt" bzw. "+N locations not shown".
* Vorschau: ``ComparePreviewService.render_all_channels`` liefert bei Kompakt
  ``email_html == ""`` und ``email_text`` = Kompakttext.
* Resolver: ``CompareRenderOptions.email_format`` ("full" Vorgabe).
"""
from __future__ import annotations

import copy
import dataclasses
import email
import json
import re
from datetime import datetime, timedelta
from email import policy

import pytest

from tests.helpers.einstellung_gleich_mail_orte import (
    JETZT_UTC,
    ORTE,
    ZIELTAG,
    _ausblick_fuer,
    _ergebnis_je_ort,
    orte_anlegen,
    preset_dict,
    profil_anlegen,
    transport_umgebung,
)
from tests.helpers.transport_mitschrift import aufzeichner_installieren

AGG = {"temperature": "max", "wind": "max", "gust": "max", "precipitation": "sum",
       "rain_probability": "max"}
#: Fuer die E-Mail gewaehlt -- Kuerzel aus dem Katalog (Protokoll-Token).
GEWAEHLT = ("temperature", "wind", "precipitation")
NICHT_GEWAEHLT = ("gust", "rain_probability")
NAMEN = [v[0] for v in ORTE.values()]
GRENZE_BYTES = 2048


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------


def _kuerzel(metric_id: str) -> str:
    from app.metric_catalog import get_all_metrics

    return next(m.compact_label for m in get_all_metrics() if m.id == metric_id)


def _katalog(schluessel: str, lang: str) -> str:
    from i18n import t

    return t(schluessel, lang)


def _preset(*, email_format: str | None = "compact", preset_id: str = "orte-kompakt",
            location_ids: list[str] | None = None, outlook: bool = True,
            hourly: bool = True, telegram_style: str | None = None,
            telegram: bool = False, sms: bool = False) -> dict:
    roh = preset_dict("basis")
    roh["id"] = preset_id
    roh["outlook_enabled"] = outlook
    roh["hourly_enabled"] = hourly
    roh["send_telegram"] = telegram
    roh["send_sms"] = sms
    if location_ids is not None:
        roh["location_ids"] = list(location_ids)
    dc = roh.setdefault("display_config", {})
    dc["channel_active_metrics"] = {
        "email": [{"metric_id": m, "aggregation": AGG[m]} for m in GEWAEHLT]}
    if email_format is not None:
        dc["email_format"] = email_format
    if telegram_style is not None:
        dc["telegram_style"] = telegram_style
    return roh


@dataclasses.dataclass
class Zustellung:
    uid: str
    roh: dict
    sendung: dict         # Aufzeichnung an EmailOutput.send
    msg: email.message.EmailMessage
    telegram: list
    sms: list


class _Engine:
    """Wetter offline: Werte aus ``build_result``; Orte ausserhalb von ``ORTE``
    (Massentest) erhalten die Werte des ersten Katalogorts."""

    def __enter__(self):
        import services.comparison_engine as ce_mod
        import services.scheduler_dispatch_service as sds_mod
        from app.user import ComparisonResult

        self._ce, self._sds = ce_mod, sds_mod
        self._alt = (ce_mod.ComparisonEngine, sds_mod._write_compare_alert_snapshots)
        je_ort = _ergebnis_je_ort()
        vorlage0 = next(iter(je_ort.values()))

        class KatalogEngine(self._alt[0]):  # echte Subklasse, kein Mock
            @staticmethod
            def run(*args, **kwargs):
                locations = kwargs.get("locations")
                if locations is None and args:
                    locations = args[0]
                aus = []
                for loc in list(locations or []):
                    v = je_ort.get(loc.id, vorlage0)
                    idx = ORTE[loc.id][3] if loc.id in ORTE else 0
                    aus.append(dataclasses.replace(
                        v, location=loc,
                        outlook_hourly_data=v.outlook_hourly_data or _ausblick_fuer(idx)))
                return ComparisonResult(
                    locations=aus, time_window=kwargs.get("time_window", (9, 16)),
                    target_date=kwargs.get("target_date", ZIELTAG),
                    created_at=datetime(2026, 10, 29, 4, 0))

        ce_mod.ComparisonEngine = KatalogEngine
        sds_mod._write_compare_alert_snapshots = lambda *a, **k: None
        return self

    def __exit__(self, *exc):
        self._ce.ComparisonEngine, self._sds._write_compare_alert_snapshots = self._alt
        return False


def _ablegen(uid: str, roh: dict) -> dict:
    from tests.helpers.tabelle_aus_wunsch import orte_wunsch_als_tabelle
    from tests.tdd._compare_kette_fixtures import preset_ablegen

    roh = orte_wunsch_als_tabelle(copy.deepcopy(roh))
    pfad = preset_ablegen(uid, roh)
    return json.loads(pfad.read_text(encoding="utf-8"))


def zustellen(monkeypatch, roh: dict, *, uid: str | None = None,
              language: str | None = None, extra_orte: list | None = None) -> Zustellung:
    from freezegun import freeze_time

    from app.config import Settings
    from app.loader import get_data_root, load_all_locations, save_location
    from output.channels.email import build_mime_message
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.tdd._compare_kette_fixtures import preset_laden

    mit = aufzeichner_installieren(monkeypatch)
    uid = profil_anlegen(uid, language=language)
    orte_anlegen(uid)
    for loc in extra_orte or []:
        save_location(loc, user_id=uid)
    gespeichert = _ablegen(uid, roh)
    telegram: list = []
    sms: list = []
    with transport_umgebung(), _Engine(), freeze_time(JETZT_UTC):
        settings = Settings().with_user_profile(uid)
        preset = preset_laden(uid, roh["id"])
        send_one_compare_preset(
            preset, settings, uid, str(get_data_root()),
            all_locations_cache=load_all_locations(user_id=uid),
            target_date=ZIELTAG, tage_ab_ortstag=0,
            telegram_sink=telegram.append, sms_sink=lambda t, *a, **k: sms.append(t),
        )
    mails = mit.sendungen("email")
    assert len(mails) == 1, f"Vorbedingung: genau eine Mail erwartet: {mit!r}"
    s = mails[0]
    kompakt = s["mail_format"] == "compact"
    msg = build_mime_message(
        subject=s["subject"], body=s["body"], from_addr="gregor@example.invalid",
        to_header=s["empfaenger"], reply_to=None, html=not kompakt,
        plain_text_body=None if kompakt else s["plain_text_body"],
        mail_type=s["mail_type"], mail_format=s["mail_format"], lang=language or "de",
    )
    msg = email.message_from_bytes(msg.as_bytes(), policy=policy.default)
    return Zustellung(uid, gespeichert, s, msg, telegram, sms)


def _text(z: Zustellung) -> str:
    teil = z.msg.get_body(("plain",))
    assert teil is not None, "kein Klartext-Teil"
    return teil.get_content()


def _ortszeile(text: str, name: str) -> str:
    treffer = [z for z in text.splitlines()
               if z.strip().startswith(name) or re.search(rf"\b{re.escape(name)}\b", z)]
    assert treffer, f"keine Zeile fuer Ort {name!r} in:\n{text}"
    return treffer[0]


def _pruefe_kompakt_mime(z: Zustellung) -> str:
    msg = z.msg
    assert msg["X-GZ-Format"] == "compact", f"X-GZ-Format={msg['X-GZ-Format']!r}, erwartet compact"
    assert msg["X-GZ-Mail-Type"] == "compare", f"X-GZ-Mail-Type={msg['X-GZ-Mail-Type']!r}"
    assert not msg.is_multipart(), "Kompakt-Mail muss genau EIN Teil sein (kein multipart)"
    assert msg.get_content_type() == "text/plain", msg.get_content_type()
    text = msg.get_content()
    assert text.isascii(), "Kompakt-Mail muss reines ASCII sein"
    return text


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dc_wert, soll", [
    ("compact", "compact"), ("full", "full"), (None, "full"), ("quatsch", "full"),
])
def test_resolver_email_format_aus_display_config(dc_wert, soll):
    """Resolver: ``display_config.email_format`` -> ``CompareRenderOptions.email_format``;
    fehlend oder unbekannt = "full" (Bestand bleibt ausfuehrlich)."""
    from services.report_config_resolver import resolve_compare_render_options

    roh = _preset(email_format=dc_wert)
    opts = resolve_compare_render_options(roh)
    assert getattr(opts, "email_format", None) == soll


# ---------------------------------------------------------------------------
# AC-1 / AC-2
# ---------------------------------------------------------------------------


def test_ac1_kompakt_ein_textteil_mit_zeile_je_ort(monkeypatch):
    """AC-1: Kompakt mit drei Orten -> ein text/plain-Teil, ``X-GZ-Format:
    compact``, je Ort eine Zeile mit Name und den Kuerzeln der gewaehlten Werte."""
    z = zustellen(monkeypatch, _preset())
    text = _pruefe_kompakt_mime(z)
    for name in NAMEN:
        zeile = _ortszeile(text, name)
        for mid in GEWAEHLT:
            k = _kuerzel(mid)
            assert re.search(rf"(?<![A-Za-z]){re.escape(k)}\s*[-+]?\d", zeile), (
                f"AC-1: Ort {name}: Kuerzel {k!r} ({mid}) mit Wert fehlt in {zeile!r}")
        for mid in NICHT_GEWAEHLT:
            k = _kuerzel(mid)
            assert not re.search(rf"(?<![A-Za-z]){re.escape(k)}\s*[-+]?\d", zeile), (
                f"AC-1: Ort {name}: nicht gewaehltes {k!r} ({mid}) steht in {zeile!r}")


def test_ac2_bestand_ohne_feld_bleibt_ausfuehrlich(monkeypatch):
    """AC-2: Abo ohne ``email_format`` -> unveraendert multipart/alternative
    mit HTML-Vergleichstabelle und Klartext (Regressionswaechter)."""
    z = zustellen(monkeypatch, _preset(email_format=None))
    assert "email_format" not in z.roh.get("display_config", {}), "Vorbedingung: Feld fehlt"
    assert z.msg.is_multipart() and z.msg.get_content_type() == "multipart/alternative"
    assert z.msg["X-GZ-Format"] in (None, "full")
    html = z.msg.get_body(("html",)).get_content()
    assert "<table" in html and all(n in html for n in NAMEN)


# ---------------------------------------------------------------------------
# AC-4 / AC-5 (Mail)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac4_ausblick_nur_wenn_eingeschaltet(monkeypatch, lang):
    """AC-4: Ausblick an -> unter jedem Ort genau eine Ausblick-Zeile; aus -> keine."""
    name = _katalog("mail.ausblick.name", lang)
    an = _pruefe_kompakt_mime(zustellen(monkeypatch, _preset(outlook=True), language=lang))
    zeilen = [z for z in an.splitlines() if z.strip().startswith(name)]
    assert len(zeilen) == len(NAMEN), f"AC-4: {len(zeilen)} Ausblick-Zeilen, erwartet {len(NAMEN)}:\n{an}"
    aus = _pruefe_kompakt_mime(zustellen(monkeypatch, _preset(outlook=False), language=lang))
    assert name not in aus, f"AC-4: Ausblick aus, steht aber drin:\n{aus}"


def test_ac5_kein_stundenverlauf_trotz_schalter(monkeypatch):
    """AC-5 (Mail): Stundenverlauf an, Kompakt -> keine Stundenwerte (hh:00)."""
    text = _pruefe_kompakt_mime(zustellen(monkeypatch, _preset(hourly=True, outlook=False)))
    stunden = re.findall(r"\b\d{2}:00\b", text)
    assert not stunden, f"AC-5: Stundenverlauf in Kompakt-Mail: {stunden}\n{text}"


# ---------------------------------------------------------------------------
# AC-6 / AC-7 / AC-8
# ---------------------------------------------------------------------------


def _viele_orte(n: int) -> list:
    from app.user import SavedLocation

    return [SavedLocation(id=f"loc-massen-{i:02d}", name=f"Massenort{i:02d}",
                          lat=46.0 + i * 0.01, lon=11.0, elevation_m=1500,
                          timezone="Europe/Vienna") for i in range(n)]


@pytest.mark.parametrize("lang, hinweis_re", [
    ("de", r"^\+(\d+) Orte nicht gezeigt$"),
    ("en", r"^\+(\d+) locations not shown$"),
])
def test_ac6_ac7_kuerzung_bei_vielen_orten(monkeypatch, lang, hinweis_re):
    """AC-6/AC-7: 40 Orte -> <= 2 KB, erste Orte vollstaendig, Hinweis mit
    richtiger Restzahl in der Nutzersprache, reines ASCII, ``X-GZ-Lang``."""
    orte = _viele_orte(40)
    z = zustellen(monkeypatch, _preset(location_ids=[o.id for o in orte], outlook=True),
                  language=lang, extra_orte=orte)
    text = _pruefe_kompakt_mime(z)
    assert len(text.encode("ascii")) <= GRENZE_BYTES, f"AC-6: {len(text.encode())} Byte > 2 KB"
    zeilen = [l.strip() for l in text.splitlines() if l.strip()]
    hinweise = [(i, m) for i, l in enumerate(zeilen) if (m := re.match(hinweis_re, l))]
    assert len(hinweise) == 1, f"AC-6: Hinweiszeile fehlt/doppelt:\n{text}"
    gezeigt = [o.name for o in orte if any(o.name in l for l in zeilen)]
    assert gezeigt == [o.name for o in orte[:len(gezeigt)]], "AC-6: gezeigt sind nicht die ERSTEN Orte"
    assert int(hinweise[0][1].group(1)) == len(orte) - len(gezeigt), "AC-6: Restzahl falsch"
    assert z.msg["X-GZ-Lang"] == lang
    if lang == "en":
        assert "Orte" not in text and "Ausblick" not in text, f"AC-7: deutsche Reste:\n{text}"


def test_ac7_englisch_ausblick_name_und_kuerzel_unuebersetzt(monkeypatch):
    """AC-7: EN-Nutzer -> "3-day outlook", Kuerzel unveraendert."""
    text = _pruefe_kompakt_mime(zustellen(monkeypatch, _preset(), language="en"))
    assert "3-day outlook" in text
    zeile = _ortszeile(text, NAMEN[0])
    for mid in GEWAEHLT:
        assert re.search(rf"(?<![A-Za-z]){re.escape(_kuerzel(mid))}\s*[-+]?\d", zeile)


def test_ac8_umlaut_ortsname_ascii_gefaltet(monkeypatch):
    """AC-8: Ort "Münster" -> "Muenster", Mail rein ASCII."""
    from app.user import SavedLocation

    ort = SavedLocation(id="loc-muenster", name="Münster", lat=51.96, lon=7.63,
                        elevation_m=60, timezone="Europe/Berlin")
    roh = _preset(location_ids=["loc-muenster", *ORTE.keys()])
    text = _pruefe_kompakt_mime(zustellen(monkeypatch, roh, extra_orte=[ort]))
    assert "Muenster" in text, f"AC-8: gefalteter Name fehlt:\n{text}"


# ---------------------------------------------------------------------------
# AC-9 Zwei Nutzer
# ---------------------------------------------------------------------------


def test_ac9_zwei_nutzer_eigenes_format_eigene_orte(monkeypatch):
    """AC-9: Nutzer A Kompakt, Nutzer B Ausfuehrlich -> jeder nur eigene Orte
    im eigenen Format; nie "default"."""
    from app.user import SavedLocation

    ort_b = SavedLocation(id="loc-nur-b", name="Bortort", lat=47.1, lon=11.2,
                          elevation_m=900, timezone="Europe/Vienna")
    a = zustellen(monkeypatch, _preset(preset_id="orte-a", email_format="compact"))
    b = zustellen(monkeypatch, _preset(preset_id="orte-b", email_format="full",
                                       location_ids=["loc-nur-b"]), extra_orte=[ort_b])
    assert a.uid != b.uid and "default" not in (a.uid, b.uid)
    text_a = _pruefe_kompakt_mime(a)
    assert "Bortort" not in text_a
    assert b.msg.is_multipart() and b.msg["X-GZ-Format"] in (None, "full")
    plain_b = b.msg.get_body(("plain",)).get_content()
    assert "Bortort" in plain_b and not any(n in plain_b for n in NAMEN)
    assert a.sendung["empfaenger"] != b.sendung["empfaenger"]


# ---------------------------------------------------------------------------
# AC-10 Vorschau = Versand
# ---------------------------------------------------------------------------


def test_ac10_vorschau_zeigt_denselben_kompakttext(monkeypatch):
    """AC-10: Vorschau (``render_all_channels``) liefert bei Kompakt leeres HTML
    und denselben Kompakttext wie die Zustellung."""
    from freezegun import freeze_time

    from services.compare_preview_service import ComparePreviewService

    z = zustellen(monkeypatch, _preset(preset_id="orte-vorschau"))
    versand = _pruefe_kompakt_mime(z)
    with transport_umgebung(), _Engine(), freeze_time(JETZT_UTC):
        vorschau = ComparePreviewService().render_all_channels(
            "orte-vorschau", user_id=z.uid, target_date=ZIELTAG.isoformat())
    assert vorschau.get("email_html") == "", "AC-10: Vorschau zeigt HTML statt Kompakt"
    assert vorschau.get("email_text") == versand, "AC-10: Vorschau-Text != zugestellter Text"


# ---------------------------------------------------------------------------
# AC-11 Δ-Anker / AC-12 andere Kanaele
# ---------------------------------------------------------------------------


def test_ac11_anker_im_kompaktpfad_wie_im_vollpfad(monkeypatch):
    """AC-11: Der Kompaktpfad laeuft durch denselben Anker-Baustein wie der
    Vollpfad: nach erfolgreichem Versand ist ``briefing_sent`` fuer das Abo
    gesetzt (Δ-Anker/Gedaechtnis-Reset, #1467/#1629).

    Hinweis: Den Fehlerpfad (Ausnahme im Versand) regelt #1629 fuer beide
    Formate gleich (Anker wird trotzdem geschrieben); er ist dort getestet
    (``test_compare_briefing_anchor_survives_dispatch_failure.py``) und wird hier
    nicht umgedeutet."""
    import services.scheduler_dispatch_service as sds_mod

    aufrufe: list[dict] = []
    original = sds_mod.write_anchor_and_reset_memory

    def zaehlend(**kw):
        aufrufe.append(kw)
        return original(**kw)

    monkeypatch.setattr(sds_mod, "write_anchor_and_reset_memory", zaehlend)
    z = zustellen(monkeypatch, _preset(preset_id="orte-anker"))
    _pruefe_kompakt_mime(z)
    assert len(aufrufe) == 1, f"AC-11: Anker-Baustein {len(aufrufe)}x aufgerufen, erwartet 1"
    assert aufrufe[0]["briefing_entity_id"] == "orte-anker"
    assert sorted(aufrufe[0]["entity_ids"]) == sorted(f"orte-anker:{lid}" for lid in ORTE)


def test_ac12_telegram_und_sms_unabhaengig_vom_mailformat(monkeypatch):
    """AC-12: Kompakt wirkt allein auf die E-Mail; Telegram (Stil rich) und SMS
    sind byte-gleich zum Ausfuehrlich-Abo."""
    kurz = zustellen(monkeypatch, _preset(preset_id="orte-k12", telegram=True, sms=True))
    voll = zustellen(monkeypatch, _preset(preset_id="orte-k12", email_format="full",
                                          telegram=True, sms=True))
    _pruefe_kompakt_mime(kurz)
    assert kurz.telegram and kurz.telegram == voll.telegram, "AC-12: Telegram weicht ab"
    assert kurz.sms == voll.sms, "AC-12: SMS weicht ab"
