# Context: feat-3202-kanalzeile-mockup

## Request Summary

Issue #3202 (Epic #2913, abgespalten aus #3151): Im Reiter Zustellung (Trip und Orte) soll die Statuszeile der
Kanaltabelle dem Mockup Fassung 4 entsprechen. 23 Besitzer-Einträge in `docs/context/einstellungen_neu/elementliste_besitzer.json`.
- E-Mail: Soll „bestätigt · henning@… · +1 Empfänger“, Ist volle Adresse, ohne Empfängerzahl.
- Telegram: Soll „verbunden · @<Name>“, Ist Chat-ID.
- SMS: Soll „bestätigt · +49 171 …“, Ist Nummer ungekürzt.
- Zustand „lücken“: Soll „unbestätigt · +49 171 …“ und „inReach · Rückadresse verfallen“, Ist laut Bericht „nicht gefunden“.

## Related Files

- Komponente: `frontend/src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte` (Statuszeile Zeile 85-88:
  `{st.statusText}{st.ziel ? ` · ${st.ziel}` : ''}`; Hinweis + Konto-Link 90-96; Ladezustand Zeile 60-61).
- Eingebunden von `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` (Zeile 105: `<KanalTabelle {stand} {status} .../>`);
  Profil wird dort EINMAL per `fetch('/api/auth/profile')` geladen (Zeile 55-65), ein Code für `context="route"|"vergleich"`.
- Logik: `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts`: `kanalStatus()` Zeile 143-194 (email 147-156,
  telegram 158-165, sms 167-190), `premiumStatus()` 109-140 (fresh/stale/none), `bedienbar()` 83, `gesperrt()` 89.
  `ziel` wird in allen Zweigen als ROHWERT gesetzt (`p.mail_to`, `p.telegram_chat_id`, `p.sms_to`, `p.premium_sms_reply_to`).
- Profil-DTO (Frontend): `shared/versand-tab/channelConnectionStatus.ts` Zeile 26-52 (`ConnectionProfile`); Go: `internal/handler/auth.go`
  `profileResponse` ab Zeile 1081 (mail_to, sms_to, telegram_chat_id, email_verified, sms_verified, premium_sms_reply_*), Modell `internal/model/user.go`.
- Katalog: `frontend/src/lib/i18n/messages/{de,en}/zustellung.json` (Zeile 43 `zustellung.status.bestaetigt`, 56-57 Premium-Status).
- Mockup: `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`: `konto()` Zeile 365-372 (Daten je Zustand), `viewZustellung()` 653-700
  (Statuszeile Zeile 659: `esc(a.st)` + `' · '+esc(a.to)` nur wenn `a.ok`), Kanal-Tabelle-CSS 143-150.
- Elementliste Soll: `docs/context/einstellungen_neu/elementliste.json` (ids `trip|orte.zustellung.normal|luecke.-.kanaele.*`).
- Ist-Erfassung Lücken: `frontend/e2e/elementliste_abgleich_logik.ts` `lueckenProfil()` Zeile 272-286 (schreibt Profil-Antwort um),
  `routenPlan` 365-371; Lauf in `frontend/e2e/elementliste-abgleich.staging.spec.ts` Zeile 434-453.
- Seed: `scripts/staging_pruefkonto_mockupdaten.py` (Zeile 259-266 `soll_empfaenger` = Konto-Mail + fiktive Zweitadresse; 387-410 Telegram/Premium-SMS).
- Zählwächter: `tests/test_2913_c2_besitzerliste.py` Zeile 131-138 (`"#3202": 23`).
- Tests: `frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts`, `p12_zustellung_gleich_ausgabe.test.ts`;
  E2E `frontend/e2e/s3b2795-zustellung-kanaele.spec.ts`, `-gesperrt.spec.ts`, `-englisch.spec.ts`, `-bilder.staging.spec.ts`, `-mandanten.spec.ts`.

## Existing Patterns

- Lücken-Zustände sind im Code SCHON implementiert: SMS unbestätigt (`zustellungModell.ts` 180-189, Text „unbestätigt“), Premium verfallen
  (`premium_sms_reply_state==='stale'`, Text `zustellung.premium.status_verfallen` = „inReach · Rückadresse verfallen“), Telegram „nicht verbunden“ + „Telegram-Chat fehlt.“.
  Dazu gehören Hinweis, Konto-Link und Sperre „gesperrt: Rückadresse verfallen“.
