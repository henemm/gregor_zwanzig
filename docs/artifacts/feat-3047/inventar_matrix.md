# Inventar-Matrix „Einstellung = Ausgabe“ (#3047, Runde 7)

Stand 2026-11-17T00:36:09 · 121 kanonische Zeilen · 968 Zellen · ✗ rot 17 · ↗ ausgelagert 61 · ✓ gruen 519 · – nicht_anwendbar 371

Quellen: `trip_mail.json`, `orte_mail.json`, `kanaele.json`, `editor.json`, `validatoren.json`, `status_updates.json`. Erzeugt mit `konsolidieren.py` (Abbildungstabelle im Skript).

## Trip

| Einstellung | HTML | Text | Kompakt | Telegram | SMS | Premium | Editor | Validator |
|---|---|---|---|---|---|---|---|---|
| **Grundauswahl** | | | | | | | | |
| Grundauswahl gespeichert: Metrik an/aus <sub>`trip.grundauswahl.gespeichert`</sub> | ✓ | ✓ | ✓ | ✓* | ✓* | ✓* | ✓* E7 | ✓ |
| Grundauswahl: Reihenfolge <sub>`trip.grundauswahl.reihenfolge`</sub> | ✓ | ✓ | ✓ | ✓* | ✓* | ✓* | –* | ✓* |
| Grundauswahl nie eingestellt (Feld fehlt) / Altbestand = Vorgabe <sub>`trip.grundauswahl.nie_eingestellt`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* E1 | ✓ |
| Grundauswahl bewusst leer <sub>`trip.grundauswahl.bewusst_leer`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓ | ✓ |
| Grundauswahl Altformat (Zeichenkette / ohne enabled) <sub>`trip.grundauswahl.altformat`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* E3 | ✓* B-L6 |
| Metrik per „+“ / Vorlage wieder eingeschaltet (hinten angehängt) <sub>`trip.grundauswahl.wieder_eingeschaltet`</sub> | ✓* B-TM2 | ✓* B-TM2 | ✓* B-TM2 | ✓* B-TM2 | ✓* B-TM2 | ✓* B-TM2 | ✓* B-TM2 | ✓* B-TM2 |
| Global nachträglich eingeschaltete Metrik in bearbeiteter Liste <sub>`trip.grundauswahl.nachtraeglich_global`</sub> | ↗ #3065 | ↗ #3065 | ↗ #3065 | ↗* #3065 | ↗* #3065 | ↗* #3065 | ↗ #3065 | ↗* #3065 |
| Morgen/Abend je Metrik <sub>`trip.metrik.morgen_abend`</sub> | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓* | ✓ |
| **E-Mail-Liste** | | | | | | | | |
| E-Mail-Liste: Zeile an/aus <sub>`trip.email_liste.an_aus`</sub> | ✓ | ✓ | ✓ | –* | –* | –* | ✓ | ✓ |
| E-Mail-Liste: Reihenfolge <sub>`trip.email_liste.reihenfolge`</sub> | ✓ | ✓ | ✓ | –* | –* | –* | ✓ | ✓ B-V8 |
| E-Mail-Liste: Roh/Einfach je Zeile (inkl. Windrichtung) <sub>`trip.email_liste.roh_einfach`</sub> | ✓ | ✓ | – | –* | –* | –* | ✓ | ✓ |
| Kanal-Liste je Bericht (Morgen/Abend) <sub>`trip.email_liste.je_bericht`</sub> | ✓ | ✓ | ✓ | –* | –* | –* | ↗ #3065 | ✓ |
| Metriken-Überblick folgt der E-Mail-Liste <sub>`trip.metriken_ueberblick`</sub> | ✓* | ✓* | ✓* | –* | –* | –* | –* | ✗* B-L5 |
| **Telegram-Liste** | | | | | | | | |
| Telegram-Liste: Zeile an/aus <sub>`trip.telegram_liste.an_aus`</sub> | – | – | – | ✓ | – | – | ✓ | – |
| Telegram-Liste: Reihenfolge <sub>`trip.telegram_liste.reihenfolge`</sub> | – | – | – | ✓ | – | – | ✓ | – |
| Telegram-Liste: Roh/Einfach je Zeile <sub>`trip.telegram_liste.roh_einfach`</sub> | – | – | – | ✓ | – | – | ✓ | – |
| Telegram-Liste: Windrichtung Roh (#3063 P2) <sub>`trip.telegram_liste.windrichtung_roh`</sub> | – | – | – | ✓* B-K1 | – | – | ✓ | – |
| Telegram-Schnittlinie (erste 7) <sub>`trip.telegram.schnittlinie`</sub> | – | – | – | ↗* B-K5 | – | – | ↗* #3032 | – |
| **SMS-Liste** | | | | | | | | |
| SMS-Liste: Zeile an/aus <sub>`trip.sms_liste.an_aus`</sub> | – | – | – | – | ✓ | ↗ | ✓ | – |
| SMS-Liste: Reihenfolge <sub>`trip.sms_liste.reihenfolge`</sub> | – | – | – | – | ✓ | ↗ | ✓ | – |
| SMS-Liste: Roh/Einfach <sub>`trip.sms_liste.roh_einfach`</sub> | – | – | – | – | ✓ | ↗ | ✓ | – |
| SMS 160 Zeichen: was zuerst wegfällt <sub>`trip.sms.kuerzung`</sub> | – | – | – | – | ✓* B-K4 | ✓* B-K4 | ↗* #3032 | – |
| **Premium-SMS-Liste** | | | | | | | | |
| Premium-SMS eigene Liste (N2) <sub>`trip.premium_sms_liste`</sub> | – | – | – | – | – | ↗ | ↗ #3031 | – |
| **Kanal-Listen** | | | | | | | | |
| Kanal-Liste nie eingestellt (Altbestand) <sub>`trip.kanal_liste.nie_eingestellt`</sub> | – | – | – | ✓ | ✓ | ✓ | ✓* | – |
| Kanal-Liste bewusst leer <sub>`trip.kanal_liste.bewusst_leer`</sub> | – | – | – | ✓ | ✓ | ✓ | ✓* | – |
| Totalschnitt: Kanal-Liste ∩ Grundauswahl leer <sub>`trip.kanal_liste.totalschnitt`</sub> | – | – | – | ✓ | ✓ | ✓ | ✓* | ✓ |
| **Ausblick** | | | | | | | | |
| 3-Tages-Ausblick: Auswahl + Reihenfolge <sub>`trip.ausblick.auswahl_reihenfolge`</sub> | ✓ | ✓ | ✓ | ✓ | – | – | ✓ | ✓ |
| 3-Tages-Ausblick: Roh/Einfach <sub>`trip.ausblick.roh_einfach`</sub> | ✓ | ✓ | ✓ | ✓ | – | – | ✓* | ✓ |
| 3-Tages-Ausblick: erscheint im Morgen/Abend (Mehrtages-Trend) <sub>`trip.ausblick.erscheint_im`</sub> | ✓ | ✓ | ✓ | ✓* | –* | –* | ✓* E2 | ✓* |
| 3-Tages-Ausblick an/aus (show_outlook) <sub>`trip.ausblick.an_aus`</sub> | ✓ | ✓ | – (B-P2) | –* | –* | –* | ✓* | ✓ B-P2 |
| 3-Tages-Ausblick: drei Tageszeilen <sub>`trip.ausblick.zeilenzahl`</sub> | ✓* | ✓* | ✓* | ✓* | –* | –* | –* | ✓* B-V1 |
| Etappennamen (Sonderzeichen, überlang) im Ausblick <sub>`trip.ausblick.etappennamen`</sub> | ✓* | ✓* | ✓* | ✓* | –* | –* | –* | ✓* |
| **Zusatzblöcke** | | | | | | | | |
| Zusatzblock Etappen-Kennzahlen (W17) <sub>`trip.zusatz.etappen_kennzahlen`</sub> | ✓ | ✓ | – (B-P1) | – | – | – | ✓* E8 | ✓* B-V2 |
| Zusatzblock Vortag-Vergleich (W18) <sub>`trip.zusatz.vortag`</sub> | ✓ | ✓ | – | – | – | – | ✓* E8 | ✓* B-V2 |
| Zusatzblock Nacht-Stundentabelle (W22) <sub>`trip.zusatz.nachtblock`</sub> | ✓ | ✓ | – | – | – | – | ✓ | ✓ |
| **Format** | | | | | | | | |
| E-Mail-Format Ausführlich/Kompakt (W15) <sub>`trip.email_format`</sub> | ✓ | ✓ | ✓ | – | – | – | ✓ | ✓* |
| Tagesfenster von–bis (W12) <sub>`trip.tagesfenster`</sub> | ✓ | ✓ | ✓ | ✓* B-L1 | ✓ | ✓ | ✓* E5 | ✗* B-V5 |
| **Warnungen/Alarm** | | | | | | | | |
| Amtliche Warnungen an/aus (W20) <sub>`trip.amtliche_warnungen.schalter`</sub> | ✓ B-TM3 | ✓ B-TM3 | ✓ B-TM3 | ✓* | ✓* | ✓* | ✗* E4 | ✗* B-L5 |
| Amtliche Warnungen feste erste Zeile (WV6) <sub>`trip.amtliche_warnungen.position`</sub> | ✓ | ✓ | ✓* B-TM1 | ✓ | ✓ | ✓ | ↗* #3031 | ✗* B-L5 |
| Amtliche Warnung fällt beim Kürzen zuletzt weg <sub>`trip.amtliche_warnungen.kuerzung_zuletzt`</sub> | – | – | – | – | ✓ | ✓ | ↗* #3031 | – |
| Radar-Regen-Alarm (N1) <sub>`trip.radar`</sub> | ↗* #2800 | ↗* #2800 | ↗* #2800 | ↗* #2800 | ↗* #2800 | ↗* #2800 | ↗ #2800 | ↗* #2800 |
| Ampel-Grenzen ändern <sub>`trip.ampel.grenzen`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✗* B-L5 |
| Alarm ab je Metrik / für alle <sub>`trip.ampel.alarm_ab`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* | –* |
| SMS-Schwellen je Metrik <sub>`trip.sms_schwellen`</sub> | –* | –* | –* | –* | –* | –* | – | –* |
| **Telegram-Kurzstil** | | | | | | | | |
| Telegram-Kurzstil: Briefing <sub>`trip.telegram_kurzstil.briefing`</sub> | – | – | – | ✓ | – | – | ✓ | – |
| Telegram-Kurzstil: Alarm <sub>`trip.telegram_kurzstil.alarm`</sub> | – | – | – | ✓ | – | – | ✓ | – |
| **Sprache** | | | | | | | | |
| Sprache DE/EN (Kopf, Spalten, Kürzel sprachfest) <sub>`trip.sprache`</sub> | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Sprache EN: Telegram-Kappungshinweis <sub>`trip.sprache.kappungshinweis`</sub> | –* | –* | –* | ✓* B-K2 | – | – | –* | –* |
| Kürzel-Legende (W21) <sub>`trip.kuerzel_legende`</sub> | –* | –* | –* | ↗ B-K9 | ↗ B-K9 | ↗ B-K9 | ↗* #3032 | –* |
| **Vorlagen** | | | | | | | | |
| Vorlage übernehmen/zurücksetzen (Ampel, abgeleitete Größen) <sub>`trip.vorlage.anwenden`</sub> | ✓ | – | ✓ | ✓* | ✓* | ✓* | ✓* E7 | ✗* B-L5 |
| Neuer Trip übernimmt eigene Standard-Vorlage <sub>`trip.vorlage.neu_aus_standard`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓ | ✗* B-L5 |
| Als eigene Vorlage speichern <sub>`trip.vorlage.eigene_speichern`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✗* B-L5 |
| **Zeiten/Versand** | | | | | | | | |
| Uhrzeit Morgen-/Abend-Briefing <sub>`trip.zeiten`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓ | –* |
| Morgen-/Abend-Briefing an/aus <sub>`trip.slots`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓ | –* |
| Briefing je Kanal <sub>`trip.briefing_kanaele`</sub> | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* TL7 | –* |
| Alarme je Kanal <sub>`trip.alarm_kanaele`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* TL5 | –* |
| Alarm ab Dringlichkeit je Kanal <sub>`trip.dringlichkeit`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓ | –* |
| Stille Stunden <sub>`trip.stille_stunden`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* TL2 | –* |
| Mindestabstand zwischen Alarmen <sub>`trip.cooldown`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓ | –* |
| **Mandanten** | | | | | | | | |
| Zwei Nutzer: eigene Konfiguration/Sprache/Empfänger <sub>`trip.zwei_nutzer`</sub> | ✓ | ✓ | ✓* | ✓ | ✓ | ✓ | ✓ | ✓* |

## Orts-Vergleich

| Einstellung | HTML | Text | Kompakt | Telegram | SMS | Premium | Editor | Validator |
|---|---|---|---|---|---|---|---|---|
| **Grundauswahl** | | | | | | | | |
| Grundauswahl gespeichert (Liste, Folge ≠ Katalog) <sub>`orte.grundauswahl.gespeichert`</sub> | ✓ | ✓ | – | ✓* | ✓* | ✓* | ✓ | ✓ |
| Grundauswahl nie eingestellt (active_metrics fehlt) <sub>`orte.grundauswahl.nie_eingestellt`</sub> | ✓ | ✓ | – | ✓* B-L4 | ✓* B-L4 | ✓* B-L4 | ✓* E1 | ✗* B-L5 |
| Grundauswahl bewusst leer (active_metrics = []) <sub>`orte.grundauswahl.bewusst_leer`</sub> | ✓ | ✓ | – | ✓* | ✓* | ✓* | ✓ | ✓ |
| Altbestand ohne neue Felder (Golden) <sub>`orte.grundauswahl.altformat`</sub> | ✓ | ✓ | – | ✓* | ✓* | ✓* | ✓* | ✓* |
| Vorlagen-Metrik ohne Vergleichs-Pendant (Tiefsttemp. Nacht) <sub>`orte.grundauswahl.vorlagen_metrik_ohne_pendant`</sub> | ✓* E6 | ✓* E6 | –* | ✓* E6 | ✓* E6 | ✓* E6 | ✓* E6 | ✓* E6 |
| Morgen/Abend je Metrik <sub>`orte.grundauswahl.morgen_abend`</sub> | – | – | – | – | – | – | – | – |
| **Vergleichstabelle** | | | | | | | | |
| Vergleichstabelle (E-Mail-Liste): Zeile an/aus <sub>`orte.vergleichstabelle.an_aus`</sub> | ✓ | ✓ | – | – | – | – | ✓ | ✓ |
| Vergleichstabelle: Reihenfolge (Warnungen fest zuerst) <sub>`orte.vergleichstabelle.reihenfolge`</sub> | ✓ | ✓ | – | – | – | – | ✓ | ✓ |
| Vergleichstabelle: Roh/Einfach je Zeile (W11) <sub>`orte.vergleichstabelle.roh_einfach`</sub> | ✓ | ✓ | – | – | – | – | ↗ #3031 | ✓* B-V3 |
| **Telegram-Liste** | | | | | | | | |
| Telegram-Liste: Zeile an/aus <sub>`orte.telegram_liste.an_aus`</sub> | – | – | – | ✓ | – | – | ↗ #3031 | – |
| Telegram-Liste: Reihenfolge <sub>`orte.telegram_liste.reihenfolge`</sub> | – | – | – | ✓ | – | – | ↗ #3031 | – |
| Telegram-Liste: Roh/Einfach je Zeile <sub>`orte.telegram_liste.roh_einfach`</sub> | – | – | – | ✓ B-K8 | – | – | ↗ #3031 | – |
| Telegram-Liste: Windrichtung Roh/Einfach (#3063 P2) <sub>`orte.telegram_liste.windrichtung_roh`</sub> | – | – | – | ✓ | – | – | ↗ #3031 | – |
| Telegram-Schnittlinie (7 je Ort) <sub>`orte.telegram.schnittlinie`</sub> | – | – | – | ✓* B-K5 | – | – | ↗* #3032 | – |
| **SMS-Liste** | | | | | | | | |
| SMS-Liste: Zeile an/aus <sub>`orte.sms_liste.an_aus`</sub> | – | – | – | – | ✓ | ↗ | ↗ #3031 | – |
| SMS-Liste: Reihenfolge <sub>`orte.sms_liste.reihenfolge`</sub> | – | – | – | – | ✓ | ↗ | ↗ #3031 | – |
| SMS-Liste: Roh/Einfach <sub>`orte.sms_liste.roh_einfach`</sub> | – | – | – | – | ✓ | ↗ | ↗ #3031 | – |
| SMS 153/160 Zeichen: Kürzung <sub>`orte.sms.kuerzung`</sub> | – | – | – | – | ✓ | ✓ | ↗* #3032 | – |
| **Premium-SMS-Liste** | | | | | | | | |
| Premium-SMS eigene Liste (N2) <sub>`orte.premium_sms_liste`</sub> | – | – | – | – | – | ↗ | ↗ #3031 | – |
| **Kanal-Listen** | | | | | | | | |
| Altformat channel_active_metrics <sub>`orte.kanal_liste.altformat`</sub> | – | – | – | ✓ | ✓ | ↗ | ↗* #3031 | – |
| Kanal-Liste bewusst leer <sub>`orte.kanal_liste.bewusst_leer`</sub> | – | – | – | ✓* B-K6 | ✓* B-K6 | ✓* B-K6 | ↗* #3031 | – |
| Totalschnitt: Liste ∩ Grundauswahl leer <sub>`orte.kanal_liste.totalschnitt`</sub> | ✓ | ✓ | – | ✓ | ✓ | ✓ | ↗* #3031 | ✓ |
| **Stundenverlauf** | | | | | | | | |
| Stundenverlauf: Auswahl + Reihenfolge <sub>`orte.stundenverlauf.auswahl_reihenfolge`</sub> | ✓ | ✓ | – | – | – | – | ✓ | ✓* B-V4 |
| Stundenverlauf an/aus (WV8) <sub>`orte.stundenverlauf.an_aus`</sub> | ✓ | ✓ | – | – | – | – | ✓ | ✓ |
| Stundenverlauf: gesperrte Größen (WV9) <sub>`orte.stundenverlauf.gesperrt`</sub> | ✓ | ✓ | – | – | – | – | ✓* | ✓* |
| Stundenverlauf: Roh/Einfach (W11) <sub>`orte.stundenverlauf.roh_einfach`</sub> | ↗* B-OM-5 | ↗* B-OM-5 | – | – | – | – | ↗* B-OM-5 | –* |
| **Ausblick** | | | | | | | | |
| 3-Tages-Ausblick: Auswahl + Reihenfolge <sub>`orte.ausblick.auswahl_reihenfolge`</sub> | ✓ | ✓ | – | ✓* B-K7 | – | – | ✓ | ✓ |
| 3-Tages-Ausblick: Roh/Einfach <sub>`orte.ausblick.roh_einfach`</sub> | ✓ | ✓ | – | ✓* B-K7 | –* | –* | ✓* | ✓ |
| 3-Tages-Ausblick an/aus <sub>`orte.ausblick.an_aus`</sub> | ✓ | ✓ | – | ✓* B-K7 | –* | –* | ✓ | ✓ |
| 3-Tages-Ausblick: erscheint im Morgen/Abend <sub>`orte.ausblick.erscheint_im`</sub> | – | – | – | –* | –* | –* | –* | – |
| 3-Tages-Ausblick: drei Zeilen je Ort <sub>`orte.ausblick.zeilenzahl`</sub> | ✓* | ✓* | –* | ✓* B-K7 | –* | –* | –* | ✓* B-V1 |
| **Orte** | | | | | | | | |
| Ortsfolge <sub>`orte.ortsfolge`</sub> | ✓ | ✓ | – | ✓* | ✓* | ✓* | ✓* | ✓ |
| Orte im Briefing (Ort fehlt) <sub>`orte.orte_auswahl`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* | ✓ |
| Ortsnamen mit Sonderzeichen <sub>`orte.ortsnamen`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* | ✓ |
| **Zusatzblöcke** | | | | | | | | |
| Zusatzblöcke <sub>`orte.zusatzbloecke`</sub> | –* | –* | –* | –* | –* | –* | – | –* |
| **Format** | | | | | | | | |
| E-Mail-Format Ausführlich/Kompakt <sub>`orte.email_format`</sub> | – | – | – | – | – | – | – | – |
| Tagesfenster von–bis (W12, über Mitternacht) <sub>`orte.tagesfenster`</sub> | ✓ B-OM-6 | ✓ B-OM-6 | – | ✓* | ✓* | ✓* | ✓* TL6 | ✓* B-V5 |
| Morgen-Briefing = heute, Abend = morgen (V8) <sub>`orte.morgen_abend_briefing`</sub> | ✓ B-OM-6 | ✓ B-OM-6 | – | ✓* | ✓* | ✓* | ✓* | ✗* B-L5 |
| **Warnungen/Alarm** | | | | | | | | |
| Amtliche Warnungen an/aus <sub>`orte.amtliche_warnungen.schalter`</sub> | ✓* B-OM-2 | ✓ B-OM-6 | – | ✓* | ✓* | ✓* | ✗* E4 | ✓* B-OM-2 |
| Amtliche Warnungen zuerst (WV6) <sub>`orte.amtliche_warnungen.position`</sub> | ✓ | ✓ | – | ✓ | ✓ | ✓ | ↗* #3031 | ✓* |
| Warnung eines weiteren Ortes beim Kürzen <sub>`orte.amtliche_warnungen.kuerzung_zuletzt`</sub> | – | – | – | ✓ | ✓* B-K3 | ✓* B-K3 | ↗* #3031 | – |
| Hinweis „Warnungen nicht abrufbar“ <sub>`orte.amtliche_warnungen.nicht_abrufbar`</sub> | ✓ | ✓* B-OM-1 | – | ✓* B-L2 | ✓* B-L2 | ✓* B-L2 | –* | ✗* B-L5 |
| Radar-Regen-Alarm <sub>`orte.radar`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓ | –* |
| Ampel-Grenzen ändern <sub>`orte.ampel.grenzen`</sub> | ✓* | –* | –* | ✓* B-L3 | ✓* | ✓* | ✓* | ✗* B-L5 |
| Alarm ab je Metrik / für alle <sub>`orte.ampel.alarm_ab`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* | –* |
| **Telegram-Kurzstil** | | | | | | | | |
| Telegram-Kurzstil: Briefing <sub>`orte.telegram_kurzstil.briefing`</sub> | – | – | – | ✓ | – | – | ✓* TL3 | – |
| Telegram-Kurzstil: Alarm <sub>`orte.telegram_kurzstil.alarm`</sub> | – | – | – | ✓* | – | – | ✓ | – |
| **Sprache** | | | | | | | | |
| Sprache DE/EN <sub>`orte.sprache`</sub> | ✓ B-OM-6 | ✓ B-OM-6 | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Kürzel-Legende (W21) <sub>`orte.kuerzel_legende`</sub> | –* | –* | –* | ↗ B-K9 | ↗ B-K9 | ↗ B-K9 | ↗* #3032 | –* |
| **Vorlagen** | | | | | | | | |
| Vorlage übernehmen/zurücksetzen; Vorlage im Mail-Kopf (K3b) <sub>`orte.vorlage.anwenden`</sub> | ↗* B-OM-3 | ↗* B-OM-3 | – | – | – | – | ✓* E6 | ✗* B-L5 |
| Neues Orts-Briefing übernimmt Standard-Vorlage <sub>`orte.vorlage.neu_aus_standard`</sub> | ✓* | –* | –* | ✓* B-L4 | ✓* B-L4 | ✓* B-L4 | ✓* E1 | ✗* B-L5 |
| Als eigene Vorlage speichern <sub>`orte.vorlage.eigene_speichern`</sub> | ✓* | –* | –* | ✓* B-L4 | ✓* B-L4 | ✓* B-L4 | ✓* | ✗* B-L5 |
| **Zeiten/Versand** | | | | | | | | |
| Uhrzeit Morgen-/Abend-Briefing <sub>`orte.zeiten`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓ | –* |
| Morgen-/Abend-Briefing an/aus <sub>`orte.slots`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* TL1 | –* |
| Briefing je Kanal <sub>`orte.briefing_kanaele`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓ | –* |
| Alarme je Kanal <sub>`orte.alarm_kanaele`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓ | –* |
| Alarm ab Dringlichkeit je Kanal <sub>`orte.dringlichkeit`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓ | –* |
| Stille Stunden <sub>`orte.stille_stunden`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* TL2 | –* |
| Mindestabstand zwischen Alarmen <sub>`orte.cooldown`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓ | –* |
| Laufzeit bis auf Weiteres / bis Datum <sub>`orte.laufzeit`</sub> | ✓* | ✓* | –* | ✓* | ✓* | ✓* | ✓* | –* |
| **Mandanten** | | | | | | | | |
| Zwei Nutzer: eigene Listen/Empfänger <sub>`orte.zwei_nutzer`</sub> | ✓ | ✓ | – | ✓ | ✓ | ✓ | ✓ | ✓* |

## Legende

- ✓ über den echten Weg ausgeführt bzw. von einem Test dort geprüft, wo es wirkt (Mutation belegt)
- ✗ Ausgabe weicht von der Einstellung ab, oder (Spalte validator_email) Validator erkennt die Abweichung nicht
- – Ausgabe hat diesen Baustein laut Konzept/ADR nicht
- ? nicht geprüft
- ↗ bekannt und in eigenem Issue ausgelagert
- `·` hinter dem Kürzel: der zuständige Bereich hat für diese Einstellung keine Teilzeile (unbelegt)
- `*` hinter dem Kürzel: per `status_updates.json` nach Behebung überschrieben
- `(B-Px)`: Produktbefund eines anderen Bereichs widerspricht der Zelle (Status unverändert, Zielkonflikt)
- Spalte Validator: prüft der Mail-Validator die Einstellung? (✗ = Abweichung bleibt unerkannt)
- Rangfolge bei mehreren Teilzeilen: rot > ungeprueft > ausgelagert > gruen > nicht_anwendbar

## Befunde

- **B-TM1** (trip_mail, mittel): Kompakt-Mail: amtliche Warnungen stehen nicht an erster Stelle (WV6)
- **B-TM2** (trip_mail, niedrig · Zielkonflikt erwähnt): Wieder eingeschaltete Metrik landet in der Mail an alter Stelle statt „hinten angehängt“
- **B-TM3** (trip_mail, mittel): Testlücke: Schalter „Amtliche Warnungen“ (W20) beim Trip-Briefing ungeschützt
- **B-TM4** (trip_mail, niedrig): Hinweis (keine Fehlwirkung): Prüfkatalog umgeht zwei render-wirksame Weichen
- **B-OM-1** (orte_mail, mittel): Klartext ohne Hinweis „Amtliche Warnungen aktuell nicht abrufbar“
- **B-OM-2** (orte_mail, mittel): Schalter „Amtliche Warnungen“ aus → HTML zeigt weiter die Zeile „Amtliche Warnungen – – –“
- **B-OM-3** (orte_mail, mittel): K3b: Mail-Kopf zeigt zwei verschiedene Profile (Vorlage UND altes `profil`)
- **B-OM-4** (orte_mail, niedrig · Zielkonflikt erwähnt): Klärung: 3-Tages-Ausblick „Erscheint im Morgen/Abend“ für Orte
- **B-OM-5** (orte_mail, niedrig): Stundenverlauf ohne Roh/Einfach (W11)
- **B-OM-6** (orte_mail, niedrig): Katalog-Lücke: fünf Einstellungen stehen nicht im #3047-Prüfkatalog
- **B-K1** (kanaele, mittel): Trip-Telegram ignoriert „Windrichtung Roh“ (#3063 Punkt 2)
- **B-K2** (kanaele, mittel): Trip-Telegram: Kappungshinweis bei EN-Nutzern deutsch
- **B-K3** (kanaele, hoch): Orte-SMS/Premium-SMS: amtliche Warnung eines weiteren Ortes fällt vor Wetterzellen weg
- **B-K4** (kanaele, mittel · Zielkonflikt erwähnt): Trip-SMS kürzt nach fester Priorität, nicht nach Listenende
- **B-K5** (kanaele, niedrig (Trip) / mittel (Orte) · Zielkonflikt erwähnt): Telegram-Schnittlinie: Konzepttext und Ausgabe widersprechen sich
- **B-K6** (kanaele, niedrig (heute nur per API/Altbestand erreichbar)): Orte: `channel_layouts.<kanal> = []` zeigt die volle Grundauswahl statt nichts
- **B-K7** (kanaele, mittel): Orte-Telegram ohne 3-Tages-Ausblick
- **B-K8** (kanaele, niedrig): Testlücke: Roh/Einfach in der Orte-Telegram-Liste von keinem Repo-Test bewacht
- **B-K9** (kanaele, niedrig (Hinweis an #3032)): Kürzel-Legende: „steht auch am Ende jedes Briefings“ stimmt für Telegram/SMS nicht
- **E1** (editor, hoch · Zielkonflikt erwähnt): Grundauswahl „nie eingestellt“: Reiter Wetter zeigt die Vorlage, die Mail etwas anderes
- **E2** (editor, mittel): Mehrtages-Trend „nie eingestellt“: Editor aus, Mail abends an; Kurzstil-Umschalten nimmt den Trend still raus
- **E3** (editor, hoch): Trip-Altformat in `metrics[]` (Zeichenkette / ohne `enabled`): Editor zeigt „nicht gewählt“, Speichern zerstört den Trip
- **E4** (editor, mittel · Zielkonflikt erwähnt): Amtliche Warnungen, Altbestand-Mischzustand: Schalter „an“, Briefing ohne Warnungen; Speichern schaltet still ein
- **E5** (editor, niedrig): Trip-Tagesfenster Altbestand halbes Paar oder Start = Ende: Editor zeigt etwas anderes als gilt
- **E6** (editor, mittel): Orte: „Tiefsttemperatur Nacht“ aus Vorlagen steht im Reiter, die Mail verwirft sie still
- **E7** (editor, mittel): Trip: abgeleitete Größen (Tiefsttemperatur Nacht, Tagestief/-hoch, Windchill-Kinder) in der Mail, im Reiter „nicht im Briefing“
- **E8** (editor, niedrig): Mail-Inhalt-Altwerte `null`: Editor „an“, Mail ohne Block
- **TL1** (editor, Testlücke): M4 `zustellungModell.ts:255` Abend-Standard Orte `?? false` → `?? true` ⇒ Editor zeigt Abend-Briefing an, Versand aus
- **TL2** (editor, Testlücke): M6 `zustellungModell.ts:212` Stille Stunden `&&` → `||` ⇒ halbe Ruhezeit als aktiv angezeigt
- **TL3** (editor, Testlücke): M7 `kanalStilSpeicherung.ts:52` Orte-Kurzstil beim Laden ignoriert ⇒ Schalter „aus“, Telegram bekommt Kurzform
- **TL4** (editor, Testlücke): M8 `reportConfigPayload.ts:55` Vorrang Flags/Liste ⇒ siehe E2
- **TL5** (editor, Testlücke): M16 `internal/handler/trip.go:484` Feld-Merge `alert_channels.email` ⇒ PUT ohne `email` verliert den Wert
- **TL6** (editor, Testlücke): M21 `internal/store/compare_preset.go:116` Lade-Klemme Tagesfenster Orte ⇒ Orte-Editor zeigte halbes Paar
- **TL7** (editor, Testlücke): M25 `zustellungModell.ts` Trip `send_email` Standard ⇒ Editor zeigt E-Mail aus, Versand an
- **TL8** (editor, Testlücke): M1 `ampelModell.ts:400` `enabled === true` → `!== false` ⇒ (macht den Editor Python-gleich, siehe E3)
- **B-V1** (validatoren, mittel): Ausblick: Zahl der Tageszeilen und Ausblick je Ort ungeprüft (bekannt #3083 H3, gegen den Auftrag echte Lücke)
- **B-V2** (validatoren, mittel): Zusatzblöcke Etappen-Kennzahlen und Vortag-Vergleich nie geprüft (bekannt #3083 H2, gegen den Auftrag echte Lücke)
- **B-V3** (validatoren, mittel): Orte-Vergleichstabelle: Roh/Einfach je Zeile ungeprüft (neu)
- **B-V4** (validatoren, niedrig–mittel): Orte-Klartext-Stundenverlauf: nur erste Stundenzeile je Ort gelesen (bekannt #3083 H3)
- **B-V5** (validatoren, mittel): Tagesfenster: Orte-Validator lehnt korrektes Fenster ab, Trip-Validator prüft es nicht (neu)
- **B-V6** (validatoren, mittel): Kanal-Parität der Prüfwerkzeuge: kein Soll-Validator für Telegram, SMS, Premium-SMS (neu)
- **B-V7** (validatoren, niedrig): Ortsfolge der HTML-Abschnitte hängt am deutschen Wort „ORT“ (latent, Code-Lesung)
- **B-V8** (validatoren, niedrig): Testlücke: Sortierung der E-Mail-Kanal-Liste nach `bucket`/`order` ungetestet (neu)
- **B-P1** (validatoren, mittel): Kompakt-Mail zeigt Etappen-Kennzahlen trotz `show_stage_stats = false`
- **B-P2** (validatoren, mittel): Kompakt-Mail zeigt 3-Tages-Ausblick trotz `show_outlook = false`
- **B-L1** (luecken, mittel · Zielkonflikt erwähnt): Trip-Telegram-Kurzübersicht ignoriert das Tagesfenster
- **B-L2** (luecken, mittel): Orte-Telegram/SMS/Premium-SMS ohne Hinweis „Warnungen nicht abrufbar“
- **B-L3** (luecken, niedrig · Zielkonflikt erwähnt): Orte-Telegram: Ampel-Grenzen ohne Wirkung, „Einfach“ zeigt Windwort
- **B-L4** (luecken, hoch): Orts-Vergleich „nie eingestellt“ / jede Neuanlage: Telegram und SMS zeigen alten Sechsersatz
- **B-L5** (luecken, niedrig (Testlücke)): Validatoren: weitere ungeprüfte Einstellungen
- **B-L6** (luecken, niedrig · Zielkonflikt erwähnt): Trip-Altformat ohne `order`: Validator lehnt die korrekte Mail ab

## Offen „ungeprüft“ (0 Zellen, davon 0 unbelegt)

