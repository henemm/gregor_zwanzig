"""Official-Alert-Mail-Validator + Gate-Routing (Issue #1197 Luecke).

`renderer_mail_gate.py` routet Aenderungen an `src/output/renderers/alert/*.py`
bislang AUSSCHLIESSLICH an `radar_alert_mail_validator.py` -- der prueft aber
nur `X-GZ-Mail-Type: radar-alert`. Die Standalone-Amtliche-Warnung-Mail
(`official_alerts.py::render_official_alert_html`, Typ `official-alert`,
notification_service.py:530/640) war dadurch strukturell NIE legitim
erfuellbar (Gate-Erosion). Dieses Modul deckt den neuen
`official_alert_mail_validator.py` UND das korrigierte Gate-Routing ab.

Mock-frei: echte `email.message.Message`-Objekte, gebaut ueber die echte
`build_mime_message()`-Pipeline mit echt gerendertem HTML aus
`render_warn_block(variant="standalone", ...)` -- byte-identisch zu dem, was
`EmailOutput.send()` tatsaechlich verschickt. Gate-Routing-Tests: echtes
Temp-Git-Repo + Subprozess-Aufruf des Gate-Hooks (Vorbild:
test_issue_811_renderer_gate.py / test_issue_830_radar_alert_validator.py).
"""
from __future__ import annotations

# Plugin-Sonde (#1196, Vorbild test_issue_811_renderer_gate.py): die Hooks
# dieser Suite laufen ueber hook_utils, einen Shim auf das installierte
# agent-os-openspec-Plugin. Ohne Plugin (CI-Runner, Web-Sessions) sauber
# ueberspringen statt rot — auf dem Server (Plugin vorhanden) laeuft alles.
import importlib.util as _gz_ilu
from pathlib import Path as _GzPath

import pytest as _gz_pytest

_gz_hook_utils = _GzPath(__file__).resolve().parents[2] / ".claude" / "hooks" / "hook_utils.py"
try:
    _gz_spec = _gz_ilu.spec_from_file_location("_gz_hook_utils_probe", _gz_hook_utils)
    _gz_mod = _gz_ilu.module_from_spec(_gz_spec)
    _gz_spec.loader.exec_module(_gz_mod)
except ImportError as _gz_exc:
    _gz_pytest.skip(
        f"agent-os-openspec-Plugin fehlt ({_gz_exc}) — Hook-Suite braucht die "
        "installierten Server-Hooks (#1196)",
        allow_module_level=True,
    )

import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
VALIDATOR_PATH = HOOKS_DIR / "official_alert_mail_validator.py"
GATE_PATH = HOOKS_DIR / "renderer_mail_gate.py"

SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

UTC = timezone.utc


def _load_validator_module():
    if not VALIDATOR_PATH.exists():
        pytest.fail(f"Validator-Datei nicht gefunden: {VALIDATOR_PATH}")
    spec = importlib.util.spec_from_file_location("official_alert_mail_validator", VALIDATOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _alert(level, hazard, label, vf, vt, region="Hermagor-Pressegger See"):
    from services.official_alerts.models import OfficialAlert
    return OfficialAlert(
        source="geosphere_warn", hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region,
    )


def _notice(alert, scope_label, sms_scope, affected_chips, free_chips):
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=affected_chips, free_chips=free_chips,
    )


def _hitze_notices() -> list:
    """Eine Standalone-Warnung (uniforme Stufe) -- Vorlage fuer BEIDE Teile
    derselben Mail."""
    vf = datetime(2026, 7, 12, 6, 0, tzinfo=UTC)
    vt = datetime(2026, 7, 12, 20, 0, tzinfo=UTC)
    return [_notice(
        _alert(2, "extreme_heat", "Hitzewarnung", vf, vt),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )]


def _render_official_alert_html() -> str:
    """Ein echt gerenderter Standalone-Alert-Body (uniforme Stufe)."""
    from output.renderers.alert.official_alerts import render_warn_block

    return render_warn_block(
        _hitze_notices(), variant="standalone", source_label="GeoSphere Austria",
        stand_at="09:30", tz=UTC,
    )


def _render_official_alert_plain() -> str:
    """Der Klartext-Teil DERSELBEN Mail (Issue #1744 A2, AC-13).

    Seit A2 baut ihn der Renderer selbst und `send_official_alert` uebergibt
    ihn ausdruecklich -- vorher entstand er per Tag-Strippen aus dem HTML. Der
    Waechter prueft seine Textregeln bevorzugt gegen den Klartext
    (`plain or html`); ein Pruefstand ohne Klartext-Teil legte ihm also einen
    Zustand vor, den der Versandweg gar nicht mehr erzeugt."""
    from output.renderers.alert.official_alerts import render_official_alert_mail_plain

    return render_official_alert_mail_plain(
        _hitze_notices(), source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )


def _build_real_official_alert_message(html_body: str, plain_body: str | None = None):
    """Baut die Mail EXAKT ueber die Produktions-Pipeline (build_mime_message),
    mail_type=official-alert -- byte-identisch zum echten Versandweg, inklusive
    des seit #1744 A2 mitgelieferten Klartext-Teils."""
    from output.channels.email import build_mime_message

    return build_mime_message(
        subject="[GR20] Amtliche Warnung — Hitze",
        body=html_body,
        from_addr="gregor_zwanzig@henemm.com",
        to_header="gregor-test@henemm.com",
        reply_to=None,
        html=True,
        plain_text_body=plain_body,
        mail_type="official-alert",
    )


