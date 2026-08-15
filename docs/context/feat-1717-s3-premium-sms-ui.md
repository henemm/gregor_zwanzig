# Context: feat-1717-s3-premium-sms-ui

**Issue:** #1717 — S3: Premium-SMS in der Oberfläche
**Vorgänger:** S1 (Rückkanal) und S2a (Versandkanal) sind **live** in Produktion
**Parallel:** #1701 (S2b, Alarm-/Vergleichspfad) — fremde Sitzung
**Basis:** `origin/main` = `64b78c63`

## Request Summary

Premium-SMS ist als Kanal live, aber **nur über die API schaltbar**. Der Nutzer kann ihn nicht
selbst ein-/ausschalten und sieht nicht, **wohin** gesendet wird. Auf Tour ist damit nicht
unterscheidbar, ob der Kanal aus ist, keine Rückadresse gelernt wurde oder sie veraltet ist —
obwohl das Backend diese drei Fälle bereits unterscheidet (`blocked_reason_codes` aus S2a).

## Der zentrale Fund: beide Platzhalter sind LEBENDIG

Die Annahme bei der Issue-Aufnahme („einer davon ist Alt-Bestand") ist **widerlegt**. Beide
deaktivierten Platzhalter werden gerendert, nur auf verschiedenen Routen:

| Platzhalter | Route(n) | Stand |
|---|---|---|
| `shared/versand-tab/VTBriefingChannels.svelte:187-192` | `/trips/[id]`, `/compare/[id]`, `/compare/new` | live |
| `edit/EditReportConfigSection.svelte:378` | **`/trips/new`** (Trip-Anlage) | **live** |

**Ursache:** Der Umbau #1232 (`424e403`, 2026-07-12) hat `EditReportConfigSection` nur im
Briefings-Reiter von `/trips/[id]` durch den geteilten `VersandTab` ersetzt. Die Trip-**Anlage**
wurde nie migriert. Zeitliche Reihenfolge: `EditReportConfigSection:376-381` ist das Original
(`7fa597c`, 2026-07-07, #1069), `VTBriefingChannels:187-192` die beim #1232-Umbau übernommene
Kopie — fünf Tage jünger.

`EditReportConfigSection` hat vier Einbaustellen, aber nur **eine** ist wirksam:

- `edit/TripEditView.svelte:203` — **kein Importer**; die Route `/trips/[id]/edit` ist ein
  Redirect-Stub. Tot.
- `briefings-tab/BriefingsTab.svelte:40` — importiert in `TripTabs.svelte:14`, aber **nie als
  Element gerendert**. Toter Import.
- `shared/WeatherMetricsTab.svelte:1546` — mit `showChannels={false}`, der Kanalblock erscheint
  dort nicht.
- **`trip-new/TripNewEditor.svelte:780` (Desktop) und `:1016` (Mobile)** — `showChannels` nicht
  gesetzt, Default `true` (`EditReportConfigSection.svelte:44`) ⇒ **Kanalblock inkl.
  Premium-SMS-Zeile wird gerendert.** Gemountet von `routes/trips/new/+page.svelte:9`.

## Vier Mounts des geteilten Versand-Reiters

| # | Stelle | `context` | Fläche |
|---|---|---|---|
| 1 | `trip-detail/BriefingScheduleTab.svelte:130` | `route` | `/trips/[id]` |
| 2 | `compare/CompareTabs.svelte:1452` | `vergleich` | `/compare/[id]` |
| 3 | `compare-new/CompareNewEditor.svelte:420` | `vergleich` (Desktop) | `/compare/new` |
| 4 | `compare-new/CompareNewEditor.svelte:502` | `vergleich` (Mobile) | `/compare/new` |

Kein Mount für die Trip-Anlage — das ist genau die Lücke oben. (Beim Nachbar-Reiter `AlarmeTab`
sind drei Compare-Mounts dokumentiert; dort deckt `AlarmeScheduleTab.svelte:60` mit
`context="route"` die Trip-Seite inklusive Anlage ab. Beim Versand ist die Anlage abgehängt.)

## Die Logik steht wörtlich doppelt im Code

Identisch in beiden Komponenten (`VTBriefingChannels.svelte:77-81`,
`EditReportConfigSection.svelte:102-106`):

```js
let availableChannels = $derived({
  email: !!profile?.mail_to,
  telegram: !!profile?.telegram_chat_id,
  sms: !!profile?.sms_to && profile?.sms_allowed !== false
});
```

`profile` wird **pro Komponenteninstanz eigenständig** per `onMount` von `/api/auth/profile`
geladen (`VTBriefingChannels.svelte:88-98`, `EditReportConfigSection.svelte:192-197`) — kein
Store, kein geteilter Zustand.

**Es gibt aber schon geteilte Helfer** für genau diese Art Logik, von beiden Komponenten benutzt:
`shared/versand-tab/channelContactLabel.ts:30` (Kontakt-Suffix am Checkbox-Label) und
`channelConnectionStatus()`. **Das ist das Muster für S3** — nicht eine dritte Kopie.

## Die Datenquelle fehlt noch komplett

- Heutige SMS-Darstellung: Label-Suffix ` (nummer)` über `channelContactLabel`, Fehlhinweis
  „Handynummer fehlt — im Account einrichten" (`VTBriefingChannels.svelte:182-185`). Quelle:
  `profile.sms_to` — eine **nutzereingegebene** Nummer (`UpdateProfileHandler`,
  `auth.go:585-586`).
- Die **gelernte** Rückadresse ist im Frontend **nirgends erreichbar**: `profileResponse`
  (`auth.go:446-465`) führt sie nicht. Ohne lesende Ergänzung gibt es keine Datenquelle.
- Tarif-Gate-Vorbild: `profile?.sms_allowed === false` ⇒ „SMS ab Level Standard verfügbar"
  (`VTBriefingChannels.svelte:178-181`). Backend: `auth.go:504` `SmsAllowed: model.SmsAllowed(tier)`,
  `model/tier.go:3-6` erlaubt `standard` + `premium`. **Premium-SMS braucht ein eigenes Gate —
  nur `premium`** (S2a hat dafür `premium_sms_allowed()` in Python; die Go-Seite hat noch keins).

## Go-Seite (gemessen)

**Lesende Profil-Ausgabe:** zwei Vorbilder, und das naheliegende ist falsch.
`EmailVerified` (`auth.go:457`, Ableitung `:505`) gibt bewusst **keinen** Rohzeitstempel aus —
AC-20 verlangt, dass `email_verified_at` nie im JSON auftaucht, festgenagelt per
Negativ-Assertion (`profile_test.go:553-554`). Für die Rückadresse ist `RequestedAt`
(`auth.go:461`, roh durchgereicht `:507`) das richtige Muster: hier **ist** der Zeitstempel die
Nutzinformation. Pointer, weil `omitempty` bei `time.Time`-Werten nicht greift.

**Kein Test nagelt die Feldmenge von `profileResponse` fest.** Es gibt nur gezielte Tests für
`sms_allowed` (`profile_test.go:465-515`) und `email_verified` (`:520-554`). Ein neues Feld ist
also unbewacht.

**`UpdateProfileHandler`-Decode-Struct** (`auth.go:541-547`) enthält die Felder nicht — S3 ist
rein lesend, dieses Struct **bleibt unverändert**. Es darf sie nie aufnehmen, sonst wird die
gelernte Adresse editierbar und die Zusage aus S2a fällt.

**Flaches Trip-Feld — kleiner als im Issue behauptet.** Korrektur: es braucht **keinen**
Merge-Zweig im Handler. Für die drei bestehenden Flach-Felder existiert keiner
(`grep` über `internal/handler/trip.go` findet die Feldnamen nicht). Der Weg ist:
Client schickt `report_config.send_premium_sms` → `mergeConfigMap` (feldweise,
`config_merge.go:11-22`) → `SaveTrip` → `normalizeTrip` → `deriveFlatFields`
(`internal/store/trip.go:57-92`) leitet neu ab. Dort werden die Pointer zuerst hart auf `nil`
zurückgesetzt (`:63-70`, Fix-Loop F001 — sonst bleibt ein Wert stehen, wenn die Quelle
verschwindet), dann bedingt gesetzt (`:79-87`).

**Frontend liest ohnehin `report_config`, nicht die Flach-Felder** (`VersandTab.svelte:91-93`,
`types.ts:343-351` nennt sie ausdrücklich „nicht autoritativ"). Das Flach-Feld ist also
Vollständigkeit des Vertrags, nicht Voraussetzung der Oberfläche.

## Ganzobjekt-Falle — für S3 NICHT relevant, aber zu kennen

`existing.AlertChannels = req.AlertChannels` (`internal/handler/trip.go:368`) ersetzt das
Unterobjekt **komplett**; `AlertChannelsConfig` (`model/trip.go:183-191`) hat kein viertes Feld.
Ein Client ohne Kenntnis eines neuen Kanals würde ihn beim Speichern still auf `false` setzen.
Der Code dokumentiert die Lehre selbst bei `AlertChannelThresholds` (`model/trip.go:193-201`) und
schützt sie deshalb **zweistufig** (`trip.go:375-386`: „ZWEI Ebenen Datenverlustschutz … Pflicht,
kein Kann"). **Das betrifft #1701, nicht S3** — S3 rührt `AlertChannels` nicht an.

## Vertrag nachzuziehen

`docs/reference/api_contract.md` erwartet diese Scheibe schon:
- `:579` — `send_premium_sms` dokumentiert, mit Hinweis „kein eigenes Go-Struct-Feld … folgt erst
  mit S3"
- `:741-743` — Trip-DTO-Block listet die drei Flach-Felder, das vierte fehlt
- `:2690-2736` + `:2832-2833` — Profil-Abschnitt ohne die Rückadress-Felder, mit dem zu
  revidierenden Hinweis „keine Auth-Profile-Ausgabe in dieser Scheibe"

## Test-Vorbilder und Regressionsnetz

1. **`shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts`** — SSR-Test, prüft
   **beide** Komponenten für dieselben Profil-Fälle auf identische Beschriftung, Verbindungsstatus
   und Deaktiviert-Zustand. **Das ist das wichtigste Netz** — es existiert genau, um die
   Doppelung synchron zu halten, und muss um Premium-SMS erweitert werden.
2. `shared/__tests__/channel_connection_status.test.ts` — u.a. „SMS hinterlegt aber tarifgesperrt".
3. `shared/versand-tab/__tests__/channelContactLabel.test.ts` — Kontakt-Suffixe.
4. `shared/versand-tab/__tests__/sendTargetLabel.test.ts` — Zieltext im Versand-Dialog, zweite
   Perspektive auf das Tarif-Gate.
5. `frontend/e2e/issue-609-sms-profil.spec.ts`, `versand-tab.spec.ts`,
   `compare-hub-versand-inline.spec.ts` — Playwright-Verankerung am Versand-Reiter.

Go-Seite: `internal/store/trip_flat_fields_test.go` (Roundtrip der Flach-Felder, inkl. „bleibt
`nil` ohne `report_config`" und „kein Stale-Zustand"), `internal/handler/profile_test.go`.

## Risks & Considerations

1. **Eine dritte Kopie der Kanal-Logik wäre der Default-Fehler.** Die Logik „fehlt / veraltet /
   frisch" gehört in einen geteilten Helfer neben `channelContactLabel.ts`, damit sie genau
   einmal existiert. Zwei Komponenten rufen sie auf.
2. **Kontrast:** „zuletzt gemeldet am …" ist ein **Daten-Label**, kein Hilfstext. Die blasseste
   Textfarbe ist strikt für Platzhalter/Deaktiviertes reserviert (2,85:1 auf Weiß) — genau dieser
   Wert entscheidet, ob man der Anzeige auf einem Handydisplay trauen kann.
3. **Die 30-Tage-Frist darf nicht zum zweiten Mal als Zahl auftauchen.** S2a führt sie als
   `PREMIUM_SMS_REPLY_TTL` in `src/output/channels/premium_sms.py:39`. Das Frontend kann sie nicht
   importieren — also muss die **Bewertung** vom Server kommen (abgeleiteter Zustand), nicht die
   Frist ins Frontend kopiert werden. Sonst driften zwei Zahlen auseinander.
4. **Browser-Gate:** Frontend-Scope ⇒ `staging_gate.py --write-verdict` lädt sechs Kernseiten in
   echtem Chromium; ohne bestandenen Lauf keine Attestation, kein Prod-Deploy. Dazu ein
   `fresh-eyes-inspector`-Lauf auf Screenshots ohne Bug-Kontext.
5. **Pendant-Sperre:** neue Dateien in einseitigen Verzeichnissen werden am Commit blockiert. Ein
   neuer geteilter Helfer gehört nach `shared/versand-tab/` — dort ist er unproblematisch.
6. **Nicht in dieser Scheibe:** `/trips/new` auf `VersandTab` umstellen. Vorbestehender Bruch der
   Teilungsregel, eigener Umbau am Anlege-Editor; gebucht in #1199.

## Nachweis-Grenze

S3 beweist: Kanal schaltbar, Zustand der Rückadresse ablesbar, kein Zustand still verschwiegen.
**Nicht** bewiesen: dass eine so eingeschaltete Premium-SMS auf dem Gerät ankommt — das bleibt
#1533.
