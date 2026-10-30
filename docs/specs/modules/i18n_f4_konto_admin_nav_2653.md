---
entity_id: i18n_f4_konto_admin_nav_2653
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2653, frontend, model-haiku]
---

# i18n F4: Katalog-Migration Konto, Admin, Sidebar/KontoSheet, Navigation, Speicher-Anzeige

**Issue:** #2653 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 3 (Frontend), 8

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Die Konto-Seite (Profil, Kanäle und Empfänger, Premium-SMS-Kopplung, SMS-Kontingent, Tier-Antrag, Scheduler-Status, Konto löschen), die Admin-Seite sowie Seitenleiste, untere Navigation, Konto-Blatt und die Speicher-Anzeige sind für englischsprachige Nutzer vollständig auf Englisch. Werte wie Kontingent- und Statuszahlen bleiben für beide Sprachen identisch, nur die Sprache der Beschriftung wechselt. Deutsch bleibt wörtlich wie heute.

## Source

- **File:** `frontend/src/routes/account/+page.svelte`, `frontend/src/routes/account/profileSaveError.ts`, `frontend/src/routes/admin/+page.svelte`, `frontend/src/lib/admin.ts`, `frontend/src/lib/components/account/PremiumSmsLinkCard.svelte`, `frontend/src/lib/components/ui/sidebar/{Sidebar,BottomNav,KontoSheet}.svelte`, `frontend/src/lib/components/ui/SaveIndicator.svelte`
- **Identifier:** `timeAgo`, `DELETE_ERROR_TEXT`, `deleteErrorText` (account/+page.svelte), `profileSaveErrorMessage` (profileSaveError.ts), `adminErrorText`, `inviteStatusText`, `inviteErrorText` (admin.ts), `baseNavItems` (Sidebar.svelte); Katalog-Namensräume `konto.*`, `admin.*`, `nav.*`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Server-Antworten der Go-API (Fehlercodes `wrong_password` …) bleiben unverändert; das Frontend übersetzt bekannte Codes selbst. Kein Go-/Python-Code in diesem Paket.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/konto.json` | MODIFY | Konto-Texte (Profil, Kanäle, Passkeys, Passwort, Wetter-Profile, Reports, Löschen, Kontingent, Tier-Antrag) |
| `frontend/src/lib/i18n/messages/en/konto.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/i18n/messages/de/admin.json` | MODIFY | Admin-Seite (Einladungen, Nutzerliste, Dialoge, Fehler) |
| `frontend/src/lib/i18n/messages/en/admin.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/i18n/messages/de/nav.json` | MODIFY | Navigation, Konto-Blatt, Speicher-Anzeige (der bestehende Schlüssel `nav.hilfe` bleibt) |
| `frontend/src/lib/i18n/messages/en/nav.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/routes/account/+page.svelte` | MODIFY | alle Beschriftungen, Hinweise, Fehlertexte, `timeAgo`, `DELETE_ERROR_TEXT` |
| `frontend/src/routes/account/profileSaveError.ts` | MODIFY | Fehlertexte von `profileSaveErrorMessage` über `tr()` |
| `frontend/src/routes/admin/+page.svelte` | MODIFY | PageHeader, Einladungs- und Nutzerbereich, Dialoge |
| `frontend/src/lib/admin.ts` | MODIFY | `adminErrorText`, `inviteErrorText`, `inviteStatusText`, `formatDate` über `tr()`; `TIER_LABELS` bleibt (Eigennamen) |
| `frontend/src/lib/components/account/PremiumSmsLinkCard.svelte` | MODIFY | Titel und Texte der Kopplungskarte |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | MODIFY | `baseNavItems`-Labels und alle weiteren sichtbaren Texte |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | MODIFY | Labels und `aria-label="Konto"` |
| `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte` | MODIFY | Menüpunkte, `aria-label`, Schalter „Dunkles Design" |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | MODIFY | Zustandstexte; die Uhrzeit bleibt ein eigenes `<span class="save-time">` |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `routes/account`, `routes/admin`, `components/account`, `ui/sidebar`, `ui/SaveIndicator` entfernen |
| `frontend/src/routes/account/__tests__/konto_sprache_je_nutzer.test.ts` | CREATE | Konto-Seite zwei Nutzer, zwei Sprachen |
| `frontend/src/routes/admin/__tests__/admin_sprache.test.ts` | CREATE | Admin-Seite, Fehlertexte de/en |
| `frontend/src/lib/components/ui/__tests__/navigation_und_speicheranzeige_sprache.test.ts` | CREATE | Sidebar, BottomNav, KontoSheet, SaveIndicator |
| `tests/golden/f4_konto_admin_nav/*.de.html` | CREATE | Golden-Fixtures der deutschen Ausgabe |

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** Kein Trip-/Compare-Pendant betroffen. `SaveIndicator` ist bereits ein gemeinsamer Atom und wird von Trip-Header und Compare-Editor geteilt; er bleibt ein Baustein. Texte, die auch auf Trip- und Ortsvergleich-Flächen identisch stehen (z. B. „Speichern", „Abbrechen"), liegen bis F9 unter `konto.aktion.*`; ein späterer Nebenbefund darf sie durch `aktionen.*` ersetzen.
> - **Mandantentrennung:** Die Konto-Seite liest nur das Profil des angemeldeten Nutzers (`user_id` aus Auth-Kontext, unverändert). Sprache kommt aus `data.lang` des Nutzers. Zwei-Nutzer-Test (AC-1).
> - **Kanäle:** Beschriftungen für alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) werden übersetzt, die Kanalnamen selbst bleiben Eigennamen.

## Estimated Scope

- **LoC:** ca. 380 Code-Zeilen (ohne Katalogdaten und Tests), davon Konto-Seite ca. 200, Admin ca. 55, Navigation und Speicher-Anzeige ca. 60, Hilfsdateien ca. 40. Das überschreitet das Limit von 250: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 16 Code-/Katalogdateien plus 3 Tests plus Golden-Fixtures
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2647 (S2) | Paket | `t`, `tn`, `tr`, `locale`, `fmtDate`, `fmtRelativeMinutes` |
| #2648 (S3) | Paket | Sprach-Auswahl-Baustein auf der Konto-Seite liegt schon im Katalog; hier nur die übrigen Texte |
| #2649 (S4) | Paket | Ratsche und Allowlist |
| #2652 (F3) | Paket (vorher) | `formatNextRun` in `schedulerTime.ts` wird dort sprachfähig; die Konto-Seite ruft es unverändert auf |
| `docs/reference/i18n_glossar.md` | Doku | Konto = account, Empfänger = recipient, Kontingent = quota, Kopplung = linking, Magic-Link, Passkey |
| ADR-0104 | adr | Sprache am Nutzer; Kanalnamen sind Eigennamen |

## Implementation Details

**1. Katalog.** Nur `messages/{de,en}/{konto,admin,nav}.json` bearbeiten. Deutsch wörtlich wie heute, Platzhalter `{name}` in beiden Sprachen gleich, Plural über `.one`/`.other`.

**2. Beispiel-Schlüssel (de / en).**

| Schlüssel | de | en |
|---|---|---|
| `nav.gespeichert` | Gespeichert | Saved |
| `nav.nicht_gespeichert` | Nicht gespeichert | Not saved |
| `nav.speichere` | Speichere … | Saving … |
| `nav.nochmal_speichern` | Nochmal speichern | Save again |
| `nav.hauptmenue.meine_trips` | Meine Trips | My trips |
| `nav.hauptmenue.vergleich` | Orts-Vergleich | Location comparison |
| `nav.konto_sheet.kanaele_empfaenger` | Kanäle & Empfänger | Channels & recipients |
| `konto.titel` | Mein Konto | My account |
| `konto.profil.anzeigename` | Anzeigename | Display name |
| `konto.kontingent.titel` | SMS-Kontingent (heute) | SMS quota (today) |
| `konto.kopplung.titel` | Premium-SMS-Verknüpfungscode | Premium SMS link code |
| `konto.zeit.gerade_eben` | gerade eben | just now |
| `konto.zeit.vor_stunden` | vor {count} Std | {count} h ago |
| `konto.fehler.wrong_password` | Das Passwort ist falsch. | The password is wrong. |
| `konto.fehler.email_taken` | Diese E-Mail-Adresse wird bereits von einem anderen Konto verwendet. | This email address is already used by another account. |
| `admin.kopf.sub` | Nutzer, Tier und Kontosperre | Users, tier and account lock |
| `admin.einladung.erstellen` | Einladung erstellen | Create invitation |
| `admin.fehler.keine_berechtigung` | Keine Berechtigung | No permission |

**3. Beispiel-Umstellung vorher → nachher.**

- `frontend/src/lib/components/ui/SaveIndicator.svelte:31` — vorher `<span>Gespeichert</span>`, nachher `<span>{$t('nav.gespeichert')}</span>`. Die Uhrzeit steht weiter im eigenen `<span class="save-time">` (Zeile 33), damit die DOM-Struktur und die vorhandenen Tests unverändert bleiben (Annahme A1, abweichend von der Issue-Skizze `nav.gespeichert` mit `{zeit}`).
- `frontend/src/routes/account/+page.svelte:467-476` — `timeAgo(iso)`: `mins < 1` → `$t('konto.zeit.gerade_eben')`; Minuten über `fmtRelativeMinutes(mins, lang)`; Stunden über `tn('konto.zeit.vor_stunden', hours)`; Tage über `tn('konto.zeit.vor_tagen', days)` mit `.one` = `vor {count} Tag` / `{count} day ago` und `.other` = `vor {count} Tagen` / `{count} days ago`. Das heutige Verhalten `vor 3 Min`, `vor 2 Std`, `vor 1 Tag`, `vor 2 Tagen` bleibt deutsch byte-gleich.
- `frontend/src/routes/account/+page.svelte:507-513` — `DELETE_ERROR_TEXT` wird zu `Record<string, MessageKey>` mit `konto.fehler.<code>`, `deleteErrorText` ruft `$t(...)` bzw. `tr(...)` auf.
- `frontend/src/lib/admin.ts:13` — vorher `return 'Keine Berechtigung';`, nachher `return tr('admin.fehler.keine_berechtigung');`.
- `frontend/src/lib/components/ui/sidebar/Sidebar.svelte:33` — vorher `label: 'Startseite'`, nachher `label: $t('nav.hauptmenue.startseite')` (die Liste als `$derived`, damit sie auf Sprachwechsel reagiert).

**4. Format-Hinweise.** `admin.ts` `formatDate` nutzt heute `toLocaleDateString('de-DE')`: bei `de` unverändert (byte-gleich), bei `en` `en-GB` (Annahme A2). Weitere `toLocaleDateString('de-AT', …)`-Aufrufe in `account/+page.svelte` (Zeile 333) und `toLocaleString('de-DE')` in `admin/+page.svelte` (Zeile 86) folgen derselben Regel. Zonen- und Zeitlogik (`schedulerLastRun`, `formatNextRun`) bleiben unberührt; `formatNextRun` kommt aus F3.

**5. Nicht übersetzen.** Kanalnamen (E-Mail, Telegram, SMS, Premium-SMS, Garmin inReach), Tier-Namen in `TIER_LABELS`, Provider-Namen (`GeoSphere (Alpen)`, `OpenMeteo`), Nutzernamen und Adressen. Der Job-Anzeigename `Trip-Checks` (`userJobs`) wird übersetzt (`konto.job.trip_checks` = Trip-Checks / Trip checks). Fließtext für Premium-SMS schreibt englisch „Premium SMS" (Glossar).

**6. Allowlist.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` entfernen: `routes/account`, `routes/admin`, `components/account`, `ui/sidebar`, `ui/SaveIndicator`. `lib/admin.ts` liegt im Bereich der späteren TS-Ratsche (ab F11); der Eintrag, falls vorhanden, wird ebenfalls entfernt.

**7. Golden-Fixture.** Vor der Umstellung die deutsche Konto-Seite (Standard-Nutzer `golden-de`, Tier Premium, mit Kontingent und gekoppeltem Telegram), die Admin-Seite (zwei Nutzer, eine Einladung) und die Navigation (Sidebar + BottomNav + KontoSheet) per SSR nach `tests/golden/f4_konto_admin_nav/<fall>.de.html` schreiben; nach der Umstellung byte-gleich vergleichen. `*.en.html` wird zur Review mit eingecheckt.

## Expected Behavior

- **Input:** Aufruf von `/account`, `/admin`; jede Seite mit sichtbarer Navigation; Speichervorgänge mit `SaveIndicator`.
- **Output:** Sichtbare Texte in der Sprache des angemeldeten Nutzers; Zahlen (Kontingent, Zähler), Kanal-, Provider-, Nutzernamen unverändert.
- **Side effects:** Keine. Keine neuen Netzaufrufe. Der Sprach-Umschalter selbst ist S3.

## Acceptance Criteria

- **AC-1:** Given Nutzer A mit Sprache Englisch und Nutzer B mit Deutsch, beide mit demselben Tier und denselben Kontingent-Zahlen / When beide `/account` laden / Then sind alle Beschriftungen bei A englisch und bei B deutsch, die Kontingent- und Statuswerte sind bei beiden identisch, und keiner sieht Daten oder Sprache des anderen.
  - Test: `frontend/src/routes/account/__tests__/konto_sprache_je_nutzer.test.ts` — zwei Nutzer in einem Lauf, Prüfung über `tr()`-Werte; Zahlenwerte als Gleichheit zwischen den Ausgaben.

- **AC-2:** Given die Konto-Seite in Englisch / When ein Fehler beim Löschen (`wrong_password`), beim Speichern des Profils (`email_taken`) und beim Anfordern eines Codes (`code_expired`) auftritt / Then erscheint jeweils der englische Katalogtext, bei unbekanntem Fehlercode die unveränderte Server-Meldung.
  - Test: `frontend/src/routes/account/__tests__/konto_sprache_je_nutzer.test.ts` — `deleteErrorText` und `profileSaveErrorMessage` für `en` und `de`, unbekannter Code liefert den Server-Text.

- **AC-3:** Given der Zeitstempel einer Scheduler-Ausführung vor 3 Minuten, 2 Stunden und 1 Tag / When die Konto-Seite die Zeit anzeigt / Then steht in Englisch „3 min ago", „2 h ago", „1 day ago" und in Deutsch weiterhin „vor 3 Min", „vor 2 Std", „vor 1 Tag".
  - Test: `frontend/src/routes/account/__tests__/konto_sprache_je_nutzer.test.ts` — `timeAgo` mit fester Zeit, beide Sprachen, Plural `.one`/`.other`.

- **AC-4:** Given ein Admin in Englisch / When die Admin-Seite lädt und eine Aktion mit Status 403, 404 und 409 (`cannot_disable_self`) scheitert / Then lauten die Zeilenfehler englisch („No permission" …) und die Einladungsstatus („Used by …", „Revoked on …") englisch; Datum und Namen bleiben unverändert.
  - Test: `frontend/src/routes/admin/__tests__/admin_sprache.test.ts` — `adminErrorText`, `inviteStatusText`, Render der Admin-Seite für `en` und `de`.

- **AC-5:** Given die Navigation (Sidebar, untere Leiste, Konto-Blatt) und die Speicher-Anzeige in Englisch / When die Zustände gespeichert, ungespeichert, speichernd, Konflikt und Fehler durchlaufen werden / Then zeigen alle Beschriftungen englischen Text („Saved", „Not saved", „Saving …", „Save again"), und bei „Saved" steht die Uhrzeit weiter im eigenen Element.
  - Test: `frontend/src/lib/components/ui/__tests__/navigation_und_speicheranzeige_sprache.test.ts` — Render je Zustand, DOM-Struktur (`.save-time`) bleibt.

- **AC-6:** Given die deutsche Oberfläche / When Konto-Seite, Admin-Seite und Navigation mit der Fixture `golden-de` gerendert werden / Then ist die Ausgabe Byte für Byte gleich zu `tests/golden/f4_konto_admin_nav/*.de.html`.
  - Test: `frontend/src/routes/account/__tests__/konto_sprache_je_nutzer.test.ts` — Golden-Vergleich (deutsche Ausgabe unverändert).

- **AC-7:** Given die Allowlist der Ratsche / When `keine_hartkodierten_nutzertexte.test.ts` und der Paritätstest laufen / Then gibt es keine Treffer mehr in den Dateien dieses Pakets, die Allowlist enthält keine Einträge für `routes/account`, `routes/admin`, `components/account`, `ui/sidebar`, und `konto`, `admin`, `nav` haben in de und en identische Schlüssel- und Platzhaltermengen.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` und `paritaet_de_en.test.ts` — Ratschen-/Paritätstest (`# doc-compliance-test`).

## Known Limitations

- **A1 (Annahme):** Die Issue-Skizze nennt `t('nav.gespeichert', {zeit})`. Im Ist-Stand stehen Text und Uhrzeit in getrennten `<span>`; der kleinste Eingriff ist ein Schlüssel ohne Platzhalter, damit das DOM unverändert bleibt.
- **A2 (Annahme):** Datumsformate in `admin.ts`, `admin/+page.svelte` und `account/+page.svelte` bleiben bei Deutsch unverändert; englisch `en-GB`. Das Format `Thu 30 Oct` (`fmtDate`) wird dort nicht erzwungen, um die deutsche Ausgabe byte-gleich zu halten.
- **A3 (Annahme):** Die untere Navigation „Übersicht" heißt englisch „Overview"; „Cockpit" (Glossar: dashboard) steht dort nicht.
- Texte, die identisch im Trip- und Ortsvergleich-Editor stehen („Speichern", „Abbrechen"), liegen hier unter `konto.aktion.*`; das Schlüssel-Umbenennen entfällt im Epic, die Zusammenführung ist ein Nebenbefund nach F10.
- Der Sprach-Auswahl-Baustein stammt aus S3 und wird hier nicht verändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Konto und Navigation folgen der Nutzersprache aus einem Katalog je Bereich, Eigennamen bleiben unübersetzt.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
