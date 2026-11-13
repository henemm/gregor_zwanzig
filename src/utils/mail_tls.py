"""TLS-Kontext fuer Postausgang (STARTTLS) und Posteingang (IMAPS), Issue #2961.

Regel: Jede Gegenstelle wird mit vollem Zertifikats- und Namensabgleich
geprueft (``ssl.create_default_context()``), ohne Schalter. Einzige Ausnahme
sind Loopback-Ziele (Host woertlich ``localhost`` oder eine Loopback-IP wie
``127.0.0.1``/``::1``): dieser Verkehr verlaesst den Rechner nicht, und ein
auf demselben Server laufender Mailserver (Stalwart) traegt fuer ``localhost``
in der Regel kein passendes Zertifikat. Die Ausnahme wird protokolliert.
"""
from __future__ import annotations

import ipaddress
import logging
import ssl

logger = logging.getLogger(__name__)


def ist_loopback_host(host: str | None) -> bool:
    """``True`` nur fuer ``localhost`` und Loopback-IP-Literale."""
    if not host:
        return False
    name = host.strip().lower().strip("[]")
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def tls_kontext_fuer(host: str | None) -> ssl.SSLContext:
    """Strenger Kontext fuer jeden Host; ungeprueft nur fuer Loopback-Ziele."""
    if ist_loopback_host(host):
        logger.info(
            "Mail-TLS zu Loopback-Ziel %s ohne Zertifikatspruefung (Verkehr bleibt auf dem Rechner)",  # i18n-log
            host,
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return ssl.create_default_context()
