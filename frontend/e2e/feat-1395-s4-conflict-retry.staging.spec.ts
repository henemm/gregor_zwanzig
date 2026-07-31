// Staging-Nachpruefung Issue #1395 Scheibe S4 — "Nochmal speichern" bei
// ETag-Konflikt.
//
// Spec: docs/specs/modules/issue_1395_s4_conflict_retry.md
// Server-Vertrag: docs/specs/modules/issue_1395_s2_etag_ifmatch.md · ADR-0036
// Vorbild: feat-1395-s3-etag-ifmatch.staging.spec.ts (Fall 2) — dieselbe
// Konflikt-Erzeugung (fremder PUT ohne If-Match an der Oberflaeche vorbei),
// erweitert um den neuen Retry-Knopf.
//
// Was NUR hier (nicht im Kern) geprueft werden kann: der ECHTE Klickpfad im
// ECHTEN Browser gegen den ECHTEN Go-Server — AC-1/AC-2 end-to-end. AC-3
// (Race waehrend des Refresh), AC-4 (generische Fehler) und AC-6 (ohne
// tripId) sind bereits deterministisch im Kern bewiesen
// (saveStatusConflictRetry.test.ts) und werden hier NICHT erneut versucht —
// ein Zeitfenster-Race in echtem Netzwerkverkehr waere strukturell flaky.

import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { E2E_TEST_PREFIX } from './helpers';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_FILE = path.join(__dirname, 'playwright', '.auth', 'staging-1395-s4.json');

const createdTripIds: string[] = [];

async function createTrip(request: APIRequestContext, tag: string) {
	const suffix = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
	const id = `e2e-gz-1395s4-${tag}-${suffix}`;
	const name = `${E2E_TEST_PREFIX}1395S4-${tag}-${suffix}`;
	createdTripIds.push(id);
	const res = await request.post('/api/trips', {
		data: {
			id,
			name,
			region: 'Korsika',
			stages: [
				{
					id: `${tag}-s1`,
					name: 'Tag 1',
					date: '2026-08-10',
					waypoints: [
						{ id: `${tag}-a1`, name: `${tag}-a1`, lat: 42.0, lon: 9.0, elevation_m: 800 },
						{ id: `${tag}-b1`, name: `${tag}-b1`, lat: 42.04, lon: 9.0, elevation_m: 800 }
					]
				}
			]
		}
	});
	expect(res.ok(), `POST /api/trips HTTP ${res.status()} — ${await res.text()}`).toBeTruthy();
	return (await res.json()) as { id: string; name: string };
}

async function deleteTrip(request: APIRequestContext, id: string) {
	const res = await request.delete(`/api/trips/${id}`);
	return res.status();
}

