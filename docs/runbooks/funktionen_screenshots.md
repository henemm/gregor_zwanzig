# Runbook — Bilder der öffentlichen Funktionsseiten erzeugen und prüfen (Issue #3319)

Spec: `docs/specs/modules/oeffentliche_doku_3319.md` (AC-8, AC-9) · Seiten: `/funktionen`,
`/funktionen/<thema>` · Bilder: `frontend/static/funktionen/*.webp` (DE) und
`frontend/static/funktionen/en/*.webp` (EN) · Maße: `frontend/src/lib/components/organisms/funktionen/bildmasse.json`

## Wann

Wenn sich die Oberfläche oder ein Renderer sichtbar ändert und ein Bild der Funktionsseiten nicht
mehr stimmt. Die Bilder spiegeln den Stand zum Aufnahmezeitpunkt.

## Zwei Quellen

| Bild | Quelle | Skript |
|---|---|---|
| `briefing-mail`, `briefing-telegram`, `alarm-mail`, `briefing-sms`, `premium-sms`, `befehle-mail`, `briefing-quelle` | echte Renderer mit festen Testdaten, ohne Netz | `uv run python scripts/landing_screenshots.py --funktionen` |
| `cockpit`, `trip-anlegen`, `trip-hub`, `trip-wetter`, `trip-zustellung`, `archiv`, `ortsvergleich`, `konto-kanaele`, `konto-level` | echte Staging-Oberfläche, Prüfkonto mit Mockup-Seed | `uv run python scripts/funktionen_screenshots.py` |

Beide Skripte schreiben je Sprache eine eigene Datei (WebP, Qualität 80, bei Bedarf kleiner, immer
unter 200 KB) und mergen die Maße in `bildmasse.json` (andere Einträge bleiben). Einzelne Bilder:
`scripts/funktionen_screenshots.py --nur archiv` bzw. `--sprache en`.

## Ablauf (auf dem Host)

1. Prüfkonto auf Seed-Stand bringen (idempotent, Runbook `staging_pruefkonto_seed.md`):
   `uv run python scripts/staging_pruefkonto_mockupdaten.py`
2. Renderer-Bilder: `uv run python scripts/landing_screenshots.py --funktionen`
3. UI-Bilder: `uv run python scripts/funktionen_screenshots.py` — meldet sich mit
   `GZ_PRUEFKONTO_USER`/`GZ_PRUEFKONTO_PASS` aus `/home/hem/gregor_zwanzig_staging/.env` an, stellt
   Kontosprache und Cookie `gz_lang` je Sprache um und setzt die Kontosprache am Ende auf Deutsch zurück.
4. Tests: `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` (Existenz, < 200 KB, WebP, Alt-Text,
   Maße, lazy, DE/EN-Paar, mindestens ein Bild je Unterseite außer `level`).
5. **Sichtprüfung jedes Bildes** (Datei öffnen und ansehen) und Ergebnis unten eintragen.

## Personendaten (AC-9)

- Vor jeder UI-Aufnahme ersetzt das Skript im sichtbaren Text, in Eingabefeldern und Platzhaltern jede
  Mail-Adresse durch `wanderer@beispiel.invalid` und jede Telefonnummer durch `+49 ••• •••••••` — auch
  gekürzt angezeigte Formen wie `name@…` oder `+49 171 …`.
- Danach prüft `pruefe_vor_aufnahme` den gesamten sichtbaren Text. Steht dort noch eine Mail-Adresse oder
  Telefonnummer außerhalb von `FIKTIV_ERLAUBT`, bricht das Skript ohne Bild ab
  (`PersonendatenGefunden`; die Fundstellen selbst werden nicht ausgegeben). Wächter-Test mit Gegenprobe:
  `tests/test_funktionen_screenshots_waechter.py`.
- Aufgenommen wird nur der Inhaltsbereich (`main`) bzw. die genannte Karte, nie die Seitenleiste mit dem
  Kontonamen.
- Der Wächter ersetzt die Sichtprüfung nicht: Namen, Kennungen oder Bilder in Bildern erkennt er nicht.

