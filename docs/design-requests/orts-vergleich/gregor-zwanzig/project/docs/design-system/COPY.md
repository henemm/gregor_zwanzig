# COPY · Terminologie-Dictionary

> Verbindliches Vokabular. Linke Spalte = kanonisch. Mittlere = wo es gilt. Rechte = was NICHT verwendet werden darf (Drift-Quellen).
>
> Maschinenlesbarkeit: dieses Dokument kann via `grep` als Suchen-und-Ersetzen-Quelle dienen. Tabu-Begriffe sind mit `❌` markiert.

---

## 1. Kern-Entitäten

| Kanonisch | Verwendung | Tabu (❌) |
|---|---|---|
| **Trip** | Eine geplante Reise (= internes Modell + User-Begriff). Maskulin: *der Trip*, *einen Trip*. | ❌ Tour · ❌ Reise · ❌ Wanderung · ❌ Trip-Datensatz |
| **Trips** | Pluralform | ❌ Touren · ❌ Tours |
| **Etappe** | Ein Tag innerhalb eines Trips | ❌ Stage · ❌ Tag-Segment · ❌ Tagesetappe |
| **Wegpunkt** | Markierter Punkt auf einer Etappe | ❌ Waypoint (außer in Code-Identifiern) |
| **Ort** | Eintrag in der Vergleichs-Liste | ❌ Location · ❌ Standort · ❌ Position |
| **Orts-Vergleich** | Vergleichs-Konfiguration mehrerer Orte | ❌ Vergleich (allein) · ❌ Compare · ❌ Vergleiche |
| **Vergleich** | Kurzform von Orts-Vergleich, **nur** wenn Kontext klar ist | OK in Lauftext, ❌ in Nav-Items |
| **Archiv** | Vergangene Trips | ❌ Historie · ❌ Vergangene · ❌ Past Trips |
| **Konto** | Benutzer-Account-Seite | ❌ Account · ❌ Profil · ❌ Einstellungen (für die ganze Seite) |
| **Profil** | Sub-Sektion innerhalb der Konto-Seite (Name, Avatar) | OK in dieser Bedeutung |
| **Briefing** | Versand-bereite Wetter-Zusammenfassung | ❌ Notification · ❌ Report (außer als technisches Detail) · ❌ Benachrichtigung |
| **Alarm** | Schwellwert-Überschreitung, sofortiger Trigger | ❌ Warning · ❌ Warnung · ❌ Notification |
| **Warnung** | Schwellwert-nahe Situation (nicht überschritten) | Abgrenzung zu Alarm ist wichtig — Warnung = gelb, Alarm = rot |

---

## 2. Verben (CTAs / Aktionen)

| Kanonisch | Bedeutung | Tabu (❌) |
|---|---|---|
| **Anlegen** | Neue Entität erzeugen ("+ Neuer Trip", "+ Ort anlegen") | ❌ Erstellen · ❌ Hinzufügen · ❌ Neu |
| **Bearbeiten** | Bestehende Entität ändern | ❌ Editieren · ❌ Ändern (für CTA-Label) |
| **Speichern** | Änderung persistieren | ❌ Sichern · ❌ Save (außer Code) |
| **Löschen** | Endgültig entfernen | ❌ Entfernen (außer für *Kanäle entkoppeln* o. Ä.) |
| **Entkoppeln** | Verbindung trennen, Entität bleibt bestehen | OK |
| **Verschieben** | Etappe / Trip terminlich verlegen | OK |
| **Verwerfen** | Algorithmus-Vorschlag ablehnen | OK |
| **Annehmen** | Algorithmus-Vorschlag akzeptieren | OK |
| **Senden** | Briefing manuell auslösen | OK · ❌ Verschicken (außer in Headline-Copy) |
| **Test senden** | Probe-Briefing | OK · ❌ Test-Briefing senden (zu lang) |
| **Anmelden** | Login | ❌ Einloggen · ❌ Sign in |
| **Abmelden** | Logout | ❌ Ausloggen · ❌ Sign out |
| **Registrieren** | Konto erstellen | ❌ Sign up · ❌ Anmelden (für Erst-Registrierung) |

