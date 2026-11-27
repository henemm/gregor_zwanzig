# Mail-Validatoren & Renderer-Gate — Detail-Referenz

Kompakte Übersicht + Dispatch-Tabelle stehen in `CLAUDE.md` → Abschnitt
„Mail-Validatoren & Renderer-Gate". Dieses Dokument hält die vollständigen
Plausibilitäts-Schwellen, das Dispatch-Verhalten, die Anti-Stale-Mechanik und
die Historie.

Es gibt **drei verschiedene Mail-Pfade** mit **drei verschiedenen Gates**. Den
falschen Validator auf einen Pfad anzuwenden ist ein Fehler — er kann strukturell
nie bestehen (Dauer-Exit-1) und führt zu falschem „Feature kaputt" oder
Gate-Erosion.

## Frische der geprüften Mail — `--max-age-minutes` / `--ignore-mail-age` (#2035)

`radar_alert_mail_validator.py`, `official_alert_mail_validator.py` und
`briefing_mail_validator.py` prüfen wie `email_spec_validator.py` (#1408), dass die
gewählte Mail frisch ist. Gemessen wird die **serverseitige INTERNALDATE**
(`_mail_trust.alter_erzwingen`), nie der absenderseitige `Date`-Kopf; liefert der
Server keine, gibt es Exit 2 statt Rückfall. Standardgrenze **60 Minuten**,
Obergrenze 1440; Abschalten nur mit `--ignore-mail-age "<Grund>"`. Eine ältere
Treffer-Mail (z. B. tagealte Fremd-Mail aus einem anderen Test) endet mit Exit 2
und der Meldung „bitte frische Mail auslösen". Test: `tests/tdd/test_mail_frische_2035.py`.
Empfehlung weiter: `--subject-contains` auf den eigenen Betreff (Herkunftsbindung).
*Regel-Budget: Prüfdatum 2027-02-25 (Gate-Audit #1197): bis dahin ein echter Fang oder Rückbau.*

## Zustellweg auf Staging und Subject-Filter (#2774)

Die Validatoren prüfen eine **echt zugestellte** Staging-Mail. Zustellen und prüfen in einem
Schritt: `python3 .claude/tools/staging_mail_pruefen.py --typ trip|compare|beide` (Rezept in
`.claude/commands/e2e-verify.md` Schritt 3b und `docs/reference/operations_playbook.md`).

- **Empfänger:** ein Wegwerf-Nutzer mit Plus-Adresse `gregor-test+<tag>@henemm.com`.
  `gregor-test@henemm.com` selbst taugt nicht als Trip-Empfänger (Go: `email_taken`).
- **Englisch (#2830):** `python3 .claude/tools/staging_mail_pruefen.py --typ trip|compare|beide --lang en`
  meldet den festen Nutzer `en` an (Empfänger `gregor-test+en@henemm.com`), der Validator läuft mit
  `--lang en --to-contains "+en@"`; der Nutzer `en` wird nie gelöscht, nur die eigenen Objekte.
  `staging_gate.py --write-verdict` verlangt `--langs de,en`, daher je Sprache ein eigener Aufruf.
- **Versand:** Einzelversand am Kern (Port 8001) mit Header `X-GZ-Core-Auth`.
- **Subject-Filter:** Beide Validatoren lesen das **ganze** Postfach und filtern nur nach
  `X-GZ-Mail-Type` und `--subject-contains`, nicht nach Empfängeradresse. Eindeutig wird die
  Mail allein über den Lauf-Tag im Betreff (Trip-Name bzw. Preset-Name), deshalb immer mit
  `--subject-contains <Tag-Betreff>` aufrufen; ohne Filter kann eine fremde Mail geprüft werden.

- **Nur Mails des Dienst-Absenders (#2961):** Beim Lesen aus dem Postfach (nicht im
  Datei-Modus `--eml`) prüfen alle vier Validatoren jede sonst passende Mail mit
  `.claude/hooks/_mail_trust.py`:
  - **Absender:** genau ein `From`-Kopf mit genau einer Adresse. Erwartet sind die
    Dienst-Absender aus der Konfiguration: Test-Routing `GZ_TEST_MAIL_FROM` bzw.
    `<GZ_TEST_SMTP_USER>@henemm.com`, die Adresse des Test-Postfachs
    `<GZ_TEST_IMAP_USER>@henemm.com`, dazu `GZ_MAIL_FROM`, `GZ_INBOUND_ADDRESS`,
    `GZ_SMTP_USER`; Überschreiben kommagetrennt per `GZ_VALIDATOR_MAIL_FROM`. Auf Staging laufen
    alle Nutzer über `for_testing()`, From ist dort `gregor-test@henemm.com`, also genau das
    Konto des Test-Postfachs (`docs/context/fix-2542-staging-befehl-pruefweg.md`); der Validator
    trifft es ohne zusätzliche Konfiguration. Gelistete Adresse: in Ordnung. Adresse in der
    Domain eines erwarteten Absenders, aber nicht gelistet (z. B. `gregor_zwanzig@henemm.com`):
    `WARNUNG:`-Zeile auf stderr, keine Ablehnung. Fremde Domain: verworfen. Kein Absender
    ermittelbar: `WARNUNG:`-Zeile statt Ablehnung (fail-soft, der Deploy-Nachweis darf an
    dieser Härtung nicht fälschlich scheitern).
  - **Authentisierung:** dieselbe Auswertung wie der Produktions-Eingang
    (`services.inbound_email_reader`: RFC-8601-Parser, Quote-Sperre, nur der **erste**
    `Authentication-Results`-Kopf, authserv-id = `GZ_MAIL_SERVER_HOSTNAME`, Annahmeregel mit
    Ausrichtung zur From-Domain über DMARC, SPF **nur im Scope `smtp.mailfrom`** oder DKIM
    `header.d`). HELO-Ergebnisse wie `spf=permerror … smtp.helo=[127.0.1.1]` zählen nicht;
    Resend-Zustellungen (`dkim=pass header.d=henemm.com header.s=resend`) bestehen. Kein Kopf
    (Einlieferung über Port 587) oder ein Kopf eines fremden Servers: Teilprüfung entfällt.
    Unlesbarer Kopf des eigenen Servers oder keine ausgerichtete Bestätigung: verworfen.
  - Verworfene Mails werden übersprungen (eine fremde jüngere Mail verdrängt die echte nicht);
    findet sich keine passende Mail, nennt die Fehlermeldung die Zahl der verworfenen und den
    Grund der neuesten. Marker-Köpfe, Schwellen und Frische-Fenster bleiben unverändert.
- **Render ohne Skript und Netz (#2961):** `briefing_mail_validator.py` rendert das Mail-HTML in
  Headless-Chromium mit abgeschaltetem JavaScript; jede Anfrage außer `file:`/`data:` wird
  abgebrochen, gewartet wird auf `load` statt `networkidle`.

| Pfad | `X-GZ-Mail-Type` | Validator | Pflicht-Argumente |
|---|---|---|---|
| Trip (`full`/`compact`) | `trip-briefing` | `briefing_mail_validator.py` | `--mail-type trip-briefing --subject-contains <Tag-Betreff>` |
| Orts-Vergleich | `compare` | `email_spec_validator.py` | `--mail-type compare --subject-contains <Tag-Betreff>` |

**Grenze „Ausblick ohne Winddaten":** #1670 AC-5 (Wind-Zelle „–" statt „0" bei fehlenden
Winddaten) ist auf Staging nicht herstellbar (echte Provider liefern Wind, der Seed-Endpoint setzt
keine Wetterdaten). Belegt per **lokalem** Render-Test (abgedeckt in #1670); kein Eingriff in
Wetterdaten.

## Sprache — Kopf `X-GZ-Lang` (seit #2663, ADR-0104)

`build_mime_message()` setzt in **jeder** Mail (HTML- und Klartext-Zweig, alle
Mail-Arten inkl. Service-Mails) neben `X-GZ-Mail-Type`/`X-GZ-Format` den Kopf
`X-GZ-Lang: de|en` — die Sprache des **Inhalts** (`en` nur bei `lang="en"`,
sonst `de`). Solange ein Renderer noch Deutsch spricht, steht dort `de`.

| Marker-Header | Werte | Gesetzt von | Gelesen von |
|---|---|---|---|
| `X-GZ-Mail-Type` | `trip-briefing` · `compare` · `deviation-alert` · `official-alert` · `radar-alert` | `build_mime_message(mail_type=…)` | Dispatch aller vier Validatoren |
| `X-GZ-Format` | `full` · `compact` | `build_mime_message(mail_format=…)` (nur Trip) | `briefing_mail_validator.py` |
| `X-GZ-Compare-Hourly-Enabled` | `true` · `false` | `build_mime_message(compare_hourly_enabled=…)` | `email_spec_validator.py` |
| `X-GZ-Lang` | `de` · `en` | `build_mime_message(lang=…)`, immer | alle vier Validatoren (`.claude/hooks/_mail_lang.py`) |

Die Validatoren lesen den Kopf über `_mail_lang.mail_lang(msg)` und bilden
ihre Erwartungen (Überschriften, Hinweise, Warn-Wörter, Marker) aus dem
Python-Katalog `src/i18n` (`mail.*`, `vergleich.*`, `warnung.*`, `alarm.*`) bzw.
dem Metrik-Register (`label(lang)`, `aggregation_label`) in dieser Sprache —
nie aus Literalen. Spaltenkürzel (`col_label`) bleiben in beiden Sprachen gleich.
Ändert ein Renderer einen dieser Texte, ändert er den Katalogeintrag und damit
zugleich die Validator-Erwartung (gewollte Kopplung).

- **Widerspruch Kopf ↔ Inhalt:** Findet ein Validator keinen Text der
  Kopfsprache, aber Texte der anderen Sprache, meldet er `SPRACHE: Kopf
  X-GZ-Lang: <x> widerspricht dem Inhalt …` (Exit 1).
- **Unbekannter Wert** (z. B. `fr`): `SPRACHE: X-GZ-Lang unbekannt oder fehlt …`, Exit 1.
- **Pflicht (seit A2 #2681):** Kopf fehlt ⇒ `SPRACHE: Marker-Header X-GZ-Lang
  fehlt — Mail nicht vom sprachfähigen Renderer`, Exit 1 (`HEADER_PFLICHT = True`
  in `_mail_lang.py`). Die Übergangsregel aus PV #2663 (`de` + Warnung) ist beendet.
- **Auswahl nach Sprache und Empfänger (A2 #2681):** alle vier Validatoren haben
  `--lang de|en` (IMAP-Default `de`) und `--to-contains TEXT`. Gewählt werden nur
  Mails mit `X-GZ-Lang == --lang` **und** passendem Empfänger (`en`: `To` enthält
  `+en@`, `de`: nicht) — `_e2e_paths.mail_passt_zu_sprache`. Eine Mail **ohne**
  Kopf an die Adresse des Nutzers bleibt wählbar und scheitert dann an der Pflicht
  (kein stilles Ausweichen auf eine ältere Mail). Mit `--eml` gelten `--lang`/
  `--to-contains` als Prüfung der Datei (passt sie nicht: Exit 1).
  Zwei Staging-Nutzer: `de` = `gregor-test@henemm.com`, `en` =
  `gregor-test+en@henemm.com` (`scripts/staging_e2e_user_en.py`).
- **Folgearbeit P2–P6 (Pflicht vor der ersten englischen Mail des Pakets):**
  Folgende Erwartungen sind noch **feste deutsche Texte** in den Validatoren,
  weil sie nicht zum PV-Schlüsselsatz gehören. Das Renderer-Paket, das den
  jeweiligen Text zuerst englisch ausgibt, legt ihn im Katalog an und stellt
  den Validator an derselben Stelle auf `erwartet(key, lang)` um — sonst lehnt
  der Validator die korrekte englische Mail ab:
  - `Stand: heute` (Footer P-5) und die Handlungsempfehlungs-Wörter (E-4,
    `_RECOMMENDATION_WORDS`) in `official_alert_mail_validator.py`;
  - der Ortskopf `ORT` im Ortsvergleich (`email_spec_validator.py`,
    `_find_location_hour_table`);
  - die Compact-Blöcke `== Metriken-Ueberblick ==`, `Report`, `Generated:`
    (`briefing_mail_validator.py`, `_check_compact_blocks`);
  - die Pille `Sonne Xh` (`briefing_mail_validator.py`, `_check_metric_plausibility`).
- **Datei-Modus `--eml PFAD`** (alle vier Validatoren): prüft eine gespeicherte
  Mail statt der IMAP-Mail, Exit-Codes unverändert (0/1/2). Damit laufen die
  Golden-Fixtures `tests/fixtures/mail/*_de.eml` ohne Netz
  (`tests/unit/test_*_sprache.py`). Der Nachweis für „E2E bestanden" bleibt die
  echt zugestellte Staging-Mail.

**Was wechselt und was bleibt:** Überschriften, Hinweise, Warn-Wörter und Betreffmuster wechseln mit
der Kopfsprache. Kürzel und Token bleiben gleich: Spaltenkürzel `col_label`, Kürzel der Token-Zeile und
`sms_code` werden nie übersetzt.

**Prüfung:** Die Golden-Fixtures `tests/fixtures/mail/*_de.eml` prüfen den Datei-Modus ohne Netz; der
Nachweis „E2E bestanden" bleibt die echt zugestellte Staging-Mail in der Kopfsprache. Die deutsche
Renderer-Ausgabe ist byte-genau über `tests/golden/` abgesichert (`docs/reference/renderer_email_spec.md`,
Abschnitt „Sprache").

## Soll aus der gespeicherten Konfiguration — `--konfig PFAD` (seit #3047)

> **Stand seit #3122 ([ADR-0124](../adr/0124-was-steht-wo-eine-tabelle.md), gebaut):** Im Reiter Wetter ersetzt **eine** Tabelle „Was steht wo“ die Listen je Kanal und Fläche; gespeichert als `display_config.placements`. Das Validator-Soll liest diese Tabelle (`placements.rows`, Regeln „Quelle der Darstellung“ und „Auswahl und Reihenfolge mit Tabelle“ unten); die Altfelder (`channel_layouts`, `channel_active_metrics`, `outlook_metrics`, `hourly_metrics` …) wirken seit #3237 nicht mehr. Die Abnahme „Einstellung = Ausgabe“ gegen den Katalog #3047 läuft in #3037.

`briefing_mail_validator.py` und `email_spec_validator.py` nehmen optional
`--konfig PFAD`: das **rohe gespeicherte JSON des Test-Nutzers**, wie die Go-API
es liefert (Trip: das ganze Trip-Objekt mit `display_config`/`report_config`;
Orte: das Preset, für die Ortsfolge mit `--orte PFAD` oder als Hülle
`{"preset": {...}, "orte": {"<id>": "<Name>"}}`). `.claude/hooks/_soll_aus_konfiguration.py` leitet daraus
das Soll ab — nur aus der Datei und dem statischen Register (`col_label`,
`label`, Compare-Katalogtabelle), **nie** über ein `resolve_*` des Produkts
(Spiegel-Test-Verbot; einzige Ausnahme: Ausblick je Briefing, #3155, unten). `pruefe_soll(msg, soll, lang)` vergleicht dann im
**HTML- und im Klartext-Teil**:

- **Trip:** Spaltenfolge jeder Etappen-Stundentabelle und der Nachttabelle
  (E-Mail-Liste der Kaskade, nach `bucket`/`order`), Kopf des 3-Tages-Ausblicks;
  im Kompaktformat die Folge der Ausblick-Tokens; `show_night_block`,
  `email_format`, Ausblick an/aus. Dazu die **Darstellung Roh/Einfach je
  Spalte** (Stunden-, Nacht-, Ausblick-Tabelle, HTML und Klartext): Roh = Zahl,
  Einfach = Symbol/Wort oder Ampelpunkt. Gewollte Ausnahmen (Spec §2 Punkt 3):
  Wind/Böen/Regen/Regen-W. zeigen Einfach im HTML als Ampelpunkt (#814), im
  Klartext als Wortstufe (Regen-W. Skala 25/50/75, #435/#3156); Gewitter zeigt roh schon das Stufenwort (im Klartext und im
  Ausblick ungeprüft); Visibility/Temperatur haben im Ausblick keine
  Einfach-Form (immer Zahl); die verschmolzene Windrichtung hat keine eigene
  Spalte (#435). Die Meldung nennt Tabelle und Spalte („Darstellung
  Etappen-Stundentabelle (Klartext) 1: Spalte 'Cloud' soll Symbol/Wort
  (Einfach) zeigen, zeigt Zahl (Roh)").
- **Orte:** Zeilenfolge der Vergleichstabelle (`channel_layouts.email` vor
  `channel_active_metrics.email`, geschnitten mit `active_metrics`), Ortsfolge (`location_ids`), Spalten des
  Stundenverlaufs je Ort (`hourly_metrics`, `hourly_enabled`), Ausblick-Kopf
  (`outlook_metrics`, `outlook_enabled`). Diese Altfeld-Regeln sind seit #3237 überholt:
  gelesen wird nur noch die Tabelle `placements.rows` (Regel „Auswahl und Reihenfolge mit Tabelle (#3242)“);
  ein Abo ohne Tabelle wird aus seiner Grundauswahl umgerechnet.

Soll-Regel Orte-Stundenverlauf (Konzept §5.8 „Jede Liste nimmt nur aus den
Metriken oben"): gespeichert = Schnitt mit der Grundauswahl (`active_metrics`)
in gespeicherter Folge; bleibt von einer nicht leeren Liste nichts übrig, die
Vorgabespalten (`HOURLY_DEFAULT_METRIC_IDS`) geschnitten mit der Grundauswahl,
sonst deren stündlich wählbare Größen; nie eingestellt = Grundauswahl, soweit
stündlich verfügbar, in deren Folge; ohne Grundauswahl die Vorgabespalten.

**Ortsfolge braucht Namen:** das rohe Preset trägt nur `location_ids`. Die
Namen kommen aus `--orte PFAD` (Orts-Verzeichnis `data/users/<id>/locations/`,
die JSON-Antwort von `GET /api/locations` oder `{"<id>": "<Name>"}`) oder aus
der Hülle. Fehlen sie, scheitert der Lauf mit „SOLL: Ortsfolge nicht prüfbar"
(Exit 1), statt die Ortsfolge still zu überspringen.

**Hülle (Orte):** `{"preset": {...}, "orte": {"<Kennung>": "<Name>"}}` — `orte`
ist ein Objekt Kennung → Name, keine Liste. Die Hüllen-Prüfung läuft beim Start
des Validators **immer**, sobald `--konfig` gesetzt ist, also auch mit `--orte`
und `--min-locations`. Eine falsche Hülle (Liste oder anderer Typ) endet mit
Exit 2 und der Meldung „FEHLER: --konfig … Huelle: 'orte' muss ein Objekt
{\"<Kennung>\": \"<Name>\"} sein" statt mit einem Traceback (#3218).

**Quelle der Darstellung Roh/Einfach (#3218):** Trägt das Abo die Tabelle
`display_config.placements` (Zeilenliste `rows`), gilt für die Darstellung
allein `rows[].formats` — wie im Renderer: Trip-Stundentabelle (`formats.email`,
HTML inklusive Ampel-Ausnahme, Klartext), Orte-Vergleichstabelle
(`formats.email`) und Ausblick Trip und Orte (`formats.outlook`). Es zählt die
erste Zeile je `metric_id`; ein Wert gilt nur an einer Stelle mit zwei Formen
(`zwei_formen_stellen`) und nur als `raw`/`simplified`; fehlt er oder ist er
ungültig, gilt der Katalog-Standard (`standard_form`), Trip und Orte gleich.
Eine abgeleitete Größe ohne eigene Zeile (z. B. Nachttief) liest die
Eltern-Zeile (`_DERIVED_METRIC_RULES`). Die Altfelder (`use_friendly_format`,
`format_mode`, `channel_layouts.email`, `outlook_metric_formats`) werden seit #3237 nicht mehr gelesen; ohne Tabelle gilt die Grundauswahl-Umrechnung.

**Auswahl und Reihenfolge mit Tabelle (#3242):** Mit `placements` folgen auch
Auswahl und Folge der Tabelle (`_tabellen_folge`, statische Zweitregel ohne
`resolve_*`): Zeilen der Grundauswahl in gespeicherter Folge, abgeleitete Größe
ohne Zeile direkt hinter der Eltern-Zeile mit deren Haken, übrige Grundauswahl
hinten (überall an), `rows: []` = ganze Grundauswahl; `places[stelle] is False`
= aus; Sperre laut `stellen_sperre` entfällt, außer `keine_eigene_spalte`
(Trip-Fenstergrößen bleiben in der E-Mail-Liste); Ausblick und Orte-Stundenverlauf
nur bei E-Mail an. Gilt für Trip-Stundentabelle und -Ausblick sowie Orte-
Vergleichstabelle (Katalog-ID aufgeweitet auf ihre Auswertungen der
Grundauswahl), -Stundenverlauf und -Ausblick; Orte ohne `active_metrics` nehmen
die Standardzeilen. `channel_layouts`, `outlook_metrics`, `hourly_metrics` und
die `metrics`-Folge wirken nicht mehr (seit #3237 auch nicht ohne Tabelle; dort gilt die Grundauswahl).
Trips ohne `display_config` bzw. nur mit `placements` (#3273) nehmen wie der Loader
die Grundauswahl aus `weather_config` (Altnamen), sonst aus der Profil-Vorlage
(Rückfall `allgemein`), von Hand im Soll abgeschrieben (ADR-0127 Nr. 5); den
Gleichlauf mit dem Loader bewacht `tests/tdd/test_3273_trip_grundauswahl_ohne_metrics.py`.

**Bekannte Einschränkung (#3242):** Abgeleitete Größen mit Fenstercharakter (z. B. Nachttief) bleiben in der Trip-E-Mail auch bei ausgeschalteter Eltern-Zeile, wie im Produkt (`keine_eigene_spalte`); das Haken-Erbe von der Eltern-Zeile wirkt nur bei künftigen abgeleiteten Größen, die keine Fenstergrößen sind.

Soll-Regel Ausblick (beide Kontexte): `[]` = Block aus; nie eingestellt = ganze
Grundauswahl in der eingestellten Reihenfolge; sonst Schnitt mit der
Grundauswahl, leerer Schnitt = volle Grundauswahl; ohne Grundauswahl die sieben
festen Spalten — im Klartext dieselben wie im HTML. Jede Abweichung ist Exit 1
mit einer `SOLL:`-Meldung, die die Spalte nennt („Spalte fehlt: 'Rain'",
„Spalte zu viel: 'UV'", „an Position 1 steht 'Temp' statt 'Gust'"), ebenso ein
Block, der nur in einem der beiden Teile steht. Nie eingestellte Listen ohne
dokumentierte Folge (Trip-Altbestand ohne `metrics`, Orte-Vergleichstabelle
ohne `active_metrics`) prüft der Validator nicht; ihre Vorgabe
sichert der Editor-Standard-Abgleich (AC-13). Ohne `--konfig` ist das Verhalten
unverändert.

**3-Tages-Ausblick: ein Name, ein Briefing (#3155, Scheibe B4, AC-12)**, nur mit `--konfig`:

- **Soll aus einer Regel:** ob der Ausblick im Morgen- bzw. Abend-Briefing steht,
  liefert `ausblick_briefings` in `_soll_aus_konfiguration.py` über die **echten**
  Funktionen aus `src/services/placements.py` (Spec-Vorgabe, bewusste Ausnahme vom
  `resolve_*`-Verbot oben): mit Tabelle `resolve_outlook_reports` + `outlook_applies`,
  sonst `_legacy_outlook_reports` (Trip samt Kompakt-Ausnahme, Orte samt
  Anlage-Marke `display_config.placements.outlook_reports` ohne `rows`). Die
  Altfelder `show_outlook`/`multi_day_trend_reports` liest der Validator nicht mehr selbst.
- **Nur im eingestellten Briefing:** ein Ausblick im falschen Briefing scheitert
  mit „SOLL: Ausblick (HTML) erscheint im Abend-Briefing, laut Konfiguration steht
  er nur im Morgen-Briefing“; fehlt er im eingestellten Briefing, „Ausblick-Block
  (…) fehlt (kein Titel '3-Tages-Ausblick')“ (Trip: außer an der letzten Etappe).
  Briefing der Mail: Trip aus Kopf/Betreff („Evening Report“/„Abend-Briefing“);
  Orte (kein Briefing-Kopf) aus `--briefing morning|evening`, sonst aus dem Slot
  (nur ein Briefing an) bzw. dem Zieltag (Morgen = Erstellungstag, Abend =
  Folgetag). Hängt der Ausblick am Briefing und ist es nicht ablesbar: Exit 1 mit
  Hinweis auf `--briefing`. `--briefing` ohne `--konfig` ist Exit 2.
- **Blockname** in der Sprache von `X-GZ-Lang`: „3-Tages-Ausblick“/„3-day outlook“
  (Trip: HTML-Eyebrow `mail.ausblick.eyebrow`, Klartext `mail.ausblick.name`,
  Kompakt dessen ASCII-Form; Orte: `vergleich.ausblick.eyebrow`/`.titel`). Ein
  früherer Name als eigener Blocktitel („Nächste Etappen“, „Ausblick“,
  „Ausblick · nächste 3 Tage“, „Mehrtages-Trend“, „3-Tages-Vorschau“, EN „Next
  stages“, „Outlook“ …) scheitert mit „Ausblick-Block (Klartext) heisst 'Nächste
  Etappen' statt '3-Tages-Ausblick'“. Tests: `tests/tdd/test_validatoren_ausblick_3155.py`.

Randfälle (dritte Nachprüfung #3047, N1–N7), alle nur mit `--konfig`:

- **Totalschnitt ≠ bewusst leer (AC-10):** liegt eine nicht leere gespeicherte
  Liste (Trip-E-Mail-Liste, Orte-Kanal-Liste, Ausblick, Stundenverlauf) ganz
  außerhalb der Grundauswahl, ist das Soll die volle Grundauswahl. Eine bewusst
  leere Liste (`[]` bzw. alle Einträge aus) bleibt leer.
- **Bewusst leere Grundauswahl:** Trip alle `enabled: false` bzw. Orte
  `active_metrics: []` → keine Metrikspalten/-zeilen, Stundenverlauf und
  Ausblick entfallen; im Trip-Kompaktformat entfällt auch der
  „Metriken-Ueberblick" (erscheint er doch: Exit 1). Die Orte-Klartext-Übersicht
  nennt die Orte dann ohne Zeilen — kein falsches „Ort fehlt".
- **Verwaiste Überschriften (Trip, Vollformat):** eine Etappen-, Ziel- oder
  Nacht-Überschrift ohne folgende Stundentabelle ist Exit 1
  („verwaiste Ueberschrift (HTML) 'SEG 1'"); Fehler-Etappen mit Hinweistext
  ausgenommen.
- **Roh/Einfach:** der Trip-Kompakt-Ausblick wird je Spalte wie der Klartext
  geprüft (`outlook_metric_formats`; „Darstellung Ausblick (Kompakt)"). Orte:
  Vergleichszeilen, die `channel_layouts.email` auf Einfach stellt
  (Ampelpunkt/Wort ohne Zahl), sind kein FORMAT-Fehler.

Randfälle (vierte Prüfung #3047, F001–F008a), alle nur mit `--konfig`:

- **Zeilenpräfix im Ausblick (F001):** Wochentag (EN „Sun") und im
  Trip-Klartext das 26 Zeichen breite Etappennamen-Feld („Wind Pass",
  „Sun Valley") stehen vor den Werten und sind keine Spaltenkürzel; sie werden
  vor der Kürzelsuche abgetrennt (`ausblick_kuerzel`).
- **Leere E-Mail-Liste mit Ausblick (F002):** die Sichtbarkeitsprüfung bei
  390px/1000px hängt nur an den Stundentabellen; erwartet das Soll einen
  Ausblick, muss dessen Tabelle (Kopfzelle „Tag"/„Day") bei beiden Breiten
  sichtbar sein.
- **Ortsabschnitte im Orte-Klartext (F006):** Anzahl und Folge der
  Ortsabschnitte gegen `location_ids` (Fehler-Orte ausgenommen); je Ort muss
  der Stundenverlauf bzw. der Ausblick stehen, wenn er laut Konfiguration an
  ist („Stundenverlauf (Klartext) fehlt bei Ort 'Kufstein'").
- **Ortszahl aus der Konfiguration (F008a):** ohne ausdrückliches
  `--min-locations` gilt die Ortszahl der Konfiguration; eine Kennung ohne
  Ortsdatei (gelöschter Ort) fällt wie im Versand heraus
  (`order_locations_by_ids` aus `src/services/compare_briefing_aufbau.py`, seit #2983). Ein gesetztes `--min-locations` hat Vorrang.
- **Verschmolzene Windrichtung (F004):** Windrichtung Einfach neben Wind (keine
  eigene WDir-Spalte) → jede Wind-Zelle der Etappen- und Nachttabelle trägt eine
  Kompassrichtung, im HTML auch neben dem Ampelpunkt, im Klartext („20 W");
  die Richtung je Stunde ist im HTML dieselbe wie im Klartext.
- **Färbung der Windrichtung (seit #3228):** Wind- bzw. WDir-Zellen können nach Gegenwind oder
  Sektor getönt sein (Details: `renderer_email_spec.md`, Abschnitt „Windrichtung: Färbung“). Die
  Validatoren prüfen diese Tönung seit #3232 mit `--windrichtung` (Abschnitt „Windrichtungs-Färbung“
  unten; Nachweis gegen zugestellte Gate-Mail).
- **Metriken-Überblick nur mit Kachel (F008b):** der Überblick (Voll: HTML und
  Klartext, Kompakt) steht genau dann in der Mail, wenn eine Größe der
  E-Mail-Liste dieses Berichts eine Kachel trägt (weiße Liste `_PILL_CATALOG_ORDER`);
  nur z. B. `temperature_night` gewählt → kein Überblick. Kacheln, die mangels
  Werten entfallen, sind aus der Konfiguration nicht ableitbar.

Randfälle (fünfte Prüfung #3047, F1, F2, A3c), alle nur mit `--konfig`:

- **Maskierte Namen im HTML (F1):** der Renderer maskiert Ortsnamen und
  Beschriftungen („Col d'Izoard" → `d&#x27;Izoard`, „&" → `&amp;`). Beide
  Validatoren vergleichen Namen, Zeilen- und Spaltenbeschriftungen aus dem HTML
  als Text (`html.unescape`) gegen das Soll; die korrekte Mail besteht.
- **Lange Etappennamen im Trip-Klartext-Ausblick (F2):** der Renderer kürzt
  den Namen nicht (`f"{name:<26} "`); ein längerer Name schiebt die Werte nach
  rechts und kann Kürzel enthalten („… Lake Of Sun"). Bekannte Namen
  (`stages[].name` der Konfiguration) werden exakt abgetrennt; sonst gilt die
  Zeilenstruktur: die erste Spalte ist das letzte Kürzel vor dem ersten
  Doppel-Leerzeichen hinter dem 26-Zeichen-Feld. Hinweiszeilen („↳") gehören
  nicht zu den Spalten.
- **Roh/Einfach im Orte-Ausblick (A3c):** der Orte-Validator prüft die
  Ausblick-Zellen in HTML und Klartext je Spalte gegen `outlook_metric_formats`
  — dieselbe Mechanik wie der Trip (`darstellung_meldungen` in
  `_soll_aus_konfiguration.py`), dieselben Ausnahmen (Visibility, Temperatur
  ohne Einfach-Form, Gewitter ungeprüft); Meldung „Darstellung Ausblick
  (Klartext) 1: Spalte 'Rain' soll Symbol/Wort (Einfach) zeigen, zeigt Zahl (Roh)".

Ergänzungen Runde 7 (#3047 AC-27/AC-28), alle nur mit `--konfig`:

- **Ausblick-Tageszeilen (B-V1):** Trip: HTML und Klartext tragen gleich viele
  Zeilen; ist das Mail-Datum (Klartext-Kopf `TT.MM.JJJJ`) ein Etappendatum der
  Konfiguration, sind es die folgenden Etappen, höchstens drei
  (`ausblick_zeilen_trip`), auch im Kompaktformat. Eine still ausgefallene
  Etappe (Teilausfall ohne Zustandshinweis) fällt damit auf. Orte: jeder Ort hat
  im HTML einen Ausblick-Abschnitt (Tabelle oder Hinweis „nicht abrufbar"),
  jede Ausblick-Tabelle bzw. jeder Klartext-Block mit Zeilen drei Tageszeilen
  (Tagesfenster über Mitternacht: zwei oder drei).
- **Zusatzblöcke (B-V2), nur Vollformat:** `show_stage_stats: false` →
  keine Kennzahl-Kacheln (HTML) bzw. Zeile `12.3 km | ↑800m` (Klartext);
  `show_yesterday_comparison: false` → kein Vortag-Vergleich. „An" wird nicht
  verlangt (datenabhängig). Das Kompaktformat ignoriert die Baustein-Schalter
  (PO-Entscheidung #722): Kennzahlen und Ausblick trotz Aus sind dort kein Fehler.
- **Roh/Einfach der Vergleichstabelle (B-V3):** je Zeile laut
  `channel_layouts.email` — Einfach: HTML Ampelpunkt (Wind, Böen,
  Niederschlag, Regenwahrscheinlichkeit) bzw. Wort, Klartext Wort; sonst Zahl.
  Gewitter, Niederschlagsart, Windrichtung ungeprüft. Meldung „Darstellung
  Vergleichstabelle (Klartext) 1: Spalte 'Wind' …".
- **Klartext-Stundenverlauf (B-V4):** jede Stundenzeile je Ort, nicht nur die erste.
- **Tagesfenster (B-V5):** Orte: `day_window_start_hour`/`_end_hour` nach der
  Regel aus ADR-0035 (beide 0–23, verschieden, sonst 4–19; Start > Ende = über
  Mitternacht). Erwartet sind die Kernstunden 09–16 innerhalb des Fensters, eine
  Stunde außerhalb ist ein Fehler — ein gesetztes Fenster wird nicht abgelehnt.
  Trip: die Stunden der Etappentabellen sind Etappenzeiten; mit `--konfig` gilt
  statt der festen Heuristik 06–22 das Band aus Tagesfenster und Etappenstart
  (siehe unten „Stundenband", B-L5).
- **Ortsabschnitte sprachunabhängig (B-V7):** Abschnittsköpfe werden am Aufbau
  erkannt (Etikett-Span + Name), nicht am Wort „ORT" (#3074); ausgenommen sind
  nur die Katalog-Etiketten Übersicht/Stunden/Ausblick. Bei Stundenverlauf an
  muss jeder erwartete Ort (ohne Ortsfehler) einen Abschnitt haben.
- **Amtliche Warnungen (AC-28, E4):** die Warnzeile der HTML-Vergleichstabelle
  gehört zum Soll, wenn der Briefing-Schalter (`official_alerts_enabled`) oder
  der Alarm-Schalter (`official_warnings.enabled`, sonst
  `official_alert_triggers_enabled`) an ist („beides an"); nur beide aus = keine
  Zeile. Ohne Warnzeile wird die Übersichtstabelle über die Kopfzelle
  „Metrik"/„Metric" gefunden. Der Hinweis „Amtliche Warnungen aktuell nicht
  abrufbar" steht im HTML genau dann, wenn er im Klartext steht.
- **Trip-Altformat ohne `order` (B-L6):** Einträge ohne `bucket` und `order`
  (Zeichenkette bzw. Objekt ohne beides) folgen der Register-Priorität wie im
  Loader (`auto_distribute`, `METRIC_PRIORITY`), nicht der Array-Folge
  (Tech-Lead-Entscheidung Runde 7).

Lückenschluss Runde 7 (#3047 B-L5, Paket p4b), alle nur mit `--konfig`:

- **Trip, amtliche Warnungen:** Schalter nach der E4-Regel („Briefing ODER
  Alarm an → beides an", `warnungen_an`). Beide aus → weder Warnblock (HTML
  `.wb`, Klartext `━━ Amtliche Warnungen ━━`, Kompakt `== Warnungen ==`) noch
  Hinweis „nicht abrufbar" (kein Abruf). An → stehen sie, wenn vorhanden, an
  erster Stelle (WV6/AC-25): Klartext/Kompakt erste Inhaltszeile nach dem Kopf
  (davor höchstens der Hinweis „nicht abrufbar"), HTML vor Tageslage,
  Metriken-Überblick und erster Etappentabelle. Meldungen
  „Amtliche Warnungen (Klartext) erscheinen, obwohl …" bzw. „… stehen nicht an
  erster Stelle".
- **Trip, Kachelfolge des Metriken-Überblicks:** die Kacheln folgen der Folge
  der E-Mail-Liste (#1703 S7) in HTML, Klartext und Kompakt; die Metrik einer
  Kachel wird am Katalogtext (`mail.pille.*`, Register-Label) erkannt, eine
  unbekannte Form bleibt ungeprüft, eine fehlende Kachel (keine Werte) ist
  erlaubt, eine Kachel einer nicht gewählten Größe ist ein Fehler.
- **Ampelfarbe (Trip und Orte):** Grenzen nach der Rückfallkette ADR-0106
  (`ampel.template` > `preset_name` > Profil > „allgemein", Abo-Grenzen je
  Metrik überschreiben; gelesen wird nur die statische Vorlagentabelle). Trip:
  je Stunde für Wind, Böen, Regen, Regen-W. — Zahl-Zelle (Roh) gegen ihre Tönung
  (ungetönt = grün); Ampelpunkt (Einfach) gegen die Klartext-Zahl derselben
  Stunde, sonst gegen den Rohwert aus `--ampel-werte JSON` (Prüfdaten, nur mit
  `--konfig`: `{"gust": {"1": [45, …]}}`, Größe → Segment N = N-te
  Etappen-Stundentabelle → Wert je Stunde; ungültig = Exit 2). Die Wortstufe
  des Klartexts (seit Spec #3122 Nr. 4) ist kein Vergleichswert: ihre Skala ist
  fest, die Ampel folgt den Grenzen des Abos (#3237). Ampelpunkt ohne Zahl und
  ohne Rohwert = Befund „kein Vergleichswert“, nie stilles Bestehen. Erste
  Abweichung je Tabelle und Spalte. Orte: Tönung der Zahl-Zellen der Vergleichstabelle
  (Temperatur, Wind, Böen, Niederschlag, Regen-W., UV; Sicht ungeprüft). Eine
  gerundete Zahl darf eine halbe letzte Stelle abweichen.
- **Trip, Stundenband:** erlaubt sind Stunden vom früheren aus Tagesfensterbeginn
  (Regel `tagesfenster` = ADR-0035) und Etappenstart (`stages[].start_time`,
  Vorgabe 08:00), höchstens 06, bis zum späteren aus Fensterende und 22;
  Fenster über Mitternacht → keine Stundengrenze. Ein Etappenstart 04:30 lehnt
  die korrekte Mail damit nicht mehr ab. Ohne `--konfig` bleibt 06–22.
- **Orte, Grundauswahl nie eingestellt** (`active_metrics` fehlt, keine
  Kanal-Liste): Soll = alle Zeilen der Vergleichstabelle in Standardfolge
  (`CV2_ZEILEN`), wie die Mail; vorher blieb die Zeilenliste ungeprüft.
- **Orte, Zieltag:** Klartext `Datum:` gegen `Erstellt:` — Morgen-Slot
  (`morning_enabled`, Vorgabe an) = derselbe Tag, Abend-Slot
  (`evening_enabled`) = der Folgetag; sind beide an, ist beides erlaubt.
- **Orte, Hinweis „nicht abrufbar" bei Schalter aus:** beide Schalter aus →
  kein Abruf, also auch kein Hinweis (HTML und Klartext).

Nachweis: `test_r7b_*` in `tests/tdd/test_einstellung_gleich_mail_validatoren.py`
(echte Mail besteht, gezielt verfälschte scheitert).

Bereichsname „Orte“ (#3122 B5, ADR-0124 Nr. 10, AC-35/AC-36), nur mit `--konfig`:

- **Kopf:** HTML-Kennzeile `ORTE · {Vorlage}` (EN `LOCATIONS · …`), erste
  Klartext-Zeile `ORTE`/`LOCATIONS`; sonst `NAME: Kopf 'ORTE' fehlt (HTML|Klartext)`.
- **Alter Bereichsname:** „Vergleich“ (deckt „Orts-Vergleich“, „Ortsvergleich“)
  und „Orts-Briefing“, in englischen Mails zusätzlich „comparison“, im
  lesbaren HTML-Text und im Klartext → `NAME: alter Bereichsname (…)`.
- **Nutzerdaten zählen nicht:** Orts- und Abo-Namen aus Konfiguration und Mail
  (z. B. „Vergleichsberg“, „Comparison Peak“, bei einem Ort „Alle Orte Bar“)
  werden vor der Prüfung ausgeblendet; geprüft werden nur die festen Texte.
- **Genau ein Ort** (eine Ortsspalte in der Übersicht): kein „alle Orte“/„1 Orte“
  (EN „all locations“/„1 locations“) → `NAME: Text setzt mehrere Orte voraus (…)`;
  der Fuß trägt „1 Ort · Vorlage“ (EN „1 location · Template“), sonst
  `NAME: Fuss '1 Ort · Vorlage' fehlt bei einem Ort (HTML)`. Die Untergrenze
  der Ortszahl (`--min-locations`, ohne `--konfig` 3) bleibt bei #2798.

Nachweis: `test_b5_*` in `tests/tdd/test_einstellung_gleich_mail_validatoren.py`.

**Auflösung des Verbots aus #1381:** Eine feste Spaltenfolge (`_HOUR_COLUMNS_V2`)
wird weiterhin **nie** vorausgesetzt — die Folge ist seit #1359 frei
einstellbar, die alte Kanon-Projektion lehnte korrekte Mails ab und blockierte
das Renderer-Commit-Gate #811. Neu ist nur, dass das Soll nicht mehr fest ist,
sondern aus der gespeicherten Konfiguration genau dieses Nutzers stammt: eine
Mail mit der vom Nutzer gewählten Folge besteht immer, eine abweichende nicht.
Reihenfolge nur gegen die gespeicherte Konfiguration, nie gegen eine feste
Folge. Nachweis ohne Netz: `tests/tdd/test_einstellung_gleich_mail_validatoren.py`
(per `--eml`, Fallliste `tests/fixtures/einstellung_gleich_mail/fallliste_validatoren.json`).

```bash
uv run python3 .claude/hooks/briefing_mail_validator.py --mail-type trip-briefing \
    --subject-contains "<Marker>" --to-contains "<Nutzer>" --konfig trip.json
uv run python3 .claude/hooks/email_spec_validator.py \
    --subject-contains "<Marker>" --to-contains "<Nutzer>" --konfig preset.json --orte orte.json
```

Das Postfach ist geteilt: `--konfig` setzt voraus, dass die geprüfte Mail dem
Nutzer des JSON gehört (Auswahl über `--to-contains`).

Bequemer Weg gegen echt zugestellte Staging-Mail (#3037): der Mail-Prüfweg legt
Wegwerf-Nutzer und Objekt an, liest es per API (`GET /api/trips/{id}` bzw.
`/api/compare/presets/{id}`), legt `konfig.json` (+ `orte.json`) privat (0700/0600)
ab, ruft den Validator mit `--konfig`/`--orte`/`--to-contains +<tag>@` und löscht alles danach:
`python3 .claude/tools/staging_mail_pruefen.py --typ trip|compare --konfig [--orte-anzahl 1|3]`
(GET-Fehler ⇒ Exit 2, kein Validator-Lauf).

## Windrichtungs-Färbung — `--windrichtung JSON` (seit #3232, Nachzug #3228)

Beide Validatoren prüfen mit `--windrichtung` die Windrichtungs-Färbung aus #3228
gegen ein **ausdrückliches Soll**. Das Soll druckt `scripts/send_gate_test_mails.py`
je Gate-Mail als Zeile `Soll Windrichtung: {…}`. Der Validator rechnet die Stufe
nicht nach (Schutz gegen Selbstbestätigung). Ohne den Schalter bleibt jedes
Verhalten unverändert.

- **Briefing** (`briefing_mail_validator.py`, Schlüssel `wind_zellen`):
  Segment-ID (Zahl-Text) → erwartete Stufe der Wind-Zelle je Stunde. Geprüft werden
  Tönung und Ampelpunkt. **Positionsregel:** Segment N = N-te Etappen-Stundentabelle
  der Mail (ohne Nacht). IDs außerhalb 1..Tabellenzahl werden gemeldet, nie still
  übersprungen. Nur Format `full`. Bei anderem `X-GZ-Format` meldet der Validator
  `SOLL: Windrichtung nur im Format full pruefbar (X-GZ-Format=…)`. Im Ampel-Modus
  setzt der Renderer zu jeder Tönung einen Punkt derselben Stufe. Fehlt er bei einer
  Tönung ungleich green, lautet die Meldung `Toenung X/Punkt fehlt`.
- **Vergleich** (`email_spec_validator.py`, Schlüssel `orte`): Ortsname →
  `[Stufe Windrichtungs-Zeile der Vergleichstabelle, Stufe Wind-Zelle je Stunde]`.
  Der Stundenverlauf wird als Liste verglichen, die Meldung nennt die Stunde.
- Gemeinsame Hilfsfunktion `zellstufe()` und Eingabeprüfung
  `windrichtung_soll_parsen()` in `_soll_aus_konfiguration.py`. Ungültige Eingabe
  (kein JSON, kein Objekt, Schlüssel fehlt, nicht numerische Segment-ID) endet mit
  `FEHLER: --windrichtung ungueltig: <Grund>` und **Exit 2**. Exit 1 bleibt „Spec verletzt“.

```bash
uv run python3 .claude/hooks/briefing_mail_validator.py --mail-type trip-briefing \
    --subject-contains <token> --windrichtung '<Soll Windrichtung Briefing>'
uv run python3 .claude/hooks/email_spec_validator.py --mail-type compare \
    --subject-contains <token> --windrichtung '<Soll Windrichtung Vergleich>'
```

`<token>` und das Soll stammen aus der Ausgabe von `send_gate_test_mails.py` (`--only briefing`
bzw. `--only compare`, Zeilen `Token fuer diesen Lauf: …` und `Soll Windrichtung: …`). Mails mit
Tag-Betreff aus `staging_mail_pruefen.py` haben kein festes Soll; dort kein `--windrichtung`.

Nachweis ohne Netz: `tests/tdd/test_feat_3228_windrichtung_validatoren.py`.

## 1. `email_spec_validator.py` — Orts-Vergleich-Mail (ZWINGEND)

**Geltungsbereich:** prüft **ausschließlich** den **Orts-Vergleich-Mail**-Pfad, seit
Issue #1108 auf den **v2-Vertrag** (`render_compare_html()`, Issue #1110) umgestellt.
Fest auf dessen Struktur verdrahtet: eine **Übersichtstabelle** (Metriken × Orte)
mit der Warn-Zeile „Amtliche Warnungen" als **erster Datenzeile** (identifiziert
die Tabelle, ersetzt die alte `class="matrix-table"`-Erkennung) sowie eine
**Stundentabelle je gelistetem Ort**. Seit Issue #1106 sind die Stundenverlauf-
Spalten konfigurierbar (9 wählbare Wert-Spalten: Temp/Gef./Wind/Böen/Regen/UV/
Gew./Regen-W./Sicht, Wolken entfernt), seit Issue #1359 auch ihre Reihenfolge.
Der Validator prüft dafür **keinen Exakt-Vertrag**: `_HOUR_COLUMNS_V2` ("Zeit"
+ die 9 Metriken) ist eine **Allowlist, keine Reihenfolge-Vorgabe** (#1381).
Gültig ist eine **Teilmenge in beliebiger Reihenfolge**: "Zeit" muss erste
Spalte sein und mindestens eine Wert-Spalte muss vorhanden sein
(Mindestspalten-Regel), jede weitere Spalte muss in `_HOUR_COLUMNS_V2` stehen
(keine Fremdspalten) und darf nur einmal vorkommen (keine Duplikate) — beides
mit eigener Fehlermeldung, die die betroffene Spalte benennt. Zusätzlich gilt
eine **Cross-Location-Konsistenz-Regel** (Adversary-Fix #1106): die
Spaltenauswahl **und ihre Reihenfolge** gelten mail-weit für alle Orte in einem
Versand — weicht die Stundentabelle eines Ortes von der des ersten
(strukturell gültigen) Ortes ab, ist das ein Fehler, auch wenn beide Tabellen
isoliert betrachtet je eine gültige Teilmenge wären. Es gibt **keine feste Metrik-Zeilenanzahl** mehr in der
Übersichtstabelle — sie darf preset-bedingt auf Warn-Zeile + einzelne
Metriken gefiltert sein (#1104); Mindestanforderung ist Warn-Zeile +
≥1 numerische Zeile. **Score-/Winner-Sprache ist ein Fehler, keine Pflicht** —
es gibt keine Winner-Box/„Empfehlung"-Sektion mehr; ein Treffer auf „Score"
(mit Zahlen-Kontext), „Winner", „Empfehlung", „Bester Standort" oder „🏆" im
Mail-Body wird als Vertragsverletzung gemeldet (Wortgrenzen-Regex, keine
ungebundene Substring-Suche — Ortsnamen wie „Scoresbysund" lösen keinen
False-Positive aus).
Eine **Trip-Briefing-Mail** (anderer Versandpfad, n Stundentabellen pro Etappe,
kein Übersichtstabellen-Vertrag) kann diesen Validator **strukturell nie**
bestehen → Dauer-Exit-1.

**Kompakt-Zweig (seit #3059):** trägt die Mail `X-GZ-Format: compact`, entfallen
die HTML-Prüfungen; geprüft wird (Fehler mit Präfix `COMPACT:`): genau ein Teil
`text/plain`, reines ASCII (7bit oder quoted-printable), unter 2048 Byte, keine
Stundentabelle (zwei oder mehr Zeilen mit `HH:MM` am Anfang); mit `--konfig` je
Ort der Konfiguration genau eine Ortszeile (beginnt mit dem ASCII-gefalteten
Namen) in der Folge von `location_ids`, ein Kürzungs-Hinweis `+N …` erlaubt das
Fehlen der letzten N Orte. Mit `--konfig` wird außerdem das Format gegen
`display_config.email_format` des Presets geprüft (fehlend = `full`, Ist ohne
Kopf = `full`): Abweichung → `SOLL: Format '<ist>' statt '<soll>'`, Exit 1 —
in beiden Richtungen. Kein neues CLI-Flag.

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

Prüft: Struktur, Location-Anzahl, Plausibilität, Format, Vollständigkeit der
Orts-Vergleich-Mail. Läuft in der Acceptance-Stage gegen die Staging-Mail:
Wegwerf-Nutzer mit Plus-Adresse `gregor-test+<tag>@henemm.com`, die Zustellung
landet im Postfach `gregor-test@henemm.com`; IMAP-Quelle ist dieses Stalwart-
Test-Postfach (`mail.henemm.com`). `fetch_latest_email()` priorisiert seit #972
`GZ_TEST_IMAP_USER`/`GZ_TEST_IMAP_PASS` vor `GZ_IMAP_*`/`GZ_SMTP_*`, sodass
verlässlich gegen das Test-Postfach geprüft wird. Credentials aus den Settings —
niemals im Klartext. Kein Gmail.

**Übergangs-Union der Übersichts-Beschriftungen (#1420, Prüfdatum 2026-10-27):**
`_OVERVIEW_METRIC_CHECKS` kennt 46 statt 24 Beschriftungen — die heutigen
deutschen **und** die englischen Kurzformen, auf die #1401 A2b umstellt (samt
den auswahlabhängigen Formen „Temp"/„Temp max"/„Temp min", analog „Feels").
Strikt additiv, damit A2b die Mail umstellen kann, ohne dass die 24
Plausibilitätsprüfungen still in den `continue`-Pfad zurückfallen. Dasselbe
Muster wie `_HOUR_COLUMNS_V2` (#1404). Das Prüfdatum ist ein reiner
Erinnerungsmarker **ohne** Verhaltenszweig — eine Selbstverengung am Stichtag
würde die dann korrekte Mail ablehnen. Rückbau nach A2b.

**Nur bei Exit 0** darfst du „E2E Test bestanden" sagen. Einfache String-Checks
beweisen NICHTS — sie prüfen nicht, ob Daten SINNVOLL sind.

**Bekannte Grenze:** Der Validator prüft nur den statischen
v2-Struktur-Vertrag (Warn-Zeile + ≥1 numerische Zeile genügt). Ob die im Preset
tatsächlich aktivierten Metriken korrekt angezeigt werden, prüft er nur mit
`--konfig` (Abschnitt „Soll aus der gespeicherten Konfiguration", #3047).

**Bekannte Grenze (Folge-Issue #1150):** Seit Issue #1107 kann die komplette
Stundenverlauf-Sektion je Compare-Preset abgeschaltet werden
(`ComparePreset.hourly_enabled=false`, Marker-Header
`X-GZ-Compare-Hourly-Enabled: false`). Der Validator liest diesen Header
noch nicht und fordert weiterhin für jeden gelisteten Ort eine Stundentabelle
— eine bewusst so konfigurierte Mail wird daher fälschlich als strukturell
unvollständig gemeldet (Dauer-Exit-1 für diesen Fall). Grund: Validator-Dateien
(`.claude/hooks/*`) dürfen nicht im selben Workflow geändert werden, dessen
Ergebnis sie prüfen sollen (`feedback_validator_changes_own_workflow`). Die
Erweiterung (`validate_structure(hourly_enabled=...)`, Header-Auswertung in
`run_validation()`) ist als eigener Workflow unter Issue #1150 ausgelagert.

## 2. `briefing_mail_validator.py` — Trip-Briefing-Mail (seit #733)

**Geltungsbereich:** kanonisches Acceptance-Gate für **Trip-Briefing-Mails**
(beide Formate: `full` HTML / `compact` Nur-Text seit #722). Dispatcht
deterministisch über zwei Marker-Header, die `build_mime_message()` setzt:
`X-GZ-Mail-Type: trip-briefing|compare` und `X-GZ-Format: full|compact`; die Sprache der Erwartungen (Marker „Nacht am Ziel"/„Night at destination", Ausblick-Spalte „Tag"/„Day", Pille „kein Regen"/„no rain") folgt `X-GZ-Lang` (Abschnitt 0).

```bash
uv run python3 .claude/hooks/briefing_mail_validator.py
```

Prüft format-spezifisch auf **Plausibilität** (nicht bloß String-Presence) gegen
die echt zugestellte Mail aus dem Stalwart-Test-Postfach. `fetch_latest_message()`
priorisiert seit #972 `GZ_TEST_IMAP_USER`/`GZ_TEST_IMAP_PASS` vor
`GZ_IMAP_*`/`GZ_SMTP_*` (Pattern wie `radar_alert_mail_validator.py`), damit der
Validator verlässlich gegen `gregor-test@henemm.com` prüft. Kein Mock, kein Gmail.

- **full:** `multipart/alternative`, je ein `text/html`- und `text/plain`-Part,
  ≥1 sequenzielle Stundentabelle (≥2 `HH:00`-Zeilen), Werte selbst-konsistent
  (`temp_lo <= temp_hi`, Wind/Regen ≥ 0, nicht alle None/0), Stunden im
  Tagesfenster 06–22 — dieser Check läuft seit #974 nur noch auf dem HTML-Teil
  **vor** dem ersten „🌙 Nacht am Ziel"-Marker; die Nacht-Sektion (kann in beiden
  morning und evening Full-Mails (#1313) erscheinen, gesteuert durch `show_night_block`,
  Ankunft→06:00 Folgetag, legitime Stunden wie 00/02/04) ist davon
  ausgenommen und löst keinen False-Positive mehr aus. Temperatur-Range- und alle
  übrigen Checks laufen weiter auf dem vollen HTML. Subject nicht leer.
- **compact:** single `text/plain`, 7bit (oder QP bei reinem ASCII), `isascii`,
  < 2 KB, HART: Kopf + `== Metriken-Ueberblick ==` + Footer; Ausblick ist
  **optional** (der Renderer lässt ihn legitim weg, wenn keine Stabilität/Trend-
  Daten vorliegen); **keine** Stundentabelle.

**Dispatch-Verhalten:** `compare`-getaggte Mail → sauberes No-Op (Exit 0, falscher
Validator). Fehlender Marker-Header → Exit 1 (Mail nicht vom getaggten Renderer).
Plausibilitäts-Schwellen sind bewusst weit kalibriert (gegen False-Positives, die
Deploys fälschlich blockieren). **Nur bei Exit 0** darfst du „E2E Test bestanden"
sagen.

Der ergänzende `IMAP-MIME-Verhaltenstest` (seit #722, #721, #636) bleibt als
Unit-/Integrationsbeweis gültig; der Validator kodifiziert genau dieses Muster als
Gate. Der `email_spec_validator.py` ist für Trip-Briefing-Mails **nicht** zuständig.

## 3. `renderer_mail_gate.py` — Commit-Gate für Mail-Renderer (seit #811)

> **„Un-überspringbar" ist eine überprüfbare Behauptung — und sie stimmte bis
> 2026-08-04 nicht** (#1431). Das Gate entschied per Teilstring `"git commit"`, ob es
> überhaupt prüft; jede Form mit etwas zwischen `git` und Unterbefehl
> (`git -C /pfad commit`, `git -c k=v commit`, `git --no-pager commit`) umging es
> **still**. Real passiert: ein Commit mit zwei gestagten Mail-Renderer-Dateien lief,
> ohne dass das Gate startete — die Aufrufform war nicht absichtlich gewählt.
> Seit #1431 entscheidet eine tokenbasierte Erkennung (`hook_utils.is_git_subcommand`,
> agent-os-openspec ≥ 3.10.0) mit umgedrehter Frage: nicht „erkenne ich einen Aufruf?",
> sondern „bin ich sicher, dass hier keiner drinsteckt?". Wer sich auf diese Zusicherung
> stützt, prüft sie am laufenden Stand nach, statt sie zu glauben.

Commit-Hook (PreToolUse→Bash-Kette nach `pre_commit_gate.py`). Macht die
Validator-„PFLICHT" technisch **un-überspringbar**: Sobald ein `git commit` eine
Mail-Inhalts-Datei staged (`src/output/renderers/email/*.py`,
`src/output/renderers/{trip_report,sms_trip,compact_summary}.py`, `src/output/renderers/alert/*.py`,
`src/output/channels/email.py`), **blockiert der Commit (Exit 2)**, bis im aktiven Workflow
**beide** Nachweise vorliegen:

1. der **Modus-Matrix-Vertragstest** (`tests/tdd/test_issue_811_mode_matrix.py`)
   lief grün — er rendert die echte Mail über
   `{full,compact}×{Einfach,Roh}×{briefing,alert}` und erzwingt, dass der Roh-Modus
   Zahlen statt Ampelpunkte zeigt (deckt **Briefing- UND Alert/„Update"-Mail** ab,
   da gemeinsamer `render_email`-Pfad);
2. ein erfolgreicher **`briefing_mail_validator.py`**-Lauf
   (`*_briefing_validation.yaml` mit `passed: true`).

**Anti-Stale:** Der Matrix-Nachweis bindet an einen sha256 der Mail-Dateien, der
Validator-Nachweis an seine `validated_at`-Frische — jede neue Renderer-Änderung
invalidiert beide → Test + Validator müssen erneut laufen. **Kein globaler/ENV-
Bypass.** Verhindert stille Mail-Format-Defekte vor dem Merge (Issue #810-Klasse).

**Abhilfe bei Blockade** (kein Override): Vertragstest laufen lassen
(`uv run pytest tests/tdd/test_issue_811_mode_matrix.py` — der Lauf schreibt den
Matrix-Nachweis automatisch) und den `briefing_mail_validator.py` gegen die
zugestellte Staging-Mail grün bekommen.

## 4. `official_alert_mail_validator.py` — amtliche Standalone-Warn-Mail (seit #1197)

**Geltungsbereich:** kanonischer Acceptance-Validator für die eigenständige
amtliche Warn-Mail (Trip- **und** Compare-Pfad), gerendert von
`src/output/renderers/alert/official_alerts.py::render_official_alert_html`
(bzw. `render_warn_block(variant="standalone", ...)`). Dispatcht über den
Marker-Header `X-GZ-Mail-Type: official-alert` — falscher Mailtyp ist ein
sauberes No-Op (Exit 0). Bis #1197 deckte **kein** Validator diesen Mailtyp
ab; `radar_alert_mail_validator.py` behandelt `official-alert`-Mails
ausdrücklich als No-Op (er ist für die **Nowcast**-Mail zuständig,
`X-GZ-Mail-Type: radar-alert`).

```bash
uv run python3 .claude/hooks/official_alert_mail_validator.py
```

Struktur-Prüfung über `html.parser.HTMLParser` (stdlib): gesammelt werden nur
tatsächlich als `class="..."`-Attributwert auftauchende CSS-Klassen-Tokens
(kein Substring-Fund auf den Rohtext). Text-Plausibilität separat auf dem
extrahierten Klartext/HTML-Fallback.

| Regel | Prüft | Konsequenz |
|---|---|---|
| S-0 | HTML-Body mit `html.parser` parsbar | kaputtes HTML ist ein echter Befund (fail-closed) |
| S-1 | Pflichtklassen `{"verdict", "warn", "body-foot"}` im HTML-Body | fehlt eine, Fehlermeldung nennt die fehlenden Klassen |
| **S-1b** (neu, Issue #1744 A2, AC-14) | Quellenangabe als **eine von zwei** gültigen Formen: CSS-Klasse `src` (Bestand, `#1233` Slice B) **ODER** eine Datenzeile `Quelle: …` im Text (Regex `^\s*Quelle:\s*\S`, MULTILINE) | **additiv** zu S-1 ergänzt, nicht ersetzt — `src` bleibt gültig; A2 löst die eigene `.src`-Box zur Datenzeile im gemeinsamen Datenzeilen-Block auf, ohne dass der Wächter eine sachlich korrekte Mail ablehnt. Eine Mail **ohne** jede Quellenangabe fällt weiterhin durch (S-1b und zusätzlich P-4) |
| S-2 | Warnstufen-Träger: Leiter (`stufe-line`, uniforme Stufe) **oder** Eskalations-Meter (`stacked`+`meter`, gemischte Stufen) | fehlt beides, Fehlermeldung nennt die gefundenen Klassen |
| P-1 | Verdict-Zeile `„{N} amtliche Warnung(en)"` mit `N>=1` | |
| P-2 | Warnstufen-Wort (`GELB`/`ORANGE`/`ROT`) im Text | |
| P-3 (Issue #1240) | jede vorhandene `„Gültig:"`-Zeile trägt einen echten Zeitraum (Wochentag + Datum) | Warnungen ohne bekannten Zeitraum tragen zu Recht **gar keine** `„Gültig:"`-Zeile (Präfektur-Zugangssperren, Waldbrand-Tagesstufen, PO-Entscheidung #1238) — Anwesenheit allein ist kein Kriterium, nur der Inhalt, falls die Zeile da ist |
| P-4 | Literale `„Quelle:"` **und** `„abgerufen bei"` im Text | unabhängig von S-1b — beide Prüfungen bleiben in Kraft |
| P-5 | Literal `„Stand: heute"` im Text | |

Exit codes wie bei `radar_alert_mail_validator.py`: `0` = bestanden/No-Op,
`1` = Spec-Verletzung mit Fehlerliste, `2` = technischer Fehler (IMAP nicht
erreichbar). IMAP-Fetch gegen dasselbe Test-Postfach, `GZ_TEST_IMAP_*` vor
`GZ_IMAP_*` priorisiert (Pattern wie `radar_alert_mail_validator.py`).

**Nur bei Exit 0** darfst du „E2E bestanden" für diesen Mailtyp sagen.

## 5. `radar_alert_mail_validator.py` — Radar-/Nowcast-Alarm-Mail (seit #830)

Kurzeintrag (Audit 2026-10-21 — bis dahin nur als Vorbild in §2/§4 erwähnt). Kanonischer
Acceptance-Validator für die Radar-Alarm-Mail: holt die zuletzt zugestellte Mail aus dem
Test-Postfach, dispatcht über `X-GZ-Mail-Type: radar-alert` (anderer Mailtyp ⇒ No-Op, Exit 0)
und prüft Plausibilität (u. a. Beginn-Uhrzeit `HH:MM`, bekannte Intensitätsstufe aus
`radar_service.py`). Exit `0` = bestanden/No-Op, `1` = Spec-Verletzung, `2` = technischer Fehler.
Detailregeln stehen im Kopf von `.claude/hooks/radar_alert_mail_validator.py`.

```bash
uv run python3 .claude/hooks/radar_alert_mail_validator.py
```

**Nur bei Exit 0** darfst du „E2E bestanden" für diesen Mailtyp sagen.

## Strukturelle Render-Checks im briefing_mail_validator (Issue #833)

Der Trip-Briefing-Validator prüft die `full`-Mail nicht mehr nur als MIME-String,
sondern **rendert** den HTML-Part headless (Playwright/Chromium) bei **≤390px** und
**≥1000px** und bewertet das gerenderte Artefakt. Fehlt Playwright/der Browser, wird
**Exit 2** (technischer Fehler) signalisiert — **nie** Exit 1 (kein False-Negative).

Erzwungene Invarianten (alle hart, Exit 1):

| Check | Funktion | Was rot wird |
|---|---|---|
| **Viewport-Render** (AC-1) | `_check_rendered` | Bei einer Breite ist keine Wetter-Tabelle sichtbar **oder** der für die Breite falsche Block ist sichtbar (≤390px → `.desktop-only`; ≥1000px → `.mobile-compact`) — Dual-Render/#794-Klasse. Konditional: flache Tabellen ohne responsive Wrapper bleiben gültig. |
| **Ebenen-Konsistenz** (AC-3) | `_check_layer_consistency` | Pill-Spitzenwert ≠ Tabellen-Spalten-Max (> ±3 km/h), Mapping über th-Spaltenindex (#807). |
| **Metrik-Plausibilität** (AC-4) | `_check_metric_plausibility` | „Sonne X.Xh" ≠ Σ Sonnenstunden (±5 min, nur Roh-Tabelle; Pille seit #1998 in Stunden statt Minuten); „kein Regen" bei Regensumme ≥ 0.1 mm (#808). |
| **Lokalisierung** (AC-5) | `_check_localization` | Englische Spaltenköpfe (Gust/Rain/Sun/Feels/Cloud/Thunder/Visib/Humid) in der deutschen Mail; Homograph „Wind" ausgenommen (#94). |

Der Mobile-Vertrag (#831) wird zusätzlich im Matrix-Test über `_data_cells_mobile()`
in **beiden** Auflösungen geprüft. Selbsttest: `tests/tdd/test_issue_833_gate.py`
füttert bewusst defekte Mails und beweist, dass das Gate sie rot meldet (kein Mock,
echte MIME-Artefakte).
