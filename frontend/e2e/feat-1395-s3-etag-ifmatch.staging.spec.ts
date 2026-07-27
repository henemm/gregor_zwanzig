// Staging-Nachpruefung Issue #1395 Scheibe S3 — „Das Frontend fuehrt den
// Aenderungsstempel."
//
// Spec: docs/specs/modules/issue_1395_s3_etag_registry.md
// Server-Vertrag: docs/specs/modules/issue_1395_s2_etag_ifmatch.md · ADR-0036
//
// Das ist der Umschaltpunkt: Ab dieser Scheibe schickt die Oberflaeche den
// Stempel (`If-Match`) mit, und ein veralteter Schreibvorgang wird zum ersten
// Mal wirklich mit 412 abgelehnt. 19 Trip-Schreibstellen laufen durch DENSELBEN
// Trichter (`frontend/src/lib/api.ts`) — ein Fehler hier bricht nicht eine
// Funktion, sondern JEDES Speichern der Anwendung. Darum wird hier nicht nur
// der Konfliktfall geprueft, sondern ausdruecklich auch, dass normales
// Speichern in mehreren Reitern weiterhin funktioniert.
//
// Nachgewiesen wird ueber den ECHTEN Klickpfad plus den ECHTEN Netzwerkverkehr
// (page.on('request') → allHeaders(), Antwort-Status und -ETag), zusaetzlich
// gegengeprueft per GET /api/trips/{id}. Test-Touren tragen das reservierte
// Praefix `E2E-GZ-` und werden im finally-Block bzw. im afterAll-Netz geloescht.

import { test, expect, type Page, type Request, type APIRequestContext } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { E2E_TEST_PREFIX } from './helpers';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_FILE = path.join(__dirname, 'playwright', '.auth', 'staging-1395-s3.json');

/** Die vom Server (internal/handler/etag.go) gelieferte 412-Meldung — woertlich. */
const CONFLICT_MESSAGE =
	'Der Stand wurde zwischenzeitlich an anderer Stelle geaendert. ' +
	'Bitte neu laden und die Aenderung erneut vornehmen.';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

const SEED_METRICS = ['temperature', 'wind', 'precipitation', 'gust', 'uv_index'].map((id, i) => ({
	metric_id: id,
	enabled: true,
	use_friendly_format: true,
	horizons: { today: true, tomorrow: true, day_after: true },
	bucket: 'primary',
	order: i
}));

/** Alle in dieser Datei angelegten Test-Touren — Sicherheitsnetz fuer den Fall,
 *  dass ein Test in eine Zeitschranke laeuft und sein `finally` den bereits
 *  geschlossenen Test-Kontext nicht mehr benutzen kann. */
const createdTripIds: string[] = [];

async function createTrip(
	request: APIRequestContext,
	tag: string,
	extra: Record<string, unknown> = {}
) {
	const suffix = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
	const id = `e2e-gz-1395s3-${tag}-${suffix}`;
	const name = `${E2E_TEST_PREFIX}1395S3-${tag}-${suffix}`;
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
					waypoints: [wp(`${tag}-a1`, 42.0), wp(`${tag}-b1`, 42.04)]
				}
			],
			...extra
		}
	});
	expect(res.ok(), `POST /api/trips HTTP ${res.status()} — ${await res.text()}`).toBeTruthy();
	return (await res.json()) as { id: string; name: string };
}

async function deleteTrip(request: APIRequestContext, id: string) {
	const res = await request.delete(`/api/trips/${id}`);
	return res.status();
}

/** Gespeicherter Stand direkt vom Server. */
async function fetchTrip(request: APIRequestContext, id: string) {
	const res = await request.get(`/api/trips/${id}`);
	expect(res.ok(), `GET /api/trips/${id} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, any>;
}

interface WriteLogEntry {
	pfad: string;
	ifMatch: string;
	status: number;
	etag: string;
}

/** Zeichnet die PUTs auf, die der BROWSER absetzt. Der `request`-Fixture-Kontext
 *  laeuft daran vorbei — Seed-, Fremd- und Kontroll-Aufrufe verfaelschen den
 *  Mitschnitt also nicht. */
function recordBrowserTripPuts(page: Page, tripId: string): Request[] {
	const reqs: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/trips/${tripId}`)) reqs.push(req);
	});
	return reqs;
}

