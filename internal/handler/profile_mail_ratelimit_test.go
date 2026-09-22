package handler

// TDD RED — Issue #2404 (Sammel-Issue #2153, Scheibe S2): Rate-Limit fuer
// Bestaetigungsmails aus Profil-Update und Resend-Verification.
// Spec: docs/specs/bugfix/profile_mail_ratelimit.md — AC-1 bis AC-8.
//
// MailFloodLimiter existiert vor /50-implement noch nicht, und
// UpdateProfileHandler/ResendVerificationHandler bekommen hier einen dritten
// Parameter, den es in auth.go noch nicht gibt — das Paket kompiliert deshalb
// bewusst nicht. Ein Compile-Fehler ist in Go ein gueltiger RED-Beleg.
//
// Wiederverwendete Helfer aus dem Paket (siehe profile_email_pending_test.go,
// magic_link_address_ownership_test.go, address_uniqueness_write_paths_test.go):
// newTestStore, speichereKonto, ausstehendCfg, ausstehendBestaetigtesKonto,
// ausstehendAltBestaetigt, ausstehendBeobachteVersand, ausstehendWarteAufMail,
// ausstehendKeineWeitereMail, ausstehendAntwortMap, ausstehendProfilLesen,
// ausstehendStr, schreibpfadFehlerCode. Neue Helfer tragen das Praefix "flut".

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Hilfen (Praefix "flut") --------------------------------------------------

// flutLimiter baut einen frischen Limiter mit dem in der Spec vorgegebenen
// Produktionswert (10 pro Stunde, Abschnitt "Implementation Details" §1).
func flutLimiter() *MailFloodLimiter {
	return NewMailFloodLimiter(10, time.Hour)
}

func flutProfilAktualisieren(s *store.Store, cfg config.Config, ml *MailFloodLimiter, userID, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	w := httptest.NewRecorder()
	UpdateProfileHandler(s, cfg, ml).ServeHTTP(w, req)
	return w
}

func flutResend(s *store.Store, cfg config.Config, ml *MailFloodLimiter, uid string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/auth/verify-email/resend",
		strings.NewReader(fmt.Sprintf(`{"username":%q}`, uid)))
	w := httptest.NewRecorder()
	ResendVerificationHandler(s, cfg, ml).ServeHTTP(w, req)
	return w
}

// --- MailFloodLimiter: Unit-Ebene ---------------------------------------------

func TestMailFloodLimiter_AllowRespectsBurstThenRejects(t *testing.T) {
	l := NewMailFloodLimiter(3, time.Hour)
	for i := 1; i <= 3; i++ {
		if !l.Allow("u1", fmt.Sprintf("a%d@beispiel.de", i)) {
			t.Fatalf("Versuch %d: erwartet true (innerhalb Burst 3)", i)
		}
	}
	if l.Allow("u1", "a4@beispiel.de") {
		t.Error("4. Versuch (User-Bucket ausgeschoepft) haette false liefern muessen")
	}
}

func TestMailFloodLimiter_UserBucketIstUeberAdressenHinwegGeteilt(t *testing.T) {
	l := NewMailFloodLimiter(2, time.Hour)
	if !l.Allow("u1", "a1@beispiel.de") {
		t.Fatal("1. Versuch (Adresse a1) haette true liefern muessen")
	}
	if !l.Allow("u1", "a2@beispiel.de") {
		t.Fatal("2. Versuch (Adresse a2, User-Bucket jetzt 2/2) haette true liefern muessen")
	}
	if l.Allow("u1", "a3@beispiel.de") {
		t.Error("3. Versuch auf einer FRISCHEN Adresse haette am erschoepften User-Bucket scheitern muessen")
	}
}

