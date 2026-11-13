"""Mitteilung ueber andere Kanaele bei zustandsaendernden Premium-SMS-Befehlen.

Issue #2961 Welle 2, ADR-0116. Eine Premium-SMS-Nachricht wird einem Konto
ueber die gelernte Rueckadresse oder den Verknuepfungscode zugeordnet -- es
gibt bewusst KEINEN zusaetzlichen PIN je Nachricht (Bedienbarkeit unterwegs).
Damit eine fremde Aenderung nicht unbemerkt bleibt, bekommt der Nutzer bei
jedem per Premium-SMS ausgefuehrten, ZUSTANDSAENDERNDEN Befehl eine kurze
Mitteilung auf seinen anderen eingerichteten Kanaelen: E-Mail an die
bestaetigte Adresse und Telegram, falls verbunden. Inhalt: was, wann, ueber
welchen Kanal, wie man es zuruecknimmt.

- Lesende Befehle loesen nichts aus.
- Fail-soft: ein Fehler kostet nie die Befehlsantwort.
- Hoechstens ``TAGESGRENZE`` Mitteilungen je Nutzer und UTC-Tag (Zaehler in
  der Tageszaehler-Datei, ``sms_daily_limit.reserve_daily_slot``).
- Versand ueber die vorhandenen Wege mit Empfaengerschutz
  (``NotificationService.send_premium_sms_change_notice``).
"""
from __future__ import annotations

import logging
from datetime import datetime

from i18n import t
from services import sms_daily_limit

logger = logging.getLogger(__name__)

#: Befehlsschluessel (``CommandResult.command``), die Trip-/Vergleichs-Zustand
#: aendern: Briefings pausieren/stoppen/fortsetzen, Ruhetag, Startdatum,
#: Etappe ueberspringen.
ZUSTANDSAENDERNDE_BEFEHLE = frozenset({
    "pause", "abbruch", "weiter", "ruhetag", "startdatum", "skip",
})
#: Befehlsschluessel, die nur lesen oder ein Briefing ausloesen, ohne
#: gespeicherten Zustand zu aendern. Zusammen mit der Menge oben vollstaendig
#: (Waechter: tests/tdd/test_premium_sms_aenderungsmitteilung.py).
LESENDE_BEFEHLE = frozenset({
    "heute", "morgen", "now", "heute_gewitter", "status", "hilfe", "glance",
    "strecke", "kuerzel", "report",
})

TAGESGRENZE = 10
ZAEHLER_SCHLUESSEL = "premium_sms_change_notice"

# i18n-dynamic: inbound.aenderung.rueckweg_
_RUECKWEG = {
    "pause": "weiter",
    "abbruch": "weiter",
    "weiter": "pause",
    "ruhetag": "editor",
    "startdatum": "editor",
    "skip": "editor",
}


def ist_zustandsaendernd(result) -> bool:
    """Nur ein ERFOLGREICH ausgefuehrter aendernder Befehl zaehlt."""
    return bool(getattr(result, "success", False)) and result.command in ZUSTANDSAENDERNDE_BEFEHLE


def texte(result, befehl: str, zeitpunkt: datetime, lang: str) -> tuple[str, str]:
    """Betreff und Text der Mitteilung aus dem Katalog."""
    zeit = zeitpunkt.strftime("%Y-%m-%d %H:%M UTC")
    ziel = result.trip_name or t("inbound.aenderung.ohne_ziel", lang)
    rueckweg = t(f"inbound.aenderung.rueckweg_{_RUECKWEG[result.command]}", lang)
    betreff = t("inbound.aenderung.betreff", lang, befehl=befehl)
    text = t(
        "inbound.aenderung.text", lang, zeit=zeit, befehl=befehl, ziel=ziel,
        ergebnis=result.confirmation_body, rueckweg=rueckweg,
    )
    return betreff, text


def melde_aenderung(service, result, *, befehl: str, zeitpunkt: datetime, lang: str) -> list[str]:
    """Verschickt die Mitteilung, falls ``result`` eine Aenderung ist.

    ``service`` ist der nutzergebundene ``NotificationService`` (echte
    ``user_id``). Rueckgabe: Kanaele, auf denen die Mitteilung rausging.
    Wirft nie.
    """
    if not ist_zustandsaendernd(result):
        return []
    try:
        user_id = service._require_user()
        # Ohne zustellbaren Kanal wird nichts gezaehlt (Gegenpruefung F003).
        if not service.premium_sms_change_notice_ziele():
            return []
        if not sms_daily_limit.reserve_daily_slot(user_id, ZAEHLER_SCHLUESSEL, TAGESGRENZE, zeitpunkt):
            logger.warning(
                "Aenderungs-Mitteilung fuer Nutzer %s uebersprungen: "  # i18n-log
                "Tagesgrenze %d erreicht", user_id, TAGESGRENZE,
            )
            return []
        betreff, text = texte(result, befehl, zeitpunkt, lang)
        kanaele = service.send_premium_sms_change_notice(betreff, text)
        if not kanaele:
            sms_daily_limit.release_reservation(user_id, ZAEHLER_SCHLUESSEL, zeitpunkt)
        return kanaele
    except Exception as e:  # noqa: BLE001 -- fail-soft, die Befehlsantwort geht vor
        logger.warning("Aenderungs-Mitteilung fehlgeschlagen: %s", e)  # i18n-log
        return []
