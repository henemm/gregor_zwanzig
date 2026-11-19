"""Orte-Ausgaben lesen die Tabelle "Was steht wo" (Issue #3122, Scheibe B1b).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md (Teil A Nr. 2, 3, 6, 7;
AC-1, AC-2, AC-4, AC-5, AC-7, AC-8, AC-9, AC-10), ADR-0124.

Echter Weg wie im Betrieb: rohes Preset-JSON mit ``display_config.placements``
im Nutzerordner -> ``load_compare_presets`` -> ``send_one_compare_preset``
(Morgen- bzw. Abend-Slot ueber den Tagesversatz) -> ``NotificationService`` ->
Transport-Mitschrift (``tests/helpers/transport_mitschrift.py``). Einzige
Naehte: Wetter (``ComparisonEngine.run``, echte Subklasse aus
``tests/helpers/einstellung_gleich_mail_orte.py``) und Transport. Das Soll
steht von Hand im Test bzw. kommt aus der gespeicherten Tabelle, nie aus
``resolve_*``-Produktfunktionen. Katalogfaelle: ``fallliste_orte.json``,
Kennungen ``O-3122-*``.
"""
from __future__ import annotations

import copy
import re
from datetime import timedelta

import pytest

from tests.helpers.einstellung_gleich_mail_orte import (
    ORTSNAMEN, ZIELTAG, html_ausblick, html_stundenverlauf,
    html_vergleichstabelle, html_vergleichszellen, katalogtext, kennungen,
    klartext_ausblick, klartext_stundenverlauf, klartext_vergleichstabelle,
    orte_anlegen, preset_dict, wetter_naht,
)
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    nutzer_anlegen, preset_ablegen, preset_laden, settings_fuer, transport_einrichten,
)

#: Grundauswahl (Maximum, Speicherform des Editors): Temperatur mit zwei
#: Auswertungen, Folge bewusst ungleich der Tabellen-Folge.
GRUND = [("temperature", "max"), ("temperature", "min"), ("wind", "max"), ("gust", "max"),
         ("precipitation", "sum"), ("rain_probability", "max"), ("sunshine", "sum"),
         ("cloud_total", "avg")]

AN = {"email": True, "telegram": True, "sms": True, "hourly": True, "outlook": True}


def zeile(metric_id: str, **places) -> dict:
    """Gespeicherte Zeile: ``places`` ueberschreibt die Haken (fehlt = an)."""
    return {"metric_id": metric_id, "places": {**AN, **places}}


#: Tabelle mit je Stelle unterschiedlichen Haken; Folge ungleich Grundauswahl.
ZEILEN = [
    zeile("gust"),
    zeile("precipitation", telegram=False),
    zeile("temperature", sms=False),
    zeile("cloud_total", email=False, telegram=False),
    zeile("wind", email=False),          # Stundenverlauf/Ausblick gespeichert an (AC-4)
    zeile("sunshine", hourly=True),      # Stundenverlauf gesperrt (AC-7)
    zeile("rain_probability", telegram=False, sms=False),
    zeile("visibility"),                 # ausserhalb der Grundauswahl (AC-2)
]


def preset(zeilen=None, *, outlook_reports=("evening",), grund=GRUND, **top) -> dict:
    p = preset_dict("basis")
    p["id"] = "orte-tabelle"
    p["display_config"] = {
        "active_metrics": [{"metric_id": m, "aggregation": a} for m, a in grund],
        "placements": {"version": 1, "rows": copy.deepcopy(ZEILEN if zeilen is None else zeilen)},
    }
    if outlook_reports is not None:
        p["display_config"]["placements"]["outlook_reports"] = list(outlook_reports)
    p.update(send_telegram=True, send_sms=True, send_premium_sms=True,
             morning_enabled=True, evening_enabled=True,
             # Briefing-Absicht fuer die Premium-SMS (#2293 S2): alert_channels vorhanden.
             alert_channels={"email": True, "telegram": False, "sms": False, "premium_sms": False})
    p.update(top)
    return p


