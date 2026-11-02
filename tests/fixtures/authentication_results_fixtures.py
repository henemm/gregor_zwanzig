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

#2252 (Spec v1.7, Abschnitt 5a): echte Prod-Header H1–H4 (authserv-id
``PROD_AUTHSERV_ID = "mail.henemm.com"``, Stalwart-Produktivinstanz am
2.11.2026) plus synthetische Grenzfaelle fuer Tokenizer, Quote-Sperre,
SPF-Scope und Domain-Ausrichtung. ``AR_PASS`` ist auf ``henemm.com``
ausgerichtet; fuer Absender anderer Domains ``ar_pass_for(<From-Adresse>)``.
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

# Nur SPF pass, weder dkim=pass noch dmarc=pass. Bis v1.5 abgelehnt (Regel
# spf=pass UND (dkim=pass ODER dmarc=pass)). Seit #2252 (Spec 5a, Variante V3,
# Regel b) AKZEPTIERT, wenn die Domain von smtp.mailfrom zur From:-Domain
# (henemm.com) ausgerichtet ist; bei fremder From:-Domain abgelehnt.
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


def ar_pass_for(addr_or_domain: str) -> str:
    """Wie ``AR_PASS`` (authserv ``TEST_AUTHSERV_ID``), aber ALLE Domains
    (``dkim header.d``, Domain von ``smtp.mailfrom``, ``dmarc header.from``)
    sind die Domain der uebergebenen Adresse (oder die uebergebene Domain).

    #2252 (Spec 5a, Domain-Ausrichtung): ein Header ist nur noch dann ein
    gueltiger Nachweis, wenn er zur ``From:``-Domain der jeweiligen Mail
    gehoert. Tests mit Absendern ausserhalb von ``henemm.com`` brauchen
    deshalb einen auf IHRE Domain ausgerichteten Header — sonst wuerden
    Annahmetests nach dem Fix brechen und Ablehnungstests nur noch wegen
    fehlender Ausrichtung (statt am eigentlich geprueften Waechter) rot.
    Kein ``"``, genau ein ``spf``-Segment mit ``smtp.mailfrom``.
    """
    domain = addr_or_domain.rpartition("@")[2].strip().lower()
    return (
        f"{TEST_AUTHSERV_ID}; "
        f"dkim=pass header.d={domain} header.s=stalwart header.a=rsa-sha256; "
        f"spf=pass smtp.mailfrom=user@{domain} smtp.helo=mail.test.example; "
        f"dmarc=pass header.from={domain}"
    )


# ---------------------------------------------------------------------------
# #2252 (Spec 5a, v1.7): ECHTE Header der Produktiv-Stalwart-Instanz vom
# 2.11.2026, woertlich als Python-repr aus der Spec uebernommen (inkl. der
# ``\r\n\t``-Faltungen, wie IMAP sie liefert). authserv-id = mail.henemm.com.
# ---------------------------------------------------------------------------

PROD_AUTHSERV_ID = "mail.henemm.com"