- Kontextunterschiede nur als Daten (`KONTEXT` in ZustellungTab.svelte); KanalTabelle ist kontextfrei, Trip und Orte also automatisch gleich.
- Texte nur über den Katalog (`tr`/`$t`), Datenwerte (Nummern, Adressen) unübersetzt.
- Mockup-Kürzung ist KEINE Regel, sondern statisch eingetippte Beispieldaten (`to:'henning@… · +1 Empfänger'`, `'+49 171 …'`, `'@henning'`).
  Einzige CSS-Kürzung `.kex` (ellipsis) betrifft andere Stelle. Eine echte Kürzungsregel muss das Produkt festlegen.
- Im Mockup steht hinter dem Premium-Status im Normalzustand KEIN Ziel (`a.to` fehlt); im Lücken-Zustand ebenfalls nicht und kein Ziel bei „nicht verbunden“.

## Dependencies

- Profil-API liefert: `mail_to`, `email_verified`, `sms_to`, `sms_verified`, `pending_sms_to`, `telegram_chat_id`, Premium-Felder. Sie liefert NICHT:
  Telegram-Name/Username (Go speichert nur `TelegramChatID`; `PostTelegramConnectHandler` `internal/handler/telegram_connect.go` Zeile 315-316 bekommt nur `token` + `chat_id`
  vom Python-Reader `src/services/inbound_telegram_reader.py` ~Zeile 662), und keine Empfängerzahl.
- Empfänger: im Ortsvergleich `ComparePreset.empfaenger []string` (`internal/model/compare_preset.go:34`, Frontend `types.ts:732`); im Trip gibt es in `internal/model/trip.go`
  keinen Empfänger-Feld (nichts gefunden). Die Zählung „+1 Empfänger“ ist also je Kontext unterschiedlich definierbar; der Seed legt für den Ortsvergleich 2 Empfänger an.
  Offen, woher „+1“ im Trip kommt (siehe Open Questions).
- Katalog EN: Soll-Eintrag `bestätigt · henning@… · +1 Empfänger` hat in der Elementliste `text_en: None`, d.h. EN-Wortlaut fehlt; Muster in Elementliste: `bestätigt · {adresse}` / `confirmed · {adresse}`.

## Existing Specs/ADRs

- ADR-0112 (Oberflächen nur aus Design-System-Bausteinen, Bildprüfung gegen Mockup), ADR-0104 (DE/EN, Katalog; Zahlen/Adressen unübersetzt), ADR-0095 (Kanal-Parität: alle vier Kanäle gleichrangig; Kürzung darf keinen Kanal benachteiligen),
  ADR-0097 (Trip/Orte ein Code). Specs: `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md` (AC-14 bis AC-21 Kanalstatus), `feat_2913_abgleich_ganzseite.md` (Zustände, Z. 46).

## Risks

- Datenschutz: Telegram-Username/Name ist personenbezogen; er wird heute nirgends gespeichert. Ihn anzuzeigen heißt: neues Feld in Go-Modell + `telegram-connect`-Aufruf des Python-Readers
  (Bot-Update enthält `from.username`/`first_name`) + Export/Löschen-Pfade (`data_export`) + Bestandskonten ohne Namen (Fallback nötig, Read-Modify-Write mit Merge, kein Replace).
