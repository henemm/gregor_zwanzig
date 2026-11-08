"""Profil-Ampel: Validierung, Aufloesung, Abweichungszahl, Gewitterfarbe.

Issue #2792 S1a, ADR-0106, Spec ``docs/specs/modules/feat_2792_s1_profil_ampel.md``
§1-§3. EIN Code fuer Trip (Objekt mit ``display_config`` als
``UnifiedWeatherDisplayConfig``) und Ortsvergleich (Dict oder ``ComparePreset``
mit ``display_config``-Dict und ``profil``).

Rueckfallkette: Abo-Ampel je Metrik -> Vorlage ``ampel.template`` bzw. Trip
``display_config.preset_name`` bzw. Compare ``profil`` -> Vorlage
„allgemein". In S1a liest noch kein Renderer diese Funktionen (S1c).
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Mapping, Sequence
from numbers import Real
from typing import Any, Optional

from app.ampel_templates import AMPEL_TEMPLATES, DEFAULT_TEMPLATE
from app.models import ThunderLevel

logger = logging.getLogger(__name__)

_LOWER = ("red", "orange", "yellow")  # aufsteigend: rot < orange < gelb
_UPPER = ("yellow", "orange", "red")  # aufsteigend: gelb < orange < rot
ALARM_AB = frozenset({"never", "yellow", "orange", "red"})
# Issue #2793 S2a (ADR-0106 P2): Gewitter „leicht" ist fest gelb und alarmiert nie.
ALARM_AB_GEWITTER = frozenset({"never", "orange", "red"})
_RANG = {"yellow": 1, "orange": 2, "red": 3}
_THUNDER_HOCH = frozenset({"orange", "red"})
_PROFIL_ZU_VORLAGE = {"summer_trekking": "alpen-trekking"}


def _feld(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _seite(werte: Any, keys: tuple, wo: str, fehler: list[str]) -> list:
    """Gesetzte Werte einer Seite in Schluessel-Reihenfolge (muss aufsteigen)."""
    if werte is None:
        return []
    if not isinstance(werte, Mapping):
        fehler.append(f"{wo}: keine Grenzen-Tabelle")
        return []
    gesetzt = []
    for k in keys:
        v = werte.get(k)
        if v is None:
            continue
        if not isinstance(v, Real) or isinstance(v, bool):
            fehler.append(f"{wo}.{k}: keine Zahl")
            continue
        gesetzt.append(v)
    if any(a >= b for a, b in zip(gesetzt, gesetzt[1:])):
        fehler.append(f"{wo}: Reihenfolge verletzt")
    return gesetzt


def _pruefe_metrik(mid: str, e: Any, fehler: list[str]) -> None:
    if not isinstance(e, Mapping):
        fehler.append(f"{mid}: kein Objekt")
        return
    unten = _seite(e.get("lower"), _LOWER, f"{mid}.lower", fehler)
    oben = _seite(e.get("upper"), _UPPER, f"{mid}.upper", fehler)
    if unten and oben and unten[-1] > oben[0]:
        fehler.append(f"{mid}: untere Grenze ueber der oberen")
    if e.get("alarm_ab") is not None and e.get("alarm_ab") not in ALARM_AB:
        fehler.append(f"{mid}.alarm_ab: unbekannt")
    elif mid == "thunder" and e.get("alarm_ab") not in (None, *ALARM_AB_GEWITTER):
        fehler.append("thunder.alarm_ab: nie gelb")
    if e.get("enabled") is not None and not isinstance(e.get("enabled"), bool):
        fehler.append(f"{mid}.enabled: kein Wahrheitswert")


def _pruefe_gewitter(th: Any, fehler: list[str]) -> None:
    if not isinstance(th, Mapping):
        fehler.append("thunder: kein Objekt")
        return
    mittel, hoch = th.get("mittel"), th.get("hoch")
    if mittel is not None and mittel not in _RANG:
        fehler.append("thunder.mittel: unbekannt")
    if hoch is not None and hoch not in _THUNDER_HOCH:
        fehler.append("thunder.hoch: nie gelb")
    if mittel in _RANG and hoch in _RANG and _RANG[hoch] < _RANG[mittel]:
        fehler.append("thunder.hoch: schwaecher als mittel")


def validate_ampel(ampel: Any) -> list[str]:
    """Fehlerliste (leer = gueltig). Gleiche Regeln wie Go ``validateAmpel``."""
    if ampel is None:
        return []
    if not isinstance(ampel, Mapping):
        return ["Ampel: kein Objekt"]
    fehler: list[str] = []
    if ampel.get("template") is not None and not isinstance(ampel.get("template"), str):
        fehler.append("template: kein Text")
    metrics = ampel.get("metrics")
    if metrics is not None and not isinstance(metrics, Mapping):
        fehler.append("metrics: kein Objekt")
    elif metrics:
        for mid, e in metrics.items():
            _pruefe_metrik(mid, e, fehler)
    if ampel.get("thunder") is not None:
        _pruefe_gewitter(ampel["thunder"], fehler)
    return fehler


def _bekannte_vorlage(tid: str, quelle: str) -> str:
    if tid in AMPEL_TEMPLATES:
        return tid
    logger.warning("Profil-Ampel: unbekannte Vorlage %r aus %s, nutze allgemein", tid, quelle)  # i18n-log
    return DEFAULT_TEMPLATE


def template_for_profil(profil: Optional[str]) -> str:
    """Compare-``profil`` -> Vorlagen-ID (Spec §3, Gross-/Kleinschreibung egal)."""
    if not profil:
        return DEFAULT_TEMPLATE
    key = str(profil).strip().lower()
    tid = _PROFIL_ZU_VORLAGE.get(key, key)
    if tid in AMPEL_TEMPLATES:
        return tid
    logger.warning("Profil-Ampel: unbekanntes Profil %r, nutze allgemein", profil)  # i18n-log
    return DEFAULT_TEMPLATE


def _abo_ampel(dc: Any) -> Optional[Mapping]:
    ampel = _feld(dc, "ampel")
    if ampel is None:
        return None
    fehler = validate_ampel(ampel)
    if fehler:
        logger.warning("Profil-Ampel ungueltig, Vorlage greift: %s", "; ".join(fehler))  # i18n-log
        return None
    return ampel


def _aufloesen(subscription: Any) -> tuple[str, Optional[Mapping]]:
    dc = _feld(subscription, "display_config")
    dc = subscription if dc is None else dc
    abo = _abo_ampel(dc)
    if abo and abo.get("template"):
        return _bekannte_vorlage(abo["template"], "ampel.template"), abo
    preset_name = _feld(dc, "preset_name")
    if preset_name:
        return _bekannte_vorlage(preset_name, "preset_name"), abo
    return template_for_profil(_feld(subscription, "profil")), abo


def template_id_for(subscription: Any) -> str:
    """ID der Vorlage, auf die ein Abo (Trip oder Compare) zurueckfaellt."""
    return _aufloesen(subscription)[0]


def _verschmelzen(tid: str, abo: Optional[Mapping]) -> dict:
    res = copy.deepcopy(AMPEL_TEMPLATES[tid])
    if not abo:
        return res
    for mid, e in (abo.get("metrics") or {}).items():
        ziel = res["metrics"].setdefault(
            mid, {"enabled": False, "lower": {}, "upper": {}, "alarm_ab": "never"})
        for k in ("lower", "upper"):
            if k in e:  # null = Seite bewusst offen
                ziel[k] = copy.deepcopy(e[k]) or {}
        for k in ("enabled", "alarm_ab"):
            if e.get(k) is not None:
                ziel[k] = e[k]
    res["thunder"].update({k: v for k, v in (abo.get("thunder") or {}).items() if v is not None})
    return res


def resolve_ampel(subscription: Any) -> dict:
    """Vollstaendige Ampel eines Abos (Vorlage + Abo-Abweichungen)."""
    return _verschmelzen(*_aufloesen(subscription))


def _schwellen(e: Mapping) -> dict:
    out = {}
    for k in _UPPER:
        if (e.get("upper") or {}).get(k) is not None:
            out[k] = e["upper"][k]
    for k in _LOWER:
        if (e.get("lower") or {}).get(k) is not None:
            out[f"{k}_lt"] = e["lower"][k]
    return out


def ampel_for(subscription: Any) -> dict[str, dict]:
    """Je Metrik das Schwellen-Dict in der Form von ``severity_from_thresholds``
    (``yellow/orange/red`` + ``yellow_lt/orange_lt/red_lt``, offene weggelassen)."""
    return {mid: _schwellen(e) for mid, e in resolve_ampel(subscription)["metrics"].items()}


# Issue #2792 S1c-1: die Metriken, die HEUTE (vor dem Umschalten) eine Farbe
# tragen. Vorlagen-Zeilen ausserhalb dieser Menge (Taupunkt, Bewoelkung, ...)
# haben in S1 keinen Leser und liefern leere Schwellen (Spec §2, AC-19).
AMPEL_LESER = frozenset({
    "temperature", "wind_chill", "wind", "gust", "precipitation",
    "rain_probability", "visibility", "uv_index", "fresh_snow",
})


def hat_ampel(metric_id: Optional[str]) -> bool:
    """Traegt diese Metrik ueberhaupt eine Farbe? (die 9 Leser; CAPE seit
    S1c-4b nicht mehr, P1/AC-6)."""
    return metric_id in AMPEL_LESER


def _pruefe_aufgeloest(ampel: Any) -> None:
    """EINE Pruefung fuer alle Ampel-Leser (Schwellen UND Gewitterfarbe):
    ``None``, ``{}``, ``{"metrics": {}}`` oder ein unaufgeloestes Abo-Ampel-
    Fragment ohne ``metrics`` sind Programmierfehler -> ``ValueError``
    (AC-27, Fix-Loop 2 Nachtrag) statt still „allgemein"."""
    if not isinstance(ampel, Mapping) or not ampel.get("metrics"):
        raise ValueError("Profil-Ampel leer: aufgeloestes Ampel-Objekt erwartet")  # i18n-log