# H1 normal (Positiv): zuerst spf=helo (permerror), dann spf=mailfrom (pass), dmarc=pass
AR_H1_NORMAL = 'mail.henemm.com;\r\n\tspf=permerror (mail.henemm.com: unable to verify SPF record for postmaster@[127.0.1.1]) smtp.helo=[127.0.1.1];\r\n\tspf=pass (mail.henemm.com: domain of probe2252-b5877b3d@henemm.com designates 178.104.143.19 as permitted sender) smtp.mailfrom=probe2252-b5877b3d@henemm.com;\r\n\tiprev=pass policy.iprev=178.104.143.19;\r\n\tdmarc=pass header.from=henemm.com policy.dmarc=quarantine'
# H2 Injektion ueber quoted Local-Part (Reject)
AR_H2_INJECTION = 'mail.henemm.com;\r\n\tspf=permerror (mail.henemm.com: unable to verify SPF record for postmaster@[127.0.1.1]) smtp.helo=[127.0.1.1];\r\n\tspf=none (mail.henemm.com: no SPF records found for xdkimpassspfpasssmtp.mailfroma@spoofer-domain.invalid) smtp.mailfrom="x;dkim=pass;spf=pass smtp.mailfrom=a@spoofer-domain.invalid";\r\n\tiprev=pass policy.iprev=178.104.143.19;\r\n\tdmarc=fail (policy not aligned) header.from=henemm.com policy.dmarc=quarantine'
# H3 Injektion mit escaped quote (Reject)
AR_H3_ESCAPED_QUOTE = 'mail.henemm.com;\r\n\tspf=permerror (mail.henemm.com: unable to verify SPF record for postmaster@[127.0.1.1]) smtp.helo=[127.0.1.1];\r\n\tspf=none (mail.henemm.com: no SPF records found for xdkimpassspfpasssmtp.mailfroma@spoofer-domain.invalid) smtp.mailfrom="x\\";dkim=pass;spf=pass smtp.mailfrom=a@spoofer-domain.invalid";\r\n\tiprev=pass policy.iprev=178.104.143.19;\r\n\tdmarc=fail (policy not aligned) header.from=henemm.com policy.dmarc=quarantine'
# H4 echte Resend-Mail (Positiv, From gregor_zwanzig@henemm.com): SPF ueber Subdomain send.henemm.com,
# zwei DKIM-Segmente (eines nicht ausgerichtet: amazonses.com), dmarc=pass
AR_H4_RESEND = 'mail.henemm.com;\r\n\tdkim=pass header.d=henemm.com header.s=resend header.b=a7IkBGaV;\r\n\tdkim=pass header.d=amazonses.com header.s=shh3fegwg5fppqsuzphvschd53n6ihuv header.b=tYFaYz8D;\r\n\tspf=none (mail.henemm.com: no SPF records found for postmaster@a3-16.smtp-out.eu-west-1.amazonses.com) smtp.helo=a3-16.smtp-out.eu-west-1.amazonses.com;\r\n\tspf=pass (mail.henemm.com: domain of 0102019f435a3b82-0d0dd774-19eb-4b66-868b-fc1b2f8be0a6-000000@send.henemm.com designates 54.240.3.16 as permitted sender) smtp.mailfrom=0102019f435a3b82-0d0dd774-19eb-4b66-868b-fc1b2f8be0a6-000000@send.henemm.com;\r\n\tiprev=pass policy.iprev=54.240.3.16;\r\n\tdmarc=pass header.from=henemm.com policy.dmarc=quarantine'

# Erwartete Anzahl Segmente (ohne authserv-id) je echtem Header — Pruefwert
# fuer den Tokenizer (H2/H3: das eingeschleuste ``dkim=pass`` ist KEIN Segment).
H1_SEGMENT_COUNT = 4
H2_SEGMENT_COUNT = 4
H3_SEGMENT_COUNT = 4
H4_SEGMENT_COUNT = 6

# Woertlicher quoted-string-Inhalt (ohne umschliessende Quotes, Escapes aufgeloest)
H2_INJECTED_MAILFROM = "x;dkim=pass;spf=pass smtp.mailfrom=a@spoofer-domain.invalid"
H3_INJECTED_MAILFROM = 'x";dkim=pass;spf=pass smtp.mailfrom=a@spoofer-domain.invalid'

# Luecke 2 (keine Domain-Ausrichtung): SPF/DKIM bestehen fuer die Domain des
# Angreifers, DMARC fuer die Opfer-Domain scheitert. From: <...@opfer.example>.
AR_FOREIGN_DOMAIN_ALIGNED = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=a@attacker.example; "
    "dkim=pass header.d=attacker.example; dmarc=fail header.from=opfer.example"
)

# H1 mit vertauschter Reihenfolge der beiden spf-Segmente (mailfrom VOR helo).
# Heute gewinnt das letzte (helo permerror) — nach #2252 ohne Wirkung (AC-10).
AR_H1_SPF_SWAPPED = 'mail.henemm.com;\r\n\tspf=pass (mail.henemm.com: domain of probe2252-b5877b3d@henemm.com designates 178.104.143.19 as permitted sender) smtp.mailfrom=probe2252-b5877b3d@henemm.com;\r\n\tspf=permerror (mail.henemm.com: unable to verify SPF record for postmaster@[127.0.1.1]) smtp.helo=[127.0.1.1];\r\n\tiprev=pass policy.iprev=178.104.143.19;\r\n\tdmarc=pass header.from=henemm.com policy.dmarc=quarantine'

# mailfrom-Segment spf=fail, helo-Segment spf=pass, kein dkim/dmarc-pass (AC-10 Gegenfall).
# Bewusst helo ZULETZT: das naive "letztes gewinnt" liefert heute spf=pass.
# Das einzige dkim=pass ist NICHT ausgerichtet (amazonses.com) — heute reicht es
# (zusammen mit dem helo-spf=pass) fuer die Annahme, nach #2252 nicht mehr.
AR_MAILFROM_FAIL_HELO_PASS = (
    f"{TEST_AUTHSERV_ID};\r\n\tspf=fail smtp.mailfrom=user@henemm.com;\r\n"
    "\tspf=pass smtp.helo=mail.henemm.com;\r\n"
    "\tdkim=pass header.d=amazonses.com;\r\n"
    "\tdmarc=fail header.from=henemm.com"
)

