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
import { adoptEtagFromPageLoad, clearEtagRegistry, getKnownEtag } from '../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from './fakeTripServer.ts';
// #2317 (Faelle ganz unten)
import { SaveStatus } from '../stores/saveStatusStore.svelte.ts';
import { installiereSitzungsspeicher, entferneSitzungsspeicher } from './sitzungsspeicherDoppel.ts';

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

// ###########################################################################
// TDD RED — Issue #2317 (Epic #2127): Nachladen nach dem Neuladen und If-Match.
// Spec: docs/specs/modules/speicherung_beim_neuladen.md
//   § Implementation Details „Baustein 3", § AC-11 (Unit-Anteil), § AC-12
//
// Zielschnittstelle (existiert noch NICHT → dynamischer Import je Test):
//   stores/nachEntladenNachladen.ts: starteNachladenNachEntladen(...), tripNachladeQuelle(tripId)
//     tripNachladeQuelle: GET /api/trips/{id} ueber `api`, fassung = ETag
//   pwa/geraetespeicher.ts: merkeSpeicherungBeimEntladen(kennung)
//
// Szenario (Kern von #2317): der SSR-Seitenaufbau las den Trip, BEVOR der
// keepalive-PUT des alten Dokuments beim Server ankam. Die neue Seite traegt
// also den veralteten Stempel E1, der Server steht schon auf E2.
// Ein Browser-Neuladen ist ein frischer JS-Realm — deshalb wird die Registry
// zwischen „altem" und „neuem" Dokument geleert und nur der SSR-Stempel
// uebernommen (`adoptEtagFromPageLoad`). Ohne diesen Schritt haette der
// keepalive-PUT die Registry selbst schon auf E2 gesetzt (api.ts:150-156) und
// der Test waere ohne jedes Nachladen gruen.
//
// „Anderes Geraet" schreibt direkt ueber `server.handler` — an `api.ts` und
// damit an der lokalen Registry vorbei, genau wie ein zweites Geraet.
// ###########################################################################

type NachladeModul = {
	starteNachladenNachEntladen: (o: Record<string, unknown>) => { stoppen(): void; fertig: Promise<void> };
	tripNachladeQuelle: (tripId: string) => () => Promise<{ stand: unknown; fassung: string }>;
};

/** Echte SaveStatus-Instanz ohne Konstruktor (Muster aus saveStatus.test.ts). */
function createSaveStatus(tripId: string): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const fields = inst as unknown as Record<string, unknown>;
	fields.state = 'idle';
	fields.savedAt = null;
	fields.error = null;
	fields._timer = null;
	fields._pendingFn = null;
	fields._inflight = null;
	fields._lastFailed = null;
	fields._unresolvedError = null;
	fields._tripId = tripId;
	return inst;
}

/**
 * Altes Dokument laedt E1, speichert beim Entladen per keepalive (Server → E2),
 * neues Dokument uebernimmt den veralteten SSR-Stempel E1.
 */
async function neuladenMitVeraltetemSeitenaufbau(): Promise<{ e1: string; e2: string }> {
	// Altes Dokument: Seite geladen, Stempel E1
	await api.get('/api/trips/gr20');
	const e1 = server.etagOf('gr20');
	// SSR-Aufbau des NEUEN Dokuments liest hier noch E1 ...
	const ssrStempel = e1;
	// ... dann kommt der keepalive-PUT des alten Dokuments beim Server an
	await api.put('/api/trips/gr20', { name: 'Wert vom Entladen' }, { keepalive: true });
	const e2 = server.etagOf('gr20');
	assert.notEqual(e2, e1, 'Vorbedingung: der keepalive-PUT hat den Server-Stand veraendert');

	// Neues Dokument = frischer JS-Realm
	clearEtagRegistry();
	adoptEtagFromPageLoad('gr20', ssrStempel);
	assert.equal(getKnownEtag('gr20'), e1, 'Vorbedingung: die neue Seite kennt nur den veralteten SSR-Stempel');
	return { e1, e2 };
}

/** Zeitgeber, der jeden Timer im naechsten Makrotask ausfuehrt (echte Reihenfolge, keine Wartezeit). */
const sofortZeitgeber = {
	setTimeout: (fn: () => void) => setImmediate(fn),
	clearTimeout: (h: unknown) => clearImmediate(h as ReturnType<typeof setImmediate>)
};

