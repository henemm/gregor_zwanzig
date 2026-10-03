// TDD RED — Issue #1433, AC-6 (Lieferstufe 3, §5 „Versand-Reiter"):
// Der Versand-Reiter (`BriefingScheduleTab.svelte`) speichert heute bei JEDER Geste
// mit `keepalive: true` (`:41-48`, `:92`) — und damit nie mit If-Match und nie
// serialisiert (`api.ts:183-185`); den angezeigten Trip setzt er aus der lokalen
// Kopie (`{...trip, report_config: snapshot}`) statt aus der Server-Antwort.
// Neu: normales Speichern laeuft wie bei den anderen Reitern ueber den Controller
// (`schedule`) in der Warteschlange MIT If-Match; `init` (keepalive) wird nur beim
// echten Unload-Flush durchgereicht; `trip` kommt aus der Server-Antwort.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §5 (Versand-Reiter),
//       AC-6; Test Plan `trip_versand_reiter_ohne_dauer_keepalive`.
//
// Der Reiter laeuft mit seinem ECHTEN Instanz-Skript (Effekt `_lastReportConfig`)
// ueber das echte `api` gegen den Ersatz-Server (Go-Merge).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_versand_reiter_ohne_dauer_keepalive.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;

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

describe('AC-6: normales Speichern — Warteschlange, If-Match, kein Dauer-keepalive', () => {
	test('der Versand-PUT traegt If-Match und ist KEIN keepalive-Request', async () => {
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		const bekannt = getKnownEtag(P.TRIP_ID);
		v.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		assert.equal(puts().length, 1, 'Messaufbau: genau ein PUT');
		const p = puts()[0];
		assert.equal(p.keepalive, false, 'ein normales Speichern darf nicht mit keepalive laufen (api.ts umgeht dort If-Match und Warteschlange)');
		assert.equal(p.ifMatch, bekannt, 'der Versand-PUT muss den bekannten Stempel als If-Match tragen');
		assert.equal(p.status, 200);
		assert.equal(stand().report_config && (stand().report_config as Record<string, unknown>).morning_time, '08:00:00');
	});

	test('das Speichern haengt am Controller (schedule): die Aenderung steht bis zum Flush aus', async () => {
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '08:00:00' });

		assert.equal(a.ctl.hasPending, true, 'AC-6: der Versand-Reiter speichert ueber `saveController.schedule`, wie die anderen Reiter');
		assert.equal(puts().length, 0, 'ein debouncter Speichervorgang feuert nicht sofort');
		a.ctl.cancel();
	});

	test('zwei Speichervorgaenge nacheinander: der zweite traegt den Stempel der Antwort des ersten (kein veralteter ETag)', async () => {
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);
		const nachErstem = server.etagOf(P.TRIP_ID);
		v.aendern({ evening_time: '19:00:00' });
		await P.fertig(a.ctl);

		assert.equal(puts().length, 2);
		assert.equal(puts()[1].ifMatch, nachErstem, 'die Registry muss den Stempel der ersten Antwort gefuehrt haben');
		assert.equal(puts()[1].status, 200);
		assert.equal((stand().report_config as Record<string, unknown>).evening_time, '19:00:00');
	});

	test('`trip` kommt aus der Server-Antwort, nicht aus der lokalen Kopie', async () => {
		// ein Fremdschreiber aendert den Namen; die Registry wird frisch gehalten (kein 412)
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		await api.get(P.TRIP_PFAD);
		const a = P.neuerAufbau(); // lokale Kopie traegt noch den alten Namen
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		const gemeldet = a.updates.at(-1);
		assert.ok(gemeldet, 'der Reiter muss den Trip nach oben melden (onTripUpdate)');
		assert.equal(gemeldet!.name, 'Fremder Name', 'heute: `{...trip, report_config: snapshot}` aus der veralteten lokalen Kopie');
		assert.equal((gemeldet!.report_config as Record<string, unknown>).morning_time, '08:00:00');
	});
});

describe('init (keepalive) wird nur beim echten Unload-Flush durchgereicht', () => {
	test('flush({ keepalive: true }) mit ausstehender Versand-Aenderung ⇒ PUT mit keepalive', async () => {
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '08:00:00' });
		assert.equal(a.ctl.hasPending, true, 'AC-6: die Versand-Aenderung muss ueber den Controller ausstehen, damit der Entlade-Flush sie schreibt');
		await a.ctl.flush({ keepalive: true });

		const p = puts().at(-1)!;
		assert.equal(p.keepalive, true, 'der Entlade-Flush muss `{ keepalive: true }` bis zum PUT durchreichen (#1376)');
		assert.equal(p.status, 200);
		assert.equal((stand().report_config as Record<string, unknown>).morning_time, '08:00:00');
	});
});

describe('bei offenem Konflikt (Anzeige bleibt, nichts wird geschrieben)', () => {
	test('Versand-Speichern bei Konflikt: 412 mit If-Match, Anzeige bleibt `conflict`', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		assert.equal(puts().at(-1)!.status, 412, 'der Versand-PUT muss den veralteten Stand zu spueren bekommen (heute: keepalive ⇒ kein If-Match ⇒ 200)');
		assert.equal(a.ctl.state, 'conflict', 'Konfliktanzeige „Nochmal speichern"');
		assert.notEqual((stand().report_config as Record<string, unknown>).morning_time, '08:00:00');
		assert.equal(stand().name, 'Fremder Name');
	});
});