func TestMailFloodLimiter_AddressBucketIstUeberNutzerHinwegGeteilt(t *testing.T) {
	l := NewMailFloodLimiter(2, time.Hour)
	if !l.Allow("u1", "opfer@beispiel.de") {
		t.Fatal("u1, 1. Versuch haette true liefern muessen")
	}
	if !l.Allow("u2", "opfer@beispiel.de") {
		t.Fatal("u2, 1. Versuch (Adress-Bucket jetzt 2/2) haette true liefern muessen")
	}
	if l.Allow("u3", "opfer@beispiel.de") {
		t.Error("u3 (frischer User-Bucket) haette am erschoepften Adress-Bucket scheitern muessen")
	}
}

// Unit-Pendant zu AC-7: die Ablehnung eines Versuchs, dessen Adress-Bucket
// voll ist, darf den User-Bucket des Ablehnenden nicht anfassen.
func TestMailFloodLimiter_AblehnungVerbrauchtKeinTokenDesEigenenUserBuckets(t *testing.T) {
	const burst = 3
	l := NewMailFloodLimiter(burst, time.Hour)
	// Adresse x wird durch drei VERSCHIEDENE Saettiger gefuellt, damit deren
	// eigene User-Buckets unberuehrt bleiben und nur der Adress-Bucket von x
	// danach voll ist.
	for i := 0; i < burst; i++ {
		if !l.Allow(fmt.Sprintf("saettiger-%d", i), "x@beispiel.de") {
			t.Fatalf("Saettiger %d haette Adresse x noch fuellen duerfen", i)
		}
	}
	if l.Allow("a", "x@beispiel.de") {
		t.Fatal("a's Versuch auf der bereits vollen Adresse x haette false liefern muessen")
	}
	for i := 0; i < burst; i++ {
		if !l.Allow("a", fmt.Sprintf("frisch-%d@beispiel.de", i)) {
			t.Errorf("a's Versuch %d auf einer frischen Adresse scheiterte — die Ablehnung auf x hat faelschlich a's User-Bucket verbraucht", i)
		}
	}
}

// Unit-Pendant zu AC-8: AllowAddressOnly darf ausschliesslich den Adress-
// Bucket beruehren, nie einen User-Bucket.
func TestMailFloodLimiter_AllowAddressOnlyBeruehrtNurDenAdressBucket(t *testing.T) {
	const burst = 3
	l := NewMailFloodLimiter(burst, time.Hour)
	for i := 0; i < burst; i++ {
		if !l.AllowAddressOnly("p@beispiel.de") {
			t.Fatalf("AllowAddressOnly Versuch %d haette true liefern muessen", i)
		}
	}
	if l.AllowAddressOnly("p@beispiel.de") {
		t.Error("Adress-Bucket p ist voll, weiterer AllowAddressOnly-Aufruf haette false liefern muessen")
	}
	for i := 0; i < burst; i++ {
		if !l.Allow("opfer", fmt.Sprintf("eigene-%d@beispiel.de", i)) {
			t.Errorf("opfer's Versuch %d scheiterte — AllowAddressOnly hat faelschlich den User-Bucket von opfer beruehrt", i)
		}
	}
}

// --- Handler-Integration: AC-1 bis AC-8 ---------------------------------------

// AC-1: der elfte Adresswechsel desselben bestaetigten Nutzers innerhalb einer
// Stunde bekommt 429 + Retry-After, die zehnte (nicht die elfte) Adresse
// bleibt im Profil stehen.
func TestAC1_ElfterAdresswechselWirdMit429AbgelehntUndNichtGespeichert(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	ml := flutLimiter()
	const uid = "flut-ac1"
	ausstehendBestaetigtesKonto(t, s, uid, "flut-ac1-email@beispiel.de", "flut-ac1-alt@beispiel.de")

	var letzteErfolgreiche string
	for i := 1; i <= 10; i++ {
		addr := fmt.Sprintf("flut-ac1-neu-%d@beispiel.de", i)
		w := flutProfilAktualisieren(s, cfg, ml, uid, fmt.Sprintf(`{"mail_to":%q}`, addr))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-1: Versuch %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
		letzteErfolgreiche = addr
	}

	elfte := "flut-ac1-neu-11@beispiel.de"
	w := flutProfilAktualisieren(s, cfg, ml, uid, fmt.Sprintf(`{"mail_to":%q}`, elfte))
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("AC-1: 11. Versuch erwartet 429, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := w.Header().Get("Retry-After"); got != "360" {
		t.Errorf("AC-1: Retry-After erwartet \"360\", bekommen %q", got)
	}
	if got := schreibpfadFehlerCode(w); got != "rate_limit_exceeded" {
		t.Errorf("AC-1: error-Code erwartet \"rate_limit_exceeded\", bekommen %q", got)
	}

	profil := ausstehendAntwortMap(t, ausstehendProfilLesen(s, uid))
	if got := ausstehendStr(profil, "pending_contact_address"); got != letzteErfolgreiche {
		t.Errorf("AC-1: GET-Profil muss weiterhin die 10. Adresse %q zeigen (nicht die 11.), zeigt %q", letzteErfolgreiche, got)
	}
}