async function fertigBinnen(p: Promise<void>, ms = 2_000): Promise<void> {
	let h: ReturnType<typeof setTimeout> | undefined;
	try {
		await Promise.race([
			p,
			new Promise<never>((_, rej) => {
				h = setTimeout(() => rej(new Error('`fertig` hat sich nicht aufgeloest')), ms);
			})
		]);
	} finally {
		clearTimeout(h);
	}
}

/** Neuladen + Nachladen ueber die echte Trip-Quelle; liefert die Uebernahmen. */
async function neuladenUndNachladen() {
	const nach = (await import('../stores/nachEntladenNachladen.ts')) as unknown as NachladeModul;
	const speicher = (await import('../pwa/geraetespeicher.ts')) as unknown as {
		merkeSpeicherungBeimEntladen: (k: { typ: 'trip' | 'vergleich'; id: string }) => void;
	};
	assert.equal(typeof nach.starteNachladenNachEntladen, 'function', 'starteNachladenNachEntladen fehlt');
	assert.equal(typeof nach.tripNachladeQuelle, 'function', 'tripNachladeQuelle fehlt');
	assert.equal(typeof speicher.merkeSpeicherungBeimEntladen, 'function', 'merkeSpeicherungBeimEntladen fehlt');

	const { e1, e2 } = await neuladenMitVeraltetemSeitenaufbau();
	// Der Waechter des alten Dokuments hat den Merker gesetzt
	speicher.merkeSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' });

	const uebernahmen: Array<{ stand: unknown; fassung: string }> = [];
	const h = nach.starteNachladenNachEntladen({
		kennung: { typ: 'trip', id: 'gr20' },
		ctl: createSaveStatus('gr20'),
		ausgelieferteFassung: e1,
		holen: nach.tripNachladeQuelle('gr20'),
		uebernehmen: (stand: unknown, fassung: string) => void uebernahmen.push({ stand, fassung }),
		zeitgeber: sofortZeitgeber
	});
	await fertigBinnen(h.fertig);
	return { e1, e2, uebernahmen };
}

