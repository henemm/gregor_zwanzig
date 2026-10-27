package handler

// Kontoloeschung: Wiederholbarkeit, Einmaligkeit, Fehlerpfade und Vorrang —
// Issue #2160 (Spec docs/specs/modules/account_deletion.md), Adversary
// Fix-Loop 1 (F001, F003, F004, F006, F007, F008).
//
// Fehler ohne Mock: VERZEICHNIS am Zielpfad der Token-Datei bzw. ein
// schreibgeschuetzter Nutzerordner.

import (
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

// F001 / AC-13: scheitert die Kaskade auf dem Code-Weg, ist die Löschung mit
// DEMSELBEN Code wiederholbar — der Code wurde nicht endgueltig verbraucht.
func TestKontoLoeschen_CodeWeg_KaskadeScheitert_DerselbeCodeLoeschtNachReparatur(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortlosKonto(t, s, "m-cccc0001", "magic@beispiel.de")
	ts := NewTelegramTokenStore(s.DataDir)
	mustIssueToken(t, ts, "m-cccc0001")
	code := setzeLoeschCode("m-cccc0001", "424242", time.Now().Add(10*time.Minute), 1)
	ablauf := code.expiresAt

	pfad := filepath.Join(s.DataDir, "telegram_tokens.json")
	if err := os.Remove(pfad); err != nil {
		t.Fatalf("remove: %v", err)
	}
	if err := os.Mkdir(pfad, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	h := DeleteAccountHandler(s, ts)
	w := postKontoLoeschen(h, "m-cccc0001", `{"code":"424242"}`)
	if w.Code != 500 || !strings.Contains(w.Body.String(), "internal") {
		t.Fatalf("expected 500 internal, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "m-cccc0001") {
		t.Fatal("bei Speicherfehler muss der Nutzerordner erhalten bleiben")
	}
	got, ok := deleteCodeStore.Load("m-cccc0001")
	if !ok {
		t.Fatal("Lösch-Code muss nach gescheiterter Kaskade wieder im Store sein")
	}
	e := got.(*deleteCodeEntry)
	if e.code != "424242" || !e.expiresAt.Equal(ablauf) || e.attempts != 1 {
		t.Errorf("wieder eingesetzter Code veraendert: code=%q ablauf=%v attempts=%d", e.code, e.expiresAt, e.attempts)
	}

	if err := os.Remove(pfad); err != nil {
		t.Fatalf("remove dir: %v", err)
	}
	w = postKontoLoeschen(h, "m-cccc0001", `{"code":"424242"}`)
	if w.Code != 200 {
		t.Fatalf("Wiederholung mit demselben Code: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if nutzerOrdnerVorhanden(s, "m-cccc0001") {
		t.Error("Konto muss nach der Wiederholung geloescht sein")
	}
}

// F001: ein inzwischen neu angeforderter Code wird beim Wiedereinsetzen nie
// ueberschrieben.
func TestRestoreDeleteCode_UeberschreibtKeinenNeuerenCode(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	alt := setzeLoeschCode("anna", "111111", time.Now().Add(10*time.Minute), 0)
	e, ok := consumeDeleteCode("anna", "111111", time.Now())
	if !ok || e != alt {
		t.Fatalf("consume: ok=%v", ok)
	}
	neu := setzeLoeschCode("anna", "222222", time.Now().Add(15*time.Minute), 0)
	restoreDeleteCode("anna", e)
	if got, _ := deleteCodeStore.Load("anna"); got.(*deleteCodeEntry) != neu {
		t.Error("restoreDeleteCode hat einen neueren Code ueberschrieben")
	}
}

// F003 / AC-6: ein Lösch-Code ist einmalig — derselbe Code ein zweites Mal
// scheitert, auch wenn der Zaehler noch Luft haette.
func TestConsumeDeleteCode_IstEinmalig(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	setzeLoeschCode("anna", "919191", time.Now().Add(10*time.Minute), 0)
	if _, ok := consumeDeleteCode("anna", "919191", time.Now()); !ok {
		t.Fatal("erster Verbrauch muss gelingen")
	}
	if _, ok := consumeDeleteCode("anna", "919191", time.Now()); ok {
		t.Error("zweiter Verbrauch desselben Codes darf nicht gelingen")
	}
	if _, ok := deleteCodeStore.Load("anna"); ok {
		t.Error("verbrauchter Code muss aus dem Store sein")
	}
}

// F004 / AC-13: scheitert DeleteUser selbst, antwortet der Handler 500
// internal und der Nutzer bleibt erhalten.
func TestKontoLoeschen_DeleteUserScheitert_500OrdnerBleibt(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("als root greifen Dateirechte nicht")
	}
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	dir := filepath.Join(s.DataDir, "users", "anna")
	if err := os.Chmod(dir, 0555); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	t.Cleanup(func() { os.Chmod(dir, 0755) })

	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir())), "anna", `{"password":"`+loeschPasswort+`"}`)
	if w.Code != 500 || !strings.Contains(w.Body.String(), `"internal"`) {
		t.Fatalf("expected 500 internal, got %d: %s", w.Code, w.Body.String())
	}
	if u, err := s.LoadUser("anna"); err != nil || u == nil {
		t.Errorf("Nutzer muss nach gescheitertem DeleteUser ladbar bleiben: %v", err)
	}
}

