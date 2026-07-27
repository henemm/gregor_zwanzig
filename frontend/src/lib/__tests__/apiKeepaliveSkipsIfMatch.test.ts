// Issue #1395 S3 — der Flush beim Verlassen der Seite umgeht BEIDES:
// Warteschlange und If-Match.
// Spec: docs/specs/modules/issue_1395_s3_etag_registry.md — AC-6.
// `{ keepalive: true }` setzt im Repo ausschliesslich der willUnload-Zweig in
// routes/trips/[id]/+page.svelte. Dieser Vorgang hat nur ein sehr kurzes
// Zeitfenster: hinter einem laufenden Schreibvorgang eingereiht ginge er
// womoeglich nie los — die letzte Aenderung waere weg. Ein unsichtbarer 412
// waere derselbe Schaden.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from './fakeTripServer.ts';

let server: FakeTripServer;

function boot(latencyMs = 0) {
	if (server) server.restore();
	server = createFakeTripServer({ latencyMs });
	server.install();
}

beforeEach(() => {
	clearEtagRegistry();
	boot(0);
});

afterEach(() => server.restore());

describe('AC-6: Abschluss-Speichervorgang beim Entladen', () => {
	test('test_keepaliveFlush_omitsIfMatch_evenWithKnownStamp', async () => {
		// GIVEN: die Tour ist geladen, ein Stand ist bekannt
		await api.get('/api/trips/gr20');
		assert.ok(getKnownEtag('gr20'), 'Vorbedingung: ein Stand muss bekannt sein');

		// WHEN: der Browser beim Entladen den letzten Speichervorgang abschickt
		await api.put('/api/trips/gr20', { report_config: { start_hour: 6 } }, { keepalive: true });

		// THEN: geht er OHNE Vorbedingung raus und wird angenommen — kein
		// unsichtbarer 412 kostet den Nutzer seine letzte Aenderung.
		const call = server.calls[server.calls.length - 1];
		assert.equal(call.method, 'PUT');
		assert.equal(call.keepalive, true, 'die keepalive-Option muss durchgereicht bleiben');
		assert.equal(call.ifMatch, null);
		assert.equal(call.contentType, 'application/json');
		assert.equal(call.status, 200);
	});

	test('test_keepaliveFlush_notQueued_startsImmediatelyDuringRunningWrite', async () => {
		// GIVEN: ein normaler Schreibvorgang auf dieselbe Tour ist WIRKLICH schon
		// unterwegs (der kurze Wartetakt ist noetig: das Einreihen laeuft ueber
		// einen Microtask, vorher ist beim Server noch nichts angekommen)
		boot(40);
		await api.get('/api/trips/gr20');
		const langsam = api.put('/api/trips/gr20', { a: 1 });
		await new Promise((r) => setTimeout(r, 5));
		assert.ok(
			server.calls.some((c) => c.method === 'PUT'),
			'Vorbedingung: der normale Schreibvorgang muss beim Server angekommen sein'
		);

		// WHEN: der Nutzer die Seite verlaesst und der Abschluss-Flush abgeht
		const flush = api.put('/api/trips/gr20', { b: 2 }, { keepalive: true });
		// allSettled, weil der Preis dieses Umgehungswegs ausdruecklich bekannt und
		// akzeptiert ist: der Flush kann einen gleichzeitig laufenden Vorgang
		// ueberholen. Beim Verlassen der Seite ist "die Aenderung des Nutzers
		// retten" wichtiger als "einen theoretischen Konflikt vermeiden".
		await Promise.allSettled([langsam, flush]);

		// THEN: hat der Flush NICHT gewartet — er startete, waehrend der andere
		// Vorgang noch lief.
		const puts = server.calls.filter((c) => c.method === 'PUT');
		const normal = puts.find((c) => !c.keepalive);
		const keepalive = puts.find((c) => c.keepalive);
		assert.ok(normal && keepalive, 'beide Schreibvorgaenge muessen beim Server angekommen sein');
		assert.ok(
			keepalive.startedAt > normal.startedAt && keepalive.startedAt < normal.finishedAt,
			`der keepalive-Flush wurde eingereiht statt sofort losgeschickt: ` +
				`normal [${normal.startedAt}, ${normal.finishedAt}], keepalive startete bei ${keepalive.startedAt}`
		);
		assert.equal(keepalive.ifMatch, null);
		assert.equal(keepalive.status, 200, 'der Abschluss-Flush muss ankommen');
	});

	test('test_nonKeepaliveCall_stillAttachesIfMatch', async () => {
		// GIVEN: derselbe Ausgangszustand wie oben
		await api.get('/api/trips/gr20');
		const stamp = getKnownEtag('gr20');

		// WHEN: ein normaler Schreibvorgang laeuft (ohne keepalive)
		await api.put('/api/trips/gr20', { a: 1 });

		// THEN: traegt er den Stand — nur der Entlade-Fall ist die Ausnahme
		const call = server.calls[server.calls.length - 1];
		assert.equal(call.keepalive, false);
		assert.equal(call.ifMatch, stamp);
	});
});
