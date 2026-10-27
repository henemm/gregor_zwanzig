# ADR-0067: Eine E-Mail-Adresse gehört höchstens einem Konto — alle Schreibwege prüfen unter einer Sperre je Adresse, Google-Login verknüpft statt ein Doppelkonto anzulegen

- **Status:** Akzeptiert (PO-Freigabe 2026-09-15 zur Spec `google_login_adress_verknuepfung.md`)
- **Datum:** 2026-09-15
- **Bezug:** GitHub-Issue #2147 (Epic #2138 Multi-User), Scheiben A/B1/B2/C mit den Specs
  `docs/specs/modules/magic_link_adress_eindeutigkeit.md` (A),
  `docs/specs/modules/adress_eindeutigkeit_schreibpfade.md` (B1),
  `docs/specs/modules/adresswechsel_nach_bestaetigung.md` (B2),
  `docs/specs/modules/google_login_adress_verknuepfung.md` (C); schreibt
  [ADR-0066](0066-login-erfordert-bestaetigte-email-adresse.md) fort und löst die Aussage
  „kein Account-Linking in v1" aus `docs/specs/modules/google_oauth_login.md` ab.

## Kontext

Die E-Mail-Adresse ist in einem Mehrnutzer-Produkt mehr als ein Kontaktfeld: Magic-Link und
Google-Login beweisen den Besitz einer Adresse und ordnen daraus ein Konto zu, Passwort-Reset und
Bestätigungsmail gehen an sie. Vor #2147 konnte dieselbe Adresse von mehreren Konten gehalten
werden — über Registrierung, Profiländerung, Magic-Link und Google-Login gleichermaßen. Welches
Konto ein Adressnachweis dann öffnet, war Zufall der Dateireihenfolge; ein Google-Login mit der
Adresse eines bestehenden Passwort-Kontos legte stillschweigend ein zweites Konto an.

## Entscheidung

1. **Eine Adresse gehört höchstens einem echten Konto.** „Halten" heißt: die normalisierte
   Adresse (`NormalizeEmailAddress`: Trim + Kleinschreibung) steht in `email` **oder** `mail_to`
   (kreuzweise). Testkonten zählen nicht. Bestätigter Inhaber ist ein Konto mit
   `EmailVerifiedAt` **und** der Adresse als wirksamer Kontaktadresse (`mail_to`, Rückfall
   `email`).
2. **Alle Schreibwege prüfen unter einer Sperre je normalisierter Adresse**
   (`store.LockEmailAddress`): Adresse auflösen und Konto anlegen/ändern geschieht atomar.
   Magic-Link (A), Registrierung und Profil (B1), Adresswechsel mit Bestätigung (B2) und
   Google-Login (C) teilen dieselbe Sperre und dieselbe Zuordnung (`ResolveAddressOwner`,
   `IsAddressTakenByOtherAccount`). Ein Lesefehler beim Scan lehnt ab (fail-closed).
3. **Ein Adresswechsel wird erst mit Bestätigung wirksam (B2).** Die neue Adresse steht bis dahin
   nur als ausstehende Adresse (`PendingContactAddress`) und gilt für andere Wege als frei.
4. **Google-Login verknüpft statt ein Doppelkonto anzulegen (C).** Für einen unbekannten
   Google-`sub` mit von Google bestätigter Adresse:
   - freie Adresse → Neukonto mit normalisierter Adresse (Double-Opt-In nach ADR-0066);
   - bestätigter Inhaber ohne Google-Identität → Verknüpfung (`OAuthProvider`/`OAuthSub`),
     Bestätigung und Sitzungen unverändert, Hinweis-Mail ohne Link an die wirksame Adresse;
   - unbestätigtes, zugangsloses Konto → Übernahme wie beim Magic-Link (bestätigen, verknüpfen,
     alte Sitzungen beenden, keine Mail);
   - bestätigter Inhaber mit anderer Google-Identität, unbestätigtes Konto mit Zugangsdaten,
     Adresse nur im Nebenfeld oder mehrere Inhaber → Ablehnung `oauth_link_failed`, nichts
     geschrieben.
   `email_verified=false` wird **vor** jeder Adressprüfung mit `oauth_failed` abgelehnt — für
   freie und belegte Adressen gleich, damit der Antwortcode nichts über die Adresse verrät.
5. **Logs nennen weder Adresse noch Kontokennung** in Zuordnungs-, Ablehnungs- und
   Verknüpfungspfaden; Versandfehler werden nie roh protokolliert (SMTP-Fehler nennen den
   Empfänger).
6. **Bestandsduplikate werden gemessen, nicht aufgelöst.** Ein Kollisionszähler
   (`Store.LogAddressCollisions`) protokolliert beim Serverstart nur Zahlen (betroffene Adressen,
   betroffene Konten), fail-soft.

## Verworfene Alternativen

- **Weiterhin getrennte Konten bei gleicher Adresse** („kein Account-Linking in v1") — macht jede
  adressbasierte Zuordnung mehrdeutig und legt Nutzern unbemerkt ein zweites, leeres Konto an.
- **Google-Login bei belegter Adresse pauschal ablehnen** — sperrt den rechtmäßigen Inhaber eines
  bestätigten Kontos vom Google-Weg aus, obwohl Google denselben Adressbesitz nachweist, den ein
  Magic-Link auch nachweist.
- **Verknüpfung auch mit unbestätigten Konten, die Zugangsdaten haben** — wer eine fremde Adresse
  registriert und ein Passwort setzt, bekäme so beim Login des echten Adressinhabers dessen
  Google-Identität an sein Konto gehängt.
- **Eindeutigkeit per Index-Datei statt Scan** — größerer Umbau der dateibasierten Persistenz; bei
  der heutigen Kontozahl ist der Scan unter der Sperre ausreichend.

## Konsequenzen

- **Positiv:** Ein Adressnachweis öffnet genau ein Konto oder keines. Alle Wege teilen eine Sperre
  und eine Zuordnungsfunktion; die Zusicherungen sind an einer Stelle prüfbar.
- **Akzeptierte Restlücken:**
  - Ein Google-Workspace-Administrator kann `email_verified=true` für Domain-Adressen ausstellen,
    die er nicht selbst besitzt. Gleiche Risikoklasse wie der bisherige Neuanlagepfad.
  - Bestandsduplikate aus der Zeit vor #2147 bleiben bestehen und werden nur gezählt; eine
    Auflösung ist eigenes Folge-Ticket, falls die Zahl größer als null ist.
  - Aus B2 (LOW, Sammel-Issue #1199): Magic-Link sieht eine ausstehende Adresse
    (`PendingContactAddress`) nicht; die Meldung `token expired` ist ein schwacher Seitenkanal.
- **Folgepflichten:**
  - Jeder neue Weg, der eine Adresse schreibt oder aus einer Adresse ein Konto ableitet, nutzt
    `LockEmailAddress` und die gemeinsame Zuordnung — kein eigener Scan.
  - Ein Test eines solchen Wegs läuft mit zwei Konten und mindestens einem Parallelfall.
