// Fix-Loop 1/2 — Issue #2278, F001/F003/F006/F008/F017/F020 am Trip-Hub als echtes VERHALTEN: der ECHTE
// Instanz-Code von routes/trips/[id]/+page.svelte (Pruefstand `tripSeite`) laeuft gegen den Ersatz-Server,
// gemessen werden die Requests. Ergaenzt die Bindungs-Tests (aktionsmodell_seiten_bindung.test.ts) um die Wirkung.
// Gewartet wird auf BEDINGUNGEN (Request angekommen, Handler fertig), nie auf feste Zeiten (F020).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_hub_aktionen_verhalten.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
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

const nach = (m: string, teil: string) => server.calls.filter((c) => c.method === m && c.path.includes(teil));

/** Wartet (max. 5 s) auf eine Bedingung; scheitert LAUT mit Beschreibung statt still durchzulaufen. */
async function bis(bedingung: () => boolean, was: string): Promise<void> {
	const ende = Date.now() + 5000;
	while (!bedingung()) {
		if (Date.now() > ende) assert.fail(`Zeitueberschreitung beim Warten auf: ${was}`);
		await new Promise((r) => setTimeout(r, 5));
	}
}
/** Alle bisher gestarteten Anfragen sind beantwortet und der Hub arbeitet nicht mehr. */
const ruhig = (u: Record<string, any>) => () =>
	u.isLoading !== true && server.calls.every((c) => !Number.isNaN(c.finishedAt));
/**
 * Abwesenheitspruefung (F024): erst auf RUHE warten (alle Anfragen beantwortet), dann einen Zeitpuffer
 * lassen, in dem auch verzoegert angestossene Handler (setTimeout) ihren Request absetzen wuerden.
 * Erst danach darf „es wurde nichts gesendet/geloescht" behauptet werden.
 */
const tick = async (u?: Record<string, any>) => {
	for (let i = 0; i < 10; i++) await Promise.resolve();
	await new Promise((r) => setTimeout(r, 120));
	await bis(() => (u ? ruhig(u)() : server.calls.every((c) => !Number.isNaN(c.finishedAt))), 'Ruhe nach der Aktion');
};

async function seite(trip: Record<string, unknown> = P.vollerTrip()) {
	const a = P.neuerAufbau(trip);
	const s = await P.tripSeite(a, server);
	server.calls.length = 0;
	const u = s.inst.u as Record<string, any>;
	u.sendTimer = undefined; // `let sendTimer;` ohne Initialisierer legt die Umgebung nicht an
	const gotos: string[] = [];
	const gotoArgs: unknown[][] = [];
	// $app/navigation ist unter node nicht ladbar
	u.goto = (pfad: string, ...rest: unknown[]) => void (gotos.push(pfad), gotoArgs.push([pfad, ...rest]));
	return { a, u, gotos, gotoArgs, aktion: (id: string) => u.handleHubAction(id) };
}

describe('F006: Pausieren/Fortsetzen schreiben den richtigen Zielzustand', () => {
	test('"pause" -> PATCH /state {paused:true}; "resume" -> {paused:false}', async () => {
		const { aktion, a, u } = await seite();
		aktion('pause');
		await bis(() => nach('PATCH', '/state').length === 1 && ruhig(u)(), 'PATCH nach "pause"');
		aktion('resume');
		await bis(() => nach('PATCH', '/state').length === 2 && ruhig(u)(), 'PATCH nach "resume"');
		a.ctl.cancel();
		assert.deepEqual(
			nach('PATCH', '/state').map((c) => c.anfrage),
			[{ paused: true }, { paused: false }]
		);
	});
});

// #3442 (feat_3442 AC-2/AC-4/AC-10/AC-11): die Rückfrage für Löschen/Archivieren sitzt im Kebab-Menü
// (kebab_seiten_bindung.test.ts belegt: onSelect erreicht die Seite erst nach der Bestätigung). Der Dispatch
// der Seite wirkt deshalb direkt — ohne eigenen Dialog — und meldet den Erfolg mit dem Text aus dem Modell.
/** Steht der Meldungstext im Zustand der Seite (gleich welche Variable ihn trägt)? */
const meldet = (u: Record<string, any>, text: string) => Object.values(u).some((v) => v === text);

