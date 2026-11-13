# ADR-0115: Kontoänderungen — frischer Nachweis je Sitzung, Hinweis-Mails, Reset entfernt andere Zugangswege, unbestätigte Anmeldungen werden ersetzt und geräumt, Sicherheitsfelder nur frisch geladen

- **Status:** Akzeptiert (PO-Auftrag 2026-11-12: alle Befunde des Sicherheits-Reviews ohne Rückfrage beheben)
- **Datum:** 2026-11-13
- **Bezug:** GitHub-Issue #2961 (Paket GO-AUTH, Befunde GA2, GA3, GA6, GA9), Spec
  `docs/specs/modules/security_haertung_2026_11_kontoaenderungen.md`; ergänzt
  [ADR-0081](0081-reauth-vor-kontoloeschung.md) (Nachweis-Baustein),
  [ADR-0067](0067-adress-eindeutigkeit.md) (Adress-Eindeutigkeit bei unbestätigten Konten),
  [ADR-0105](0105-email-als-login-identifier.md) (Änderung der Login-Kennung),
  [ADR-0060](0060-dauerhafte-anmeldung-mit-widerrufsliste.md) (Sitzungen),
  [ADR-0066](0066-login-erfordert-bestaetigte-email-adresse.md) (Bestätigungspflicht)
- **Ergänzt durch:** —

## Kontext

Das Sicherheits-Review 2026-11 fand im Bereich Kontoverwaltung vier zusammenhängende Schwächen:

- **Sitzung → dauerhafte Übernahme (GA3).** Wer eine Sitzung erbeutet (offenes Gerät, gestohlenes
  Cookie), konnte ohne weiteren Nachweis die wirksame Mailadresse ändern und einen eigenen Passkey
  hinzufügen. Die alte Adresse erfuhr davon nichts. Ein Passwort-Reset und „Auf allen Geräten
  abmelden“ beendeten nur Sitzungen; ein eingeschleuster Passkey oder eine Google-Verknüpfung blieb.
- **Vorab angelegte Konten (GA2).** Eine Registrierung mit einer fremden Adresse hielt diese
  Adresse fest („Adresse vergeben“), auch ohne Bestätigung, und hinterlegte Zugangsdaten für das
  Konto, das der echte Inhaber später übernehmen würde.
- **Verlorene Schreibvorgänge (GA6).** Die meisten Schreiber laden `user.json`, ändern ein Feld und
  schreiben das ganze Objekt zurück. Ein parallel laufender Profil-Schreiber konnte so einen eben
  gesetzten Passwort-Hash, eine Admin-Sperre oder entfernte Passkeys wieder zurücksetzen.
- **Login-Kennung ohne Nachweis (GA9).** War `mail_to` gesetzt, wurde eine neue Login-Kennung
  (`email`) sofort geschrieben, ohne dass die neue Adresse bewiesen war.

## Entscheidung

1. **Frischer Nachweis vor sicherheitsrelevanten Kontoänderungen (ergänzt ADR-0081).**
   Wechsel von `mail_to` oder `email`, Passkey hinzufügen und Passkey entfernen verlangen einen
   Nachweis: das aktuelle Passwort ODER einen Code, der an die bisherige wirksame Adresse geht.
   Der Code-Baustein der Kontolöschung ist verallgemeinert (eigener Store und eigene Mail je
   Zweck; ein Lösch-Code ist kein Nachweis-Code). Ohne Nachweis antwortet der Server
   `403 reauth_required`. Ein Nachweis gilt **10 Minuten für genau diese Sitzung dieses Nutzers**;
   eine frisch ausgestellte Sitzung (Anmeldung, Passwortwechsel) trägt ihn bereits, weil die
   Anmeldung selbst ein gleichwertiger Nachweis ist. Die Sperre sitzt als Hülle an den Routen
   (Profil-PUT nur bei tatsächlicher Adressänderung). Die Konto-Seite öffnet bei
   `reauth_required` den Dialog der Kontolöschung im Nachweis-Modus und wiederholt danach die
   Änderung.
2. **Google-Verknüpfung.** Eine sitzungsgebundene Verknüpfen-/Lösen-Funktion gibt es nicht. Die
   Verknüpfung entsteht nur beim Google-Login, wenn Google dieselbe bestätigte Adresse nachweist
   (gleichwertig zu einem Code an die Adresse, ADR-0067), und meldet sich per Hinweis-Mail.
   Gelöst wird sie über den Passwort-Reset (Punkt 4). Wer künftig eine sitzungsgebundene
   Verknüpfen-/Lösen-Funktion baut, hängt sie hinter denselben Nachweis.