---

## 3. Status & Zustände

| Kanonisch | Bedeutung | Visuell | Tabu (❌) |
|---|---|---|---|
| **Aktiv** | Trip läuft / Kanal verbunden / Etappe heute | `<Dot tone="good">` + Label | ❌ Live · ❌ Online · ❌ Running |
| **Geplant** | Trip in der Zukunft | `<Pill tone="neutral">` | ❌ Upcoming · ❌ Bevorstehend |
| **Abgeschlossen** | Trip in der Vergangenheit | `<Pill tone="ghost">` | ❌ Beendet · ❌ Fertig · ❌ Done |
| **Pausiert** | Trip temporär gestoppt | `<Pill tone="warn">` | ❌ Paused · ❌ Inaktiv |
| **Verbunden** | Kanal funktioniert | `<Dot tone="good">` Verbunden | ❌ OK · ❌ Connected · ❌ Working |
| **Nicht verbunden** | Kanal nie initialisiert | `<Dot tone="neutral">` Nicht verbunden | ❌ Disconnected · ❌ Offline · ❌ Inaktiv |
| **Verifikation offen** | Kanal initialisiert, wartet auf User | `<Dot tone="warn">` | ❌ Pending · ❌ Wartet · ❌ Bestätigung ausstehend |
| **Fehler** | Kanal hat Zustellungs-Problem | `<Dot tone="bad">` Fehler | ❌ Error · ❌ Defekt |

---

## 4. Zeit & Datum

| Kanonisch | Format | Beispiel |
|---|---|---|
| Datum (lang) | `DD. MMM YYYY` | `17. Mai 2026` |
| Datum (kurz) | `DD.MM.YYYY` | `17.05.2026` |
| Datum (Tabelle) | `DD. MMM` | `17. Mai` |
| Uhrzeit | `HH:MM` (24 h) | `06:30` |
| Wochentag-Kürzel | 2 Buchstaben Caps | `MO DI MI DO FR SA SO` |
| Zeitspanne | `HH:MM – HH:MM` mit langem Bindestrich | `06:00 – 19:00` |
| Datumsspanne | `DD.–DD. MMM YYYY` | `17.–19. Mai 2026` |
| Relative Zeit | "vor X h/min/Tag" | `vor 12 Min`, `vor 3 Tagen` |
| Future relative | "in X h/min/Tag" | `in 14 h 22 m` |
| Trip-Tag-Label | `TAG N · TT DD. MMM` | `TAG 2 · DI 13. SEP` |

---

## 5. Einheiten & Zahlen

| Größe | Einheit | Format | Beispiel |
|---|---|---|---|
| Temperatur | °C | Ganzzahl ohne Nachkomma | `12 °C` (mit non-breaking-space) |
| Temperaturspanne | °C | `min–max` | `5–12 °C` |
| Niederschlag | mm | eine Nachkomma | `9.6 mm` |
| Windgeschwindigkeit | km/h | Ganzzahl | `22 km/h` |
| Böen | km/h | Ganzzahl | `44 km/h` |
| Höhenmeter | m | Ganzzahl mit Pfeil-Prefix | `↑ 880 / ↓ 720 m` |
| Distanz | km | eine Nachkomma | `12.4 km` |
| Score | 0–100 | Ganzzahl | `87` |
| Prozent | % | Ganzzahl, ohne Leerzeichen | `65%` |
| Himmelsrichtung | Caps-Abkürzung | `WSW` `NNW` (nicht `West-Süd-West`) |

---

## 6. Page-Titles & Eyebrows