// AC-2: zwei verschiedene bestaetigte Konten wechseln unabhaengig auf
// dieselbe fremde Adresse — ab der gemeinsamen elften Anfrage greift 429,
// unabhaengig davon, welches Konto den Request stellt.
func TestAC2_CrossAccountAdressFloodWirdGemeinsamGezaehlt(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	ml := flutLimiter()
	const uidA = "flut-ac2-a"
	const uidB = "flut-ac2-b"
	const opfer = "flut-ac2-opfer@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uidA, "flut-ac2-a-email@beispiel.de", "flut-ac2-a-alt@beispiel.de")
	ausstehendBestaetigtesKonto(t, s, uidB, "flut-ac2-b-email@beispiel.de", "flut-ac2-b-alt@beispiel.de")

	for i := 1; i <= 6; i++ {
		w := flutProfilAktualisieren(s, cfg, ml, uidA, fmt.Sprintf(`{"mail_to":%q}`, opfer))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-2: A Versuch %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}
	for i := 1; i <= 4; i++ {
		w := flutProfilAktualisieren(s, cfg, ml, uidB, fmt.Sprintf(`{"mail_to":%q}`, opfer))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-2: B Versuch %d (gemeinsame Summe %d) erwartet 200, bekommen %d: %s", i, 6+i, w.Code, w.Body.String())
		}
	}
	w := flutProfilAktualisieren(s, cfg, ml, uidB, fmt.Sprintf(`{"mail_to":%q}`, opfer))
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("AC-2: B's 5. Versuch (gemeinsame Summe 11) erwartet 429, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// AC-3: derselbe Nutzer wechselt zuerst fuenfmal auf Adresse A, dann fuenfmal
// auf Adresse B — beide Adress-Buckets bleiben unter dem Limit, alle zehn
// Requests gehen durch.
func TestAC3_UnabhaengigeAdressBucketsErlaubenZehnWechselDesselbenNutzers(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	ml := flutLimiter()
	const uid = "flut-ac3"
	const adresseA = "flut-ac3-a@beispiel.de"
	const adresseB = "flut-ac3-b@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, "flut-ac3-email@beispiel.de", "flut-ac3-alt@beispiel.de")

	for i := 1; i <= 5; i++ {
		w := flutProfilAktualisieren(s, cfg, ml, uid, fmt.Sprintf(`{"mail_to":%q}`, adresseA))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-3: A-Versuch %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}
	for i := 1; i <= 5; i++ {
		w := flutProfilAktualisieren(s, cfg, ml, uid, fmt.Sprintf(`{"mail_to":%q}`, adresseB))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-3: B-Versuch %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}
}

// AC-4: das Adress-Limit einer Adresse ist ueber den Profil-Update-Pfad
// bereits ausgeschoepft — ein Resend fuer ein anderes Konto mit ausstehender
// Aenderung auf dieselbe Adresse bleibt 200, versendet aber keine Mail.
func TestAC4_ResendUeberAusgeschoepfteAdresseVersendetKeineMailBleibtAber200(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	ml := flutLimiter()
	versand := ausstehendBeobachteVersand(t)
	const saettiger = "flut-ac4-saettiger"
	const opfer = "flut-ac4-opfer"
	const adresseX = "flut-ac4-x@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, saettiger, "flut-ac4-saettiger-email@beispiel.de", "flut-ac4-saettiger-alt@beispiel.de")

	for i := 1; i <= 10; i++ {
		w := flutProfilAktualisieren(s, cfg, ml, saettiger, fmt.Sprintf(`{"mail_to":%q}`, adresseX))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-4 Saettigung: Versuch %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
		ausstehendWarteAufMail(t, versand, adresseX)
	}

	opferBestaetigt := ausstehendAltBestaetigt
	speichereKonto(t, s, model.User{
		ID: opfer, Email: "flut-ac4-opfer-email@beispiel.de", MailTo: "flut-ac4-opfer-alt@beispiel.de",
		EmailVerifiedAt: &opferBestaetigt, PendingContactAddress: adresseX, PendingContactField: "mail_to",
	})

	w := flutResend(s, cfg, ml, opfer)
	if w.Code != http.StatusOK || w.Body.String() != `{"status":"ok"}` {
		t.Fatalf("AC-4: Resend erwartet 200 {\"status\":\"ok\"}, bekommen %d: %s", w.Code, w.Body.String())
	}
	ausstehendKeineWeitereMail(t, versand, "AC-4", adresseX)
}

// AC-5: mehrere Profil-Updates mit ausschliesslich harmlosen Feldern
// verbrauchen kein Kontingent — danach gehen trotzdem alle zehn erlaubten
// Adresswechsel durch.
func TestAC5_HarmloseFelderVerbrauchenKeinKontingent(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	ml := flutLimiter()
	const uid = "flut-ac5"
	ausstehendBestaetigtesKonto(t, s, uid, "flut-ac5-email@beispiel.de", "flut-ac5-alt@beispiel.de")

	for i := 1; i <= 5; i++ {
		w := flutProfilAktualisieren(s, cfg, ml, uid, fmt.Sprintf(`{"display_name":"Name %d"}`, i))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-5: harmloser Versuch %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}
	for i := 1; i <= 10; i++ {
		addr := fmt.Sprintf("flut-ac5-neu-%d@beispiel.de", i)
		w := flutProfilAktualisieren(s, cfg, ml, uid, fmt.Sprintf(`{"mail_to":%q}`, addr))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-5: Adress-Versuch %d erwartet 200, bekommen %d: %s (harmlose Requests haetten kein Kontingent verbrauchen duerfen)", i, w.Code, w.Body.String())
		}
	}
}