describe('Issue #2317 AC-11/AC-12: Nachladen haelt den If-Match-Schutz korrekt', () => {
	beforeEach(() => {
		installiereSitzungsspeicher();
	});
	afterEach(() => {
		entferneSitzungsspeicher();
	});

	test('Gegenprobe (Szenario echt): OHNE Nachladen scheitert die naechste Speicherung faelschlich mit 412', async () => {
		// GIVEN: neue Seite mit veraltetem SSR-Stempel, kein Nachladen
		await neuladenMitVeraltetemSeitenaufbau();

		// WHEN: der Nutzer speichert regulaer
		await assert.rejects(
			api.put('/api/trips/gr20', { name: 'naechste Aenderung' }),
			(e: { status?: number }) => e?.status === 412,
			'Vorbedingung des Szenarios: ohne Nachladen muss die Speicherung am veralteten Stempel scheitern'
		);
	});

	test('AC-11: nach Uebernahme der neueren Fassung speichert der Nutzer ohne faelschlichen 412', async () => {
		// GIVEN: Neuladen mit veraltetem Seitenaufbau, Nachladen ueber die echte Trip-Quelle
		const { e2, uebernahmen } = await neuladenUndNachladen();

		// THEN (Nachladen): die neuere Server-Fassung wurde uebernommen
		assert.equal(uebernahmen.length, 1, 'die neuere Server-Fassung muss genau einmal uebernommen werden');
		assert.equal(uebernahmen[0].fassung, e2, 'uebernommene Fassung = aktueller ETag des Servers');
		assert.equal(
			(uebernahmen[0].stand as { name?: string }).name,
			'Wert vom Entladen',
			'der uebernommene Stand muss den beim Entladen gespeicherten Wert tragen'
		);
		assert.equal(getKnownEtag('gr20'), e2, 'die ETag-Registry muss die uebernommene Fassung tragen');

		// WHEN: der Nutzer direkt danach etwas aendert und regulaer speichert
		await api.put('/api/trips/gr20', { name: 'direkt danach' });

		// THEN: kein Konflikt
		const call = server.calls[server.calls.length - 1];
		assert.equal(call.method, 'PUT');
		assert.equal(call.keepalive, false);
		assert.equal(call.ifMatch, e2, 'die Speicherung muss mit der uebernommenen Fassung als If-Match laufen');
		assert.equal(call.status, 200, 'nach der Uebernahme darf kein faelschlicher 412 entstehen');
	});

	test('F004: aendert ein anderer Vorgang die Registry, WAEHREND der Nachlade-GET unterwegs ist, wird nur eine Fassung uebernommen, die der Registry entspricht', async () => {
		// GIVEN: Pruefstand mit langsamer Leseantwort (Schreibvorgaenge sofort)
		server.restore();
		server = createFakeTripServer({ latencyMs: (method) => (method === 'GET' ? 40 : 0) });
		server.install();
		const nach = (await import('../stores/nachEntladenNachladen.ts')) as unknown as NachladeModul;
		const speicher = (await import('../pwa/geraetespeicher.ts')) as unknown as {
			merkeSpeicherungBeimEntladen: (k: { typ: 'trip' | 'vergleich'; id: string }) => void;
		};
		const { e1, e2 } = await neuladenMitVeraltetemSeitenaufbau();
		speicher.merkeSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' });

		// WHEN: das Nachladen startet (GET unterwegs) ...
		const uebernahmen: Array<{ fassung: string; registry: string | undefined }> = [];
		const h = nach.starteNachladenNachEntladen({
			kennung: { typ: 'trip', id: 'gr20' },
			ctl: createSaveStatus('gr20'),
			ausgelieferteFassung: e1,
			holen: nach.tripNachladeQuelle('gr20'),
			uebernehmen: (_stand: unknown, fassung: string) => void uebernahmen.push({ fassung, registry: getKnownEtag('gr20') }),
			zeitgeber: sofortZeitgeber
		});
		// ... und ein anderer Reiter speichert direkt ueber `api` (nicht ueber den
		// Speicher-Takt): mit dem veralteten SSR-Stempel → 412, die Registry wird verworfen.
		await assert.rejects(
			api.put('/api/trips/gr20', { name: 'anderer Reiter' }),
			(e: { status?: number }) => e?.status === 412,
			'Vorbedingung: der konkurrierende Schreibvorgang veraendert die Registry, waehrend der GET laeuft'
		);
		assert.equal(getKnownEtag('gr20'), undefined, 'Vorbedingung: die Registry ist verworfen');
		await fertigBinnen(h.fertig, 3_000);

		// THEN: uebernommen wird genau eine Fassung, und die Registry traegt sie —
		// sonst liefe die naechste Speicherung ohne (oder mit fremdem) If-Match.
		assert.equal(uebernahmen.length, 1, 'die neuere Fassung muss (im Folgeversuch) uebernommen werden');
		assert.equal(uebernahmen[0].fassung, e2);
		assert.equal(
			uebernahmen[0].registry,
			uebernahmen[0].fassung,
			'bei der Uebernahme muss die Registry genau die uebernommene Fassung tragen'
		);
	});

	test('AC-12: aendert ein anderes Geraet den Trip nach dem Nachladen, erkennt die App den echten Konflikt (412)', async () => {
		// GIVEN: Nachladen hat uebernommen, der Nutzer hat einmal erfolgreich gespeichert
		const { uebernahmen } = await neuladenUndNachladen();
		assert.equal(uebernahmen.length, 1, 'Vorbedingung: das Nachladen hat uebernommen');
		await api.put('/api/trips/gr20', { name: 'direkt danach' });
		const eigenerStand = getKnownEtag('gr20');
		assert.equal(server.calls[server.calls.length - 1].status, 200, 'Vorbedingung: eigene Speicherung angenommen');

		// WHEN: ein anderes Geraet schreibt — an der lokalen Registry vorbei
		const fremd = await server.handler('/api/trips/gr20', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'anderes Geraet' })
		});
		assert.equal(fremd.status, 200, 'Vorbedingung: die fremde Aenderung wurde angenommen');
		assert.notEqual(server.etagOf('gr20'), eigenerStand, 'Vorbedingung: der Server steht auf einer fremden Fassung');

		// THEN: die naechste eigene Speicherung scheitert am echten Konflikt
		await assert.rejects(
			api.put('/api/trips/gr20', { name: 'dieses Geraet' }),
			(e: { status?: number }) => e?.status === 412,
			'ein echter Konflikt muss weiterhin als 412 erkannt werden (If-Match-Schutz bleibt wirksam)'
		);
		const call = server.calls[server.calls.length - 1];
		assert.equal(call.ifMatch, eigenerStand, 'die Speicherung muss den eigenen, nun veralteten Stand als If-Match tragen');
		assert.deepEqual(
			(server.storedBody('gr20') as { name?: string }).name,
			'anderes Geraet',
			'die fremde Aenderung darf nicht ueberschrieben werden'
		);
	});
});