# ---------------------------------------------------------------------------
# Validator: Datei existiert + ist ladbar
# ---------------------------------------------------------------------------

def test_validator_file_exists():
    assert VALIDATOR_PATH.exists(), (
        f"official_alert_mail_validator.py nicht gefunden: {VALIDATOR_PATH}"
    )


def test_validator_exports_validate_message():
    mod = _load_validator_module()
    assert hasattr(mod, "validate_message"), (
        "validate_message-Funktion fehlt im Validator-Modul"
    )


# ---------------------------------------------------------------------------
# Kernfall 1: valide official-alert-Mail -> True
# ---------------------------------------------------------------------------

def test_valid_official_alert_mail_passes():
    mod = _load_validator_module()
    msg = _build_real_official_alert_message(
        _render_official_alert_html(), _render_official_alert_plain(),
    )

    ok, errors = mod.validate_message(msg)
    assert ok is True, (
        f"Echt gerenderte official-alert-Mail sollte Checks bestehen, "
        f"aber errors={errors}"
    )


# ---------------------------------------------------------------------------
# Kernfall 2: falscher Mail-Typ -> No-Op True mit Info
# ---------------------------------------------------------------------------

def test_wrong_mail_type_is_clean_noop():
    mod = _load_validator_module()
    msg = _build_real_official_alert_message(_render_official_alert_html())
    # X-GZ-Mail-Type auf einen anderen Typ umschreiben.
    del msg["X-GZ-Mail-Type"]
    msg["X-GZ-Mail-Type"] = "trip-briefing"

    ok, errors = mod.validate_message(msg)
    assert ok is True, (
        f"Falscher Mail-Typ sollte No-Op sein (ok=True), aber ok={ok}, errors={errors}"
    )
    assert errors and "trip-briefing" in errors[0], (
        f"No-Op-Info sollte den fremden Mail-Typ nennen: {errors}"
    )


# ---------------------------------------------------------------------------
# Kernfall 3: kaputter/leerer Body -> False
# ---------------------------------------------------------------------------

def test_broken_body_fails():
    from email.mime.text import MIMEText

    mod = _load_validator_module()
    msg = MIMEText("Fehler beim Rendern — leerer Body.", "plain", "utf-8")
    msg["Subject"] = "[GR20] Amtliche Warnung"
    msg["X-GZ-Mail-Type"] = "official-alert"

    ok, errors = mod.validate_message(msg)
    assert ok is False, (
        f"Body ohne Verdict/Warnstufe/Quelle-Struktur sollte scheitern, aber ok={ok}"
    )
    assert errors, "Fehlerliste sollte nicht leer sein"


def test_empty_body_fails():
    from email.mime.text import MIMEText

    mod = _load_validator_module()
    msg = MIMEText("", "plain", "utf-8")
    msg["Subject"] = "[GR20] Amtliche Warnung"
    msg["X-GZ-Mail-Type"] = "official-alert"

    ok, errors = mod.validate_message(msg)
    assert ok is False


# ---------------------------------------------------------------------------
# P-3 (Issue #1240): Gueltigkeit wird auf INHALT geprueft, nicht auf Anwesenheit
# ---------------------------------------------------------------------------

def _untimed_notices() -> list:
    """Eine Warnung OHNE Zeitangabe -- genau das, was `massif_closure`/
    `meteo_forets` liefern (kein valid_from/valid_to)."""
    from services.official_alerts.models import OfficialAlert

    return [_notice(
        OfficialAlert(
            source="massif_closure", hazard="access_ban", level=4,
            label="Zugang gesperrt — Maures", dedup_id="maures",
        ),
        scope_label="nur Collobrières", sms_scope="nurCollobrieres",
        affected_chips=["Collobrières"], free_chips=[],
    )]


_UNTIMED_KWARGS = dict(source_label="Präfektur (Zugangssperre)", stand_at="02:00", tz=UTC)


def _render_untimed_official_alert_html() -> str:
    """Echt gerenderter Standalone-Body fuer eine Warnung OHNE Zeitangabe.
    Seit #1238 (E4/AC-7) laesst der Renderer die 'Gueltig:'-Zeile hier komplett
    weg, statt 'unbekannt' zu schreiben."""
    from output.renderers.alert.official_alerts import render_warn_block

    return render_warn_block(_untimed_notices(), variant="standalone", **_UNTIMED_KWARGS)


def _render_untimed_official_alert_plain() -> str:
    """Der Klartext-Teil derselben zeitlosen Mail (#1744 A2, AC-13)."""
    from output.renderers.alert.official_alerts import render_official_alert_mail_plain

    return render_official_alert_mail_plain(_untimed_notices(), **_UNTIMED_KWARGS)


