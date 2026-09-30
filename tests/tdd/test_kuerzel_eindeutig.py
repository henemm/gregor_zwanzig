"""Ein Kuerzel = eine Bedeutung, ueberall — und was man liest, kann man senden.

Issue #2417, Spec ``docs/specs/modules/feat_2417_kurzform_englisch.md``
(AC-9 bis AC-17, AC-22 bis AC-24). Kontext:
``docs/context/feature-2417-kurzform-englisch.md``.

Test-Politik: KEIN ``Mock()``/``patch()``/``MagicMock``. Jede Verhaltens-
zusicherung liest die TATSAECHLICH versendete Antwort (Recorder am Netzrand aus
``tests/tdd/_befehl_e2e_fixtures.py``) bzw. den gerenderten Text des echten
Renderers. Einzige Ausnahme: AC-24 (``# doc-compliance-test``).

===========================================================================
Festgelegte Namen fuer /50-implement (die Spec laesst sie offen)
===========================================================================

Die Spec schreibt nur vor, WO die Bedeutungen stehen (Tabelle "Wo die
Bedeutungen stehen"), nicht wie die Felder heissen. Dieser Test legt fest:

1. Wettermetriken (``src/app/metric_catalog.py``, je ``MetricDefinition``):
   ``kuerzel_bedeutung_en: dict[str, str]`` und
   ``kuerzel_bedeutung_de: dict[str, str]`` — Schluessel = das Kuerzel, wie
   es in CODES/KUERZEL steht (Register-Symbol ohne Grammatik-Doppelpunkt:
   ``TH``, ``TH+``, ``WD``, ``PT``, ``NS24+``; ``temperature`` -> ``T``),
   Wert = kurze Bedeutung. Ein dict je Sprache, weil ``thunder`` ZWEI
   Kuerzel (``TH``/``TH+``) traegt. Beispiel: ``precipitation`` ->
   ``kuerzel_bedeutung_en={"R": "rain mm"}``,
   ``kuerzel_bedeutung_de={"R": "Regen mm"}``.
   Das dict-Objekt MUSS vom Produkt zur Laufzeit gelesen werden (AC-23:
   der Test aendert per ``monkeypatch.setitem`` einen Eintrag des ECHTEN
   Katalog-dicts und erwartet den geaenderten Text in der CODES-Antwort).
2. Warn-Kuerzel (``src/output/tokens/hazard_symbols.py``, direkt bei
   ``HAZARD_SMS_SYMBOLS``): ``HAZARD_BEDEUTUNG_EN: dict[str, str]`` und
   ``HAZARD_BEDEUTUNG_DE: dict[str, str]`` — Schluessel = hazard-Kennung
   (dieselben Schluessel wie ``HAZARD_SMS_SYMBOLS``).
3. Bausteine ohne Katalog-Eintrag (``src/output/tokens/builder.py``, direkt
   bei den Konstanten): ``BAUSTEIN_BEDEUTUNG_EN: dict[str, str]`` und
   ``BAUSTEIN_BEDEUTUNG_DE: dict[str, str]`` — Schluessel = das Symbol, wie
   es der Builder erzeugt (``"AV"``, ``"Z:"``, ``"M:"``, ``VIGI_HR``,
   ``VIGI_TH``, ``UNAVAILABLE_SYMBOL``, ``"MAX"`` …). Formatzeichen duerfen
   im selben dict oder daneben stehen; dieser Test verlangt nur die
   Bausteine.

Alle neuen Symbole werden per ``getattr(..., None)`` abgefragt — jeder Test
scheitert mit eigener Assertion, nie mit einem Import-Fehler auf Modulebene.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tests.tdd._befehl_e2e_fixtures import (
    FEHLERTEXTE,
    _ortstag_jetzt,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    lege_po_lage_nutzer_an,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    sms_segments,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

REPO = Path(__file__).resolve().parents[2]
TZ = ZoneInfo("Europe/Vienna")

FELD_EN = "kuerzel_bedeutung_en"
FELD_DE = "kuerzel_bedeutung_de"
HAZARD_FELD_EN = "HAZARD_BEDEUTUNG_EN"
HAZARD_FELD_DE = "HAZARD_BEDEUTUNG_DE"
BAUSTEIN_FELD_EN = "BAUSTEIN_BEDEUTUNG_EN"
BAUSTEIN_FELD_DE = "BAUSTEIN_BEDEUTUNG_DE"

#: Deutscher KUERZEL-Wortlaut, zeichengenau aus der Spec (AC-10). #2422 S6 (B1,
#: PO-Entscheid V1): "TF" (gefuehlte Temperatur, Stundenwert) steht WIEDER auch im
#: TRIP-Kontext -- es loest Bug #2454 AC-6 ("TF entfaellt im Trip") ab, weil der
#: Trip ``TF<Tiefstwert>@<Stunde>`` jetzt versendet. Der Wortlaut ist der des
#: Ortsvergleich-Kontexts (AC-7, unveraendert).
KUERZEL_WORTLAUT_DE = "\n".join([
    "Kürzel",
    "Wetter: T Temperatur, D Tageshöchstwert, N Nacht, L Tagestiefstwert, "
    "TF gefühlt, FD/FL/FN = D/L/N gefühlt, R Regen mm, PR "
    "Regenwahrscheinlichkeit %, TH Gewitter, TH+ Gewitter Folge-Etappe, W Wind "
    "km/h, G Böen, WD Windrichtung, HU Luftfeuchte, DP Taupunkt, CP "
    "Gewitterenergie, PT Niederschlagsart, SL Schneefallgrenze m, NS24+ "
    "Neuschnee 24h, CT/CL/CM/CH Bewölkung gesamt/tief/mittel/hoch, VS Sicht, "
    "SU Sonnenstunden, UV UV-Index, HP Luftdruck, FZ Nullgradgrenze m.",
    "Weitere: SD Schneehöhe, AV Lawinenstufe, C Vorhersage-Verlässlichkeit, "
    "Z:/MAX/M: Brandzonen/Höchststufe/Massive.",
    "Format: E4 Etappe 4, 23@5 über der Schwelle ab 5 Uhr, (24@7) Spitze, "
    "D13/27 Tiefst/Höchst, +HL Hagel, - nichts, ? keine Daten.",
    "Warnungen nach !: TS Gewitter, FO Hochwasser, RA Starkregen, WG Wind, SN "
    "Schnee, IC Glätte, HT Hitze, CD Kälte, FR Waldbrand, AB Sperrung. L/M/H "
    "niedrig/mittel/hoch. VR:VT: Météo-France-Risiko Regen/Gewitter. X? keine "
    "Warndaten.",
])

#: Antwort-Merkmale "nicht erkannt" (geteilte Fehlertexte + die beiden
#: Fehlerwege, die dort nicht stehen: strukturierter Befehlsfehler, englisch).
NICHT_ERKANNT = (*FEHLERTEXTE, "Befehlsformat", "kein bekannter Befehl", "unknown")

#: Premium-SMS-Verknuepfungscode-Gestalt (inbound_sms_reader.py:90, AC-17).
VERKNUEPFUNGSCODE_RE = re.compile(r"^XX[A-HJKMNP-Z]{3}[2-9]{3}$")


# ═══════════════════════════════════════════════════════════════════════════
# Register-Ableitungen (Soll-Mengen werden gerechnet, nie abgetippt)
# ═══════════════════════════════════════════════════════════════════════════

def _norm(symbol: str) -> str:
    """Grammatik-Doppelpunkt gehoert nicht zum Kuerzel (``TH:`` -> ``TH``,
    ``TH+:`` -> ``TH+``, ``VR:`` -> ``VR``); ``X?``/``NS24+`` bleiben."""
    return symbol.rstrip(":")


def _eingabe_norm(code: str) -> str:
    """Eingabe-Normalisierung laut AC-15: Suffix ``24+`` entfaellt."""
    code = _norm(code)
    return code[:-3] if code.endswith("24+") else code


def _metriken():
    from app.metric_catalog import _METRICS
    return list(_METRICS)


def _ausgabe_kuerzel_je_metrik() -> dict[str, set[str]]:
    """metric_id -> normalisierte Ausgabe-Kuerzel. Register
    (``SMS_SYMBOL_BY_METRIC``/``SMS_MULTI_SYMBOLS_BY_METRIC``) haben Vorrang;
    eine Groesse ohne Register-Eintrag, aber mit ``sms_code`` (Alarm-/
    Vergleichs-SMS, z. B. ``temperature``, ``wind_chill``), fuehrt ihren
    ``sms_code``."""
    from app.metric_catalog import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    out: dict[str, set[str]] = {}
    for m in _metriken():
        codes: set[str] = set()
        if m.id in SMS_SYMBOL_BY_METRIC:
            codes.add(_norm(SMS_SYMBOL_BY_METRIC[m.id]))
        for sym in SMS_MULTI_SYMBOLS_BY_METRIC.get(m.id, ()):
            codes.add(_norm(sym))
        if not codes and m.sms_code:
            codes.add(_norm(m.sms_code))
        if codes:
            out[m.id] = codes
    return out


def _register_kuerzel() -> set[str]:
    from app.metric_catalog import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    codes = {_norm(s) for s in SMS_SYMBOL_BY_METRIC.values()}
    for syms in SMS_MULTI_SYMBOLS_BY_METRIC.values():
        codes |= {_norm(s) for s in syms}
    return codes


def _builder_symbole() -> list[tuple[str, str]]:
    """(Symbol, Kategorie) jedes Tokens, das ``builder.py`` erzeugen kann —
    ausser ``DBG`` (erscheint nur im Debug-Modus, Spec AC-9)."""
    from output.tokens import builder
    return [(s, k) for s, k in builder.POSITIONAL if s != "DBG"]


def _hazard_kuerzel() -> set[str]:
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS
    return set(HAZARD_SMS_SYMBOLS.values())


def _soll_codes_ac9() -> set[str]:
    return (
        _register_kuerzel()
        | _hazard_kuerzel()
        | {_norm(s) for s, _k in _builder_symbole()}
    )


# ═══════════════════════════════════════════════════════════════════════════
# Kanal-Helfer: die TATSAECHLICH versendete Antwort
# ═══════════════════════════════════════════════════════════════════════════

def _premium_antwort(settings, recorder, nutzer, text: str) -> str:
    vorher = len(recorder.premium_sms_out)
    sende_premium_sms(settings, recorder, nutzer, text)
    neu = [
        e["text"] for e in recorder.premium_sms_out[vorher:]
        if e["to"] == nutzer.premium_sms_reply_to
    ]
    assert neu, (
        f"Auf Premium-SMS {text!r} wurde gar keine Antwort versendet "
        f"(Rohaufzeichnung: {recorder.premium_sms_out!r})."
    )
    return "".join(neu)


def _telegram_antwort(settings, recorder, nutzer, text: str) -> str:
    vorher = len(recorder.telegram_inhalte(nutzer.telegram_chat_id))
    sende_telegram_text(settings, nutzer, text)
    neu = recorder.telegram_inhalte(nutzer.telegram_chat_id)[vorher:]
    assert neu, f"Auf Telegram {text!r} wurde gar keine Antwort versendet."
    return "\n---\n".join(e["payload"].get("text", "") for e in neu)


def _email_text(gesendet: dict) -> str:
    """Betreff + jeder Text-Anteil der versendeten Mail (lokale Kopie, kein
    Import aus einem anderen Testmodul)."""
    import email as email_lib
    from email.header import decode_header, make_header

    msg = email_lib.message_from_string(gesendet["raw"])
    teile = [str(make_header(decode_header(msg.get("Subject", ""))))]
    for teil in (msg.walk() if msg.is_multipart() else [msg]):
        if teil.get_content_maintype() != "text":
            continue
        payload = teil.get_payload(decode=True)
        if payload:
            teile.append(payload.decode(teil.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(teile)


def _email_antwort(settings, recorder, nutzer, text: str) -> str:
    vorher = len(recorder.emails)
    sende_email(settings, nutzer, text)
    neu = [e for e in recorder.emails[vorher:] if nutzer.mail_to in e["to"]]
    assert neu, f"Auf die Mail {text!r} wurde keine Antwortmail versendet."
    return "\n".join(_email_text(e) for e in neu)


def _codes_tokens(text: str) -> set[str]:
    teile = re.split(r"[\s,/=:.;()]+", text)
    return {t for t in teile if t}


def _code_match(text: str, code: str):
    return re.search(rf"(?<![A-Za-z0-9+]){re.escape(code)}(?![A-Za-z0-9+])", text)


def _hat_bedeutung_im_text(text: str, code: str, alle_codes: set[str]) -> bool:
    """Hinter dem ersten Vorkommen von ``code`` steht bis zum naechsten
    ``,``/``. ``/Zeilenende mindestens ein Wort, das selbst kein Kuerzel ist."""
    m = _code_match(text, code)
    if m is None:
        return False
    rest = text[m.end():]
    ende = min(
        (i for i in (rest.find(", "), rest.find(". "), rest.find("\n")) if i != -1),
        default=len(rest),
    )
    worte = re.findall(r"[A-Za-z][a-z]+|[A-Za-z]{2,}", rest[:ende])
    return any(w not in alle_codes for w in worte)


# ═══════════════════════════════════════════════════════════════════════════
# AC-9 — CODES vollstaendig gegen die Ausgabe-Register
# ═══════════════════════════════════════════════════════════════════════════

def test_codes_tokenizer_selbsttest_am_spec_wortlaut():
    """WERKZEUG-SELBSTTEST, KEIN AC-9-NACHWEIS: der Tokenizer/Bedeutungs-
    Finder dieses Moduls funktioniert am englischen Spec-Wortlaut (AC-9).
    Macht zugleich sichtbar, welche Register-Kuerzel der FREIGEGEBENE
    Wortlaut NICHT erklaert (Befund fuer /50: ``MAX`` aus
    ``builder.POSITIONAL``)."""
    spec_codes = (
        "Weather: T temp, D day max, N night, L day min, TF feels like, "
        "FD/FL/FN = D/L/N feels like, R rain mm, PR rain %, TH thunder, TH+ next "
        "stage, W wind km/h, G gusts, WD wind dir, HU humidity, DP dew point, CP "
        "storm energy, PT precip type, SL snow line m, NS24+ new snow 24h, "
        "CT/CL/CM/CH clouds total/low/mid/high, VS visibility, SU sun h, UV "
        "index, HP pressure, FZ 0C level m.\n"
        "More: SD snow depth, AV avalanche level, C confidence, Z:/MAX/M: "
        "fire zones/top level/massifs.\n"
        "Format: E4 stage 4, 23@5 over limit from 5h, (24@7) peak, D13/27 "
        "min/max, +HL hail, - none, ? no data.\n"
        "Alerts after !: TS storm, FO flood, RA heavy rain, WG wind, SN snow, IC "
        "ice, HT heat, CD cold, FR fire, AB closure. L/M/H low/mid/high. VR:VT: "
        "Meteo-France rain/storm risk. X? no alert data."
    )
    tokens = _codes_tokens(spec_codes)
    codes = _soll_codes_ac9() | {"T", "TF", "C"}
    for code in ("T", "D", "N", "TH+", "NS24+", "VR", "VT", "X?", "Z", "MAX", "M", "AB"):
        assert code in tokens, f"Tokenizer verliert {code!r}: {sorted(tokens)}"
        assert _hat_bedeutung_im_text(spec_codes, code, codes), code
    # Spec v1.1: MAX ist im Wortlaut; die aus dem Code gerechnete AC-9-Soll-
    # Menge ist bis auf die GREEN-Umbenennungen (Warn-/Meteo-France-Kuerzel)
    # vollstaendig im Wortlaut enthalten.
    # Heute noch im Register, mit AC-27 umbenannt (TH/W bleiben Wetter-Kuerzel):
    umbenannt = {"FL", "HR", "CL"}
    rest = sorted(c for c in _soll_codes_ac9() if c not in tokens and c not in umbenannt)
    assert not rest, f"Spec-Wortlaut erklaert gerechnete Soll-Kuerzel nicht: {rest}"
    kaputt = spec_codes.replace("R rain mm", "R ")
    assert not _hat_bedeutung_im_text(kaputt, "R", codes), (
        "Bedeutungs-Finder erkennt ein Kuerzel ohne Bedeutung nicht."
    )


def test_codes_vollstaendig_gegen_ausgabe_register(monkeypatch, user_ids):
    """AC-9: Given die CODES-Antwort per Premium-SMS (immer englisch) / When
    sie aufgebaut und versendet wird / Then enthaelt sie JEDES Kuerzel aus
    ``SMS_SYMBOL_BY_METRIC``/``SMS_MULTI_SYMBOLS_BY_METRIC``/
    ``HAZARD_SMS_SYMBOLS`` und jedes Token-Symbol aus ``builder.py`` (ausser
    ``DBG``), jedes mit einer Bedeutung, die Formatzeichen, und braucht
    hoechstens 5 Segmente. Soll-Menge zur Laufzeit gerechnet."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    text = _premium_antwort(basis_settings(), recorder, nutzer, "CODES")

    soll = _soll_codes_ac9()
    assert len(soll) > 30, f"Soll-Menge verdaechtig klein ({len(soll)}): {sorted(soll)}"
    tokens = _codes_tokens(text)
    fehlend = sorted(c for c in soll if c not in tokens)
    assert not fehlend, (
        f"AC-9 FAIL: {len(fehlend)} Kuerzel, die in einer Kurzform-SMS "
        f"erscheinen koennen, fehlen in der CODES-Antwort: {fehlend}\n"
        f"Antwort: {text!r}"
    )
    ohne = sorted(c for c in soll if not _hat_bedeutung_im_text(text, c, soll))
    assert not ohne, (
        f"AC-9 FAIL: Kuerzel ohne Bedeutungstext in der CODES-Antwort: {ohne}\n"
        f"Antwort: {text!r}"
    )
    for format_zeichen in ("E4", "@", "(", "/", "+HL", " - ", "?", "L/M/H"):
        assert format_zeichen in text, (
            f"AC-9 FAIL: Formatzeichen {format_zeichen!r} wird nicht erklaert: {text!r}"
        )
    assert "Alerts" in text, f"AC-9 FAIL: kein Abschnitt 'Alerts': {text!r}"
    segmente = sms_segments(text)
    assert segmente <= 5, f"AC-9 FAIL: CODES braucht {segmente} Segmente (max 5)."


