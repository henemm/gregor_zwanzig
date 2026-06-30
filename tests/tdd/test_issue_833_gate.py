"""TDD RED — Issue #833: Strukturelle Härtung des Mail-Acceptance-Gates.

Beweist VERHALTEN (kein Mock, keine Dateiinhalt-Checks): das erweiterte Gate
`.claude/hooks/briefing_mail_validator.py` muss eine Defekt-Klasse erkennen, die
heute durchrutscht, weil der Validator die Mail nur als MIME-String prüft:

  AC-1  Render statt String — Mobile-Viewport fehlt → Gate rot (über validate_message)
  AC-3  Ebenen-Konsistenz   — Pills-Spitze ≠ Tabellen-Max → _check_layer_consistency
  AC-4  Metrik-Plausibilität — „Sonne X min" ≠ Tabellen-Summe; „kein Regen" bei Regen
  AC-5  Lokalisierung        — englische Spaltenköpfe (Gust/Rain/Sun) → _check_localization
  AC-6  Selbsttest des Gates — konstruierte defekte Mails → validate_message liefert Exit-1

Die neuen Check-Funktionen existieren in der RED-Phase noch NICHT → die getattr-
Guards schlagen mit klarer Meldung fehl. Die konstruierten HTML-Artefakte tragen
die ECHTEN Renderer-Marker (`<table class="resp">`, `data-label`, Pill-`<span>`,
`<th>`, `.mobile-compact`) — kein Mock, sondern reale Wire-Artefakte.

Spec: docs/specs/modules/issue_833_mail_gate_structural.md
"""
from __future__ import annotations

import email
import importlib.util
from email.message import EmailMessage
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "briefing_mail_validator.py"


