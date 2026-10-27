// TDD RED — Issue #2147 Scheibe C (Epic #2138), AC-18.
// Spec: docs/specs/modules/google_login_adress_verknuepfung.md
//
// Der Google-Callback (Go) lehnt per Redirect ab: `/login?error=oauth_link_failed`,
// `?error=oauth_failed`, `?error=email_not_verified`. Heute ist das auf der
// Login-Seite unsichtbar — der Nutzer landet stumm wieder auf der Maske.
//
// Gemessen wird, was der Nutzer SIEHT: die echte Route, serverseitig gerendert
// (svelte/server `render()`), mit genau dem, was SvelteKit ihr fuer diese URL
// gaebe — `data` aus dem echten `load()` von +page.server.ts (mit `url`) UND
// `$page.url` mit derselben Query (einstellbarer Stub, app-stores-url-stub-hooks.mjs).
// So bleibt offen, ob die Umsetzung den Code in `load` oder in der Komponente
// liest. Kein Mock des Prueflings, kein Datei-Inhalt-Grep.
//
// Die Zusicherung haengt NICHT am Wortlaut (die Spec legt keinen fest), sondern
// an der Sichtbarkeit: der Seitentext mit Fehlercode muss gegenueber der
// Seite ohne Code um eine Meldung wachsen, die den Rohcode nicht zeigt, nicht
// englisch "error/failed" ausgibt und nichts ueber die Existenz einer Adresse
// sagt. Der Kontrast-Teil (WCAG-AA) von AC-18 ist Staging-Nachweis (Browser),
// nicht Kern.
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/login/__tests__/login_oauth_fehlertexte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> login -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(HERE, 'app-stores-url-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { load } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.server.ts')).href
);
const { render } = await import('svelte/server');
const Login = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.svelte')).href)
).default;

const g = globalThis as unknown as { __gzLoginTestUrl?: string };

/** Die Login-Seite, wie SvelteKit sie fuer `href` serverseitig ausliefern wuerde. */
async function seiteFuer(href: string): Promise<string> {
	g.__gzLoginTestUrl = href;
	const url = new URL(href);
	const geladen = (await load({ url } as unknown as Parameters<typeof load>[0])) ?? {};
	return render(Login, {
		props: { form: null, data: { googleEnabled: true, ...(geladen as object) } }
	}).body;
}

/** Sichtbarer Text: Kommentare, Tags und Mehrfach-Leerraum entfernt. */
function sichtbarerText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

/** Der Text, um den `mit` gegenueber `ohne` gewachsen ist (gemeinsamer Anfang/Ende abgezogen). */
function hinzugekommen(ohne: string, mit: string): string {
	let anfang = 0;
	while (anfang < ohne.length && anfang < mit.length && ohne[anfang] === mit[anfang]) anfang++;
	let ende = 0;
	while (
		ende < ohne.length - anfang &&
		ende < mit.length - anfang &&
		ohne[ohne.length - 1 - ende] === mit[mit.length - 1 - ende]
	)
		ende++;
	return mit.slice(anfang, mit.length - ende).trim();
}

const BASIS = 'http://localhost/login';
const BEKANNTE_CODES = ['oauth_link_failed', 'oauth_failed', 'email_not_verified'] as const;
// Woerter, mit denen eine Meldung die Existenz/Belegung einer Adresse verriete.
const ENUMERATION = /existiert|vergeben|belegt|already|exists/i;

describe('#2147-C AC-18 — Google-Ablehnungen sind auf /login sichtbar und neutral', () => {
	for (const code of BEKANNTE_CODES) {
		test(`AC18_${code}_zeigt_neutrale_deutsche_meldung`, async () => {
			const ohne = sichtbarerText(await seiteFuer(BASIS));
			const mit = sichtbarerText(await seiteFuer(`${BASIS}?error=${code}`));
			const meldung = hinzugekommen(ohne, mit);

			assert.ok(
				meldung.length >= 20,
				`AC-18: /login?error=${code} zeigt keine Meldung — der Seitentext ist gegenueber /login ` +
					`nicht gewachsen (hinzugekommen: ${JSON.stringify(meldung)}). Der Nutzer landet stumm auf der Maske.`
			);
			assert.ok(
				!mit.includes(code),
				`AC-18: der Rohcode "${code}" steht sichtbar in der Seite: ${JSON.stringify(meldung)}`
			);
			assert.doesNotMatch(
				meldung,
				/\b(error|failed|oauth)\b/i,
				`AC-18: die Meldung ist nicht deutsch/nutzerlesbar: ${JSON.stringify(meldung)}`
			);
			assert.doesNotMatch(
				meldung,
				ENUMERATION,
				`AC-18: die Meldung sagt etwas ueber Existenz/Belegung einer Adresse: ${JSON.stringify(meldung)}`
			);
		});
	}

	test('AC18_unbekannter_code_zeigt_keinen_codetext', async () => {
		const code = 'irgendwas_unbekannt_2147c';
		const mit = sichtbarerText(await seiteFuer(`${BASIS}?error=${code}`));
		assert.ok(
			!mit.includes(code),
			`AC-18: ein unbekannter Fehlercode darf nicht roh angezeigt werden, Seite: ${JSON.stringify(mit)}`
		);
	});

	// Fix-Loop 1 (Adversary F002): Codes, die Namen von Object.prototype-Eigenschaften
	// tragen, sind unbekannte Codes — die Seite waechst um nichts (ein Nachschlagen
	// in einem Objekt-Literal lieferte hier eine Funktion bzw. das Prototyp-Objekt).
	for (const code of ['constructor', '__proto__', 'toString', 'hasOwnProperty']) {
		test(`AC18_prototyp_code_${code}_zeigt_keine_meldung`, async () => {
			const ohne = sichtbarerText(await seiteFuer(BASIS));
			const mit = sichtbarerText(await seiteFuer(`${BASIS}?error=${code}`));
			assert.equal(
				hinzugekommen(ohne, mit),
				'',
				`AC-18: /login?error=${code} darf keine Meldung zeigen, hinzugekommen: ${JSON.stringify(hinzugekommen(ohne, mit))}`
			);
		});
	}
});
