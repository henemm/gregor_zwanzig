// Issue #1265 Teil D — E2E-Prod-Sperre.
//
// Verhindert, dass ein Playwright-Lauf (global.setup.ts und damit jeder
// datenanlegende Spec) versehentlich gegen die Produktions-Domain
// (gregor20.henemm.com OHNE staging.-Präfix) läuft und dort Test-Daten
// anlegt (Root Cause von Issue #1265: "Screenshot-1106"-Presets landeten
// im Prod-default-User über genau diesen Pfad, siehe global.setup.ts).
//
// Spec: docs/specs/modules/issue_1265_prod_testdata_cleanup.md, AC-5.

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