def _mail_with_unknown_validity():
    """Mail einer zeitlosen Warnung MIT wieder eingesetzter Platzhalter-Zeile
    'Gültig: unbekannt' — also genau der Renderer-Regress, den P-3 abfangen
    soll. Seit #1238 erzeugt der echte Renderer diesen Zustand nicht mehr
    (AC-7), die VALIDATOR-Regel muss ihn aber weiter zurueckweisen: der Pruefer
    sieht nur den Mail-Text und darf einen Platzhalter nie als Zeitangabe
    durchwinken.

    #1744 A2: der Platzhalter wird in BEIDE Teile gesetzt. Der Waechter liest
    bevorzugt den Klartext (`plain or html`); ein Regress im Renderer schluege
    ohnehin auf beide Teile durch, weil sie aus denselben `(Label, Wert)`-
    Tupeln entstehen. Nur im HTML zu faelschen, hiesse den Pruefer an einer
    Stelle zu testen, die er gar nicht liest."""
    html_body = _render_untimed_official_alert_html()
    plain_body = _render_untimed_official_alert_plain()
    assert "Gültig:" not in html_body and "Gültig:" not in plain_body, (
        "Renderer schreibt wieder eine 'Gültig:'-Zeile bei fehlenden Zeiten (AC-7)"
    )
    placeholder = (
        '<span class="k">Gültig:</span> <span class="mono">unbekannt</span><br>'
    )
    injected = html_body.replace('<div class="facts"', placeholder + '<div class="facts"', 1)
    assert placeholder in injected, "Testaufbau: Platzhalter-Zeile nicht eingesetzt"
    return _build_real_official_alert_message(
        injected, "Gültig: unbekannt\n" + plain_body,
    )


def test_validity_unknown_is_rejected():
    """'Gueltig: unbekannt' ist keine Zeitangabe -- der Pruefer muss die Mail
    zurueckweisen, statt sie (wie bisher) durchzuwinken."""
    mod = _load_validator_module()
    msg = _mail_with_unknown_validity()

    ok, errors = mod.validate_message(msg)
    assert ok is False, (
        "Mail mit 'Gültig: unbekannt' muss an P-3 scheitern (leere Zeitangabe), "
        f"wurde aber akzeptiert. errors={errors}"
    )
    assert any("P-3" in e for e in errors), f"Erwartet P-3-Befund, bekam: {errors}"


def test_missing_validity_line_is_accepted():
    """Warnungen ohne Zeitangabe tragen kuenftig GAR KEINE 'Gueltig:'-Zeile
    (PO-Entscheidung #1238). Der Pruefer darf so eine Mail nicht blockieren --
    die Anwesenheit der Zeile ist kein taugliches Kriterium (der Pruefer sieht
    nur den Text und kann 'Renderer hat's vergessen' nicht von 'Quelle liefert
    keine Zeiten' unterscheiden)."""
    import re as _re

    mod = _load_validator_module()
    html_body = _render_untimed_official_alert_html()
    # Vorwegnahme des kuenftigen Renderer-Verhaltens (#1238 E4): Gueltig-Zeile faellt weg.
    without_validity = _re.sub(
        r'<span class="k"[^>]*>Gültig:</span>.*?<br>', "", html_body, flags=_re.S,
    )
    assert "Gültig:" not in without_validity, "Testaufbau: Gültig-Zeile nicht entfernt"

    msg = _build_real_official_alert_message(
        without_validity, _render_untimed_official_alert_plain(),
    )
    ok, errors = mod.validate_message(msg)
    assert ok is True, (
        "Mail ohne 'Gültig:'-Zeile ist bei zeitlosen Warnungen korrekt und darf "
        f"nicht blockiert werden. errors={errors}"
    )


def test_valid_timed_validity_still_passes():
    """Non-Regression: eine Warnung MIT Zeitraum behaelt ihre 'Gueltig:'-Zeile
    und besteht weiterhin."""
    mod = _load_validator_module()
    msg = _build_real_official_alert_message(
        _render_official_alert_html(), _render_official_alert_plain(),
    )

    ok, errors = mod.validate_message(msg)
    assert ok is True, f"Mail mit echtem Zeitraum muss bestehen, errors={errors}"


# ---------------------------------------------------------------------------
# Gate-Routing: official_alerts.py -> official-Validator (nicht radar);
# render.py (Radar-Renderer) -> radar-Validator (nicht official).
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


_WF_NAME = "fix-1197-official-alert-mail-validator"


def _setup_repo(tmp_path: Path) -> Path:
    import shutil

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(GATE_PATH, hooks / "renderer_mail_gate.py")
    for helper in ("config_loader.py", "workflow.py", "workflow_state_multi.py", "hook_utils.py"):
        src = HOOKS_DIR / helper
        if src.exists():
            shutil.copy(src, hooks / helper)

    (repo / ".claude" / "workflows" / "_log").mkdir(parents=True)

    alert_dir = repo / "src" / "output" / "renderers" / "alert"
    alert_dir.mkdir(parents=True)
    (alert_dir / "official_alerts.py").write_text("# official alert renderer initial\n")
    (alert_dir / "render.py").write_text("# radar/deviation renderer initial\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _run_gate(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["OPENSPEC_ACTIVE_WORKFLOW"] = _WF_NAME
    env["GZ_ACTIVE_WORKFLOW"] = _WF_NAME
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "renderer_mail_gate.py"), *args],
        cwd=repo, input=stdin, capture_output=True, text=True, env=env,
    )


def _commit_stdin() -> str:
    return json.dumps({"tool_input": {"command": "git commit -m wip"}})


def _write_official_alert_log(repo: Path, *, passed: bool = True, validated_at=None) -> Path:
    now = validated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    log_dir = repo / ".claude" / "workflows" / "_log"
    ts = now.strftime("%Y%m%d_%H%M%S")
    p = log_dir / f"{ts}_{_WF_NAME}_official_alert_validation.yaml"
    p.write_text(
        "validator: official_alert_mail_validator\n"
        f"validated_at: '{now.isoformat()}'\n"
        f"workflow_id: '{_WF_NAME}'\n"
        f"passed: {str(passed).lower()}\n"
        "error_count: 0\n"
    )
    return p