# AC-11-Fixtures: jeweils GENAU EIN mehrdeutiges/scope-loses Merkmal, das bei
# korrekter Regel nicht zaehlt; daneben nur Nicht-Ausgerichtetes (amazonses.com,
# reine helo-Segmente). Heute (naiver Parser, flaches Dict) sind sie alle "pass".

# AC-11: zwei spf-Segmente mit smtp.mailfrom, beide pass und ausgerichtet.
AR_TWO_MAILFROM_BOTH_PASS = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=a@henemm.com; "
    "spf=pass smtp.mailfrom=b@henemm.com; dkim=pass header.d=amazonses.com; "
    "dmarc=none header.from=henemm.com"
)

# AC-11: spf=pass ganz ohne Scope-Parameter.
AR_SPF_PASS_NO_SCOPE = (
    f"{TEST_AUTHSERV_ID}; spf=pass; dkim=pass header.d=amazonses.com; "
    "dmarc=none header.from=henemm.com"
)

# AC-11: dkim=pass ohne header.d (SPF nur helo, DMARC none).
AR_DKIM_PASS_NO_D = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.helo=mail.henemm.com; "
    "dkim=pass header.s=stalwart; dmarc=none header.from=henemm.com"
)

# AC-11: dmarc=pass ohne header.from (SPF nur helo, DKIM none).
AR_DMARC_PASS_NO_FROM = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.helo=mail.henemm.com; "
    "dkim=none header.d=henemm.com; dmarc=pass policy.dmarc=quarantine"
)

# AC-11: zwei dmarc-Segmente (beide pass, ausgerichtet), SPF nur helo, DKIM none.
AR_TWO_DMARC = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.helo=mail.henemm.com; "
    "dkim=none header.d=henemm.com; dmarc=pass header.from=henemm.com; "
    "dmarc=pass header.from=henemm.com"
)

# AC-8: unbalancierte Quote (sonst voll gueltig/ausgerichtet).
AR_UNBALANCED_QUOTE = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=\"user@henemm.com; "
    "dkim=pass header.d=henemm.com; dmarc=pass header.from=henemm.com"
)

# AC-8: ueberzaehlige schliessende Klammer, KEIN ``"`` (prueft den
# Parse-Fehler-Pfad unabhaengig von der Quote-Sperre). Ein nachsichtiger
# Tokenizer, der das ``)`` ignoriert, wuerde ueber dkim/dmarc annehmen.
AR_UNBALANCED_PAREN = (
    f"{TEST_AUTHSERV_ID}; spf=pass (domain of user@henemm.com) "
    "smtp.mailfrom=user@henemm.com); dkim=pass header.d=henemm.com; "
    "dmarc=pass header.from=henemm.com"
)

# AC-8: nicht geschlossene Klammer, KEIN ``"``.
AR_UNCLOSED_PAREN = (
    f"{TEST_AUTHSERV_ID}; dkim=pass header.d=henemm.com; dmarc=pass header.from=henemm.com; "
    "spf=pass (mail.test.example: domain of user@henemm.com smtp.mailfrom=user@henemm.com"
)

# AC-8: harmloses, BALANCIERTES Quote-Paar nur im Kommentar, sonst voll gueltig
# und ausgerichtet — die Quote-Sperre muss trotzdem ablehnen.
AR_HARMLESS_QUOTE_IN_COMMENT = (
    f"{TEST_AUTHSERV_ID}; spf=pass (sender said \"ok\") smtp.mailfrom=user@henemm.com; "
    "dkim=pass header.d=henemm.com; dmarc=pass header.from=henemm.com"
)

# AC-9: Kommentar mit ``;`` VOR smtp.mailfrom (ohne jedes ``"``), KEIN dkim/dmarc-pass:
# Annahme haengt allein an korrekter Kommentar-Behandlung. Dazu ein dkim-Segment
# (fail, nicht wertungsrelevant) mit ``header.b=M/C96LSA==`` (``=`` im Wert).
AR_SEMICOLON_IN_COMMENT = (
    f"{TEST_AUTHSERV_ID}; spf=pass (domain of a; b designates 1.2.3.4 as permitted sender) "
    "smtp.mailfrom=u@henemm.com; dkim=fail header.d=henemm.com header.b=M/C96LSA==; "
    "dmarc=none header.from=henemm.com"
)

# AC-13: ausschliesslich nicht ausgerichtetes dkim=pass (amazonses.com).
# (spf=pass nur ueber smtp.helo — heute zaehlt das, nach #2252 nicht.)
AR_ONLY_UNALIGNED_DKIM = (
    f"{TEST_AUTHSERV_ID}; dkim=pass header.d=amazonses.com header.s=x; "
    "spf=pass smtp.helo=a3-16.smtp-out.eu-west-1.amazonses.com; "
    "dmarc=none header.from=henemm.com"
)

