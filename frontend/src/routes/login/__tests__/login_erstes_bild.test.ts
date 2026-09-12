// TDD RED — Issue #2247 (Scheibe 2 von #2199).
// Spec: docs/specs/modules/passkey_login_anordnung.md — AC-3, AC-11.
//
// Der tragende Waechter dieser Scheibe: der Passkey-Knopf muss bereits im
// VOM SERVER ausgelieferten HTML stehen, nicht erst nach der Hydration
// eingefuegt werden (sonst entsteht der Einfuege-Sprung, den der PO verworfen
// hat -- siehe Kontext-Dokument, "Der Befund, der alles andere ordnet"). Eine
// Zusicherung auf die Server-Ausgabe misst genau das: deterministisch, ohne
// Zeitfenster, ohne Browser.
//
// Echtes serverseitiges Rendern der echten Route (svelte/server `render()`,
// Hooks: test-svelte-ssr-hooks.mjs). Keine Mocks, kein Datei-Inhalt-Grep.
//
// AC-4 (zwei Zustaende: Faehigkeit vorhanden/abwesend) wird hier NICHT
// geprueft: `isWebAuthnSupported()` braucht `window` (passkey.ts:17), das SSR
// nie hat, und die Spec definiert keinen Einspeisepunkt, um den
// `false`-Zustand von aussen in die Route zu zwingen (kein `profileOverride`-
// Aequivalent, keine Test-Prop). Ein erfundener Backdoor-Prop auf einer
// Produktivroute waere genau der "Stellvertreter", den die Spec zwei Absaetze
// vorher fuer die verworfene Auslagerung in eine eigene Komponente ablehnt --
// eine erfundene Test-Prop haette dasselbe Problem, nur versteckt. Der
// Negativ-Zweig hat einen echten, nicht erfundenen Messpunkt:
// frontend/e2e/passkey-login.spec.ts (AC-5/AC-6) ueber `page.addInitScript`,
// das `window.PublicKeyCredential` entfernt -- dort ist die Faehigkeitspruefung
// real. Gemeldet als offener Punkt an den Auftraggeber.
//
// RED heute: `frontend/src/routes/login/+page.svelte` enthaelt kein einziges
// Wort "passkey" (Spec, Abschnitt "Source") -- weder ein Knopf mit
// `data-testid="login-passkey-btn"` noch `autocomplete="username webauthn"`
// existieren.
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/login/__tests__/login_erstes_bild.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> login -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

// Reihenfolge wie bei test-app-environment-stub-hooks.mjs vorgezeichnet: der
// lokale $app/stores-Stub zuerst registrieren, DANACH die geteilten Hooks
// (.svelte-Kompilat + $lib-Aufloesung) -- beide werden gebraucht, die
// geteilte Kette bleibt dabei unveraendert (eigene Datei statt Aenderung an
// test-svelte-ssr-hooks.mjs, siehe Kommentar dort).
register(
	pathToFileURL(path.join(HERE, 'app-stores-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const Login = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.svelte')).href)
).default;

function renderLogin(): string {
	return render(Login, { props: { form: null, data: { googleEnabled: false } } }).body;
}

/** Das vollstaendige Start-Tag des Elements, das das gegebene Attribut traegt. */
function openingTagByAttr(html: string, attr: string): string {
	const markerIdx = html.indexOf(attr);
	assert.notEqual(markerIdx, -1, `Attribut ${attr} nicht im gerenderten HTML gefunden.`);
	const tagStart = html.lastIndexOf('<', markerIdx);
	assert.notEqual(tagStart, -1, `Kein umschliessendes Tag vor ${attr} gefunden.`);
	const tagEnd = html.indexOf('>', markerIdx);
	assert.notEqual(tagEnd, -1, `Start-Tag zu ${attr} nicht geschlossen gefunden.`);
	return html.slice(tagStart, tagEnd + 1);
}

/** Das vollstaendige Start-Tag des Elements, das den gegebenen Testid traegt. */
function openingTag(html: string, testid: string): string {
	return openingTagByAttr(html, `data-testid="${testid}"`);
}

function tagName(openTag: string): string {
	const m = openTag.match(/^<([a-zA-Z0-9-]+)/);
	return m ? m[1].toLowerCase() : '';
}

describe('#2247 AC-3 — Passkey-Knopf steht bereits im Server-HTML', () => {
	test('server_html_enthaelt_passkey_knopf_ohne_browser', () => {
		const html = renderLogin();
		const tag = openingTag(html, 'login-passkey-btn');
		assert.equal(
			tagName(tag),
			'button',
			`AC-3: data-testid="login-passkey-btn" haengt an einem <${tagName(tag) || '???'}>` +
				`, nicht an einem <button> -- ${tag}`
		);
		assert.doesNotMatch(
			tag,
			/\bdisabled(=""|(?=[\s/>]))/,
			'AC-3/Implementation Details: der Passkey-Knopf darf nicht `disabled` sein -- ' +
				'ein deaktivierter Knopf ist per Tastatur nicht erreichbar (Spec, ' +
				'"Knopf bei leerem Benutzernamen bleibt bedienbar").'
		);
	});
});

describe('#2247 AC-11 — Benutzernamen-Feld traegt die Autofill-Anbindung', () => {
	test('username_feld_traegt_autocomplete_username_webauthn', () => {
		const html = renderLogin();
		// Das Feld ist per `id="username"` adressiert, nicht per data-testid --
		// es existiert schon heute (login/+page.svelte:63) ohne data-testid.
		const tag = openingTagByAttr(html, 'id="username"');
		assert.match(
			tag,
			/autocomplete="username webauthn"/,
			`AC-11: das Benutzernamen-Feld traegt nicht autocomplete="username webauthn" -- ${tag}`
		);
	});
});
