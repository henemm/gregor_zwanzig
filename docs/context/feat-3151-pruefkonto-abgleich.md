# Context: #3151 Elementlisten-Abgleich mit geseedetem Prüfkonto (247 `#2967`-Einträge auflösen)

Workflow `feat-3151-pruefkonto-abgleich`, Epic #2913, Phase 1 (nur Recherche, Stand 2026-11-20).

## Request Summary

Der Staging-Seed für das Prüfkonto (`scripts/staging_pruefkonto_mockupdaten.py`, aus #2967) wird um die Kanalauswahl des Mockups erweitert (Befund S1: Trip und Vergleich haben live nur E-Mail als Briefing- und Alarmkanal). Danach läuft der Abgleich DE+EN neu, und die 247 Besitzer-Einträge mit `verweis: "#2967"` in `elementliste_besitzer.json` werden aufgelöst (Eintrag entfernt, weil das Schema keinen Status „aufgelöst“ kennt) oder auf neue Kind-Issues von #2913 umgehängt. Der Zählwächter `tests/test_2913_c2_besitzerliste.py` zieht nach. Neuer Befund 20.11.: im Prüfkonto fehlen GR221-Trip, Münsterland-Vergleich und Orte (nur Vorlage „Mallorca Frühling“ ist da), also Seed zuerst erneut laufen lassen (idempotent). Echte Code-Abweichungen (B1–B9) bekommen nach Dublettenprüfung je ein Kind-Issue von #2913. #3145 ist bereits geschlossen.

Klassifizierung aus dem Issue-Kommentar vom 19.11. (247 Einträge, Rohdaten nur gitignored im Worktree `crystalline-zooming-barto` unter `docs/artifacts/feat-2967-pruefkonto-mockupdaten/`, `klassifizierung-2967.json`, evtl. nicht mehr vorhanden):

| Klasse | Anzahl | Bedeutung |
|---|---|---|
| A aufgelöst | 119 | im Abgleich DE+EN gefunden (2 nur DE, EN-Lücke „Mallorca Frühling“ war #2968, jetzt abgeräumt) |
| S1 Seed-Lücke | 53 | Kanalauswahl fehlt im Seed, Folgefehler Dringlichkeits-Reihenfolge und „–“ |
| B echte Abweichung | 62 | B1 Kanalzeile (23), B1b Sperrzelle (4), B2 Grünbereich (14), B3 Temperatur-Skala, B4 Gewitter-Stufen, B5 Vorbote (2 + Abschnitt), B6 Vorlagen-Auswahl Orte (2), B7 Zurücksetzen (2), B8 Anzeige-Metriken Trip (10), B9 „:00“ (1); Abschnitts-Einträge `metriken` (2) aufteilen |
| Umhängen auf Bestehende | 15 | 13 nur-EN-Zusatztexte (waren #2968, inzwischen erledigt, neu prüfen), 2 „gesperrt: {grund}“ → #3122 |

Achtung: Die Klassifizierung stammt vom Stand vor #2968/#3192 (beide inzwischen gemergt); die Zahlen können sich im Neulauf verschieben. Der Neulauf des Abgleichs ist die verbindliche Quelle.

## Related Files

| Datei:Zeile | Inhalt |
|---|---|
| `scripts/staging_pruefkonto_mockupdaten.py:207-214` | `soll_trip()`: id/name/region/stages, KEINE `report_config`, keine Alarmfelder |
| `scripts/staging_pruefkonto_mockupdaten.py:217-222` | `soll_wetter()`: `metrics` + `ampel` (Vorlage alpen-trekking), geschrieben per `PUT /api/trips/{id}/weather-config` |
| `scripts/staging_pruefkonto_mockupdaten.py:225-231` | `soll_empfaenger()`: Konto-Adresse + `pruefkonto-2967@gregor-test.invalid` (2 Empfänger) |
| `scripts/staging_pruefkonto_mockupdaten.py:242-250` | `soll_vergleich()`: name, location_ids, schedule daily, morning 07:00:00, `empfaenger`, `display_config`; KEINE `send_telegram`/`alert_channels`/`alert_channel_thresholds` |
| `scripts/staging_pruefkonto_mockupdaten.py:286-293` | `sichere_datensatz`: GET, 404 → POST, sonst `_enthaelt`-Teilvergleich, bei Abweichung `PUT {**ist, **soll}` (oberste Ebene ersetzt, Go mergt `report_config` aber serverseitig per `mergeConfigMap`) |
| `scripts/staging_pruefkonto_mockupdaten.py:314-327` | `sichere_vergleich`: Treffer per Name, RMW mit Merge nur von `display_config`; sonst `{**ist, **soll}` |
| `scripts/staging_pruefkonto_mockupdaten.py:331-367` | Kanäle: Tarif premium (`/api/auth/staging-seed`), SMS (staging-code), Telegram (`/api/internal/telegram-connect` am Loopback 8091), Premium-SMS (Trockenlauf, dann scharf) |
| `scripts/staging_pruefkonto_mockupdaten.py:370-386` | `fuehre_seed`: Reihenfolge anmelden, E-Mail-bestätigt-Prüfung, Empfänger, Tarif, Trip, Wetter+Vorlage, Orte, Vergleich, Kanäle |
| `scripts/staging_pruefkonto_mockupdaten.py:63-66` | fiktive Kanalwerte: `SMS_NUMMER`, `TELEGRAM_CHAT_ID`, `INREACH_FROM`, `ZWEIT_EMPFAENGER` |
| `docs/runbooks/staging_pruefkonto_seed.md` | Runbook: Aufruf, Exit-Codes, Idempotenz, Abgleich-Aufruf mit `GZ_AUTH_*` = Prüfkonto |
| `docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md:107-150,178-190` | ACs und Known Limitations (Reihenfolge „Nicht im Briefing“, Vorlage allgemein, alpen-trekking weicht ab) |
| `tests/tdd/test_staging_pruefkonto_mockupdaten.py:107` | Fake-Server `_Fake` (Zustand je Nutzer, Aufrufprotokoll); ~60 Tests, u. a. :377 Trip, :436 Idempotenz, :455 kein Schreibzugriff im 2. Lauf, :467 RMW, :580 vier Kanäle, :750/:888 Vergleich-RMW |
| `internal/model/trip.go:154-165` | Trip `AlertChannels`, `AlertChannelThresholds` (Pointer-Structs, nil = Altverhalten) |
| `internal/model/trip.go:187-190` | abgeleitete Flachfelder `SendEmail/Sms/Telegram/PremiumSms` (nicht autoritativ, aus `report_config` bei jedem Load) |
| `internal/model/trip.go:222-249` | `AlertChannelsConfig` {email, telegram, sms, premium_sms: *bool}, `AlertChannelThresholdsConfig` (*string "LOW"/"MODERATE"/"HIGH") |
| `internal/store/trip.go:108-121` | Ableitung `report_config.send_email/send_sms/send_telegram/send_premium_sms` → Flachfelder |
| `internal/handler/trip.go:289-335` | `tripUpdateRequest`: `report_config` (map), `alert_channels`, `alert_channel_thresholds` |
| `internal/handler/trip.go:437-453` | `report_config` Feld-Level-Merge (`mergeConfigMap`), Viertelstunden-Prüfung |
| `internal/handler/trip.go:489-535` | Feld-Level-Merge in `alert_channels` und `alert_channel_thresholds` (fehlender Kanal bleibt erhalten); KEINE Wertprüfung der Schwellen im Go-Handler gefunden (kein `validate…Threshold`) |
| `internal/model/compare_preset.go:92-119` | Vergleich: `send_email/send_telegram/send_sms/send_premium_sms` (top-level), `alert_channels`, `alert_channel_thresholds` |
| `internal/store/compare_preset.go:55-71` | `materializeAlertChannels`: fehlt `alert_channels`, wird es aus den Flachfeldern abgeleitet (E-Mail immer an) |
| `src/services/alert_channels.py:103-143` | Python: `_briefing_channels` (Trip aus `report_config`), `_compare_channel_inputs` (Vergleich aus Flachfeldern, `alert_channels` als Override) |
| `src/services/alert_channels.py:22-80` | Tarif-Gates: `sms` nur bei `sms_allowed`, `premium_sms` nur bei `premium_sms_allowed` (Seed setzt Tarif premium) |
| `src/services/alert_urgency.py:6,20` | Schwellen "LOW"/"MODERATE"/"HIGH" |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:197-265` | Lesesicht: `standAusTrip` (`report_config.send_*`, `alert_channels`, `alert_channel_thresholds`), `standAusPreset`; fehlender Schwellenwert = LOW |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts:1-40` | wie die UI speichert: Trip `{report_config: {send_*}}`, Vergleich top-level; Alarme immer top-level |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:373-374` | Mockup-Soll `st[ctx].sw.ch`: E-Mail `{b:true,a:true,s:'gering'}`, Telegram `{b:true,a:true,s:'gering'}`, SMS `{b:false,a:true,s:'mittel'}`, Premium-SMS `{b:false,a:true,s:'hoch'}` (b = Briefing, a = Alarm, s = Dringlichkeit) |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:362-371` | `konto()`: Kanalzeilen-Texte (E-Mail „bestätigt · henning@… · +1 Empfänger“, Telegram „verbunden · @henning“, SMS „+49 171 …“, Premium „inReach · Rückadresse gelernt 28.10. …“) |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts:5-19,387-391` | Abgleich: Umgebung `ELEMENTLISTE_SCOPE/_STRICT/_ABNAHME/_SPRACHE/_TRIP_ID/_ORTE_ID/_BERICHT_DIR`, Login `GZ_AUTH_USER/PASS` |
| `frontend/package.json:14` | `npm run elementliste:abgleich` → `scripts/elementliste_abgleich.ts` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | Besitzerliste, Schlüssel `zweck`, `besitzer` (871 Einträge), `ausnahmen`; Eintrag `{art, id|text|muster, ctx?, reiter?, abschnitt?, grund, verweis}` |
| `tests/test_2913_c2_besitzerliste.py:123-136` | Zählwächter `soll = {"#2967": 247, … "#3194": 100, "#3151": 4}`; Kommentar Z.109-122 dokumentiert die Historie |
| `tests/test_3007_besitzerliste.py` | zählt `#2967` nicht (nur Etappen/Orte-Listen) |

## Existing Patterns

**Seed-Struktur.** Reine Soll-Funktionen (`soll_trip/soll_wetter/soll_vergleich/soll_empfaenger`) plus Klasse `PruefkontoSeed` mit injizierbarem Transport (Tests über Fake-Server). Je Datensatz GET vor POST; vorhanden → `_enthaelt(ist, soll)` (Teilvergleich, vom Server ergänzte Felder zählen nicht) → nur bei Abweichung PUT. Zweiter Lauf schreibt nichts außer `staging-seed` (Tarif/Zähler). Kanäle: Zustandsprüfung am Profil, nur bei Abweichung verbinden.

**Kanalauswahl: Datenmodell (zu schreiben im Seed).**
- Trip: `PUT /api/trips/{id}` mit `{"report_config": {"send_email": true, "send_telegram": true, "send_sms": false, "send_premium_sms": false}, "alert_channels": {"email": true, "telegram": true, "sms": true, "premium_sms": true}, "alert_channel_thresholds": {"email": "LOW", "telegram": "LOW", "sms": "MODERATE", "premium_sms": "HIGH"}}`. Go mergt `report_config` je Schlüssel, `alert_channels` und `alert_channel_thresholds` je Kanal (RMW-sicher). Flachfelder am Trip leitet der Store ab; nicht selbst schreiben.
- Vergleich: top-level `send_email: true, send_telegram: true, send_sms: false, send_premium_sms: false`, `alert_channels: {…alle true…}`, `alert_channel_thresholds: {…}`. Hinweis: `alert_channels` fehlt → Store materialisiert es aus den Flachfeldern (Alarm = Briefing + E-Mail), also MUSS der Seed `alert_channels` explizit setzen, sonst stehen „Alarme alle 4“ nicht.
- Dringlichkeit Mockup „gering/mittel/hoch“ ↔ Datenwert „LOW/MODERATE/HIGH“ (`zustellungModell.ts:197-200`, `alert_urgency.py:20`). Fehlt der Wert, liest die UI LOW.
- Briefing nur E-Mail+Telegram: SMS und Premium-SMS im Briefing aus, aber im Alarm an. Telegram im Briefing verlangt nur einen verbundenen Chat (Seed verbindet ihn schon).

**Seed-Reihenfolge.** `fuehre_seed` verbindet Kanäle erst NACH den Datensätzen (Z.382-385); die Kanalauswahl der Datensätze (Briefing/Alarm-Flags) ist davon unabhängig, kann direkt im Soll-Trip/Soll-Vergleich stehen. Für die Trip-Seite `soll_trip()` erweitern (oder eigene `sichere_kanalauswahl`, weil `/api/trips/{id}` PUT mit `{**ist, **soll}` das ganze `report_config` im Body ersetzt, Go mergt aber serverseitig; besser nur die Soll-Schlüssel senden, damit nichts Fremdes überschrieben wird).

**Besitzerliste.** Eintragsarten `element` (103 bei #2967), `zusaetzlich` (142), `abschnitt` (2). Verteilung der 247: ctx=None ohne Reiter 103 (Zustellung/Element-IDs), `orte/wetter` 58, `*/wetter` 45 + `trip/wetter` 18, `*/zustellung` 21, Abschnitt `wetter/metriken` je ctx 1. Gründe: „Mockup-Beispieldaten: Metrik-Zeile bzw. Zähler …“ (76), „Datenabhängig: das Staging-Prüfkonto hat nur E-Mail verbunden …“ (64), „Metrik-Zeile im Reiter Wetter … Prüfkonto zeigt“ (45), „Mockup-Beispieldaten (Kontodaten …)“ (35), „Kontodaten des Prüf-Kontos …“ (21), „eigene Vorlage ‚Mallorca Frühling‘ … fehlt“ (4), „Prüfkonto weicht vom Mockup-Beispiel (GR221 / Alpen-Trekking) ab“ (2). Aktuelle Zählung je Verweis (Python, gerade gemessen): `#2795` 318, **`#2967` 247**, `#3194` 100, `#2913` 82, `#3022` 62, `#2796` 38, `#3122` 10, `#2797` 8, `#3151` 4, `#2913-e` 2 (Summe 871). Auflösen heißt Eintrag entfernen; Nachweis „nicht still gelöscht“ per Vorher-Datei + Klassifizierung (Artefakt unter `docs/artifacts/…`, gitignored, daher Zusammenfassung ins Issue-Kommentar).

**Zählwächter.** `tests/test_2913_c2_besitzerliste.py:123-136`, Dict `soll`: `#2967: 247 → 0`; Einträge, die auf neue Kind-Issues umgehängt werden, als neue Schlüssel ergänzen (+ Kommentar mit Historie wie bisher); `#3151: 4` (EN-Lücken „eigene · aus GR221 gespeichert“) ist dem Issue selbst zugeordnet und bleibt oder wird gelöst. Der Test vergleicht ein Dict nur über die Schlüssel von `soll`, neue Verweise müssen also dort stehen, sonst unbewacht. `test_3007_besitzerliste.py` unberührt.

**Abgleich starten (Staging-Host).**
```
IDS=$(uv run python scripts/staging_pruefkonto_mockupdaten.py) && export $IDS
set -a; . /home/hem/gregor_zwanzig_staging/.env; set +a
cd frontend && GZ_AUTH_USER="$GZ_PRUEFKONTO_USER" GZ_AUTH_PASS="$GZ_PRUEFKONTO_PASS" \
  npm run elementliste:abgleich -- [--sprache en] [--scope wetter]
```
Laufzeit je Lauf (DE, EN) rund 8 Minuten (Issue-Kommentar 19.11.); `--scope wetter` (aus #3192) verkürzt. Prüfkonto `u-89f9fe2f` (`gzp-pruefkonto-mockup`), Zugang in Staging-`.env` (`GZ_PRUEFKONTO_USER/PASS/MAIL`). Ergebnis des letzten Laufs (19.11.): DE gefunden 1303, abweichend 1139, nicht prüfbar 198, zusätzlich 301; EN 921/411/1308/336. Der Abgleich legt kurz „E2E-GZ #2966“ an und löscht ihn, setzt Sprache und stellt zurück (nicht wörtlich „rein lesend“, Endzustand unverändert; Schreib-Tripwire 0). Hinweis: #3192 hat danach den Wetter-Teil auf Mockup-Datenlage umgestellt (156 `#3111` abgeräumt), Berichte liegen unter `frontend/test-results/elementliste-abgleich` (`ELEMENTLISTE_BERICHT_DIR`).

## Dependencies

- Staging-Host, Staging-`.env` (Core-Secret, `GZ_PRUEFKONTO_*`), Loopback `localhost:8091`; kein aktiver `GZ_SEVEN_API_KEY`.
- Go-API Staging: `PUT /api/trips/{id}`, `PUT /api/compare/presets/{id}`, `POST /api/auth/staging-seed`. Bestehend, keine Go-Änderung für die Kanalauswahl nötig (Felder und Merge existieren).
- Premium-Tarif des Prüfkontos (Seed setzt ihn vor den Datensätzen), sonst filtert Python SMS/Premium-SMS aus der Alarm-Auflösung.
- Abgleich-Werkzeug: `frontend/e2e/elementliste-abgleich.staging.spec.ts`, `scripts/elementliste_abgleich.ts`, `elementliste_abgleich_logik.ts` (liest `elementliste_besitzer.json`), `elementliste.json` (Generator aus dem Katalog, #3178 offen).
- Abhängige Epics/Issues: #2913 (Epic), #2967 (geschlossen), #3145 (geschlossen), #2968 (erledigt, EN-Zuordner), #3192 (geschlossen, Wetter-Dialoge), #3194 (offen, EN-Sollwerte Wetter-Dialog), #3122/#3037/#3009 (offen, „Was steht wo“, Abnahme).

## Existing Specs

- `docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md` (Seed; AC-8/AC-9 an #3151 abgetreten; Known Limitations Z.178-190)
- `docs/specs/modules/feat_2913_c2_seitenkopf.md` (Besitzerliste/Zählwächter-Regeln AC-12)
- `docs/specs/modules/feat_3007_etappen_orte_listen.md` (Besitzerliste AC-16/20)
- #3192-Spec (Wetter-Dialog-Abgleich) im Repo, Stand Merge 04625e2fd.
- Eine eigene Spec für #3151 existiert noch nicht (Phase 3 anlegen: Seed-Erweiterung Kanalauswahl, Abgleich, Besitzer-Umhängung, Zählwächter).

## Dubletten-Prüfung B1–B9 (`gh issue list --state all --search …`)

| Thema | Treffer (Nummer, Status, Titel) | Urteil |
|---|---|---|
| B1/B1b Kanalzeile Zustellung (Adresse gekürzt, Empfängerzahl, Sperrgrund) | #2797 OPEN Einstellungen neu S5: „Test schicken ▾“ (Kanal-Menü mit Ziel und Sperre); #3038 CLOSED Zustellung Reiter neu; #2795 OPEN S3b Inhalt je Kanal; #3122 OPEN Was steht wo | keine Dublette für die Kanal-ZEILE (Kürzung „henning@… · +1 Empfänger“, `KanalTabelle.svelte:87`); #2797 betrifft nur das Test-Menü. Neues Kind-Issue |
| B2 Grünbereich „· grün:“ | #3011/#3012 (laut Kommentar keine Dublette), #2794 CLOSED S3a Reiter Wetter (Ampel-Leiste, Grenzen), #3122 OPEN | keine offene Dublette. Neues Kind-Issue |
| B4 Gewitter-Stufen keins/mittel/hoch | #2955 CLOSED „Reiter Wetter: Metrik-Inhalte weichen vom Mockup ab (Vorbote-Kennzeichnung, Gewitter-Skala, Namen)“; #2010 CLOSED, #1474/#1419 CLOSED | #2955 ist geschlossen, trotzdem im Abgleich weiter Abweichung: prüfen, ob #2955 die Skala nur teilweise lieferte; sonst neues Kind-Issue mit Verweis auf #2955 |
| B5 Vorbote (Tiefe Wolken, Sonnenstunden „kein Alarm“) | #2799 OPEN S7 Ampel für weitere Metriken (Sonnenstunden, Bewölkung, tiefe Wolken, Taupunkt …); #2867 OPEN Metrik-Katalog: Vorboten-Markierung (wind_chill, dewpoint, cloud_total, pressure); #3086 OPEN Luftdruck-Zeile widerspricht sich; #2955 CLOSED | Dublette/Umhängen auf #2799 (Sonnenstunden, tiefe Wolken) und #2867 (Markierung) |
| B8 Anzeige-Metriken (Tages-Tiefst/Höchsttemperatur (Gehzeit), „nur Anzeige, keine Ampel“) | Suche liefert nur #3151 | keine Dublette. Verwandt: #3086 (Luftdruck nur Anzeige) und #2799 |
| B3/B7 alpen-trekking Known Limitation (Temperatur-Skala, Zurücksetzen auf Vorlage) | #2794 CLOSED, #2792 CLOSED, #3003 CLOSED; Known Limitation steht in Spec feat_2967 Z.183 | kein offenes Issue; Known Limitation dokumentiert. Entscheiden: als Ausnahme in `ausnahmen` mit Spec-Verweis oder Kind-Issue (Katalog-Vorlage alpen-trekking weicht vom Mockup ab: cloud_total aktiv, wind_direction fehlt) |
| B6 Vorlagen-Auswahl Orte „Mallorca Frühling“ | #2798 OPEN S6 Orte mit 1..n Orten; #2796 OPEN S4 Vorlage und Tempo trennen | wahrscheinlich Mockup-Abweichung (Route-Vorlage nur im Trip-Kontext, „Vorlagen je Art“); nicht Code |
| Umhängen „gesperrt: {grund}“ | #3122 OPEN | Ziel steht fest |
| EN-Zusatztexte | #2968 erledigt, #3194 OPEN (EN-Sollwerte Wetter-Dialog) | Neulauf zeigt, was bleibt; Rest → #3194 |
| S9/S5 Alarm-Dringlichkeit je Kanal | #2801 OPEN Einstellungen neu S9 Premium-SMS … Dringlichkeit SMS ab mittel, Premium hoch | fachliche Quelle des Mockup-Solls Dringlichkeit |

## Risks & Considerations

1. **Staging-only, Mandantentrennung.** Seed läuft nur gegen `https://staging.gregor20.henemm.com` und Loopback 8091, nur mit `GZ_PRUEFKONTO_*` (nie `default`, nie `GZ_AUTH_*`); `u-89f9fe2f` ist das einzige Zielkonto. Die Kanalauswahl-Erweiterung darf nur eigene Seed-Datensätze (feste Trip-ID `gz2967-gr221-mallorca`, Vergleich per Name „Münsterland“) berühren. Bestehender Test `test_ac10_zweiter_nutzer_bleibt_unveraendert` muss erhalten bleiben und für die neuen Felder gelten.
2. **Merge statt Replace.** `sichere_datensatz` ersetzt oberste Schlüssel (`{**ist, **soll}`). Für `report_config`, `alert_channels`, `alert_channel_thresholds` nur die Soll-Schlüssel senden (Go mergt je Feld); keine Neuschreibung ganzer Unterobjekte aus dem Seed. Beim Vergleich mergt der Seed nur `display_config` selbst; neue Sub-Objekte `alert_channels`/`alert_channel_thresholds` ebenfalls feldweise mergen, sonst überschreibt ein Seed-Lauf Handänderungen im Prüfkonto (CLAUDE.md Daten-Schema-Regel, BUG-DATALOSS-GR221).
3. **Idempotenz.** `_enthaelt` verlangt Listenlängengleichheit und Gleichwert; `alert_channel_thresholds`/Flags müssen genau in der Form zurückkommen, wie Go sie speichert (Normalisierung prüfen, vgl. `07:00:00`-Fall), sonst schreibt der zweite Lauf. Testfall analog `test_ac4_f001_zweiter_lauf_ohne_schreibzugriff_trotz_go_normalisierung`. Der Fake-Server in `tests/tdd/test_staging_pruefkonto_mockupdaten.py` bildet `alert_channels`-Materialisierung nicht nach; ggf. erweitern (Vergleich ohne `alert_channels` wird in Go aus Flags abgeleitet).
4. **Keine echten Versände.** Telegram-Chat-ID, SMS-Nummer, inReach-Absender sind fiktiv; Alarmkanäle „alle 4“ + Zeitplan daily 07:00 könnten den Scheduler auf Staging echte Briefings/Alarme senden lassen. Prüfen: ob der Staging-Scheduler an das Prüfkonto sendet (E-Mail über Resend an Konto-Adresse und `.invalid`; SMS nur Sandbox-Schlüssel `GZ_SEVEN_SANDBOX_KEY`; Telegram-Bot an fiktive Chat-ID liefert Fehler/ins Leere). Trip-Datum liegt in der Vergangenheit (Status „fertig“), also kein Briefing-Lauf zu erwarten; für den Vergleich (`schedule: daily`) gilt das nicht, im Plan prüfen.
5. **Zählwächter.** Zählung pro Verweis ist hart (`==`); jede Umhängung muss die Summe aller Verweise konsistent halten. Neue Verweis-Schlüssel (Kind-Issues von #2913) in `soll` ergänzen, #2967 auf 0. Aufgelöste Einträge werden entfernt, nicht umbenannt; Abschnitts-Einträge `wetter/metriken` aufteilen (deckt in DE 52 Elemente ohne eigenen Besitzer, B2–B5).
6. **Zahlen sind veraltet.** Klassifizierung vom 19.11. (vor #2968-Abräumung und #3192) kann nicht blind übernommen werden: nach dem Seed-Neulauf (inkl. Orten/Trip, die laut Befund 20.11. fehlen) den Abgleich DE+EN neu laufen lassen, Berichte neu klassifizieren (A/S1/B/Umhängen), dann erst die Liste ändern. Rohdaten im Worktree `crystalline-zooming-barto` sind nicht verlässlich verfügbar.
7. **Laufzeit/Sitzungsrisiko.** Zwei Abgleichläufe ~8 min je; Lauf schreibt vorübergehend „E2E-GZ #2966“ im Prüfkonto. Nicht parallel zu anderen Staging-Läufen mit demselben Konto starten. Spec #3192 misst Dialoge auf eigenen Prüf-Datensätzen, kollidiert nicht.
8. **Workflow-Hinweise.** Staging-Seed nach Phase 1 nicht in dieser Phase laufen lassen (Auftrag: kein Seed-Lauf). Ablauf des Seeds auf dem Staging-Host nach Merge/Deploy des Skripts (`uv run python scripts/staging_pruefkonto_mockupdaten.py`, zweimal; Exit 0, zweiter Lauf ohne Änderung). Neue Kind-Issues unter Epic #2913 als Sub-Issues anlegen (nie `@name` ohne Backticks in GitHub-Texten); Epic #2913 nicht schließen; PR-Text „Refs #N“, nicht „Closes“.
9. **Offene fachliche Frage (nur Tech-Lead, keine PO-Frage):** ob B3/B7 (alpen-trekking-Abweichung vom Mockup) als Ausnahme mit Spec-Verweis in `ausnahmen` oder als Kind-Issue geführt werden; Empfehlung nach Known-Limitation-Regel der Spec: Kind-Issue mit Dublettenprüfung, da „Jede bestätigte Abweichung bekommt … ein Kind-Issue von #2913“ (Spec Z.184).

## Analysis

### Type
Feature/Daten-Pflege (Staging-Seed erweitern + Besitzerliste bereinigen). Kein Go-/Frontend-Produktcode; Python-Seed, Tests, JSON, Runbook, Zählwächter.

### Affected Files (with changes)
| File | Change Type | Description |
|---|---|---|
| `scripts/staging_pruefkonto_mockupdaten.py` | MODIFY | reine Soll-Funktionen Kanalauswahl Trip/Vergleich (Mockup Z.373-374); nur Soll-Teilobjekte senden, feldweiser Merge in `sichere_datensatz` (Z.286-293) / `sichere_vergleich` (Z.314-327) |
| `tests/tdd/test_staging_pruefkonto_mockupdaten.py` | MODIFY | Fake-Server: `alert_channels`-Materialisierung + Go-Merge je Kanal; Tests Soll-Werte, Merge erhält Fremdfelder, 2. Lauf schreibfrei, Mandantentrennung neue Felder |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | 247 `#2967` nach Neuklassifizierung entfernen bzw. umhängen |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY | `soll` Z.123-136: `#2967: 0`, Ziel-Zähler, neue Schlüssel |
| `docs/runbooks/staging_pruefkonto_seed.md` | MODIFY | Kanalauswahl-Soll, Abgleich DE+EN, Klassifizierungs-Nachweis |

### Scope Assessment
- Dateien 5 (+ Spec). LoC: Seed ~+40, Tests ~+120, Zählwächter ~+10, Runbook ~+15; JSON mechanisch per Skript.
- Risiko mittel-niedrig; Aufwand im Staging-Lauf (2x Seed, 2x Abgleich à ~8 min) und der Neuklassifizierung.

### Technical Approach
1. Trip: nur Soll-Schlüssel senden: `report_config {send_email:true, send_telegram:true, send_sms:false, send_premium_sms:false}`, `alert_channels` alle 4 true, `alert_channel_thresholds {email:LOW, telegram:LOW, sms:MODERATE, premium_sms:HIGH}` (Go mergt je Feld, `internal/handler/trip.go:437-535`; Flachfelder leitet der Store ab, `internal/store/trip.go:108-121`).
2. Vergleich: top-level `send_*`, `alert_channels` EXPLIZIT (sonst Ableitung `internal/store/compare_preset.go:55-71`), `alert_channel_thresholds`; Unterobjekte feldweise mergen.
3. `_enthaelt`-Teilvergleich auf Unterobjekte; Idempotenz-Test mit Go-Normalisierung (Muster `test_ac4_f001_zweiter_lauf_ohne_schreibzugriff_trotz_go_normalisierung`); Go validiert Schwellen nicht → exakte Werte LOW/MODERATE/HIGH als Konstanten.
4. TDD: Tests rot, dann Seed.
5. Nach Merge: Seed auf Staging zweimal (Lauf 2 schreibfrei; legt fehlenden GR221-Trip/Münsterland/Orte neu an), Abgleich DE und EN.
6. Neuklassifizierung der 247 aus frischen Berichten (alte Zahlen 119/53/62/15 veraltet); Klassifizierung als Issue-Kommentar.
7. Besitzerliste per Skript: aufgelöste entfernen; B5 → #2799/#2867; „gesperrt: {grund}“ → #3122; EN-Rest → #3194; übrige echte Abweichungen → neue Kind-Issues von #2913 (Mockup ist Soll, Epic #2913): Kanalzeile Zustellung (B1+B1b), Grünbereich „· grün:“ (B2), Gewitter-Stufen (B4, #2955 prüfen), Anzeige-Metriken Trip-Wetter (B8, verwandt #3086), Vorlage alpen-trekking Temperatur-Skala/Zurücksetzen (B3+B7), Kleinkram (B9 „:00“, B6 Vorlagen-Auswahl Orte). Nur anlegen, was der Neulauf bestätigt.
8. Zählwächter anpassen; Besitzerlisten-Wächter und Seed-Tests mit benannten Dateien laufen lassen.
9. GitHub-Texte: Telegram-/Mockup-Namen nie als bares At-Handle (Nutzerbeschwerde im Issue), immer in Backticks.

### Befunde gegen den Plan
- Seed sendet heute `{**ist, **soll}` oberste Schlüssel → für Unterobjekte unzureichend; nur Soll-Teilobjekte senden.
- Versand-Risiko: Vergleich `schedule: daily` 07:00 mit Telegram-Briefing und Alarmen auf 4 Kanälen. SMS auf Staging Sandbox (`src/app/config.py:222-224`), Telegram Test-Bot (`config.py:255-258`), Empfänger fiktiv bzw. Test-Postfach. In der Spec prüfen/festlegen, dass nichts an echte Geräte geht.
- Zählwächter bewacht nur Schlüssel in `soll`: neue Verweise dort aufnehmen.

### Dependencies
- Staging-`.env` (`GZ_PRUEFKONTO_*`), Loopback 8091, Premium-Tarif des Prüfkontos; Ziel-Issues #2799, #2867, #3122, #3194; #3145 geschlossen bestätigen.

### Open Questions
- keine an den PO: Epic #2913 legt das Mockup als Soll fest; B3/B6/B7 werden als Kind-Issues (App ans Mockup) angelegt, dort ggf. Produktentscheid.
