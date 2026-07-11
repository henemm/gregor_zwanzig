package store

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
)

// TDD GREEN — Issue #1219 Scheibe 2a-i: Token-Store fuer den
// E-Mail-Bestätigungslink-Versand. Spec:
// docs/specs/modules/fix_1219_verify_flow_2a.md (AC-1, AC-7, AC-8, AC-9).

func TestSaveVerificationTokenCreatesFile(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	hash, _ := bcrypt.GenerateFromPassword([]byte("plaintext-token"), bcrypt.MinCost)
	token := model.EmailVerificationToken{TokenHash: string(hash), ExpiresAt: time.Now().Add(24 * time.Hour)}
	if err := s.SaveVerificationToken("alice", token); err != nil {
		t.Fatalf("SaveVerificationToken error: %v", err)
	}

	path := filepath.Join(tmpDir, "users", "alice", "email_verification.json")
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("AC-1: email_verification.json should exist: %v", err)
	}
}

func TestLoadVerificationTokenReturnsSavedToken(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	hash, _ := bcrypt.GenerateFromPassword([]byte("plaintext-token"), bcrypt.MinCost)
	expiry := time.Now().Add(24 * time.Hour)
	saved := model.EmailVerificationToken{TokenHash: string(hash), ExpiresAt: expiry}
	if err := s.SaveVerificationToken("bob", saved); err != nil {
		t.Fatalf("SaveVerificationToken error: %v", err)
	}

	loaded, err := s.LoadVerificationToken("bob")
	if err != nil || loaded == nil {
		t.Fatalf("LoadVerificationToken failed: %v", err)
	}
	if err := bcrypt.CompareHashAndPassword([]byte(loaded.TokenHash), []byte("plaintext-token")); err != nil {
		t.Errorf("loaded token hash does not verify against original plaintext: %v", err)
	}
}

func TestLoadVerificationTokenMissingReturnsNil(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	loaded, err := s.LoadVerificationToken("nobody")
	if err != nil {
		t.Fatalf("expected nil error for missing token, got: %v", err)
	}
	if loaded != nil {
		t.Errorf("expected nil token for missing user, got: %+v", loaded)
	}
}

// AC-7: ein zweiter SaveVerificationToken-Aufruf überschreibt den ersten
// vollständig — der alte Klartext-Token passt danach nicht mehr.
func TestSaveVerificationToken_SecondCallInvalidatesFirst_AC7(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	hash1, _ := bcrypt.GenerateFromPassword([]byte("token-one"), bcrypt.MinCost)
	token1 := model.EmailVerificationToken{TokenHash: string(hash1), ExpiresAt: time.Now().Add(24 * time.Hour)}
	if err := s.SaveVerificationToken("carla", token1); err != nil {
		t.Fatalf("first SaveVerificationToken failed: %v", err)
	}

	hash2, _ := bcrypt.GenerateFromPassword([]byte("token-two"), bcrypt.MinCost)
	token2 := model.EmailVerificationToken{TokenHash: string(hash2), ExpiresAt: time.Now().Add(24 * time.Hour)}
	if err := s.SaveVerificationToken("carla", token2); err != nil {
		t.Fatalf("second SaveVerificationToken failed: %v", err)
	}

	loaded, err := s.LoadVerificationToken("carla")
	if err != nil || loaded == nil {
		t.Fatalf("LoadVerificationToken failed: %v", err)
	}
	if err := bcrypt.CompareHashAndPassword([]byte(loaded.TokenHash), []byte("token-one")); err == nil {
		t.Error("AC-7: alter Token (token-one) darf nach Überschreiben NICHT mehr passen")
	}
	if err := bcrypt.CompareHashAndPassword([]byte(loaded.TokenHash), []byte("token-two")); err != nil {
		t.Errorf("AC-7: neuer Token (token-two) muss passen, war: %v", err)
	}
}

// AC-8: zwei verschiedene Nutzer haben vollständig isolierte Token-Dateien.
func TestSaveVerificationToken_IsolatedPerUser_AC8(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	hashA, _ := bcrypt.GenerateFromPassword([]byte("token-a"), bcrypt.MinCost)
	hashB, _ := bcrypt.GenerateFromPassword([]byte("token-b"), bcrypt.MinCost)
	s.SaveVerificationToken("userA", model.EmailVerificationToken{TokenHash: string(hashA), ExpiresAt: time.Now().Add(24 * time.Hour)})
	s.SaveVerificationToken("userB", model.EmailVerificationToken{TokenHash: string(hashB), ExpiresAt: time.Now().Add(24 * time.Hour)})

	pathA := filepath.Join(tmpDir, "users", "userA", "email_verification.json")
	pathB := filepath.Join(tmpDir, "users", "userB", "email_verification.json")
	if _, err := os.Stat(pathA); err != nil {
		t.Errorf("AC-8: userA token file missing: %v", err)
	}
	if _, err := os.Stat(pathB); err != nil {
		t.Errorf("AC-8: userB token file missing: %v", err)
	}

	loadedA, _ := s.LoadVerificationToken("userA")
	if err := bcrypt.CompareHashAndPassword([]byte(loadedA.TokenHash), []byte("token-b")); err == nil {
		t.Error("AC-8: userA darf nicht durch userB's Token verifizierbar sein — Cross-User-Leck")
	}
}

func TestDeleteVerificationTokenRemovesFile(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	hash, _ := bcrypt.GenerateFromPassword([]byte("token"), bcrypt.MinCost)
	s.SaveVerificationToken("dana", model.EmailVerificationToken{TokenHash: string(hash), ExpiresAt: time.Now().Add(24 * time.Hour)})

	if err := s.DeleteVerificationToken("dana"); err != nil {
		t.Fatalf("DeleteVerificationToken error: %v", err)
	}
	loaded, err := s.LoadVerificationToken("dana")
	if err != nil {
		t.Fatalf("LoadVerificationToken after delete error: %v", err)
	}
	if loaded != nil {
		t.Error("token should be gone after DeleteVerificationToken")
	}
}
