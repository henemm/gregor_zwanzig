// TDD RED — Issue #1433, AC-7 (Lieferstufe 3, §5 „Unload-Flush bei offenem Konflikt"):
// Der Abschluss-Speichervorgang beim Verlassen der Seite (`keepalive: true`) sendet
// heute NIE If-Match (`api.ts:183-185`) und ueberschreibt deshalb bei einem offenen
// Konflikt die Fremdaenderung. Neu: ist die Ressource in der Registry als
// `konflikt` markiert, traegt auch der keepalive-Request das (alte) If-Match ⇒ der
// Server antwortet 412, nichts wird geschrieben. OHNE Konflikt bleibt alles wie
// heute (kein If-Match, nicht serialisiert — der Unload-Flush darf weder warten
// noch an einem unsichtbaren 412 scheitern).
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §5, AC-7;
//       bestehende Zusicherung: apiKeepaliveSkipsIfMatch.test.ts (AC-6 aus S3).
//
// Wo die Zusicherung wirkt: der Entlade-Flush laeuft durch den echten Controller
// (`flush({ keepalive: true })`) und den echten Alarme-Reiter; gelesen wird der
// Server-Stand im Ersatz-Server.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/__tests__/trip_unload_flush_bei_konflikt.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from './fakeTripServer.ts';
import * as P from '../components/trip-detail/__tests__/tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
const FREMDE_METRIKEN = [{ metric_id: 'cape', enabled: true, aggregations: ['max'] }];

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const stand = () => server.stand(P.TRIP_ID);

describe('AC-7: offener Konflikt — der Unload-Flush traegt If-Match und wird abgelehnt', () => {
	test('api.put mit keepalive bei Konflikt: altes If-Match, 412, Server unveraendert', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
		const alt = getKnownEtag(P.TRIP_ID)!;
		await assert.rejects(api.put(P.TRIP_PFAD, { activity: 'mtb' }), (e: { status?: number }) => e.status === 412);
		const vorher = JSON.stringify(stand());

		await assert.rejects(
			api.put(P.TRIP_PFAD, { activity: 'skitour' }, { keepalive: true }),
			(e: { status?: number }) => e.status === 412,
			'der Unload-Flush bei offenem Konflikt muss mit 412 abgelehnt werden'
		);

		const flush = puts().at(-1)!;
		assert.equal(flush.keepalive, true, 'die keepalive-Option muss durchgereicht bleiben');
		assert.equal(flush.ifMatch, alt, 'bei offenem Konflikt traegt auch der keepalive-Request das ALTE If-Match (api.ts:183-185)');
		assert.equal(flush.status, 412);
		assert.equal(JSON.stringify(stand()), vorher, 'der Server darf nichts geschrieben haben');
	});

	test('ueber den echten Controller + Alarme-Reiter: Konflikt, dann Seite verlassen ⇒ Fremdaenderung bleibt', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau();
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: Konflikt offen');
		const alt = puts()[0].ifMatch;

		// Nutzer aendert weiter und laedt die Seite neu: beforeNavigate/willUnload → flush({keepalive:true})
		alarme.kanalUmschalten('sms');
		assert.equal(a.ctl.hasPending, true, 'Messaufbau: eine Aenderung steht aus');
		await a.ctl.flush({ keepalive: true });

		const flush = puts().at(-1)!;
		assert.equal(flush.keepalive, true);
		assert.equal(flush.ifMatch, alt, 'der Entlade-Flush muss bei Konflikt das alte If-Match tragen');
		assert.equal(flush.status, 412, 'der Server lehnt ab');
		const dc = stand().display_config as Record<string, unknown>;
		assert.deepEqual(dc.metrics, FREMDE_METRIKEN, 'die Fremdaenderung bleibt erhalten');
		assert.notEqual((stand().alert_channels as Record<string, unknown>).sms, true, 'die Aenderung des Tabs mit Konflikt ist nicht geschrieben');
	});
});

describe('Ohne Konflikt bleibt der Unload-Flush wie heute (Regressionswaechter)', () => {
	test('keepalive ohne Konflikt: KEIN If-Match, wird angenommen', async () => {
		assert.ok(getKnownEtag(P.TRIP_ID), 'Vorbedingung: ein Stand ist bekannt');
		await api.put(P.TRIP_PFAD, { activity: 'skitour' }, { keepalive: true });
		const flush = puts().at(-1)!;
		assert.equal(flush.keepalive, true);
		assert.equal(flush.ifMatch, null, 'ohne offenen Konflikt darf der Unload-Flush kein If-Match tragen (kein unsichtbarer 412)');
		assert.equal(flush.status, 200);
		assert.equal(stand().activity, 'skitour');
	});

	test('ueber den Controller ohne Konflikt: letzte Aenderung wird beim Verlassen geschrieben', async () => {
		const a = P.neuerAufbau();
		const alarme = await P.alarmeReiter(a);
		alarme.kanalUmschalten('sms');
		await a.ctl.flush({ keepalive: true });
		const flush = puts().at(-1)!;
		assert.equal(flush.keepalive, true);
		assert.equal(flush.ifMatch, null);
		assert.equal(flush.status, 200);
		assert.equal((stand().alert_channels as Record<string, unknown>).sms, true);
	});

	test('nicht serialisiert: der keepalive-Flush startet, waehrend ein normaler PUT noch laeuft', async () => {
		server.restore();
		server = createFakeTripServer({ merge: true, latencyMs: (m) => (m === 'PUT' ? 40 : 0) });
		server.install();
		server.seed(P.TRIP_ID, P.vollerTrip());
		clearEtagRegistry();
		await api.get(P.TRIP_PFAD);
		const langsam = api.put(P.TRIP_PFAD, { activity: 'mtb' });
		await new Promise((r) => setTimeout(r, 5));
		const flush = api.put(P.TRIP_PFAD, { name: 'beim Verlassen' }, { keepalive: true });
		await Promise.allSettled([langsam, flush]);
		const p = puts();
		const normal = p.find((c) => !c.keepalive)!;
		const ka = p.find((c) => c.keepalive)!;
		assert.ok(ka.startedAt < normal.finishedAt, 'der Unload-Flush darf nicht hinter dem laufenden Schreibvorgang warten');
	});
});
