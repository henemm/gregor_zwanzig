"""Dauerhafter Doppelungs-Waechter: keine Metrik, kein Kuerzel, kein Befehl
doppelt (Issue #2417, AC-25 bis AC-27).

SPEC: ``docs/specs/modules/feat_2417_kurzform_englisch.md`` Abschnitt K.
PO woertlich (27.09.2026): "Ich moechte einen permanenten Test, der
sicherstellt, dass es nicht zu einer Dopplung von Metriken, Kurzformen,
Kuerzeln etc. kommt."

Kern-Schicht: ohne Netz, deterministisch, KEIN Mock. Jede Soll-Menge wird
aus den Registern GERECHNET (``_METRICS``, ``SMS_SYMBOL_BY_METRIC``,
``SMS_MULTI_SYMBOLS_BY_METRIC``, ``SMS_SYMBOL_GRAMMAR``,
``HAZARD_SMS_SYMBOLS``, ``builder.POSITIONAL``, ``_COMMAND_SPECS``,
``_BARE_KEYWORD_MAP``, ``BOT_COMMANDS``), nichts abgetippt.

Aufbau: je Punkt 1–5 eine REINE Pruef-Funktion auf einfachen Daten
(``(verstoesse, geprueft)``), dazu je eine Gegenprobe mit einer verfaelschten
Kopie der echten Daten (``copy.deepcopy`` + eingepflanzte Doppelung), die rot
werden MUSS — ein Waechter, der nur auf dem heutigen Bestand gruen ist,
bewacht nichts (Muster ``test_telegram_kuerzel_folgt_register.py::
pruefe_kuerzel``).

Bewusst NICHT als Kennung geprueft (Spec Abschnitt K):
- ``friendly_label``: Deko-Symbol, von allen vier Bewoelkungsgroessen
  absichtlich geteilt — es benennt keine Groesse.
- ``dp_field``: Datenquelle; mehrere Auswertungen (Tagestief/-hoch/Nacht)
  lesen denselben Messwert, das ist keine Doppelung einer Kennung.

Die neuen Bedeutungsfelder heissen (Festlegung siehe
``tests/tdd/test_kuerzel_eindeutig.py``): ``kuerzel_bedeutung_en`` /
``kuerzel_bedeutung_de`` (dict Kuerzel -> Bedeutung je ``MetricDefinition``).

Ergaenzt, ersetzt nicht: ``test_metrik_listen_register_ratchet.py`` (Metrik-
Listen ausserhalb des Katalogs), ``test_sms_token_symbol_register_ratchet.py``
(SMS-Symbole abweichend vom Katalog).
"""
from __future__ import annotations

import copy
from collections import defaultdict

import pytest

FELD_EN = "kuerzel_bedeutung_en"
FELD_DE = "kuerzel_bedeutung_de"

#: Die EINE Ausnahmeliste erlaubter Doppelungen: (Feld, betroffene Kennungen)
#: -> Begruendungssatz. Eine Ausnahme, die nicht mehr vorkommt, macht
#: ``test_ausnahmeliste_ist_aktuell`` rot.
AUSNAHMEN: dict[tuple[str, frozenset[str]], str] = {
    ("alert_label", frozenset({"temperature", "temperature_cold"})): (
        "temperature_cold ist keine eigene Groesse, sondern der nicht waehlbare "
        "Kaelte-Alarm auf dieselbe Temperatur — beide Alarme heissen zu Recht 'Temp'."
    ),
    # Spec v1.1 AC-28: Punkt 2 (Kuerzel), Feldname "kuerzel:<Kuerzel>".
    ("kuerzel:T", frozenset({"temperature", "temperature_cold"})): (
        "Der Kaelte-Alarm temperature_cold schaut auf dieselbe Temperatur wie "
        "temperature — seine SMS traegt deshalb dasselbe Kuerzel T; CODES "
        "erklaert T einmal ueber temperature."
    ),
}

PUNKT1_FELDER = ("id", "label_de", "col_key", "col_label", "compact_label", "alert_label")


# ═══════════════════════════════════════════════════════════════════════════
# Normalisierung
# ═══════════════════════════════════════════════════════════════════════════

def _norm(symbol: str) -> str:
    return symbol.rstrip(":")


