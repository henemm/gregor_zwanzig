#!/usr/bin/env python3
"""Konsolidiert die fuenf Teil-Inventare (#3047 Runde 7) zu EINER Matrix.

Wiederholbar:  python3 -I docs/artifacts/feat-3047/inventar/konsolidieren.py
Eingaben (Ordner des Skripts, docs/artifacts/feat-3047/inventar/):
           {trip_mail,orte_mail,kanaele,editor,validatoren}.json + *_befunde.md
Optional:  status_updates.json  {"<kanonische_id>|<spalte>": {"status","beleg","notiz","befund"}}, luecken_befunde.md,
           befund_status.json  (Status je Befund nach den Behebungspaketen, Runde 7)
Ausgaben (eine Ebene hoeher, docs/artifacts/feat-3047/):
           inventar_matrix.json, inventar_matrix.md, runde7_befunde.md
Belege der Form ``scratchpad/inventar/...`` verweisen auf Pruefskripte der Inventur, die bewusst
nicht im Repo liegen; Belege ``tests/...``/``frontend/...``/``internal/...`` sind Repo-Tests.

Regeln
- Zustaendig je Spalte: email_* -> trip_mail (Trip) bzw. orte_mail (Orte);
  telegram/sms/premium_sms -> kanaele; einstellungsseite -> editor;
  validator_email -> validatoren (schlechtester Status ueber email_html/text/kompakt der Validator-Zeile).
- Mehrere Teilzeilen auf einer Zelle: rot > ungeprueft > ausgelagert > gruen > nicht_anwendbar.
- Zelle bleibt ungeprueft, obwohl ein anderer (nicht zustaendiger) Bereich sie belegt -> dessen Status/Beleg.
  (validatoren zaehlt dafuer NICHT fuer Ausgabe-Spalten: dort heisst gruen "Validator prueft", nicht "Ausgabe stimmt".)
- Zelle ohne jede Teilzeile -> ungeprueft mit Merkmal unbelegt=True.
- QUER_HINWEISE: Produktbefunde eines fremden Bereichs, die einer Zelle widersprechen, werden angehaengt,
  aendern den Status aber nicht (Zielkonflikt sichtbar machen statt still entscheiden).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

BASIS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
ZIEL = Path(sys.argv[2]) if len(sys.argv) > 2 else BASIS.parent
BEREICHE = ["trip_mail", "orte_mail", "kanaele", "editor", "validatoren"]
AUSGABE = ["email_html", "email_text", "email_kompakt", "telegram", "sms", "premium_sms", "einstellungsseite"]
SPALTEN = AUSGABE + ["validator_email"]
RANG = {"rot": 5, "ungeprueft": 4, "ausgelagert": 3, "gruen": 2, "nicht_anwendbar": 1}
KUERZEL = {"gruen": "✓", "rot": "✗", "nicht_anwendbar": "–", "ungeprueft": "?", "ausgelagert": "↗"}
LEGENDE = {
    "gruen": "✓ über den echten Weg ausgeführt bzw. von einem Test dort geprüft, wo es wirkt (Mutation belegt)",
    "rot": "✗ Ausgabe weicht von der Einstellung ab, oder (Spalte validator_email) Validator erkennt die Abweichung nicht",
    "nicht_anwendbar": "– Ausgabe hat diesen Baustein laut Konzept/ADR nicht",
    "ungeprueft": "? nicht geprüft",
    "ausgelagert": "↗ bekannt und in eigenem Issue ausgelagert",
}


def zustaendig(spalte: str, kontext: str) -> str:
    if spalte.startswith("email_"):
        return "orte_mail" if kontext == "orte" else "trip_mail"
    if spalte in ("telegram", "sms", "premium_sms"):
        return "kanaele"
    if spalte == "einstellungsseite":
        return "editor"
    return "validatoren"


# --------------------------------------------------------------------------------------------
# Kanonische Zeilen: (id, Gruppe, Einstellung)
# --------------------------------------------------------------------------------------------
KANON = [
    # ---------------- Trip ----------------
    ("trip.grundauswahl.gespeichert", "Grundauswahl", "Grundauswahl gespeichert: Metrik an/aus"),
    ("trip.grundauswahl.reihenfolge", "Grundauswahl", "Grundauswahl: Reihenfolge"),
    ("trip.grundauswahl.nie_eingestellt", "Grundauswahl", "Grundauswahl nie eingestellt (Feld fehlt) / Altbestand = Vorgabe"),
    ("trip.grundauswahl.bewusst_leer", "Grundauswahl", "Grundauswahl bewusst leer"),
    ("trip.grundauswahl.altformat", "Grundauswahl", "Grundauswahl Altformat (Zeichenkette / ohne enabled)"),
    ("trip.grundauswahl.wieder_eingeschaltet", "Grundauswahl", "Metrik per „+“ / Vorlage wieder eingeschaltet (hinten angehängt)"),
    ("trip.grundauswahl.nachtraeglich_global", "Grundauswahl", "Global nachträglich eingeschaltete Metrik in bearbeiteter Liste"),
    ("trip.metrik.morgen_abend", "Grundauswahl", "Morgen/Abend je Metrik"),
    ("trip.email_liste.an_aus", "E-Mail-Liste", "E-Mail-Liste: Zeile an/aus"),
    ("trip.email_liste.reihenfolge", "E-Mail-Liste", "E-Mail-Liste: Reihenfolge"),
    ("trip.email_liste.roh_einfach", "E-Mail-Liste", "E-Mail-Liste: Roh/Einfach je Zeile (inkl. Windrichtung)"),
    ("trip.email_liste.je_bericht", "E-Mail-Liste", "Kanal-Liste je Bericht (Morgen/Abend)"),
    ("trip.metriken_ueberblick", "E-Mail-Liste", "Metriken-Überblick folgt der E-Mail-Liste"),
    ("trip.telegram_liste.an_aus", "Telegram-Liste", "Telegram-Liste: Zeile an/aus"),
    ("trip.telegram_liste.reihenfolge", "Telegram-Liste", "Telegram-Liste: Reihenfolge"),
    ("trip.telegram_liste.roh_einfach", "Telegram-Liste", "Telegram-Liste: Roh/Einfach je Zeile"),
    ("trip.telegram_liste.windrichtung_roh", "Telegram-Liste", "Telegram-Liste: Windrichtung Roh (#3063 P2)"),
    ("trip.telegram.schnittlinie", "Telegram-Liste", "Telegram-Schnittlinie (erste 7)"),
    ("trip.sms_liste.an_aus", "SMS-Liste", "SMS-Liste: Zeile an/aus"),
    ("trip.sms_liste.reihenfolge", "SMS-Liste", "SMS-Liste: Reihenfolge"),
    ("trip.sms_liste.roh_einfach", "SMS-Liste", "SMS-Liste: Roh/Einfach"),
    ("trip.sms.kuerzung", "SMS-Liste", "SMS 160 Zeichen: was zuerst wegfällt"),
    ("trip.premium_sms_liste", "Premium-SMS-Liste", "Premium-SMS eigene Liste (N2)"),
    ("trip.kanal_liste.nie_eingestellt", "Kanal-Listen", "Kanal-Liste nie eingestellt (Altbestand)"),
    ("trip.kanal_liste.bewusst_leer", "Kanal-Listen", "Kanal-Liste bewusst leer"),
    ("trip.kanal_liste.totalschnitt", "Kanal-Listen", "Totalschnitt: Kanal-Liste ∩ Grundauswahl leer"),
    ("trip.ausblick.auswahl_reihenfolge", "Ausblick", "3-Tages-Ausblick: Auswahl + Reihenfolge"),
    ("trip.ausblick.roh_einfach", "Ausblick", "3-Tages-Ausblick: Roh/Einfach"),
    ("trip.ausblick.erscheint_im", "Ausblick", "3-Tages-Ausblick: erscheint im Morgen/Abend (Mehrtages-Trend)"),
    ("trip.ausblick.an_aus", "Ausblick", "3-Tages-Ausblick an/aus (show_outlook)"),
    ("trip.ausblick.zeilenzahl", "Ausblick", "3-Tages-Ausblick: drei Tageszeilen"),
    ("trip.ausblick.etappennamen", "Ausblick", "Etappennamen (Sonderzeichen, überlang) im Ausblick"),
    ("trip.zusatz.etappen_kennzahlen", "Zusatzblöcke", "Zusatzblock Etappen-Kennzahlen (W17)"),
    ("trip.zusatz.vortag", "Zusatzblöcke", "Zusatzblock Vortag-Vergleich (W18)"),
    ("trip.zusatz.nachtblock", "Zusatzblöcke", "Zusatzblock Nacht-Stundentabelle (W22)"),
    ("trip.email_format", "Format", "E-Mail-Format Ausführlich/Kompakt (W15)"),
    ("trip.tagesfenster", "Format", "Tagesfenster von–bis (W12)"),
    ("trip.amtliche_warnungen.schalter", "Warnungen/Alarm", "Amtliche Warnungen an/aus (W20)"),
    ("trip.amtliche_warnungen.position", "Warnungen/Alarm", "Amtliche Warnungen feste erste Zeile (WV6)"),
    ("trip.amtliche_warnungen.kuerzung_zuletzt", "Warnungen/Alarm", "Amtliche Warnung fällt beim Kürzen zuletzt weg"),
    ("trip.radar", "Warnungen/Alarm", "Radar-Regen-Alarm (N1)"),
    ("trip.ampel.grenzen", "Warnungen/Alarm", "Ampel-Grenzen ändern"),
    ("trip.ampel.alarm_ab", "Warnungen/Alarm", "Alarm ab je Metrik / für alle"),
    ("trip.sms_schwellen", "Warnungen/Alarm", "SMS-Schwellen je Metrik"),
    ("trip.telegram_kurzstil.briefing", "Telegram-Kurzstil", "Telegram-Kurzstil: Briefing"),
    ("trip.telegram_kurzstil.alarm", "Telegram-Kurzstil", "Telegram-Kurzstil: Alarm"),
    ("trip.sprache", "Sprache", "Sprache DE/EN (Kopf, Spalten, Kürzel sprachfest)"),
    ("trip.sprache.kappungshinweis", "Sprache", "Sprache EN: Telegram-Kappungshinweis"),
    ("trip.kuerzel_legende", "Sprache", "Kürzel-Legende (W21)"),
    ("trip.vorlage.anwenden", "Vorlagen", "Vorlage übernehmen/zurücksetzen (Ampel, abgeleitete Größen)"),
    ("trip.vorlage.neu_aus_standard", "Vorlagen", "Neuer Trip übernimmt eigene Standard-Vorlage"),
    ("trip.vorlage.eigene_speichern", "Vorlagen", "Als eigene Vorlage speichern"),
    ("trip.zeiten", "Zeiten/Versand", "Uhrzeit Morgen-/Abend-Briefing"),
    ("trip.slots", "Zeiten/Versand", "Morgen-/Abend-Briefing an/aus"),
    ("trip.briefing_kanaele", "Zeiten/Versand", "Briefing je Kanal"),
    ("trip.alarm_kanaele", "Zeiten/Versand", "Alarme je Kanal"),
    ("trip.dringlichkeit", "Zeiten/Versand", "Alarm ab Dringlichkeit je Kanal"),
    ("trip.stille_stunden", "Zeiten/Versand", "Stille Stunden"),
    ("trip.cooldown", "Zeiten/Versand", "Mindestabstand zwischen Alarmen"),
    ("trip.zwei_nutzer", "Mandanten", "Zwei Nutzer: eigene Konfiguration/Sprache/Empfänger"),
    # ---------------- Orte ----------------
    ("orte.grundauswahl.gespeichert", "Grundauswahl", "Grundauswahl gespeichert (Liste, Folge ≠ Katalog)"),
    ("orte.grundauswahl.nie_eingestellt", "Grundauswahl", "Grundauswahl nie eingestellt (active_metrics fehlt)"),
    ("orte.grundauswahl.bewusst_leer", "Grundauswahl", "Grundauswahl bewusst leer (active_metrics = [])"),
    ("orte.grundauswahl.altformat", "Grundauswahl", "Altbestand ohne neue Felder (Golden)"),
    ("orte.grundauswahl.vorlagen_metrik_ohne_pendant", "Grundauswahl", "Vorlagen-Metrik ohne Vergleichs-Pendant (Tiefsttemp. Nacht)"),
    ("orte.grundauswahl.morgen_abend", "Grundauswahl", "Morgen/Abend je Metrik"),
    ("orte.vergleichstabelle.an_aus", "Vergleichstabelle", "Vergleichstabelle (E-Mail-Liste): Zeile an/aus"),
    ("orte.vergleichstabelle.reihenfolge", "Vergleichstabelle", "Vergleichstabelle: Reihenfolge (Warnungen fest zuerst)"),
    ("orte.vergleichstabelle.roh_einfach", "Vergleichstabelle", "Vergleichstabelle: Roh/Einfach je Zeile (W11)"),
    ("orte.telegram_liste.an_aus", "Telegram-Liste", "Telegram-Liste: Zeile an/aus"),
    ("orte.telegram_liste.reihenfolge", "Telegram-Liste", "Telegram-Liste: Reihenfolge"),
    ("orte.telegram_liste.roh_einfach", "Telegram-Liste", "Telegram-Liste: Roh/Einfach je Zeile"),
    ("orte.telegram_liste.windrichtung_roh", "Telegram-Liste", "Telegram-Liste: Windrichtung Roh/Einfach (#3063 P2)"),
    ("orte.telegram.schnittlinie", "Telegram-Liste", "Telegram-Schnittlinie (7 je Ort)"),
    ("orte.sms_liste.an_aus", "SMS-Liste", "SMS-Liste: Zeile an/aus"),
    ("orte.sms_liste.reihenfolge", "SMS-Liste", "SMS-Liste: Reihenfolge"),
    ("orte.sms_liste.roh_einfach", "SMS-Liste", "SMS-Liste: Roh/Einfach"),
    ("orte.sms.kuerzung", "SMS-Liste", "SMS 153/160 Zeichen: Kürzung"),
    ("orte.premium_sms_liste", "Premium-SMS-Liste", "Premium-SMS eigene Liste (N2)"),
    ("orte.kanal_liste.altformat", "Kanal-Listen", "Altformat channel_active_metrics"),
    ("orte.kanal_liste.bewusst_leer", "Kanal-Listen", "Kanal-Liste bewusst leer"),
    ("orte.kanal_liste.totalschnitt", "Kanal-Listen", "Totalschnitt: Liste ∩ Grundauswahl leer"),
    ("orte.stundenverlauf.auswahl_reihenfolge", "Stundenverlauf", "Stundenverlauf: Auswahl + Reihenfolge"),
    ("orte.stundenverlauf.an_aus", "Stundenverlauf", "Stundenverlauf an/aus (WV8)"),
    ("orte.stundenverlauf.gesperrt", "Stundenverlauf", "Stundenverlauf: gesperrte Größen (WV9)"),
    ("orte.stundenverlauf.roh_einfach", "Stundenverlauf", "Stundenverlauf: Roh/Einfach (W11)"),
    ("orte.ausblick.auswahl_reihenfolge", "Ausblick", "3-Tages-Ausblick: Auswahl + Reihenfolge"),
    ("orte.ausblick.roh_einfach", "Ausblick", "3-Tages-Ausblick: Roh/Einfach"),
    ("orte.ausblick.an_aus", "Ausblick", "3-Tages-Ausblick an/aus"),
    ("orte.ausblick.erscheint_im", "Ausblick", "3-Tages-Ausblick: erscheint im Morgen/Abend"),
    ("orte.ausblick.zeilenzahl", "Ausblick", "3-Tages-Ausblick: drei Zeilen je Ort"),
    ("orte.ortsfolge", "Orte", "Ortsfolge"),
    ("orte.orte_auswahl", "Orte", "Orte im Briefing (Ort fehlt)"),
    ("orte.ortsnamen", "Orte", "Ortsnamen mit Sonderzeichen"),
    ("orte.zusatzbloecke", "Zusatzblöcke", "Zusatzblöcke"),
    ("orte.email_format", "Format", "E-Mail-Format Ausführlich/Kompakt"),
    ("orte.tagesfenster", "Format", "Tagesfenster von–bis (W12, über Mitternacht)"),
    ("orte.morgen_abend_briefing", "Format", "Morgen-Briefing = heute, Abend = morgen (V8)"),
    ("orte.amtliche_warnungen.schalter", "Warnungen/Alarm", "Amtliche Warnungen an/aus"),
    ("orte.amtliche_warnungen.position", "Warnungen/Alarm", "Amtliche Warnungen zuerst (WV6)"),
    ("orte.amtliche_warnungen.kuerzung_zuletzt", "Warnungen/Alarm", "Warnung eines weiteren Ortes beim Kürzen"),
    ("orte.amtliche_warnungen.nicht_abrufbar", "Warnungen/Alarm", "Hinweis „Warnungen nicht abrufbar“"),
    ("orte.radar", "Warnungen/Alarm", "Radar-Regen-Alarm"),
    ("orte.ampel.grenzen", "Warnungen/Alarm", "Ampel-Grenzen ändern"),
    ("orte.ampel.alarm_ab", "Warnungen/Alarm", "Alarm ab je Metrik / für alle"),
    ("orte.telegram_kurzstil.briefing", "Telegram-Kurzstil", "Telegram-Kurzstil: Briefing"),
    ("orte.telegram_kurzstil.alarm", "Telegram-Kurzstil", "Telegram-Kurzstil: Alarm"),
    ("orte.sprache", "Sprache", "Sprache DE/EN"),
    ("orte.kuerzel_legende", "Sprache", "Kürzel-Legende (W21)"),
    ("orte.vorlage.anwenden", "Vorlagen", "Vorlage übernehmen/zurücksetzen; Vorlage im Mail-Kopf (K3b)"),
    ("orte.vorlage.neu_aus_standard", "Vorlagen", "Neues Orts-Briefing übernimmt Standard-Vorlage"),
    ("orte.vorlage.eigene_speichern", "Vorlagen", "Als eigene Vorlage speichern"),
    ("orte.zeiten", "Zeiten/Versand", "Uhrzeit Morgen-/Abend-Briefing"),
    ("orte.slots", "Zeiten/Versand", "Morgen-/Abend-Briefing an/aus"),
    ("orte.briefing_kanaele", "Zeiten/Versand", "Briefing je Kanal"),
    ("orte.alarm_kanaele", "Zeiten/Versand", "Alarme je Kanal"),
    ("orte.dringlichkeit", "Zeiten/Versand", "Alarm ab Dringlichkeit je Kanal"),
    ("orte.stille_stunden", "Zeiten/Versand", "Stille Stunden"),
    ("orte.cooldown", "Zeiten/Versand", "Mindestabstand zwischen Alarmen"),
    ("orte.laufzeit", "Zeiten/Versand", "Laufzeit bis auf Weiteres / bis Datum"),
    ("orte.zwei_nutzer", "Mandanten", "Zwei Nutzer: eigene Listen/Empfänger"),
]

# --------------------------------------------------------------------------------------------
# Abbildungstabelle: (Bereich, Teilzeilen-ID) -> [kanonische IDs]
# --------------------------------------------------------------------------------------------
ABBILDUNG: dict[str, dict[str, list[str]]] = {
    "trip_mail": {
        "trip.grundauswahl.auswahl": ["trip.grundauswahl.gespeichert"],
        "trip.grundauswahl.reihenfolge": ["trip.grundauswahl.reihenfolge"],
        "trip.grundauswahl.neu_hinzugefuegt": ["trip.grundauswahl.wieder_eingeschaltet"],
        "trip.grundauswahl.nachtraeglich_global": ["trip.grundauswahl.nachtraeglich_global"],
        "trip.email_liste.auswahl": ["trip.email_liste.an_aus"],
        "trip.email_liste.reihenfolge": ["trip.email_liste.reihenfolge"],
        "trip.email_liste.roh_einfach": ["trip.email_liste.roh_einfach"],
        "trip.email_liste.je_bericht": ["trip.email_liste.je_bericht"],
        "trip.metrik.morgen_abend": ["trip.metrik.morgen_abend"],
        "trip.ausblick.metriken": ["trip.ausblick.auswahl_reihenfolge"],
        "trip.ausblick.roh_einfach": ["trip.ausblick.roh_einfach"],
        "trip.ausblick.erscheint_im": ["trip.ausblick.erscheint_im"],
        "trip.ausblick.show_outlook": ["trip.ausblick.an_aus"],
        "trip.zusatz.etappen_kennzahlen": ["trip.zusatz.etappen_kennzahlen"],
        "trip.zusatz.vortag": ["trip.zusatz.vortag"],
        "trip.zusatz.nachtblock": ["trip.zusatz.nachtblock"],
        "trip.email_format": ["trip.email_format"],
        "trip.tagesfenster": ["trip.tagesfenster"],
        "trip.amtliche_warnungen.schalter": ["trip.amtliche_warnungen.schalter"],
        "trip.amtliche_warnungen.position": ["trip.amtliche_warnungen.position"],
        "trip.sprache": ["trip.sprache"],
        "trip.vorlage.ampel": ["trip.vorlage.anwenden"],
        "trip.mandantentrennung": ["trip.zwei_nutzer"],
    },
    "orte_mail": {
        "orte.grundauswahl.nie_eingestellt": ["orte.grundauswahl.nie_eingestellt"],
        "orte.grundauswahl.bewusst_leer": ["orte.grundauswahl.bewusst_leer"],
        "orte.grundauswahl.liste": ["orte.grundauswahl.gespeichert"],
        "orte.vergleichstabelle.auswahl_reihenfolge": ["orte.vergleichstabelle.an_aus", "orte.vergleichstabelle.reihenfolge"],
        "orte.vergleichstabelle.roh_einfach": ["orte.vergleichstabelle.roh_einfach"],
        "orte.vergleichstabelle.totalschnitt": ["orte.kanal_liste.totalschnitt"],
        "orte.stundenverlauf.auswahl_reihenfolge": ["orte.stundenverlauf.auswahl_reihenfolge"],
        "orte.stundenverlauf.an_aus": ["orte.stundenverlauf.an_aus"],
        "orte.stundenverlauf.gesperrt": ["orte.stundenverlauf.gesperrt"],
        "orte.stundenverlauf.roh_einfach": ["orte.stundenverlauf.roh_einfach"],
        "orte.ausblick.auswahl_reihenfolge": ["orte.ausblick.auswahl_reihenfolge"],
        "orte.ausblick.roh_einfach": ["orte.ausblick.roh_einfach"],
        "orte.ausblick.an_aus": ["orte.ausblick.an_aus"],
        "orte.ausblick.morgen_abend": ["orte.ausblick.erscheint_im"],
        "orte.ortsfolge": ["orte.ortsfolge"],
        "orte.email_format": ["orte.email_format"],
        "orte.tagesfenster": ["orte.tagesfenster"],
        "orte.amtliche_warnungen.schalter": ["orte.amtliche_warnungen.schalter"],
        "orte.amtliche_warnungen.erste_zeile": ["orte.amtliche_warnungen.position"],
        "orte.amtliche_warnungen.nicht_abrufbar": ["orte.amtliche_warnungen.nicht_abrufbar"],
        "orte.sprache": ["orte.sprache"],
        "orte.vorlage_im_kopf": ["orte.vorlage.anwenden"],
        "orte.morgen_abend_briefing": ["orte.morgen_abend_briefing"],
        "orte.zwei_nutzer": ["orte.zwei_nutzer"],
        "orte.altbestand": ["orte.grundauswahl.altformat"],
    },
    "kanaele": {
        "trip.telegram_liste.reihenfolge": ["trip.telegram_liste.reihenfolge"],
        "trip.telegram_liste.an_aus": ["trip.telegram_liste.an_aus"],
        "trip.telegram_liste.roh_einfach": ["trip.telegram_liste.roh_einfach"],
        "trip.telegram_liste.windrichtung_roh": ["trip.telegram_liste.windrichtung_roh"],
        "trip.telegram.schnittlinie_7": ["trip.telegram.schnittlinie"],
        "trip.sms_liste.reihenfolge": ["trip.sms_liste.reihenfolge"],
        "trip.sms_liste.an_aus": ["trip.sms_liste.an_aus"],
        "trip.sms_liste.roh_einfach": ["trip.sms_liste.roh_einfach"],
        "trip.sms.kuerzung_160": ["trip.sms.kuerzung"],
        "trip.premium_sms_liste": ["trip.premium_sms_liste"],
        "trip.telegram_style.briefing": ["trip.telegram_kurzstil.briefing"],
        "trip.telegram_style.alarm": ["trip.telegram_kurzstil.alarm"],
        "trip.grundauswahl.morgen_abend": ["trip.metrik.morgen_abend"],
        "trip.grundauswahl.totalschnitt": ["trip.kanal_liste.totalschnitt"],
        "trip.kanal_liste.nie_eingestellt": ["trip.kanal_liste.nie_eingestellt"],
        "trip.kanal_liste.bewusst_leer": ["trip.kanal_liste.bewusst_leer"],
        "trip.ausblick": ["trip.ausblick.auswahl_reihenfolge", "trip.ausblick.roh_einfach"],
        "trip.tagesfenster": ["trip.tagesfenster"],
        "trip.amtliche_warnungen.position": ["trip.amtliche_warnungen.position"],
        "trip.amtliche_warnungen.kuerzung_zuletzt": ["trip.amtliche_warnungen.kuerzung_zuletzt"],
        "trip.sprache.kopf_kuerzel": ["trip.sprache"],
        "trip.sprache.kappungshinweis": ["trip.sprache.kappungshinweis"],
        "trip.kuerzel_legende": ["trip.kuerzel_legende"],
        "trip.zwei_nutzer": ["trip.zwei_nutzer"],
        "orte.telegram_liste.reihenfolge": ["orte.telegram_liste.reihenfolge"],
        "orte.telegram_liste.an_aus": ["orte.telegram_liste.an_aus"],
        "orte.telegram_liste.roh_einfach": ["orte.telegram_liste.roh_einfach"],
        "orte.telegram_liste.windrichtung_roh": ["orte.telegram_liste.windrichtung_roh"],
        "orte.telegram.schnittlinie_7": ["orte.telegram.schnittlinie"],
        "orte.sms_liste.reihenfolge_an_aus": ["orte.sms_liste.reihenfolge", "orte.sms_liste.an_aus"],
        "orte.sms_liste.roh_einfach": ["orte.sms_liste.roh_einfach"],
        "orte.channel_active_metrics": ["orte.kanal_liste.altformat"],
        "orte.sms.kuerzung": ["orte.sms.kuerzung"],
        "orte.amtliche_warnungen.kuerzung_zuletzt": ["orte.amtliche_warnungen.kuerzung_zuletzt"],
        "orte.amtliche_warnungen.position": ["orte.amtliche_warnungen.position"],
        "orte.premium_sms_liste": ["orte.premium_sms_liste"],
        "orte.telegram_style.briefing": ["orte.telegram_kurzstil.briefing"],
        "orte.telegram_style.alarm": ["orte.telegram_kurzstil.alarm"],
        "orte.kanal_liste.bewusst_leer": ["orte.kanal_liste.bewusst_leer"],
        "orte.kanal_liste.totalschnitt": ["orte.kanal_liste.totalschnitt"],
        "orte.grundauswahl.morgen_abend": ["orte.grundauswahl.morgen_abend"],
        "orte.ausblick": ["orte.ausblick.auswahl_reihenfolge"],
        "orte.tagesfenster": ["orte.tagesfenster"],
        "orte.sprache": ["orte.sprache"],
        "orte.kuerzel_legende": ["orte.kuerzel_legende"],
        "orte.zwei_nutzer": ["orte.zwei_nutzer"],
    },
    "editor": {
        "trip.grundauswahl.gespeichert": ["trip.grundauswahl.gespeichert"],
        "trip.grundauswahl.nie_eingestellt": ["trip.grundauswahl.nie_eingestellt"],
        "trip.grundauswahl.bewusst_leer": ["trip.grundauswahl.bewusst_leer"],
        "trip.grundauswahl.altformat": ["trip.grundauswahl.altformat"],
        "orte.grundauswahl.gespeichert": ["orte.grundauswahl.gespeichert"],
        "orte.grundauswahl.nie_eingestellt": ["orte.grundauswahl.nie_eingestellt"],
        "orte.grundauswahl.bewusst_leer": ["orte.grundauswahl.bewusst_leer"],
        "orte.grundauswahl.nachttemperatur": ["orte.grundauswahl.vorlagen_metrik_ohne_pendant"],
        "trip.vorlage.anwenden": ["trip.vorlage.anwenden"],
        "orte.vorlage.anwenden": ["orte.vorlage.anwenden"],
        "trip.vorlage.neu_aus_standard": ["trip.vorlage.neu_aus_standard"],
        "orte.vorlage.neu_aus_standard": ["orte.vorlage.neu_aus_standard"],
        "vorlage.eigene_speichern": ["trip.vorlage.eigene_speichern", "orte.vorlage.eigene_speichern"],
        "trip.ampel.grenzen": ["trip.ampel.grenzen"],
        "orte.ampel.grenzen": ["orte.ampel.grenzen"],
        "trip.ampel.alarm_ab": ["trip.ampel.alarm_ab"],
        "orte.ampel.alarm_ab": ["orte.ampel.alarm_ab"],
        "trip.amtliche_warnungen": ["trip.amtliche_warnungen.schalter"],
        "orte.amtliche_warnungen": ["orte.amtliche_warnungen.schalter"],
        "orte.radar": ["orte.radar"],
        "trip.radar": ["trip.radar"],
        "trip.tagesfenster": ["trip.tagesfenster"],
        "orte.tagesfenster": ["orte.tagesfenster"],
        "trip.zeiten": ["trip.zeiten"],
        "orte.zeiten": ["orte.zeiten"],
        "trip.slots": ["trip.slots"],
        "orte.slots": ["orte.slots"],
        "trip.briefing_kanaele": ["trip.briefing_kanaele"],
        "orte.briefing_kanaele": ["orte.briefing_kanaele"],
        "trip.alarm_kanaele": ["trip.alarm_kanaele"],
        "orte.alarm_kanaele": ["orte.alarm_kanaele"],
        "trip.dringlichkeit": ["trip.dringlichkeit"],
        "orte.dringlichkeit": ["orte.dringlichkeit"],
        "trip.stille_stunden": ["trip.stille_stunden"],
        "orte.stille_stunden": ["orte.stille_stunden"],
        "trip.cooldown": ["trip.cooldown"],
        "orte.cooldown": ["orte.cooldown"],
        "orte.laufzeit": ["orte.laufzeit"],
        "trip.telegram_kurzstil": ["trip.telegram_kurzstil.briefing", "trip.telegram_kurzstil.alarm"],
        "orte.telegram_kurzstil": ["orte.telegram_kurzstil.briefing", "orte.telegram_kurzstil.alarm"],
        "trip.mehrtages_trend": ["trip.ausblick.erscheint_im"],
        "trip.liste.kanaele": [
            "trip.email_liste.an_aus", "trip.email_liste.reihenfolge", "trip.email_liste.roh_einfach",
            "trip.telegram_liste.an_aus", "trip.telegram_liste.reihenfolge", "trip.telegram_liste.roh_einfach",
            "trip.telegram_liste.windrichtung_roh",
            "trip.sms_liste.an_aus", "trip.sms_liste.reihenfolge", "trip.sms_liste.roh_einfach",
        ],
        "trip.liste.premium_sms": ["trip.premium_sms_liste"],
        "trip.liste.je_bericht": ["trip.email_liste.je_bericht"],
        "trip.liste.global_nachtraeglich": ["trip.grundauswahl.nachtraeglich_global"],
        "trip.ausblick": ["trip.ausblick.auswahl_reihenfolge"],
        "trip.ausblick.roh_einfach": ["trip.ausblick.roh_einfach"],
        "orte.liste.vergleichstabelle": ["orte.vergleichstabelle.an_aus", "orte.vergleichstabelle.reihenfolge"],
        "orte.liste.kanaele_roh_einfach": [
            "orte.vergleichstabelle.roh_einfach",
            "orte.telegram_liste.an_aus", "orte.telegram_liste.reihenfolge", "orte.telegram_liste.roh_einfach",
            "orte.telegram_liste.windrichtung_roh",
            "orte.sms_liste.an_aus", "orte.sms_liste.reihenfolge", "orte.sms_liste.roh_einfach",
            "orte.premium_sms_liste",
        ],
        "orte.stundenverlauf": ["orte.stundenverlauf.auswahl_reihenfolge", "orte.stundenverlauf.an_aus"],
        "orte.ausblick": ["orte.ausblick.auswahl_reihenfolge", "orte.ausblick.an_aus"],
        "orte.ortsfolge": ["orte.ortsfolge"],
        "trip.email_format": ["trip.email_format"],
        "orte.email_format": ["orte.email_format"],
        "trip.zusatz.etappen_kennzahlen": ["trip.zusatz.etappen_kennzahlen"],
        "trip.zusatz.vortag": ["trip.zusatz.vortag"],
        "trip.zusatz.nachtblock": ["trip.zusatz.nachtblock"],
        "orte.zusatzbloecke": ["orte.zusatzbloecke"],
        "trip.sms_schwellen": ["trip.sms_schwellen"],
        "editor.sprache": ["trip.sprache", "orte.sprache"],
        "editor.zwei_nutzer": ["trip.zwei_nutzer", "orte.zwei_nutzer"],
    },
    "validatoren": {
        "validator.trip.email_liste.auswahl": ["trip.email_liste.an_aus"],
        "validator.trip.email_liste.reihenfolge": ["trip.email_liste.reihenfolge"],
        "validator.trip.email_liste.darstellung": ["trip.email_liste.roh_einfach"],
        "validator.trip.email_liste.windrichtung": ["trip.email_liste.roh_einfach"],
        "validator.trip.grundauswahl": ["trip.grundauswahl.gespeichert", "trip.grundauswahl.bewusst_leer",
                                        "trip.kanal_liste.totalschnitt"],
        "validator.trip.metrik_flags_je_bericht": ["trip.metrik.morgen_abend"],
        "validator.trip.per_report_liste": ["trip.email_liste.je_bericht"],
        "validator.trip.ausblick.auswahl": ["trip.ausblick.auswahl_reihenfolge"],
        "validator.trip.ausblick.reihenfolge": ["trip.ausblick.auswahl_reihenfolge"],
        "validator.trip.ausblick.darstellung": ["trip.ausblick.roh_einfach"],
        "validator.trip.ausblick.zeilenzahl": ["trip.ausblick.zeilenzahl"],
        "validator.trip.ausblick.berichte": ["trip.ausblick.erscheint_im"],
        "validator.trip.ausblick.schalter": ["trip.ausblick.an_aus"],
        "validator.trip.email_format": ["trip.email_format"],
        "validator.trip.zusatz.etappen_kennzahlen": ["trip.zusatz.etappen_kennzahlen"],
        "validator.trip.zusatz.vortag": ["trip.zusatz.vortag"],
        "validator.trip.zusatz.nacht": ["trip.zusatz.nachtblock"],
        "validator.trip.metriken_ueberblick": ["trip.metriken_ueberblick"],
        "validator.trip.etappennamen": ["trip.ausblick.etappennamen"],
        "validator.trip.sprache": ["trip.sprache"],
        "validator.trip.altbestand": ["trip.grundauswahl.nie_eingestellt"],
        "validator.trip.tagesfenster": ["trip.tagesfenster"],
        "validator.orte.vergleich.auswahl": ["orte.vergleichstabelle.an_aus"],
        "validator.orte.vergleich.reihenfolge": ["orte.vergleichstabelle.reihenfolge"],
        "validator.orte.vergleich.darstellung": ["orte.vergleichstabelle.roh_einfach"],
        "validator.orte.grundauswahl": ["orte.grundauswahl.gespeichert", "orte.grundauswahl.bewusst_leer",
                                        "orte.kanal_liste.totalschnitt"],
        "validator.orte.stunden.auswahl": ["orte.stundenverlauf.auswahl_reihenfolge"],
        "validator.orte.stunden.reihenfolge": ["orte.stundenverlauf.auswahl_reihenfolge"],
        "validator.orte.stunden.schalter": ["orte.stundenverlauf.an_aus"],
        "validator.orte.stunden.darstellung": ["orte.stundenverlauf.roh_einfach"],
        "validator.orte.ausblick.auswahl_reihenfolge": ["orte.ausblick.auswahl_reihenfolge"],
        "validator.orte.ausblick.darstellung": ["orte.ausblick.roh_einfach"],
        "validator.orte.ausblick.schalter": ["orte.ausblick.an_aus"],
        "validator.orte.ausblick.zeilen_je_ort": ["orte.ausblick.zeilenzahl"],
        "validator.orte.ortsfolge": ["orte.ortsfolge"],
        "validator.orte.orte_auswahl": ["orte.orte_auswahl"],
        "validator.orte.ortsnamen": ["orte.ortsnamen"],
        "validator.orte.sprache": ["orte.sprache"],
        "validator.orte.tagesfenster": ["orte.tagesfenster"],
    },
}

# Produktbefunde aus fremdem Bereich, die einer Zelle widersprechen: nur Hinweis, kein Statuswechsel.
QUER_HINWEISE = {
    "trip.zusatz.etappen_kennzahlen|email_kompakt":
        ("B-P1", "Widerspruch: validatoren meldet Kompakt zeigt Etappen-Kennzahlen trotz Schalter aus (T21); "
                 "trip_mail führt Kompakt als ‚ignoriert Baustein-Schalter‘ (PO-Entscheidung compact.py:4-6) → Zielkonflikt klären"),
    "trip.ausblick.an_aus|email_kompakt":
        ("B-P2", "Widerspruch: validatoren meldet Kompakt zeigt Ausblick trotz show_outlook=false (T22); "
                 "trip_mail führt das als PO-Ausnahme (compact.py:4-6) → Zielkonflikt klären"),
}


def lade(bereich: str) -> dict:
    return json.loads((BASIS / f"{bereich}.json").read_text(encoding="utf-8"))


def schlechtester(stati):
    stati = [s for s in stati if s]
    return max(stati, key=lambda s: RANG[s]) if stati else None


def vereinige(texte):
    aus = []
    for t in texte:
        for teil in [x.strip() for x in (t or "").split(" ;; ")]:
            if teil and teil not in aus:
                aus.append(teil)
    return " ;; ".join(aus)


def zelle_aus(beitraege, unbelegt_notiz="von keinem Bereich belegt"):
    """beitraege: Liste (bereich, teilzeile, zelle). Ergebnis-Zelle nach Rangregel."""
    if not beitraege:
        return {"status": "ungeprueft", "beleg": "", "befund": "", "notiz": unbelegt_notiz,
                "quellen": [], "unbelegt": True}
    status = schlechtester([z["status"] for _, _, z in beitraege])
    # Belege/Befunde aller Teilzeilen vereinigen; Teilzeilen mit dem gewinnenden Status zuerst
    sortiert = sorted(beitraege, key=lambda b: -RANG[b[2]["status"]])
    return {
        "status": status,
        "beleg": vereinige(z.get("beleg", "") for _, _, z in sortiert),
        "befund": vereinige(z.get("befund", "") for _, _, z in sortiert if z.get("befund")),
        "notiz": vereinige(f"[{t}] {z['notiz']}" if z.get("notiz") else "" for _, t, z in sortiert),
        "quellen": [f"{b}:{t}={z['status']}" for b, t, z in sortiert],
        "unbelegt": False,
    }


def validator_status(z: dict) -> dict:
    """Validator-Zeile -> eine Zelle: schlechtester Status ueber email_html/text/kompakt (ohne n/a, ausser alle n/a)."""
    teile = [z["zellen"][k] for k in ("email_html", "email_text", "email_kompakt")]
    stati = [c["status"] for c in teile if c["status"] != "nicht_anwendbar"] or ["nicht_anwendbar"]
    return {
        "status": schlechtester(stati),
        "beleg": vereinige(c.get("beleg", "") for c in teile),
        "befund": vereinige(c.get("befund", "") for c in teile if c.get("befund")),
        "notiz": vereinige(c.get("notiz", "") for c in teile),
    }


def befunde_lesen():
    """Eine Zeile je Befund aus allen *_befunde.md."""
    kopf = re.compile(r"^#{2,4}\s+(B-[A-Z]+-?\d+|E\d+)\s*[—–·-]+\s*(.*)$")
    tl = re.compile(r"^\|\s*(TL\d+)\s+\|\s(.*)\s\|\s*$")
    liste = []
    # Bereich "luecken" (Lueckenschluss) liefert nur Befunde und status_updates.json, keine Teilzeilen.
    for bereich in BEREICHE + ["luecken"]:
        pfad = BASIS / f"{bereich}_befunde.md"
        if not pfad.exists():
            continue
        zeilen = pfad.read_text(encoding="utf-8").splitlines()
        for i, z in enumerate(zeilen):
            m = kopf.match(z)
            if m:
                bid, titel = m.group(1), m.group(2).strip()
                schwere = ""
                ms = re.search(r"Schwere:\s*([^·*]+)", titel)
                if ms:
                    schwere = ms.group(1).strip()
                else:
                    mo = re.match(r"(hoch|mittel|niedrig[^·]*)\s*·\s*(.*)$", titel)
                    if mo:
                        schwere, titel = mo.group(1).strip(), mo.group(2).strip()
                    mk = re.search(r"\((hoch|mittel|niedrig)\)\s*$", titel)
                    if mk:
                        schwere = mk.group(1)
                if not schwere:
                    for folge in zeilen[i + 1:i + 6]:
                        mf = re.search(r"\*\*Schwere:\*\*\s*([^.(]+)", folge)
                        if mf:
                            schwere = mf.group(1).strip()
                            break
                ende = next((j for j in range(i + 1, len(zeilen)) if zeilen[j].startswith("#")), len(zeilen))
                block = "\n".join(zeilen[i:ende])
                zielkonflikt = "Zielkonflikt" in block and not re.search(r"kein(en)? Zielkonflikt", block)
                titel = re.sub(r"\s*·\s*Schwere:.*$", "", titel)
                titel = re.sub(r"\s*\((hoch|mittel|niedrig)\)\s*$", "", titel)
                liste.append({"id": bid, "bereich": bereich, "schwere": schwere or "–",
                              "titel": titel.replace("**", "").strip(), "zielkonflikt": zielkonflikt})
                continue
            m = tl.match(z)
            if m:
                mutation, _, wirkung = m.group(2).partition(" | ")
                liste.append({"id": m.group(1), "bereich": bereich, "schwere": "Testlücke",
                              "titel": f"{mutation.strip()} ⇒ {wirkung.strip()}", "zielkonflikt": False})
    return liste


def main():
    daten = {b: lade(b) for b in BEREICHE}
    kanon = OrderedDict((k, {"id": k, "kontext": k.split(".")[0], "gruppe": g, "einstellung": e,
                             "teilzeilen": [], "gesetzt_in": [], "gespeichert_als": []})
                        for k, g, e in KANON)
    warnungen = []

    # Abbildungstabelle pruefen
    for b, tab in ABBILDUNG.items():
        ids = {z["id"] for z in daten[b]["zeilen"]}
        for tid, ziele in tab.items():
            if tid not in ids:
                warnungen.append(f"Abbildung {b}:{tid} existiert nicht in {b}.json")
            for k in ziele:
                if k not in kanon:
                    raise SystemExit(f"Abbildung {b}:{tid} -> unbekannte kanonische Zeile {k}")

    # Beitraege einsammeln: beitraege[kanon][spalte] -> [(bereich, teilzeile, zelle)]
    beitraege = {k: {s: [] for s in SPALTEN} for k in kanon}
    for b in BEREICHE:
        for z in daten[b]["zeilen"]:
            ziele = ABBILDUNG.get(b, {}).get(z["id"])
            if not ziele:  # Restzeile -> eigene kanonische Zeile, nichts geht verloren
                rest_id = f"rest.{b}.{z['id']}"
                kontext = z.get("kontext", "?")
                kanon[rest_id] = {"id": rest_id, "kontext": kontext.split("|")[0], "gruppe": "Restzeilen",
                                  "einstellung": z["einstellung"], "teilzeilen": [],
                                  "gesetzt_in": [], "gespeichert_als": []}
                beitraege[rest_id] = {s: [] for s in SPALTEN}
                ziele = [rest_id]
                warnungen.append(f"Restzeile {b}:{z['id']} -> {rest_id}")
            for k in ziele:
                kanon[k]["teilzeilen"].append(f"{b}:{z['id']}")
                for feld in ("gesetzt_in", "gespeichert_als"):
                    if z.get(feld) and z[feld] not in kanon[k][feld]:
                        kanon[k][feld].append(z[feld])
                if b == "validatoren":
                    beitraege[k]["validator_email"].append((b, z["id"], validator_status(z)))
                else:
                    for s in AUSGABE:
                        beitraege[k][s].append((b, z["id"], z["zellen"][s]))

    updates_pfad = BASIS / "status_updates.json"
    updates = json.loads(updates_pfad.read_text(encoding="utf-8")) if updates_pfad.exists() else {}

    zeilen_aus = []
    for k, meta in kanon.items():
        kontext = meta["kontext"]
        zellen = {}
        for s in SPALTEN:
            alle = beitraege[k][s]
            zust = zustaendig(s, kontext)
            eigen = [b for b in alle if b[0] == zust]
            zelle = zelle_aus(eigen, unbelegt_notiz=f"zuständiger Bereich {zust} hat keine Teilzeile")
            if zelle["status"] == "ungeprueft" and s != "validator_email":
                fremd = [b for b in alle if b[0] != zust and b[0] != "validatoren"
                         and b[2]["status"] != "ungeprueft"]
                if fremd:
                    ersatz = zelle_aus(fremd)
                    ersatz["notiz"] = vereinige([f"Ersatzbeleg aus anderem Bereich ({zust} ungeprüft)",
                                                 ersatz["notiz"]])
                    ersatz["ersatz_aus"] = sorted({b[0] for b in fremd})
                    zelle = ersatz
            if s == "validator_email" and zelle.get("unbelegt"):
                # keine Validator-Zeile: n/a, wenn die E-Mail die Einstellung gar nicht traegt
                email = [zellen[x]["status"] for x in ("email_html", "email_text", "email_kompakt")]
                if all(x == "nicht_anwendbar" for x in email):
                    zelle = {"status": "nicht_anwendbar", "beleg": "", "befund": "",
                             "notiz": "E-Mail trägt die Einstellung nicht", "quellen": [], "unbelegt": False}
                else:
                    zelle["notiz"] = "keine Validator-Zeile für diese Einstellung"
            q = QUER_HINWEISE.get(f"{k}|{s}")
            if q:
                zelle["querbefund"] = q[0]
                zelle["notiz"] = vereinige([zelle["notiz"], q[1]])
            u = updates.get(f"{k}|{s}")
            if u:
                zelle = dict(zelle, **{f: u[f] for f in ("status", "beleg", "notiz") if f in u},
                             aktualisiert=True, unbelegt=False)
                if "befund" in u:
                    zelle["befund"] = u["befund"]
            assert zelle["status"] in RANG, (k, s, zelle["status"])
            zellen[s] = zelle
        zeilen_aus.append({"id": k, "kontext": kontext, "gruppe": meta["gruppe"],
                           "einstellung": meta["einstellung"], "gesetzt_in": meta["gesetzt_in"],
                           "gespeichert_als": meta["gespeichert_als"], "teilzeilen": meta["teilzeilen"],
                           "zellen": zellen})

    unbekannte_updates = [u for u in updates if u.split("|")[0] not in kanon or u.split("|")[-1] not in SPALTEN]
    warnungen += [f"status_updates: unbekannter Schlüssel {u}" for u in unbekannte_updates]

    # Vollstaendigkeit: jede Teilzeile steckt in mindestens einer kanonischen Zeile
    erfasst = {t for z in zeilen_aus for t in z["teilzeilen"]}
    for b in BEREICHE:
        for z in daten[b]["zeilen"]:
            assert f"{b}:{z['id']}" in erfasst, f"Teilzeile verloren: {b}:{z['id']}"

    gesamt = Counter(z["zellen"][s]["status"] for z in zeilen_aus for s in SPALTEN)
    ausgabe = Counter(z["zellen"][s]["status"] for z in zeilen_aus for s in AUSGABE)
    je_spalte = {s: dict(Counter(z["zellen"][s]["status"] for z in zeilen_aus)) for s in SPALTEN}
    ungeprueft = [{"id": z["id"], "spalten": [s for s in SPALTEN if z["zellen"][s]["status"] == "ungeprueft"],
                   "davon_unbelegt": [s for s in SPALTEN if z["zellen"][s].get("unbelegt")]}
                  for z in zeilen_aus if any(z["zellen"][s]["status"] == "ungeprueft" for s in SPALTEN)]
    befunde = befunde_lesen()

    kopf = {
        "stand": _dt.datetime.now().isoformat(timespec="seconds"),
        "quellen": {b: {"datei": f"{b}.json", "teilzeilen": len(daten[b]["zeilen"]),
                        "befunde": f"{b}_befunde.md"} for b in BEREICHE}
                   | ({"status_updates": {"datei": "status_updates.json", "eintraege": len(updates)}} if updates else {}),
        "spalten": SPALTEN,
        "zustaendigkeit": {"email_*": "trip_mail (Trip) / orte_mail (Orte)", "telegram|sms|premium_sms": "kanaele",
                           "einstellungsseite": "editor",
                           "validator_email": "validatoren (schlechtester Status über email_html/text/kompakt)"},
        "rangfolge": "rot > ungeprueft > ausgelagert > gruen > nicht_anwendbar",
        "statuslegende": LEGENDE,
        "zaehlung": {
            "kanonische_zeilen": len(zeilen_aus),
            "zellen_gesamt": sum(gesamt.values()),
            "je_status_gesamt": dict(gesamt),
            "je_status_ausgabe_spalten": dict(ausgabe),
            "je_spalte": je_spalte,
            "ungeprueft_zellen": gesamt.get("ungeprueft", 0),
            "ungeprueft_davon_unbelegt": sum(len(u["davon_unbelegt"]) for u in ungeprueft),
            "befunde": len(befunde),
        },
        "warnungen": warnungen,
    }
    matrix = dict(kopf, zeilen=zeilen_aus, ungeprueft=ungeprueft, befunde=befunde)
    (ZIEL / "inventar_matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=1), encoding="utf-8")
    (ZIEL / "inventar_matrix.md").write_text(markdown(matrix), encoding="utf-8")
    status_pfad = BASIS / "befund_status.json"
    if status_pfad.exists():
        (ZIEL / "runde7_befunde.md").write_text(
            befunde_markdown(befunde, json.loads(status_pfad.read_text(encoding="utf-8"))), encoding="utf-8")
    print(json.dumps(kopf["zaehlung"], ensure_ascii=False))
    for w in warnungen:
        print("WARNUNG:", w)


def _zelle_md(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def befunde_markdown(befunde: list, stand: dict) -> str:
    """Eine Zeile je Befund: ID, Schwere, Kurztext, Status, Test/Issue."""
    je = stand.get("befunde", {})
    fehlend = [b["id"] for b in befunde if b["id"] not in je]
    if fehlend:
        raise SystemExit(f"befund_status.json: Status fehlt fuer {fehlend}")
    zeilen = [(b["id"], b["schwere"], b["titel"], je[b["id"]]["status"], je[b["id"]]["beleg"]) for b in befunde]
    zeilen += [(z["id"], z["schwere"], z["titel"], z["status"], z["beleg"]) for z in stand.get("zusatz", [])]
    zaehlung = Counter(z[3] for z in zeilen)
    out = ["# Befunde Runde 7 (#3047)", "",
           "Status nach den Behebungspaketen: " + " · ".join(f"{s} {n}" for s, n in sorted(zaehlung.items())) + ".",
           "Quelle: `inventar/*_befunde.md` und `inventar/befund_status.json`, erzeugt mit `inventar/konsolidieren.py`.",
           "", "| ID | Schwere | Kurztext | Status | Test/Issue |", "|---|---|---|---|---|"]
    out += ["| " + " | ".join(_zelle_md(x) for x in z) + " |" for z in zeilen]
    return "\n".join(out) + "\n"


def zelltext(z: dict) -> str:
    sym = KUERZEL[z["status"]] + ("·" if z.get("unbelegt") else "")
    ids = [x for x in (z.get("befund") or "").split(" ;; ") if x]
    if z.get("querbefund"):
        ids.append(f"({z['querbefund']})")
    if z.get("aktualisiert"):
        sym += "*"
    return sym + (" " + ",".join(ids) if ids and z["status"] != "nicht_anwendbar" else
                  (" " + ",".join(i for i in ids if i.startswith("(")) if any(i.startswith("(") for i in ids) else ""))


def markdown(m: dict) -> str:
    kurz = {"email_html": "HTML", "email_text": "Text", "email_kompakt": "Kompakt", "telegram": "Telegram",
            "sms": "SMS", "premium_sms": "Premium", "einstellungsseite": "Editor", "validator_email": "Validator"}
    z = m["zaehlung"]
    out = [
        "# Inventar-Matrix „Einstellung = Ausgabe“ (#3047, Runde 7)", "",
        f"Stand {m['stand']} · {z['kanonische_zeilen']} kanonische Zeilen · {z['zellen_gesamt']} Zellen · "
        + " · ".join(f"{KUERZEL[s]} {s} {n}" for s, n in sorted(z["je_status_gesamt"].items(), key=lambda x: -RANG[x[0]])),
        "",
        "Quellen: " + ", ".join(f"`{q['datei']}`" for q in m["quellen"].values())
        + ". Erzeugt mit `konsolidieren.py` (Abbildungstabelle im Skript).", "",
    ]
    for kontext, titel in (("trip", "Trip"), ("orte", "Orts-Vergleich")):
        out += [f"## {titel}", "", "| Einstellung | " + " | ".join(kurz[s] for s in SPALTEN) + " |",
                "|---|" + "---|" * len(SPALTEN)]
        gruppe = None
        for zl in m["zeilen"]:
            if zl["kontext"] != kontext:
                continue
            if zl["gruppe"] != gruppe:
                gruppe = zl["gruppe"]
                out.append(f"| **{gruppe}** |" + " |" * len(SPALTEN))
            out.append(f"| {zl['einstellung']} <sub>`{zl['id']}`</sub> | "
                       + " | ".join(zelltext(zl["zellen"][s]) for s in SPALTEN) + " |")
        out.append("")
    rest = [zl for zl in m["zeilen"] if zl["kontext"] not in ("trip", "orte")]
    if rest:
        out += ["## Sonstige", ""] + [f"- `{zl['id']}` {zl['einstellung']}" for zl in rest] + [""]
    out += ["## Legende", ""] + [f"- {v}" for v in m["statuslegende"].values()] + [
        "- `·` hinter dem Kürzel: der zuständige Bereich hat für diese Einstellung keine Teilzeile (unbelegt)",
        "- `*` hinter dem Kürzel: per `status_updates.json` nach Behebung überschrieben",
        "- `(B-Px)`: Produktbefund eines anderen Bereichs widerspricht der Zelle (Status unverändert, Zielkonflikt)",
        "- Spalte Validator: prüft der Mail-Validator die Einstellung? (✗ = Abweichung bleibt unerkannt)",
        f"- Rangfolge bei mehreren Teilzeilen: {m['rangfolge']}", "",
        "## Befunde", "",
    ]
    for b in m["befunde"]:
        zk = " · Zielkonflikt erwähnt" if b["zielkonflikt"] else ""
        out.append(f"- **{b['id']}** ({b['bereich']}, {b['schwere']}{zk}): {b['titel']}")
    out += ["", f"## Offen „ungeprüft“ ({z['ungeprueft_zellen']} Zellen, davon {z['ungeprueft_davon_unbelegt']} unbelegt)", ""]
    for u in m["ungeprueft"]:
        out.append(f"- `{u['id']}`: " + ", ".join(kurz[s] + ("·" if s in u["davon_unbelegt"] else "") for s in u["spalten"]))
    if m["warnungen"]:
        out += ["", "## Warnungen", ""] + [f"- {w}" for w in m["warnungen"]]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
