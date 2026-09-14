package handler

// TDD RED — Issue #2147 Scheibe B2: Einloesen eines adressgebundenen
// Bestaetigungs-Tokens (VerifyEmailHandler).
// Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md — AC-2, AC-3,
// AC-8, AC-9, AC-12. JSON-Vertrag und Helfer: profile_email_pending_test.go.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- AC-2 ---------------------------------------------------------------------

// AC-2: bestaetigtes Konto mit ausstehender Aenderung loest den Link ein ->
// neue Adresse wirksam, email_verified_at NEU gestempelt, Pending weg, Token
// weg; derselbe Link bewirkt beim zweiten Mal nichts (400, Zustand gleich).
//
// Offener Punkt (siehe red-notizen): der Test-Bullet der Spec nennt fuer den
// Zweitversuch `token expired`, §2 loescht das Token aber und laesst die
// Hash-/Ladepruefung unveraendert -> dort entsteht `invalid token`. Das
// freigegebene "Then" verlangt nur "kann kein zweites Mal etwas bewirken";
// deshalb wird hier 400 mit einem der beiden Codes akzeptiert, streng ist
// der unveraenderte Zustand.
func TestAC2_EinloesenMachtAusstehendeAdresseWirksamUndNeuGestempelt(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "einloesen-ac2-b2"
	const email = "einloesen-ac2-email-b2@beispiel.de"
	const alt = "einloesen-ac2-alt-b2@beispiel.de"
	const neu = "einloesen-ac2-neu-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, email, alt)

	if w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu)); w.Code != http.StatusOK {
		t.Fatalf("AC-2: Profil-Update erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	token := ausstehendToken(t, mustMail(t, versand, neu))

	zwischen := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(zwischen, "mail_to"); got != alt {
		t.Errorf("AC-2 Ausgangslage: vor dem Einloesen muss mail_to noch %q sein, ist %q", alt, got)
	}
	if ts := ausstehendZeitstempel(t, "AC-2", zwischen); ts == nil || !ts.Equal(ausstehendAltBestaetigt) {
		t.Errorf("AC-2 Ausgangslage: vor dem Einloesen muss email_verified_at unveraendert %v sein, ist %v",
			ausstehendAltBestaetigt, ts)
	}
	if got := ausstehendStr(zwischen, "pending_contact_address"); got != neu {
		t.Errorf("AC-2 Ausgangslage: pending_contact_address muss %q sein, ist %q", neu, got)
	}

	w := ausstehendEinloesen(s, uid, token)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-2: Einloesen erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	danach := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(danach, "mail_to"); got != neu {
		t.Errorf("AC-2: nach dem Einloesen muss mail_to %q sein, ist %q", neu, got)
	}
	if got := ausstehendStr(danach, "email"); got != email {
		t.Errorf("AC-2: email darf sich nicht aendern (%q), ist %q", email, got)
	}
	ts := ausstehendZeitstempel(t, "AC-2", danach)
	if ts == nil || !ts.After(ausstehendAltBestaetigt) {
		t.Errorf("AC-2: email_verified_at muss gesetzt und neuer als %v sein, ist %v", ausstehendAltBestaetigt, ts)
	}
	ausstehendKeinePendingFelder(t, "AC-2", danach)
	if _, da := ausstehendTokenMap(t, s, uid); da {
		t.Errorf("AC-2: das Token muss nach erfolgreicher Einloesung geloescht sein")
	}

	rohNachErstem := rohesKonto(t, s, uid)
	w2 := ausstehendEinloesen(s, uid, token)
	if w2.Code != http.StatusBadRequest {
		t.Errorf("AC-2: Zweitversuch mit demselben Token muss 400 liefern, bekommen %d: %s", w2.Code, w2.Body.String())
	}
	if code := schreibpfadFehlerCode(w2); code != "token expired" && code != "invalid token" {
		t.Errorf("AC-2: Zweitversuch muss als abgelaufen/ungueltig abgewiesen werden, Code %q", code)
	}
	if string(rohNachErstem) != string(rohesKonto(t, s, uid)) {
		t.Errorf("AC-2: der Zweitversuch darf user.json nicht veraendern (z.B. neu stempeln)")
	}
}

// mustMail ist ausstehendWarteAufMail ohne die Nebenliste.
func mustMail(t *testing.T, ch chan ausstehendMail, an string) ausstehendMail {
	t.Helper()
	m, _ := ausstehendWarteAufMail(t, ch, an)
	return m
}

// --- AC-3 ---------------------------------------------------------------------

// AC-3: zweiter Wechsel vor dem ersten Klick ersetzt den ersten vollstaendig;
// der erste Link -> 400 {"error":"token expired"} (freigegebenes Then), Konto
// bleibt bei der zweiten ausstehenden Adresse. Positivkontrolle: der zweite
// Link wirkt danach.
func TestAC3_ZweiterWechselEntwertetErstenLinkMitTokenExpired(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "doppelt-ac3-b2"
	const alt = "doppelt-ac3-alt-b2@beispiel.de"
	const neu1 = "doppelt-ac3-neu1-b2@beispiel.de"
	const neu2 = "doppelt-ac3-neu2-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, "doppelt-ac3-email-b2@beispiel.de", alt)

	if w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu1)); w.Code != http.StatusOK {
		t.Fatalf("AC-3: erstes Profil-Update erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	token1 := ausstehendToken(t, mustMail(t, versand, neu1))
	w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu2))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-3: zweites Profil-Update erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	token2 := ausstehendToken(t, mustMail(t, versand, neu2))

	zwischen := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(zwischen, "mail_to"); got != alt {
		t.Errorf("AC-3: mail_to muss nach zwei ausstehenden Wechseln %q bleiben, ist %q", alt, got)
	}
	if got := ausstehendStr(zwischen, "pending_contact_address"); got != neu2 {
		t.Errorf("AC-3: pending_contact_address muss die ZWEITE Adresse %q tragen, ist %q", neu2, got)
	}
	rohVorher := rohesKonto(t, s, uid)

	w1 := ausstehendEinloesen(s, uid, token1)
	if w1.Code != http.StatusBadRequest || schreibpfadFehlerCode(w1) != "token expired" {
		t.Errorf("AC-3: erster, ersetzter Link muss 400 {\"error\":\"token expired\"} liefern, bekommen %d: %s",
			w1.Code, w1.Body.String())
	}
	if string(rohVorher) != string(rohesKonto(t, s, uid)) {
		t.Errorf("AC-3: der ersetzte Link darf user.json nicht veraendern")
	}
	if tok, da := ausstehendTokenMap(t, s, uid); !da {
		t.Errorf("AC-3: das Token der zweiten Aenderung muss nach dem Fehlversuch weiter existieren")
	} else if got := ausstehendStr(tok, "address"); got != neu2 {
		t.Errorf("AC-3: gespeichertes Token muss an %q gebunden sein, ist %q", neu2, got)
	}

	// Positivkontrolle: der zweite Link wirkt.
	if w2 := ausstehendEinloesen(s, uid, token2); w2.Code != http.StatusOK {
		t.Fatalf("AC-3 Positivkontrolle: zweiter Link erwartet 200, bekommen %d: %s", w2.Code, w2.Body.String())
	}
	if got := ausstehendStr(ausstehendKontoMap(t, s, uid), "mail_to"); got != neu2 {
		t.Errorf("AC-3 Positivkontrolle: nach dem zweiten Link muss mail_to %q sein, ist %q", neu2, got)
	}
}