| Kontext | Eyebrow (Mono-Caps) | Page-Title (Sentence-Case) |
|---|---|---|
| Startseite | `STARTSEITE · ÜBERSICHT` | `Startseite` |
| Trips-Liste | `TRIPS` | `Meine Trips` |
| Trip-Detail | `TRIP · {NAME}` | `{Trip-Name}` |
| Trip-Wizard Step N | `SCHRITT N / 4 · NEUER TRIP` | `{Schritt-Titel}` |
| Orts-Vergleich | `ORTS-VERGLEICH` | `{Preset-Name}` |
| Archiv | `ARCHIV · VERGANGENE TRIPS` | `Archiv` |
| Konto | `KONTO · /account` | `Konto-Einstellungen` |
| Login | `01 · ANMELDEN` | `Willkommen zurück.` |
| Registrierung | `02 · KONTO ERSTELLEN` | `Konto erstellen.` |
| Passwort vergessen | `03 · PASSWORT VERGESSEN` | `Passwort zurücksetzen.` |
| Reset-Password | `04 · NEUES PASSWORT` | `Passwort vergeben.` |

---

## 7. Empty-States

| Kontext | Headline | Body | CTA |
|---|---|---|---|
| Trips leer | Noch kein Trip. | Lege deinen ersten Trip an — Wizard in 4 Schritten. | + Neuer Trip |
| Orts-Vergleich leer | Noch kein Vergleich. | Wähle Orte und einen Zeitraum — wir empfehlen automatisch. | + Neuer Vergleich |
| Archiv leer | Noch nichts archiviert. | Abgeschlossene Trips erscheinen automatisch hier. | — |
| Kanäle leer | Noch kein Kanal verbunden. | Mindestens ein Kanal muss aktiv sein, damit Briefings versendet werden. | + Kanal hinzufügen |
| Templates leer | Noch kein Template. | Speichere deine Wetter-Konfiguration als wiederverwendbares Template. | + Neues Template |

---

## 8. Formatierungs-Regeln

- **Lange Bindestriche (en-dash `–`)** für Zeitspannen, Datumsspannen, Wertspannen. **Nicht** Minus (-) und nicht em-dash (—).
- **Em-dash (—)** in Lauftext für Einschübe — wie hier.
- **Aufzählungs-Trennzeichen** in Mono-Strings: Mittelpunkt `·` mit Leerzeichen drumherum (`a · b · c`).
- **Non-breaking-space** vor `°C`, `km/h`, `mm`, `m`, `%`, `Min`, `h`.
- **Anführungszeichen**: Im Lauftext deutsche „…" — im Code für Strings ASCII `"…"`.

---

## 9. Verbotene Worte (Drift-Wachhund)

Diese Wörter erscheinen **nirgendwo** im Produkt-UI (Mockups, Implementierung, Issue-Bodies):

`Tour` · `Touren` · `Stage` · `Waypoint` (außer Code) · `Account` · `Notification` · `Forecast-Alert` · `Dashboard` · `Settings` (außer Code-Pfad `/settings` falls vorhanden) · `Cockpit` · `Active-Trip-Cockpit` · `Sign in` · `Sign up` · `Sign out` · `Trip anlegen!` (Ausrufezeichen) · `Erstellen` · `Editieren` · `Kanal-Verwaltung` (heißt einfach **Kanäle**)

**Ausnahmen** (kein Drift, weil keine Trip-Konzept-Referenz):
- Sportart-Vokabular: `Skitour`, `Skitouren`, `Hochtour`, `Radtour`, `Wandertour`, `Mountainbike-Touren`, `Rundtour` (= Route)
- Eigennamen: `Tour du Mont Blanc`
- Interne IDs: `alpine-touring`

---

## 10. Versionierung

| Version | Datum | Anmerkung |
|---|---|---|
| v1.0 | 2026-05-21 | Initiales Dictionary — Runde 1 |
| v2.0 | 2026-05-26 | **Breaking:** Kern-Begriff umgedreht — `Trip` ist jetzt kanonisch (User-Facing + intern), `Tour`/`Touren` sind tabu außer in Sportart-Vokabular und Eigennamen. |