describe('F008 → #3442: nach der Rückfrage im Menü wirken Löschen und Archivieren direkt', () => {
	test('"delete" (im Menü bestätigt) -> genau ein DELETE auf den Trip, danach /trips; kein Seitendialog', async () => {
		const { aktion, u, gotos } = await seite();
		aktion('delete');
		await bis(() => nach('DELETE', P.TRIP_PFAD).length === 1 && gotos.length === 1, 'DELETE und Navigation nach "delete"');
		await tick(u);
		assert.equal(nach('DELETE', P.TRIP_PFAD).length, 1);
		assert.deepEqual(gotos, ['/trips'], 'nach dem Loeschen landet der Nutzer in der Trip-Liste');
		assert.notEqual(u.deleteDialogOpen, true, 'Seitendialog geöffnet statt gelöscht');
	});

	test('"archive" (im Menü bestätigt) -> PATCH {archived:true}, bleibt auf der Seite, Meldung „Archiviert. …“', async () => {
		const { aktion, u, a, gotos } = await seite();
		aktion('archive');
		await bis(() => nach('PATCH', '/state').length === 1 && ruhig(u)(), 'PATCH nach "archive"');
		a.ctl.cancel();
		assert.deepEqual(nach('PATCH', '/state').map((c) => c.anfrage), [{ archived: true }]);
		assert.deepEqual(gotos, [], 'Archivieren verlässt die Seite');
		assert.notEqual(u.archiveDialogOpen, true, 'Seitendialog geöffnet statt archiviert');
		assert.ok(meldet(u, 'Archiviert. Im Archiv kannst du es reaktivieren.'), 'Erfolgsmeldung „Archiviert. …“ fehlt');
	});

	test('"unarchive" -> PATCH {archived:false} ohne Rückfrage, Meldung „Reaktiviert.“ (AC-10)', async () => {
		const { aktion, u, a, gotos } = await seite();
		aktion('unarchive');
		await bis(() => nach('PATCH', '/state').length === 1 && ruhig(u)(), 'PATCH nach "unarchive"');
		a.ctl.cancel();
		assert.deepEqual(nach('PATCH', '/state').map((c) => c.anfrage), [{ archived: false }]);
		assert.deepEqual(gotos, []);
		assert.ok(meldet(u, 'Reaktiviert.'), 'Erfolgsmeldung „Reaktiviert.“ fehlt');
	});

	test('"pause"/"resume" melden „Pausiert. …“ bzw. „Fortgesetzt. …“ (AC-11)', async () => {
		const { aktion, u, a } = await seite();
		aktion('pause');
		await bis(() => nach('PATCH', '/state').length === 1 && ruhig(u)(), 'PATCH nach "pause"');
		assert.ok(meldet(u, 'Pausiert. Bis ‚Fortsetzen‘ kommen keine Briefings und Alarme.'), 'Meldung „Pausiert. …“ fehlt');
		aktion('resume');
		await bis(() => nach('PATCH', '/state').length === 2 && ruhig(u)(), 'PATCH nach "resume"');
		a.ctl.cancel();
		assert.ok(meldet(u, 'Fortgesetzt. Das nächste Briefing kommt wie geplant.'), 'Meldung „Fortgesetzt. …“ fehlt');
	});
});

describe('F001/F017: Senden erst nach Bestaetigung, mit der gewaehlten Berichtsart', () => {
	test('Aktion "send" im Hub-Dispatch loest keinen Versand aus', async () => {
		const { aktion, u } = await seite();
		aktion('send');
		await tick(u);
		assert.equal(nach('POST', '/send').length, 0);
	});

	// #3440: der Hub sendet über das Menü „Test schicken ▾“ (handleTest); das Segment liefert die Berichtsart.
	test('handleTest({telegram, evening}) -> genau ein POST /send?report_type=evening&channel=telegram, Erfolg wird gemeldet', async () => {
		const { u } = await seite();
		await u.handleTest({ kanal: 'telegram', berichtsart: 'evening' });
		clearTimeout(u.sendTimer);
		const posts = nach('POST', '/send');
		assert.equal(posts.length, 1);
		assert.match(posts[0].path, /report_type=evening/);
		assert.match(posts[0].path, /channel=telegram/);
		assert.equal(u.sendStatus, 'ok');
	});

	test('handleTest({alle, morning}) sendet den Morgen-Bericht ohne channel', async () => {
		const { u } = await seite();
		await u.handleTest({ kanal: 'alle', berichtsart: 'morning' });
		clearTimeout(u.sendTimer);
		const posts = nach('POST', '/send');
		assert.equal(posts.length, 1);
		assert.match(posts[0].path, /report_type=morning/);
		assert.doesNotMatch(posts[0].path, /channel=/);
	});
});