// AC-6: ein kombinierter Request (Adresse + harmloses Feld) bei ausgeschoepftem
// Limit wird komplett verworfen — auch das harmlose Feld bleibt unveraendert.
func TestAC6_KombinierterRequestBeiAusgeschoepftemLimitVerwirftAuchHarmloseFelder(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	ml := flutLimiter()
	const uid = "flut-ac6"
	ausstehendBestaetigtesKonto(t, s, uid, "flut-ac6-email@beispiel.de", "flut-ac6-alt@beispiel.de")

	for i := 1; i <= 10; i++ {
		addr := fmt.Sprintf("flut-ac6-neu-%d@beispiel.de", i)
		w := flutProfilAktualisieren(s, cfg, ml, uid, fmt.Sprintf(`{"mail_to":%q}`, addr))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-6 Vorbedingung: Versuch %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}
	vorherProfil := ausstehendAntwortMap(t, ausstehendProfilLesen(s, uid))
	alterName := ausstehendStr(vorherProfil, "display_name")

	w := flutProfilAktualisieren(s, cfg, ml, uid,
		fmt.Sprintf(`{"mail_to":%q,"display_name":"Ganz Neu"}`, "flut-ac6-elfte@beispiel.de"))
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("AC-6: kombinierter Request erwartet 429, bekommen %d: %s", w.Code, w.Body.String())
	}

	nachherProfil := ausstehendAntwortMap(t, ausstehendProfilLesen(s, uid))
	if got := ausstehendStr(nachherProfil, "display_name"); got != alterName {
		t.Errorf("AC-6: display_name muss unveraendert %q bleiben (kein Teil-Save), ist %q", alterName, got)
	}
}

