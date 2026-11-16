# Mail-Validatoren & Renderer-Gate — Detail-Referenz

Kompakte Übersicht + Dispatch-Tabelle stehen in `CLAUDE.md` → Abschnitt
„Mail-Validatoren & Renderer-Gate". Dieses Dokument hält die vollständigen
Plausibilitäts-Schwellen, das Dispatch-Verhalten, die Anti-Stale-Mechanik und
die Historie.

Es gibt **drei verschiedene Mail-Pfade** mit **drei verschiedenen Gates**. Den
falschen Validator auf einen Pfad anzuwenden ist ein Fehler — er kann strukturell
nie bestehen (Dauer-Exit-1) und führt zu falschem „Feature kaputt" oder
Gate-Erosion.

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

`briefing_mail_validator.py` und `email_spec_validator.py` nehmen optional
`--konfig PFAD`: das **rohe gespeicherte JSON des Test-Nutzers**, wie die Go-API
es liefert (Trip: das ganze Trip-Objekt mit `display_config`/`report_config`;
Orte: das Preset, für die Ortsfolge mit `--orte PFAD` oder als Hülle
`{"preset": {...}, "orte": {"<id>": "<Name>"}}`). `.claude/hooks/_soll_aus_konfiguration.py` leitet daraus
das Soll ab — nur aus der Datei und dem statischen Register (`col_label`,
`label`, Compare-Katalogtabelle), **nie** über ein `resolve_*` des Produkts
(Spiegel-Test-Verbot). `pruefe_soll(msg, soll, lang)` vergleicht dann im
**HTML- und im Klartext-Teil**:

- **Trip:** Spaltenfolge jeder Etappen-Stundentabelle und der Nachttabelle
  (E-Mail-Liste der Kaskade, nach `bucket`/`order`), Kopf des 3-Tages-Ausblicks;
  im Kompaktformat die Folge der Ausblick-Tokens; `show_night_block`,
  `email_format`, Ausblick an/aus. Dazu die **Darstellung Roh/Einfach je
  Spalte** (Stunden-, Nacht-, Ausblick-Tabelle, HTML und Klartext): Roh = Zahl,
  Einfach = Symbol/Wort oder Ampelpunkt. Gewollte Ausnahmen (Spec §2 Punkt 3):
  Wind/Böen/Regen/Regen-W. zeigen Einfach im HTML als Ampelpunkt, im Klartext
  als Zahl (#814); Gewitter zeigt roh schon das Stufenwort (im Klartext und im
  Ausblick ungeprüft); Visibility/Temperatur haben im Ausblick keine
  Einfach-Form (immer Zahl); die verschmolzene Windrichtung hat keine eigene
  Spalte (#435). Die Meldung nennt Tabelle und Spalte („Darstellung
  Etappen-Stundentabelle (Klartext) 1: Spalte 'Cloud' soll Symbol/Wort
  (Einfach) zeigen, zeigt Zahl (Roh)").
- **Orte:** Zeilenfolge der Vergleichstabelle (`channel_layouts.email` vor
  `channel_active_metrics.email`, geschnitten mit `active_metrics`), Ortsfolge (`location_ids`), Spalten des
  Stundenverlaufs je Ort (`hourly_metrics`, `hourly_enabled`), Ausblick-Kopf
  (`outlook_metrics`, `outlook_enabled`).

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
  (`order_locations_by_ids`). Ein gesetztes `--min-locations` hat Vorrang.
- **Verschmolzene Windrichtung (F004):** Windrichtung Einfach neben Wind (keine
  eigene WDir-Spalte) → jede Wind-Zelle der Etappen- und Nachttabelle trägt eine
  Kompassrichtung, im HTML auch neben dem Ampelpunkt, im Klartext („20 W");
  die Richtung je Stunde ist im HTML dieselbe wie im Klartext.
- **Metriken-Überblick nur mit Kachel (F008b):** der Überblick (Voll: HTML und
  Klartext, Kompakt) steht genau dann in der Mail, wenn eine Größe der
  E-Mail-Liste dieses Berichts eine Kachel trägt (weiße Liste `_PILL_CATALOG_ORDER`);
  nur z. B. `temperature_night` gewählt → kein Überblick. Kacheln, die mangels
  Werten entfallen, sind aus der Konfiguration nicht ableitbar.

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