def _write_radar_alert_log(repo: Path, *, passed: bool = True, validated_at=None) -> Path:
    now = validated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    log_dir = repo / ".claude" / "workflows" / "_log"
    ts = now.strftime("%Y%m%d_%H%M%S")
    p = log_dir / f"{ts}_{_WF_NAME}_radar_alert_validation.yaml"
    p.write_text(
        "validator: radar_alert_mail_validator\n"
        f"validated_at: '{now.isoformat()}'\n"
        f"workflow_id: '{_WF_NAME}'\n"
        f"passed: {str(passed).lower()}\n"
        "error_count: 0\n"
    )
    return p


def _write_workflow_state(repo: Path) -> Path:
    state = {"name": _WF_NAME, "phase": "phase6", "issue": 1197, "gates": {}}
    p = repo / ".claude" / "workflows" / f"{_WF_NAME}.json"
    p.write_text(json.dumps(state))
    return p


def test_official_alerts_py_blocked_without_official_nachweis(tmp_path):
    """official_alerts.py gestaged, KEIN official-alert-Validator-Log -> Exit 2."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo)
    official_path = repo / "src" / "output" / "renderers" / "alert" / "official_alerts.py"
    official_path.write_text("# changed\n")
    _git(repo, "add", "src/output/renderers/alert/official_alerts.py")

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 2, (
        f"official_alerts.py ohne official-alert-Validator-Nachweis muss blockieren. "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )
    assert "official_alert_mail_validator.py" in res.stderr, (
        f"Blockierung soll den official-Validator nennen: {res.stderr!r}"
    )


def test_official_alerts_py_passes_with_official_nachweis_alone(tmp_path):
    """official_alerts.py gestaged + official-alert-Log (frisch, passed) -> Exit 0
    OHNE dass ein radar_alert_validation.yaml noetig ist (kein Doppel-Zwang)."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo)
    official_path = repo / "src" / "output" / "renderers" / "alert" / "official_alerts.py"
    official_path.write_text("# changed\n")
    _git(repo, "add", "src/output/renderers/alert/official_alerts.py")

    mtime = official_path.stat().st_mtime
    fresh = datetime.fromtimestamp(mtime + 2.0, tz=timezone.utc)
    _write_official_alert_log(repo, passed=True, validated_at=fresh)

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 0, (
        f"official_alerts.py MIT frischem official-alert-Nachweis muss passieren "
        f"(kein radar-Log noetig). rc={res.returncode} stderr={res.stderr!r}"
    )


