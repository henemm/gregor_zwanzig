"""Der Warn-Mail-Waechter und die aufgeloeste Quelle-Box (#1744 A2, AC-14).

SPEC: docs/specs/modules/fix_1744_alarm_format_angleichen.md
      („Der Waechter prueft CSS-Klassen, nicht nur Text")

`.claude/hooks/official_alert_mail_validator.py` verlangte in S-1 die CSS-Klasse
`src` — die Quelle-Box. Der A2-Umbau loest sie auf: die Quelle ist eine
Datenzeile wie Gefahrenart, Gueltigkeit und Ortsbezug. Ein Waechter, der
gueltige Formen aufzaehlt, lehnt jede neue ab (dieselbe Falle wie in A1, wo
`_SEGMENT_RE` `🏁 Ziel` nicht kannte). Behandlung wie damals: **additiv
erweitern, nie lockern** — `src` bleibt gueltig, die Datenzeilen-Form kommt
hinzu, und eine Mail OHNE jede Quellenangabe faellt weiterhin durch.

Kein Mock, kein Netz, kein IMAP: `validate_message()` nimmt ein fertiges
`email.message.Message` entgegen. Der Waechter wird als Datei geladen (Pfad
relativ zur Testdatei, Regel #1409 — nie ueber den festen Hauptrepo-Pfad).

🔴 **Pruefort = Wirkort (Adversary F002, 2026-08-13).** Bis zum Fix baute
dieser Pruefstand den Zielaufbau selbst — er nahm die echte Mail und schnitt
ihr per BeautifulSoup die `.src`-Box heraus. Gemessen am echten Renderer war
`class="src"` aber die ganze Zeit da: die alte Waechter-Regel haette die neue
Mail klaglos bestanden, und die additive Regel S-1b waere von keiner echt
gerenderten Mail je erreicht worden. Beide Positivfaelle messen deshalb jetzt
den **unveraenderten** Renderer-Output — HTML *und* den seit AC-13 eigens
gebauten Klartext-Teil, also genau die zwei Teile, die der Versandweg
verschickt. Nachbearbeitet wird nur noch, was der Code gar nicht mehr erzeugen
kann: die abgeloeste Bauform und die Mail ohne Quellenangabe.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path

from bs4 import BeautifulSoup

from output.channels.email import build_mime_message
from output.renderers.alert.official_alerts import (
    OfficialAlertNotice, render_official_alert_mail_plain, render_warn_block,
)
from services.official_alerts.models import OfficialAlert

# Regel #1409: Pruefling relativ zur eigenen Testdatei aufloesen, damit aus
# einem Worktree nicht die unveraenderte Hauptrepo-Kopie geprueft wird.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR = _REPO_ROOT / ".claude" / "hooks" / "official_alert_mail_validator.py"

UTC = timezone.utc
QUELLE = "GeoSphere Austria"
REGION = "Hermagor-Pressegger See"
_RENDER_KWARGS = dict(source_label=QUELLE, stand_at="09:30", tz=UTC, context_label="KHW 403")


def _validator():
    """Laedt `official_alert_mail_validator.py` an Ort und Stelle.

    Keine Kopie in ein tmp-Verzeichnis: `validate_message()` ist rein und
    schreibt kein Log (das tut nur `main()`), und der Modulkopf erweitert
    `sys.path` um sein eigenes Hooks-Verzeichnis, um `_e2e_paths`/
    `_validator_log` zu finden — eine verschobene Kopie faende die nicht.
    """
    assert _VALIDATOR.is_file(), f"Waechter nicht gefunden: {_VALIDATOR}"
    spec = importlib.util.spec_from_file_location(
        "official_alert_mail_validator_unter_test", str(_VALIDATOR),
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _notices() -> list[OfficialAlertNotice]:
    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=datetime(2026, 7, 11, 15, 0, tzinfo=UTC),
        valid_to=datetime(2026, 7, 11, 21, 0, tzinfo=UTC),
        region_label=REGION,
    )
    return [OfficialAlertNotice(
        alert=alert, scope_label="Segment 3", sms_scope="nur S3",
        affected_chips=["Segment 3"], free_chips=[],
    )]


def _warnmail_html() -> str:
    """Die eigenstaendige amtliche Warn-Mail, wie `send_official_alert` sie
    rendert (geteilter Baustein, `variant="standalone"`) — unveraendert."""
    return render_warn_block(_notices(), variant="standalone", **_RENDER_KWARGS)


def _warnmail_plain() -> str:
    """Ihr Klartext-Teil, wie `send_official_alert` ihn uebergibt (AC-13) —
    unveraendert. Der Waechter prueft seine Textregeln bevorzugt gegen den
    Klartext (`plain or html`); in der Datenzeilen-Bauform steht die
    Beschriftung in einer eigenen Tabellenzelle, das Pflicht-Literal
    „Quelle:" entsteht also erst hier."""
    return render_official_alert_mail_plain(_notices(), **_RENDER_KWARGS)