def _eingabe_norm(code: str) -> str:
    code = _norm(code)
    return code[:-3] if code.endswith("24+") else code


# ═══════════════════════════════════════════════════════════════════════════
# Daten aus den echten Registern
# ═══════════════════════════════════════════════════════════════════════════

def _metrik_eintraege() -> list[dict]:
    """Je ``_METRICS``-Eintrag (auch nicht waehlbare) die Punkt-1-Felder.
    ``alert_label`` = das, was der Alarm tatsaechlich sagt (``get_alert_label``:
    ``alert_label or label_de``)."""
    from app.metric_catalog import _METRICS, get_alert_label

    return [
        {
            "id": m.id, "label_de": m.label_de, "col_key": m.col_key,
            "col_label": m.col_label, "compact_label": m.compact_label,
            "alert_label": get_alert_label(m.id),
            FELD_EN: getattr(m, FELD_EN, None), FELD_DE: getattr(m, FELD_DE, None),
        }
        for m in _METRICS
    ]


def _katalog_kuerzel_quellen() -> list[tuple[str, str]]:
    """(metric_id, Kuerzel-Rohform) aus ``sms_code``, ``sms_multi_symbols``,
    ``SMS_SYMBOL_GRAMMAR``, ``SMS_MULTI_SYMBOLS_BY_METRIC`` und den Schluesseln
    der Bedeutungs-dicts."""
    from app.metric_catalog import (
        _METRICS, SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_GRAMMAR,
    )

    quellen: list[tuple[str, str]] = []
    for m in _METRICS:
        roh = [m.sms_code, *m.sms_multi_symbols, SMS_SYMBOL_GRAMMAR.get(m.id, ""),
               *SMS_MULTI_SYMBOLS_BY_METRIC.get(m.id, ())]
        for feld in (FELD_EN, FELD_DE):
            roh += list(dict(getattr(m, feld, None) or {}))
        quellen += [(m.id, r) for r in roh if r]
    return quellen


def _hazard_paare() -> list[tuple[str, str]]:
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS
    return list(HAZARD_SMS_SYMBOLS.items())


def _baustein_symbole(katalog_codes: set[str]) -> list[str]:
    """Symbole, die ``builder.py`` SELBST besitzt (nicht aus dem Katalog):
    Kategorien vigilance/fire/unavailable/debug sowie Wintersport-Symbole ohne
    Katalog-Kuerzel (``AV``). ``forecast``-Token sind Katalog-Kuerzel — ihren
    Abgleich mit dem Katalog bewacht ``test_sms_token_symbol_register_ratchet.py``."""
    from output.tokens.builder import POSITIONAL

    eigen: list[str] = []
    for sym, kategorie in POSITIONAL:
        if kategorie in {"vigilance", "fire", "unavailable", "debug"}:
            eigen.append(sym)
        elif kategorie == "wintersport" and _norm(sym) not in katalog_codes:
            eigen.append(sym)
    return eigen


def _befehls_paare() -> tuple[list[tuple[str, str]], list[str]]:
    """(Wort, Befehlskennung). Kennung = interner Schluessel aus
    ``_BARE_KEYWORD_MAP`` (``stop`` -> ``abbruch``). Zweiter Wert: Eintraege
    ohne Feldnamen ``wort``/``wort_en``."""
    from services.trip_command_processor import _BARE_KEYWORD_MAP, _COMMAND_SPECS

    paare = [(w.lower(), k) for w, k in _BARE_KEYWORD_MAP.items()]
    ohne_en: list[str] = []
    for eintrag in _COMMAND_SPECS:
        wort = getattr(eintrag, "wort", None)
        wort_en = getattr(eintrag, "wort_en", None)
        if wort is None and isinstance(eintrag, tuple):
            wort = eintrag[0]
        if not wort:
            continue
        kennung = _BARE_KEYWORD_MAP.get(wort.lower(), wort.lower())
        paare.append((wort.lower(), kennung))
        if wort_en:
            paare.append((wort_en.lower(), kennung))
        else:
            ohne_en.append(wort)
    return paare, ohne_en


def _menue_namen() -> list[str]:
    from output.channels.telegram import BOT_COMMANDS
    return [e["command"] for e in BOT_COMMANDS]


