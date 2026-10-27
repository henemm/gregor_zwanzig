"""Versionierte Authentication-Results-Header-Fixtures (Issue #2143).

Format empirisch verifiziert in der Analyse-Phase von #2143 durch direkte
Pruefung der Produktiv-Stalwart-Instanz (/home/hem/henemm-infra/stalwart,
Docker-Container stalwart-mail: Config, Logs, Blob-Store): Stalwart fuehrt
SPF/DKIM/DMARC-Checks auf jeder anonymen Inbound-SMTP:25-Verbindung durch
(Stock-Verhalten, keine explizite Config) und PREPENDET einen
``Authentication-Results: <authserv-id>; dkim=...; spf=...; dmarc=...``-Header
(RFC 8601) an zugestellte Nachrichten — verifiziert an echten zugestellten
Mails. henemm.com publiziert ``DMARC p=reject``. Die Checks sind advisory
(kein Hard-Reject bei Fail), daher muss die Anwendung selbst auswerten.

TEST_AUTHSERV_ID ist bewusst NICHT der Prod-Hostname (mail.henemm.com),
sondern ein testeigener Wert — Tests duerfen nicht zufaellig durch eine
Uebereinstimmung mit einem Produktions-Default gruen werden, sondern nur
weil ``Settings.mail_server_hostname`` explizit auf diesen Wert gesetzt ist.
"""

TEST_AUTHSERV_ID = "mail.test.example"

# Regulaerer, gueltiger Absender — SPF und DKIM beide pass.
AR_PASS = (
    f"{TEST_AUTHSERV_ID}; "
    "dkim=pass header.d=henemm.com header.s=stalwart header.a=rsa-sha256; "
    "spf=pass smtp.mailfrom=user@henemm.com smtp.helo=mail.test.example; "
    "dmarc=pass header.from=henemm.com"
)

# SPF/DKIM beide fail — gefaelschter Envelope-Absender / fremde IP.
AR_FAIL = (
    f"{TEST_AUTHSERV_ID}; "
    "dkim=fail header.d=henemm.com header.s=stalwart header.a=rsa-sha256; "
    "spf=fail smtp.mailfrom=user@henemm.com smtp.helo=evil.example.com; "
    "dmarc=fail header.from=henemm.com"
)

# authserv-id gehoert einem FREMDEN Mailserver — ein Header, der (bewusst
# oder durch Fehlkonfiguration) nicht vom eigenen Stalwart stammt.
AR_FOREIGN_AUTHSERV = (
    "mx.example-other-provider.net; "
    "dkim=pass header.d=henemm.com header.s=stalwart header.a=rsa-sha256; "
    "spf=pass smtp.mailfrom=user@henemm.com smtp.helo=mail.test.example; "
    "dmarc=pass header.from=henemm.com"
)

# Nur SPF pass, weder dkim=pass noch dmarc=pass (Alignment-Ersatz) — muss
# trotz spf=pass ablehnen (AC verlangt spf=pass UND (dkim=pass ODER
# dmarc=pass)).
AR_SPF_ONLY = (
    f"{TEST_AUTHSERV_ID}; "
    "dkim=none header.d=henemm.com header.s=stalwart header.a=rsa-sha256; "
    "spf=pass smtp.mailfrom=user@henemm.com smtp.helo=mail.test.example; "
    "dmarc=none header.from=henemm.com"
)

# DMARC-Alignment als DKIM-Ersatz: spf=pass + dmarc=pass, dkim=none — darf
# laut Spec durchgehen (dmarc=pass zaehlt als Alignment-Ersatz fuer dkim).
AR_SPF_DMARC_ALIGNMENT = (
    f"{TEST_AUTHSERV_ID}; "
    "dkim=none header.d=henemm.com header.s=stalwart header.a=rsa-sha256; "
    "spf=pass smtp.mailfrom=user@henemm.com smtp.helo=mail.test.example; "
    "dmarc=pass header.from=henemm.com"
)