# AC-12 Subdomain-Gegenrichtung: From x@sub.opfer.example, nur Oberdomain ausgerichtet.
AR_PARENT_DOMAIN_ONLY = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=a@opfer.example; "
    "dkim=pass header.d=opfer.example; dmarc=pass header.from=opfer.example"
)

# Suffix-Falle: header.d endet auf "opfer.example", ist aber KEINE Subdomain.
AR_SUFFIX_LOOKALIKE = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=a@evilopfer.example; "
    "dkim=pass header.d=evilopfer.example; dmarc=none header.from=opfer.example"
)

# Echte Subdomain-Richtung (erlaubt, Regel b/c): From x@opfer.example, SPF/DKIM
# ueber mail.opfer.example; kein dmarc-pass.
AR_SUBDOMAIN_ALIGNED = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=bounce@mail.opfer.example; "
    "dkim=pass header.d=mail.opfer.example; dmarc=none header.from=opfer.example"
)

# AC-16 Wrapper: zwei dkim-Segmente mit widerspruechlichem Ergebnis, beide Reihenfolgen.
AR_DKIM_CONTRADICTORY_PASS_FIRST = (
    f"{TEST_AUTHSERV_ID}; dkim=pass header.d=henemm.com; dkim=fail header.d=henemm.com; "
    "spf=pass smtp.mailfrom=user@henemm.com"
)
AR_DKIM_CONTRADICTORY_FAIL_FIRST = (
    f"{TEST_AUTHSERV_ID}; dkim=fail header.d=henemm.com; dkim=pass header.d=henemm.com; "
    "spf=pass smtp.mailfrom=user@henemm.com"
)
# AC-16 Wrapper: zwei dkim-Segmente, GLEICHES Ergebnis -> Eintrag bleibt.
AR_DKIM_TWICE_SAME = (
    f"{TEST_AUTHSERV_ID}; dkim=pass header.d=henemm.com; dkim=pass header.d=amazonses.com; "
    "spf=pass smtp.mailfrom=user@henemm.com"
)

# F001 (Adversary #2252): H2-Muster, aber die eingeschleuste Nutzlast ist zur
# From-Domain henemm.com AUSGERICHTET. Ohne Quote-Sperre UND ohne Quote-Handling
# im Tokenizer wuerde ``dkim=pass header.d=henemm.com`` ein eigenes Segment und
# die Mail akzeptiert — dieser Header unterscheidet beide Schutzschichten.
H2B_INJECTED_MAILFROM = "x;dkim=pass header.d=henemm.com;spf=pass smtp.mailfrom=a@henemm.com"
AR_H2B_ALIGNED_INJECTION = (
    "mail.henemm.com;\r\n\tspf=permerror (mail.henemm.com: unable to verify SPF record for "
    "postmaster@[127.0.1.1]) smtp.helo=[127.0.1.1];\r\n\tspf=none (mail.henemm.com: no SPF "
    "records found for xdkimpassspfpasssmtp.mailfroma@spoofer-domain.invalid) "
    f'smtp.mailfrom="{H2B_INJECTED_MAILFROM}";\r\n\tiprev=pass policy.iprev=178.104.143.19;'
    "\r\n\tdmarc=fail (policy not aligned) header.from=henemm.com policy.dmarc=quarantine"
)

# F002: doppelter Property-Schluessel im selben Segment, beide Reihenfolgen ⇒
# mehrdeutig ⇒ ganzer Header unlesbar (nie "erster/letzter gewinnt").
AR_DUPLICATE_MAILFROM_ALIGNED_FIRST = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=u@henemm.com smtp.mailfrom=u@evil.example"
)
AR_DUPLICATE_MAILFROM_FOREIGN_FIRST = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=u@evil.example smtp.mailfrom=u@henemm.com"
)

# F003: leerer smtp.mailfrom-Wert mit spf=pass — bei leerer from_domain waere
# "" == "" ausgerichtet; nur die Pruefung "from_domain leer ⇒ ablehnen" schuetzt.
AR_SPF_PASS_EMPTY_MAILFROM = f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom="

# F004: mailfrom-Domain ist der Teil nach dem LETZTEN @ (Spec 5a, Regel b).
AR_MAILFROM_LAST_AT_ALIGNED = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=a@evil.example@henemm.com; "
    "dmarc=none header.from=henemm.com"
)
AR_MAILFROM_LAST_AT_FOREIGN = (
    f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=a@henemm.com@evil.example; "
    "dmarc=none header.from=henemm.com"
)
