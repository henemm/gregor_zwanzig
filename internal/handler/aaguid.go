package handler

import "fmt"

// aaguidMap bildet bekannte AAGUID-UUID-Strings auf Klartextnamen ab.
// Quelle: https://passkeydeveloper.github.io/passkey-authenticator-aaguids/aaguids.json
// Issue #468 — AAGUID-Labels in der Passkey-Liste.
var aaguidMap = map[string]string{
	"fbfc3007-154e-4ecc-8cfb-6ef08c534b35": "iCloud Keychain",
	"dd4ec289-e01d-41c9-bb89-70fa845d4bf2": "iCloud Keychain",
	"08987058-cadc-4b81-b6e1-30de50dcbe96": "Windows Hello",
	"9ddd1817-af5a-4672-a2b9-3e3dd95000a9": "Windows Hello",
	"6028b017-b1d4-4c02-b4b3-afcdafc96bb2": "Windows Hello",
	"ee882879-721c-4913-9775-3dfcce97072a": "Google Password Manager",
	"2fc0579f-8113-47ea-b116-bb5a8db9202a": "YubiKey 5 NFC",
	"cb69481e-8ff7-4039-93ec-0a2729a154a8": "YubiKey 5",
	"ea9b8d66-4d01-1d21-3ce4-b6b48cb575d4": "YubiKey 5 Series",
	"9f77e279-a6e2-4d58-b700-31e5943c6a98": "YubiKey Security Key NFC",
	"d548826e-79b4-db40-a3d8-11116f7e8349": "Bitwarden",
	"bada5566-a7aa-401f-bd96-45619a55120d": "1Password",
	"53414d53-554e-4700-0000-000000000000": "Samsung Pass",
	"b93fd961-f2e6-462f-b122-82002247de78": "Android Fingerprint",
	"b84e4048-15dc-4dd0-8640-f4f60813c8af": "Google Phone",
	"6e9ac0b4-c626-4e0a-869f-6e3bf5e72291": "KeePassXC",
	"531126d6-e717-415c-9320-3d9aa6981239": "Dashlane",
	"adce0002-35bc-c60a-648b-0b25f1f05503": "Chrome on Mac",
	"2ffd6452-01da-471f-821b-ea4bf6c8676a": "Feitian ePass FIDO2",
	"12ded745-4bed-47d4-abaa-e713f51d6393": "Feitian BioPass FIDO2",
	"39a5647e-1853-446c-a1f6-a79bae9f5bc7": "IDmelon",
	"bbc3b584-ddf7-4c5d-9c6f-0c8dae524084": "Keeper",
	"87dbc5a1-4c94-4dc8-8a47-97d800fd1f3c": "Enpass",
	"20f0be98-9af9-986a-4b42-8eca4acb28e4": "Nitrokey FIDO2",
}

// aaguidToName gibt den Klartextnamen eines Authenticators zurück.
// Bei Zero-AAGUID (alle Bytes 0x00), unbekannter AAGUID oder falscher Länge → "".
// Pure Funktion, kein I/O, keine Seiteneffekte.
func aaguidToName(b []byte) string {
	if len(b) != 16 {
		return ""
	}
	key := fmt.Sprintf("%08x-%04x-%04x-%04x-%012x",
		b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
	return aaguidMap[key]
}
