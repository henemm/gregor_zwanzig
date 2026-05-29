package handler

// ResetOTPStoreForTest empties the package-level otpStore used by the
// magic-link handlers. Tests call this via t.Cleanup to keep their state
// isolated. Lives in *_test.go so it is not part of the production binary.
func ResetOTPStoreForTest() {
	otpStore.Range(func(k, _ any) bool {
		otpStore.Delete(k)
		return true
	})
}