# ═══════════════════════════════════════════════════════════════════════════
# Reine Pruef-Funktionen: (verstoesse, geprueft)
# ═══════════════════════════════════════════════════════════════════════════

def pruefe_punkt1(eintraege: list[dict], ausnahmen: dict) -> tuple[list[str], int]:
    verstoesse: list[str] = []
    geprueft = 0
    gruppen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for e in eintraege:
        for feld in PUNKT1_FELDER:
            wert = e.get(feld)
            if wert:
                gruppen[(feld, wert)].add(e["id"])
                geprueft += 1
        for feld in (FELD_EN, FELD_DE):
            for bedeutung in dict(e.get(feld) or {}).values():
                if str(bedeutung).strip():
                    gruppen[(feld, str(bedeutung).strip())].add(e["id"])
                    geprueft += 1
    erlaubt = {(feld, ids) for (feld, ids) in ausnahmen}
    for (feld, wert), ids in sorted(gruppen.items()):
        if len(ids) > 1 and (feld, frozenset(ids)) not in erlaubt:
            verstoesse.append(f"{feld}={wert!r} doppelt: {sorted(ids)}")
    return verstoesse, geprueft


def _kuerzel_besitzer(quellen: list[tuple[str, str]]) -> dict[str, set[str]]:
    besitzer: dict[str, set[str]] = defaultdict(set)
    for metric_id, roh in quellen:
        besitzer[_eingabe_norm(roh)].add(metric_id)
    return besitzer


def veraltete_ausnahmen(
    eintraege: list[dict], quellen: list[tuple[str, str]], ausnahmen: dict,
) -> list[str]:
    gruppen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for e in eintraege:
        for feld in PUNKT1_FELDER:
            if e.get(feld):
                gruppen[(feld, e[feld])].add(e["id"])
    vorhanden = {(feld, frozenset(ids)) for (feld, _w), ids in gruppen.items() if len(ids) > 1}
    vorhanden |= {
        (f"kuerzel:{code}", frozenset(ids))
        for code, ids in _kuerzel_besitzer(quellen).items() if len(ids) > 1
    }
    return [f"{feld}: {sorted(ids)}" for (feld, ids) in ausnahmen if (feld, ids) not in vorhanden]


def pruefe_punkt2(quellen: list[tuple[str, str]], ausnahmen: dict) -> tuple[list[str], int]:
    erlaubt = set(ausnahmen)
    verstoesse = [
        f"Kuerzel {code!r} gehoert zu {sorted(ids)}"
        for code, ids in sorted(_kuerzel_besitzer(quellen).items())
        if len(ids) > 1 and (f"kuerzel:{code}", frozenset(ids)) not in erlaubt
    ]
    return verstoesse, len(quellen)


def pruefe_punkt3(
    hazard_paare: list[tuple[str, str]], baustein_symbole: list[str],
    katalog_codes: set[str],
) -> tuple[list[str], int]:
    verstoesse: list[str] = []
    hazard_codes: dict[str, list[str]] = defaultdict(list)
    for hazard, code in hazard_paare:
        hazard_codes[_norm(code)].append(hazard)
    for code, hz in sorted(hazard_codes.items()):
        if len(hz) > 1:
            verstoesse.append(f"Warn-Kuerzel {code!r} doppelt in HAZARD_SMS_SYMBOLS: {hz}")
        if code in katalog_codes:
            verstoesse.append(f"Warn-Kuerzel {code!r} ({hz}) == Katalog-Kuerzel")
    baustein_codes: dict[str, list[str]] = defaultdict(list)
    for sym in baustein_symbole:
        baustein_codes[_norm(sym)].append(sym)
    for code, syms in sorted(baustein_codes.items()):
        if len(syms) > 1:
            verstoesse.append(f"Baustein {code!r} doppelt im Builder: {syms}")
        if code in katalog_codes:
            verstoesse.append(f"Baustein {syms} kollidiert mit Katalog-Kuerzel {code!r}")
        if code in hazard_codes:
            verstoesse.append(f"Baustein {syms} kollidiert mit Warn-Kuerzel {code!r}")
    return verstoesse, len(hazard_paare) + len(baustein_symbole)