// #3443 (feat_3443 AC-3/AC-6/AC-10): „Aktivieren“ im Trip-Entwurf (keine Etappe mit Datum). Der Klick schreibt nichts,
// nennt, was fehlt, und öffnet den Reiter Etappen — gleich, ob aus dem Kopf (handleAktivieren, Prop onAktivieren)
// oder aus dem Kebab (handleHubAction('activate')).
const ohneDatum = () => {
	const t = P.vollerTrip() as Record<string, any>;
	return { ...t, stages: t.stages.map((st: Record<string, unknown>) => ({ ...st, date: '' })) };
};
const SCHREIBEND = new Set(['PUT', 'PATCH', 'POST', 'DELETE']);

describe('#3443: „Aktivieren“ im Trip-Entwurf nennt, was fehlt, und öffnet Etappen — ohne Schreibzugriff', () => {
	test('Kebab „activate“ -> Meldung „Zum Aktivieren fehlt noch: Datum der Etappen.“, goto ?tab=etappen, kein Schreibaufruf', async () => {
		const { aktion, u, gotos, gotoArgs } = await seite(ohneDatum());
		assert.equal(u.lifecycle, 'draft', 'Messaufbau: Trip ohne Datum ist ein Entwurf');
		aktion('activate');
		await tick(u);
		assert.ok(meldet(u, 'Zum Aktivieren fehlt noch: Datum der Etappen.'), 'Hinweis „Zum Aktivieren fehlt noch: Datum der Etappen.“ fehlt');
		assert.equal(gotos.length, 1, `Navigation: ${JSON.stringify(gotos)}`);
		assert.match(gotos[0], /[?&]tab=etappen(&|$)/, `Ziel ${gotos[0]}`);
		assert.deepEqual(gotoArgs[0][1], { noScroll: true, keepFocus: true }, 'goto ohne noScroll/keepFocus (Seite springt)');
		assert.deepEqual(server.calls.filter((c) => SCHREIBEND.has(c.method)).map((c) => `${c.method} ${c.path}`), [], 'Schreibaufruf beim Aktivieren-Klick');
	});

	test('Kopf-Knopf (handleAktivieren) und Kebab („activate“) wirken gleich (AC-6)', async () => {
		const kopf = await seite(ohneDatum());
		assert.equal(typeof kopf.u.handleAktivieren, 'function', 'Trip-Hub hat keine Seitenfunktion handleAktivieren (Kopf-Knopf)');
		kopf.u.handleAktivieren();
		await tick(kopf.u);
		const kopfStand = { gotos: [...kopf.gotos], meldung: Object.values(kopf.u).filter((v) => typeof v === 'string' && v.startsWith('Zum Aktivieren')) };
		const kebab = await seite(ohneDatum());
		kebab.aktion('activate');
		await tick(kebab.u);
		const kebabStand = { gotos: [...kebab.gotos], meldung: Object.values(kebab.u).filter((v) => typeof v === 'string' && v.startsWith('Zum Aktivieren')) };
		assert.ok(kopfStand.gotos.length === 1 && kopfStand.meldung.length >= 1, `Kopf wirkt nicht: ${JSON.stringify(kopfStand)}`);
		assert.deepEqual(kebabStand, kopfStand);
	});

	test('aktiver Trip: „activate“ (Stand-Wettlauf) zeigt keinen Hinweis, navigiert nicht, schreibt nicht', async () => {
		const { aktion, u, gotos } = await seite();
		aktion('activate');
		await tick(u);
		assert.deepEqual(gotos, []);
		assert.ok(!Object.values(u).some((v) => typeof v === 'string' && v.startsWith('Zum Aktivieren')), 'Hinweis bei vollständigem Trip');
		assert.equal(server.calls.filter((c) => SCHREIBEND.has(c.method)).length, 0);
	});
});
