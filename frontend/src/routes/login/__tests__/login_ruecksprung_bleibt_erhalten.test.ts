// Issue #3281 (MCP-Konnektor „Gregor Wetter“, Scheibe 2) — AC-4: wer ohne
// Sitzung auf die Autorisierung kommt, landet auf `/login?redirect=<authorize>`
// und nach der Anmeldung wieder auf der Zustimmungsseite.
//
// Befund vor der Aenderung: das Formular postet an `?/login` und verliert
// damit die Abfrage der Seite — die Action sah nie ein `redirect` und leitete
// immer auf `/`. Geprueft wird die echte Seite (serverseitig gerendert) UND
// die echte Action gegen einen HTTP-Server an Stelle der Go-API.
//
//   cd frontend && npm test -- src/routes/login/__tests__/login_ruecksprung_bleibt_erhalten.test.ts

import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> login -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

register(pathToFileURL(path.join(HERE, 'app-stores-url-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const goApi = createServer((_req, res) => {
	res.writeHead(200, { 'Content-Type': 'application/json', 'Set-Cookie': 'gz_session=u.s.1.sig; Path=/' });
	res.end('{}');
});
await new Promise<void>((fertig) => goApi.listen(0, '127.0.0.1', fertig));
process.env.GZ_API_BASE = `http://127.0.0.1:${(goApi.address() as AddressInfo).port}`;
after(() => goApi.close());

const { actions } = await import(pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.server.ts')).href);
const { render } = await import('svelte/server');
const Login = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.svelte')).href)).default;

const AUTHORIZE =
	'/api/mcp/oauth/authorize?response_type=code&client_id=https%3A%2F%2Fclaude.ai%2Foauth%2Fmeta' +
	'&redirect_uri=https%3A%2F%2Fclaude.ai%2Fapi%2Fmcp%2Fauth_callback&code_challenge=abc&state=z';

function formularAktion(seitenUrl: string): string {
	(globalThis as { __gzLoginTestUrl?: string }).__gzLoginTestUrl = seitenUrl;
	const html = render(Login, { props: { form: null, data: { googleEnabled: false } } }).body;
	const treffer = html.match(/<form method="POST" action="([^"]*)" class="space-y-4"/);
	assert.ok(treffer, 'Anmeldeformular nicht gefunden');
	return treffer[1].replaceAll('&amp;', '&');
}

async function meldeAnUeber(aktion: string): Promise<string> {
	const ziel = new URL(aktion, 'http://localhost/login');
	const body = new FormData();
	body.set('username', 'anna');
	body.set('password', 'geheim-genug-fuer-den-test');
	const ereignis = {
		request: new Request(ziel, { method: 'POST', body }),
		cookies: { set: () => {} },
		url: ziel
	};
	try {
		await actions.login(ereignis as never);
	} catch (e) {
		const r = e as { status?: number; location?: string };
		assert.equal(r.status, 302);
		return r.location ?? '';
	}
	assert.fail('Login hat nicht weitergeleitet');
}

test('AC-4: nach der Anmeldung geht es zur Autorisierung zurueck', async () => {
	const aktion = formularAktion(`http://localhost/login?redirect=${encodeURIComponent(AUTHORIZE)}`);
	const ziel = await meldeAnUeber(aktion);
	assert.ok(ziel.startsWith(AUTHORIZE), `Ruecksprung verloren: ${ziel}`);
});

test('ohne redirect bleibt das Formular bei ?/login und fuehrt auf /', async () => {
	const aktion = formularAktion('http://localhost/login');
	assert.equal(aktion, '?/login');
	assert.ok((await meldeAnUeber(aktion)).startsWith('/?'));
});

test('fremde Ziele werden nicht ins Formular uebernommen', async () => {
	for (const fremd of ['https://evil.example/x', '//evil.example', '/\\evil.example']) {
		const aktion = formularAktion(`http://localhost/login?redirect=${encodeURIComponent(fremd)}`);
		assert.equal(aktion, '?/login', fremd);
	}
});