def test_render_py_still_requires_radar_nachweis_not_official(tmp_path):
    """render.py (Radar-/Deviation-Renderer) gestaged -> weiterhin radar-Validator
    erforderlich, NICHT der official-Validator (Routing bleibt praezise)."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo)
    render_path = repo / "src" / "output" / "renderers" / "alert" / "render.py"
    render_path.write_text("# changed radar renderer\n")
    _git(repo, "add", "src/output/renderers/alert/render.py")

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 2, "render.py ohne Nachweis muss weiterhin blockieren"
    assert "radar_alert_mail_validator.py" in res.stderr, (
        f"Blockierung soll den radar-Validator nennen: {res.stderr!r}"
    )
    assert "official_alert_mail_validator.py" not in res.stderr, (
        "render.py darf NICHT den official-Validator verlangen (falsches Routing): "
        f"{res.stderr!r}"
    )

    mtime = render_path.stat().st_mtime
    fresh = datetime.fromtimestamp(mtime + 2.0, tz=timezone.utc)
    _write_radar_alert_log(repo, passed=True, validated_at=fresh)

    res2 = _run_gate(repo, stdin=_commit_stdin())
    assert res2.returncode == 0, (
        f"render.py MIT radar-Nachweis (ohne official-Log) muss passieren. "
        f"rc={res2.returncode} stderr={res2.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Issue #1441 (Spec avalanche_report_bulletin.md Abschnitt 7, ADR-0089):
# Lawinen-Lagebericht -- Stufe als Wortlaut "Lawinenstufe N (<EAWS-Wort>)",
# keine Leiter/Farbwoerter. Mails kommen ueber den ECHTEN Versandpfad
# `NotificationService.send_official_alert` inkl. `EmailOutput.send` und
# MIME-Bau; ersetzt ist nur der SMTP-Rand `_dial_and_send`. Verfaelschungen
# ausschliesslich per String-Ersetzung im zugestellten HTML/Klartext.
# ---------------------------------------------------------------------------

_AVALANCHE_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "avalanche_report" / "bulletins"
    / "2026-02-20_AT-07_de_CAAMLv6.json"
)


def _avalanche_stufe4():
    """Echter Parser auf das aufgezeichnete Bulletin, Quelle wie im Produktivpfad."""
    from services.official_alerts.avalanche_report import parse_region_alert

    doc = json.loads(_AVALANCHE_FIXTURE.read_text(encoding="utf-8"))
    return parse_region_alert(doc, "AT-07-25", source="avalanche_report:AT-07")


def _gewitter_alert(label: str = "Gewitterwarnung"):
    """Default-Label wie im aufgezeichneten MeteoAlarm-Feed (`"event":"Gewitterwarnung"`);
    GeoSphere liefert das kurze Typ-Wort "Gewitter" (geosphere_warn.py `_HAZARD_MAP`)."""
    return _alert(
        2, "thunderstorm", label,
        datetime(2026, 2, 20, 12, 0, tzinfo=UTC), datetime(2026, 2, 20, 20, 0, tzinfo=UTC),
        region="Stubai",
    )


def _zugestellte_mail(monkeypatch, alerts: list, trip_name: str = "Stubai"):
    """Versendet `alerts` ueber den echten Trip-Warnpfad und liefert
    (Message, HTML-Teil, Klartext-Teil) der zugestellten Mail."""
    from datetime import date

    from app.config import Settings
    from app.trip import Stage, Trip, Waypoint
    from output.channels.email import EmailOutput
    from services.notification_service import NotificationService

    erfasst = []
    monkeypatch.setattr(EmailOutput, "_dial_and_send",
                        lambda self, *a, **kw: erfasst.append(kw.get("msg") if "msg" in kw else a[5]))
    settings = Settings(smtp_host="smtp.test.invalid", smtp_user="t@test.invalid", smtp_pass="x",
                        mail_to="to@test.invalid")
    waypoints = [Waypoint(id=f"w{i}", name=f"P{i}", lat=47.0 + i * 0.01, lon=11.0 + i * 0.01,
                          elevation_m=2000.0) for i in range(3)]
    trip = Trip(id="t-1441-validator", name=trip_name,
                stages=[Stage(id="s1", name="Tag 1", date=date(2026, 2, 20), waypoints=waypoints)])

    NotificationService(settings, "t-1441-validator").send_official_alert(
        trip=trip, notices=[(a, ["1"]) for a in alerts], effective_channels={"email"},
        sms_sink=lambda text: None,
    )

    assert len(erfasst) == 1 and erfasst[0].get("X-GZ-Mail-Type") == "official-alert"
    teile = {p.get_content_type(): p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8")
             for p in erfasst[0].walk() if p.get_content_type() in ("text/html", "text/plain")}
    return erfasst[0], teile["text/html"], teile["text/plain"]


_STUFE4_ECHT = "Lawinenstufe 4 (groß)"
_STUFE4_FALSCH = "Lawinenstufe 5 (groß)"


def test_avalanche_only_mail_passes(monkeypatch):
    """Reine Lawinenmail (keine Leiter, keine Farbwoerter) besteht -- S-2/P-2
    sind nur fuer sie gelockert."""
    mod = _load_validator_module()
    msg, html, plain = _zugestellte_mail(monkeypatch, [_avalanche_stufe4()])
    assert _STUFE4_ECHT in html and _STUFE4_ECHT in plain, "Testaufbau: Stufen-Wortlaut fehlt"
    assert "stufe-line" not in html, "Testaufbau: reine Lawinenmail traegt eine Leiter"

    ok, errors = mod.validate_message(msg)
    assert ok is True, f"Echt gerenderte reine Lawinenmail muss bestehen, errors={errors}"


def test_avalanche_wrong_eaws_word_only_in_html_fails(monkeypatch):
    """F013: Ziffer 5 mit Wort 'groß' NUR im HTML-Teil -- der Klartext ist
    korrekt, der Pruefer muss den HTML-Teil trotzdem lesen (P-2b)."""
    mod = _load_validator_module()
    _msg, html, plain = _zugestellte_mail(monkeypatch, [_avalanche_stufe4()])
    html_falsch = html.replace(_STUFE4_ECHT, _STUFE4_FALSCH)
    assert html_falsch != html and _STUFE4_FALSCH not in plain, "Testaufbau: Verfaelschung"

    ok, errors = mod.validate_message(_build_real_official_alert_message(html_falsch, plain))
    assert ok is False, f"'Lawinenstufe 5 (groß)' im HTML muss fallen, errors={errors}"
    assert any(e.startswith("P-2b") for e in errors), f"Erwartet P-2b-Befund: {errors}"


def test_avalanche_wrong_eaws_word_only_in_plain_fails(monkeypatch):
    """Dasselbe NUR im Klartext-Teil -> P-2b."""
    mod = _load_validator_module()
    _msg, html, plain = _zugestellte_mail(monkeypatch, [_avalanche_stufe4()])
    plain_falsch = plain.replace(_STUFE4_ECHT, _STUFE4_FALSCH)
    assert plain_falsch != plain and _STUFE4_FALSCH not in html, "Testaufbau: Verfaelschung"

    ok, errors = mod.validate_message(_build_real_official_alert_message(html, plain_falsch))
    assert ok is False, f"'Lawinenstufe 5 (groß)' im Klartext muss fallen, errors={errors}"
    assert any(e.startswith("P-2b") for e in errors), f"Erwartet P-2b-Befund: {errors}"


def _ohne_farbwoerter(text: str) -> str:
    for wort in ("GELB", "ORANGE", "ROT"):
        text = text.replace(wort, "")
    return text


@pytest.mark.parametrize("label", [
    "Gewitter",         # GeoSphere-Label (geosphere_warn.py _HAZARD_MAP)
    "Gewitterwarnung",  # MeteoAlarm-Label, so aufgezeichnet in tests/fixtures
])
def test_thunderstorm_mail_without_ladder_but_avalanche_text_fails(monkeypatch, label):
    """F012: eine Gewittermail, deren Leiter und Farbwoerter verloren gehen,
    darf sich nicht durch angehaengten Lawinen-Wortlaut in die Lockerung fuer
    reine Lawinenmails retten -- S-2 bleibt strikt. Fuer BEIDE realen
    Label-Formen: der Renderer zeigt das zusammengesetzte Quell-Label
    ("Gewitterwarnung") unveraendert an (`_display_label`)."""
    mod = _load_validator_module()
    _msg, html, plain = _zugestellte_mail(monkeypatch, [_gewitter_alert(label)])
    assert 'class="stufe-line"' in html, "Testaufbau: Gewittermail ohne Leiter gerendert"
    lawine = f"{_STUFE4_ECHT} oberhalb Waldgrenze · Lawinenwarndienst Tirol, avalanche.report"

    html_kaputt = _ohne_farbwoerter(html.replace('class="stufe-line"', 'class="x"'))
    html_kaputt = html_kaputt.replace("</body>", f"<p>{lawine}</p></body>", 1)
    plain_kaputt = _ohne_farbwoerter(plain) + "\n" + lawine + "\n"
    assert "stufe-line" not in html_kaputt and lawine in html_kaputt, "Testaufbau: Verfaelschung"
    assert not any(w in plain_kaputt for w in ("GELB", "ORANGE", "ROT")), "Testaufbau: Farbwort"

    ok, errors = mod.validate_message(_build_real_official_alert_message(html_kaputt, plain_kaputt))
    assert ok is False, f"Gewittermail ohne Leiter muss fallen, errors={errors}"
    assert any(e.startswith("S-2") for e in errors), f"Erwartet S-2-Befund: {errors}"


def test_mixed_thunderstorm_and_avalanche_mail_passes(monkeypatch):
    """Gemischte Mail (Gewitter + Lawine) traegt das Eskalations-Meter und besteht."""
    mod = _load_validator_module()
    msg, html, _plain = _zugestellte_mail(monkeypatch, [_gewitter_alert(), _avalanche_stufe4()])
    assert _STUFE4_ECHT in html and "Gewitter" in html, "Testaufbau: keine gemischte Mail"

    ok, errors = mod.validate_message(msg)
    assert ok is True, f"Gemischte Mail muss bestehen, errors={errors}"


def test_mixed_mail_without_meter_or_ladder_fails(monkeypatch):
    """Gemischte Mail ohne Meter/Leiter faellt -- die Lawinen-Lockerung gilt
    nur fuer reine Lawinenmails."""
    mod = _load_validator_module()
    _msg, html, plain = _zugestellte_mail(monkeypatch, [_gewitter_alert(), _avalanche_stufe4()])
    assert 'class="warn stacked"' in html and 'class="meter ' in html, "Testaufbau: kein Meter"
    html_kaputt = (html.replace('class="warn stacked"', 'class="warn"')
                   .replace('class="meter ', 'class="x ')
                   .replace('class="stufe-line"', 'class="x"'))

    ok, errors = mod.validate_message(_build_real_official_alert_message(html_kaputt, plain))
    assert ok is False, f"Gemischte Mail ohne Meter/Leiter muss fallen, errors={errors}"
    assert any(e.startswith("S-2") for e in errors), f"Erwartet S-2-Befund: {errors}"


def test_other_hazard_words_mirror_renderer_hazard_labels():
    """Drift-Waechter: `_OTHER_HAZARD_RE` spiegelt genau `_HAZARD_LABELS` ohne
    die Lawinen-Eintraege. Kommt eine Gefahrenart dazu, muss der Pruefer sie
    kennen -- sonst rettet sich deren Mail in die Lawinen-Lockerung (F012)."""
    import re as _re

    from output.renderers.alert.official_alerts import _HAZARD_LABELS

    mod = _load_validator_module()
    gruppe = _re.search(r"\(([^()]*)\)", mod._OTHER_HAZARD_RE.pattern)
    assert gruppe, f"Unerwartete Form von _OTHER_HAZARD_RE: {mod._OTHER_HAZARD_RE.pattern!r}"
    im_pruefer = set(gruppe.group(1).split("|"))
    erwartet = {label for hazard, label in _HAZARD_LABELS.items()
                if hazard not in ("avalanche", "avalanche_bulletin")}

    assert im_pruefer == erwartet, (
        f"Drift: nur im Pruefer {sorted(im_pruefer - erwartet)}, "
        f"nur im Renderer {sorted(erwartet - im_pruefer)}"
    )


# ---------------------------------------------------------------------------
# Issue #1441 Scheibe S3 (Spec feat_1441_s3_slf.md, AC-30): SLF-Lagebericht mit
# amtlicher Feinstufe ("Lawinenstufe 3- (erheblich)") und SLF-Quellenangabe.
# Die Mail entsteht aus dem AUFGEZEICHNETEN SLF-Bulletin (tests/fixtures/slf/,
# Region CH-7231, 2026-03-01 Morgen: erheblich/minus) ueber die echte Quelle
# `SlfSource` und den echten Versandpfad (`_zugestellte_mail`). Verfaelschungen
# ausschliesslich per String-Ersetzung im zugestellten HTML/Klartext.
# ---------------------------------------------------------------------------

_SLF_STUFE = "Lawinenstufe 3- (erheblich)"
_SLF_STUFE_FALSCH = "Lawinenstufe 3- (mäßig)"


def _slf_alert_ch_7231():
    """Echte SLF-Warnung aus dem aufgezeichneten Bulletin (lazy: Pruefling im RED)."""
    from datetime import datetime as _dt

    from tests.helpers.slf_support import (
        WINTER_MORGEN, FakeClock, SlfFixtureTransport, interior_point, make_slf_source,
    )

    quelle = make_slf_source(SlfFixtureTransport(WINTER_MORGEN),
                             FakeClock(_dt(2026, 3, 1, 8, 0, tzinfo=UTC)))
    alerts = quelle.fetch(*interior_point("CH-7231"))
    assert len(alerts) == 1, f"Testaufbau: genau eine SLF-Warnung fuer CH-7231 erwartet: {alerts!r}"
    return alerts[0]


def _slf_mail(monkeypatch):
    from tests.helpers.slf_support import SLF_LABEL

    msg, html, plain = _zugestellte_mail(monkeypatch, [_slf_alert_ch_7231()])
    assert _SLF_STUFE in html and _SLF_STUFE in plain, (
        f"Testaufbau: Feinstufen-Wortlaut '{_SLF_STUFE}' fehlt in der gerenderten SLF-Mail")
    assert SLF_LABEL in plain, "Testaufbau: SLF-Quellenangabe fehlt in der gerenderten Mail"
    return msg, html, plain


def test_ac30_slf_mail_mit_feinstufe_und_slf_quelle_besteht(monkeypatch):
    """AC-30 [Mail-Validator kennt Feinstufe und SLF]
    GIVEN eine aus dem SLF-Bulletin gerenderte Warnungs-Mail mit "Lawinenstufe 3- (erheblich)"
          und der Quelle "WSL-Institut fuer Schnee- und Lawinenforschung SLF" (kein
          avalanche.report im Text)
    WHEN  official_alert_mail_validator.py sie prueft
    THEN  wird sie als reine Lawinenmail erkannt und besteht (ok=True, keine Fehler).
    (Heute faellt eine solche Mail mit S-2/P-2: "3-" passt nicht auf das Stufenmuster, und die
    einzige Quellen-Kennung ist avalanche.report.)"""
    mod = _load_validator_module()
    msg, html, plain = _slf_mail(monkeypatch)
    assert "avalanche.report" not in html + plain, "Testaufbau: SLF-Mail traegt avalanche.report"

    ok, errors = mod.validate_message(msg)
    assert ok is True, f"Echt gerenderte SLF-Lawinenmail mit Feinstufe muss bestehen, errors={errors}"


def test_ac30_slf_mail_mit_feinstufe_und_falschem_eaws_wort_faellt(monkeypatch):
    """AC-30 (Gegenprobe Wort)
    GIVEN dieselbe SLF-Mail, in HTML und Klartext "Lawinenstufe 3- (mäßig)" statt "(erheblich)"
    WHEN  der Validator sie prueft
    THEN  faellt sie mit dem P-2b-Befund (Ziffer und EAWS-Wort passen nicht zusammen) -- nicht
          bloss, weil die Mail gar nicht als Lawinenmail erkannt wird."""
    mod = _load_validator_module()
    _msg, html, plain = _slf_mail(monkeypatch)
    html_falsch = html.replace(_SLF_STUFE, _SLF_STUFE_FALSCH)
    plain_falsch = plain.replace(_SLF_STUFE, _SLF_STUFE_FALSCH)
    assert _SLF_STUFE not in html_falsch + plain_falsch, "Testaufbau: Verfaelschung unvollstaendig"

    ok, errors = mod.validate_message(_build_real_official_alert_message(html_falsch, plain_falsch))
    assert ok is False, f"'{_SLF_STUFE_FALSCH}' muss fallen, errors={errors}"
    assert any(e.startswith("P-2b") for e in errors), f"Erwartet P-2b-Befund: {errors}"


def test_ac30_slf_mail_ohne_quelle_faellt(monkeypatch):
    """AC-30 (Gegenprobe Quelle)
    GIVEN dieselbe SLF-Mail, aus der jede Quellenangabe entfernt ist (Quellen-Datenzeile,
          "abgerufen bei"-Link, Fusszeilen-Label, SLF-Link)
    WHEN  der Validator sie prueft
    THEN  faellt sie mit einem Quellen-Befund (S-1b bzw. P-4)."""
    import re as _re

    from tests.helpers.slf_support import SLF_LABEL

    mod = _load_validator_module()
    _msg, html, plain = _slf_mail(monkeypatch)

    def _ohne_quelle(text: str) -> str:
        text = _re.sub(r"https?://[^\s\"<]*slf\.ch[^\s\"<]*", "", text)
        for traeger in (SLF_LABEL, "Quelle:", "abgerufen bei"):
            text = text.replace(traeger, "")
        return text

    html_ohne, plain_ohne = _ohne_quelle(html), _ohne_quelle(plain)
    assert SLF_LABEL not in html_ohne + plain_ohne and "slf.ch" not in html_ohne + plain_ohne, (
        "Testaufbau: Quellenangabe nicht vollstaendig entfernt")
    assert _SLF_STUFE in plain_ohne, "Testaufbau: Stufen-Wortlaut muss bleiben"

    ok, errors = mod.validate_message(_build_real_official_alert_message(html_ohne, plain_ohne))
    assert ok is False, f"SLF-Mail ohne Quelle muss fallen, errors={errors}"
    assert any(e.startswith(("S-1b", "P-4")) for e in errors), f"Erwartet S-1b/P-4: {errors}"


@pytest.mark.parametrize("trip_name", ["PROBE Sturmtrip", "Hitzeck"])
def test_avalanche_only_mail_passes_despite_hazard_word_in_trip_name(monkeypatch, trip_name):
    """#2560 AC-1/AC-2: ein Typwort im TRIP-NAMEN ("Sturm", "Hitze") darf eine
    echt gerenderte reine Lawinenmail nicht in die strikte S-2-Pruefung kippen."""
    mod = _load_validator_module()
    msg, html, plain = _zugestellte_mail(monkeypatch, [_avalanche_stufe4()], trip_name=trip_name)
    assert trip_name in html and _STUFE4_ECHT in html, "Testaufbau: Name/Stufe fehlt"
    assert "stufe-line" not in html, "Testaufbau: reine Lawinenmail traegt eine Leiter"

    ok, errors = mod.validate_message(msg)
    assert ok is True, f"Lawinenmail von '{trip_name}' muss bestehen, errors={errors}"


def test_thunderstorm_mail_without_ladder_fails_with_hazard_word_trip_name(monkeypatch):
    """#2560 AC-3: Gewittermail ohne Leiter/Farbwoerter + angehaengter Lawinentext
    faellt mit Trip "PROBE Sturmtrip" weiter an S-2 (Namens-Entfernung darf das
    Typwort der Warnkarte nicht mitentfernen)."""
    mod = _load_validator_module()
    msg, html, plain = _zugestellte_mail(monkeypatch, [_gewitter_alert()], trip_name="PROBE Sturmtrip")
    assert 'class="stufe-line"' in html, "Testaufbau: Gewittermail ohne Leiter gerendert"
    lawine = f"{_STUFE4_ECHT} oberhalb Waldgrenze · Lawinenwarndienst Tirol, avalanche.report"

    html_kaputt = _ohne_farbwoerter(html.replace('class="stufe-line"', 'class="x"'))
    html_kaputt = html_kaputt.replace("</body>", f"<p>{lawine}</p></body>", 1)
    plain_kaputt = _ohne_farbwoerter(plain) + "\n" + lawine + "\n"

    # F001: Betreff des echten Trip-Pfads ("[PROBE Sturmtrip] ..."), damit die
    # Namens-Entfernung tatsaechlich greift.
    kaputt = _build_real_official_alert_message(html_kaputt, plain_kaputt)
    kaputt.replace_header("Subject", msg["Subject"])
    assert mod._decoded_subject(kaputt).startswith("[PROBE Sturmtrip]"), "Testaufbau: Betreff"

    ok, errors = mod.validate_message(kaputt)
    assert ok is False, f"Gewittermail ohne Leiter muss fallen, errors={errors}"
    assert any(e.startswith("S-2") for e in errors), f"Erwartet S-2-Befund: {errors}"


def test_thunderstorm_mail_named_like_hazard_keeps_card_label(monkeypatch):
    """#2560 F002: heisst der Trip exakt wie die Gefahrenart ("Gewitter"), darf
    nur der Fusszeilen-Name ("Gewitter · Amtliche Warnung", letzte Fundstelle)
    entfernt werden, nie das Karten-Label "Gewitter · Fr 20.02. · ..." (Badge-
    Format aus `_format_validity`). Gewittermail ohne Leiter/Farbwoerter +
    Lawinentext muss weiter an S-2 fallen."""
    mod = _load_validator_module()
    msg, html, plain = _zugestellte_mail(monkeypatch, [_gewitter_alert("Gewitter")], trip_name="Gewitter")
    assert "Gewitter · Amtliche Warnung" in html and "Gewitter · Amtliche Warnung" in plain, \
        "Testaufbau: Fusszeilen-Name fehlt"
    lawine = f"{_STUFE4_ECHT} oberhalb Waldgrenze · Lawinenwarndienst Tirol, avalanche.report"
    badge = "Gewitter · Fr 20.02. · 13:00–21:00"

    # Das Typ-Wort steht nur noch im Karten-Label (Badge-Format) und im Fuss.
    html_kaputt = _ohne_farbwoerter(html.replace('class="stufe-line"', 'class="x"'))
    html_kaputt = re.sub(r"Gewitter(?! · )", "", html_kaputt)
    html_kaputt = re.sub(r"(<body[^>]*>)", rf"\1<div>{badge}</div>", html_kaputt, count=1)
    html_kaputt = html_kaputt.replace("</body>", f"<p>{lawine}</p></body>", 1)
    plain_kaputt = badge + "\n" + re.sub(r"Gewitter(?! · )", "", _ohne_farbwoerter(plain))
    plain_kaputt += "\n" + lawine + "\n"
    assert html_kaputt.index(badge) < html_kaputt.index("Gewitter · Amtliche Warnung"), \
        "Testaufbau: Karten-Label muss vor dem Fusszeilen-Namen stehen"

    kaputt = _build_real_official_alert_message(html_kaputt, plain_kaputt)
    kaputt.replace_header("Subject", msg["Subject"])
    assert mod._decoded_subject(kaputt).startswith("[Gewitter]"), "Testaufbau: Betreff"

    ok, errors = mod.validate_message(kaputt)
    assert ok is False, f"Gewittermail ohne Leiter muss fallen, errors={errors}"
    assert any(e.startswith("S-2") for e in errors), f"Erwartet S-2-Befund: {errors}"
