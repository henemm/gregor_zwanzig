// TDD RED — Issue #2375 Punkt 2 (Epic #2345): der Seitenaufbau des
// Ortsvergleichs übernimmt den ETag, damit schon die ERSTE Speicherung nach
// dem Laden `If-Match` trägt — sonst überschreibt sie still, was ein anderer
// Tab inzwischen gespeichert hat. Vorlage: Trip (`routes/trips/[id]/
// +page.server.ts` gibt `etag` zurück, `+page.svelte:38-40` übernimmt ihn).
//
// Spec: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md
//   Test 8 / AC-1 — Loader liefert `etag`; die Seite übernimmt ihn per
//                   `adoptEtagFromPageLoad`; der erste PUT trägt `If-Match`
//                   und scheitert am fremd geänderten Stand mit 412.
//
// Gemessen wird der ECHTE Loader (`load()` aus +page.server.ts) gegen einen
// Ersatz-`fetch` mit echtem `ETag`-Header, und der ECHTE `$effect` der Seite
// (svelteInstanzPruefstand.ts: `effekteVon`) plus der echte `saveName`.
// Die zweite Hälfte (Browser) sichert E2E-Test 9 per Request-Mitschnitt.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_seitenaufbau_uebernimmt_etag.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import { effekteVon, umgebungFuer } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer
} from '../../shared/__tests__/goMergeServerPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const ROUTE = join(FRONTEND, 'src/routes/compare/[id]');

register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const ID = 'cp-2375-seitenaufbau';
let server: GoMergeServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
});
afterEach(() => server.restore());

describe('Test 8 / AC-1: der Seitenaufbau übernimmt den ETag', () => {
	test('load() gibt den ETag-Header der Vergleich-Antwort als `etag` zurück', async () => {
		const { load } = (await import(pathToFileURL(join(ROUTE, '+page.server.ts')).href)) as {
			load: (e: unknown) => Promise<Record<string, unknown>>;
		};
		const ergebnis = await load({ cookies: { get: () => undefined }, params: { id: ID } });
		assert.equal(
			(ergebnis.preset as Record<string, unknown>)?.id,
			ID,
			'Messaufbau: der Loader muss den Vergleich über den Ersatz-Server geladen haben'
		);
		assert.equal(
			ergebnis.etag,
			server.etagOf(ID),
			'der Loader muss den ETag der ausgelieferten Fassung zurückgeben (Trip-Muster)'
		);
	});

	test('die Seite übernimmt data.etag; der erste Kopf-PUT trägt If-Match und scheitert am fremden Stand mit 412', async () => {
		const etag = server.etagOf(ID);
		const { ast, quelle, u } = await umgebungFuer(join(ROUTE, '+page.svelte'), {
			data: { preset: vollerVergleich(ID), etag }
		});
		const effekte = effekteVon(ast, quelle, u, 'adoptEtagFromPageLoad');
		assert.ok(
			effekte.length > 0,
			'+page.svelte hat keinen $effect, der adoptEtagFromPageLoad(data.preset.id, data.etag) aufruft'
		);
		for (const e of effekte) e();
		assert.equal(getKnownEtag(ID), etag, 'der Seitenaufbau-Stempel muss in der ETag-Registry stehen');

		// Ein anderer Tab speichert, danach bedient dieser Tab den Kopf.
		server.fremdSchreiben(ID, { name: 'Fremd von A' });
		u.editName = 'Von B';
		await (u.saveName as () => Promise<void>)();

		const put = server.mitschnitt.find((e) => e.method === 'PUT');
		assert.ok(put, 'Messaufbau: saveName hat keinen PUT ausgelöst');
		assert.equal(put!.ifMatch, etag, 'der erste PUT nach dem Laden muss If-Match aus dem Seitenaufbau tragen');
		assert.equal(put!.status, 412, 'mit If-Match muss der fremd geänderte Stand abgelehnt werden');
		assert.equal(server.stand(ID).name, 'Fremd von A', 'der fremde Name darf nicht still überschrieben werden');
	});
});
