package middleware

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"
)

type contextKey string

const userIDContextKey contextKey = "userId"

func AuthMiddleware(secret string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path == "/api/health" || r.URL.Path == "/api/scheduler/status" ||
				r.URL.Path == "/api/auth/register" || r.URL.Path == "/api/auth/login" {
				next.ServeHTTP(w, r)
				return
			}

			cookie, err := r.Cookie("gz_session")
			if err != nil {
				http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
				return
			}

			userId, ok := validateSession(cookie.Value, secret)
			if !ok {
				http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
				return
			}

			ctx := context.WithValue(r.Context(), userIDContextKey, userId)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

func UserIDFromContext(ctx context.Context) string {
	uid, _ := ctx.Value(userIDContextKey).(string)
	return uid
}

// SignSession creates a signed session token compatible with SvelteKit validation.
// Format: {userId}.{timestamp}.{hmacSig}
func SignSession(userId, secret string) string {
	ts := time.Now().Unix()
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(fmt.Sprintf("%s:%d", userId, ts)))
	sig := hex.EncodeToString(mac.Sum(nil))
	return fmt.Sprintf("%s.%d.%s", userId, ts, sig)
}

// ContextWithUserID returns a new context with the given userId set.
// Used by AuthMiddleware internally and by tests to simulate authenticated requests.
func ContextWithUserID(ctx context.Context, userId string) context.Context {
	return context.WithValue(ctx, userIDContextKey, userId)
}

func validateSession(value, secret string) (string, bool) {
	parts := strings.SplitN(value, ".", 3)
	if len(parts) != 3 {
		return "", false
	}

	userId, tsStr, sig := parts[0], parts[1], parts[2]
	if userId == "" || tsStr == "" || sig == "" {
		return "", false
	}

	ts, err := strconv.ParseInt(tsStr, 10, 64)
	if err != nil {
		return "", false
	}

	if time.Now().Unix()-ts > 86400 {
		return "", false
	}

	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(fmt.Sprintf("%s:%d", userId, ts)))
	expected := hex.EncodeToString(mac.Sum(nil))

	if !hmac.Equal([]byte(sig), []byte(expected)) {
		return "", false
	}

	return userId, true
}