async function fetchTrip(request: APIRequestContext, id: string) {
	const res = await request.get(`/api/trips/${id}`);
	expect(res.ok(), `GET /api/trips/${id} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, any>;
}

function saveIndicator(page: Page) {
	return page.locator('[data-testid="save-indicator"]:visible').first();
}

test.beforeEach(async ({ baseURL, page }) => {
	assertNotProdBaseURL(baseURL ?? '');
	await page.setViewportSize({ width: 1440, height: 1000 });
});

test.afterAll(async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	if (createdTripIds.length === 0) return;
	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: {
			username: process.env.GZ_VALIDATOR_USER ?? 'admin',
			password: process.env.GZ_VALIDATOR_PASS ?? 'test1234'
		},
		storageState: AUTH_FILE
	});
	for (const id of createdTripIds) {
		const res = await ctx.delete(`/api/trips/${id}`);
		console.log(`[#1395 S4 Raeumlauf] DELETE /api/trips/${id} -> HTTP ${res.status()}`);
	}
	await ctx.dispose();
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-1/AC-2 end-to-end: 412 im echten Browser -> Konflikt-Zustand mit Knopf
// -> Klick -> Refresh (GET) VOR dem Retry (PUT) -> Retry gelingt -> "Gespeichert".
// ─────────────────────────────────────────────────────────────────────────────
test('#1395 S4 (AC-1/AC-2): 412 zeigt "Nochmal speichern" — Klick frischt auf und wiederholt erfolgreich', async ({
	page,
	request
}) => {
	test.setTimeout(300_000);
	const trip = await createTrip(request, 'retry');
	try {
		// Synchroner Listener (KEIN async/await im Handler) auf das 'request'-
		// Ereignis — feuert VOR Response/RequestFinished, wall-clock via
		// Date.now(). Vermeidet den Race eines async-`requestfinished`-Handlers,
		// der um dieselbe Anfrage mit dem eigenen await-Fortsatz konkurriert.
		const dispatchLog: { method: string; ts: number }[] = [];
		page.on('request', (req) => {
			const url = new URL(req.url());
			if (url.pathname !== `/api/trips/${trip.id}`) return;
			if (req.method() !== 'GET' && req.method() !== 'PUT') return;
			dispatchLog.push({ method: req.method(), ts: Date.now() });
		});

		await page.goto(`/trips/${trip.id}?tab=alarme`);
		await expect(page.getByTestId('alarme-tab')).toBeVisible({ timeout: 30_000 });
		const toggle = page
			.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible')
			.first();
		await expect(toggle).toBeVisible({ timeout: 20_000 });

		// An der Oberflaeche vorbei: fremde Aenderung ohne If-Match — server-seitig
		// angenommen (S2-Rollout-Politik), macht den Browser-Stempel veraltet.
		const fremdRes = await request.put(`/api/trips/${trip.id}`, {
			data: { alert_channels: { email: false, telegram: true, sms: true } }
		});
		expect(fremdRes.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

		// Im Browser speichern — der Stempel ist jetzt veraltet -> 412.
		const rejected = page.waitForResponse(
			(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 60_000 }
		);
		await toggle.click();
		const rejectedRes = await rejected;
		expect(rejectedRes.status(), 'Vorbedingung: der veraltete Schreibvorgang wird abgelehnt').toBe(412);

		// AC-1: der Anzeiger wechselt in den NEUEN 'conflict'-Zustand mit Knopf.
		const indicator = saveIndicator(page);
		await expect(indicator, "AC-1: Anzeiger zeigt 'conflict' statt generischem 'error'").toHaveAttribute(
			'data-state',
			'conflict',
			{ timeout: 20_000 }
		);
		const retryButton = indicator.getByRole('button', { name: 'Nochmal speichern' });
		await expect(retryButton, 'AC-1: Wiederholen-Knopf ist sichtbar').toBeVisible({ timeout: 10_000 });
		await page.screenshot({
			path: path.join(__dirname, 'playwright', '1395-s4-conflict-button.png'),
			fullPage: false
		});

		// AC-1: Klick loest zuerst einen GET (Refresh), danach automatisch denselben
		// PUT erneut aus — ohne dass hier irgendetwas erneut eingegeben wird.
		const refreshGet = page.waitForResponse(
			(r) => r.request().method() === 'GET' && new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 30_000 }
		);
		const retryPut = page.waitForResponse(
			(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 30_000 }
		);
		await retryButton.click();
		const refreshRes = await refreshGet;
		const retryRes = await retryPut;

		expect(refreshRes.status(), 'AC-1: der Refresh-GET gelingt').toBe(200);
		expect(retryRes.status(), 'AC-2: der wiederholte Speichervorgang gelingt (kein erneutes 412)').toBe(200);

		// Reihenfolge ueber wall-clock-Zeitstempel des Absendezeitpunkts (aus dem
		// synchronen 'request'-Listener oben): der GET-Dispatch muss vor dem
		// PUT-Dispatch liegen — retryConflict() awaitet refreshTripEtag() VOR
		// doSave(), der PUT kann also erst NACH Abschluss des GET losgehen.
		const getDispatch = dispatchLog.find((e) => e.method === 'GET');
		const putDispatches = dispatchLog.filter((e) => e.method === 'PUT');
		expect(getDispatch, 'Refresh-GET wurde mitgeschnitten').toBeTruthy();
		expect(putDispatches.length, 'zwei PUTs: der abgelehnte und der Retry').toBeGreaterThanOrEqual(2);
		const retryPutDispatch = putDispatches[putDispatches.length - 1];
		expect(
			retryPutDispatch.ts,
			'AC-1: der Retry-PUT wird erst NACH dem Absenden des Refresh-GET losgeschickt'
		).toBeGreaterThanOrEqual(getDispatch!.ts);
		expect(
			retryRes.request().headers()['if-match'],
			'AC-1: der Retry-PUT traegt den frisch aufgefrischten Stand als If-Match'
		).toMatch(/^"[0-9a-f-]+"$/);

		// AC-2: der Anzeiger zeigt danach wieder "Gespeichert" (idle), kein Konflikt mehr.
		await expect(indicator, 'AC-2: Anzeiger kehrt zu idle zurueck').toHaveAttribute('data-state', 'idle', {
			timeout: 20_000
		});

		// Die eigene (zuvor abgelehnte) Aenderung ist jetzt tatsaechlich gespeichert.
		const danach = await fetchTrip(request, trip.id);
		console.log(`[#1395 S4] Stand nach Retry: official_warnings=${JSON.stringify(danach.official_warnings)}`);
	} finally {
		console.log(`[#1395 S4] DELETE -> HTTP ${await deleteTrip(request, trip.id)} (${trip.id})`);
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Aufraeum-Kontrolle.
// ─────────────────────────────────────────────────────────────────────────────
test('#1395 S4 Aufraeum-Kontrolle: keine Test-Tour dieses Laufs bleibt liegen', async ({ request }) => {
	const res = await request.get('/api/trips');
	expect(res.ok(), `GET /api/trips HTTP ${res.status()}`).toBeTruthy();
	const trips = (await res.json()) as Array<{ id: string; name?: string }>;
	const leftovers = trips
		.filter((t) => (t.name ?? '').startsWith(`${E2E_TEST_PREFIX}1395S4-`))
		.map((t) => `${t.id} (${t.name})`);
	console.log(`[#1395 S4 Aufraeumen] Reste: ${JSON.stringify(leftovers)}`);
	expect(leftovers, 'keine Test-Tour dieses Laufs bleibt liegen').toEqual([]);
});