def schwellen_aus_ampel(ampel: Mapping, metric_id: Optional[str]) -> dict:
    """Schwellen-Dict (Form ``severity_from_thresholds``) einer Metrik aus dem
    AUFGELOESTEN Ampel-Objekt (``resolve_ampel(sub)``). ``ampel_for`` taugt
    dafuer nicht: das aufgeloeste Dict hat kein ``ampel``/``preset_name`` und
    fiele still auf „allgemein" zurueck.

    Eine leere Ampel (``{}`` bzw. ohne ``metrics``) ist ein Programmierfehler
    und scheitert laut, fuer jede Metrik (S1c-4b, AC-27)."""
    _pruefe_aufgeloest(ampel)
    if metric_id not in AMPEL_LESER:
        return {}
    return _schwellen(ampel["metrics"].get(metric_id) or {})


def _vorlage_der_ampel(ampel: Optional[Mapping]) -> str:
    tid = (ampel or {}).get("template")
    return _bekannte_vorlage(tid, "ampel.template") if tid else DEFAULT_TEMPLATE


def _ohne_offene(seite: Any) -> dict:
    return {k: v for k, v in (seite or {}).items() if v is not None}


def deviation_count(ampel: Optional[Mapping]) -> int:
    """Anzahl Metriken (plus Gewitter), die von der Vorlage abweichen.

    Issue #2794 S3a (AC-28): je Metrik zaehlen Grenzen, ``enabled`` (Metrik
    hinzugefuegt/entfernt) und ``alarm_ab``, hoechstens einmal je Metrik; die
    Gewitterfarbe zaehlt einmal. Ein Wert gleich dem Vorlagenwert zaehlt nicht.
    Metrik ohne Vorlagen-Zeile: Vorlage gilt als aus, ``alarm_ab`` = never
    (wie ``_verschmelzen``). Paritaet zum Frontend-Spiegel ueber
    ``tests/fixtures/ampel_deviation_cases.json``."""
    if not ampel:
        return 0
    vorlage = AMPEL_TEMPLATES[_vorlage_der_ampel(ampel)]
    ohne_zeile = {"enabled": False, "lower": {}, "upper": {}, "alarm_ab": "never"}
    n = 0
    for mid, e in (ampel.get("metrics") or {}).items():
        v = vorlage["metrics"].get(mid, ohne_zeile)
        grenzen = any(k in e and _ohne_offene(e[k]) != _ohne_offene(v.get(k)) for k in ("lower", "upper"))
        werte = any(e.get(k) is not None and e[k] != v.get(k) for k in ("enabled", "alarm_ab"))
        if grenzen or werte:
            n += 1
    gewitter = {**vorlage["thunder"], **_ohne_offene(ampel.get("thunder"))}
    return n + (gewitter != vorlage["thunder"])