def _load_validator():
    """Lädt den Validator als isoliertes Modul (Muster wie test_issue_733)."""
    spec = importlib.util.spec_from_file_location("bmv833", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _require(mod, name: str):
    """Holt eine (in RED noch fehlende) Check-Funktion oder failt mit klarer Meldung."""
    fn = getattr(mod, name, None)
    assert fn is not None, (
        f"Funktion {name}() existiert noch nicht in briefing_mail_validator.py "
        f"— Issue #833 nicht implementiert (RED erwartet)."
    )
    return fn


# --------------------------------------------------------------------------- #
# Echte HTML-Bausteine mit den Renderer-Markern (verifiziert gegen render_email)
# --------------------------------------------------------------------------- #
def _table_resp(rows: list[tuple[str, str]], col_label: str, header_de: str) -> str:
    """Desktop-Tabelle `<table data-table="resp">` mit Zeit-Spalte + einer Metrik-Spalte.

    rows: Liste (HH:00, wert). header_de: deutscher Spaltenkopf der Metrik.
    fix-911-table-jsx AC-1: Marker ist data-table="resp" (kein CSS-class).
    """
    trs = "".join(
        f'<tr><td data-label="Time">{t}</td>'
        f'<td data-label="{col_label}">{v}</td></tr>'
        for t, v in rows
    )
    return (
        f'<table data-table="resp" style="width:100%;border-collapse:collapse;">'
        f'<thead><tr><th>Zeit</th><th>{header_de}</th></tr>'
        f'</thead><tbody>{trs}</tbody></table>'
    )


def _pill(text: str) -> str:
    return (
        '<span style="display:inline-flex;align-items:center;padding:4px 10px;'
        'border:1px solid #8aacd0;background:#dde8f3;color:#1e3a5f;font-size:11px;'
        f'font-weight:600;border-radius:2px;">{text}</span>'
    )


def _overview(pills: list[str]) -> str:
    inner = " ".join(pills)
    return (
        '<p style="font-size:9px;text-transform:uppercase;color:#5c5a52;'
        f'margin:0 0 6px 0">Metriken-Überblick</p>{inner}'
    )


def _wire(msg: EmailMessage) -> email.message.Message:
    return email.message_from_bytes(msg.as_bytes())


def _build_full(html: str,
                plain: str = "Gravel-Trip Evening Report\nEtappe 3",
                subject: str = "Gravel-Trip - Evening Report") -> email.message.Message:
    """Vollständige multipart/alternative-Mail mit den Pflicht-Markern."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "gregor_zwanzig@henemm.com"
    msg["To"] = "gregor-test@henemm.com"
    msg["X-GZ-Mail-Type"] = "trip-briefing"
    msg["X-GZ-Format"] = "full"
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    return _wire(msg)


# Saubere deutsche Stundentabelle (≥2 HH:00, Stunden 06–22, temp lo≤hi) als Basis.
_CLEAN_TABLE = _table_resp(
    [("10:00", "55"), ("11:00", "30"), ("12:00", "20")],
    col_label="Gust", header_de="Böen",
)


# --------------------------------------------------------------------------- #
# AC-5 — Lokalisierung: englische Spaltenköpfe (#94-Klasse)
# --------------------------------------------------------------------------- #
class TestAC5Localization:
    @pytest.mark.xfail(
        reason="#862: _check_localization deliberately removed — superseded by fix-862-849",
        strict=False,
    )
    def test_english_header_gust_rain_sun_detected(self):
        mod = _load_validator()
        check = _require(mod, "_check_localization")
        html = (
            '<table class="resp"><thead><tr><th>Time</th><th>Gust</th>'
            '<th>Rain</th><th>Sun</th></tr></thead><tbody>'
            '<tr><td data-label="Time">10:00</td><td>85</td><td>8</td><td>0.5 h</td></tr>'
            '</tbody></table>'
        )
        errors = check(html)
        joined = " ".join(errors)
        assert errors, "Englische Spaltenköpfe (Gust/Rain/Sun) müssen rot melden"
        assert "Gust" in joined and "Sun" in joined, (
            f"Erwartete EN-Begriffe in der Fehlerliste, bekam: {errors}"
        )

    @pytest.mark.xfail(
        reason="#862: _check_localization deliberately removed — superseded by fix-862-849",
        strict=False,
    )
    def test_homograph_wind_not_flagged(self):
        mod = _load_validator()
        check = _require(mod, "_check_localization")
        html = (
            '<table class="resp"><thead><tr><th>Zeit</th><th>Wind</th>'
            '<th>Böen</th></tr></thead><tbody>'
            '<tr><td data-label="Zeit">10:00</td><td>55</td><td>85</td></tr>'
            '</tbody></table>'
        )
        errors = check(html)
        assert errors == [], (
            f"Homograph 'Wind' (DE=EN) darf NICHT als englisch gemeldet werden, "
            f"bekam: {errors}"
        )


# --------------------------------------------------------------------------- #
# AC-3 — Ebenen-Konsistenz: Pills-Spitze ≠ Tabellen-Max (#807-Klasse)
# --------------------------------------------------------------------------- #
class TestAC3LayerConsistency:
    def test_pill_peak_contradicts_table_max(self):
        mod = _load_validator()
        check = _require(mod, "_check_layer_consistency")
        # Pill behauptet Böen-Spitze 84 km/h, Tabelle zeigt max 30 km/h → Δ54.
        html = (
            _overview([_pill("Böen ab 14:00 · 84 km/h")])
            + _table_resp(
                [("10:00", "20"), ("11:00", "30"), ("12:00", "25")],
                col_label="Gust", header_de="Böen",
            )
        )
        errors = check(html)
        assert errors, (
            "Böen-Spitze 84 (Pill) vs. Tabellen-Max 30 muss als Ebenen-Widerspruch "
            "rot melden (#807-Klasse)"
        )
        assert any("84" in e or "Böen" in e or "Ebene" in e for e in errors), (
            f"Fehlermeldung soll den Widerspruch benennen, bekam: {errors}"
        )

    def test_pill_peak_within_tolerance_passes(self):
        mod = _load_validator()
        check = _require(mod, "_check_layer_consistency")
        # Pill 55, Tabellen-Max 55 → identisch, kein Fehler (Rundungs-Toleranz).
        html = (
            _overview([_pill("Böen ab 10:00 · 55 km/h")])
            + _table_resp(
                [("10:00", "55"), ("11:00", "30"), ("12:00", "20")],
                col_label="Gust", header_de="Böen",
            )
        )
        errors = check(html)
        assert errors == [], (
            f"Übereinstimmende Spitzen dürfen NICHT rot melden, bekam: {errors}"
        )


# --------------------------------------------------------------------------- #
# AC-4 — Metrik-Plausibilität gegen die Tabelle (#808-Klasse)
# --------------------------------------------------------------------------- #
class TestAC4MetricPlausibility:
    def test_sonne_pill_contradicts_zero_sun_table(self):
        mod = _load_validator()
        check = _require(mod, "_check_metric_plausibility")
        # Pill „Sonne 120 min" aber Tabelle hat 0.0 h Sonne in jeder Stunde.
        html = (
            _overview([_pill("Sonne 120 min")])
            + _table_resp(
                [("10:00", "0.0 h"), ("11:00", "0.0 h"), ("12:00", "0.0 h")],
                col_label="Sun", header_de="Sonne",
            )
        )
        errors = check(html)
        assert errors, (
            "‚Sonne 120 min' bei 0 h Sonne in der Tabelle muss rot melden (#808-Klasse)"
        )
        assert any("Sonne" in e for e in errors), (
            f"Fehlermeldung soll Sonne benennen, bekam: {errors}"
        )

    def test_kein_regen_pill_contradicts_rain_table(self):
        mod = _load_validator()
        check = _require(mod, "_check_metric_plausibility")
        # Pill „kein Regen" aber Tabelle summiert 0.5 mm.
        html = (
            _overview([_pill("kein Regen")])
            + _table_resp(
                [("10:00", "0.3"), ("11:00", "0.2"), ("12:00", "0.0")],
                col_label="Rain", header_de="Regen",
            )
        )
        errors = check(html)
        assert errors, (
            "‚kein Regen' bei 0.5 mm Niederschlagssumme muss rot melden"
        )

    def test_sonne_pill_matches_table_passes(self):
        mod = _load_validator()
        check = _require(mod, "_check_metric_plausibility")
        # Pill „Sonne 120 min" == 2.0 h Sonne in der Tabelle (1.0 + 1.0).
        html = (
            _overview([_pill("Sonne 120 min")])
            + _table_resp(
                [("10:00", "1.0 h"), ("11:00", "1.0 h"), ("12:00", "0.0 h")],
                col_label="Sun", header_de="Sonne",
            )
        )
        errors = check(html)
        assert errors == [], (
            f"Übereinstimmende Sonne-Angabe darf NICHT rot melden, bekam: {errors}"
        )


# --------------------------------------------------------------------------- #
# AC-1 — Render statt String: Mobile-Viewport-Block fehlt (über validate_message)
# --------------------------------------------------------------------------- #
class TestAC1RenderViewport:
    def test_missing_mobile_block_rejected(self):
        """Eine full-Mail OHNE `.mobile-compact`-Block muss rot werden — bei ≤390px
        ist die Desktop-Tabelle per @media versteckt und nichts bliebe sichtbar.
        Heute (nur String-Prüfung) rutscht das durch → RED."""
        mod = _load_validator()
        # Nur Desktop-Block, KEIN .mobile-compact — der Defekt.
        html = (
            '<style>@media (max-width:600px){.desktop-only{display:none}}</style>'
            '<div class="desktop-only">' + _CLEAN_TABLE + '</div>'
        )
        msg = _build_full(html)
        ok, errors = mod.validate_message(msg)
        assert ok is False, (
            "full-Mail ohne Mobile-Viewport-Block muss das Gate rot machen (AC-1)"
        )
        assert any(
            "mobile" in e.lower() or "viewport" in e.lower() or "390" in e
            for e in errors
        ), f"Fehlermeldung soll den fehlenden Mobile-Viewport benennen, bekam: {errors}"

    def test_dual_render_desktop_visible_on_mobile_rejected(self):
        """F001: Beide Blöcke vorhanden, aber OHNE jede @media-Regel → bei 390px
        ist `.desktop-only` (mit der breiten Desktop-Tabelle) weiter sichtbar.
        Das ist die #794-Klasse: Desktop-Tabelle aufs Handy, mobil unlesbar.
        Die bloße String-Präsenz beider Blöcke täuscht ‚responsiv' vor; erst der
        echte Render bei 390px deckt auf, dass der falsche Block sichtbar bleibt."""
        mod = _load_validator()
        # KEINE @media-Regel → kein Viewport-Switch. Beide Blöcke immer sichtbar.
        html = (
            '<div class="desktop-only">' + _CLEAN_TABLE + '</div>'
            '<div class="mobile-compact"><pre>Zeit Böen\n10   55\n11   30</pre></div>'
        )
        msg = _build_full(html)
        ok, errors = mod.validate_message(msg)
        assert ok is False, (
            "Dual-Render (Desktop-Block bei 390px sichtbar, kein @media-Switch) "
            "muss das Gate rot machen (F001/#794-Klasse)"
        )
        joined = " ".join(errors).lower()
        assert "desktop" in joined and "390" in joined and "versteckt" in joined, (
            f"Fehler soll ‚desktop'/‚390'/‚versteckt' benennen, bekam: {errors}"
        )

    def test_render_unavailable_when_playwright_missing(self):
        """F002: Fehlt Playwright beim Import, muss `_check_rendered` mit
        RenderUnavailable abbrechen (Exit 2, NICHT Exit 1) — mock-frei via
        Subprozess mit vorangestelltem Stub-`playwright`, das ImportError wirft."""
        import os
        import subprocess
        import sys
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d) / "playwright"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "sync_api.py").write_text(
                "raise ImportError('stub: playwright unavailable')\n"
            )
            code = (
                "import importlib.util as u;"
                f"s=u.spec_from_file_location('bmv', r'{VALIDATOR_PATH}');"
                "m=u.module_from_spec(s);s.loader.exec_module(m);"
                "import sys\n"
                "try:\n"
                "    m._check_rendered('<html><body>x</body></html>')\n"
                "    print('NO_RAISE')\n"
                "except m.RenderUnavailable as e:\n"
                "    print('RENDER_UNAVAILABLE:' + str(e))\n"
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = d + os.pathsep + env.get("PYTHONPATH", "")
            res = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
            )
        out = res.stdout + res.stderr
        assert "RENDER_UNAVAILABLE:" in out, (
            f"Fehlendes Playwright muss RenderUnavailable auslösen, bekam: {out!r}"
        )
        assert "playwright" in out.lower(), (
            f"Meldung soll ‚Playwright' benennen, bekam: {out!r}"
        )


# --------------------------------------------------------------------------- #
# AC-6 — Selbsttest: konstruierte defekte Mails → validate_message liefert Exit-1
# --------------------------------------------------------------------------- #
_MOBILE_OK = (
    '<style>@media (max-width:600px){.desktop-only{display:none}'
    '.mobile-compact{display:block}}</style>'
    '<div class="mobile-compact"><pre>Zeit Böen\n10   55\n11   30</pre></div>'
)


def _defect_en_header() -> email.message.Message:
    html = _MOBILE_OK + '<div class="desktop-only">' + _table_resp(
        [("10:00", "85"), ("11:00", "40")], col_label="Gust", header_de="Gust"
    ) + '</div>'
    return _build_full(html)


def _defect_sonne() -> email.message.Message:
    html = _MOBILE_OK + '<div class="desktop-only">' + _overview(
        [_pill("Sonne 180 min")]
    ) + _table_resp(
        [("10:00", "0.0 h"), ("11:00", "0.0 h")], col_label="Sun", header_de="Sonne"
    ) + '</div>'
    return _build_full(html)


def _defect_layer() -> email.message.Message:
    html = _MOBILE_OK + '<div class="desktop-only">' + _overview(
        [_pill("Böen ab 14:00 · 95 km/h")]
    ) + _table_resp(
        [("10:00", "30"), ("11:00", "28")], col_label="Gust", header_de="Böen"
    ) + '</div>'
    return _build_full(html)


def _defect_kein_regen() -> email.message.Message:
    html = _MOBILE_OK + '<div class="desktop-only">' + _overview(
        [_pill("kein Regen")]
    ) + _table_resp(
        [("10:00", "0.4"), ("11:00", "0.3")], col_label="Rain", header_de="Regen"
    ) + '</div>'
    return _build_full(html)


class TestAC6GateSelfVerification:
    @pytest.mark.parametrize(
        "builder, label",
        [
            (_defect_en_header, "englischer Spaltenkopf Gust"),
            (_defect_sonne, "Sonne 180 min bei 0 h Tabelle"),
            (_defect_layer, "Böen 95 (Pill) vs. 30 (Tabelle)"),
            (_defect_kein_regen, "kein Regen bei 0.7 mm Tabelle"),
        ],
    )
    def test_deliberately_broken_mail_is_rejected(self, builder, label):
        """Jede bewusst defekte Mail muss das erweiterte Gate rot melden — sonst
        ist das Gate selbst unverifiziert (kein Mock, echtes MIME-Artefakt)."""
        mod = _load_validator()
        ok, errors = mod.validate_message(builder())
        assert ok is False, (
            f"Defekt ‚{label}' muss das Gate rot machen (Exit-1), wurde aber "
            f"durchgelassen. Fehlerliste: {errors}"
        )
        assert errors, f"Defekt ‚{label}': nicht-leere Fehlerliste erwartet"