/** Loest die aufgezeichneten Anfragen in ein protokollierbares Bild auf:
 *  Adresse, gesendete `If-Match`-Kopfzeile, Antwort-Status, zurueckgegebener
 *  Stempel. Reihenfolge = Absende-Reihenfolge. */
async function toWriteLog(reqs: Request[]): Promise<WriteLogEntry[]> {
	const out: WriteLogEntry[] = [];
	for (const req of reqs) {
		const reqHeaders = await req.allHeaders();
		const res = await req.response();
		const resHeaders = res ? await res.allHeaders() : {};
		out.push({
			pfad: new URL(req.url()).pathname,
			ifMatch: reqHeaders['if-match'] ?? '(kein If-Match)',
			status: res ? res.status() : -1,
			etag: resHeaders['etag'] ?? '(kein ETag)'
		});
	}
	return out;
}

function logWrites(label: string, log: WriteLogEntry[]): void {
	console.log(`[#1395 S3 ${label}] Schreibvorgaenge des Browsers:`);
	log.forEach((e, i) =>
		console.log(
			`  ${i + 1}. PUT ${e.pfad}\n` +
				`     If-Match : ${e.ifMatch}\n` +
				`     Status   : ${e.status}\n` +
				`     ETag neu : ${e.etag}`
		)
	);
}

/** Sichtbarer Speicher-Anzeiger (Testids kommen im DOM doppelt vor: Mobil/Desktop). */
function saveIndicator(page: Page) {
	return page.locator('[data-testid="save-indicator"]:visible').first();
}

test.beforeEach(async ({ baseURL, page }) => {
	assertNotProdBaseURL(baseURL ?? '');
	await page.setViewportSize({ width: 1440, height: 1000 });
});

