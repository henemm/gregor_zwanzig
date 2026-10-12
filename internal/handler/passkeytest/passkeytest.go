// Package passkeytest ist ein reines Test-Hilfspaket: ein ECDSA-P-256-Authenticator
// mit "none"-Attestation, der echte Attestation-/Assertion-Objekte baut, die
// go-webauthn kryptographisch prueft. Wird NUR aus *_test.go importiert (nie aus
// cmd/ oder Produktivcode), damit es nicht ins Binary gelinkt wird (#2159).
package passkeytest

import (
	"bytes"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"testing"

	"github.com/fxamacker/cbor/v2"
	"github.com/go-webauthn/webauthn/webauthn"
)

type Authenticator struct {
	RPID    string
	Origin  string
	PrivKey *ecdsa.PrivateKey
	CredID  []byte
	AAGUID  []byte
}

func NewAuthenticator(t *testing.T, rpID, origin string) *Authenticator {
	t.Helper()
	priv, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatalf("ecdsa keygen: %v", err)
	}
	credID := make([]byte, 32)
	if _, err := rand.Read(credID); err != nil {
		t.Fatalf("rand credID: %v", err)
	}
	return &Authenticator{
		RPID:    rpID,
		Origin:  origin,
		PrivKey: priv,
		CredID:  credID,
		AAGUID:  make([]byte, 16), // zero AAGUID (none-format authenticator)
	}
}

// cosePublicKey returns the CBOR-encoded COSE_Key for the EC2 public key.
func (a *Authenticator) cosePublicKey(t *testing.T) []byte {
	t.Helper()
	x := a.PrivKey.PublicKey.X.Bytes()
	y := a.PrivKey.PublicKey.Y.Bytes()
	// pad to 32 bytes
	x = leftPad(x, 32)
	y = leftPad(y, 32)
	// COSE_Key map with int keys (canonical CTAP2 encoding):
	// 1 (kty)  = 2 (EC2)
	// 3 (alg)  = -7 (ES256)
	// -1 (crv) = 1 (P-256)
	// -2 (x)   = x-coord
	// -3 (y)   = y-coord
	m := map[int]interface{}{
		1:  2,
		3:  -7,
		-1: 1,
		-2: x,
		-3: y,
	}
	enc, err := cbor.CTAP2EncOptions().EncMode()
	if err != nil {
		t.Fatalf("cbor enc mode: %v", err)
	}
	out, err := enc.Marshal(m)
	if err != nil {
		t.Fatalf("cbor marshal cose key: %v", err)
	}
	return out
}

// buildAuthenticatorData constructs the binary authenticator data blob.
// withAttested=true → includes AttestedCredentialData (registration case).
func (a *Authenticator) buildAuthenticatorData(t *testing.T, withAttested bool, signCount uint32) []byte {
	t.Helper()
	rpidHash := sha256.Sum256([]byte(a.RPID))

	var flags byte
	flags |= 0x01 // UP (user present)
	flags |= 0x04 // UV (user verified)
	if withAttested {
		flags |= 0x40 // AT (attested credential data included)
	}

	buf := &bytes.Buffer{}
	buf.Write(rpidHash[:])
	buf.WriteByte(flags)
	scBuf := make([]byte, 4)
	binary.BigEndian.PutUint32(scBuf, signCount)
	buf.Write(scBuf)

	if withAttested {
		buf.Write(a.AAGUID) // 16 bytes
		credLen := make([]byte, 2)
		binary.BigEndian.PutUint16(credLen, uint16(len(a.CredID)))
		buf.Write(credLen)
		buf.Write(a.CredID)
		buf.Write(a.cosePublicKey(t))
	}
	return buf.Bytes()
}

// MakeAttestationResponse constructs the JSON body the browser would POST to
// /register/finish: { id, rawId, type, response: { clientDataJSON, attestationObject } }.
func (a *Authenticator) MakeAttestationResponse(t *testing.T, challengeB64URL string) []byte {
	t.Helper()
	clientData := map[string]interface{}{
		"type":      "webauthn.create",
		"challenge": challengeB64URL,
		"origin":    a.Origin,
	}
	clientDataJSON, err := json.Marshal(clientData)
	if err != nil {
		t.Fatalf("clientData marshal: %v", err)
	}

	authData := a.buildAuthenticatorData(t, true, 0)

	// AttestationObject CBOR: { fmt: "none", attStmt: {}, authData: <bytes> }
	attObj := map[string]interface{}{
		"fmt":      "none",
		"attStmt":  map[string]interface{}{},
		"authData": authData,
	}
	enc, _ := cbor.CTAP2EncOptions().EncMode()
	attObjBytes, err := enc.Marshal(attObj)
	if err != nil {
		t.Fatalf("attObj marshal: %v", err)
	}

	credIDB64 := base64.RawURLEncoding.EncodeToString(a.CredID)
	body := map[string]interface{}{
		"id":    credIDB64,
		"rawId": credIDB64,
		"type":  "public-key",
		"response": map[string]interface{}{
			"clientDataJSON":    base64.RawURLEncoding.EncodeToString(clientDataJSON),
			"attestationObject": base64.RawURLEncoding.EncodeToString(attObjBytes),
		},
	}
	out, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("body marshal: %v", err)
	}
	return out
}