def thunder_color(level: Any, ampel: Mapping) -> Optional[str]:
    """Gewitterstufe -> Ampelfarbe: keins gruen, leicht fest gelb (P2), mittel/
    hoch nach ``ampel.thunder`` (sonst Vorlage). ``None`` = keine Aussage.

    Fix-Loop 2 Nachtrag (AC-27): ``ampel`` ist die AUFGELOESTE Abo-Ampel;
    leer/fehlend scheitert laut, fuer jede Stufe (kein stilles „allgemein")."""
    _pruefe_aufgeloest(ampel)
    if level is None:
        return None
    from app.thunder_scale import thunder_ordinal
    from output.metric_format import thunder_ampel_band  # zentrale Abbildung (#1491)

    lvl = ThunderLevel(level)
    if thunder_ordinal(lvl) < thunder_ordinal(ThunderLevel.MED):
        return thunder_ampel_band(lvl)  # keins gruen, leicht fest gelb (P2)
    gewitter = _verschmelzen(_vorlage_der_ampel(ampel), ampel)["thunder"]
    return gewitter["mittel"] if lvl == ThunderLevel.MED else gewitter["hoch"]


# Issue #2792 S1c-4a: Vorbau fuer das Umschalten (noch ohne Leser).
_GELB_ODER_SCHLECHTER = frozenset({"yellow", "orange", "red"})