// Sicherheitsnetz-Raeumlauf mit EIGENEM Request-Kontext (worker-scoped
// `playwright`-Fixture): laeuft auch dann noch, wenn ein Test in seine
// Zeitschranke gelaufen ist und sein Test-Kontext bereits geschlossen wurde.
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
		console.log(`[#1395 S3 Raeumlauf] DELETE /api/trips/${id} -> HTTP ${res.status()}`);
	}
	await ctx.dispose();
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall 1 — AC-3 (Kernfall) + AC-2.
//
// Der Wetter-Reiter setzt beim Speichern ZWEI Schreibvorgaenge hintereinander
// ab: erst `PUT /api/trips/{id}/weather-config`, dann `PUT /api/trips/{id}`.
// Der erste veraendert die Datei und damit den Stempel. Traegt der zweite den
// alten, scheitert JEDES Speichern in diesem Reiter mit 412.
// ─────────────────────────────────────────────────────────────────────────────
test('#1395 S3 Fall 1 (AC-3/AC-2): Wetter-Reiter — beide Schreibvorgaenge gelingen, der zweite traegt den NEUEN Stempel', async ({
	page,
	request
}) => {
	test.setTimeout(300_000);
	const trip = await createTrip(request, 'weather', {
		display_config: { metrics: SEED_METRICS }
	});
	try {
		const puts = recordBrowserTripPuts(page, trip.id);

		await page.goto(`/trips/${trip.id}?tab=weather`);
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible({ timeout: 30_000 });

		// Bisher inaktive Metrik zuschalten — echte Nutzergeste, loest den
		// Doppel-Schreibvorgang aus (WeatherMetricsTab.scheduleAutoSave).
		const rainToggle = page
			.locator('[data-testid="wm2-grundauswahl"] .toggle-btn')
			.filter({ hasText: 'Regenwahrscheinlichkeit' })
			.first();
		await expect(rainToggle).toBeVisible({ timeout: 20_000 });
		await expect(rainToggle).not.toHaveClass(/\bon\b/);

		const secondPut = page.waitForResponse(
			(r) =>
				r.request().method() === 'PUT' &&
				new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 60_000 }
		);
		await rainToggle.click();
		await secondPut;

		const log = await toWriteLog(puts);
		logWrites('Fall 1', log);

		// Genau die beiden erwarteten Schreibvorgaenge, in dieser Reihenfolge.
		expect(log.map((e) => e.pfad), 'zwei Schreibvorgaenge in fester Reihenfolge').toEqual([
			`/api/trips/${trip.id}/weather-config`,
			`/api/trips/${trip.id}`
		]);

		// AC-2: beide tragen ueberhaupt eine If-Match-Kopfzeile.
		expect(log[0].ifMatch, 'AC-2: erster Schreibvorgang traegt If-Match').toMatch(/^"[0-9a-f]+"$/);
		expect(log[1].ifMatch, 'AC-2: zweiter Schreibvorgang traegt If-Match').toMatch(/^"[0-9a-f]+"$/);

		// AC-3: beide gelingen …
		expect(log[0].status, 'AC-3: erster Schreibvorgang gelingt').toBe(200);
		expect(log[1].status, 'AC-3: zweiter Schreibvorgang gelingt (kein 412)').toBe(200);

		// … und der zweite traegt NICHT den alten, sondern den vom ersten
		// zurueckgegebenen neuen Stempel. Das ist der eigentliche Nachweis.
		expect(log[0].etag, 'erster Schreibvorgang liefert einen neuen Stempel').toMatch(
			/^"[0-9a-f]+"$/
		);
		expect(
			log[1].ifMatch,
			'AC-3: zweiter Schreibvorgang traegt den vom ersten zurueckgegebenen Stempel'
		).toBe(log[0].etag);
		expect(
			log[1].ifMatch,
			'AC-3: zweiter Schreibvorgang traegt einen ANDEREN Stempel als der erste'
		).not.toBe(log[0].ifMatch);

		// Der Speicher-Anzeiger meldet keinen Fehler.
		await expect(saveIndicator(page)).not.toHaveAttribute('data-state', 'error', {
			timeout: 20_000
		});

		// Die Aenderung ist wirklich gespeichert — nach hartem Neuladen noch da.
		await page.reload();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible({ timeout: 30_000 });
		const rainAfter = page
			.locator('[data-testid="wm2-grundauswahl"] .toggle-btn')
			.filter({ hasText: 'Regenwahrscheinlichkeit' })
			.first();
		await expect(rainAfter, 'UI nach Neuladen: Metrik ist aktiv').toHaveClass(/\bon\b/, {
			timeout: 20_000
		});

		const saved = await fetchTrip(request, trip.id);
		const active = (saved.display_config?.metrics ?? [])
			.filter((m: { enabled: boolean }) => m.enabled)
			.map((m: { metric_id: string }) => m.metric_id);
		console.log(`[#1395 S3 Fall 1] gespeicherte aktive Metriken: ${JSON.stringify(active)}`);
		expect(active, 'gespeicherter Stand enthaelt die zugeschaltete Metrik').toContain(
			'rain_probability'
		);
	} finally {
		console.log(
			`[#1395 S3 Fall 1] DELETE -> HTTP ${await deleteTrip(request, trip.id)} (${trip.id})`
		);
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall 2 — AC-4 + AC-8 (der Zweck der ganzen Uebung) und anschliessend AC-7.
//
// Tour im Browser geoeffnet, dann AN DER OBERFLAECHE VORBEI eine Aenderung an
// derselben Tour (PUT ohne If-Match — das nimmt der Server laut S2 an), danach
// im Browser speichern. Erwartung: 412, die fremde Aenderung bleibt erhalten,
// und am Speicher-Anzeiger steht die deutsche Servermeldung.
//
// Danach (AC-7): der naechste Versuch geht ohne Vorbedingung durch — nach einer
// Ablehnung verwirft die Registry den veralteten Stand, der Nutzer kommt aus
// dem Zustand wieder heraus.
// ─────────────────────────────────────────────────────────────────────────────
test('#1395 S3 Fall 2 (AC-4/AC-8/AC-7): fremde Aenderung -> 412 mit deutscher Meldung, fremder Stand bleibt, danach geht es weiter', async ({
	page,
	request
}) => {
	test.setTimeout(300_000);
	const trip = await createTrip(request, 'konflikt');
	try {
		// Ausgangsstand: Kanaele und amtliche Warnungen ausdruecklich gesetzt.
		const seedRes = await request.put(`/api/trips/${trip.id}`, {
			data: {
				official_warnings: { enabled: true },
				alert_channels: { email: true, telegram: false, sms: false }
			}
		});
		expect(seedRes.ok(), `Seed-PUT HTTP ${seedRes.status()}`).toBeTruthy();

		const puts = recordBrowserTripPuts(page, trip.id);

		// Der Browser laedt die Tour — ab hier fuehrt er ihren Stempel.
		await page.goto(`/trips/${trip.id}?tab=alarme`);
		await expect(page.getByTestId('alarme-tab')).toBeVisible({ timeout: 30_000 });
		const toggle = page
			.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible')
			.first();
		await expect(toggle).toBeVisible({ timeout: 20_000 });

		// An der Oberflaeche vorbei: fremde Aenderung ohne If-Match — angenommen.
		const fremdRes = await request.put(`/api/trips/${trip.id}`, {
			data: { alert_channels: { email: false, telegram: true, sms: true } }
		});
		console.log(`[#1395 S3 Fall 2] fremder PUT (ohne If-Match) -> HTTP ${fremdRes.status()}`);
		expect(fremdRes.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

		// Jetzt im Browser speichern — der Stempel ist veraltet.
		const rejected = page.waitForResponse(
			(r) =>
				r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 60_000 }
		);
		await toggle.click();
		const rejectedRes = await rejected;
		expect(rejectedRes.status(), 'AC-4: der veraltete Schreibvorgang wird abgelehnt').toBe(412);

		// AC-8: deutsche Servermeldung am Speicher-Anzeiger, kein nackter Code.
		const indicator = saveIndicator(page);
		await expect(indicator).toHaveAttribute('data-state', 'error', { timeout: 20_000 });
		const indicatorText = (await indicator.innerText()).replace(/\s+/g, ' ').trim();
		console.log(`[#1395 S3 Fall 2] Speicher-Anzeiger woertlich: „${indicatorText}"`);
		expect(indicatorText, 'AC-8: die deutsche Servermeldung erscheint').toContain(
			CONFLICT_MESSAGE
		);
		expect(indicatorText, 'AC-8: kein nackter Statuscode').not.toContain('412');

		// Die fremde Aenderung ist erhalten, die eigene NICHT durchgekommen.
		const nachKonflikt = await fetchTrip(request, trip.id);
		console.log(
			`[#1395 S3 Fall 2] Stand nach der Ablehnung: alert_channels=${JSON.stringify(
				nachKonflikt.alert_channels
			)} official_warnings=${JSON.stringify(nachKonflikt.official_warnings)}`
		);
		expect(
			nachKonflikt.alert_channels,
			'AC-4: die fremde Aenderung bleibt erhalten (wird nicht ueberschrieben)'
		).toEqual({ email: false, telegram: true, sms: true });
		expect(
			nachKonflikt.official_warnings?.enabled,
			'AC-4: die abgelehnte Browser-Aenderung ist NICHT gespeichert'
		).toBe(true);

		const logKonflikt = await toWriteLog(puts);
		logWrites('Fall 2 (Konflikt)', logKonflikt);
		expect(logKonflikt).toHaveLength(1);
		expect(logKonflikt[0].ifMatch, 'der abgelehnte Vorgang trug einen (veralteten) Stempel').toMatch(
			/^"[0-9a-f]+"$/
		);

		// ── AC-7: der naechste Versuch. Fuer diese Tour ist jetzt kein Stand mehr
		// bekannt (nach 412 verworfen) — er geht ohne Vorbedingung raus und wird
		// angenommen, also exakt wie vor dieser Scheibe.
		const retry = page.waitForResponse(
			(r) =>
				r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 60_000 }
		);
		await toggle.click();
		const retryRes = await retry;
		const logRetry = (await toWriteLog(puts)).slice(1);
		logWrites('Fall 2 (naechster Versuch, AC-7)', logRetry);
		expect(retryRes.status(), 'AC-7: der naechste Versuch wird angenommen').toBe(200);
		expect(logRetry).toHaveLength(1);
		expect(
			logRetry[0].ifMatch,
			'AC-7: ohne bekannten Stand geht KEINE Vorbedingung mit'
		).toBe('(kein If-Match)');
		await expect(saveIndicator(page)).not.toHaveAttribute('data-state', 'error', {
			timeout: 20_000
		});
	} finally {
		console.log(
			`[#1395 S3 Fall 2] DELETE -> HTTP ${await deleteTrip(request, trip.id)} (${trip.id})`
		);
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall 3 — AC-5: kein selbstverschuldeter Konflikt nach dem Pausieren.
//
// `PATCH /state` veraendert die Tourdatei, liefert aber keinen neuen Stempel.
// Ohne die Vorkehrung (discardEtag) baut sich die Anwendung hier selbst einen
// Konflikt — ein Fehler, den es vor S3 nicht gab.
// ─────────────────────────────────────────────────────────────────────────────
test('#1395 S3 Fall 3 (AC-5): nach dem Pausieren gelingt das Speichern im Alarme-Reiter', async ({
	page,
	request
}) => {
	test.setTimeout(300_000);
	const trip = await createTrip(request, 'pause');
	try {
		const puts = recordBrowserTripPuts(page, trip.id);
		await page.goto(`/trips/${trip.id}?tab=alarme`);
		await expect(page.getByTestId('alarme-tab')).toBeVisible({ timeout: 30_000 });

		// Pausieren auf der Detailseite (echter Klickpfad).
		await page.getByRole('button', { name: 'Pausieren' }).click();
		await expect(
			page.getByRole('button', { name: 'Fortsetzen' }),
			'Tour ist pausiert'
		).toBeVisible({ timeout: 30_000 });
		const nachPause = await fetchTrip(request, trip.id);
		console.log(`[#1395 S3 Fall 3] paused_at=${JSON.stringify(nachPause.paused_at)}`);
		expect(nachPause.paused_at, 'Vorbedingung: die Tour ist wirklich pausiert').toBeTruthy();

		// Danach im Editor-Reiter speichern — das MUSS gelingen.
		const saved = page.waitForResponse(
			(r) =>
				r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 60_000 }
		);
		await page
			.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible')
			.first()
			.click();
		const savedRes = await saved;
		const log = await toWriteLog(puts);
		logWrites('Fall 3', log);
		expect(savedRes.status(), 'AC-5: kein selbstgebauter Konflikt nach dem Pausieren').toBe(200);
		await expect(saveIndicator(page)).not.toHaveAttribute('data-state', 'error', {
			timeout: 20_000
		});

		// Die im Browser vorgenommene Aenderung ist wirklich gespeichert. Geprueft
		// wird gegen den TATSAECHLICH gesendeten Rumpf (Richtung des Schalters
		// haengt am Ausgangszustand der Tour und ist hier nebensaechlich).
		const gesendet = puts[0].postDataJSON() as { official_warnings?: { enabled?: boolean } };
		const danach = await fetchTrip(request, trip.id);
		console.log(
			`[#1395 S3 Fall 3] gesendet official_warnings=${JSON.stringify(
				gesendet.official_warnings
			)} — gespeichert=${JSON.stringify(danach.official_warnings)}`
		);
		expect(
			danach.official_warnings?.enabled,
			'die Aenderung ist wirklich gespeichert'
		).toBe(gesendet.official_warnings?.enabled);
	} finally {
		console.log(
			`[#1395 S3 Fall 3] DELETE -> HTTP ${await deleteTrip(request, trip.id)} (${trip.id})`
		);
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall 4 — AC-5, zweite Haelfte: dasselbe nach dem Archivieren.
// ─────────────────────────────────────────────────────────────────────────────
test('#1395 S3 Fall 4 (AC-5): nach dem Archivieren gelingt das Speichern im Alarme-Reiter', async ({
	page,
	request
}) => {
	test.setTimeout(300_000);
	const trip = await createTrip(request, 'archiv');
	try {
		const puts = recordBrowserTripPuts(page, trip.id);
		await page.goto(`/trips/${trip.id}?tab=alarme`);
		await expect(page.getByTestId('alarme-tab')).toBeVisible({ timeout: 30_000 });

		await page.getByRole('button', { name: 'Archivieren' }).click();
		const dialog = page.getByTestId('trip-detail-archive-confirm-dialog');
		await expect(dialog).toBeVisible({ timeout: 20_000 });
		await page.getByTestId('trip-detail-archive-confirm-yes').click();
		await expect(
			page.getByRole('button', { name: 'Reaktivieren' }),
			'Tour ist archiviert'
		).toBeVisible({ timeout: 30_000 });
		const nachArchiv = await fetchTrip(request, trip.id);
		console.log(`[#1395 S3 Fall 4] archived_at=${JSON.stringify(nachArchiv.archived_at)}`);
		expect(nachArchiv.archived_at, 'Vorbedingung: die Tour ist wirklich archiviert').toBeTruthy();

		const saved = page.waitForResponse(
			(r) =>
				r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 60_000 }
		);
		await page
			.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible')
			.first()
			.click();
		const savedRes = await saved;
		logWrites('Fall 4', await toWriteLog(puts));
		expect(savedRes.status(), 'AC-5: kein selbstgebauter Konflikt nach dem Archivieren').toBe(200);

		const gesendet = puts[0].postDataJSON() as { official_warnings?: { enabled?: boolean } };
		const danach = await fetchTrip(request, trip.id);
		console.log(
			`[#1395 S3 Fall 4] gesendet official_warnings=${JSON.stringify(
				gesendet.official_warnings
			)} — gespeichert=${JSON.stringify(danach.official_warnings)}`
		);
		expect(danach.official_warnings?.enabled, 'die Aenderung ist wirklich gespeichert').toBe(
			gesendet.official_warnings?.enabled
		);
	} finally {
		console.log(
			`[#1395 S3 Fall 4] DELETE -> HTTP ${await deleteTrip(request, trip.id)} (${trip.id})`
		);
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall 5 — Regressionsprobe Etappen-Reiter. Absicherung gegen „ein Reiter geht,
// die anderen sind kaputt": alle 19 Trip-Schreibstellen laufen durch denselben
// Trichter.
// ─────────────────────────────────────────────────────────────────────────────
test('#1395 S3 Fall 5 (Regression): Etappen-Reiter speichert weiterhin, mit If-Match und dauerhaft', async ({
	page,
	request
}) => {
	test.setTimeout(300_000);
	const trip = await createTrip(request, 'etappen');
	try {
		const puts = recordBrowserTripPuts(page, trip.id);
		await page.goto(`/trips/${trip.id}?tab=stages`);
		await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 30_000 });

		const timeInput = page
			.locator('[data-testid="stage-start-time-field"]:visible input[type="time"]')
			.first();
		await expect(timeInput).toBeVisible({ timeout: 30_000 });

		const saved = page.waitForResponse(
			(r) =>
				r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${trip.id}`,
			{ timeout: 60_000 }
		);
		await timeInput.fill('09:30');
		await timeInput.blur();
		const savedRes = await saved;
		const log = await toWriteLog(puts);
		logWrites('Fall 5', log);

		expect(savedRes.status(), 'Regression: Speichern im Etappen-Reiter gelingt').toBe(200);
		expect(log[0].ifMatch, 'AC-2 auch hier: If-Match geht mit').toMatch(/^"[0-9a-f]+"$/);
		await expect(saveIndicator(page)).not.toHaveAttribute('data-state', 'error', {
			timeout: 20_000
		});

		await page.reload();
		await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 30_000 });
		const timeAfter = page
			.locator('[data-testid="stage-start-time-field"]:visible input[type="time"]')
			.first();
		await expect(timeAfter, 'UI nach Neuladen').toHaveValue('09:30', { timeout: 20_000 });

		const danach = await fetchTrip(request, trip.id);
		console.log(
			`[#1395 S3 Fall 5] gespeicherte Startzeit: ${JSON.stringify(danach.stages?.[0]?.start_time)}`
		);
		expect(danach.stages?.[0]?.start_time, 'gespeicherter Stand').toBe('09:30');
	} finally {
		console.log(
			`[#1395 S3 Fall 5] DELETE -> HTTP ${await deleteTrip(request, trip.id)} (${trip.id})`
		);
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall 6 — Aufraeum-Kontrolle.
// ─────────────────────────────────────────────────────────────────────────────
test('#1395 S3 Aufraeum-Kontrolle: keine Test-Tour dieses Laufs bleibt liegen', async ({
	request
}) => {
	const res = await request.get('/api/trips');
	expect(res.ok(), `GET /api/trips HTTP ${res.status()}`).toBeTruthy();
	const trips = (await res.json()) as Array<{ id: string; name?: string }>;
	const leftovers = trips
		.filter((t) => (t.name ?? '').startsWith(`${E2E_TEST_PREFIX}1395S3-`))
		.map((t) => `${t.id} (${t.name})`);
	console.log(`[#1395 S3 Aufraeumen] Reste: ${JSON.stringify(leftovers)}`);
	expect(leftovers, 'keine Test-Tour dieses Laufs bleibt liegen').toEqual([]);
});