def pruefe_punkt4(paare: list[tuple[str, str]], codes: set[str]) -> tuple[list[str], int]:
    befehle: dict[str, set[str]] = defaultdict(set)
    for wort, kennung in paare:
        befehle[wort].add(kennung)
    verstoesse = [
        f"Wort {wort!r} loest mehrere Befehle aus: {sorted(k)}"
        for wort, k in sorted(befehle.items()) if len(k) > 1
    ]
    verstoesse += [f"Befehlswort {w!r} ist zugleich ein Kuerzel" for w in sorted(set(befehle) & codes)]
    return verstoesse, len(paare)


def pruefe_punkt5(namen: list[str]) -> tuple[list[str], int]:
    zaehler: dict[str, int] = defaultdict(int)
    for n in namen:
        zaehler[n] += 1
    return [f"Menueeintrag /{n} {k}x" for n, k in sorted(zaehler.items()) if k > 1], len(namen)


def _katalog_codes() -> set[str]:
    codes = set()
    for _m, roh in _katalog_kuerzel_quellen():
        codes |= {_norm(roh), _eingabe_norm(roh)}
    return codes


# ═══════════════════════════════════════════════════════════════════════════
# AC-25 — die fuenf Punkte am echten Bestand
# ═══════════════════════════════════════════════════════════════════════════

def test_punkt1_metrik_kennungen_eindeutig():
    """AC-25.1 (+ AC-26): keine zwei ``_METRICS``-Eintraege teilen ``id``,
    ``label_de``, ``col_key``, ``col_label``, ``compact_label``,
    ``alert_label`` oder eine Bedeutung (en/de). Heute rot: ``alert_label``
    'Schnee' fuer ``snow_depth``/``fresh_snow`` und fehlende Bedeutungsfelder."""
    eintraege = _metrik_eintraege()
    ohne = sorted(e["id"] for e in eintraege
                  if not isinstance(e[FELD_EN], dict) or not isinstance(e[FELD_DE], dict))
    verstoesse, geprueft = pruefe_punkt1(eintraege, AUSNAHMEN)
    assert geprueft > 100, f"Waechter prueft nur {geprueft} Kennungen — blind?"
    assert not verstoesse, "AC-25.1 FAIL — doppelte Kennungen:\n  " + "\n  ".join(verstoesse)
    assert not ohne, (
        f"AC-25.1 FAIL: {len(ohne)} Metriken ohne Bedeutungsfelder "
        f"{FELD_EN}/{FELD_DE} (dann ist ihre Eindeutigkeit ungeprueft): {ohne}"
    )


def test_ausnahmeliste_ist_aktuell():
    """AC-25: jede Ausnahme hat einen Begruendungssatz und kommt noch vor —
    sonst veraltet die Liste still."""
    for schluessel, grund in AUSNAHMEN.items():
        assert len(grund.strip()) >= 30, f"Ausnahme {schluessel} ohne Begruendung"
    assert len(AUSNAHMEN) == 2, f"Spec v1.1: genau zwei Ausnahmen, gefunden {len(AUSNAHMEN)}"
    veraltet = veraltete_ausnahmen(_metrik_eintraege(), _katalog_kuerzel_quellen(), AUSNAHMEN)
    assert not veraltet, f"AC-25 FAIL: Ausnahmen kommen nicht mehr vor: {veraltet}"


def test_punkt2_ein_kuerzel_eine_metrik():
    """AC-25.2 (+ AC-28): kein Kuerzel gehoert zu mehr als einer Metrik
    (ueber ``sms_code``, ``sms_multi_symbols``, Grammatikformen,
    normalisiert); einzige Ausnahme ``T`` fuer temperature/temperature_cold.
    Heute rot: ``D`` (temperature/temperature_day_high) und ``N``
    (temperature_cold/temperature_night)."""
    verstoesse, geprueft = pruefe_punkt2(_katalog_kuerzel_quellen(), AUSNAHMEN)
    assert geprueft > 30, f"Nur {geprueft} Kuerzel-Quellen — Waechter blind?"
    assert not verstoesse, "AC-25.2 FAIL:\n  " + "\n  ".join(verstoesse)