def _mit_quelle_box(html: str) -> str:
    """Baut die ABGELOESTE Bauform nach: die Quellen-Datenzeile wird wieder zur
    getoenten `.src`-Box unter der Warn-Karte.

    Nachbearbeitung ist hier richtig — diesen Zustand kann der Code nicht mehr
    erzeugen, und genau darum geht es: der Waechter muss ihn WEITERHIN
    annehmen (additiv erweitert, nicht ersetzt). Damals trug die Mail keinen
    eigens gebauten Klartext, deshalb prueft der zugehoerige Test sie auch
    ohne einen.
    """
    soup = BeautifulSoup(html, "html.parser")
    huelle = _quellen_huelle(soup)
    assert huelle is not None, "Vorbedingung entfallen: die Mail hat keine Quellen-Datenzeile"
    wert = huelle.get_text(" ", strip=True)
    if wert.startswith("Quelle:"):
        wert = wert[len("Quelle:"):].strip()
    box = BeautifulSoup(
        f'<div class="src" style="font-size:14px;padding:12px 16px;">'
        f'<b style="font-weight:600;">Quelle:</b> {wert}</div>',
        "html.parser",
    )
    huelle.replace_with(box)
    return str(soup)


def _quellen_huelle(soup: BeautifulSoup):
    """Das `<div>`, das die Quellen-Datenzeile (und ggf. den Scope-Satz) traegt."""
    for zelle in soup.select('table[role="presentation"] td[align="left"]'):
        if zelle.get_text(" ", strip=True).startswith("Quelle"):
            return zelle.find_parent("table").parent
    return None


def _ohne_jede_quellenangabe() -> tuple[str, str]:
    """Entfernt jede Quellenangabe aus BEIDEN Teilen: die Quellen-Datenzeile,
    das „abgerufen bei"-Ende der Stand-Zeile und die Herkunfts-Fusszeile.

    Der Pruefling ist damit keine realistische Mail mehr — er ist der
    Gegenbeweis: ein Waechter, der ihn durchwinkt, prueft die Quelle nicht
    mehr.
    """
    soup = BeautifulSoup(_warnmail_html(), "html.parser")
    huelle = _quellen_huelle(soup)
    if huelle is not None:
        huelle.decompose()
    fuss = soup.select_one(".body-foot")
    if fuss is not None:
        fuss.string = "Stand: heute 09:30"
    for el in list(soup.body.find_all(recursive=False)):
        if QUELLE in el.get_text(" ", strip=True):
            el.decompose()

    zeilen = []
    for zeile in _warnmail_plain().splitlines():
        if QUELLE not in zeile:
            zeilen.append(zeile)
        elif zeile.startswith("Stand: heute"):
            zeilen.append("Stand: heute 09:30")
    return str(soup), "\n".join(zeilen)


def _als_mail(html: str, plain: str | None) -> Message:
    return build_mime_message(
        subject="[KHW 403] Segment 3 · Gewitter (GELB)", body=html,
        from_addr="gregor_zwanzig@henemm.com", to_header="gregor-test@henemm.com",
        reply_to=None, plain_text_body=plain, html=True,
        mail_type="official-alert",
    )


def _pruefen(html: str, plain: str | None) -> tuple[bool, list[str]]:
    return _validator().validate_message(_als_mail(html, plain))


# ---------------------------------------------------------------------------
# AC-14 — der echte Zielaufbau muss den Waechter bestehen
# ---------------------------------------------------------------------------
def test_ac14_mail_im_zielaufbau_besteht_den_waechter():
    """AC-14: Given der Umbau loest die Quelle-Box auf / When eine sachlich
    korrekte Mail im neuen Aufbau geprueft wird / Then besteht sie den
    Waechter.

    Gemessen am WIRKORT: HTML und Klartext kommen unveraendert aus den beiden
    Renderern, die der Versandweg aufruft. Vor dem Fix trug die Mail trotz
    „aufgeloester Box" weiterhin `class="src"`; die Zusicherung stand damit nur
    auf dem Papier des Pruefstands.
    """
    html, plain = _warnmail_html(), _warnmail_plain()

    assert 'class="src"' not in html, (
        "Der Renderer traegt weiter die Kennung der alten Quelle-Box — dann "
        "prueft dieser Test die neue Form gar nicht (Adversary F002)."
    )
    assert "Quelle:" in plain and QUELLE in plain, (
        f"Klartext-Teil nennt die Quelle nicht: {plain!r}"
    )
    assert "abgerufen bei" in plain, f"Klartext-Teil ohne Stand-Zeile: {plain!r}"

    ok, fehler = _pruefen(html, plain)
    assert ok, (
        "Der Warn-Mail-Waechter lehnt eine sachlich korrekte Mail im Zielaufbau ab. "
        "Seine Formen-Aufzaehlung muss additiv erweitert werden (nie gelockert):\n"
        + "\n".join(f"  - {f}" for f in fehler)
    )


