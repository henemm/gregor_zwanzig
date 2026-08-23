"""RED — #1848 A2: die Kennung ``temperature`` ergibt in ALLEN VIER Ausgaben
genau eine Spalte mit der Tief/Hoch-Spanne.

SPEC: docs/specs/modules/feat_1848_a2_ausblick_kennungen.md — AC-4
KONTEXT: docs/context/feat-1848-a2-outlook-kennungen.md

Alle vier Ausgaben entstehen aus DERSELBEN gespeicherten Auswahl und ueber den
ECHTEN Versandpfad (``_send_trip_report_outcome()`` -> NotificationService ->
EmailOutput/TelegramOutput). Kompakt-Mail und Telegram-Bubble sind auf dem
Formatter-Weg gar nicht erreichbar (Befund #1720 S2), deshalb der Versandlauf.

Versand-Sicherheit (#1477): beide Transporte sind vor dem Lauf durch
aufzeichnende ECHTE Unterklassen ersetzt (kein Mock-Framework), SMS und
Premium-SMS bleiben unkonfiguriert und abgeschaltet — es verlaesst nichts den
Prozess.

Kern-Schicht: kein Netz (Wetter kommt aus der Fixture-Unterklasse des
Zeitplaners). Pfadregel #1409.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

# Reine Kennung — ohne Auswertungsangabe. Genau das ist die A2-Umstellung.
AUSWAHL = ["temperature"]

_SPANNE = re.compile(r"-?\d+(?:[.,]\d+)?/-?\d+(?:[.,]\d+)?")


def _spannen_zelle(text, quelle: str) -> str:
    """Die Tief/Hoch-Zelle aus einem Ausgabeteil — mit sprechendem Fehler,
    solange der Ausblick dort gar nicht erscheint."""
    assert text, (
        f"{quelle}: Der 3-Tages-Ausblick fehlt vollstaendig. Die gespeicherte "
        f"Kennungsauswahl {AUSWAHL!r} wurde verworfen und wie 'bewusst "
        "geleert' behandelt — der Block ist abgeschaltet statt gerendert "
        "(AC-4)."
    )
    treffer = _SPANNE.findall(text)
    assert treffer, (
        f"{quelle}: Keine Tief/Hoch-Zelle der Form '9/27' gefunden. "
        f"Gesehener Ausblick:\n{text}"
    )
    return treffer[0]


def test_ac4_temperatur_kennung_zeigt_ueberall_dieselbe_eine_spannen_spalte():
    """AC-4: Given die Kennung ``temperature`` ist fuer den Ausblick gewaehlt /
    When das Briefing gerendert wird / Then zeigt die Ausblick-Tabelle GENAU
    EINE Temperatur-Spalte, deren Zelle Tief und Hoch mit Schraegstrich vereint
    (Form ``9/27``) — uebereinstimmend in HTML-Mail, Klartext, Kompaktmail und
    Telegram.

    Die vier Ausgaben duerfen nicht auseinanderlaufen (#1366-Fehlerklasse):
    der Nutzer liest je nach Empfangslage einen anderen Kanal — auf dem Pass
    E-Mail und Telegram, auf der Huette nur Satellit.
    """
    from tests.helpers.trip_outlook_channels import (
        compact_outlook_block, telegram_outlook_bubble, trip, versendete_teile,
    )
    from tests.helpers.trip_outlook_selection import (
        html_outlook_body_rows, html_outlook_headers, plain_outlook_block,
    )
    from tests.tdd.test_trip_outlook_dispatch_mail import _zugestellte_teile

    html, plain = _zugestellte_teile(
        trip(outlook_metrics=AUSWAHL, email_format="full"))
    kompakt_body, bubbles = versendete_teile(
        trip(outlook_metrics=AUSWAHL, email_format="compact"))

    kopf = html_outlook_headers(html)
    zeilen = html_outlook_body_rows(html)
    assert kopf and zeilen, (
        "HTML-Mail: Der 3-Tages-Ausblick fehlt vollstaendig. Die gespeicherte "
        f"Kennungsauswahl {AUSWAHL!r} wurde verworfen und wie 'bewusst "
        "geleert' behandelt (AC-4)."
    )
    # #2098: hinter der Auswahl steht die fest angehaengte ACC-Zusatzspalte
    # (Tag + 1 Metrikspalte + ACC) -- die Zusicherung "GENAU EINE
    # Temperatur-Spalte" wird deshalb an der Auswahl-Mitte geprueft.
    assert kopf == ["Tag", "Temperatur", "ACC"], (
        f"HTML-Mail: Die Ausblick-Tabelle hat die Kopfzeile {kopf!r}. Aus der "
        "einen Kennung 'temperature' muss GENAU EINE Wert-Spalte entstehen "
        "(neben 'Tag' und der festen ACC-Spalte) — Tief und Hoch gehoeren in "
        "dieselbe Zelle (AC-4)."
    )

    zellen = {
        "HTML-Mail": zeilen[0][1] if len(zeilen[0]) > 1 else "",
        "Klartext": _spannen_zelle(plain_outlook_block(plain), "Klartext"),
        "Kompaktmail": _spannen_zelle(compact_outlook_block(kompakt_body),
                                      "Kompaktmail"),
        "Telegram": _spannen_zelle(telegram_outlook_bubble(bubbles), "Telegram"),
    }

    assert _SPANNE.fullmatch(zellen["HTML-Mail"] or ""), (
        f"HTML-Mail: Die Temperatur-Zelle lautet {zellen['HTML-Mail']!r} statt "
        "einer Tief/Hoch-Spanne der Form '9/27' (AC-4)."
    )
    assert len(set(zellen.values())) == 1, (
        "Die vier Ausgaben zeigen verschiedene Temperatur-Zellen fuer denselben "
        f"Tag: {zellen!r}. Sie stammen aus derselben Auswahl und muessen "
        "uebereinstimmen (AC-4, #1366-Fehlerklasse)."
    )