// --- AC-8 ---------------------------------------------------------------------

// AC-8: Zwei Nutzer. A beantragt x (ausstehend). B erhaelt x danach ganz
// normal (Registrierung ODER Profil-Update eines unbestaetigten Kontos) —
// eine ausstehende Aenderung zaehlt nicht als belegt. A loest danach seinen
// gueltigen Link ein -> 409 address_taken, A behaelt alte Adresse und
// Bestaetigung, A's Pending und Token sind geloescht, B byteidentisch.
func TestAC8_AusstehendeAdresseZaehltNichtAlsBelegtEinloesenScheitertMit409(t *testing.T) {
	faelle := []struct {
		name  string
		holen func(t *testing.T, s *store.Store, x string) string // liefert B's Kennung
	}{
		{"registrierung", func(t *testing.T, s *store.Store, x string) string {
			const uidB = "bneu-reg-ac8-b2"
			w := schreibpfadRegistrieren(s, ausstehendCfg(), uidB, x)
			if w.Code != http.StatusCreated {
				t.Fatalf("AC-8/registrierung: B's Registrierung mit %q muss gelingen (201), bekommen %d: %s",
					x, w.Code, w.Body.String())
			}
			return uidB
		}},
		{"profil", func(t *testing.T, s *store.Store, x string) string {
			const uidB = "bneu-prof-ac8-b2"
			speichereKonto(t, s, model.User{ID: uidB, Email: "bneu-prof-ac8-alt-b2@beispiel.de"})
			w := schreibpfadProfilAktualisieren(s, ausstehendCfg(), uidB, fmt.Sprintf(`{"email":%q}`, x))
			if w.Code != http.StatusOK {
				t.Fatalf("AC-8/profil: B's Profil-Update auf %q muss gelingen (200), bekommen %d: %s",
					x, w.Code, w.Body.String())
			}
			return uidB
		}},
	}
	for i, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			cfg := ausstehendCfg()
			versand := ausstehendBeobachteVersand(t)
			uidA := fmt.Sprintf("konto-a%d-ac8-b2", i)
			emailA := fmt.Sprintf("konto-a%d-ac8-email-b2@beispiel.de", i)
			altA := fmt.Sprintf("konto-a%d-ac8-alt-b2@beispiel.de", i)
			x := fmt.Sprintf("x%d-ac8-b2@beispiel.de", i)
			ausstehendBestaetigtesKonto(t, s, uidA, emailA, altA)
			vorherA := ausstehendKontoMap(t, s, uidA)

			if w := schreibpfadProfilAktualisieren(s, cfg, uidA, fmt.Sprintf(`{"mail_to":%q}`, x)); w.Code != http.StatusOK {
				t.Fatalf("AC-8: A's Profil-Update erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
			}
			tokenA := ausstehendToken(t, mustMail(t, versand, x))
			if got := ausstehendStr(ausstehendKontoMap(t, s, uidA), "pending_contact_address"); got != x {
				t.Fatalf("AC-8 Ausgangslage: A muss x=%q als AUSSTEHEND tragen (pending_contact_address), ist %q "+
					"— ohne ausstehenden Zustand ist der Rest des Nachweises gegenstandslos", x, got)
			}

			uidB := f.holen(t, s, x)
			vorherB := rohesKonto(t, s, uidB)

			w := ausstehendEinloesen(s, uidA, tokenA)
			if w.Code != http.StatusConflict || schreibpfadFehlerCode(w) != "address_taken" {
				t.Errorf("AC-8: A's Einloesen muss 409 {\"error\":\"address_taken\"} liefern, bekommen %d: %s",
					w.Code, w.Body.String())
			}
			nachherA := ausstehendKontoMap(t, s, uidA)
			for _, k := range []string{"email", "mail_to", "email_verified_at"} {
				if fmt.Sprint(vorherA[k]) != fmt.Sprint(nachherA[k]) {
					t.Errorf("AC-8: A's %s muss unveraendert bleiben — vorher %v, nachher %v", k, vorherA[k], nachherA[k])
				}
			}
			ausstehendKeinePendingFelder(t, "AC-8 (A nach 409)", nachherA)
			if _, da := ausstehendTokenMap(t, s, uidA); da {
				t.Errorf("AC-8: A's Token muss nach 409 geloescht sein")
			}
			if string(vorherB) != string(rohesKonto(t, s, uidB)) {
				t.Errorf("AC-8: B's user.json muss byteidentisch bleiben")
			}
		})
	}
}