# ═══════════════════════════════════════════════════════════════════════════
# AC-10 — KUERZEL deutsch auf E-Mail und Telegram, zeichengenau
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("kanal", ["email", "telegram"])
def test_codes_deutsch_auf_langform_kanaelen(monkeypatch, user_ids, kanal):
    """AC-10: Given ``kuerzel`` per E-Mail (immer deutsch) bzw. Telegram
    (deutsches Wort -> deutsch) / When die Antwort versendet wird / Then
    enthaelt sie den deutschen Wortlaut der Spec ZEICHENGENAU als
    zusammenhaengenden Block (Fusszeile/Betreff/Telegram-Kopf duerfen
    drumherum stehen, der Block selbst nicht abweichen)."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()
    if kanal == "email":
        text = _email_antwort(settings, recorder, nutzer, "kuerzel")
    else:
        text = _telegram_antwort(settings, recorder, nutzer, "kuerzel")
        treffer = [
            e for e in recorder.telegram_inhalte(nutzer.telegram_chat_id)
            if KUERZEL_WORTLAUT_DE in e["payload"].get("text", "")
        ]
        assert len(treffer) <= 1, "KUERZEL-Block mehrfach per Telegram versendet."
    assert KUERZEL_WORTLAUT_DE in text, (
        f"AC-10 FAIL ({kanal}): die Antwort auf 'kuerzel' enthaelt den "
        f"freigegebenen deutschen Wortlaut nicht zeichengenau.\n"
        f"Soll:\n{KUERZEL_WORTLAUT_DE}\n\nIst:\n{text}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# #2422 S6 löst #2454 AC-6 ab: "TF" steht im Trip UND im Ortsvergleich (AC-7)
# ═══════════════════════════════════════════════════════════════════════════

def test_ac6_trip_kuerzel_enthaelt_tf(monkeypatch, user_ids):
    """#2454 AC-6 ABGELOEST durch #2422 S6 (B1, PO-Entscheid V1): Given ein Nutzer
    sendet 'kuerzel'/'codes' im Trip-Kontext (kein aufgeloester Ortsvergleich) /
    When die Antwort gebaut wird / Then enthaelt sie in jeder Sprache das Kuerzel
    'TF' MIT Bedeutung -- der Trip versendet ``TF<Tiefstwert>@<Stunde>`` jetzt
    (``wind_chill``, Klasse (b) Invers-Min), die Kuerzel-Antwort muss es erklaeren.
    Vorher (#2454) entfiel 'TF' dort, weil der Trip es nie sendete.

    RED heute: ``codes_text(vergleich=False)`` entfernt 'TF' im Trip-Kontext."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    text_de = _premium_antwort(settings, recorder, nutzer, "kürzel")
    text_en = _premium_antwort(settings, recorder, nutzer, "codes")

    for sprache, text in (("de", text_de), ("en", text_en)):
        assert _code_match(text, "TF") is not None, (
            f"AC-6 (S6) FAIL ({sprache}): die Trip-CODES/KUERZEL-Antwort nennt "
            f"'TF' nicht, obwohl der Trip diesen Code jetzt versendet.\n"
            f"Antwort: {text}"
        )
        assert _hat_bedeutung_im_text(text, "TF", _soll_codes_ac9() | {"T", "TF", "C"}), (
            f"AC-6 (S6) FAIL ({sprache}): 'TF' steht ohne Bedeutungstext:\n{text}"
        )


def test_ac7_ortsvergleich_kuerzel_behaelt_tf(monkeypatch, user_ids):
    """AC-7: Given ein Ortsvergleich-Nutzer sendet 'kuerzel' im aufgeloesten
    Vergleichs-Kontext (per Namen adressiert, ``_dispatch_compare`` erreicht)
    / When die Antwort gebaut wird / Then bleibt 'TF' unveraendert enthalten
    -- der Ortsvergleich versendet 'TF' tatsaechlich (comparison.py:636).

    Heute bereits gruen (Regressionswaechter fuer AC-6: die Trip-Aenderung
    darf den Ortsvergleich nicht mittreffen)."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    name = nutzer.presets[0]["name"]
    settings = basis_settings()

    text = _premium_antwort(settings, recorder, nutzer, f"{name} kuerzel")

    assert _code_match(text, "TF") is not None, (
        f"AC-7 FAIL: im aufgeloesten Ortsvergleich-Kontext muss 'TF' erhalten "
        f"bleiben (unveraendertes Bestandsverhalten).\nAntwort: {text}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-11 — ein Kuerzel, eine Bedeutung, ueber alle Abschnitte
# ═══════════════════════════════════════════════════════════════════════════

def _bedeutungs_abbildung(sprache_feld: str, hazard_feld: str, baustein_feld: str):
    """Kuerzel -> [(Quelle, Bedeutung)] aus ALLEN drei Registern. Liefert
    zusaetzlich die Liste fehlender Register."""
    from output.tokens import builder, hazard_symbols

    fehlend: list[str] = []
    abbildung: dict[str, list[tuple[str, str]]] = {}
    for m in _metriken():
        feld = getattr(m, sprache_feld, None)
        if feld is None:
            fehlend.append(f"MetricDefinition.{sprache_feld} ({m.id})")
            continue
        for code, bedeutung in dict(feld).items():
            abbildung.setdefault(_norm(code), []).append((f"metrik:{m.id}", bedeutung))
    hazard_dict = getattr(hazard_symbols, hazard_feld, None)
    if hazard_dict is None:
        fehlend.append(f"hazard_symbols.{hazard_feld}")
    else:
        for hazard, code in hazard_symbols.HAZARD_SMS_SYMBOLS.items():
            abbildung.setdefault(_norm(code), []).append(
                (f"warnung:{hazard}", hazard_dict.get(hazard, ""))
            )
    baustein_dict = getattr(builder, baustein_feld, None)
    if baustein_dict is None:
        fehlend.append(f"builder.{baustein_feld}")
    else:
        for sym, bedeutung in baustein_dict.items():
            abbildung.setdefault(_norm(sym), []).append((f"baustein:{sym}", bedeutung))
    return abbildung, fehlend


@pytest.mark.parametrize("sprache", ["en", "de"])
def test_ein_kuerzel_eine_bedeutung_ueberall(sprache):
    """AC-11: Given die Kuerzel aller CODES-Abschnitte (Weather/More/Format/
    Alerts) / When sie ueber ALLE Register zusammen geprueft werden / Then
    kommt jedes Kuerzel genau einmal vor und hat genau eine Bedeutung — ohne
    Ausnahme je Abschnitt."""
    felder = {
        "en": (FELD_EN, HAZARD_FELD_EN, BAUSTEIN_FELD_EN),
        "de": (FELD_DE, HAZARD_FELD_DE, BAUSTEIN_FELD_DE),
    }[sprache]
    abbildung, fehlend = _bedeutungs_abbildung(*felder)
    assert not fehlend, (
        f"AC-11 FAIL ({sprache}): Bedeutungs-Register fehlen: "
        f"{sorted(set(f.split(' (')[0] for f in fehlend))} "
        f"(betroffen u. a.: {fehlend[:5]})"
    )
    assert len(abbildung) > 30, f"Nur {len(abbildung)} Kuerzel gefunden — Waechter blind?"
    doppelt = {c: q for c, q in abbildung.items() if len(q) > 1}
    assert not doppelt, f"AC-11 FAIL ({sprache}): Kuerzel mehrfach belegt: {doppelt}"
    leer = sorted(c for c, q in abbildung.items() if not str(q[0][1]).strip())
    assert not leer, f"AC-11 FAIL ({sprache}): Kuerzel ohne Bedeutung: {leer}"


# ═══════════════════════════════════════════════════════════════════════════
# AC-12 — Temperatur-Stundenverlauf traegt T
# ═══════════════════════════════════════════════════════════════════════════

def test_temperature_kuerzel_ist_t():
    """AC-12: Given ``temperature`` trug ``sms_code="D"`` / When bereinigt /
    Then ``sms_code == "T"`` und KEIN anderer Katalog-Eintrag traegt ``T`` als
    ``sms_code``, ``col_label`` oder in ``sms_multi_symbols``.

    Einzige Ausnahme (Spec v1.1, AC-28): der nicht waehlbare Kaelte-Alarm
    ``temperature_cold`` traegt ebenfalls ``sms_code="T"`` — er schaut auf
    dieselbe Temperatur (Ausnahmeliste in
    ``tests/unit/test_keine_doppelten_kennungen.py``)."""
    from app.metric_catalog import get_metric

    assert get_metric("temperature").sms_code == "T", (
        f"AC-12 FAIL: temperature.sms_code ist "
        f"{get_metric('temperature').sms_code!r} statt 'T' — 'D' bleibt doppelt "
        f"belegt (Stundenverlauf vs. Tageshoechstwert)."
    )
    andere = [
        m.id for m in _metriken() if m.id not in ("temperature", "temperature_cold") and (
            m.sms_code == "T" or m.col_label == "T"
            or "T" in {_norm(s) for s in m.sms_multi_symbols}
        )
    ]
    assert not andere, f"AC-12 FAIL: 'T' zusaetzlich vergeben an {andere}"


# ═══════════════════════════════════════════════════════════════════════════
# AC-13/AC-14/AC-15 — Kuerzel-Abfrage ueber den echten Befehlspfad
# ═══════════════════════════════════════════════════════════════════════════

def _variiere_temperaturen(nutzer) -> None:
    """Ueberschreibt den Snapshot des Trips mit VARIIERENDEN Stundenwerten
    (Stunde i -> 5+i °C), damit Tageswert und Stundenverlauf unterscheidbar
    sind (die geteilte Fixture setzt 12 °C konstant)."""
    from services.weather_snapshot import WeatherSnapshotService

    segmente = [_variiertes_segment(stage) for stage in nutzer.trip.stages]
    WeatherSnapshotService(nutzer.user_id).save(nutzer.trip.id, segmente, _ortstag_jetzt())


#: Stundenwerte des lokalen Testsegments — BEWUSST eine eigene Kopie (nicht
#: ``_befehl_e2e_fixtures.STANDARD_STUNDENWERT``), damit die zeichengenau
#: festgehaltene Briefing-Zeile (AC-22) nicht an fremden Fixture-Werten haengt.
_STUNDENWERT = dict(
    wind10m_kmh=18.0, wind_direction_deg=225, gust_kmh=30.0,
    precip_1h_mm=0.4, pop_pct=40, pressure_msl_hpa=1013.0, humidity_pct=55,
    dewpoint_c=6.0, snow_depth_cm=12.0, snow_new_24h_cm=2.0,
    snowfall_limit_m=1800, freezing_level_m=2200, visibility_m=8000,
    cloud_total_pct=60, cloud_low_pct=40, cloud_mid_pct=20, cloud_high_pct=10,
    dni_wm2=120.0,
)


def _variiertes_segment(stage):
    """EIN Segment ueber den ganzen Ortstag (Innsbruck) von ``stage.date``,
    stuendlich; Stunde i -> Temperatur 5+i °C, gefuehlt 1+i °C (Bauart wie
    ``_befehl_e2e_fixtures._segment_fuer_stage``, lokal kopiert)."""
    from datetime import time, timedelta, timezone

    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        PrecipType, Provider, SegmentWeatherData, SegmentWeatherSummary,
        ThunderLevel, TripSegment,
    )

    def mitternacht(tag):
        return datetime.combine(tag, time(0, 0), tzinfo=TZ).astimezone(timezone.utc)

    start = mitternacht(stage.date)
    ende_exkl = mitternacht(stage.date + timedelta(days=1))
    stunden = int((ende_exkl - start).total_seconds() // 3600)
    punkte = [
        ForecastDataPoint(
            ts=start + timedelta(hours=i), t2m_c=float(5 + i), wind_chill_c=float(1 + i),
            thunder_level=ThunderLevel.MED, precip_type=PrecipType.RAIN, **_STUNDENWERT,
        )
        for i in range(stunden)
    ]
    ende = ende_exkl - timedelta(minutes=1)
    segment = TripSegment(
        segment_id=f"seg-2417b-{stage.id}",
        start_point=GPXPoint(lat=47.2692, lon=11.4041, elevation_m=600),
        end_point=GPXPoint(lat=47.2892, lon=11.4241, elevation_m=900),
        start_time=start, end_time=ende,
        duration_hours=(ende - start).total_seconds() / 3600,
        distance_km=10.0, ascent_m=300.0, descent_m=300.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=0.0),
            data=punkte,
        ),
        aggregated=SegmentWeatherSummary(
            temp_min_c=-10.0, temp_max_c=35.0, thunder_level_max=ThunderLevel.MED,
            wind_max_kmh=40.0, precip_sum_mm=5.0, pop_max_pct=60,
        ),
        fetched_at=start, provider=Provider.OPENMETEO.value,
    )


def _briefing_zeile(segment, stage_name: str = "Heute") -> str:
    from output.renderers.sms_trip import SMSTripFormatter

    return SMSTripFormatter().format_sms(
        [segment], tz=TZ, report_type="evening",
        day_window_start_hour=0, day_window_end_hour=23,
        stage_name=stage_name, max_length=400,
    )


def _briefing_tageswerte(nutzer) -> dict[str, str]:
    """Tageshoechst ``D`` und Nachtwert ``N`` der heutigen Etappe, so wie das
    Trip-Briefing (echter SMS-Renderer) sie fuer denselben Datenstand zeigt."""
    heute = next(s for s in nutzer.trip.stages if s.date == _ortstag_jetzt())
    zeile = _briefing_zeile(_variiertes_segment(heute))
    d = re.search(r"(?<![A-Z])D(-?\d+)/(-?\d+)", zeile)
    n = re.search(r"(?<![A-Z])N(-?\d+)", zeile)
    assert d and n, f"Testaufbau: Briefing-Zeile ohne D/N-Token: {zeile!r}"
    return {"D": d.group(2), "N": n.group(1)}


def _ist_stundenverlauf(text: str) -> bool:
    return (
        len(re.findall(r"\b\d{1,2}:\d{2}\b", text)) > 1
        or len(re.findall(r"\d@\d", text)) > 1
        or "Verlauf" in text
    )


@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
@pytest.mark.parametrize("kuerzel", ["D", "N"])
def test_d_und_n_liefern_tageswert_kein_stundenverlauf(monkeypatch, user_ids, kanal, kuerzel):
    """AC-13: Given ``D`` (Tageshoechst) / ``N`` (Nacht) / When als Kuerzel-
    Abfrage per Nachricht gesendet / Then liefert die Antwort den Tages-
    Einzelwert der heutigen Etappe — denselben Wert wie das Trip-Briefing —
    und KEINEN Stundenverlauf."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    _variiere_temperaturen(nutzer)
    soll = _briefing_tageswerte(nutzer)[kuerzel]
    settings = basis_settings()
    if kanal == "telegram":
        text = _telegram_antwort(settings, recorder, nutzer, kuerzel)
    else:
        text = _premium_antwort(settings, recorder, nutzer, kuerzel)

    assert not any(f.lower() in text.lower() for f in NICHT_ERKANNT), (
        f"AC-13 FAIL ({kanal}): {kuerzel!r} wird nicht als Kuerzel erkannt: {text!r}"
    )
    assert not _ist_stundenverlauf(text), (
        f"AC-13 FAIL ({kanal}): {kuerzel!r} liefert einen Stundenverlauf statt "
        f"des Tageswerts: {text!r}"
    )
    assert re.search(rf"(?<![\d.,:]){re.escape(soll)}(?:[.,]0)?(?![\d.,:])", text), (
        f"AC-13 FAIL ({kanal}): Antwort auf {kuerzel!r} zeigt nicht den "
        f"Briefing-Tageswert {soll}: {text!r}"
    )


def test_t_liefert_den_bisherigen_temperatur_stundenverlauf(monkeypatch, user_ids):
    """AC-14: Given bisher lieferte ``D`` den Temperatur-Stundenverlauf / When
    nach der Aenderung ``T`` bzw. ``D`` gesendet wird / Then liefert ``T``
    genau den Temperatur-Stundenverlauf (= Antwort auf das Spaltenwort
    ``temp``) und ``D`` nicht mehr. Telegram und Premium-SMS."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    _variiere_temperaturen(nutzer)
    settings = basis_settings()

    tg_temp = _telegram_antwort(settings, recorder, nutzer, "temp")
    tg_t = _telegram_antwort(settings, recorder, nutzer, "T")
    tg_d = _telegram_antwort(settings, recorder, nutzer, "D")
    assert _ist_stundenverlauf(tg_temp), f"Testaufbau: 'temp' kein Verlauf: {tg_temp!r}"
    assert tg_t == tg_temp, (
        f"AC-14 FAIL (Telegram): 'T' liefert nicht den Temperatur-"
        f"Stundenverlauf.\n'temp': {tg_temp!r}\n'T':    {tg_t!r}"
    )
    assert tg_d != tg_temp, (
        f"AC-14 FAIL (Telegram): 'D' liefert weiterhin den Temperatur-"
        f"Stundenverlauf statt des Tageshoechstwerts: {tg_d!r}"
    )

    ps_temp = _premium_antwort(settings, recorder, nutzer, "temp")
    ps_t = _premium_antwort(settings, recorder, nutzer, "T")
    assert ps_t == ps_temp, (
        f"AC-14 FAIL (Premium-SMS): 'T' != 'temp'.\n'temp': {ps_temp!r}\n'T': {ps_t!r}"
    )
    assert ps_temp.startswith("T "), (
        f"AC-14 FAIL (Premium-SMS): der Temperatur-Stundenverlauf traegt nicht "
        f"das Kuerzel 'T' (Ein Kuerzel = eine Bedeutung): {ps_temp!r}"
    )


def test_ns24plus_wird_zu_ns_normalisiert(monkeypatch, user_ids):
    """AC-15: Given ``fresh_snow`` erscheint in der SMS als ``NS24+`` / When
    der Nutzer ``NS24+`` unveraendert zuruecksendet / Then ist das dieselbe
    Abfrage wie ``NS``."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()
    ns = _telegram_antwort(settings, recorder, nutzer, "NS")
    ns24 = _telegram_antwort(settings, recorder, nutzer, "NS24+")
    assert not any(f.lower() in ns.lower() for f in NICHT_ERKANNT), (
        f"Testaufbau: 'NS' nicht erkannt: {ns!r}"
    )
    assert ns24 == ns, (
        f"AC-15 FAIL: 'NS24+' wird nicht wie 'NS' behandelt.\n'NS': {ns!r}\n"
        f"'NS24+': {ns24!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-16/AC-17 — Kollisionsfreiheit der Befehlswoerter
# ═══════════════════════════════════════════════════════════════════════════

def _befehlswoerter() -> tuple[set[str], list[str]]:
    """Alle Befehlswoerter (de + en + Aliase), klein. Zweiter Wert: Befunde,
    wenn ``_COMMAND_SPECS`` die Feldnamen ``wort``/``wort_en`` nicht traegt."""
    from services.trip_command_processor import _BARE_KEYWORD_MAP, _COMMAND_SPECS

    woerter = {w.lower() for w in _BARE_KEYWORD_MAP}
    befunde: list[str] = []
    for eintrag in _COMMAND_SPECS:
        wort = getattr(eintrag, "wort", None)
        wort_en = getattr(eintrag, "wort_en", None)
        if not wort or not wort_en:
            befunde.append(repr(eintrag)[:60])
            if isinstance(eintrag, tuple) and eintrag and isinstance(eintrag[0], str):
                woerter.add(eintrag[0].lower())
            continue
        woerter |= {wort.lower(), wort_en.lower()}
    return woerter, befunde


def _eingabe_kuerzel() -> set[str]:
    codes = {"T"}
    for cs in _ausgabe_kuerzel_je_metrik().values():
        codes |= cs
    for m in _metriken():
        for feld in (FELD_EN, FELD_DE):
            codes |= {_norm(c) for c in dict(getattr(m, feld, None) or {})}
    return {_eingabe_norm(c).lower() for c in codes} | {c.lower() for c in codes}


def test_befehle_und_kuerzel_sind_disjunkt():
    """AC-16: Given alle Befehlswoerter (de + en inkl. Aliase) und alle
    Eingabe-Kuerzel (Ausgabe-Kuerzel normalisiert + ``T``) / When beide
    Mengen gebildet werden / Then sind sie disjunkt."""
    woerter, befunde = _befehlswoerter()
    assert not befunde, (
        "AC-16 FAIL: _COMMAND_SPECS-Eintraege ohne Feldnamen 'wort'/'wort_en' "
        f"(englisches Befehlswort fehlt): {befunde}"
    )
    kuerzel = _eingabe_kuerzel()
    assert len(woerter) >= 24 and len(kuerzel) > 25, (woerter, kuerzel)
    kollision = sorted(woerter & kuerzel)
    assert not kollision, f"AC-16 FAIL: Befehlswort == Eingabe-Kuerzel: {kollision}"


def test_kein_befehlswort_kollidiert_mit_verknuepfungscode():
    """AC-17 — REGRESSIONSWAECHTER, heute absichtlich GRUEN: kein Befehlswort
    (de, Aliase und — sobald vorhanden — ``wort_en``) hat die Gestalt des
    Premium-SMS-Verknuepfungscodes ``^XX[A-HJKMNP-Z]{3}[2-9]{3}$``. Kein Wort
    beginnt mit ``XX``; der Waechter faengt kuenftige Woerter ab."""
    woerter, _befunde = _befehlswoerter()
    assert woerter, "Keine Befehlswoerter gefunden — Waechter blind."
    treffer = sorted(w for w in woerter if VERKNUEPFUNGSCODE_RE.match(w.upper()))
    assert not treffer, f"AC-17 FAIL: Befehlswort sieht aus wie ein Code: {treffer}"
    assert VERKNUEPFUNGSCODE_RE.match("XXABC234"), "Muster-Selbsttest"


# ═══════════════════════════════════════════════════════════════════════════
# AC-22 — automatisch versendete Ausgaben nach der T-Umstellung
# ═══════════════════════════════════════════════════════════════════════════

#: Trip-Briefing-Kurzformzeile vom 27.09.2026 (vor der Umstellung), echter
#: Renderer, fester Datenstand (Stage 2026-07-03, Stunde i -> 5+i °C).
BRIEFING_ZEILE_VORHER = (
    "Heute: N5 D5/28 FN1 FD1/24 R0.4@0 PR40%@0 W18@0 G30@0 TH:M@0 TH+:- "
    "HU55@0 DP6@0 WD:SW PT:R CT60@0 CL40@0 CM20@0 CH10@0 VS8.0@0 SU12 HP1013 "
    "FZ2200@0"
)

#: Ortsvergleich-Kurzform vom 27.09.2026 (vor der Umstellung), echter
#: Renderer ``render_compare_sms`` mit ``temp_max``/``temp_min``.
VERGLEICH_ZEILE_VORHER = "Vergleich 27.07.: Andermatt D 16C L 6C"


def test_automatische_ausgaben_nach_t_umstellung():
    """AC-22: Given Trip/Ortsvergleich mit Temperatur und ein Temperatur-Alarm
    / When nach der Umstellung automatisch erzeugt / Then (a) bleibt die
    Trip-Briefing-Kurzformzeile zeichengleich (``D`` = Tageshoechst), (b)
    bleibt die Ortsvergleich-Kurzform zeichengleich bei ``D``/``L`` (Spec
    v1.1: sie liest ueber ``kuerzel_metric_id`` die Groessen
    ``temperature_day_high``/``temperature_day_low``), (c) zeigt NUR die
    Temperatur-Alarm-SMS ``T`` statt ``D``. (a) und (b) sind
    Regressionswaechter, (c) ist das neue Verhalten."""
    from app.trip import Stage, Waypoint
    from app.models import ThunderLevel
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from output.renderers.alert.render import render_sms
    from output.renderers.comparison import render_compare_sms

    # (a) Trip-Briefing zeichengleich
    stage = Stage(
        id="T1", name="Heute", date=date(2026, 7, 3),
        waypoints=[
            Waypoint(id="a", name="S", lat=47.2692, lon=11.4041, elevation_m=600),
            Waypoint(id="b", name="Z", lat=47.2892, lon=11.4241, elevation_m=900),
        ],
    )
    zeile = _briefing_zeile(_variiertes_segment(stage))
    assert zeile == BRIEFING_ZEILE_VORHER, (
        f"AC-22 FAIL (a): die Trip-Briefing-Zeile hat sich veraendert.\n"
        f"vorher: {BRIEFING_ZEILE_VORHER!r}\nnachher: {zeile!r}"
    )
    assert "D5/28" in zeile, "AC-22 (a): D muss der Tagesbereich bis Tageshoechst sein"

    # (b) Ortsvergleich-Kurzform zeichengleich bei D/L (Regressionswaechter)
    loc = LocationResult(
        location=SavedLocation(id="a", name="Andermatt", lat=47.0, lon=11.0, elevation_m=600),
        temp_max=16.4, temp_min=6.2, wind_max=15.0, gust_max=20.0,
        thunder_level_max=ThunderLevel.NONE,
    )
    result = ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=date(2026, 7, 27),
        created_at=datetime(2026, 7, 27, 8, 0),
    )
    sms = render_compare_sms(result, enabled_metrics=["temp_max", "temp_min"])
    assert sms == VERGLEICH_ZEILE_VORHER, (
        f"AC-22 FAIL (b): die Ortsvergleich-Kurzform hat sich veraendert.\n"
        f"vorher: {VERGLEICH_ZEILE_VORHER!r}\nnachher: {sms!r}"
    )

    # (c) Temperatur-Alarm-SMS: T statt D
    ereignis = AlertEvent(
        metric_id="temperature", value_from=20.0, value_to=28.0, threshold=25.0,
        cmp="über", occurred_at="14:00", km_from=8.0, km_to=8.0, segment_id="Ziel",
    )
    alarm = render_sms(AlertMessage(trip_short="KHW 403", stand_at="10:00", events=(ereignis,)))
    assert "T20->28" in alarm and "D20" not in alarm, (
        f"AC-22 FAIL (c): Temperatur-Alarm-SMS traegt nicht 'T': {alarm!r} "
        f"(D bedeutet in der SMS den Tageshoechstwert)."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-28 — Kaelte-Alarm traegt T statt N
# ═══════════════════════════════════════════════════════════════════════════

def test_kaelte_alarm_traegt_t_statt_n():
    """AC-28: Given der Kaelte-Alarm ``temperature_cold`` trug ``N`` (in der
    SMS = Nachtwert) / When eine Kaelte-Alarm-SMS gerendert wird / Then
    traegt sie ``T`` — dieselbe Temperatur wie ``temperature``."""
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from output.renderers.alert.render import render_sms

    ereignis = AlertEvent(
        metric_id="temperature_cold", value_from=2.0, value_to=-4.0, threshold=0.0,
        cmp="unter", occurred_at="05:00", km_from=8.0, km_to=8.0, segment_id="Ziel",
    )
    sms = render_sms(AlertMessage(trip_short="KHW 403", stand_at="10:00", events=(ereignis,)))
    assert "T2->-4" in sms and not re.search(r"(?<![A-Z])N-?\d", sms), (
        f"AC-28 FAIL: die Kaelte-Alarm-SMS traegt nicht 'T' (N bedeutet in der "
        f"SMS den Nachtwert): {sms!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-29 — Ortsvergleich-Auswahl zeigt das gesendete Kuerzel
# ═══════════════════════════════════════════════════════════════════════════

def test_vergleichsauswahl_zeigt_das_gesendete_kuerzel():
    """AC-29: Given die Ortsvergleich-Auswahl (``get_compare_metric_catalog``)
    / When sie ausgeliefert wird / Then traegt jeder Eintrag als ``sms_code``
    das Kuerzel, das die Ortsvergleich-SMS fuer ihn zeigt (ueber
    ``kuerzel_metric_id``, sonst ``metric_id``): ``temp_max_c`` -> ``D``,
    ``temp_min_c`` -> ``L``; kein Kuerzel steht auf zwei Eintraegen.

    Soll je Eintrag = ``kurzform_kuerzel(kuerzel_metric_id_for(e))`` — dieselbe
    Funktion, mit der ``comparison._sms_metric_cell`` das Kuerzel der
    versendeten Vergleichs-SMS bildet. Dass die SMS selbst ``D``/``L`` zeigt,
    misst ``test_automatische_ausgaben_nach_t_umstellung`` (b) am gerenderten
    Text."""
    from app.metric_catalog import kurzform_kuerzel
    from output.renderers.compare_metric_catalog import (
        get_compare_metric_catalog, kuerzel_metric_id_for,
    )

    eintraege = get_compare_metric_catalog()
    je_key = {e["key"]: e for e in eintraege}
    assert je_key["temp_max_c"]["sms_code"] == "D", (
        f"AC-29 FAIL: temp_max_c traegt sms_code {je_key['temp_max_c']['sms_code']!r} "
        f"statt 'D' (die Vergleichs-SMS zeigt 'D')."
    )
    assert je_key["temp_min_c"]["sms_code"] == "L", (
        f"AC-29 FAIL: temp_min_c traegt sms_code {je_key['temp_min_c']['sms_code']!r} "
        f"statt 'L' (die Vergleichs-SMS zeigt 'L')."
    )
    abweichend = [
        (e["key"], e["sms_code"], kurzform_kuerzel(kuerzel_metric_id_for(e)))
        for e in eintraege
        if e["sms_code"] != kurzform_kuerzel(kuerzel_metric_id_for(e))
    ]
    assert not abweichend, (
        f"AC-29 FAIL: Auswahl-Kuerzel weicht vom gesendeten Kuerzel ab "
        f"(key, Auswahl, SMS): {abweichend}"
    )
    zaehler: dict[str, list[str]] = {}
    for e in eintraege:
        if e["sms_code"]:
            zaehler.setdefault(e["sms_code"], []).append(e["key"])
    doppelt = {k: v for k, v in zaehler.items() if len(v) > 1}
    assert not doppelt, f"AC-29 FAIL: Kuerzel auf mehreren Eintraegen: {doppelt}"


# ═══════════════════════════════════════════════════════════════════════════
# AC-23 — Bedeutung kommt nur aus dem Katalog
# ═══════════════════════════════════════════════════════════════════════════

#: Spec v1.1 AC-28: ``temperature_cold`` teilt ``T`` mit ``temperature`` und
#: traegt KEINE eigene Kuerzel-Bedeutung (CODES erklaert ``T`` einmal).
OHNE_EIGENE_BEDEUTUNG = frozenset({"temperature_cold"})

def test_bedeutung_kommt_nur_aus_dem_katalog(monkeypatch, user_ids):
    """AC-23: Given die Bedeutung eines Wetter-Kuerzels steht genau einmal im
    ``MetricDefinition``-Eintrag / When sie zur Laufzeit im ECHTEN Katalog-
    Objekt geaendert wird / Then zeigt die CODES-Antwort den geaenderten Text.
    Zusaetzlich traegt jede ``_METRICS``-Metrik mit Ausgabe-Kuerzel eine nicht
    leere en- UND de-Bedeutung fuer jedes ihrer Kuerzel."""
    from app.metric_catalog import get_metric

    luecken: list[str] = []
    for metric_id, codes in sorted(_ausgabe_kuerzel_je_metrik().items()):
        if metric_id in OHNE_EIGENE_BEDEUTUNG:
            continue
        m = get_metric(metric_id)
        for feld in (FELD_EN, FELD_DE):
            werte = getattr(m, feld, None)
            if not isinstance(werte, dict):
                luecken.append(f"{metric_id}.{feld} fehlt")
                continue
            for code in sorted(codes):
                if not str(werte.get(code, "")).strip():
                    luecken.append(f"{metric_id}.{feld}[{code!r}] leer")
    assert not luecken, (
        f"AC-23 FAIL: {len(luecken)} Katalog-Bedeutungen fehlen: {luecken}"
    )

    bedeutungen = getattr(get_metric("precipitation"), FELD_EN)
    monkeypatch.setitem(bedeutungen, "R", "zzqx rainfall")
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    text = _premium_antwort(basis_settings(), recorder, nutzer, "CODES")
    assert "zzqx rainfall" in text, (
        f"AC-23 FAIL: die im Katalog geaenderte Bedeutung von 'R' erscheint "
        f"nicht in der CODES-Antwort — der CODES-Aufbau liest sie nicht aus "
        f"dem Katalog: {text!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-24 — Referenzdokument
# ═══════════════════════════════════════════════════════════════════════════

def test_metric_output_matrix_fuehrt_codes_kuerzel():  # doc-compliance-test
    """AC-24 (# doc-compliance-test): ``docs/reference/metric_output_matrix.md``
    fuehrt CODES/KUERZEL in Abschnitt 2 mit Datei:Zeile und Waechter, nennt
    das neue Bedeutungsfeld im Absatz "Grundlage" und fuehrt ``temperature``
    nicht mehr als Telegram-Ausnahme."""
    doc = (REPO / "docs" / "reference" / "metric_output_matrix.md").read_text(encoding="utf-8")
    grundlage = doc.split("### Grundlage", 1)[1].split("\n## 2.", 1)[0]
    abschnitt2 = doc.split("\n## 2.", 1)[1].split("\n## 3.", 1)[0]

    zeilen = [z for z in abschnitt2.splitlines() if "CODES" in z and "KUERZEL" in z]
    assert zeilen, "AC-24 FAIL: Abschnitt 2 nennt CODES/KUERZEL nicht."
    assert any(re.search(r"\.py:\d+", z) for z in zeilen), (
        f"AC-24 FAIL: CODES/KUERZEL-Zeile ohne Datei:Zeile: {zeilen}"
    )
    assert any("test_kuerzel_eindeutig.py" in z for z in zeilen), (
        f"AC-24 FAIL: CODES/KUERZEL-Zeile ohne Waechter: {zeilen}"
    )
    assert FELD_EN in grundlage and FELD_DE in grundlage, (
        "AC-24 FAIL: Absatz 'Grundlage' nennt das Bedeutungsfeld nicht."
    )
    assert "`temperature` (`T`)" not in grundlage, (
        "AC-24 FAIL: 'Grundlage' fuehrt temperature weiter als Telegram-Ausnahme."
    )