3. **Hinweis-Mails.** Schon das Anstoßen eines Adress- oder Kennungswechsels meldet sich an die
   bisherige bestätigte Adresse; ein wirksam gewordener Wechsel meldet sich dort erneut
   (jeweils mit der neuen Adresse im Text); Passkey hinzugefügt/entfernt,
   Passwort geändert/zurückgesetzt und Google verknüpft an die aktuelle bestätigte Adresse.
   Unbestätigte Konten bekommen keine. Texte über den Katalog (DE/EN), Versand über den engen
   Go-Mailweg mit Empfängerschutz (ADR-0087), fail-soft, höchstens 5 je Nutzer und Stunde.
4. **Passwort-Reset entfernt auf Wunsch alle anderen Zugangswege.** Die Reset-Seite bietet
   „Alle anderen Zugangswege entfernen (Passkeys, Google-Verknüpfung)“, standardmäßig aktiv
   (die API nimmt `remove_other_access` mit Vorgabe `true`). Bei einem unbestätigten Konto
   werden sie immer entfernt. Sitzungen werden wie bisher geleert. „Auf allen Geräten
   abmelden“ bleibt eine reine Sitzungsaktion; die Konto-Seite zeigt dabei die Zahl der weiter
   gültigen Passkeys mit Sprung zur Passkey-Verwaltung.
