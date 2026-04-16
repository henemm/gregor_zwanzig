package middleware

import (
	"strings"
	"testing"
)

// TDD RED: Tests for SignSession — must FAIL until implemented.

func TestSignSessionFormat(t *testing.T) {
	// GIVEN: A userId and secret
	userId := "alice"
	secret := "test-secret-32-chars-long-enough"

	// WHEN: Signing a session
	token := SignSession(userId, secret)

	// THEN: Format is userId.timestamp.signature
	parts := strings.SplitN(token, ".", 3)
	if len(parts) != 3 {
		t.Fatalf("expected 3 dot-separated parts, got %d: %s", len(parts), token)
	}
	if parts[0] != "alice" {
		t.Errorf("first part should be userId 'alice', got '%s'", parts[0])
	}
	if len(parts[2]) == 0 {
		t.Error("signature part should not be empty")
	}
}

func TestSignSessionValidateRoundtrip(t *testing.T) {
	// GIVEN: A signed session
	secret := "test-secret-32-chars-long-enough"
	token := SignSession("bob", secret)

	// WHEN: Validating with the same secret
	userId, ok := validateSession(token, secret)

	// THEN: Returns the original userId
	if !ok {
		t.Fatal("expected session to be valid")
	}
	if userId != "bob" {
		t.Errorf("expected userId 'bob', got '%s'", userId)
	}
}

func TestSignSessionInvalidWithWrongSecret(t *testing.T) {
	// GIVEN: A signed session
	token := SignSession("charlie", "correct-secret-32-chars-long!!!")

	// WHEN: Validating with wrong secret
	_, ok := validateSession(token, "wrong-secret-32-chars-long!!!!!")

	// THEN: Validation fails
	if ok {
		t.Error("expected session to be invalid with wrong secret")
	}
}