def test_punkt3_warn_und_baustein_kuerzel_ohne_ueberschneidung():
    """AC-25.3 (+ AC-27): Warn-Kuerzel nicht doppelt, keine Ueberschneidung
    zwischen Warn-Kuerzeln, Builder-Bausteinen und Katalog-Kuerzeln. Heute
    rot: TH/FL/W/CL (Warnung vs. Katalog), HR:/TH: (Meteo-France vs. Warnung
    bzw. Katalog)."""
    katalog = _katalog_codes()
    verstoesse, geprueft = pruefe_punkt3(_hazard_paare(), _baustein_symbole(katalog), katalog)
    assert geprueft >= 10, f"Nur {geprueft} Kuerzel geprueft — Waechter blind?"
    assert not verstoesse, "AC-25.3 FAIL:\n  " + "\n  ".join(verstoesse)


def test_punkt4_befehlswoerter_eindeutig_und_kein_kuerzel():
    """AC-25.4 (AC-16): ein Wort loest genau einen Befehl aus und gleicht
    keinem Kuerzel; gleich geschriebene de/en-Woerter (PAUSE, STATUS, SKIP,
    STOP) sind ein Wort fuer einen Befehl, keine Doppelung."""
    paare, ohne_en = _befehls_paare()
    assert not ohne_en, (
        f"AC-25.4 FAIL: _COMMAND_SPECS-Eintraege ohne englisches Wort "
        f"(Feld 'wort_en'): {ohne_en}"
    )
    codes = {c.lower() for c in _katalog_codes()} | {"t"}
    verstoesse, geprueft = pruefe_punkt4(paare, codes)
    assert geprueft >= 24, f"Nur {geprueft} Befehlswoerter — Waechter blind?"
    assert not verstoesse, "AC-25.4 FAIL:\n  " + "\n  ".join(verstoesse)


def test_punkt5_telegram_menue_ohne_doppelten_eintrag():
    """AC-25.5 — REGRESSIONSWAECHTER, heute absichtlich GRUEN: kein Slash-
    Name steht zweimal in ``BOT_COMMANDS``. Wird rot, sobald /50 gleich
    geschriebene de/en-Befehle (``/pause``, ``/status``, ``/skip``, ``/stop``)
    doppelt eintraegt."""
    verstoesse, geprueft = pruefe_punkt5(_menue_namen())
    assert geprueft > 0, "BOT_COMMANDS leer — Waechter blind."
    assert not verstoesse, "AC-25.5 FAIL:\n  " + "\n  ".join(verstoesse)


# ═══════════════════════════════════════════════════════════════════════════
# AC-25 — Gegenproben: verfaelschte Kopie der echten Daten MUSS rot werden
# (Werkzeug-Selbsttests, heute gruen und bleiben gruen)
# ═══════════════════════════════════════════════════════════════════════════

def test_gegenprobe_punkt1_doppeltes_label():
    kopie = copy.deepcopy(_metrik_eintraege())
    kopie[1]["col_label"] = kopie[0]["col_label"]
    verstoesse, _ = pruefe_punkt1(kopie, AUSNAHMEN)
    assert any(f"col_label={kopie[0]['col_label']!r}" in v for v in verstoesse), verstoesse
    kopie = copy.deepcopy(_metrik_eintraege())
    kopie[0][FELD_EN] = {"X1": "zzq gleich"}
    kopie[1][FELD_EN] = {"X2": "zzq gleich"}
    verstoesse, _ = pruefe_punkt1(kopie, AUSNAHMEN)
    assert any("zzq gleich" in v for v in verstoesse), verstoesse


def test_gegenprobe_ausnahme_veraltet():
    kopie = copy.deepcopy(_metrik_eintraege())
    for e in kopie:
        if e["id"] == "temperature_cold":
            e["alert_label"] = "Kaelte"
    veraltet = veraltete_ausnahmen(kopie, _katalog_kuerzel_quellen(), AUSNAHMEN)
    assert any(v.startswith("alert_label") for v in veraltet), veraltet
    # Kuerzel-Ausnahme T: kommt sie vor, ist sie NICHT veraltet; fehlt sie, schon.
    mit_t = [q for q in _katalog_kuerzel_quellen() if q[0] not in ("temperature", "temperature_cold")]
    mit_t += [("temperature", "T"), ("temperature_cold", "T")]
    assert not any(v.startswith("kuerzel:T") for v in veraltete_ausnahmen(kopie, mit_t, AUSNAHMEN))
    ohne_t = [q for q in mit_t if q[1] != "T"]
    assert any(v.startswith("kuerzel:T") for v in veraltete_ausnahmen(kopie, ohne_t, AUSNAHMEN))