**Lehre aus der ersten Aufnahme (24.11.2026):** Der Reiter Zustellung zeigt Adresse und Nummer gekürzt
(„…@…“, „+49 171 …“). Die erste Fassung des Wächters erkannte nur vollständige Adressen; die
Sichtprüfung fand die gekürzten Formen. Seitdem maskiert und prüft das Skript auch gekürzte Formen
(Testfall `test_gegenprobe_gekuerzt_angezeigte_kontaktdaten_werden_erkannt`).

## Ergebnis der Sichtprüfung (24.11.2026, Stand Staging und Renderer)

Jedes Bild in DE und EN geöffnet und angesehen. Ergebnis: keine echten Personendaten.

| Bild | Inhalt (DE/EN) | Befund |
|---|---|---|
| `cockpit` | Startklar-Liste, Ortsvergleich Münsterland, Versand heute, Datum | keine Personendaten; Seitenleiste nicht im Bild |
| `trip-anlegen` | Schritt Route, leere Felder mit Beispieltext „Karnischer Höhenweg“ | keine Personendaten |
| `trip-hub` | Trip GR221 Mallorca (Seed), Etappen Port d'Andratx → Estellencs …, Wetter, Briefings | nur Seed-Daten |
| `trip-wetter` | Reiter Wetter, Vorlage Alpen-Trekking, Schwellen | nur Seed-Daten |
| `trip-zustellung` | Zeiten, Laufzeit, Kanaltabelle | Adresse als `wanderer@beispiel.invalid`, Nummer als `+49 ••• •••••••` maskiert |
| `archiv` | leeres Archiv mit Suche und Filtern | keine Personendaten |
| `ortsvergleich` | Ortsvergleich Münsterland (Münster, Telgte, Tecklenburg) | nur Seed-Daten |
| `konto-kanaele` | Karte Kanäle: E-Mail, Handynummer, Telegram verbunden (…001, fiktive Chat-ID des Seeds) | Adresse und Nummer maskiert |
| `konto-level` | Level Premium, Antrag, Mengen, SMS-Kontingent, Benachrichtigungen, Wetter-Modelle | Adresse maskiert, Telegram …001 (fiktiv) |
| `briefing-mail` | Abend-Briefing „Beispiel-Trip GR20“ / „Example trip GR20“, Etappe 3 | feste Testdaten |
| `briefing-telegram` | Telegram-Blasen „Beispiel-Trip GR20“ | feste Testdaten |
| `alarm-mail` | amtliche Warnungen GeoSphere (Gailtal, Hermagor) | feste Testdaten |
| `briefing-sms` | SMS-Zeile aus `format_email` (58 bzw. 63 Zeichen) | feste Testdaten |
| `premium-sms` | Premium-SMS-Zeile in Geräteansicht | feste Testdaten |
| `befehle-mail` | Abschnitt Antwort-Befehle der Briefing-Mail | keine Personendaten |
| `briefing-quelle` | Fußzeile der Briefing-Mail (Zeit, openmeteo, arome_france) | keine Personendaten |

Hinweise zum Bildinhalt: Das Archiv des Prüfkontos ist leer (der Seed legt keine archivierten Trips an);
das Cockpit zeigt den beendeten Seed-Trip nicht, nur den Ortsvergleich. Die Alt-Texte beschreiben genau
das, was zu sehen ist.

**Bekannte Schwäche Archiv-Bild:** Ein leeres Archiv zeigt die Funktion nur schwach. Ein fiktiver
archivierter Trip ginge nur über eine Erweiterung des Prüfkonto-Seeds
(`scripts/staging_pruefkonto_mockupdaten.py`): zweiter Trip, Archiv-Aufruf, Anpassung seiner eigenen
Tests (`tests/tdd/test_staging_pruefkonto_mockupdaten.py`). Außerdem würde sich der Bestand des Kontos
ändern, den der Elementlisten-Abgleich (#2913) gegen das Mockup liest. Das ist kein kleiner Umbau und
wurde deshalb in #3319 nicht gemacht. Wird der Seed später um einen archivierten Trip erweitert:
`uv run python scripts/funktionen_screenshots.py --nur archiv`, Sichtprüfung, Alt-Text
`funktionen.bild.archiv.alt` (DE/EN) anpassen.
