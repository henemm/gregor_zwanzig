// Issue #2961 (FE-U2) — wann ein Anmelde-Cookie das `Secure`-Flag traegt.
//
// Bisher allein an NODE_ENV gebunden: ein Betrieb ueber HTTPS ohne
// `NODE_ENV=production` haette die Sitzung ohne `Secure` ausgeliefert. Jetzt
// genuegt eine der beiden Bedingungen — nie schwaecher als zuvor.
export function cookieSicher(nodeEnv: string | undefined, url: URL): boolean {
	return nodeEnv === 'production' || url.protocol === 'https:';
}