def ampel_stufe(ampel: Mapping, metric_id: Optional[str], wert: Optional[float]) -> Optional[str]:
    """Ampelstufe eines Werts aus dem AUFGELOESTEN Ampel-Objekt; derselbe
    Vergleichs-Kern wie ``severity_for`` (``severity_from_thresholds``)."""
    from output.metric_format import severity_from_thresholds
    return severity_from_thresholds(schwellen_aus_ampel(ampel, metric_id), wert)


def gelb_oder_schlechter(ampel: Mapping, metric_id: Optional[str], wert: Optional[float]) -> bool:
    """Beidseitiges Hervorhebungs-Praedikat: Stufe gelb, orange oder rot."""
    return ampel_stufe(ampel, metric_id, wert) in _GELB_ODER_SCHLECHTER


_STUFEN_RANG = {"yellow": 1, "orange": 2, "red": 3}


def _mildeste_grenze(schwellen: Mapping, seite: str) -> Optional[float]:
    """Mildeste gesetzte Grenze einer Seite (``oben``: yellow/orange/red,
    ``unten``: yellow_lt/orange_lt/red_lt) -- dort beginnt die Hervorhebung."""
    folge = ("yellow", "orange", "red") if seite == "oben" else ("yellow_lt", "orange_lt", "red_lt")
    return next((schwellen[k] for k in folge if schwellen.get(k) is not None), None)


def ampel_seite(ampel: Mapping, metric_id: Optional[str], wert: Optional[float]) -> Optional[str]:
    """Ausloesende Seite eines hervorgehobenen Werts: ``oben``/``unten``;
    ``None``, wenn der Wert gruen ist. Liegen beide Seiten an (nur bei
    sich kreuzenden Grenzen denkbar), gilt die weiter vom Gruen entfernte."""
    if not gelb_oder_schlechter(ampel, metric_id, wert):
        return None
    schwellen = schwellen_aus_ampel(ampel, metric_id)
    oben, unten = _mildeste_grenze(schwellen, "oben"), _mildeste_grenze(schwellen, "unten")
    ab_oben = wert - oben if oben is not None and wert >= oben else None
    ab_unten = unten - wert if unten is not None and wert < unten else None
    if ab_unten is None:
        return "oben"
    if ab_oben is None:
        return "unten"
    return "oben" if ab_oben >= ab_unten else "unten"


def ampel_schaerfe(ampel: Mapping, metric_id: Optional[str], wert: Optional[float]) -> tuple:
    """Wie schlimm ist ein Wert? ``(Stufenrang 0..3, Abstand vom gruenen
    Bereich)`` -- Abstand zur mildesten Grenze der ausloesenden Seite.
    Issue #2792 S1c-4b Fix-Loop 2 (F003): EINE Regel fuer die SMS-Klammer,
    den Ausblick und die Mail-Kachel (``schlimmster_index``)."""
    seite = ampel_seite(ampel, metric_id, wert)
    if seite is None:
        return (0, 0.0)
    grenze = _mildeste_grenze(schwellen_aus_ampel(ampel, metric_id), seite)
    abstand = wert - grenze if seite == "oben" else grenze - wert
    return (_STUFEN_RANG[ampel_stufe(ampel, metric_id, wert)], float(abstand))


def schlimmster_index(werte_zeitlich: Sequence[float], schaerfe: Callable[[float], tuple]) -> int:
    """Index des schlimmsten Werts einer zeitlich sortierten Reihe: hoechste
    Stufe, dann weiter vom gruenen Bereich, dann die frueheste Stunde."""
    return max(range(len(werte_zeitlich)), key=lambda i: (schaerfe(werte_zeitlich[i]), -i))


def gewitter_gelb_oder_schlechter(level: Any) -> bool:
    """Gewitter ab „leicht" (fest gelb, P2) ist gelb oder schlechter."""
    if level is None:
        return False
    from app.thunder_scale import thunder_ordinal
    return thunder_ordinal(ThunderLevel(level)) >= thunder_ordinal(ThunderLevel.LOW)


def vorlage_label_schluessel(template_id: str) -> str:
    """Katalogschluessel des Vorlagen-Labels (EINE Stelle). Der Katalog
    erlaubt keinen Bindestrich, daher ``-`` -> ``_``; die Vorlagen-ID bleibt
    Protokoll-Token. Unbekannte ID -> ``KeyError``."""
    if template_id not in AMPEL_TEMPLATES:
        raise KeyError(template_id)
    return "mail.vorlage." + template_id.replace("-", "_")
