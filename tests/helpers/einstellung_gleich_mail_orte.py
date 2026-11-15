"""Pruefkatalog "Einstellung = Mail", Kontext Orte (Issue #3047, Paket B).

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(§1 Orte-Kette, §2 Listen Orte, AC-5..AC-8, AC-10..AC-12, AC-21).

Kette wie im Betrieb: das Preset liegt als ROHES JSON (Persistenzformat des
Editors) im Nutzerverzeichnis einer isolierten Datenwurzel, wird vom ECHTEN
``load_compare_presets`` gelesen und ueber ``send_one_compare_preset``
versendet. Naehte:

* Wetter: ``ComparisonEngine.run`` (echte Subklasse, kein Mock) liefert die
  Ortsergebnisse aus ``tests.helpers.vergleichs_mail_fixture.build_result``
  (offline, deterministisch), umgehaengt auf die Orte dieses Katalogs.
* Transport: ``mail_sink`` mit Parameter ``plain_body`` -- HTML und Klartext
  stammen damit aus DERSELBEN Mail (``notification_service._sink_accepts_
  plain_body``). Die Empfaengeradresse ist der Rueckgabewert des Versands
  (``mail_to`` aus dem Profil des Nutzers).

Die Parser lesen nur die Mail; das Soll kommt aus dem rohen Preset-JSON
und den statischen Beschriftungen des Registers (``col_label``/Namen aus
``app.metric_catalog``), nie aus ``resolve_*``-Produktfunktionen.

Nur innerhalb von pytest benutzen: die isolierte Datenwurzel stellt
``tests/conftest.py`` (autouse) bereit.
"""
from __future__ import annotations

import contextlib
import copy
import dataclasses
import html as html_mod
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Iterator, Optional

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_gleich_mail"

#: Orts-Kennung -> (Name, lat, lon, Index in ``build_result``).
ORTE: dict[str, tuple[str, float, float, int]] = {
    "loc-kronplatz": ("Kronplatz", 46.74, 11.95, 0),
    "loc-sulden": ("Sulden", 46.52, 10.59, 1),
    "loc-ahrntal": ("Ahrntal", 46.98, 11.95, 2),
}
ORTSNAMEN = tuple(v[0] for v in ORTE.values())

#: Feste Uhr (UTC) -- Erstellt-/Naechster-Versand-Zeilen bleiben stabil.
JETZT_UTC = "2026-10-29T04:00:00+00:00"
ZIELTAG = date(2026, 10, 29)


# ---------------------------------------------------------------------------
# Fixtures (rohe Preset-Dateien)
# ---------------------------------------------------------------------------


