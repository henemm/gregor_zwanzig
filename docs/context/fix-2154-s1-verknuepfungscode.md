# Context: fix-2154-s1-verknuepfungscode

Issue: [#2154](https://github.com/henemm/gregor_zwanzig/issues/2154) (`bug`, `priority:high`, Teil von Epic #2138)
Scheibe: **A — Sicherheit/Backend**. Scheibe B (Konto-Oberfläche) folgt in eigenem Workflow.

## Request Summary

Der Premium-SMS-Rückkanal ordnet eine eingehende Garmin-Rufnummer heute per Heuristik einem Nutzer
zu: Treffer auf die gespeicherte Rückadresse, sonst „genau ein Premium-Kandidat". Bei einem
Premium-Nutzer wird dadurch **jede** fremde Nummer diesem Nutzer zugeschrieben und überschreibt
seine legitime Rückadresse (Hijacking, Kostenwirkung); ab zwei Premium-Nutzern scheitert jede
Erstzuordnung dauerhaft mit 409. Ersatz: ein Verknüpfungs-Code aus dem Konto, den der Nutzer per
inReach mitschickt — Vorbild ist der Telegram-`/start TOKEN`-Fluss.

## Der heutige Pfad (Ist-Stand)

```
seven.io-Journal  →  InboundSmsReader (Python)  →  POST /api/internal/premium-sms-learn (Go)
                     Marker "inreachlink.com"      R3-Heuristik → user_id
                             ↓                              ↓
                     Befehl = Text VOR dem Marker   ←  user_id aus der Antwort
                             ↓
                     InboundMessage → TripCommandProcessor
```

**Zentral:** Der Lernaufruf ist der einzige Ort der Nutzer-Auflösung. Python konsumiert das Ergebnis
(`inbound_sms_reader.py:244`); fehlt `user_id`, wird der Befehl gar nicht verarbeitet
(`inbound_sms_reader.py:245-251`, bewusst gegen Cross-User-Lecks). Ein Verknüpfungs-Code repariert
deshalb nicht nur das Lernen, sondern denselben Pfad, über den **Befehle** einem Konto zugeordnet
werden.

**Der Nutzertext ist verfügbar, wird aber nicht gemeldet.** `inbound_sms_reader.py:255` schneidet den
Text vor dem Garmin-Kennzeichen als Befehl heraus; die Aufzeichnung
`tests/unit/test_inbound_sms_reply_learning.py:57` belegt die Form
(`"Test ueber App inreachlink.com/… (51.9956, 7.7136)"`). An Go geht heute aber nur
`{"from": sender}` (`inbound_sms_reader.py:171`) — der Text fehlt im Payload.

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/handler/premium_sms_connect.go:52-115` | **Kern des Bugs.** R3-Heuristik inkl. `len(candidates) == 1`-Fallback (Z. 71-73), 409-Pfad (Z. 98-105), `SaveUser` (Z. 107-113) |
| `internal/handler/telegram_connect.go:17-139` | **Bauvorbild.** `TelegramTokenStore` (Z. 25-29), JSON-Persistenz `load`/`save` 0600 (Z. 41-68), `CreateToken` 16 Byte hex / 24 h (Z. 72-83), `ResolveAndDelete` atomar unter Lock (Z. 88-102), Konto-Endpoint mit `UserIDFromContext` (Z. 108) |
| `internal/model/user.go:33-38` | `PremiumSmsReplyTo` / `PremiumSmsReplyAt`; Kommentar hält fest: Rückadresse wird von Garmin **je Gespräch neu** vergeben |
| `internal/model/tier.go:35-40` | `EffectiveTier` — Kandidatenfilter auf `premium` |
| `internal/store/user.go:19,51,73` | `ListUserIDs` / `LoadUser` / `SaveUser`; `SaveUser` ist **Replace**, der Read-Modify-Write-Zyklus liegt im Handler |
| `internal/router/router.go:92,93,94,97` | Registrierung telegram-link / telegram-status (SessionAuth) und telegram-connect / premium-sms-learn (localhost-only) |
| `internal/middleware/auth.go:66` | `/api/internal/` ist von der `AuthMiddleware` ausgenommen |
| `cmd/server/main.go:63,118` | Wo der Token-Store instanziiert und in `router.Deps` gehängt wird |
| `src/services/inbound_sms_reader.py:164-230` | Poll-Schleife: Lernaufruf **vor** Befehlsverarbeitung, Statuscode-Behandlung (200/4xx/5xx), Zeiger-Logik |
| `src/services/inbound_sms_reader.py:171-175` | Payload `{"from": …}` (+ `dry_run`) — hier muss der Text mit |
| `src/services/inbound_sms_reader.py:232-275` | `_verarbeite_befehl`: `user_id` aus Go-Antwort, `befehl` per `split(GARMIN_MARKER)`, `InboundMessage` |
| `src/output/channels/premium_sms.py:61-93` | `_resolve_sender`/`_resolve_recipient`; 30-Tage-TTL der gelernten Adresse |
| `docs/reference/api_contract.md:3005-3007,3277-3278` | SSoT der DTO-Felder; `premium_sms_reply_to` ist read-only, einziger Schreiber ist der Lern-Endpoint |

## Existing Patterns

- **Verknüpfungs-Token (Telegram):** eigener Store als JSON-Datei neben `user.json`, nicht als Feld im
  Nutzerprofil; 16 Byte `crypto/rand` → 32 hex; TTL 24 h; `ResolveAndDelete` verbraucht den Token
  atomar; Einlösung nur über einen localhost-Endpoint; Eindeutigkeitsprüfung vor dem Schreiben
  (409 `chat_id_already_linked`), Re-Connect desselben Nutzers erlaubt.
- **Kein gemeinsamer Token-Generator.** Dreimal dasselbe Muster `rand.Read(N) → hex`:
  `telegram_connect.go:72-76` (16 B), `auth.go:260-268` (Passwort-Reset, 32 B), `auth.go:760-765`
  (E-Mail-Bestätigung, 32 B). Ein `internal/token`-Paket existiert nicht.
- **Fail-closed ohne `default`:** der bestehende 409-Pfad fällt nie auf `"default"` zurück — dieses
  Verhalten ist zu erhalten.
- **Rufnummern nur maskiert protokollieren:** `maskPhoneNumber` (`premium_sms_connect.go:122-127`).
- **Dry-Run als eigener Rückgabepfad**, nicht als `if` um `SaveUser` (`premium_sms_connect.go:77-96`).

## Dependencies

- **Upstream (was wir benutzen):** `store.ListUserIDs/LoadUser/SaveUser`, `model.EffectiveTier`,
  `middleware.UserIDFromContext`, seven.io-Journal, `app.origin_guard.classify_origin`.
- **Downstream (was von uns abhängt):** `InboundSmsReader._verarbeite_befehl` (braucht `user_id`),
  `TripCommandProcessor` (`docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md`),
  `PremiumSmsOutput._resolve_recipient` (liest `premium_sms_reply_to`), Alarm-Versand (#1701),
  `GET /api/auth/profile` (gibt `premium_sms_reply_state` lesend aus, #1717 S3).

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` (v1.5) | **Wird abgelöst, soweit es die Zuordnung betrifft.** AC-4 (Z. 303-304) schreibt den Ein-Kandidaten-Fallback ausdrücklich fest, AC-5 (Z. 306-307) den 409 bei zwei Nutzern |
| `docs/specs/modules/feat_1717_s3_premium_sms_ui.md` | Rückadress-Status in der Oberfläche (`premium_sms_reply_state`) |
| `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md` | Befehlsverarbeitung, die auf der Zuordnung aufsetzt |
| `docs/features/architecture.md:203 ff.` | beschreibt den Rückkanal ausdrücklich „für genau einen Premium-Nutzer" — muss mit |

## Bestehende Tests (Regressionsnetz)

- `internal/handler/premium_sms_connect_test.go` — Persistenz, Dry-Run.
- `tests/unit/test_inbound_sms_reply_learning.py` — 8 Tests: Marker-Erkennung, Dedup-Zeiger,
  Herkunftssperre, Zeiger-Verhalten bei 409 vs. Netzwerkfehler.
- `tests/tdd/test_premium_sms_kommandopfad.py:803` — `test_ac7_zwei_nutzer_erhalten_je_ihre_eigene_antwort`:
  bereits ein Zwei-Nutzer-Fall, allerdings mit **vorab gesetzten** Rückadressen — die Erstzuordnung
  prüft er nicht.
- `internal/model/premium_sms_test.go`, `tests/test_premium_sms_ttl_drift.py` — TTL-Gleichlauf Go/Python.

## Risks & Considerations

1. **🔴 Die Rufnummer ist kein Wiedererkennungsmerkmal.** Garmin vergibt die Rückadresse je Gespräch
   neu (`internal/model/user.go:33`). Ein „einmal verknüpfen, danach erkennt uns die Nummer" gibt es
   hier nicht. → **Kernfrage für `/20-analyse`** (unten).
2. **🔴 Der IP-Rate-Limiter passt nicht.** `internal/middleware/ratelimit.go:33` zählt je IP; der
   Lernaufruf kommt immer von localhost. Eine Bremse gegen Code-Raten muss an der Absendernummer
   oder am Code selbst hängen, nicht an der IP.
3. **Migrations-Spannung.** Die Datenregel verlangt Bestandserhalt, der Sicherheitsbefund sagt: genau
   die gespeicherte `premium_sms_reply_to` ist die möglicherweise entführte. Annahme muss als AC
   formuliert und vom PO freigegeben werden.
4. **Schema-Hook.** Edits an `internal/model/user.go` / `internal/store/store.go` lösen
   `data_schema_backup.py` aus; Read-Modify-Write-Merge ist Pflicht (`SaveUser` ist Replace).
5. **API-Vertrag.** Die Payload-Änderung Python→Go und etwaige neue Konto-Felder gehören in
   `docs/reference/api_contract.md` (SSoT).
6. **Abgrenzung zu Nachbar-Issues:** #2153 (allgemeine Quoten/Rate-Limits am Profil) und #2159
   (Localhost-Guard hängt am nginx-Header) bleiben eigene Tickets — hier nur der Code-spezifische
   Schutz.
7. **Staging ist blind.** Der Poll läuft außerhalb der Produktion nur mit
   `GZ_PREMIUM_SMS_POLL_DRYRUN=1` und dann ohne Schreibwirkung
   (`inbound_sms_reader.py:101-117`). Der Nachweis muss deshalb im Kern liegen (Go- und
   Python-Tests), nicht an einem echten inReach.
8. **LoC-Grenze.** Token-Store + Erzeugungs-Endpoint + Handler-Umbau + Python-Payload + Tests
   sprengen voraussichtlich 250 — `loc_limit_override 500` einplanen.

## Aus dem Code bereits entschieden (nicht mehr offen)

**E1 — Der Code wird nur verlangt, wenn die Absendernummer unbekannt ist** (also einmal je
Gespräch), nicht in jeder Nachricht. Grund ist nicht Bequemlichkeit, sondern der Befehlspfad:
`inbound_sms_reader.py:255` reicht den gesamten Text vor dem Garmin-Kennzeichen als Befehl weiter.
Müsste in *jeder* Nachricht ein Code stehen, müsste er in *jeder* Nachricht wieder herausgeschnitten
werden, bevor `TripCommandProcessor` ihn sieht — eine dauerhafte Last auf dem Befehlspfad (#2184 S4)
und ein Bruch der bestehenden Befehls-Aufzeichnungen. Zwingende Gegenbedingung: ein Treffer auf eine
**gespeicherte** Nummer darf nur die bestehende Zuordnung bestätigen, **niemals** eine neue auslösen.

**E2 — Der Code ist ein stabiles Konto-Geheimnis, kein verbrauchbarer Token.** Weil Garmin die
Nummer je Gespräch neu vergibt (Risiko 1), wäre ein Einmal-Token wie bei Telegram
(`ResolveAndDelete`, `telegram_connect.go:88-102`) vor **jedem** Gespräch neu aus der Weboberfläche
zu holen — unterwegs bei unvorhersehbarer Empfangslage unbrauchbar. Vom Telegram-Vorbild wird
deshalb die **Persistenz- und Sperrmechanik** übernommen, **nicht** die Token-Semantik
`CreateToken`/`ResolveAndDelete`.

**E3 — Die Ratebremse gehört in diese Scheibe, nicht nach #2153.** Ein kurzer, von Hand getippter,
dauerhaft gültiger Code an einem localhost-Endpoint ohne Versuchszähler wäre die gesamte
Sicherheitsgrenze dieser Scheibe. „Ein Kandidat gewinnt" durch „ratbarer Code, unbegrenzte Versuche"
zu ersetzen wäre keine Verbesserung. Der Zähler muss an Absendernummer/Code hängen (nicht an der IP,
Risiko 2) und als eigenes AC erscheinen.

## Offene Fragen für `/20-analyse`

1. **Code-Gestalt:** Der Nutzer tippt ihn auf einem inReach-Gerät ab. 32 hex wie beim Telegram-Token
   ist dafür zu lang. Länge/Alphabet/Verwechselungsarmut gegen Ratbarkeit abwägen — zusammen mit der
   Bremse aus E3.
2. **Verhalten bei Bestandsdaten:** bleibt eine heute gelernte `premium_sms_reply_to` gültig, oder
   wird sie beim Umstieg verworfen und muss neu verknüpft werden? (Annahme als AC formulieren,
   Entscheidung beim PO bei der AC-Freigabe.)
3. **Was passiert mit dem Rest der Verknüpfungs-Nachricht** — nur verknüpfen, oder Code abtrennen
   und den Rest als Befehl ausführen?
4. **Wo sieht der Nutzer seinen Code, solange Scheibe B fehlt?** Mindestens ein lesender
   Konto-Endpoint muss in Scheibe A entstehen, sonst ist der Code unerreichbar und der Kanal tot.

## Analysis

### Type
**Bug** (`priority:high`, Hijacking-Befund). Befund-Aktualität geprüft: seit dem Issue-Datum
06.09.2026 keine Änderung an `internal/handler/premium_sms_connect.go` oder
`src/services/inbound_sms_reader.py`; keine Code-/Token-Mechanik im Bestand. Der Beleg gilt.

### Zweiter Befund aus der Gegenprobe (war im Issue nicht enthalten)

**🔴 Der Bestätigungspfad prüft das Alter der gespeicherten Nummer nicht.**
`premium_sms_connect.go:63-66` vergleicht `body.From` gegen `user.PremiumSmsReplyTo` **ohne**
`PremiumSmsReplyAt` bzw. `model.PremiumSmsReplyTTL` (30 Tage, `internal/model/premium_sms.go:24`)
heranzuziehen — die TTL wird ausschließlich beim **ausgehenden** Versand geprüft
(`src/output/channels/premium_sms.py:82-92`). `docs/adr/0049-premium-sms-vierter-kanal.md:65-67`
hält ausdrücklich fest, dass Garmin Nummern neu vergibt und eine alte Nummer bei einem Fremden
landen kann — gebaut ist diese Einsicht aber nur für den Ausgang, nicht symmetrisch für den Eingang.

**Folge:** Wandert eine Nummer nach Ablauf der 30 Tage an ein fremdes Gerät, trifft dessen erste
Garmin-Nachricht `storedMatch` **ohne Code** und übernimmt das Konto. Kein Raten nötig, bloßer
Nummern-Umlauf genügt. `TestLearnOverwritesReplyAddressAcrossCalls` testet dieses bedingungslose
Überschreiben heute als Sollverhalten. **Ein Fix, der nur die Erstzuordnung härtet, lässt diese Tür
offen** — der TTL-Abgleich muss in den Eingangspfad.

### Zur Rotationsrate (B2): die Antwort wird bewusst irrelevant gemacht

„Garmin vergibt die Nummer je Gespräch neu" steht an drei Stellen unbelegt
(`internal/model/user.go:33`, ADR-0049:29, `feat_1676_s1…md:24`); die einzige empirische Grundlage
ist **eine** Messung vom 10.08.2026 (`feat_1676_s1…md:326` nennt das Kennzeichen selbst „einfach
belegt, nicht bewiesen"). Statt die Rate zu messen, wird das Design so gebaut, dass sie keine Rolle
spielt: **Der Code wird immer dann verlangt, wenn kein *frischer* gespeicherter Treffer vorliegt.**
Rotiert Garmin häufig, tippt der Nutzer den Code je Gespräch einmal mit; ist die Nummer stabil,
praktisch nie. Beides ist korrekt und sicher. Die Code-Abtrennung aus dem Text ist dadurch auf die
**jeweils erste Nachricht** beschränkt — die im Kontext beschriebene Dauerlast auf dem Befehlspfad
entsteht in keinem der beiden Fälle.

### Technische Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| **D1** | Code liegt **nicht** in `model.User`, sondern als eigene Datei je Nutzer (`data/users/<id>/premium_sms_link.json`) mit `CodeHash` + `CreatedAt` | Vorbild sind die zwei bestehenden Präzedenzfälle `SaveResetToken`/`SaveVerificationToken` (`internal/store/user.go:104-136,150 ff.`) — bereits pro Nutzer und bereits gehasht. Vermeidet Schema-Migration, `data_schema_backup.py` und das Replace-Risiko von `SaveUser` |
| **D2** | **7 Zeichen**, Alphabet ohne verwechselbare Zeichen (kein `I`/`L`/`O`/`0`/`1`) → 31 Zeichen, ≈ 35 Bit | Der Nutzer tippt ihn auf einer inReach-Tastatur ab. Schlüsselraum ≈ 2,75·10¹⁰; jeder Rateversuch kostet den Angreifer eine echte, bezahlte SMS und trifft frühestens beim nächsten 5-Minuten-Poll ein |
| **D3** | Konto-Endpoint erzeugt/erneuert den Code und gibt ihn **einmal** im Klartext zurück; Status-Endpoint zeigt nur „Code vorhanden ja/nein" | Gespeichert wird nur der Hash, also ist Wiederanzeigen unmöglich. Genau das Muster von Passwort-Reset und E-Mail-Bestätigung (`internal/handler/auth.go:756-778`). Erneuern entwertet den alten Code |
| **D4** | **TTL-Abgleich auch im Eingang:** ein gespeicherter Nummern-Treffer bestätigt nur, solange er innerhalb `PremiumSmsReplyTTL` liegt; danach zählt er als unbekannt und verlangt den Code. Der Eingang liest **dieselbe Konstante** `model.PremiumSmsReplyTTL`, nie einen neuen Zahlenwert | Schließt die Recycling-Lücke oben. Es gibt bereits einen Gleichlauf-Wächter Go↔Python (`tests/test_premium_sms_ttl_drift.py`) — eine dritte Kopie der Frist würde ihn unterlaufen |
| **D5** | Ratebremse: **globaler Zähler nur für erfolglose Code-Vergleiche**, nicht je IP, nicht je Absendernummer, nicht je Konto | Die IP ist immer localhost; die Absenderkennung ist fälschbar; je Konto gezählt könnte ein einzelner Angreifer mehrere Premium-Nutzer gleichzeitig aussperren. Dry-Run-Läufe dürfen den Zähler nie berühren |
| **D6** | Bestehende gelernte `premium_sms_reply_to` werden beim Umstieg **verworfen** — als **testbare Migrationsfunktion**, nicht als Hand-Eingriff im Datenbestand | Jede Variante mit Bestandserhalt hält genau die möglicherweise entführte Nummer als Bestätigungspfad am Leben. Betroffen ist heute genau ein Nutzer; als Funktion bleibt der Schritt bei künftig mehr Premium-Nutzern wiederholbar. **Folge für den PO: einmal neu verknüpfen.** Geht als AC in die Freigabe |
| **D7** | Ein **nicht aufgelöster Absender löst keine ausgehende Antwort aus**. Das AC wird gegen das **beobachtbare Ergebnis** formuliert („keine ausgehende SMS an eine unbekannte Nummer"), nicht gegen den Mechanismus; die Gegenprobe lautet „Antwort im unaufgelösten Zweig wieder einbauen ⇒ Test muss rot werden" | Heute erzeugt jede fremde Nachricht bei genau einem Premium-Nutzer eine kostenpflichtige Premium-SMS an die fremde Nummer (`inbound_sms_reader.py:203,271-275`) — Kosten-DoS ohne jedes Geheimnis. **Achtung:** Nach dem Fix ergibt sich das Verhalten als *Folge* des 409-Pfads (`:245-251`), es ist keine eigene Zusicherung. Deshalb muss der Test am Wirkort messen, nicht am Codeort |
| **D8** | Ein abgelehnter Lernversuch (4xx) muss im Scheduler-Status **sichtbar** werden | `api/routers/scheduler.py:167` zählt nur Netz-/5xx-Fehler; ein 409 meldet weiterhin `"status": "ok"`. Sonst ist ein ausgesperrter Nutzer stumm ausgesperrt |
| **D9** | Die Code-Abtrennung aus dem SMS-Text geschieht an **genau einer** Stelle und wird von Payload-Aufbau und `_verarbeite_befehl` gemeinsam genutzt | Sonst landet der Code als erstes Wort im ersten Befehl nach jeder Verknüpfung. Größtes stilles Bruchrisiko des ganzen Umbaus |

### Neuer Entscheidungsbaum `PostPremiumSmsLearnHandler`

1. `requireLocalOnly` — unverändert.
2. Body: `from` (Pflicht, sonst 400), `code` (optional), `dry_run`.
3. Premium-Kandidaten sammeln (`EffectiveTier == "premium"`), `storedMatch` per Nummern-Treffer.
4. `storedMatch` vorhanden **und frisch** (D4) → Ziel = dieser Nutzer; ein mitgeschickter Code wird
   ignoriert, die Ratebremse bleibt unberührt.
5. Sonst, **kein Code** → kein Ziel. *(Hier entfällt der `len(candidates) == 1`-Fallback ersatzlos
   — das ist der eigentliche Bugfix.)*
6. Sonst, **Code vorhanden** → Budget erschöpft: 429 ohne jeden Hash-Vergleich. Sonst Vergleich
   gegen den Hash jedes Kandidaten: genau ein Treffer → Ziel; kein oder mehrdeutiger Treffer →
   Zähler +1, kein Ziel, nie „default".
7. Kein Ziel → Dry-Run `would_skip` mit unterscheidbarem Grund; real 409 (bzw. 429).
8. Ziel → Dry-Run `would_learn` ohne Schreiben; real `PremiumSmsReplyTo`/`-At` setzen und speichern.

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `internal/model/premium_sms_link.go` | CREATE | Datenform des Verknüpfungs-Codes |
| `internal/store/user.go` | MODIFY | `Save/LoadPremiumSmsLinkCode` nach Vorbild der Reset-Token |
| `internal/handler/premium_sms_link_code.go` | CREATE | Konto-Endpoint: erzeugen/erneuern (einmalige Klartext-Ausgabe), Status |
| `internal/handler/premium_sms_connect.go` | MODIFY | Fallback raus, Code-Abgleich, TTL-Abgleich, Ratebremse |
| `internal/handler/premium_sms_ratelimit.go` | CREATE | Fehlversuchszähler (D5) |
| `internal/router/router.go`, `cmd/server/main.go` | MODIFY | Registrierung + Instanziierung |
| `src/services/inbound_sms_reader.py` | MODIFY | Code aus dem Text abtrennen (D9), im Payload mitschicken; keine Antwort ohne Auflösung (D7) |
| `api/routers/scheduler.py` | MODIFY | Abgelehnte Lernversuche sichtbar machen (D8) |
| Go- und Python-Tests | CREATE/MODIFY | s. Testliste oben |
| `docs/reference/api_contract.md`, `feat_1676_s1…md`, `architecture.md`, ADR-0049 | MODIFY | Doku-Gleichlauf |

### Scope Assessment

- Dateien: ~13
- Geschätzt: **+550 bis +650 LoC**, −50
- Risiko: **HOCH** (Auth-nahe Identitätsbindung, Kanal für Alarme auf der Tour)
- **250-LoC-Grenze reicht nicht** — Anhebung nötig.

## Pflicht-Mitänderungen (dokumentierte Entscheidungen)

Die abzuschaffende Heuristik ist **dokumentiert** — sie darf nicht still verschwinden:

- `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` AC-4 (Z. 303-304) schreibt den
  Ein-Kandidaten-Fallback fest → ablösender Vermerk in derselben Scheibe.
- `docs/features/architecture.md:203 ff.` („für genau einen Premium-Nutzer") → mitziehen.
- `docs/reference/api_contract.md` → geänderte Payload des Lern-Endpoints.