// F006 / AC-9: der Fehlversuchszaehler haelt auch bei parallelen Versuchen —
// nach 20 gleichzeitigen Falschversuchen ist auch der richtige Code gesperrt.
func TestKontoLoeschen_ParalleleFehlversucheSperrenDenRichtigenCode(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	setzeLoeschCode("anna", "656565", time.Now().Add(10*time.Minute), 0)
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	var wg sync.WaitGroup
	start := make(chan struct{})
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			postKontoLoeschen(h, "anna", `{"code":"000000"}`)
		}()
	}
	close(start)
	wg.Wait()

	w := postKontoLoeschen(h, "anna", `{"code":"656565"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "invalid_code") {
		t.Fatalf("richtiger Code nach 20 parallelen Fehlversuchen: expected 403 invalid_code, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "anna") {
		t.Error("gesperrter Code darf nichts loeschen")
	}
}

// F007 / AC-14: eine Einloesung wird persistiert — ein neu geladener Store
// kennt den eingeloesten Token nicht mehr.
func TestTelegramTokenStore_EinloesungUeberlebtNeustartNicht(t *testing.T) {
	dir := t.TempDir()
	ts := NewTelegramTokenStore(dir)
	tok := mustIssueToken(t, ts, "anna")
	if _, ok := ts.ResolveAndDelete(tok); !ok {
		t.Fatal("frischer Token muss einloesbar sein")
	}
	neu := NewTelegramTokenStore(dir)
	if _, ok := neu.ResolveAndDelete(tok); ok {
		t.Error("eingeloester Token ist nach Neuladen wieder da (nicht persistiert)")
	}
}

// F007 / AC-14: scheitert die Persistierung, bleibt der Speicherzustand
// unveraendert — kein ungespeicherter Token im Speicher.
func TestTelegramTokenStore_IssueTokenSpeicherfehlerLaesstSpeicherUnveraendert(t *testing.T) {
	dir := t.TempDir()
	ts := NewTelegramTokenStore(dir)
	mustIssueToken(t, ts, "bertram")
	pfad := filepath.Join(dir, "telegram_tokens.json")
	if err := os.Remove(pfad); err != nil {
		t.Fatalf("remove: %v", err)
	}
	if err := os.Mkdir(pfad, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	if _, err := ts.IssueToken("anna"); err == nil {
		t.Fatal("IssueToken muss den Speicherfehler melden")
	}
	ts.mu.Lock()
	n, anna := len(ts.tokens), tokenAnzahlFuer(ts.tokens, "anna")
	ts.mu.Unlock()
	if n != 1 || anna != 0 {
		t.Errorf("Speicher nach Speicherfehler veraendert: %d Tokens, davon %d von anna", n, anna)
	}
}

// F008: Passwort hat Vorrang vor dem Code, wenn beides im Body steht.
func TestKontoLoeschen_RichtigesPasswortUndFalscherCode_Loescht(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	setzeLoeschCode("anna", "121212", time.Now().Add(10*time.Minute), 0)

	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir())), "anna",
		`{"password":"`+loeschPasswort+`","code":"000000"}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Konto muss geloescht sein")
	}
}

func TestKontoLoeschen_FalschesPasswortUndRichtigerCode_403CodeUnberuehrt(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	code := setzeLoeschCode("anna", "343434", time.Now().Add(10*time.Minute), 0)

	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir())), "anna",
		`{"password":"falsch","code":"343434"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "wrong_password") {
		t.Fatalf("expected 403 wrong_password, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Konto darf nicht geloescht sein")
	}
	if got, ok := deleteCodeStore.Load("anna"); !ok || got.(*deleteCodeEntry) != code || code.attempts != 0 {
		t.Error("Lösch-Code samt Zaehler muss bei falschem Passwort unberuehrt bleiben")
	}
}
