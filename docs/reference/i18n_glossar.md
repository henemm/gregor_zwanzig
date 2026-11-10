# i18n-Glossar Deutsch → Englisch (bindend, ADR-0104, Epic #2644)

> **Hinweis (PO 2026-10-31, ADR-0104):** Die Kurzform (Token-Zeile) von SMS, Premium-SMS und Telegram ist nie sprachabhängig: sie bleibt in jeder Sprache (Konto-Sprache de/en) unverändert und wird nicht übersetzt.

> Stand: 2026-11-02 (Abschluss Epic #2644, Paket A1 #2680; Erstfassung 2026-10-30 mit #2645). Regel: **ein** Begriff je Zeile,
> neue Fachwörter zuerst hier, dann in den Katalog. Einfaches Englisch, Fachbegriffe wo sie
> der Klarheit dienen. **Verboten:** „Tour"/*tour* (Produktbegriff ist Trip); im deutschen UI
> außerdem „Drafts", „Alert-Trigger" und „Alerts justieren" (ADR-0111, #2881: „Entwürfe",
> „Alarm-Auslöser", „Alarme einstellen").

## Produktbegriffe

| Deutsch | Englisch | Hinweis |
|---|---|---|
| Trip | trip | Eigenname des Produkts, bleibt |
| Etappe | stage | nie *leg*, nie *tour* |
| Ortsvergleich | location comparison | Kurz in Reitern: *comparison* |
| Briefing | briefing | bleibt |
| Alarm | alert | Abweichungs-Alarm = *deviation alert*, Regen-/Radar-Alarm = *rain alert (radar)* |
| Alarm-Auslöser | alert trigger | Zeile der Übersicht; nie „Alert-Trigger" im deutschen UI (#2881) |
| Alarme einstellen | adjust alerts | nie „Alerts justieren" (#2881) |
| Entwürfe | drafts | Listen-Zähler; nie „Drafts" im deutschen UI (#2881) |
| amtliche Warnung | official warning | Quelle unverändert (DWD, MeteoAlarm, Météo-France, GeoSphere, SLF) |
| Wertebereiche | target ranges | Reiter-Name |
| Versand | delivery | Reiter-Name; „Versandkanal" = *delivery channel* |
| Layout | layout | bleibt |
| Korridor | corridor | bleibt |
| Orte | locations | |
| Standardwerte | defaults | „Standardwerte speichern" = *Save as defaults* |
| Verlässlichkeit | confidence | Nur Meta-Hinweis, keine Metrik (#710) |
| Kürzel | code | SMS-Kürzel = *SMS code*; Protokoll-Token nie übersetzen |
| Kurzform / Kurzstil | compact style | Platzform, keine Sprache (ADR-0042) |
| Ruhetag | rest day | Inbound-Befehl `RUHETAG`/`RESTDAY` |
| Pausentag | rest day | Pause-Etappe in der Etappenkarte (#2660) |
| Cockpit | dashboard | Startfläche nach Login |
| Archiv | archive | |
| Konto | account | |
| Empfänger | recipient | |
| Vorschau | preview | |
| Handversand / Test-Versand | send now / test send | |
| Pausieren / Fortsetzen | pause / resume | |
| Archivieren | archive | Verb |
| Löschen | delete | |
| Speichern | save | „✓ Gespeichert HH:MM" = *✓ Saved HH:MM* |
| Stand | as of | „Stand 12:30" = *as of 12:30* |
| Zeitfenster | time window | |
| Tagesfenster | day window | |
| Ausblick (3 Tage) | outlook (3-day) | |
| Legende | legend | |
| Hinweis | note | |
| Wetterlage | weather pattern | Stabilitäts-Satz „Wetterlage: STABIL" = *Weather pattern: STABLE* (#2665) |
| Ersatzquelle / Ersatzmodell | backup source / backup model | Herkunfts-Vertretung; Quellennamen bleiben (#2665) |
| Antwort-Kommandos | reply commands | Kopf des Befehlsblocks; Befehlswörter selbst siehe P10 (#2665) |
| nicht zugestellt: FEHLGESCHLAGEN / ZURÜCKGEHALTEN | FAILED / HELD BACK | Blöcke im Briefing (#2665) |
| Totalausfall | complete outage | Provider-Ausfall-Meldung |
| Kontingent | quota | SMS-Kontingent = *SMS quota* |
| Premium-SMS | Premium SMS | Kanalname, bleibt; Zusatz *(inReach)* |
| Kopplung (inReach) | linking | „Kopplungscode" = *link code* |
| Magic-Link | magic link | |
| Passkey | passkey | |
| Stufe (Alarm/Warnung) | level | Warnstufe = *warning level* |
| Level (Tarifstufe) | level | Kontostufe; Tarif-Begriffe ergänzt G3 (#2677) |
| Tarif | plan | „in deinem Tarif“ = *on your plan* (Kontingent-Meldung, #2677) |
| Schwelle | threshold | |
| Aktivitätsprofil | activity profile | Werte: *general*, *hiking*, *mountaineering*, … (Register prüfen) |
| Stundenverlauf | hourly view | Abschnitt im Ortsvergleich; Abschnittskopf „STUNDEN" = *HOURLY* (#2666) |
| Gehzeit | walking hours | Tageswerte „(Gehzeit)" = *(walking hours)*, wie `label_en` im Metrik-Register (#2751) |
| Nachtfenster | night window | Nacht-Einzelwert = *single value for the night window* (#2751) |
| Abo | subscription | „Dieses Abo" = *This subscription*, „Abo bearbeiten" = *Edit subscription* (#2666) |
| Übersicht | overview | Abschnittskopf „ÜBERSICHT" = *OVERVIEW* (#2666) |

## Wettergrößen (volle Form, ADR-0042 Klasse 2 „voll")

Quelle ist das Metrik-Register (`src/app/metric_catalog.py`, Paket #2662 füllt `label_en`).
Hier nur Beispiele der Konvention; **Kurzform (`col_label`) und Kürzel bleiben**:

| Deutsch (`label_de`) | Englisch (`label_en`) | Kurzform (unverändert) |
|---|---|---|
| Temperatur | Temperature | Temp |
| Gefühlte Temperatur | Feels-like temperature | Feels |
| Böen | Wind gusts | Gust |
| Niederschlag | Precipitation | Rain |
| Regenwahrscheinlichkeit | Rain probability | Rain% |
| Luftfeuchtigkeit | Humidity | Humid |
| Taupunkt | Dew point | Dew |
| Sichtweite | Visibility | Visib |
| Bewölkung | Cloud cover | Cloud |
| Gewitter | Thunderstorm | Thdr |
| Schneefallgrenze | Snow line | SnowL |
| Schneehöhe | Snow depth | SnowH |
| Sonnenstunden | Sunshine hours | Sun |
| UV-Index | UV index | UV |

## Konto und Anmeldung

| Deutsch | Englisch |
|---|---|
| Anmelden | Sign in |
| Registrieren | Sign up |
| Abmelden | Sign out |
| Passwort | Password |
| Passwort vergessen | Forgot password |
| Passwort zurücksetzen | Reset password |
| E-Mail bestätigen | Verify email |
| Bestätigungscode | Verification code |
| Anzeigename | Display name |
| Sprache | Language |
| Benutzername | Username |
| E-Mail | Email |
| Hilfe | Help |
| Testmail | Test email |
| Konto erstellen | Create account |
| Anmeldelink | sign-in link |
| E-Mail-Code | email code |
| Bestätigungslink | confirmation link |
| Bestätigungsmail | confirmation email |
| Einladung | invitation |
| Reset-Link | reset link |
| Datenschutz | Privacy policy |

## Zeit und Format (ADR-0104 Nr. 6)

| Deutsch | Englisch |
|---|---|
| `Fr 30.10.` | `Fri 30 Oct` |
| 14:30 | 14:30 (24 h) |
| heute / morgen / übermorgen | today / tomorrow / day after tomorrow |
| vor 3 Min | 3 min ago |
| Mo Di Mi Do Fr Sa So | Mon Tue Wed Thu Fri Sat Sun |
| 12.5 (Punkt) | 12.5 (point) |

## Inbound-Befehle (beide Sprachen werden verstanden, #2673)

| Deutsch | Englisch | Bemerkung |
|---|---|---|
| HILFE | HELP | |
| STATUS | STATUS | |
| RUHETAG | RESTDAY | |
| STARTDATUM | STARTDATE | |
| ABBRUCH | CANCEL | |
| WEITER | RESUME | |
| PAUSE | PAUSE | |
| STRECKE | ROUTE | |
| KUERZEL | CODES | heute schon so (#2417) |
| HEUTE | TODAY | Tagesbericht der Etappe |
| MORGEN | TOMORROW | Vorschau auf den nächsten Tag |
| JETZT | NOW | Regen und Gewitter in den nächsten zwei Stunden |
| GEWITTER | STORMS | Gewitterlage heute |
| SKIP | SKIP | nächstes Briefing überspringen |
| STOP | STOP | Briefings beenden |
| REPORT | REPORT | Bericht sofort senden (Trip-Briefing oder Ortsvergleich) |

## Amtliche Warnungen (#2668)

| Deutsch | Englisch | Hinweis |
|---|---|---|
| GELB / ORANGE / ROT (GRÜN) | YELLOW / ORANGE / RED (GREEN) | Stufenwörter; SMS-Stufenbuchstaben bleiben |
| Warnstufe / höchste Stufe | warning level / highest level | |
| Gültig | Valid | Datenzeile „Valid: Thu 29 Oct · 11:00–20:00“ |
| ganztägig | all day | |
| Gefahr | hazard | Datenzeile |
| Entwarnung | all clear | „Stufe 3 → beendet“ = *Level 3 → ended* |
| Lawinenstufe | avalanche level | EAWS-Wörter: low, moderate, considerable, high, very high |
| Waldgrenze | treeline | |
| Quelltext: Französisch | Source text in French | Behördentext wird nie übersetzt |
| gesamte Route / alle Orte | entire route / all locations | SMS-Umfang (`ges.Route`, `alleOrte`) bleibt |
| Zugang gesperrt | Access closed | Massiv-Namen bleiben |
| Waldbrand-Gefahr | Wildfire risk | |

## Abweichungs- und Regen-Alarme (#2667)

| Deutsch | Englisch | Hinweis |
|---|---|---|
| Ziel (Etappenziel im Alarm) | destination | `🏁 Destination`; derselbe Schlüssel `alarm.segment.ziel` wie im Radar-Validator |
| stärkste Stunde | peak hour | Zeitpunkt des stärksten Werts |
| Luftmasse | air mass | Gewitter-Zeile bis „leicht“ (#2176) |
| Radar-Nowcast | radar nowcast | Badge der Regen-Alarm-Mail |
| Beginn (Regen-/Gewitter-Beginn) | onset | „Niedersch-Beginn“ = *Precip onset* |
| Cooldown | cooldown | „höchstens einmal in“ = *at most once in* |
| grün / gelb / orange / rot (Ampelfarbe im Abweichungs-Alarm) | green / yellow / orange / red | Kleingeschrieben im Satz (`alarm.ampel.farbe.*`, #2793); Kurzform-Buchstaben `G/Y/O/R` nie übersetzt |
| gestiegen (von … auf …) | rose (from … to …) | Verschärfung der Ampelfarbe |
| großer Sprung | large jump | „weiter rot, großer Sprung“ = *still red, large jump* |
| Entwarnung (Abweichungs-Alarm) | all clear | „von orange auf gelb zurückgegangen“ = *back from orange to yellow* |
| Tageshöchst / Tagestief | daily high / daily low | Seite der Temperatur im Ampel-Satz |
| Alarm ab | alert from | Schwelle der Ampel je Metrik (`alarm_ab`) |

## Reiter Wetter (#2794 S3a)

| Deutsch | Englisch | Hinweis |
|---|---|---|
| Wetter (Reiter) | weather | Reiter-Name in Trip und Orts-Briefing (Katalog `wetter.*`); löst Wertebereiche/Alarme als Wetter-Reiter ab (Bereinigung Teil-PR 4) |
| Vorlage | template | Systemvorlage oder eigene Vorlage; „Eigene" = *Your own*, „Als eigene Vorlage speichern" = *Save as your own template* |
| Ampel | traffic light | Bewertung einer Metrik grün/gelb/orange/rot (ADR-0106); „Ampel-Grenzen" = *traffic-light limits* |
| Grenzen ändern | change limits | Knopf je Metrik-Zeile; „Fertig" = *Done* |
| Nicht im Briefing | not in the briefing | Liste der abgewählten Metriken mit „+ {Metrik}" |
| Abweichung (von der Vorlage) | change (from the template) | „{n} Abweichungen" = *{n} changes*; „unverändert" = *unchanged* |
| Orts-Briefing | location briefing | Kontext `vergleich` im Reiter Wetter |
