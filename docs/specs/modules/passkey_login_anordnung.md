---
entity_id: passkey_login_anordnung
type: module
created: 2026-09-11
updated: 2026-09-11
status: draft
version: "1.0"
tags: [sveltekit, auth, webauthn, passkey, login, mobile]
---

<!-- Issue #2247 — Scheibe 2 von #2199 (Epic „Passkey-UI wieder sichtbar machen"), Scheibe 1 (#2246) ist geliefert -->

# Passkey-Login-Anordnung

## Approval

- [ ] Approved

## Purpose

Auf der Anmeldeseite entsteht ein Passkey-Weg neben Passwort, Google und Magic-Link. Auf dem
Handy steht er als erster sichtbarer Anmeldeweg oben, auf dem Desktop bleibt die heutige
Anordnung erhalten und der Passkey-Weg sitzt unterhalb des Passwort-Formulars. Diese Scheibe
existiert, weil der Passkey-Login-Baustein (`frontend/src/lib/passkey.ts`) seit seiner
Einführung technisch fertig, aber auf der Anmeldeseite **nirgends verdrahtet** ist — heute
kommt dort kein einziges Wort „passkey" vor. Ohne diese Scheibe kann niemand sich per Passkey
anmelden, obwohl Scheibe 1 (#2246) das Anlegen von Passkeys bereits ermöglicht.

## Source

- **File:** `frontend/src/routes/login/+page.svelte` — einzige Produktivdatei mit
  Kern-Änderung, 120 Zeilen, heutige Blockfolge: Passwort-Formular (Zeilen 59–90),
  Google-Anmeldung (91–106), Fusslinks (108–118)
- **Identifier:** neuer Passkey-Block, eingefügt vor das Passwort-Formular, mit
  `desktop:order-*`-Klassen zur Umsortierung auf großen Bildschirmen

### Weitere betroffene Dateien

- **File:** `frontend/src/routes/login/__tests__/login_erstes_bild.test.ts` (CREATE) — prüft
  die vom Server ausgelieferte Seite direkt, ohne Browser; das ist der tragende Wächter dieser
  Scheibe
- **File:** `frontend/src/routes/login/__tests__/app-stores-stub-hooks.mjs` (CREATE) —
  eigene, lokale Hilfsdatei für den Test oben. Bewusst **nicht** in die geteilte Hook-Datei
  eingefügt, von der andere, heute grüne Tests abhängen — eine Änderung dort hätte fremde
  Tests mit betroffen
- **File:** `frontend/e2e/passkey-login.spec.ts` (CREATE) — Nachweis im echten Browser:
  Anmeldung am echten Knopf, Positionsvergleich Handy/Desktop, Höhengleichheit, Abbruch
- **File:** `frontend/e2e/run-passkey-login.sh` (CREATE) — eigener, rücksichtsvoller
  Testlauf, der das geteilte Anfrage-Kontingent der Passkey-Routen nicht sprengt (siehe
  Rate-Limit-Abschnitt unten)

> **Schicht-Hinweis:** Diese Scheibe ist **ausschließlich Frontend-Arbeit**
> (`frontend/src/...`, SvelteKit). Es wird **kein** Go-Code (`internal/`, `cmd/`) und **kein**
> Python-Code (`api/`, `src/`) geändert — alle benötigten Endpunkte und der Client-Baustein
> `frontend/src/lib/passkey.ts` existieren bereits. Der Anmeldemechanismus selbst bleibt
> unverändert; diese Scheibe verdrahtet ihn nur erstmals auf der Anmeldeseite.

## Estimated Scope

- **LoC:** ~95–110 Produktiv-LoC, ~280 Test-LoC, gesamt ~390 von 500 (das
  Standard-Workflow-Limit liegt bei 250 und braucht hier einen dokumentierten Override)
- **Files:** 1 MODIFY (`login/+page.svelte`), 4 CREATE (zwei Tests, eine Test-Hilfsdatei, ein
  Lauf-Skript)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/passkey.ts` | Frontend-Modul (bereits vorhanden) | Stellt `isWebAuthnSupported()`, `loginWithPasskey(username)` und `loginWithDiscoverablePasskey(signal?)` bereit; alle drei haben heute keinen einzigen Aufrufer im Login-Pfad |
| `POST /api/auth/passkey/login/{begin,finish}` und `/discoverable/{begin,finish}` | Go-API-Endpunkte (bereits vorhanden) | Zeremonie-Endpunkte für die Anmeldung, hinter `passkey.ts` verborgen |
| `frontend/src/app.css` (`mobile:`/`desktop:`-Varianten) | Bestehende CSS-Infrastruktur | Wird für die Umsortierung genutzt, bleibt selbst unverändert |
| Passkey-Rate-Limiter (`internal/router/router.go:97`) | Bestehende Infrastruktur | Gemeinsamer Eimer für alle Passkey-Routen; bei Testläufen zu beachten (kein Änderungsbedarf dieser Scheibe, nur Nachweis-Risiko) |
| Scheibe 1 (#2246, geliefert) | Fachliche Voraussetzung | Liefert den einzigen Weg, überhaupt einen Passkey anzulegen — ohne sie gäbe es nichts anzumelden |

## Implementation Details

**Anordnung.** Der Passkey-Block steht im HTML **zuerst**, vor dem Passwort-Formular.
`desktop:order-*`-Klassen schieben ihn auf großen Bildschirmen unter das Formular; auf dem
Handy bleibt die HTML-Reihenfolge unverändert die sichtbare Reihenfolge. Der umgebende
Container wechselt von `space-y-6` auf `flex flex-col gap-6` — `space-y-*` hängt den Abstand
an alle Geschwisterelemente außer dem ersten, das würde nach der Umsortierung am falschen
Element sitzen. Innerhalb des Passwort-Formulars bleibt `space-y-4` unverändert, dort sortiert
nichts um.

**Kein Nachlade-Sprung.** Der Passkey-Block wird **immer serverseitig mitgerendert**, nicht
erst nachträglich vom Browser eingefügt. Damit ist der reservierte Platz von Anfang an der
tatsächliche Knopf und kann nicht von dessen echter Höhe abweichen. Die Fähigkeitsprüfung im
Browser tauscht danach nur noch den **Inhalt** dieses bereits vorhandenen Platzes aus, statt
etwas nachträglich einzufügen. Das kehrt die Fähigkeitsprüfung gegenüber Scheibe 1 (#2246) um:
dort bedeutet „noch nicht gemessen" nichts anzuzeigen, hier bedeutet „noch nicht gemessen"
(und ebenso „Gerät kann WebAuthn") den Passkey-Knopf zu zeigen; erst wenn feststeht, dass das
Gerät kein WebAuthn kann, wechselt die Anzeige auf den Hinweistext.

**Knopf bei leerem Benutzernamen bleibt bedienbar.** Er wird nicht deaktiviert — ein
deaktivierter Knopf ist nicht per Tastatur erreichbar und wäre als erstes Element auf dem
Handy ein toter Auftakt. Ein Klick bei leerem Feld setzt stattdessen den Fokus auf das
Benutzernamen-Feld. Dieser Klick darf die im Hintergrund laufende Autofill-Anbindung
(Conditional UI) nicht abbrechen und neu starten — ein Abbruch verbraucht zusätzliche Anfragen
aus dem geteilten Passkey-Kontingent und würde genau den Weg beschädigen, für den der Knopf
hier nur ein Notausgang ist.

**Hinweistext ohne WebAuthn.** Kein knopfförmiges Element, sondern ein kurzer erklärender
Text. Damit der Inhaltstausch nichts verschiebt, hat der Bereich in allen drei Zuständen
dieselbe Höhe — erzwungen durch einen festen Container statt durch „Text kurz halten".

**Autofill-Anbindung am Benutzernamen-Feld.** Das Feld trägt `autocomplete="username webauthn"`
(so bereits in `c09172f5`). Erst dieses Attribut erlaubt dem Browser, den Passkey als Vorschlag
im Eingabefeld anzubieten — es ist die eigentliche Verdrahtung des „ohne Tippen"-Weges, der
Knopf bleibt der manuelle Notausgang. Die Anbindung startet nur, wenn
`PublicKeyCredential.isConditionalMediationAvailable()` sie meldet; diese Prüfung läuft rein im
Browser und verbraucht kein Kontingent.

**Deutscher Fehlertext für den Fehlschlag.** Der gesamte geräteseitige Fehlschlag-Fall —
Abbruch, Zeitüberschreitung und „kein passender Passkey" — bekommt **einen** verständlichen
deutschen Text. Getrennte Texte für Abbruch und Zeitüberschreitung sind strukturell
unmöglich, siehe den entsprechenden Punkt unter „Known Limitations"; der `TimeoutError`-Zweig
der Vorlage in `c09172f5` war aus demselben Grund toter Code. Serverseitige Fehlschläge
bleiben davon unberührt und dürfen eigene Texte haben. Übersetzungsmuster:
`account/+page.svelte:232-238`. `passkey.ts` selbst wirft nur technische Codes; die
Übersetzung ist Aufgabe der Anmeldeseite.

**Verworfen: eigene Komponente.** Naheliegend, um den Block isoliert testbar zu machen — aber
der serverseitige Test kann die Anmeldeseite direkt rendern. Eine ausgelagerte Komponente wäre
ein Stellvertreter: geprüft würde dann nicht mehr das tatsächlich ausgelieferte Artefakt,
sondern nur ein Baustein davon. Die Seite direkt zu rendern ist die schärfere Messung und
spart eine zusätzliche Datei.

**Abgelöste Vorgänger-Beschreibung.** `docs/specs/modules/passkey_webauthn.md` beschreibt die
Anmeldeseite noch in ihrer alten Anordnung (Knopf unterhalb des Formulars, hinter einem
„oder"-Trenner). Diese Scheibe ersetzt diese Beschreibung durch die oben genannte
bildschirmabhängige Anordnung — der Anmeldemechanismus selbst (welcher Endpunkt wann
aufgerufen wird) ändert sich dabei nicht.

## Rate-Limit-Abschnitt

Das Issue stellt die Rate-Limit-Frage ausdrücklich als zu klärenden Punkt. Antwort:

1. Abgebrochene Anmeldeversuche zählen trotzdem gegen das Kontingent — der Verbrauch entsteht
   bereits beim Start der Zeremonie, unabhängig vom Ausgang.
2. Das Kontingent ist zahlenmäßig genauso groß wie beim Passwort-Login, wird aber schneller
   verbraucht: eine vollständige Passkey-Anmeldung braucht zwei Anfragen (Beginn und Abschluss
   der Zeremonie), eine Passwort-Anmeldung nur eine.
3. Es ist keine starre Stundensperre, sondern füllt sich laufend langsam wieder auf — wer sich
   leerläuft, wartet Minuten, nicht eine volle Stunde.
4. Schärfer als erwartet: Allein der Aufruf der Anmeldeseite kann bereits ein Kontingent-Token
   verbrauchen, weil die Autofill-Anbindung im Hintergrund automatisch eine Anfrage startet.
   Ein Testlauf, der mehrfach hintereinander die volle Zeremonie durchspielt, stößt dadurch
   real an das Limit (`internal/router/router.go:97`, Mechanik `internal/middleware/ratelimit.go:75`)
   — deshalb der eigene, rücksichtsvolle Lauf in `run-passkey-login.sh` statt eines einzigen
   durchgehenden Testlaufs.

## Expected Behavior

- **Input:** Seitenaufruf `/login` auf 375 px (Handy) und auf 1280 px (Desktop) breiten
  Bildschirmen; Klick auf den Passkey-Knopf; Klick auf den Knopf bei leerem
  Benutzernamen-Feld; Abbruch der Passkey-Zeremonie am Gerät.
- **Output:** Auf dem Handy erscheint der Passkey-Weg oberhalb, auf dem Desktop unterhalb des
  Passwort-Formulars — beides bereits in der vom Server ausgelieferten Seite, ohne
  sichtbaren Sprung beim Nachladen. Passwort, Google und Magic-Link bleiben auf beiden
  Bildschirmgrößen ohne Scrollen erreichbar. Bei einem Gerät ohne WebAuthn-Unterstützung
  erscheint an der Stelle des Knopfs ein deutscher Hinweistext, gleich hoch wie der Knopf. Bei
  Abbruch der Zeremonie erscheint eine deutsche Fehlermeldung, der Passwort-Weg bleibt sofort
  bedienbar.
- **Side effects:** Eine vollständige Passkey-Anmeldung löst zwei Anfragen an den geteilten
  Passkey-Rate-Limiter aus (Beginn und Abschluss der Zeremonie), gegenüber einer Anfrage bei
  einer Passwort-Anmeldung. Schon der bloße Aufruf der Anmeldeseite kann über die im
  Hintergrund laufende Autofill-Anbindung ein weiteres Token aus demselben Kontingent ziehen.
  Kein neuer Netzwerk-Aufruf entsteht durch die reine Anzeige des Passkey-Blocks selbst.

## Acceptance Criteria

- **AC-1:** Given ein Bildschirm mit 375 Pixel Breite (Handy) / When die Anmeldeseite
  geladen ist / Then steht der Passkey-Weg an seiner tatsächlichen Bildschirmposition oberhalb
  des Passwort-Formulars
  - Test: `frontend/e2e/passkey-login.spec.ts` → AC-1: Positionsvergleich bei 375 px, Passkey-Block liegt oberhalb des Formulars

- **AC-2:** Given ein Bildschirm mit 1280 Pixel Breite (Desktop) / When die Anmeldeseite
  geladen ist / Then steht der Passkey-Weg an seiner tatsächlichen Bildschirmposition
  unterhalb des Passwort-Formulars
  - Test: `frontend/e2e/passkey-login.spec.ts` → AC-2: Positionsvergleich bei 1280 px, Passkey-Block liegt unterhalb des Formulars

- **AC-3:** Given ein Nutzer ruft die Anmeldeseite auf / When die Seite vom Server
  ausgeliefert wird, noch bevor der Browser irgendetwas ausgeführt hat / Then enthält diese
  ausgelieferte Seite den Passkey-Knopf bereits
  - Test: `frontend/src/routes/login/__tests__/login_erstes_bild.test.ts` → AC-3: die vom Server erzeugte Seite enthält den Passkey-Knopf ohne Browser-Ausführung

- **AC-4:** Given zwei Geräte, eines mit und eines ohne WebAuthn-Fähigkeit / When beide die
  Anmeldeseite laden / Then zeigt nur das fähige Gerät den Passkey-Knopf, beim unfähigen
  Gerät fehlt er — beide Fälle werden geprüft, nicht nur einer
  - Test: **Positiv-Zweig** `frontend/src/routes/login/__tests__/login_erstes_bild.test.ts` (Knopf ist in der Server-Auslieferung vorhanden — fällt rot, sobald jemand ihn wieder erst im Browser entstehen liesse). **Negativ-Zweig** `frontend/e2e/passkey-login.spec.ts` (Fähigkeit vor dem Laden real entfernt ⇒ kein Knopf). Bewusst getrennt: serverseitig existiert `window` nie, ein dort geprüfter Negativ-Zweig stellte sich von selbst ein und bewachte nichts. Ein nur zum Testen eingebauter Einspeisepunkt auf der Produktivseite wäre derselbe Stellvertreter-Fehler, den diese Spec bei der Komponenten-Auslagerung schon ablehnt.

- **AC-5:** Given ein Gerät ohne WebAuthn-Unterstützung / When die Anmeldeseite geladen ist /
  Then fehlt der Passkey-Knopf, an seiner Stelle steht ein deutscher Hinweistext, und der
  Passwort-Weg bleibt sichtbar und bedienbar
  - Test: `frontend/e2e/passkey-login.spec.ts` → AC-5: ohne WebAuthn-Fähigkeit erscheint Hinweistext statt Knopf, Passwort-Weg bleibt bedienbar

- **AC-6:** Given die drei möglichen Zustände des Passkey-Bereichs (Fähigkeit noch nicht
  geprüft, Gerät fähig, Gerät nicht fähig) / When zwischen ihnen gewechselt wird / Then bleibt
  der Passkey-Bereich in allen drei Zuständen gleich hoch, sodass nichts auf der Seite
  verrutscht
  - Test: `frontend/e2e/passkey-login.spec.ts` → AC-6: Höhenvergleich des Passkey-Bereichs in allen drei Zuständen, erzwungen durch Entfernen der WebAuthn-Fähigkeit vor dem Laden

- **AC-7:** Given ein Nutzer mit angelegtem Passkey / When er auf den Passkey-Knopf klickt
  und die Anmeldung an einem (virtuellen) Authentifikator bestätigt / Then ist er
  angemeldet, ohne an irgendeiner Stelle ein Passwort eingegeben zu haben
  - Test: `frontend/e2e/passkey-login.spec.ts` → AC-7: Anmeldung am echten Passkey-Knopf über virtuellen Authentifikator, ohne Passworteingabe

- **AC-8:** Given die Anmeldeseite auf 375 px und auf 1280 px Breite / When sie geladen ist /
  Then sind Passwort-Weg, Google-Anmeldung und Magic-Link auf beiden Bildschirmgrößen ohne
  Scrollen erreichbar, nicht nur irgendwo im Dokument vorhanden
  - Test: `frontend/e2e/passkey-login.spec.ts` → AC-8: Bildschirmposition von Passwort, Google und Magic-Link wird gegen die Höhe des sichtbaren Bereichs gemessen, auf beiden Breiten

- **AC-9:** Given ein Nutzer startet die Passkey-Anmeldung / When die Zeremonie am Gerät
  fehlschlägt — gleich ob er sie abbricht, ob sie in eine Zeitüberschreitung läuft oder ob
  kein passender Passkey gefunden wird / Then erscheint eine verständliche deutsche
  Fehlermeldung, und der Passwort-Weg ist sofort weiter bedienbar
  - Test: `frontend/e2e/passkey-login.spec.ts` → AC-9: zwei verschiedene reale Fehlschlag-Wege (Authentifikator entfernt · Präsenzbestätigung aus mit gekürzter Frist) führen beide zu einer deutschen Fehlermeldung, Passwort-Weg bleibt sofort bedienbar

- **AC-10:** Given das Benutzernamen-Feld ist leer / When der Nutzer auf den Passkey-Knopf
  klickt / Then ist der Knopf nicht deaktiviert, der Fokus springt auf das
  Benutzernamen-Feld, und die im Hintergrund laufende Anmeldung per Autofill-Vorschlag bleibt
  danach weiterhin nutzbar
  - Test: `frontend/e2e/passkey-login.spec.ts` → AC-10: Klick bei leerem Feld fokussiert das Benutzernamen-Feld und unterbricht die Autofill-Anmeldung nicht

- **AC-11:** Given ein Nutzer tippt in das Benutzernamen-Feld der Anmeldeseite / When sein
  Browser Passkey-Vorschläge im Eingabefeld beherrscht / Then ist das Feld so ausgezeichnet,
  dass der Browser den hinterlegten Passkey dort als Vorschlag anbieten darf — ohne dass der
  Nutzer den Passkey-Knopf benutzen muss
  - Test: `frontend/src/routes/login/__tests__/login_erstes_bild.test.ts` → AC-11: die vom Server erzeugte Seite zeichnet das Benutzernamen-Feld mit `autocomplete="username webauthn"` aus

## Known Limitations

- **Kurzes Aufblitzen auf Geräten ohne WebAuthn.** Weil der Knopf bis zum Abschluss der
  Fähigkeitsprüfung immer mitgerendert wird, ist er auf Geräten ohne WebAuthn-Unterstützung
  kurz sichtbar, bevor er zum Hinweistext wechselt. Betroffen sind praktisch nur seltene
  In-App-Browser und alte Android-Firefox-Versionen; ein Klick vor Abschluss der Prüfung löst
  ohnehin noch nichts aus.
- **Die Fokusreihenfolge weicht auf dem Desktop von der sichtbaren Reihenfolge ab**
  (betrifft die Barrierefreiheits-Richtlinie WCAG 2.4.3, Focus Order). Eine einzige
  Dokumentreihenfolge kann nicht zwei unterschiedliche Bildschirmreihenfolgen gleichzeitig
  bedienen; die Umsortierung per CSS ändert nur die sichtbare, nicht die Tab-Reihenfolge.
  Diese Abweichung ist unvermeidbar und wird bewusst auf die Desktop-Seite gelegt — auf dem
  Handy, dem eigentlichen Ziel dieser Scheibe, stimmen Fokus- und Sichtreihenfolge überein.
- **Der zusätzliche Sprungfühler steht unter Vorbehalt.** Ein technischer Zusatz-Nachweis, der
  die erste sichtbare Bildposition gegen den Ruhezustand vergleicht, wird nur eingebaut, wenn
  er sich zuvor an einer bewusst fehlerhaften Vergleichsseite als wirksam erweist. Schlägt
  diese Vorprüfung fehl, entfällt der Zusatz-Nachweis ersatzlos — die Höhengleichheit aus AC-6
  und der serverseitige Nachweis aus AC-3/AC-4 tragen dann allein.

- **🔴 Abbruch und Zeitüberschreitung lassen sich nicht auseinanderhalten — das ist so
  gewollt.** Das Issue fordert getrennte deutsche Texte für beide Fälle. WebAuthn meldet beide
  Fälle jedoch absichtlich als denselben Fehler (`NotAllowedError`), damit eine Webseite nicht
  herausfinden kann, ob ein Nutzer abgelehnt hat oder ob überhaupt kein passender Passkey
  vorhanden war. Die Anmeldeseite kann also gar nicht unterscheiden, was passiert ist. Der
  entsprechende Zweig im alten Stand (`c09172f5`) war aus demselben Grund toter Code — passend
  zu dessen Commit-Botschaft „nie getestet, nie funktioniert". AC-9 verlangt deshalb eine
  verständliche Meldung für den gesamten Fehlschlag-Fall statt zweier getrennter.
- **Kontingent-Erschöpfung wird als „kein passender Passkey" angezeigt.** `passkey.ts` wirft
  bei jeder abschlägigen Server-Antwort denselben technischen Code, auch bei HTTP 429. Wer das
  geteilte Passkey-Kontingent leergelaufen hat, liest deshalb eine irreführende Meldung. Das
  ist **Bestandsverhalten**, nicht von dieser Scheibe eingeführt, und liegt ausserhalb ihres
  Umfangs — als Nebenbefund notiert.
- **Der Autofill-Vorschlag selbst ist nicht automatisch prüfbar.** AC-11 bewacht, dass das
  Eingabefeld korrekt ausgezeichnet ist — also den Draht. Ob der Browser den Passkey dort
  tatsächlich als Vorschlag einblendet, entscheidet er selbst und lässt sich weder mit einem
  virtuellen Authentifikator noch sonst verlässlich automatisiert auslösen. Diese letzte Strecke
  bleibt manuellem Ausprobieren auf einem echten Gerät vorbehalten; die Spec behauptet sie
  nicht als bewiesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe ändert weder den Anmeldemechanismus noch das Datenmodell noch
  einen Endpunkt — sie verdrahtet ausschließlich bereits fertige, dokumentierte Bausteine
  (`frontend/src/lib/passkey.ts`, bestehende Go-Endpunkte, bestehende CSS-Infrastruktur für
  Bildschirmgrößen) auf der Anmeldeseite. Sie löst dabei die in
  `docs/specs/modules/passkey_webauthn.md` beschriebene alte Anordnung (Knopf unterhalb,
  hinter einem „oder"-Trenner) durch die hier festgelegte bildschirmabhängige Anordnung ab —
  das ist eine Layout-, keine Architekturentscheidung und rechtfertigt kein eigenes ADR.

## Changelog

- 2026-09-11: Initial spec created — Scheibe 2 von #2199, Issue #2247