- Kürzung der Adresse/Nummer verbirgt Information, die der Nutzer heute zur Kontrolle sieht (z.B. falsche Nummer). Auch die Orts-Auswahl nutzt Adressen in `channelContactLabel.ts` (Chat-ID in Klammern) – nicht anfassen, sonst Regression der Versand-Dialoge (#1510).
- Gekürzte Nummer „+49 171 …“: bei nicht-deutschen Nummern keine definierte Regel.
- Der Zustand „lücken“ im Ist wird per Netz-Umschreibung erzeugt (`lueckenProfil`); die dort verwendete Nummer ist `+49 171 0000000` und die inReach-Adresse `e2e-gz@inreach.garmin.com`: ungekürzt würde der Ist-Text „unbestätigt · +49 171 0000000“ ≠ Soll.
- Zählwächter `#3202: 23` muss nach der Arbeit auf 0 gehen (Einträge löschen) und der Wächter angepasst werden; Wächter-Zahl und Liste im selben Schritt ändern.
- Empfängerzahl in der Kanalzeile gilt nur für E-Mail; Telegram, SMS, Premium haben keine Empfängerliste (Parität ADR-0095 prüfen).

## Analysis

### Type: Feature

### Root Cause

Die Kanalzeile zeigt `statusText · ziel` mit dem Rohwert aus dem Profil (`zustellungModell.ts` 143-194, `KanalTabelle.svelte` 87). Das Mockup zeigt gekürzte Beispielwerte, einen Telegram-Namen und
eine Empfängerzahl; dafür gibt es weder Kürzungsfunktion noch Daten. Zur „Lücken: nicht gefunden“-Meldung: Texte „unbestätigt“ und „Rückadresse verfallen“ existieren im Code und werden erzeugt; im Ist stehen sie aber mit angehängtem
Rohziel (`… · +49 171 0000000`, `inReach · Rückadresse verfallen · e2e-gz@inreach…`), das Mockup hat dort `+49 171 …` bzw. gar kein Ziel; die Elementliste matcht den Gesamttext, daher „nicht gefunden“.
Gleiches im Normalzustand: Ist-Premium hängt `ziel` (Rückadresse) hinter den Status, Mockup nicht (Mockup-Premium-Text ohne Adresse, Zeile 369).

### Affected Files (with changes)

- `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts`: neue reine Funktionen `adresseGekuerzt(mail)` („lokalteil@…“) und `nummerGekuerzt(nr)` („+49 171 …“); `ziel` in `kanalStatus()` gekürzt setzen; Premium: Ziel entfernen (nicht anzeigen); E-Mail: Empfängerzahl anhängen (Parameter aus Kontext).
- `.../organisms/zustellung-tab/KanalTabelle.svelte`: ggf. Zeile 87 anpassen (Anhang „+N Empfänger“ über Katalog mit Plural `trn`).
- `frontend/src/lib/i18n/messages/de|en/zustellung.json`: neuer Schlüssel für Empfängerzahl (DE „+{n} Empfänger“, EN „+{n} recipient(s)“), Telegram-Anzeige.
- Falls Telegram-Name: `internal/model/user.go`, `internal/handler/auth.go` (`profileResponse`), `internal/handler/telegram_connect.go`, `src/services/inbound_telegram_reader.py`, Export-Handler, `api_contract.md`.
- Falls Empfängerzahl: Quelle je Kontext (Preset `empfaenger`; Trip offen) an `ZustellungTab.svelte` → `kanalStatus(profil, kontext)` reichen.
- Seed `scripts/staging_pruefkonto_mockupdaten.py`: Telegram-Name des Test-Chats setzen (falls Name gespeichert wird), Empfängerzahl +1 beim Trip anlegen (falls Trip-Empfänger existiert).
- Test/Wächter: `elementliste_besitzer.json` 23 Einträge entfernen, `tests/test_2913_c2_besitzerliste.py` Zeile 138 anpassen; Modell-Unit-Tests, E2E `s3b2795-zustellung-kanaele.spec.ts`, Mockup-Bildprüfung.

### Scope Assessment

- Frontend-only (Kürzung, Premium-Ziel weg, Lücken-Texte, EN-Katalog): ca. 4-6 Dateien, ca. 80-120 LoC plus Tests.
- Mit Backend (Telegram-Name, evtl. Trip-Empfängerzahl): zusätzlich ca. 5-7 Dateien Go/Python, ca. 100-150 LoC plus Tests und Migration. Frontend-only reicht NICHT für den Telegram-Namen: Backend-Feld nötig.
- Empfängerzahl: für Ortsvergleich im Frontend schon vorhanden (`preset.empfaenger`); für Trip fehlt ein Feld (nicht gefunden).

### Technical Approach

1. Kürzungsfunktionen im Modell (rein, node:testbar): Adresse = Text bis „@“ + „@…“; Nummer = „+“ Landesvorwahl + erste drei Ziffern der Rufnummer + „ …“ (aus E.164 normalisiert; fallback ohne Landesvorwahl: erste 3 Zeichen + „ …“). Kürzung nur in der Tabellenzeile; Kontosettings behalten Volltext.
2. Premium: Ziel aus der Statuszeile entfernen (Mockup zeigt keinen); Lücken-Text kommt dann ohne Anhang wie Soll.
3. Empfängerzahl: `kanalStatus` bekommt optional `empfaengerAnzahl` (Kontext-Datum aus Preset/Trip); „· +N Empfänger“ nur E-Mail und nur wenn N>0.
4. Telegram-Name: nur nach Produktentscheidung; sonst Fallback „verbunden“ ohne Name (nie Chat-ID zeigen).
5. Elementliste/Wächter nachziehen, Staging-Ist per Ganzseitenvergleich DE+EN, Zwei-Nutzer-Test (`s3b2795-zustellung-mandanten.spec.ts`), Mockup-Bildprüfer.

### Befunde gegen den Plan

- Der Bericht „Zustand lücken nicht gefunden“ ist kein Fehlen der Funktion: die Lücken-Zustände existieren, nur der Zielanhang weicht ab (siehe Root Cause).
- Der Seed erzeugt nur den Normalzustand (Spec `feat_2913_abgleich_ganzseite.md` Z. 46); Lücken entstehen im Abgleich per Umschreibung der Profil-Antwort (`lueckenProfil`), nicht im Seed. Der Seed muss für Lücken nichts erzeugen. Er braucht höchstens den Telegram-Namen.
- Mockup-Telegram ist `@henning` (Elementliste `verbunden · @henning`, EN `connected · @henning`), ein @Benutzername, kein Anzeigename. Issue nennt „<Telegram-Name>“.
- Das Mockup hat im E-Mail-Fall im Lücken-Zustand ebenfalls „bestätigt · henning@… · +1 Empfänger“; die Elementliste enthält EN-Text `None` für die E-Mail-Zeile (Lücke in der Liste, EN-Wortlaut festlegen).
- Mockup lässt Premium-Normalzeile ohne Ziel; Ist hängt die Rückadresse an: eigener, im Issue nicht genannter Befund, gehört in denselben Schritt.

### Open Questions

1. Telegram: Soll der Benutzername (`@name`) neu gespeichert und angezeigt werden (Datenschutz, Bestandskonten ohne Namen), oder nur „verbunden“ ohne Namen? Das Mockup zeigt den Namen; heute liegt nur die Chat-ID vor.
2. Was zählt als „+1 Empfänger“ beim Trip (er hat kein Empfängerfeld) – nur Ortsvergleich (`empfaenger`) oder ein neues Feld auch für Trips?
3. Kürzungsregel für fremdländische Nummern und Adressen (Beispiel „+49 171 …“ nur für deutsche Mobilnummern festgelegt): Landesvorwahl + 3 Ziffern allgemein bestätigen?

## PO-Entscheidungen (20.11.2026)
1. Telegram: nur „verbunden“, kein Telegram-Name (keine neuen personenbezogenen Daten). Mockup-Abweichung `@name` bewusst → Elementliste-Ausnahme mit Begründung.
2. Empfängerzahl „+N Empfänger“ nur wo zusätzliche Empfänger existieren (Orts-Vergleich); beim Trip entfällt der Zusatz.
3. Kürzungsregel (Tech-Lead): E-Mail `lokalteil@…`, Telefon `+<Landesvorwahl> <3 Ziffern> …` (Mockup-Beispiel), Premium im Normalzustand ohne Rückadresse (wie Mockup).
4. **Korrektur 21.11. (PO):** „+N Empfänger“ entfällt ÜBERALL (auch Orts-Vergleich) — `preset.empfaenger` ist seit #1452 inert (scheduler_dispatch_service.py:845, compare_preset.go:144), Anzeige wäre falsch. Mockup Fassung 4 wird an Entscheidungen 1 und 4 angeglichen (Telegram ohne `@name`, E-Mail ohne „+1 Empfänger“), Elementliste neu erzeugen; keine Besitzer-Umhängung nach #3194.