5. **Unbestätigte Anmeldungen (ergänzt ADR-0067 und ADR-0066).** Als unbestätigte Anmeldung
   gilt ein Konto ohne bestätigte Adresse, kein Testkonto, ohne ausstehende Adressänderung,
   angelegt ab Einführung der Bestätigungspflicht (2026-09-12) und mit Bestätigungstoken. Im
   Zweifel nicht. Behandelt wird sie zudem nur, wenn ihr Kontoordner **keine Nutzinhalte** hat
   (Positivliste: `user.json`, `sessions.json`, `email_verification.json`,
   `password_reset.json`, leere `locations/`, `gpx/`, `weather_snapshots/`; alles andere heißt
   „nicht leer“). Bestandsdaten bleiben erhalten (#102): ein solcher Ordner wird **nie gelöscht**,
   sondern per Rename nach `<Datenwurzel>/.entfernt-unbestaetigt/<kennung>-<UTC-Zeitstempel>/`
   verschoben (außerhalb von `users/`, kein Loader sieht ihn) und erst nach 30 Tagen vom Reaper
   endgültig entfernt; Zurückholen = Ordner zurückschieben (Playbook, Betriebs-Backup).
   - Eine Registrierung (Passwort oder öffentlicher Passkey) für eine Adresse, die nur solche
     Konten halten, **ersetzt** sie (Kontoordner samt Zugangsdaten und Passkeys in die Ablage
     verschoben; neues Konto mit neuem Bestätigungstoken). „Adresse vergeben“ gilt weiter, wenn
     ein anderes Konto oder eine Anmeldung mit Nutzinhalten die Adresse hält. Damit gilt die
     Eindeutigkeit aus ADR-0067 unverändert: auch danach hält genau ein Konto die Adresse.
   - Der vorhandene Store-Reaper verschiebt höchstens stündlich unbestätigte Anmeldungen, deren
     Token seit mehr als 24 Stunden abgelaufen ist, in die Ablage; eine Anmeldung mit
     Nutzinhalten bleibt mit Warn-Logzeile (maskierte Kennung) stehen. Bestandskonten von vor
     der Bestätigungspflicht (Nachtrag #2304), Testkonten und Konten ohne Token bleiben.
   - Die Bestätigungsmail sagt ausdrücklich, dass sie zu ignorieren ist, wer sich nicht selbst
     registriert hat.
6. **Login-Kennung nur mit Bestätigung (ergänzt ADR-0105).** Eine neue `email` eines
   bestätigten Kontos wird erst mit dem Bestätigungslink an die neue Adresse wirksam, auch wenn
   `mail_to` gleich bleibt. Die ausstehende Adresse blockiert keine fremde Registrierung.
   Ändern sich `email` und `mail_to` zugleich, wartet nur `mail_to`.
7. **Sicherheitsfelder nur frisch geladen (GA6).** Alle Lesen-Ändern-Schreiben-Wege auf
   `user.json` laufen unter einer Sperre je Nutzer (prozessweit; Go ist der einzige Schreiber,
   der Python-Core liest nur). `password_hash`, `passkey_credentials`, `oauth_provider`,
   `oauth_sub`, `disabled`, `tier` und `email_verified_at` schreibt nur `UpdateUser` (lädt unter
   der Sperre frisch) oder ein Merge-Setter; `SaveUser` übernimmt sie bei vorhandener Datei vom
   Plattenstand. Ein veralteter Schreiber kann sie damit nicht zurücksetzen. Dasselbe gilt für
   `email`, `mail_to` und `pending_contact_*`: der Profil-PUT schreibt nur die Felder, die er
   ändert, auf den frisch geladenen Stand (bei zwischenzeitlich verändertem Adressstand 412), der
   Bestätigungslink wendet die ausstehende Änderung auf dem frischen Stand an.
8. **Verdrängen unbestätigter Anmeldungen.** Eine Registrierung verdrängt erst unmittelbar vor
   der Kontoanlage, nachdem alle Prüfungen bestanden sind; scheitert die Anlage, kommt die
   Anmeldung aus der Ablage zurück. Je Adresse höchstens eine Ersetzung pro Stunde (darüber
   „Adresse vergeben“). Die Ablage prüft unter der Nutzersperre erneut, ob es noch eine leere
   unbestätigte Anmeldung ist.

## Verworfene Alternativen

- **Nachweis bei jeder Änderung ohne Zeitfenster** — mehrere Änderungen hintereinander (Adresse,
  dann Passkey) würden mehrfach abgefragt; das Zeitfenster je Sitzung ist das übliche
  „Sudo“-Muster.
- **Nachweis an den Nutzer statt an die Sitzung binden** — ein Nachweis auf einem Gerät würde
  eine parallel erbeutete Sitzung mit freischalten.
- **Passkey-Zeremonie als eigener Nachweis** — wie in ADR-0081 zurückgestellt; Passwort und Code
  an die bisherige Adresse decken alle Konten ab.
- **Unbestätigte Konten nie ersetzen, nur nach Frist löschen** — der echte Inhaber müsste bis
  zu 48 Stunden warten, bevor er sich registrieren kann.
- **„Auf allen Geräten abmelden“ entfernt auch Passkeys** — der Nutzer verlöre ohne Rückfrage
  seine eigenen Geräte; der Passwort-Reset ist der vorgesehene Notweg mit ausdrücklicher Wahl.
- **Ein Index/Datenbank statt Dateisperre** — größerer Umbau; eine Prozess-Sperre reicht, weil
  genau ein Go-Prozess `user.json` schreibt.

## Konsequenzen

- **Positiv:** Eine erbeutete Sitzung reicht nicht mehr, um Adresse oder Passkeys dauerhaft zu
  übernehmen; der Inhaber erfährt jede solche Änderung per Mail und kann mit einem Reset alle
  fremden Zugangswege auf einmal entfernen. Vorab angelegte Konten blockieren keine Adresse mehr
  und verschwinden von selbst. Sicherheitswerte überleben parallele Schreiber.
- **Restrisiken (bewusst hingenommen):**
  - Wer eine fremd ausgelöste Registrierung per Klick auf den Bestätigungslink bestätigt,
    bestätigt das Konto eines Dritten. Die Mail warnt davor; der Inhaber kann es danach per
    Passwort-Reset (entfernt alle anderen Zugangswege) übernehmen.
  - Innerhalb der 10 Minuten nach einem Nachweis bzw. einer Anmeldung kann eine Sitzung die
    geschützten Änderungen ohne erneute Abfrage ausführen.
  - Eine neue Registrierung kann eine echte, noch nicht bestätigte Registrierung derselben Adresse
    ersetzen. Bestätigen kann nur, wer das Postfach liest.
  - Nachweise und Codes leben im Prozess; ein Neustart verlangt den Nachweis erneut.
  - Ein Angreifer mit Zugriff auf das Postfach der bisherigen Adresse kann den Code anfordern —
    gleiche Risikoklasse wie Magic-Link und Passwort-Reset.
- **Folgepflichten:** Jede neue Funktion, die Adresse, Login-Kennung oder Zugangswege einer
  bestehenden Sitzung ändert, hängt hinter `RequireFreshReauth` bzw. das Änderungs-Prädikat des
  Profils und schreibt Sicherheitsfelder nur über `UpdateUser`/Merge-Setter.
