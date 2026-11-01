GZ_SMTP_HOST="op://Private/Gregor Zwanzig SMTP/host"
GZ_SMTP_PORT="op://Private/Gregor Zwanzig SMTP/port"
GZ_SMTP_USER="op://Private/Gregor Zwanzig SMTP/username"
GZ_SMTP_PASS="op://Private/Gregor Zwanzig SMTP/password"
GZ_MAIL_FROM="op://Private/Gregor Zwanzig SMTP/mail_from"
GZ_MAIL_TO="op://Private/Gregor Zwanzig SMTP/mail_to"
GZ_PO_EMAIL="op://Private/Gregor Zwanzig SMTP/mail_to"

# Weitere Secrets (#2163 Scheibe 2). Echte 1Password-Pfade sind noch unbekannt
# und werden nicht erfunden; Waechter: tests/unit/test_env_tpl_secret_drift.py
# Go-Config (internal/config/config.go)
# GZ_SESSION_SECRET=  (1Password-Eintrag noch anzulegen)
# GZ_CORE_SHARED_SECRET=  (1Password-Eintrag noch anzulegen)
# GZ_AUTH_PASS=  (1Password-Eintrag noch anzulegen)
# GZ_GOOGLE_SMTP_PASS=  (1Password-Eintrag noch anzulegen)
# GZ_FALLBACK_SMTP_PASS=  (1Password-Eintrag noch anzulegen)
# GZ_GOOGLE_CLIENT_SECRET=  (1Password-Eintrag noch anzulegen)
# GZ_TELEGRAM_WEBHOOK_SECRET=  (1Password-Eintrag noch anzulegen) (Go liest auch unpräfixiert)
# GZ_SEVEN_WEBHOOK_PATH_SECRET=  (1Password-Eintrag noch anzulegen) (Go liest auch unpräfixiert)
# GZ_SEVEN_WEBHOOK_SIGNING_KEY=  (1Password-Eintrag noch anzulegen) (Go liest auch unpräfixiert)
# GZ_STALWART_WEBHOOK_PATH_SECRET=  (1Password-Eintrag noch anzulegen) (Go liest auch unpräfixiert)
# GZ_STALWART_WEBHOOK_SECRET=  (1Password-Eintrag noch anzulegen) (Go liest auch unpräfixiert)
# GZ_STATUS_TOKEN=  (1Password-Eintrag noch anzulegen)
# Python-Settings (src/app/config.py)
# GZ_IMAP_PASS=  (1Password-Eintrag noch anzulegen)
# GZ_TEST_SMTP_PASS=  (1Password-Eintrag noch anzulegen)
# GZ_TEST_IMAP_PASS=  (1Password-Eintrag noch anzulegen)
# GZ_SEVEN_API_KEY=  (1Password-Eintrag noch anzulegen)
# GZ_SEVEN_SANDBOX_KEY=  (1Password-Eintrag noch anzulegen)
# GZ_TELEGRAM_BOT_TOKEN=  (1Password-Eintrag noch anzulegen)
# GZ_TELEGRAM_TEST_BOT_TOKEN=  (1Password-Eintrag noch anzulegen)
# Python direkt per os.environ (providers/meteofrance.py, official_alerts/*)
# GZ_METEOFRANCE_APIKEY=  (1Password-Eintrag noch anzulegen)