def test_gegenprobe_punkt2_kuerzel_bei_zwei_metriken():
    kopie = copy.deepcopy(_katalog_kuerzel_quellen()) + [("wind", "HP")]
    verstoesse, _ = pruefe_punkt2(kopie, AUSNAHMEN)
    assert any("'HP'" in v for v in verstoesse), verstoesse
    kopie = copy.deepcopy(_katalog_kuerzel_quellen()) + [("wind", "NS24+")]
    verstoesse, _ = pruefe_punkt2(kopie, AUSNAHMEN)
    assert any("'NS'" in v for v in verstoesse), "Normalisierung NS24+ -> NS greift nicht"
    # Die T-Ausnahme gilt NUR fuer genau dieses Paar: ein dritter T-Traeger ist rot.
    basis = [q for q in _katalog_kuerzel_quellen() if q[1] != "T"]
    paar = basis + [("temperature", "T"), ("temperature_cold", "T")]
    verstoesse, _ = pruefe_punkt2(paar, AUSNAHMEN)
    assert not any("'T'" in v for v in verstoesse), verstoesse
    verstoesse, _ = pruefe_punkt2(paar + [("wind", "T")], AUSNAHMEN)
    assert any("'T'" in v for v in verstoesse), verstoesse


def test_gegenprobe_punkt3_ueberschneidung():
    katalog = _katalog_codes()
    hazards = copy.deepcopy(_hazard_paare()) + [("zzq_gefahr", "HP")]
    verstoesse, _ = pruefe_punkt3(hazards, _baustein_symbole(katalog), katalog)
    assert any("'HP'" in v and "Katalog" in v for v in verstoesse), verstoesse
    hazards = copy.deepcopy(_hazard_paare())
    hazards += [("zzq_a", "QQ"), ("zzq_b", "QQ")]
    verstoesse, _ = pruefe_punkt3(hazards, [], katalog)
    assert any("'QQ' doppelt" in v for v in verstoesse), verstoesse
    verstoesse, _ = pruefe_punkt3([], ["UV:"], katalog)
    assert any("'UV'" in v for v in verstoesse), verstoesse


def test_gegenprobe_punkt4_wort_zweimal():
    paare, _ = _befehls_paare()
    kopie = copy.deepcopy(paare) + [("status", "zzq_anderer_befehl")]
    verstoesse, _ = pruefe_punkt4(kopie, set())
    assert any("'status'" in v for v in verstoesse), verstoesse
    verstoesse, _ = pruefe_punkt4(copy.deepcopy(paare) + [("hp", "zzq")], {"hp"})
    assert any("'hp'" in v and "Kuerzel" in v for v in verstoesse), verstoesse
    verstoesse, _ = pruefe_punkt4([("pause", "pause"), ("pause", "pause")], set())
    assert not verstoesse, "Gleich geschriebenes de/en-Wort faelschlich als Doppelung gemeldet"


def test_gegenprobe_punkt5_menue_doppelt():
    kopie = copy.deepcopy(_menue_namen())
    kopie.append(kopie[0])
    verstoesse, _ = pruefe_punkt5(kopie)
    assert verstoesse, "Doppelter Menueeintrag nicht erkannt."


# ═══════════════════════════════════════════════════════════════════════════
# AC-26 — Schneehoehe und Neuschnee im Alarm unterscheidbar
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("metric_id,name", [("snow_depth", "Schneehöhe"), ("fresh_snow", "Neuschnee")])
def test_schnee_alarm_nennt_die_groesse(metric_id, name):
    """AC-26: Given ein Alarm zu ``snow_depth`` bzw. ``fresh_snow`` / When er
    gerendert wird (Telegram und E-Mail) / Then heisst die Groesse
    "Schneehöhe" bzw. "Neuschnee" — nicht beide "Schnee"."""
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from output.renderers.alert.render import render_email, render_telegram

    ereignis = AlertEvent(
        metric_id=metric_id, value_from=5.0, value_to=40.0, threshold=20.0,
        cmp="über", occurred_at="14:00", km_from=8.0, km_to=8.0, segment_id="Ziel",
    )
    msg = AlertMessage(trip_short="KHW 403", stand_at="10:00", events=(ereignis,))
    telegram = render_telegram(msg)
    betreff_oder_html = render_email(msg)[0]
    assert name in telegram, f"AC-26 FAIL (Telegram, {metric_id}): {name!r} fehlt: {telegram!r}"
    assert name in betreff_oder_html, f"AC-26 FAIL (E-Mail, {metric_id}): {name!r} fehlt"


