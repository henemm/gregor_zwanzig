# testdata

`seven_sms_mo.json`: Testvektor fuer den seven.io-`sms_mo`-Webhook (Issue #2439), KEIN Mitschnitt.
Der echte Signing-Key und echte Rufnummern duerfen nicht ins Repo. Struktur und Body folgen der
seven.io-Doku (Fantasienummern, Test-Schluessel, Test-Pfad-Secret). `X-Signature` wurde einmalig mit
einem Wegwerf-Skript nach dem gegen seven.io belegten Algorithmus berechnet:

    string_to_sign = X-Timestamp \n X-Nonce \n METHODE \n volle URL \n md5_hex(Body)
    X-Signature    = hex(HMAC-SHA256(signing_key, string_to_sign))

Beleg des Algorithmus gegen die echte Gegenseite:
`docs/artifacts/feat-2439-befehle-push-eingang/seven-signatur-nachweis.md`.