// --- AC-9 ---------------------------------------------------------------------

// AC-9: A hat x ausstehend; B (unbestaetigt) aendert sein Profil auf x,
// WAEHREND A einloest. Deterministische Anordnung ohne Zeitglueck in der
// Ergebnisrichtung:
//
//  1. B's Profil-Update laeuft bis zur Naht profileUpdateAfterFirstAddressLock.
//     B's Sperrmenge ist {x, B-alt}; x ist lexikografisch kleiner
//     ("aaa-…" < "zzz-…"), die ERSTE genommene Sperre ist also x.
//  2. In der Naht startet A's Einloesen. Laut Spec §2 laeuft es unter
//     store.LockEmailAddress(x) -> es MUSS blockieren, solange B die Sperre
//     haelt. Wird es binnen 500 ms fertig, nimmt das Einloesen die
//     Adresssperre nicht -> Befund (die Richtung des Fehlers ist nur
//     "Mutation unter extremer Last evtl. unentdeckt", nie "korrekter Code
//     rot").
//  3. B laeuft weiter und schreibt x (unbestaetigtes Konto: sofort wirksam).
//     Danach bekommt A die Sperre, prueft neu -> 409 address_taken.
//
// Endzustand: genau ein Konto haelt x (B), hoechstens ein Konto traegt x als
// bestaetigte wirksame Adresse (hier keins), A behaelt seine alte Adresse.
//
// Grenze: das gefaehrliche Gegen-Interleaving (A prueft "frei", B schreibt, A
// schreibt) liesse sich nur mit einer NEUEN Produktiv-Naht zwischen Pruefung
// und Schreiben in VerifyEmailHandler erzwingen; der Test belegt stattdessen
// die Sperre selbst am Wirkort.
func TestAC9_EinloesenGegenGleichzeitigesProfilUpdateErgibtGenauEinenInhaber(t *testing.T) {
	t.Cleanup(func() { profileUpdateAfterFirstAddressLock = nil })
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uidA = "konto-a-ac9-b2"
	const uidB = "konto-b-ac9-b2"
	const altA = "konto-a-ac9-alt-b2@beispiel.de"
	const x = "aaa-ziel-ac9-b2@beispiel.de"
	const altB = "zzz-konto-b-ac9-alt-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uidA, "konto-a-ac9-email-b2@beispiel.de", altA)
	speichereKonto(t, s, model.User{ID: uidB, Email: altB})

	if w := schreibpfadProfilAktualisieren(s, cfg, uidA, fmt.Sprintf(`{"mail_to":%q}`, x)); w.Code != http.StatusOK {
		t.Fatalf("AC-9: A's Profil-Update erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	tokenA := ausstehendToken(t, mustMail(t, versand, x))
	if got := ausstehendStr(ausstehendKontoMap(t, s, uidA), "pending_contact_address"); got != x {
		t.Fatalf("AC-9 Ausgangslage: A muss x=%q ausstehend tragen, ist %q — Rennen nicht herstellbar", x, got)
	}

	// Anfragen VOR der Startschranke bauen.
	reqB := withUserCtx(httptest.NewRequest(http.MethodPut, "/api/auth/profile",
		strings.NewReader(fmt.Sprintf(`{"email":%q}`, x))), uidB)
	reqA := httptest.NewRequest(http.MethodPost, "/api/auth/verify-email",
		strings.NewReader(fmt.Sprintf(`{"user":%q,"token":%q}`, uidA, tokenA)))
	wA, wB := httptest.NewRecorder(), httptest.NewRecorder()

	aFertig := make(chan struct{})
	var nahtAufrufe int32
	var aLiefDurchSperre int32
	profileUpdateAfterFirstAddressLock = func(userID string) {
		if userID != uidB {
			return
		}
		if atomic.AddInt32(&nahtAufrufe, 1) != 1 {
			return
		}
		go func() {
			VerifyEmailHandler(s).ServeHTTP(wA, reqA)
			close(aFertig)
		}()
		select {
		case <-aFertig:
			atomic.StoreInt32(&aLiefDurchSperre, 1)
		case <-time.After(500 * time.Millisecond):
		}
	}

	bFertig := make(chan struct{})
	go func() {
		UpdateProfileHandler(s, cfg).ServeHTTP(wB, reqB)
		close(bFertig)
	}()
	for _, ch := range []chan struct{}{bFertig, aFertig} {
		select {
		case <-ch:
		case <-time.After(3 * time.Second):
			t.Fatalf("AC-9: kein Ergebnis binnen 3s — Verklemmung (A=%d, B=%d)", wA.Code, wB.Code)
		}
	}

	if got := atomic.LoadInt32(&nahtAufrufe); got != 1 {
		t.Fatalf("AC-9: Naht feuerte %d mal fuer B statt 1 — die Kollisionslage wurde nicht hergestellt", got)
	}
	if atomic.LoadInt32(&aLiefDurchSperre) == 1 {
		t.Errorf("AC-9: A's Einloesen wurde fertig, WAEHREND B die Adresssperre fuer x hielt — " +
			"VerifyEmailHandler nimmt store.LockEmailAddress(x) nicht (Spec §2)")
	}
	if wB.Code != http.StatusOK {
		t.Errorf("AC-9: B hielt die Sperre zuerst und muss gewinnen (200), bekommen %d: %s", wB.Code, wB.Body.String())
	}
	if wA.Code != http.StatusConflict || schreibpfadFehlerCode(wA) != "address_taken" {
		t.Errorf("AC-9: A muss nach B's Schreiben 409 address_taken bekommen, bekommen %d: %s", wA.Code, wA.Body.String())
	}

	// Endzustand-Invarianten
	if n := schreibpfadAdresseHalterAnzahl(t, s, x); n != 1 {
		t.Errorf("AC-9: genau ein Konto darf x in email/mail_to halten, sind %d", n)
	}
	bestaetigtWirksam := 0
	for _, uid := range []string{uidA, uidB} {
		u := ladeKonto(t, s, uid)
		if u.EmailVerifiedAt != nil && store.EffectiveContactAddress(u) == x {
			bestaetigtWirksam++
		}
	}
	if bestaetigtWirksam > 1 {
		t.Errorf("AC-9: %d Konten tragen x als bestaetigte wirksame Adresse — hoechstens eins erlaubt", bestaetigtWirksam)
	}
	if got := ausstehendStr(ausstehendKontoMap(t, s, uidA), "mail_to"); got != altA {
		t.Errorf("AC-9: A muss seine alte Adresse %q behalten, mail_to ist %q", altA, got)
	}
}

// --- AC-12 --------------------------------------------------------------------

// AC-12 — Regressionswächter B2: heute grün.
// Alt-Token ohne "address"-Feld (Vor-Deploy-Zustand, ROH in
// email_verification.json geschrieben) fuer ein unbestaetigtes Konto ->
// Einloesen bestaetigt das Konto wie bisher.
func TestAC12_AltTokenOhneAdresseBestaetigtUnbestaetigtesKonto(t *testing.T) {
	s := newTestStore(t)
	const uid = "alttoken-ac12-b2"
	const mt = "alttoken-ac12-mt-b2@beispiel.de"
	const klartext = "alt-token-ac12-klartext"
	speichereKonto(t, s, model.User{ID: uid, Email: "alttoken-ac12-b2@beispiel.de", MailTo: mt})

	hash, err := bcrypt.GenerateFromPassword([]byte(klartext), bcrypt.MinCost)
	if err != nil {
		t.Fatal(err)
	}
	roh, _ := json.Marshal(map[string]any{
		"token_hash": string(hash),
		"expires_at": time.Now().Add(24 * time.Hour).UTC().Format(time.RFC3339Nano),
	})
	if err := os.WriteFile(filepath.Join(s.UserDir(uid), "email_verification.json"), roh, 0o644); err != nil {
		t.Fatal(err)
	}

	w := ausstehendEinloesen(s, uid, klartext)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-12: Alt-Token muss angenommen werden (200), bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ausstehendKontoMap(t, s, uid)
	if ausstehendZeitstempel(t, "AC-12", nachher) == nil {
		t.Errorf("AC-12: nach dem Einloesen muss email_verified_at gesetzt sein")
	}
	if got := ausstehendStr(nachher, "mail_to"); got != mt {
		t.Errorf("AC-12: die wirksame Adresse %q darf sich nicht aendern, ist %q", mt, got)
	}
	ausstehendKeinePendingFelder(t, "AC-12", nachher)
	if _, da := ausstehendTokenMap(t, s, uid); da {
		t.Errorf("AC-12: das Alt-Token muss nach Einloesung geloescht sein")
	}
}