@pytest.fixture
def mit(monkeypatch):
    transport_einrichten(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def senden(mit, p: dict, *, slot: str = "morning", uid: str | None = None) -> dict:
    """Ein Briefing ueber den echten Versandweg; ``slot`` waehlt Morgen
    (Versatz 0) oder Abend (Versatz 1) wie der Slot-Scheduler."""
    from app.loader import get_data_root, load_all_locations
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = uid or nutzer_anlegen("premium")
    orte_anlegen(uid)
    preset_ablegen(uid, copy.deepcopy(p))
    versatz = 1 if slot == "evening" else 0
    mit.leeren()
    with wetter_naht():
        send_one_compare_preset(
            preset_laden(uid, p["id"]), settings_fuer(uid), uid, str(get_data_root()),
            all_locations_cache=load_all_locations(user_id=uid),
            target_date=ZIELTAG + timedelta(days=versatz), tage_ab_ortstag=versatz,
        )
    mail = mit.sendungen("email")
    assert len(mail) == 1, f"Vorbedingung: genau eine Mail, {mit!r}"
    aus = {"uid": uid, "html": mail[0]["body"], "plain": mail[0]["plain_text_body"],
           "hourly_header": mail[0].get("compare_hourly_enabled")}
    for kanal in ("telegram", "sms", "premium_sms"):
        sendungen = mit.sendungen(kanal)
        assert len(sendungen) == 1, f"Vorbedingung: genau eine {kanal}-Sendung, {mit!r}"
        aus[kanal] = sendungen[0]["body"]
    return aus


# ---------------------------------------------------------------------------
# Parser fuer Telegram und SMS (von Hand, Beschriftungen aus dem Register)
# ---------------------------------------------------------------------------

#: Telegram-Zellbeschriftung je Zeile (DE, von Hand wie test_3047_runde7_orte_kanaele).
TG = {"gust": "Böen", "temperature": "Temp", "wind": "Wind", "precipitation": "Regen",
      "rain_probability": "Regenwahrscheinlichkeit", "cloud_total": "Wolken",
      "sunshine": "Sonne", "visibility": "Sicht"}
#: SMS-Kuerzel je Zeile (von Hand, sms_format.md).
KUERZEL = {"gust": "G", "temperature": "D", "wind": "W", "precipitation": "R",
           "rain_probability": "PR", "cloud_total": "CT", "sunshine": "SU", "visibility": "V"}


def tg_bloecke(tg: str) -> dict[str, list[str]]:
    """Telegram -> {Ort: eingerueckte Zeilen des Ortsblocks}."""
    bloecke: dict[str, list[str]] = {}
    aktuell = None
    for z in tg.splitlines():
        if z in ORTSNAMEN:
            aktuell = bloecke.setdefault(z, [])
        elif aktuell is not None and z.startswith("   "):
            aktuell.append(z.strip())
    return bloecke


def _tg_kopf() -> str:
    return katalogtext("telegram.kopf.ausblick")


def tg_werte(block: list[str]) -> list[str]:
    """Zell-Kennungen der Telegram-Liste eines Ortes (ohne Ausblick), in Folge."""
    if _tg_kopf() in block:
        block = block[:block.index(_tg_kopf())]
    zellen = [c for z in block if " · " in z or re.match(r"^\S+ \S", z) for c in z.split(" · ")]
    aus = []
    for c in zellen:
        treffer = [m for m, n in TG.items() if c.startswith(n + " ")]
        if treffer:
            aus.append(max(treffer, key=lambda m: len(TG[m])))
    return aus


def tg_ausblick(block: list[str]) -> list[str] | None:
    """Zeilen des Telegram-Ausblicks eines Ortes; ``None`` = kein Ausblick."""
    if _tg_kopf() not in block:
        return None
    return block[block.index(_tg_kopf()) + 1:]


def tg_ausblick_zellen(block: list[str]) -> dict[str, str] | None:
    """{Spaltenkopf: Wert des ersten Tages} des Telegram-Ausblicks eines Ortes;
    ``None`` = kein Ausblick."""
    zeilen = tg_ausblick(block)
    if zeilen is None:
        return None
    aus: dict[str, str] = {}
    for z in zeilen:
        for teil in z.split("  "):
            m = re.match(r"^(\S+): (.+)$", teil.strip())
            if m:
                aus.setdefault(m.group(1), m.group(2))
    return aus


def sms_kuerzel(sms: str, name: str) -> list[str]:
    """Kuerzel-Folge eines Ortes in der SMS (#3172, Token-Zeile der Trip-SMS
    ohne Namen: ``O1 G30@8(38@16) R- CT78@16``; ``O{n}`` = Stelle in
    ``ORTSNAMEN``). Ein Ort ohne Token steht nur als ``O{n}`` da."""
    from tests.helpers.orte_sms import orte_kuerzel, orte_teil

    ort = orte_teil(sms, ORTSNAMEN.index(name) + 1)
    return [k for k in orte_kuerzel(ort) if k in KUERZEL.values()]


def uebersicht_beschriftungen(html: str) -> list[str]:
    """Zeilenbeschriftungen der HTML-Uebersicht im Wortlaut (mit Auswertung)."""
    from tests.helpers.einstellung_gleich_mail_orte import _TABLE_RE, _zellen

    for m in _TABLE_RE.finditer(html):
        zeilen = _zellen(m.group(1))
        if zeilen and zeilen[0] and zeilen[0][0] == "Metrik":
            return [z[0] for z in zeilen[1:] if z and z[0] != "Amtliche Warnungen"]
    raise AssertionError("Uebersicht nicht gefunden")


def kopf(metric_id: str) -> str:
    from app.metric_catalog import get_metric

    return get_metric(metric_id).col_label


def ausblick_ids(aus: dict) -> dict[str, list[str] | None]:
    """Ausblick-Kennungen je Ausgabe (erster Ort); ``None`` = Block fehlt."""
    html = html_ausblick(aus["html"]).get(ORTSNAMEN[0])
    plain = klartext_ausblick(aus["plain"]).get(ORTSNAMEN[0])
    tg = tg_ausblick_zellen(tg_bloecke(aus["telegram"])[ORTSNAMEN[0]])
    return {
        "html": None if html is None else kennungen(html),
        "klartext": None if plain is None else kennungen(plain),
        "telegram": None if tg is None else kennungen(list(tg)),
    }


def stunden_ids(aus: dict) -> dict[str, list[str] | None]:
    html = html_stundenverlauf(aus["html"]).get(ORTSNAMEN[0])
    plain = klartext_stundenverlauf(aus["plain"]).get(ORTSNAMEN[0])
    return {"html": None if html is None else kennungen(html),
            "klartext": None if plain is None else kennungen(plain)}


# ---------------------------------------------------------------------------
# AC-1: je Stelle genau die angehakten Metriken in der einen Reihenfolge
# ---------------------------------------------------------------------------

#: Soll aus ZEILEN (von Hand): Grundauswahl-Zeilen mit Haken an der Stelle, in
#: Tabellenfolge; Temperatur mit beiden Auswertungen (Hoechst-, dann Tiefstwert).
SOLL_EMAIL = ["gust", "precipitation", "temperature", "temperature", "sunshine", "rain_probability"]
SOLL_TELEGRAM = ["gust", "temperature", "temperature", "wind", "sunshine"]
SOLL_SMS = ["G", "R", "CT", "W", "SU"]


@pytest.mark.parametrize("slot", ["morning", "evening"])
def test_ac1_jede_stelle_zeigt_genau_ihre_haken(mit, slot):
    """AC-1 (Orte): Uebersicht (HTML, Nur-Text), Telegram und SMS zeigen je
    genau die dort angehakten Metriken in der Tabellenfolge; Premium-SMS =
    SMS. Zwei Nutzer, je eigene Zustellung."""
    laeufe = [senden(mit, preset(), slot=slot) for _ in range(2)]
    assert laeufe[0]["uid"] != laeufe[1]["uid"]
    for aus in laeufe:
        _orte, ids = html_vergleichstabelle(aus["html"])
        assert ids == SOLL_EMAIL, f"HTML-Uebersicht ({aus['uid']}): {ids}"
        beschriftung = uebersicht_beschriftungen(aus["html"])
        assert beschriftung[2:4] == ["Temperatur Maximum", "Temperatur Minimum"], beschriftung
        _folge, je_ort = klartext_vergleichstabelle(aus["plain"])
        for ort in ORTSNAMEN:
            assert je_ort[ort] == SOLL_EMAIL, f"Nur-Text {ort}: {je_ort[ort]}"
            assert tg_werte(tg_bloecke(aus["telegram"])[ort]) == SOLL_TELEGRAM, aus["telegram"]
            ist = sms_kuerzel(aus["sms"], ort)
            assert len(ist) >= 2 and ist == SOLL_SMS[:len(ist)], f"SMS {ort}: {ist} / {aus['sms']}"
        assert aus["telegram"].index("Temp max") < aus["telegram"].index("Temp min")
        assert aus["premium_sms"] == aus["sms"], "Premium-SMS weicht von der SMS ab"


# ---------------------------------------------------------------------------
# AC-2 / AC-7: ausserhalb der Grundauswahl und gesperrte Stelle
# ---------------------------------------------------------------------------

def test_ac2_zeile_ausserhalb_grundauswahl_erscheint_nirgends(mit):
    """AC-2: Sichtweite hat eine Zeile mit allen Haken, steht aber nicht in
    der Grundauswahl -- keine Stelle zeigt sie, auch Stundenverlauf und
    Ausblick nicht."""
    aus = senden(mit, preset(), slot="evening")
    assert "visibility" not in html_vergleichstabelle(aus["html"])[1]
    assert all("visibility" not in z for z in klartext_vergleichstabelle(aus["plain"])[1].values())
    for stelle, ids in {**stunden_ids(aus), **ausblick_ids(aus)}.items():
        assert ids is not None, f"Vorbedingung: Block {stelle} vorhanden"
        assert "visibility" not in ids, f"Sichtweite im Block {stelle}: {ids}"
    assert "Sicht" not in aus["telegram"] and f"{kopf('visibility')}:" not in aus["telegram"]
    assert " V " not in aus["sms"], aus["sms"]


def test_ac7_sonnenstunden_im_stundenverlauf_trotz_haken_nicht_da(mit):
    """AC-7 (Ausgabe): Sonnenstunden haben im Stundenverlauf keinen
    Stundenwert -- der gespeicherte Haken wirkt dort nicht; im Ausblick
    (eigene Ausgabe) stehen sie."""
    aus = senden(mit, preset(), slot="evening")
    for stelle, ids in stunden_ids(aus).items():
        assert ids and "sunshine" not in ids, f"Stundenverlauf {stelle}: {ids}"
    assert "sunshine" in ausblick_ids(aus)["html"]


# ---------------------------------------------------------------------------
# AC-4: ohne E-Mail-Haken fehlt die Metrik auch in Stundenverlauf und Ausblick
# ---------------------------------------------------------------------------

def test_ac4_ohne_email_haken_fehlt_in_stundenverlauf_und_ausblick(mit):
    """AC-4: Wind und Bewoelkung haben gespeicherte Haken in Stundenverlauf
    und Ausblick, aber keinen in der E-Mail: sie fehlen in Uebersicht,
    Stundenverlauf und im Ausblick von Mail (HTML, Nur-Text) und Telegram.
    Nach Wiederanhaken der E-Mail sind sie dort wieder da."""
    aus = senden(mit, preset(), slot="evening")
    assert not {"wind", "cloud_total"} & set(html_vergleichstabelle(aus["html"])[1])
    for stelle, ids in {**stunden_ids(aus), **ausblick_ids(aus)}.items():
        assert ids, f"Vorbedingung: Block {stelle} vorhanden"
        assert not {"wind", "cloud_total"} & set(ids), f"{stelle} zeigt Metrik ohne E-Mail-Haken: {ids}"

    wieder = [zeile(z["metric_id"], **{**z["places"], "email": True})
              if z["metric_id"] in ("wind", "cloud_total") else z for z in ZEILEN]
    aus = senden(mit, preset(wieder), slot="evening")
    assert {"wind", "cloud_total"} <= set(html_vergleichstabelle(aus["html"])[1])
    for stelle, ids in {**stunden_ids(aus), **ausblick_ids(aus)}.items():
        assert {"wind", "cloud_total"} <= set(ids or []), f"{stelle} nach Wiederanhaken: {ids}"


# ---------------------------------------------------------------------------
# AC-5: Format je Stelle unabhaengig
# ---------------------------------------------------------------------------

def _formate_zeilen(gust_telegram: str = "raw") -> list[dict]:
    return [
        {"metric_id": "gust", "places": AN, "formats": {
            "email": "simplified", "telegram": gust_telegram, "hourly": "simplified",
            "outlook": "raw"}},
        {"metric_id": "precipitation", "places": AN, "formats": {
            "email": "raw", "telegram": "simplified", "hourly": "raw", "outlook": "simplified"}},
        {"metric_id": "temperature", "places": AN},
    ]


def _zellen(aus: dict) -> dict:
    """Zellen je Stelle fuer den ersten Ort (Mail HTML/Nur-Text, Telegram)."""
    ort = ORTSNAMEN[0]
    tg = tg_bloecke(aus["telegram"])[ort]
    tg_liste = [c for z in tg[:tg.index(_tg_kopf())] for c in z.split(" · ")]
    uebersicht = aus["plain"].split(f"\n{ort}\n", 1)[1].split("\n\n", 1)[0]
    stunden = aus["plain"].split(f"\n{ort} (", 1)[1].splitlines()
    return {
        "html_uebersicht": {k: v[0] for k, v in html_vergleichszellen(aus["html"]).items()},
        "klartext_uebersicht": dict(re.findall(r"^   ([^:]+): (.*)$", uebersicht, re.M)),
        "stunden_zeile": next(z for z in stunden if re.match(r"^\s+\d\d:\d\d\s", z)),
        "ausblick_html": dict(html_ausblick(aus["html"])[ort]),
        "ausblick_klartext": dict(klartext_ausblick(aus["plain"])[ort]),
        "ausblick_telegram": tg_ausblick_zellen(tg),
        "telegram": {c.split(" ", 1)[0]: c for c in tg_liste},
    }


def test_ac5_format_je_stelle_unabhaengig(mit):
    """AC-5 (Orte): Boeen E-Mail Einfach (HTML Ampelpunkt, Nur-Text Wortstufe),
    Telegram Roh, Stundenverlauf Einfach, Ausblick Roh; Niederschlag
    umgekehrt. Umschalten der Telegram-Form der Boeen aendert nur Telegram."""
    z = _zellen(senden(mit, preset(_formate_zeilen()), slot="evening"))
    text, roh_html = z["html_uebersicht"]["gust"]
    assert "border-radius:50%" in roh_html and not text, f"HTML-Boeen ohne Ampelpunkt: {roh_html}"
    assert not re.search(r"\d", z["klartext_uebersicht"]["Böen"]), z["klartext_uebersicht"]
    assert re.search(r"\d", z["html_uebersicht"]["precipitation"][0])
    assert re.search(r"\d", z["klartext_uebersicht"]["Niederschlag"])
    assert re.search(r"\d", z["telegram"]["Böen"]), z["telegram"]
    assert not re.search(r"Regen \d", z["telegram"]["Regen"]), z["telegram"]
    assert re.search(r"Gust [^\d\s·]", z["stunden_zeile"]), z["stunden_zeile"]
    assert re.search(r"Rain (\d|·)", z["stunden_zeile"]), z["stunden_zeile"]
    for stelle in ("ausblick_html", "ausblick_klartext", "ausblick_telegram"):
        assert re.search(r"\d", z[stelle]["Gust"]), f"{stelle}: Boeen nicht roh: {z[stelle]}"
        assert not re.search(r"\d", z[stelle]["Rain"]), f"{stelle}: Regen nicht einfach: {z[stelle]}"

    um = _zellen(senden(mit, preset(_formate_zeilen("simplified")), slot="evening"))
    assert not re.search(r"\d", um["telegram"]["Böen"].split("@", 1)[0]), um["telegram"]
    for stelle in z:
        if stelle != "telegram":
            assert um[stelle] == z[stelle], f"Telegram-Umschalten aendert {stelle}"


@pytest.mark.xfail(strict=True, reason="#3122 offen_feature: Regenwahrscheinlichkeit "
                   "hat in der HTML-Uebersicht noch keinen Ampelpunkt (Spec Teil A Nr. 4)")
def test_ac5_regenwahrscheinlichkeit_einfach_html_ampelpunkt(mit):
    """AC-5/Spec Nr. 4: Regenwahrscheinlichkeit auf Einfach zeigt in der
    HTML-Uebersicht den Ampelpunkt (heute: Wortstufe). Renderer-Nachzug ist
    eine eigene Scheibe."""
    zeilen = [{"metric_id": "rain_probability", "places": AN, "formats": {"email": "simplified"}}]
    aus = senden(mit, preset(zeilen), slot="evening")
    _text, roh_html = html_vergleichszellen(aus["html"])["rain_probability"][0]
    assert "border-radius:50%" in roh_html, roh_html


# ---------------------------------------------------------------------------
# AC-8 / AC-9: Ausblick je Briefing-Typ, Stundenverlauf-Schalter
# ---------------------------------------------------------------------------

def _hat_ausblick(aus: dict) -> dict[str, bool]:
    return {k: v is not None for k, v in ausblick_ids(aus).items()}


ALLE = {"html": True, "klartext": True, "telegram": True}
KEINE = {"html": False, "klartext": False, "telegram": False}


def test_ac8_ausblick_nur_im_abend_briefing(mit):
    """AC-8 (Orte): ``outlook_reports: ["evening"]`` -> Ausblick abends in
    HTML-Mail, Nur-Text-Mail und Telegram, morgens in keiner."""
    p = preset(outlook_reports=["evening"])
    assert _hat_ausblick(senden(mit, p, slot="evening")) == ALLE
    assert _hat_ausblick(senden(mit, p, slot="morning")) == KEINE


def test_ac8_ausblick_nur_im_morgen_briefing(mit):
    p = preset(outlook_reports=["morning"])
    assert _hat_ausblick(senden(mit, p, slot="morning")) == ALLE
    assert _hat_ausblick(senden(mit, p, slot="evening")) == KEINE


def test_ac8_ausblick_beide_schalter_aus_nirgends(mit):
    """AC-8: ``outlook_reports: []`` -> in keinem Briefing ein Ausblick, auch
    wenn das Preset-Feld ``outlook_enabled`` noch an ist."""
    p = preset(outlook_reports=[], outlook_enabled=True)
    for slot in ("morning", "evening"):
        assert _hat_ausblick(senden(mit, p, slot=slot)) == KEINE, slot


@pytest.mark.parametrize("morgen, abend, soll", [
    (True, True, {"morning": KEINE, "evening": ALLE}),
    (True, False, {"morning": ALLE, "evening": KEINE}),
])
def test_ac9_vorbelegung_ohne_gespeicherte_ausblick_einstellung(mit, morgen, abend, soll):
    """AC-9 (Orte): ohne ``outlook_reports`` steht der Ausblick abends; ist nur
    das Morgen-Briefing eingeschaltet, morgens. Der Slot kommt aus dem
    Versandweg (Versatz), die eingeschalteten Briefings aus dem Abo."""
    p = preset(outlook_reports=None, morning_enabled=morgen, evening_enabled=abend)
    for slot, erwartet in soll.items():
        assert _hat_ausblick(senden(mit, p, slot=slot)) == erwartet, slot


def test_ac8_stundenverlauf_aus_schalter(mit):
    """``hourly_enabled: false`` -> kein Stundenverlauf (HTML, Nur-Text); der
    Mail-Kopf ``X-GZ-Compare-Hourly-Enabled`` traegt denselben Zustand."""
    aus = senden(mit, preset(hourly_enabled=False), slot="evening")
    assert stunden_ids(aus) == {"html": None, "klartext": None}
    assert aus["hourly_header"] is False
    an = senden(mit, preset(hourly_enabled=True), slot="evening")
    assert an["hourly_header"] is True and stunden_ids(an)["html"]


# ---------------------------------------------------------------------------
# AC-10: Spalte leer / Grundauswahl leer -> kein Rueckfall
# ---------------------------------------------------------------------------

def test_ac10_spalte_leer_kein_rueckfall(mit):
    """AC-10: Telegram-, Stundenverlauf- und Ausblick-Spalte ohne Haken -> dort
    keine Metrik, Stundenverlauf und Ausblick entfallen als Block (kein
    Rueckfall auf Grundauswahl oder Vorgabemenge)."""
    leer = [zeile(m, telegram=False, hourly=False, outlook=False) for m, _a in GRUND]
    aus = senden(mit, preset(leer), slot="evening")
    assert html_vergleichstabelle(aus["html"])[1], "Vorbedingung: Uebersicht gefuellt"
    assert stunden_ids(aus) == {"html": None, "klartext": None}
    assert _hat_ausblick(aus) == KEINE
    for ort in ORTSNAMEN:
        assert tg_werte(tg_bloecke(aus["telegram"])[ort]) == [], aus["telegram"]


def test_ac10_grundauswahl_bewusst_leer(mit):
    """AC-10: bewusst leere Grundauswahl -> keine Metrik an keiner Stelle,
    Stundenverlauf und Ausblick entfallen, auch nicht die Stundenverlauf-
    Vorgabemenge."""
    aus = senden(mit, preset(grund=[]), slot="evening")
    assert html_vergleichstabelle(aus["html"])[1] == []
    assert stunden_ids(aus) == {"html": None, "klartext": None}
    assert _hat_ausblick(aus) == KEINE
    for ort in ORTSNAMEN:
        assert tg_werte(tg_bloecke(aus["telegram"])[ort]) == []
        assert sms_kuerzel(aus["sms"], ort) == []


# ---------------------------------------------------------------------------
# Spalten-Legende und Mail-Kopf bei abgeschaltetem Stundenverlauf
# ---------------------------------------------------------------------------

def legende(aus: dict) -> dict[str, list[str]]:
    """Legenden-Zeilen ("Einheiten: ..."/"Spalten: ...") je Mail-Fassung."""
    import html as html_mod

    def zeilen(text: str) -> list[str]:
        return [z.strip() for z in text.splitlines()
                if z.strip().startswith(("Einheiten:", "Spalten:"))]

    return {"html": zeilen(html_mod.unescape(re.sub(r"<[^>]+>", "\n", aus["html"]))),
            "klartext": zeilen(aus["plain"])}


def test_tabelle_stundenverlauf_aus_ohne_rest_in_der_legende(mit):
    """Abo mit Tabelle, ``hourly_enabled: false``, Stundenverlauf-Haken
    gespeichert: kein Stundenverlauf und keine Einheiten-Zeile der
    Stundenspalten in HTML und Nur-Text (Block entfaellt ohne Rest); die
    Spalten-Zeile des Ausblicks bleibt."""
    aus = senden(mit, preset(hourly_enabled=False), slot="evening")
    assert stunden_ids(aus) == {"html": None, "klartext": None}
    for fassung, zeilen in legende(aus).items():
        assert not [z for z in zeilen if z.startswith("Einheiten:")], f"{fassung}: {zeilen}"
        assert [z for z in zeilen if z.startswith("Spalten:")], f"{fassung}: Ausblick-Legende fehlt"


def bestand(schalter, *, stunden: bool) -> dict:
    """Bestands-Abo ohne Tabelle (orte_basis.json) mit Stundenverlauf-Schalter."""
    p = preset_dict("basis")
    p.update(id="orte-bestand", send_telegram=True, send_sms=True, send_premium_sms=True,
             alert_channels={"email": True, "telegram": False, "sms": False, "premium_sms": False},
             hourly_enabled=schalter)
    if not stunden:
        p["display_config"]["hourly_metrics"] = []
    return p


#: Heutiger Stand (von Hand aus der zugestellten Mail vor #3122 B1b): die
#: Legende nennt die Stundenspalten auch bei abgeschaltetem Block, solange der
#: Ausblick sichtbar ist; ``Wind`` erklaert sich selbst (keine Spalten-Zeile).
EINHEITEN_BESTAND = "Einheiten: Temp °C · Wind, Gust km/h · Rain mm · Rain% %"
SPALTEN_BESTAND = ("Spalten: Temp = Temperatur · Gust = Böen · Rain = Niederschlag · "
                   "Rain% = Regenwahrscheinlichkeit")


@pytest.mark.parametrize("schalter, kopf_soll", [(False, False), (None, None)])
@pytest.mark.parametrize("stunden", [True, False])
def test_bestand_stundenverlauf_aus_legende_und_kopf_unveraendert(mit, schalter, kopf_soll, stunden):
    """Bestands-Abo ohne Tabelle, ``hourly_enabled: false`` bzw. ``null``, mit
    und ohne Stundenauswahl: kein Stundenverlauf; Legende (HTML, Nur-Text) und
    Mail-Kopf ``X-GZ-Compare-Hourly-Enabled`` wie heute (``null`` = kein Kopf)."""
    aus = senden(mit, bestand(schalter, stunden=stunden), slot="evening")
    assert stunden_ids(aus) == {"html": None, "klartext": None}
    soll = ([EINHEITEN_BESTAND] if stunden else []) + [SPALTEN_BESTAND]
    assert legende(aus) == {"html": soll, "klartext": soll}
    assert aus["hourly_header"] is kopf_soll
