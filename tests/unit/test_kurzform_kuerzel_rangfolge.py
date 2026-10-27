"""Die Rangfolge `sms_multi_symbols` VOR `sms_code` ist bewacht (Adversary F001
zu #2232).

SPEC: docs/specs/modules/fix_2232_kuerzel_ein_modell_trip_vergleich.md

Zwei Leser loesen "welches Kuerzel sendet die Kurzform fuer diese Groesse?" auf,
beide mit derselben Rangfolge, aber ueber verschiedene Tabellen:

  * `metric_catalog.kurzform_kuerzel()` — Vergleichs-SMS
    (`comparison.py::_sms_metric_cell`), liest `SMS_MULTI_SYMBOLS_BY_METRIC`,
    sonst `sms_code`.
  * `api.routers.config.sms_symbols_for()` — Editor-Marke ueber
    `/api/sms-symbols`, liest `SMS_MULTI_SYMBOLS_BY_METRIC`, sonst
    `SMS_SYMBOL_BY_METRIC`.

🔴 Warum dieser Test noetig ist (gemessener Adversary-Befund F001, 2026-09-09):
im ECHTEN Register traegt keine einzige Groesse zugleich einen `sms_code` UND
ein davon ABWEICHENDES `sms_multi_symbols[0]`. Wo beide Zweige denselben Wert
liefern, ist ihre Reihenfolge unbeobachtbar — die Rangfolge liesse sich
vertauschen, ohne dass ein Test rot wird. Genau daran haengt aber die
#2232-Zusicherung: `temperature_day_high` fuehrt sein `D` AUSSCHLIESSLICH in
`sms_multi_symbols` (`sms_code` ist leer, weil `"D"` global schon von
`temperature` belegt ist). Wuerde `sms_code` gewinnen, faende der Vergleich
kein Kuerzel und die Zelle entfiele ersatzlos.

Der divergierende Datenpunkt wird deshalb als Registerkopie INJIZIERT (Muster
`compare_metric_catalog.kuerzel_identity_violations(entries=...)`) — kein
`patch()` auf Modulglobale, keine Veraenderung des echten Registers.

Test-Politik (CLAUDE.md, Schicht "Kern"): deterministisch, kein Netz, kein Mock.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from api.routers.config import sms_symbols_for
from app import metric_catalog as register_mod
from app.metric_catalog import (
    SMS_MULTI_SYMBOLS_BY_METRIC, get_sms_code, kurzform_kuerzel,
)

# Issue #1409: Prueflinge relativ zur eigenen Testdatei aufloesen.
_REPO = Path(__file__).resolve().parents[2]

# Der divergierende Datenpunkt, den es im echten Register nicht gibt: das
# Mehrfach-Symbol sagt "Y", der Einzel-/Registercode sagt "X". Nur an so einem
# Paar ist ueberhaupt sichtbar, WELCHER der beiden Zweige gewinnt.
_KENNUNG = "pruefgroesse_mit_zwei_kuerzeln"
_AUS_MEHRFACH = "Y"
_AUS_SMS_CODE = "X"


def test_waechter_prueft_den_code_dieses_arbeitsbaums():
    """#1409: der Pruefling muss aus DIESEM Arbeitsbaum stammen."""
    pfad = Path(register_mod.__file__).resolve()
    assert str(pfad).startswith(str(_REPO)), (
        f"Der Waechter prueft {pfad} statt den Code unterhalb {_REPO}."
    )


def test_das_echte_register_kann_die_rangfolge_gar_nicht_zeigen():
    """Begruendung dieses Tests, als Zusicherung statt als Prosa: solange keine
    Registergroesse divergierende Werte traegt, ist die Rangfolge am echten
    Datenbestand unbeobachtbar. Schlaegt dieser Test eines Tages an, gibt es
    einen echten divergierenden Datenpunkt — dann gehoert er in die
    Positivkontrolle unten aufgenommen, und der injizierte darf verschwinden."""
    divergierend = {
        metric_id: (symbole[0].rstrip(":"), get_sms_code(metric_id))
        for metric_id, symbole in SMS_MULTI_SYMBOLS_BY_METRIC.items()
        if symbole and get_sms_code(metric_id)
        and symbole[0].rstrip(":") != get_sms_code(metric_id)
    }
    assert divergierend == {}, (
        "Das Register traegt jetzt divergierende Kuerzel "
        f"({divergierend!r}) — dieser Fall gehoert in die Positivkontrolle, "
        "der injizierte Datenpunkt wird dann ueberfluessig."
    )


