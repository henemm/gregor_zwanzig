"""TDD — Issue #2046 AC-8: E-Mail-/Telegram-Langform ignorieren `onset_precip_mm`.

Die Kurzform (`_render_sms_onset`) bekam mit #2046 eine Mengenangabe
(`R2.5@18:00`). Die Langform bleibt laut Spec unveraendert: sie zeigt weiter
`intensity_label` als Wort und liest `onset_precip_mm` NICHT. Zwei Ebenen,
wie von der Spec verlangt (`docs/specs/modules/fix_2046_onset_menge.md`,
AC-8):

1. Verhaltenstest (der eigentliche Waechter): dieselbe Eingabe einmal mit
   `onset_precip_mm=None`, einmal mit einem gesetzten Wert gerendert -- beide
   Ausgaben muessen zeichengleich sein.
2. Struktureller Nachweis via `inspect.getsource()`: der Bezeichner
   `onset_precip_mm` kommt im Quelltext der beiden Funktionen nicht vor.

Mock-frei: echte Dataclass-Konstruktion, echte Renderer-Aufrufe.

SPEC: docs/specs/modules/fix_2046_onset_menge.md, AC-8
"""
from __future__ import annotations

import inspect

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import _render_email_onset, _render_telegram_onset


def _onset_msg(*, onset_precip_mm: float | None) -> AlertMessage:
    onset = OnsetEvent(
        onset_minutes=18, onset_time="18:00", km_from=5.0, km_to=9.0,
        is_convective=False, intensity_label="leichter Regen",
        source_label="Radar (DWD)", onset_precip_mm=onset_precip_mm,
    )
    return AlertMessage(
        trip_short="GR20", stand_at="17:42", events=(onset,),
        source="Radar (DWD)", cooldown_display="2 Stunden",
    )


class TestEmailLangformIgnoriertMenge:
    def test_html_und_plain_zeichengleich_mit_und_ohne_menge(self):
        html_ohne, plain_ohne = _render_email_onset(_onset_msg(onset_precip_mm=None))
        html_mit, plain_mit = _render_email_onset(_onset_msg(onset_precip_mm=2.5))

        assert html_ohne == html_mit, (
            "E-Mail-HTML unterscheidet sich, obwohl nur onset_precip_mm variiert:\n"
            f"  ohne: {html_ohne!r}\n  mit:  {html_mit!r}"
        )
        assert plain_ohne == plain_mit, (
            "E-Mail-Plain-Text unterscheidet sich, obwohl nur onset_precip_mm "
            f"variiert:\n  ohne: {plain_ohne!r}\n  mit:  {plain_mit!r}"
        )


class TestTelegramLangformIgnoriertMenge:
    def test_text_zeichengleich_mit_und_ohne_menge(self):
        tg_ohne = _render_telegram_onset(_onset_msg(onset_precip_mm=None))
        tg_mit = _render_telegram_onset(_onset_msg(onset_precip_mm=2.5))

        assert tg_ohne == tg_mit, (
            "Telegram-Langform unterscheidet sich, obwohl nur onset_precip_mm "
            f"variiert:\n  ohne: {tg_ohne!r}\n  mit:  {tg_mit!r}"
        )


class TestStrukturellerNichtberuehrungsNachweis:
    """AC-8 verlangt zusaetzlich einen Grep-Nicht-Beruehrungs-Nachweis ueber
    `inspect.getsource()` (kein Dateiinhalt-Check per `file.read_text()`,
    das waere nach der Test-Politik ein verbotener Verhaltensersatz)."""

    def test_render_email_onset_referenziert_onset_precip_mm_nicht(self):
        source = inspect.getsource(_render_email_onset)  # doc-compliance-test
        assert "onset_precip_mm" not in source, (
            "_render_email_onset() referenziert onset_precip_mm -- laut AC-8 "
            "darf die Langform dieses Feld nicht lesen."
        )

    def test_render_telegram_onset_referenziert_onset_precip_mm_nicht(self):
        source = inspect.getsource(_render_telegram_onset)  # doc-compliance-test
        assert "onset_precip_mm" not in source, (
            "_render_telegram_onset() referenziert onset_precip_mm -- laut "
            "AC-8 darf die Langform dieses Feld nicht lesen."
        )