def test_ac14_zielaufbau_wird_ohne_die_neue_regel_abgelehnt():
    """Gegenprobe zur additiven Erweiterung: Given der Waechter im Stand VOR
    A2 (`src` als Pflichtklasse, keine Datenzeilen-Alternative) / When er die
    echte Mail im Zielaufbau prueft / Then lehnt er sie ab.

    Ohne diesen Fall waere nicht belegt, dass die neue Regel ueberhaupt etwas
    bewirkt — sie koennte tote Ergaenzung sein. Der alte Stand wird nicht aus
    einer Datei geladen, sondern aus dem heutigen Waechter abgeleitet: seine
    Pflichtklassen um `src` ergaenzt, die Datenzeilen-Alternative abgeschaltet.
    """
    mod = _validator()
    mod._REQUIRED_CLASSES = mod._REQUIRED_CLASSES | {"src"}
    ok, fehler = mod.validate_message(_als_mail(_warnmail_html(), _warnmail_plain()))

    assert not ok, (
        "Der Waechter im Stand VOR A2 haette die neue Mail bestanden — dann "
        "bewacht die neue Regel nichts (Adversary F002)."
    )
    assert any("src" in f for f in fehler), (
        f"Ablehnung kommt nicht von der fehlenden `src`-Klasse: {fehler!r}"
    )


# ---------------------------------------------------------------------------
# AC-14 — Bewahrung: der Waechter prueft weiterhin etwas
# ---------------------------------------------------------------------------
def test_ac14_mail_ohne_quellenangabe_wird_weiter_beanstandet():
    """AC-14 (Negativfall): Given eine Mail OHNE jede Quellenangabe / When der
    Waechter sie prueft / Then beanstandet er sie weiterhin.

    Ohne diesen Fall belegt der Positivfall oben nur, dass der Waechter nichts
    mehr prueft. Geprueft wird nicht bloss „irgendein Fehler", sondern DASS die
    fehlende Quelle der Grund ist (P-4) — sonst koennte der Test nach dem Umbau
    aus dem falschen Grund gruen bleiben.
    """
    html, plain = _ohne_jede_quellenangabe()
    assert QUELLE not in plain and "abgerufen bei" not in plain, (
        f"Pruefstand hat noch eine Quellenangabe stehen: {plain!r}"
    )

    ok, fehler = _pruefen(html, plain)
    assert not ok, f"Waechter winkt eine Mail ohne jede Quellenangabe durch: {plain!r}"
    assert any(f.startswith("P-4") for f in fehler), (
        "Waechter beanstandet die Mail, aber nicht wegen der fehlenden Quelle "
        f"(P-4). Gemeldet: {fehler!r}"
    )


def test_ac14_zielaufbau_ohne_gebauten_klartext_wird_beanstandet():
    """Wofuer die neue Regel S-1b ueber P-4 hinaus einsteht: Given die Mail im
    Zielaufbau, aber OHNE den seit AC-13 gebauten Klartext-Teil / When der
    Waechter sie prueft / Then beanstandet er sie.

    Das ist genau der Rueckfall, den A2 beseitigt: `build_mime_message` strippt
    dann die Tags aus dem HTML, und der Klartext-Leser bekommt eine einzige
    zusammengeklebte Zeile. P-4 merkt davon NICHTS — beide Pflicht-Literale
    ("Quelle:", "abgerufen bei") stehen ja weiterhin irgendwo im Text. Erst
    S-1b sieht den Unterschied, weil es die Quelle als ZEILE verlangt.

    Ohne diesen Fall waere S-1b tote Ergaenzung: der Negativfall unten faellt
    schon an P-4 durch.
    """
    html = _warnmail_html()
    ok, fehler = _pruefen(html, None)

    assert not ok, (
        "Waechter winkt eine Mail durch, deren Klartext-Teil aus dem HTML "
        "gestrippt wurde — genau den Zustand beseitigt AC-13."
    )
    assert any(f.startswith("S-1b") for f in fehler), (
        f"Beanstandung kommt nicht von der Quellen-Form (S-1b): {fehler!r}"
    )
    assert not any(f.startswith("P-4") for f in fehler), (
        "P-4 faengt diesen Fall wider Erwarten selbst — dann belegt dieser Test "
        f"nicht mehr, wofuer S-1b einsteht: {fehler!r}"
    )


def test_ac14_abgeloeste_bauform_mit_quelle_box_besteht_weiterhin():
    """AC-14 (Additivitaet): Given die Mail in der ABGELOESTEN Bauform — Quelle
    als `.src`-Box, kein eigens gebauter Klartext — / When der Waechter sie
    prueft / Then besteht sie ihn weiterhin: keine bestehende Alternative wurde
    entfernt oder verschaerft.

    Zusammen mit dem Positivfall oben ist das die Zusicherung „additiv
    erweitern": beide Formen muessen bestehen, nicht nur die neue. Der
    Pruefling ist bewusst nachgebaut — diese Form erzeugt der Code nicht mehr.
    """
    ok, fehler = _pruefen(_mit_quelle_box(_warnmail_html()), None)
    assert ok, (
        "Der Waechter lehnt die abgeloeste Bauform ab — die Formen-Aufzaehlung "
        "wurde ersetzt statt erweitert:\n" + "\n".join(f"  - {f}" for f in fehler)
    )