def test_vergleichs_sms_liest_das_mehrfach_symbol_nicht_den_sms_code():
    """Adversary F001, Leser 1: `kurzform_kuerzel()` MUSS `Y` liefern.

    Mutationsnachweis: vertauscht man die beiden Zweige in
    `metric_catalog.kurzform_kuerzel()`, liefert dieser Aufruf `X` und der Test
    wird rot."""
    ergebnis = kurzform_kuerzel(
        _KENNUNG,
        mehrfach_symbole={_KENNUNG: (_AUS_MEHRFACH,)},
        sms_codes={_KENNUNG: _AUS_SMS_CODE},
    )
    assert ergebnis == _AUS_MEHRFACH, (
        f"kurzform_kuerzel() liefert {ergebnis!r} statt {_AUS_MEHRFACH!r} — die "
        "Rangfolge ist vertauscht. Folge im Betrieb: `temperature_day_high` "
        "fuehrt sein 'D' NUR in sms_multi_symbols (sms_code ist leer, weil 'D' "
        "global von `temperature` belegt ist); gewaenne sms_code, faende die "
        "Vergleichs-SMS kein Kuerzel und die Temperaturzelle entfiele ganz."
    )


def test_editor_marke_liest_das_mehrfach_symbol_nicht_das_einzel_symbol():
    """Adversary F001, Leser 2: `/api/sms-symbols::sms_symbols_for()` MUSS
    `['Y']` liefern — dieselbe Rangfolge, andere Tabelle.

    Mutationsnachweis: vertauscht man die beiden Zweige in
    `api/routers/config.py::sms_symbols_for()`, liefert dieser Aufruf `['X']`."""
    ergebnis = sms_symbols_for(
        _KENNUNG, {_KENNUNG: (_AUS_MEHRFACH,)}, {_KENNUNG: _AUS_SMS_CODE},
    )
    assert ergebnis == [_AUS_MEHRFACH], (
        f"sms_symbols_for() liefert {ergebnis!r} statt {[_AUS_MEHRFACH]!r} — die "
        "Editor-Marke zeigte dann ein anderes Kuerzel als die SMS sendet "
        "(genau der Widerspruch, den #2232 beseitigt hat)."
    )


def test_beide_leser_liefern_am_selben_datenpunkt_dasselbe_kuerzel():
    """Die Klammer um beide: derselbe divergierende Datenpunkt ergibt in beiden
    Lesern dasselbe Kuerzel. Wird die Rangfolge nur in EINEM der beiden
    gedreht, faellt es hier zusaetzlich auf."""
    aus_sms = kurzform_kuerzel(
        _KENNUNG,
        mehrfach_symbole={_KENNUNG: (_AUS_MEHRFACH,)},
        sms_codes={_KENNUNG: _AUS_SMS_CODE},
    )
    aus_editor = sms_symbols_for(
        _KENNUNG, {_KENNUNG: (_AUS_MEHRFACH,)}, {_KENNUNG: _AUS_SMS_CODE},
    )[0]
    assert aus_sms == aus_editor, (
        f"SMS-Weg sendet {aus_sms!r}, der Editor zeigt {aus_editor!r} — die "
        "beiden Rangfolgen sind auseinandergelaufen."
    )


@pytest.mark.parametrize(
    "mehrfach,codes,erwartet",
    [
        # Kein Mehrfach-Symbol -> Rueckfall auf den Code (beide Zweige noetig,
        # sonst waere "gib immer das Mehrfach-Symbol" ebenfalls gruen).
        ({}, {_KENNUNG: _AUS_SMS_CODE}, _AUS_SMS_CODE),
        # Leeres Tupel zaehlt als "kein Mehrfach-Symbol", nicht als leeres Kuerzel.
        ({_KENNUNG: ()}, {_KENNUNG: _AUS_SMS_CODE}, _AUS_SMS_CODE),
        # Weder noch -> kein Kuerzel (die Zelle entfaellt, sie wird nicht leer).
        ({}, {}, ""),
        # Grammatik-Doppelpunkt gehoert nicht zum Kuerzel (Muster 'TH:').
        ({_KENNUNG: ("TH:", "TH+:")}, {_KENNUNG: _AUS_SMS_CODE}, "TH"),
    ],
    ids=["Rueckfall auf sms_code", "leeres Tupel faellt zurueck",
         "gar kein Kuerzel", "Doppelpunkt abgetrennt"],
)
def test_die_uebrigen_zweige_der_rangfolge(
    mehrfach: dict, codes: dict, erwartet: str,
):
    """Ohne diese Faelle waere ein `return mehrfach[0]` ohne jeden Rueckfall
    ebenfalls gruen -- der Test bewiese dann nur den halben Vertrag."""
    assert kurzform_kuerzel(
        _KENNUNG, mehrfach_symbole=mehrfach, sms_codes=codes,
    ) == erwartet


def test_positivkontrolle_am_echten_register():
    """Ohne Injektion misst dieselbe Funktion weiterhin das echte Register --
    sonst bewiese der Test nur, dass die Parameter funktionieren."""
    assert kurzform_kuerzel("temperature_day_high") == "D"
    assert kurzform_kuerzel("temperature_day_low") == "L"
    assert kurzform_kuerzel("wind") == get_sms_code("wind") == "W"
    assert kurzform_kuerzel("thunder") == "TH"