# ═══════════════════════════════════════════════════════════════════════════
# AC-27 — neue Warn- und Meteo-France-Kuerzel in der versendeten Nachricht
# ═══════════════════════════════════════════════════════════════════════════

def _tokens(text: str) -> set[str]:
    import re
    return {t for t in re.split(r"[\s!]+", text) if t}


def test_warn_sms_traegt_die_neuen_kuerzel():
    """AC-27: Given amtliche Warnungen Gewitter/Hochwasser/Starkregen/
    Sturmboeen/Sperrung / When die Warn-SMS gerendert wird / Then stehen dort
    ``TS``, ``FO``, ``RA``, ``WG``, ``AB`` — nicht mehr ``TH``, ``FL``,
    ``HR``, ``W``, ``CL``."""
    from output.renderers.alert.official_alerts import (
        OfficialAlertNotice, render_official_alert_sms,
    )
    from services.official_alerts.models import OfficialAlert

    notices = [
        OfficialAlertNotice(
            alert=OfficialAlert(
                source="geosphere_warn", hazard=hazard, level=3, label=hazard,
                region_label="Kärnten", valid_from=None, valid_to=None,
            ),
            scope_label="Segment 4", sms_scope="Seg 4", affected_chips=["Segment 4"],
            free_chips=[], scope_ids=("4",),
        )
        for hazard in ("thunderstorm", "flood", "rain", "wind_gust", "access_ban")
    ]
    sms = render_official_alert_sms(notices, limit=300)
    kuerzel = {t.split(":")[0] for t in _tokens(sms)}
    assert {"TS", "FO", "RA", "WG", "AB"} <= kuerzel, (
        f"AC-27 FAIL: neue Warn-Kuerzel fehlen in der Warn-SMS: {sms!r}"
    )
    alt = kuerzel & {"TH", "FL", "HR", "W", "CL"}
    assert not alt, f"AC-27 FAIL: alte Warn-Kuerzel {sorted(alt)} in der Warn-SMS: {sms!r}"


def test_meteo_france_block_traegt_vr_und_vt():
    """AC-27: Given ein Meteo-France-Tag mit Regen- und Gewitterrisiko und
    OHNE Gewitter-Vorhersage-Token / When die Kurzform-Zeile gebaut und
    gerendert wird / Then heissen die Bausteine ``VR:``/``VT:`` statt
    ``HR:``/``TH:``."""
    from output.tokens.builder import build_token_line
    from output.tokens.dto import DailyForecast, NormalizedForecast

    forecast = NormalizedForecast(
        days=(DailyForecast(temp_min_c=5.0, temp_max_c=15.0),),
        provider="meteofrance", country="",
        vigilance_hr_level="M", vigilance_hr_hour=14,
        vigilance_th_level="H", vigilance_th_hour=17,
    )
    line = build_token_line(forecast, [], report_type="evening", stage_name="Heute")
    vigilance = [t.symbol for t in line.tokens if t.category == "vigilance"]
    text = line.render(400)
    assert vigilance and set(vigilance) == {"VR:", "VT:"}, (
        f"AC-27 FAIL: Meteo-France-Bausteine heissen {vigilance}, erwartet "
        f"VR:/VT:. Gerendert: {text!r}"
    )
    assert "VR:M@14" in text and "VT:H@17" in text, f"AC-27 FAIL: {text!r}"
    # 'TH:' selbst darf als Gewitter-VORHERSAGE-Token (Kategorie forecast)
    # weiter erscheinen ('TH:-'); geprueft wird nur der Meteo-France-Block.
    assert "HR:" not in text and "TH:H@17" not in text, f"AC-27 FAIL: alte Bausteine in {text!r}"
