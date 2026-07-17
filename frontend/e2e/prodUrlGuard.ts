// Issue #1265 Teil D — E2E-Prod-Sperre.
//
// Verhindert, dass ein Playwright-Lauf (global.setup.ts und damit jeder
// datenanlegende Spec) versehentlich gegen die Produktions-Domain
// (gregor20.henemm.com OHNE staging.-Präfix) läuft und dort Test-Daten
// anlegt (Root Cause von Issue #1265: "Screenshot-1106"-Presets landeten
// im Prod-default-User über genau diesen Pfad, siehe global.setup.ts).
//
// Spec: docs/specs/modules/issue_1265_prod_testdata_cleanup.md, AC-5.

import { promises as dns } from 'node:dns';
import { PROD_API_PROXY_TARGET } from './apiProxyTarget.ts';

const PROD_HOST = 'gregor20.henemm.com';

/**
 * Wirft, wenn `url` auf die Produktions-Domain zeigt (ohne staging.-Präfix).
 * Staging- und lokale Dev-URLs laufen unverändert an. Eine leere/ungültige
 * URL wird nicht gesperrt (kein valides Ziel -> nichts zu schützen).
 */
export function assertNotProdBaseURL(url: string): void {
	let host: string;
	try {
		host = new URL(url).hostname;
	} catch {
		return;
	}
	if (host === PROD_HOST) {
		throw new Error(
			`E2E-Lauf gegen PRODUKTION verboten: Base-URL zeigt auf "${host}" ` +
				`(ohne staging.-Präfix). Verwende https://staging.${PROD_HOST} ` +
				`oder eine lokale Dev-URL (Issue #1265).`
		);
	}
}

// Issue #1284 — Netzwerk-Wurzel-Fix. Verhindert, dass der `/api`-Proxy von
// Vite (und damit jeder Playwright-Lauf) auf den Produktiv-Go-Server
// (Port 8090) zeigt, unabhängig von Spec-Auswahl oder Login-Konto.
//
// Spec: docs/specs/modules/fix_1284_admin_prod_testdata.md, AC-2.

// F004 (Adversary Fix-Loop 1, HIGH, security) — reine String-Gleichheit war
// umgehbar (IP-Literal, Trailing-Slash, Groß-/Kleinschreibung, Whitespace).
// F011 (Adversary Fix-Loop 2, HIGH, security) — die daraus gebaute
// Sperrliste (BLOCKED_LOCAL_HOSTS) war IMMER NOCH umgehbar: der DNS-
// Trailing-Dot ("localhost." — gültige FQDN-Notation) war kein Set-Mitglied.
// Der F011-Fix ersetzte die Sperrliste durch eine Positivliste (nur das
// exakte erwartete Ziel erlaubt) — aber die Positivliste verglich den Wert
// aus apiProxyTarget.ts MIT SICH SELBST und konnte darum per Konstruktion
// nie ablehnen (F012, Adversary Fix-Loop 3, CRITICAL). Real griff nur noch
// die Loopback-Sperrliste, die per DNS-Alias (z.B. "localtest.me" -> "::1",
// eine öffentliche DNS-Domain) umgangen wurde: kein Set-Mitglied, aber
// exakt derselbe Prod-Server.
//
// Eine Liste verbotener Schreibweisen (egal ob Sperr- oder Positivliste)
// lässt sich beliebig oft neu umgehen, weil sie NAMEN vergleicht statt
// WIRKUNG zu prüfen. Darum: den Hostnamen real auflösen (DNS) und fragen,
// ob er auf einer Loopback-Adresse mit dem Prod-Port landet — das erledigt
// jeden Alias, jede Schreibweise, jeden Trailing-Dot in einem Schritt.
const PROD_PORT = new URL(PROD_API_PROXY_TARGET).port;

/** Entfernt IPv6-Klammern ("[::1]" -> "::1") für dns.lookup(). */
function stripBrackets(hostname: string): string {
	return hostname.startsWith('[') && hostname.endsWith(']') ? hostname.slice(1, -1) : hostname;
}