// AC-7: eine fremde Adresse ist bereits voll ausgeschoepft (10/10) — der
// abgelehnte Versuch eines anderen Nutzers auf dieser Adresse verbraucht
// keinen Token seines eigenen User-Buckets; er kann danach noch alle zehn
// erlaubten Wechsel auf eigene, frische Adressen durchfuehren.
func TestAC7_AblehnungWegenVollerAdresseVerbrauchtKeinTokenDesEigenenUserBuckets(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	ml := flutLimiter()
	const fremdesKonto = "flut-ac7-fremd"
	const uidA = "flut-ac7-a"
	const adresseX = "flut-ac7-x@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, fremdesKonto, "flut-ac7-fremd-email@beispiel.de", "flut-ac7-fremd-alt@beispiel.de")
	ausstehendBestaetigtesKonto(t, s, uidA, "flut-ac7-a-email@beispiel.de", "flut-ac7-a-alt@beispiel.de")

	for i := 1; i <= 10; i++ {
		w := flutProfilAktualisieren(s, cfg, ml, fremdesKonto, fmt.Sprintf(`{"mail_to":%q}`, adresseX))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-7 Saettigung: Versuch %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}

	w := flutProfilAktualisieren(s, cfg, ml, uidA, fmt.Sprintf(`{"mail_to":%q}`, adresseX))
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("AC-7: A's Versuch auf der vollen Adresse X erwartet 429, bekommen %d: %s", w.Code, w.Body.String())
	}

	for i := 1; i <= 10; i++ {
		addr := fmt.Sprintf("flut-ac7-a-frisch-%d@beispiel.de", i)
		fw := flutProfilAktualisieren(s, cfg, ml, uidA, fmt.Sprintf(`{"mail_to":%q}`, addr))
		if fw.Code != http.StatusOK {
			t.Errorf("AC-7: A's Folge-Versuch %d auf frischer eigener Adresse erwartet 200, bekommen %d — die Ablehnung auf X hat faelschlich A's User-Bucket verbraucht", i, fw.Code)
		}
	}
}

// AC-8: ein Angreifer schoepft ueber zehn Resend-Aufrufe mit fremdem
// `username` das Adress-Limit der ausstehenden Adresse des Opfers aus — das
// User-Kontingent des Opfers bleibt unberuehrt; das Opfer kann anschliessend
// selbst auf eine frische Adresse wechseln.
func TestAC8_ResendMitFremdemUsernameBeruehrtNichtDasOpferUserBudget(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	ml := flutLimiter()
	const opfer = "flut-ac8-opfer"
	const adresseP = "flut-ac8-p@beispiel.de"
	const adresseQ = "flut-ac8-q@beispiel.de"
	opferBestaetigt := ausstehendAltBestaetigt
	speichereKonto(t, s, model.User{
		ID: opfer, Email: "flut-ac8-opfer-email@beispiel.de", MailTo: "flut-ac8-opfer-alt@beispiel.de",
		EmailVerifiedAt: &opferBestaetigt, PendingContactAddress: adresseP, PendingContactField: "mail_to",
	})

	for i := 1; i <= 10; i++ {
		w := flutResend(s, cfg, ml, opfer)
		if w.Code != http.StatusOK {
			t.Fatalf("AC-8: Angreifer-Resend %d erwartet 200, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}

	w := flutProfilAktualisieren(s, cfg, ml, opfer, fmt.Sprintf(`{"mail_to":%q}`, adresseQ))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-8: Opfer's eigener Wechsel auf eine frische Adresse erwartet 200, bekommen %d: %s — "+
			"die zehn fremden Resend-Aufrufe haben faelschlich das Opfer-User-Budget verbraucht", w.Code, w.Body.String())
	}
}