// MakeAssertionResponse signs an assertion for the given challenge and returns
// the JSON body for /login/finish.
func (a *Authenticator) MakeAssertionResponse(t *testing.T, challengeB64URL string, signCount uint32) []byte {
	t.Helper()
	clientData := map[string]interface{}{
		"type":      "webauthn.get",
		"challenge": challengeB64URL,
		"origin":    a.Origin,
	}
	clientDataJSON, err := json.Marshal(clientData)
	if err != nil {
		t.Fatalf("clientData marshal: %v", err)
	}
	clientDataHash := sha256.Sum256(clientDataJSON)

	authData := a.buildAuthenticatorData(t, false, signCount)

	// Signature over authData || sha256(clientDataJSON), ASN.1 DER encoded.
	signedPayload := append([]byte{}, authData...)
	signedPayload = append(signedPayload, clientDataHash[:]...)
	digest := sha256.Sum256(signedPayload)
	sig, err := ecdsa.SignASN1(rand.Reader, a.PrivKey, digest[:])
	if err != nil {
		t.Fatalf("ecdsa sign: %v", err)
	}

	credIDB64 := base64.RawURLEncoding.EncodeToString(a.CredID)
	body := map[string]interface{}{
		"id":    credIDB64,
		"rawId": credIDB64,
		"type":  "public-key",
		"response": map[string]interface{}{
			"clientDataJSON":    base64.RawURLEncoding.EncodeToString(clientDataJSON),
			"authenticatorData": base64.RawURLEncoding.EncodeToString(authData),
			"signature":         base64.RawURLEncoding.EncodeToString(sig),
			"userHandle":        base64.RawURLEncoding.EncodeToString([]byte("placeholder")),
		},
	}
	out, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("body marshal: %v", err)
	}
	return out
}

func leftPad(in []byte, n int) []byte {
	if len(in) >= n {
		return in
	}
	out := make([]byte, n)
	copy(out[n-len(in):], in)
	return out
}

func NewWebAuthn(t *testing.T, rpID, origin string) *webauthn.WebAuthn {
	t.Helper()
	wa, err := webauthn.New(&webauthn.Config{
		RPID:          rpID,
		RPDisplayName: "Gregor Zwanzig Test",
		RPOrigins:     []string{origin},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	return wa
}

// MakeAssertionResponseDiscoverable builds an assertion body for the Discoverable
// flow where userHandle carries the real user ID (not "placeholder").
func (a *Authenticator) MakeAssertionResponseDiscoverable(t *testing.T, challengeB64URL string, signCount uint32, userID string) []byte {
	t.Helper()
	clientData := map[string]interface{}{
		"type":      "webauthn.get",
		"challenge": challengeB64URL,
		"origin":    a.Origin,
	}
	clientDataJSON, err := json.Marshal(clientData)
	if err != nil {
		t.Fatalf("clientData marshal: %v", err)
	}
	clientDataHash := sha256.Sum256(clientDataJSON)

	authData := a.buildAuthenticatorData(t, false, signCount)

	signedPayload := append([]byte{}, authData...)
	signedPayload = append(signedPayload, clientDataHash[:]...)
	digest := sha256.Sum256(signedPayload)
	sig, err := ecdsa.SignASN1(rand.Reader, a.PrivKey, digest[:])
	if err != nil {
		t.Fatalf("ecdsa sign: %v", err)
	}

	credIDB64 := base64.RawURLEncoding.EncodeToString(a.CredID)
	body := map[string]interface{}{
		"id":    credIDB64,
		"rawId": credIDB64,
		"type":  "public-key",
		"response": map[string]interface{}{
			"clientDataJSON":    base64.RawURLEncoding.EncodeToString(clientDataJSON),
			"authenticatorData": base64.RawURLEncoding.EncodeToString(authData),
			"signature":         base64.RawURLEncoding.EncodeToString(sig),
			// Real user ID as userHandle — required by DiscoverableUserHandler
			"userHandle": base64.RawURLEncoding.EncodeToString([]byte(userID)),
		},
	}
	out, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("body marshal: %v", err)
	}
	return out
}