// F013 (Adversary Fix-Loop 4, MEDIUM, security) — die IPv4-mapped-Erkennung
// traf nur die Dotted-Quad-Notation ("::ffff:127.0.0.1"). `new URL()` liefert
// für IPv6-Literale aber die kompakte Hex-Form zurück
// ("::ffff:127.0.0.1" -> Hostname "[::ffff:7f00:1]"), die die alte Regex
// nicht matchte. Statt eine zweite String-Notation nachzuflicken (die
// nächste Notation wäre wieder eine Lücke), werden die letzten 32 Bit der
// gemappten Adresse jetzt NUMERISCH dekodiert -- deckt beide Notationen
// und den ganzen 127.0.0.0/8-Bereich in einem Schritt ab.

/** Dekodiert die IPv4-Oktette einer IPv4-mapped-IPv6-Adresse (beide Notationen). */
function mappedIPv4Octets(address: string): number[] | null {
	const dotted = address.match(/^::ffff:(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/i);
	if (dotted) return dotted.slice(1, 5).map(Number);
	const hex = address.match(/^::ffff:([0-9a-f]{1,4}):([0-9a-f]{1,4})$/i);
	if (hex) {
		const n = (parseInt(hex[1], 16) << 16) | parseInt(hex[2], 16);
		return [(n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff];
	}
	return null;
}

/**
 * true, wenn `address` (Ergebnis von dns.lookup) im Loopback-Bereich liegt:
 * 127.0.0.0/8, ::1, IPv4-mapped ::ffff:127.0.0.0/8 (Dotted-Quad UND
 * Hex-Notation), 0.0.0.0 (auch IPv4-mapped), ::
 */
function isLoopbackAddress(address: string): boolean {
	if (address === '::' || address === '::1' || address === '0.0.0.0') return true;
	if (address.startsWith('127.')) return true;
	const octets = mappedIPv4Octets(address);
	if (!octets) return false;
	return octets[0] === 127 || octets.every((o) => o === 0);
}

/**
 * Wirft, wenn `target` real auf den Prod-Go-Server auflöst: irgendeine
 * aufgelöste Adresse liegt im Loopback-Bereich UND der Port ist der
 * Prod-Port (8090). Das ist wirkungsbezogen -- unabhängig von Schreibweise
 * oder DNS-Alias des Hostnamens (Issue #1284, F012). Ein Ziel, das sich
 * nicht als URL parsen lässt ODER dessen Hostname sich nicht auflösen
 * lässt, wird fail-closed abgelehnt: was man nicht auflösen kann, darf man
 * nicht ansteuern. Ein legitimes eigenes Dev-Backend (z.B.
 * "http://localhost:8000") läuft unverändert an, weil nur die Kombination
 * Loopback+8090 verboten ist, nicht Loopback allein.
 */
export async function assertNotProdApiProxyTarget(target: string): Promise<void> {
	let parsed: URL;
	try {
		parsed = new URL(target.trim());
	} catch {
		throw new Error(
			`E2E-Lauf gegen PRODUKTION verboten (fail-closed): /api-Proxy-Ziel ` +
				`"${target}" lässt sich nicht als URL verstehen und wird darum ` +
				`abgelehnt statt durchgewinkt (Issue #1284, F004).`
		);
	}
	const hostname = stripBrackets(parsed.hostname);
	let addresses: { address: string }[];
	try {
		addresses = await dns.lookup(hostname, { all: true });
	} catch {
		throw new Error(
			`E2E-Lauf verboten (fail-closed): /api-Proxy-Ziel "${target}" -- ` +
				`Hostname "${hostname}" lässt sich nicht auflösen. Was sich nicht ` +
				`auflösen lässt, darf nicht angesteuert werden (Issue #1284, F012).`
		);
	}
	if (parsed.port === PROD_PORT && addresses.some((a) => isLoopbackAddress(a.address))) {
		throw new Error(
			`E2E-Lauf gegen PRODUKTION verboten: /api-Proxy-Ziel "${target}" löst ` +
				`auf eine Loopback-Adresse mit dem Prod-Port ${PROD_PORT} auf ` +
				`(Hostname "${hostname}" -> ${addresses.map((a) => a.address).join(', ')}). ` +
				`Prod bleibt verboten, auch bei DNS-Alias oder Env-Override ` +
				`(Issue #1284, F012).`
		);
	}
}
