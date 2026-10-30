# i18n-Glossar Deutsch → Englisch (bindend, ADR-0104, Epic #2644)

> Stand: 2026-10-30 (freigegeben mit #2645). Regel: **ein** Begriff je Zeile,
> neue Fachwörter zuerst hier, dann in den Katalog. Einfaches Englisch, Fachbegriffe wo sie
> der Klarheit dienen. **Verboten:** „Tour"/*tour* (Produktbegriff ist Trip).

## Produktbegriffe

| Deutsch | Englisch | Hinweis |
|---|---|---|
| Trip | trip | Eigenname des Produkts, bleibt |
| Etappe | stage | nie *leg*, nie *tour* |
| Ortsvergleich | location comparison | Kurz in Reitern: *comparison* |
| Briefing | briefing | bleibt |
| Alarm | alert | Abweichungs-Alarm = *deviation alert*, Regen-/Radar-Alarm = *rain alert (radar)* |
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
| Totalausfall | complete outage | Provider-Ausfall-Meldung |
| Kontingent | quota | SMS-Kontingent = *SMS quota* |
| Premium-SMS | Premium SMS | Kanalname, bleibt; Zusatz *(inReach)* |
| Kopplung (inReach) | linking | „Kopplungscode" = *link code* |
| Magic-Link | magic link | |
| Passkey | passkey | |
| Stufe (Alarm/Warnung) | level | Warnstufe = *warning level* |
| Schwelle | threshold | |
| Aktivitätsprofil | activity profile | Werte: *general*, *hiking*, *mountaineering*, … (Register prüfen) |

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