def preset_dict(name: str) -> dict:
    """Rohes ``json.load`` von ``orte_<name>.json`` -- frische Kopie je Aufruf."""
    pfad = FIXTURE_DIR / f"orte_{name}.json"
    return copy.deepcopy(json.loads(pfad.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Nutzer, Orte, Wetter-Naht
# ---------------------------------------------------------------------------


def profil_anlegen(uid: Optional[str] = None, *, language: Optional[str] = None) -> str:
    """Frisches Profil (eigene Kennung, eigener Empfaenger). ``uid`` fest nur
    fuer die Golden-Dateien (deterministischer Inhalt); nie ``"default"``."""
    from app.loader import get_data_dir
    from tests.tdd._einstellung_auslieferung_fixtures import frisches_profil

    if uid is None:
        uid = frisches_profil()
    else:
        assert uid != "default", "Mandantentrennung: nie die Kennung 'default'"
        ordner = get_data_dir(uid)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "user.json").write_text(json.dumps({
            "id": uid, "tier": "premium", "mail_to": f"{uid}@example.invalid",
        }), encoding="utf-8")
    if language is not None:
        pfad = get_data_dir(uid) / "user.json"
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        daten["language"] = language
        pfad.write_text(json.dumps(daten), encoding="utf-8")
    return uid


def orte_anlegen(uid: str) -> None:
    from app.loader import save_location
    from app.user import SavedLocation

    for lid, (name, lat, lon, _i) in ORTE.items():
        save_location(SavedLocation(id=lid, name=name, lat=lat, lon=lon,
                                    elevation_m=1500, timezone="Europe/Vienna"), user_id=uid)


def _ausblick_fuer(i: int) -> list:
    """Ausblick-Stunden wie ``build_result`` sie fuer Ort 0/1 erzeugt; Ort 2 hat
    dort absichtlich keinen Ausblick (Fehlerfall der Golden) -- hier wird er
    mit DERSELBEN Erzeugungsregel nachgereicht, damit jeder Ort eine
    Ausblick-Tabelle hat."""
    from tests.helpers.vergleichs_mail_fixture import _dp

    return [
        _dp(datetime(2026, 10, 30, 0, 0) + timedelta(days=d, hours=s), i, 8 + s // 2)
        for d in range(3) for s in range(0, 24, 3)
    ]


def _ergebnis_je_ort() -> dict:
    from tests.helpers.vergleichs_mail_fixture import build_result

    basis = build_result(mit_fehlerort=False)
    return {lid: basis.locations[i] for lid, (_n, _a, _o, i) in ORTE.items()}


@contextlib.contextmanager
def wetter_naht(warnungen: Optional[dict] = None) -> Iterator[None]:
    """``ComparisonEngine`` durch eine echte Subklasse ersetzen (je Ort ein
    Lauf, Werte aus ``build_result``) und den Delta-Anker-Schreiber (Netz)
    neutralisieren; danach alles zuruecksetzen. ``warnungen`` ({Orts-Kennung:
    [OfficialAlert]}) belegt ``official_alerts`` einzelner Orte (#3047 WV6)."""
    warnungen = warnungen or {}
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from app.user import ComparisonResult

    original_engine = ce_mod.ComparisonEngine
    original_anker = sds_mod._write_compare_alert_snapshots
    je_ort = _ergebnis_je_ort()

    class KatalogEngine(original_engine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            ergebnisse = []
            for loc in list(locations or []):
                vorlage = je_ort[loc.id]
                ausblick = vorlage.outlook_hourly_data or _ausblick_fuer(ORTE[loc.id][3])
                ergebnisse.append(dataclasses.replace(
                    vorlage, location=loc, outlook_hourly_data=ausblick,
                    official_alerts=list(warnungen.get(loc.id, vorlage.official_alerts))))
            return ComparisonResult(
                locations=ergebnisse, time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", ZIELTAG),
                created_at=datetime(2026, 10, 29, 4, 0),
            )

    ce_mod.ComparisonEngine = KatalogEngine
    sds_mod._write_compare_alert_snapshots = lambda *a, **k: None
    try:
        yield
    finally:
        ce_mod.ComparisonEngine = original_engine
        sds_mod._write_compare_alert_snapshots = original_anker


@contextlib.contextmanager
def transport_umgebung() -> Iterator[None]:
    """Jedes Transportfeld ausdruecklich unbrauchbar (#1477), danach zurueck."""
    from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV

    alt = {k: os.environ.get(k) for k in TRANSPORT_ENV}
    os.environ.update(TRANSPORT_ENV)
    try:
        yield
    finally:
        for k, v in alt.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# Versand ueber die echte Kette
# ---------------------------------------------------------------------------


@dataclass
class OrteMail:
    uid: str
    roh: dict            # JSON, wie es auf der Platte liegt
    subject: str
    html: str
    plain: str
    empfaenger: list


def sende_orte_mail(preset_json: dict, *, uid: Optional[str] = None,
                    language: Optional[str] = None,
                    warnungen: Optional[dict] = None) -> OrteMail:
    """Preset roh ablegen, ueber den echten Loader lesen, ueber
    ``send_one_compare_preset`` mit ``mail_sink(plain_body=...)`` versenden."""
    from freezegun import freeze_time

    from app.config import Settings
    from app.loader import get_data_root
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.tdd._compare_kette_fixtures import preset_ablegen, preset_laden

    uid = profil_anlegen(uid, language=language)
    orte_anlegen(uid)
    pfad = preset_ablegen(uid, preset_json)
    gesendet: list[dict] = []

    def sink(*, subject: str, body: str, plain_body: str) -> None:
        gesendet.append({"subject": subject, "html": body, "plain": plain_body})

    with transport_umgebung(), wetter_naht(warnungen), freeze_time(JETZT_UTC):
        from app.loader import load_all_locations

        settings = Settings().with_user_profile(uid)
        preset = preset_laden(uid, preset_json["id"])
        _top, empfaenger = send_one_compare_preset(
            preset, settings, uid, str(get_data_root()),
            all_locations_cache=load_all_locations(user_id=uid),
            target_date=ZIELTAG, tage_ab_ortstag=0, mail_sink=sink,
        )
    assert len(gesendet) == 1, f"Vorbedingung: genau eine Mail erwartet, {len(gesendet)} gesendet"
    m = gesendet[0]
    return OrteMail(uid, json.loads(pfad.read_text(encoding="utf-8")), m["subject"],
                    m["html"], m["plain"], list(empfaenger))


def baue_orte_eml(preset_json: dict, *, uid: Optional[str] = None,
                  language: Optional[str] = None) -> bytes:
    """Komplette Mail (multipart/alternative: Klartext + HTML, mit To/Subject/
    From und ``X-GZ-Mail-Type: compare``) aus der echten Kette -- fuer
    ``--eml``-Laeufe der Validatoren (Paket C). Nur in pytest (isolierte
    Datenwurzel) aufrufen."""
    mail = sende_orte_mail(preset_json, uid=uid, language=language)
    msg = EmailMessage()
    msg["Subject"] = mail.subject
    msg["From"] = "gregor@example.invalid"
    msg["To"] = ", ".join(mail.empfaenger)
    msg["X-GZ-Mail-Type"] = "compare"
    msg.set_content(mail.plain)
    msg.add_alternative(mail.html, subtype="html")
    return msg.as_bytes()


# ---------------------------------------------------------------------------
# Statisches Register (Beschriftungen, Katalogfolge) -- keine Aufloesung
# ---------------------------------------------------------------------------


def _katalog() -> list:
    from app.metric_catalog import get_all_metrics

    return list(get_all_metrics())


def katalogfolge(ids) -> list[str]:
    """``ids`` in der Folge des zentralen Registers (Vergleichsgroesse fuer
    "Reihenfolge ungleich Katalogfolge")."""
    rang = {m.id: i for i, m in enumerate(_katalog())}
    return sorted(ids, key=lambda k: rang[k])


def name_von(metric_id: str) -> str:
    """Langname (Zeilenbeschriftung Vergleichstabelle, ``label_de``)."""
    return next(m.label_de for m in _katalog() if m.id == metric_id)


def kopf_von(metric_id: str) -> str:
    """Spaltenkopf (``col_label``) in Stundenverlauf und Ausblick."""
    return next(m.col_label for m in _katalog() if m.id == metric_id)


_AGG_WOERTER = ("Maximum", "Minimum", "Mittel", "Summe")


def _id_aus(label: str, feld: str) -> str:
    """Beschriftung -> Kennung; unbekannte Beschriftung bleibt als
    ``?<label>`` sichtbar (eine fremde Zeile faellt im Vergleich auf)."""
    tafel = {getattr(m, feld): m.id for m in _katalog()}
    if label in tafel:
        return tafel[label]
    stamm, _, rest = label.rpartition(" ")
    if rest in _AGG_WOERTER and stamm in tafel:
        return tafel[stamm]
    return f"?{label}"


# ---------------------------------------------------------------------------
# Soll aus dem ROHEN Preset-JSON (ADR-0050: Grundauswahl = Maximum)
# ---------------------------------------------------------------------------


def _ids(rohliste) -> Optional[list[str]]:
    """Gespeicherte Liste (Paarform ``{metric_id, aggregation}`` oder Kennung)
    -> Kennungen in Speicherfolge, ohne Doppelte; ``None`` = Feld fehlt."""
    if not isinstance(rohliste, list):
        return None
    aus: list[str] = []
    for e in rohliste:
        mid = e.get("metric_id") if isinstance(e, dict) else e
        if isinstance(mid, str) and mid not in aus:
            aus.append(mid)
    return aus


def grundauswahl(roh: dict) -> Optional[list[str]]:
    return _ids((roh.get("display_config") or {}).get("active_metrics"))


def soll_vergleichstabelle(roh: dict) -> Optional[list[str]]:
    """Zeilen der Vergleichstabelle: E-Mail-Liste geschnitten mit der
    Grundauswahl, ohne Eintrag die Grundauswahl; ``None`` = weder Maximum noch
    Eintrag (Standardsatz des Produkts, nur "nicht leer" pruefbar)."""
    dc = roh.get("display_config") or {}
    basis = grundauswahl(roh)
    cam = dc.get("channel_active_metrics")
    if not isinstance(cam, dict) or "email" not in cam:
        return basis
    eintrag = _ids(cam["email"]) or []
    if basis is None:
        return eintrag
    return [m for m in eintrag if m in basis]


def soll_stundenverlauf(roh: dict, standard: tuple[str, ...]) -> Optional[list[str]]:
    """Spaltenkoepfe des Stundenverlaufs (ohne "Zeit"); ``None`` = Block fehlt.
    ``standard`` = Standardliste fuer "nie eingestellt" (der Abgleich mit dem
    Editor-Standard ist Paket D / AC-13). Spec AC-10/Konzept §5.8: eine Liste
    nimmt nur aus der Grundauswahl."""
    if roh.get("hourly_enabled", True) is False:
        return None
    gespeichert = _ids((roh.get("display_config") or {}).get("hourly_metrics"))
    liste = list(standard) if gespeichert is None else gespeichert
    basis = grundauswahl(roh)
    if gespeichert is not None and basis is not None:
        liste = [m for m in liste if m in basis]
    liste = [m for m in liste if m != "wind_direction"]  # reines Merge-Signal, keine Spalte
    return [kopf_von(m) for m in liste] or None


def soll_ausblick(roh: dict) -> Optional[list[str]]:
    """Kennungen der Ausblick-Spalten in Folge; ``None`` = Block fehlt.
    Nie eingestellt = ganze Grundauswahl in ihrer Folge; sonst Schnitt mit der
    Grundauswahl; Totalschnitt = dokumentierter Rueckfall auf die volle
    Grundauswahl (ADR-0050, #1848 A3)."""
    if roh.get("outlook_enabled", True) is False:
        return None
    gespeichert = _ids((roh.get("display_config") or {}).get("outlook_metrics"))
    basis = grundauswahl(roh)
    if gespeichert == []:
        return None
    if basis is None:
        return gespeichert
    if gespeichert is None:
        return list(basis)
    return [m for m in gespeichert if m in basis] or list(basis)


def soll_einfach(roh: dict) -> dict[str, bool]:
    """Gespeicherte Roh/Einfach-Zuordnung des Ausblicks (True = Einfach)."""
    f = (roh.get("display_config") or {}).get("outlook_metric_formats")
    return {k: v for k, v in f.items() if isinstance(v, bool)} if isinstance(f, dict) else {}


# ---------------------------------------------------------------------------
# Parser HTML
# ---------------------------------------------------------------------------

_TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL)
_ORT_RE = re.compile(r">ORT</span>\s*<span[^>]*>([^<]*)</span>")
_AUSBLICK_ORT_RE = re.compile(r">AUSBLICK</span>\s*<span[^>]*>([^<]*?) · ")


def _zellen(fragment: str) -> list[list[str]]:
    zeilen = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", fragment, re.DOTALL):
        zellen = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.DOTALL)
        zeilen.append([html_mod.unescape(re.sub(r"<[^>]+>", "", z)).strip() for z in zellen])
    return zeilen


def _tabellen(html: str) -> list[tuple[int, list[list[str]]]]:
    return [(m.start(), _zellen(m.group(1))) for m in _TABLE_RE.finditer(html)]


def html_vergleichstabelle(html: str) -> tuple[list[str], list[str]]:
    """(Orts-Spalten in Folge, Zeilen-Kennungen in Folge) der Uebersicht; die
    feste Zeile "Amtliche Warnungen" ist keine Metrik und bleibt aussen vor.
    Gelesen wird nur die Zeilenbeschriftung, nie die Zellform (Roh/Einfach der
    Vergleichstabelle aendert #3039)."""
    for _pos, zeilen in _tabellen(html):
        if zeilen and zeilen[0] and zeilen[0][0] == "Metrik":
            orte = [re.sub(r"^#\d+\s*", "", z) for z in zeilen[0][1:]]
            ids = [_id_aus(z[0], "label_de") for z in zeilen[1:]
                   if z and z[0] != "Amtliche Warnungen"]
            return orte, ids
    raise AssertionError("Vergleichstabelle (Kopf 'Metrik') nicht im HTML gefunden")


def _ort_marken(html: str) -> list[tuple[int, str]]:
    marken = [(m.start(), m.group(1).strip()) for m in _ORT_RE.finditer(html)]
    marken += [(m.start(), m.group(1).strip()) for m in _AUSBLICK_ORT_RE.finditer(html)]
    return sorted(marken)


def _tabellen_je_ort(html: str, erste_zelle: str) -> dict[str, list[list[str]]]:
    """{Ort: Zeilen} der Tabellen mit Kopf ``erste_zelle`` ("Zeit"/"Tag"),
    zugeordnet ueber die letzte Orts-Marke davor; Reihenfolge = Mail-Folge."""
    marken = _ort_marken(html)
    aus: dict[str, list[list[str]]] = {}
    for pos, zeilen in _tabellen(html):
        if not (zeilen and zeilen[0] and zeilen[0][0] == erste_zelle):
            continue
        davor = [ort for p, ort in marken if p < pos]
        assert davor, f"Tabelle '{erste_zelle}' ohne vorausgehenden Ort"
        assert davor[-1] not in aus, f"Ort {davor[-1]!r} hat zwei '{erste_zelle}'-Tabellen"
        aus[davor[-1]] = zeilen
    return aus


def html_stundenverlauf(html: str) -> dict[str, list[str]]:
    """{Ort: Spaltenkoepfe ohne "Zeit"} in Mail-Folge der Orte."""
    return {o: z[0][1:] for o, z in _tabellen_je_ort(html, "Zeit").items()}


def html_ausblick(html: str) -> dict[str, list[tuple[str, str]]]:
    """{Ort: [(Spaltenkopf, Zelle der ersten Tageszeile)]} in Mail-Folge."""
    aus = {}
    for ort, zeilen in _tabellen_je_ort(html, "Tag").items():
        kopf = zeilen[0][1:]
        erste = zeilen[1][1:] if len(zeilen) > 1 else [""] * len(kopf)
        aus[ort] = list(zip(kopf, erste))
    return aus


# ---------------------------------------------------------------------------
# Parser Klartext
# ---------------------------------------------------------------------------


def _zelltoken(zeile: str) -> list[tuple[str, str]]:
    """``Kopf Wert  Kopf Wert ...`` -> [(Kopf, Wert)]; ein Token ist Kopf, wenn
    es ein ``col_label`` des Registers ist (ein folgendes Aggregationswort
    gehoert zum Kopf)."""
    koepfe = {m.col_label for m in _katalog()}
    aus: list[list[str]] = []
    tokens = zeile.split()
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in koepfe:
            kopf = t
            if i + 1 < len(tokens) and tokens[i + 1] in _AGG_WOERTER:
                kopf, i = f"{t} {tokens[i + 1]}", i + 1
            aus.append([kopf, ""])
        elif aus:
            aus[-1][1] = f"{aus[-1][1]} {t}".strip()
        i += 1
    return [(k, v) for k, v in aus]


_ABSCHNITT_RE = re.compile(r"^([^:\s][^:]*?) \([A-Z]{2,5}\)$")  # ohne Doppelpunkt: nicht "Erstellt: ..."


def _abschnitte(plain: str) -> tuple[list[str], dict[str, list[str]]]:
    """Klartext -> (Uebersichtsteil, {Ort: Zeilen des Abschnitts "<Ort> (ZONE)"});
    ein Abschnitt endet an der Leerzeile."""
    zeilen = plain.splitlines()
    start = next((i for i, z in enumerate(zeilen)
                  if _ABSCHNITT_RE.match(z) or z == "STUNDENVERLAUF"), len(zeilen))
    abschnitte: dict[str, list[str]] = {}
    aktuell = None
    for z in zeilen[start:]:
        m = _ABSCHNITT_RE.match(z)
        if m:
            aktuell = m.group(1)
            abschnitte[aktuell] = []
        elif aktuell is not None:
            if not z.strip():
                aktuell = None
            else:
                abschnitte[aktuell].append(z)
    return zeilen[:start], abschnitte


def klartext_vergleichstabelle(plain: str, orte=ORTSNAMEN) -> tuple[list[str], dict[str, list[str]]]:
    """(Orts-Bloecke in Folge, {Ort: Zeilen-Kennungen in Folge})."""
    uebersicht, _ = _abschnitte(plain)
    folge: list[str] = []
    zeilen: dict[str, list[str]] = {}
    aktuell = None
    for z in uebersicht:
        if z in orte:
            aktuell = z
            folge.append(z)
            zeilen[z] = []
            continue
        m = re.match(r"^   ([^:]+): ", z)
        if aktuell is not None and m:
            zeilen[aktuell].append(_id_aus(m.group(1), "label_de"))
    return folge, zeilen


def klartext_stundenverlauf(plain: str) -> dict[str, list[str]]:
    """{Ort: Spaltenkoepfe der ersten Stundenzeile} (nur Orte mit Stundenzeilen)."""
    if "STUNDENVERLAUF" not in plain.splitlines():
        return {}
    _, abschnitte = _abschnitte(plain)
    aus = {}
    for ort, zeilen in abschnitte.items():
        stunden = [z for z in zeilen if re.match(r"^\s+\d\d:\d\d\s", z)]
        if stunden:
            aus[ort] = [k for k, _v in _zelltoken(stunden[0].split(None, 1)[1])]
    return aus


def klartext_ausblick(plain: str) -> dict[str, list[tuple[str, str]]]:
    """{Ort: [(Spaltenkopf, Wert)] der ersten Tageszeile nach '3-Tages-Ausblick'}."""
    _, abschnitte = _abschnitte(plain)
    aus = {}
    for ort, zeilen in abschnitte.items():
        if "3-Tages-Ausblick" not in zeilen:
            continue
        rest = zeilen[zeilen.index("3-Tages-Ausblick") + 1:]
        tag = next((z for z in rest if re.match(r"^\S{2}\s", z)), None)
        if tag is not None:
            aus[ort] = _zelltoken(tag.split(None, 1)[1])
    return aus


def kennungen(koepfe) -> list[str]:
    """Spaltenkoepfe (oder (Kopf, Zelle)-Paare) -> Kennungen; Aggregations-
    spalten derselben Groesse direkt hintereinander zaehlen einmal."""
    aus: list[str] = []
    for k in koepfe:
        mid = _id_aus(k[0] if isinstance(k, tuple) else k, "col_label")
        if not aus or aus[-1] != mid:
            aus.append(mid)
    return aus


def ist_zahl(zelle: str) -> bool:
    """Roh = die Zelle traegt eine Zahl; Einfach = Wort/Symbol ohne Ziffer."""
    return bool(re.search(r"\d", zelle))
