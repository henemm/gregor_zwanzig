// E2E — Issue #2347 S3b (Epic #2345, Etappe P6): Versand-Abschnitt inline
// bearbeiten (Kanal-Schalter, Uhrzeit) und Pausieren-Pfade — EINE Zusicherung für
// BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3b_paritaets_e2e.md § AC-2, AC-3, AC-4 (VI-1..VI-6)
//
// Ersetzt compare-hub-versand-inline.spec.ts (#1256 S7, nur Vergleich, eigener
// Staging-storageState, im CI-Stack nicht lauffähig):
//   AC-35 Telegram-Schalter              → VI-1 (je kind)
//   AC-36 Uhrzeit inline, keine Navigation → VI-2 (je kind)
//   AC-37/17/18 Pausieren                 → VI-3 Kebab (je kind) + VI-4 Karte (vergleich)
//   F002 Uhrzeit + sofort pausieren       → VI-5 Kebab (je kind) + VI-5k Karte (vergleich)
//   F004 Uhrzeit, PUT abwarten, Kebab     → VI-6 (je kind)
//   #2283 Senden nur im Hub-Kopf          → hub-kopf-aufbau.spec.ts KA-5/KA-5b
//   F001 „Bis auf Weiteres"               → hub-versand-speichert-selbst.spec.ts VS-7
//
// Pausieren je kind (Spec „Frage 3"): Trip per PATCH `/api/trips/{id}/state`
// `{paused}`, Vergleich per PUT `{schedule, previous_schedule}` (Kebab →
// toggleActiveFromParent, Karte → handleToggleActive, beide denselben Hub-Schreiber).
//
// ABWEICHUNG VI-6 (vergleich) von der Spec-Formulierung, im RED-Bericht gemeldet:
// die Alt-Zusicherung F004 „der Kebab-PUT trägt die zuvor geänderte Uhrzeit im
// Körper" ist seit #2375 überholt — der Pausier-Rumpf trägt NUR den Status
// (compareHubPersistenz.ts:40-49 buildToggleActivePutPayload; geratscht in
// hub-alarme-speichert-selbst.spec.ts AS-3, Schlüssel exakt
// ['previous_schedule', 'schedule']). Beide Zusicherungen können auf demselben
// Pfad nicht gleichzeitig grün sein. VI-6 bewacht F004 deshalb in der #2375-Form:
// Feld-PUT VOR dem Status-PUT, Status-Rumpf exakt die Status-Schlüssel (ein
// Spread aus veralteter Baseline brächte `morning_time` mit und wird rot), und der
// Server-Stand trägt danach neue Uhrzeit UND pausiert.
//
// ABWEICHUNG VI-1 von der Spec-Formulierung, im RED-Bericht gemeldet: die
// Vorbedingung „telegram_chat_id setzen" geht seit #2141 nicht mehr per Profil-PUT
// (auth.go: nur der Leerstring wird übernommen). VI-1 läuft weiter als Wegwerf-
// Zweitnutzer (testMitZustellbaremZiel, worker-weit geteilt mit KA-5/KA-5b/VA-3),
// ergänzt die clientseitige Profil-Lesung per page.route um eine Test-Chat-ID und
// prüft am Ende, dass das echte Profil unverändert ist. Kein Profil wird verändert.
//
// Wartebedingungen nur expect.poll / toHaveAttribute / waitForResponse.
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh). Aufräumen im finally.

import { test, expect, type Page, type Request } from '@playwright/test';
import {
	createTestLocation,
	HUB_KINDS,
	HUB_SEL,
	hubApiPath,
	openHub,
	seedHub,
	testMitZustellbaremZiel,
	type HubKind
} from './helpers';

type Stand = Record<string, unknown>;
const rc = (s: Stand) => (s.report_config as Stand | undefined) ?? {};

/** kind-Tabelle (Spec „Kind-Kontraste": Kanal-Testids und Feld, Pausier-Übertragungsweg). */
const VI_SEL: Record<
	HubKind,
	{
		telegram: string;
		telegramWert: (s: Stand) => unknown;
		morgen: (s: Stand) => unknown;
		statusMethode: 'PATCH' | 'PUT';
		statusSchluessel: string[];
		statusPausiert: (rumpf: Stand) => boolean;
		istPausiert: (s: Stand) => boolean;
	}
> = {
	route: {
		telegram: 'channel-telegram',
		telegramWert: (s) => rc(s).send_telegram,
		morgen: (s) => rc(s).morning_time,
		statusMethode: 'PATCH',
		statusSchluessel: ['paused'],
		statusPausiert: (r) => r.paused === true,
		istPausiert: (s) => Boolean(s.paused_at)
	},
	vergleich: {
		telegram: 'compare-step5-channel-telegram',
		telegramWert: (s) => s.send_telegram,
		morgen: (s) => s.morning_time,
		statusMethode: 'PUT',
		statusSchluessel: ['previous_schedule', 'schedule'],
		statusPausiert: (r) => r.schedule === 'manual',
		istPausiert: (s) => s.schedule === 'manual'
	}
};

/** Geordnetes Protokoll ALLER Schreibvorgänge auf das Objekt (PUT bzw. PATCH /state). */
function protokolliereSchreiber(page: Page, pfad: string): { alle: Request[]; fertig: Request[] } {
	const alle: Request[] = [];
	const fertig: Request[] = [];
	const trifft = (r: Request) => {
		const p = new URL(r.url()).pathname;
		return (r.method() === 'PUT' && p === pfad) || (r.method() === 'PATCH' && p === `${pfad}/state`);
	};
	page.on('request', (r) => {
		if (trifft(r)) alle.push(r);
	});
	page.on('requestfinished', (r) => {
		if (trifft(r)) fertig.push(r);
	});
	return { alle, fertig };
}

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');
const abschnitt = (page: Page) => page.locator('[data-testid="versand-abschnitt"]:visible');
const morgenUhrzeit = (page: Page) => abschnitt(page).locator('[data-testid="report-morning-time"]:visible');
const karte = (page: Page) => page.locator('[data-testid="compare-hub-activation-card"]:visible');
const cta = (page: Page) => page.locator('[data-testid="compare-hub-activation-cta"]:visible');
const statusPille = (page: Page) => page.locator('[data-status]:visible').first();

async function oeffneVersand(page: Page, kind: HubKind, id: string): Promise<void> {
	await openHub(page, kind, id, { tab: 'wetter-metriken', hash: 'versand' });
	await expect(abschnitt(page)).toBeVisible({ timeout: 10_000 });
	await expect(morgenUhrzeit(page)).toBeVisible({ timeout: 10_000 });
}

async function kebabOeffnen(page: Page): Promise<void> {
	await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
}

async function kebabWaehle(page: Page, punkt: 'Pausieren' | 'Fortsetzen'): Promise<void> {
	await kebabOeffnen(page);
	const eintrag = page.getByRole('menuitem', { name: punkt });
	await expect(eintrag, `Vorbedingung: der Hub bietet „${punkt}" an`).toBeVisible();
	await eintrag.click();
}

/** Öffnet den Kebab, prüft den angebotenen Lebenszyklus-Punkt und schließt ihn wieder. */
async function kebabZeigt(page: Page, punkt: 'Pausieren' | 'Fortsetzen', message: string): Promise<void> {
	await kebabOeffnen(page);
	await expect(page.getByRole('menuitem', { name: punkt }), message).toBeVisible({ timeout: 10_000 });
	await page.keyboard.press('Escape');
	await expect(page.getByRole('menuitem', { name: punkt })).toHaveCount(0);
}

/** Wartet auf die Antwort des Status-Schreibvorgangs des kind (PATCH /state bzw. PUT). */
function statusAntwort(page: Page, kind: HubKind, id: string) {
	const pfad = hubApiPath(kind, id);
	const methode = VI_SEL[kind].statusMethode;
	const ziel = methode === 'PATCH' ? `${pfad}/state` : pfad;
	return page.waitForResponse((r) => r.request().method() === methode && new URL(r.url()).pathname === ziel);
}

// ─── VI-1 (Zweitnutzer mit zustellbarem Ziel) ───────────────────────────────
for (const kind of HUB_KINDS) {
	const vi = VI_SEL[kind];
	// VI-1 (Alt AC-35) — fängt: Kanal-Schalter hart `disabled` bzw. Kanalfeld fehlt im PUT.
	testMitZustellbaremZiel(`VI-1 (${kind}): Telegram-Schalter im Versand-Abschnitt schaltet sofort und persistiert per PUT`, async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		// Seed-Besonderheit (kind-Zweig nur für den Seed, Muster KA-5): die
		// e2e-loc-* aus global.setup.ts gehören dem Admin — der Zweitnutzer
		// bekommt für den Vergleich eigene Orte; der Trip braucht keine Orte.
		const orte =
			kind === 'vergleich'
				? [await createTestLocation(page.request, { name: 'VI1-A' }), await createTestLocation(page.request, { name: 'VI1-B' })]
				: [];
		const hub = await seedHub(page.request, kind, orte.length ? { extra: { location_ids: orte.map((o) => o.id) } } : {});
		// Ausgangswert des echten Profils (page.request läuft an page.route vorbei).
		const ausgang = ((await (await page.request.get('/api/auth/profile')).json())?.telegram_chat_id as string | undefined) ?? '';
		try {
			// Vorbedingung „Telegram verbunden": seit #2141 lässt sich telegram_chat_id
			// NICHT per PUT /api/auth/profile setzen (auth.go, nur der Leerstring kommt
			// durch; Setzen nur über den localhost-gesperrten Connect-Flow). Die Sperre
			// des Schalters ist rein clientseitig (VTBriefingChannels.svelte
			// availableChannels.telegram = !!profile?.telegram_chat_id, Profil per fetch
			// in onMount) — deshalb wird NUR diese Profil-Lesung im Browser um eine
			// Test-Chat-ID ergänzt. Schalter, PUT, Server-Stand und Neuladen bleiben echt;
			// kein Profil (Admin oder Zweitnutzer) wird verändert.
			await page.route('**/api/auth/profile', async (route) => {
				if (route.request().method() !== 'GET') return route.continue();
				const echt = await route.fetch();
				const profil = (await echt.json()) as Record<string, unknown>;
				await route.fulfill({ response: echt, json: { ...profil, telegram_chat_id: 'e2e-s3b-test-chat' } });
			});

			await oeffneVersand(page, kind, hub.id);
			const schalter = abschnitt(page).locator(`[data-testid="${vi.telegram}"] input[type="checkbox"]`);
			await expect(schalter).toBeVisible({ timeout: 10_000 });
			// Kernaussage AC-35: der Schalter ist NICHT hart auf disabled verdrahtet.
			await expect(schalter).toBeEnabled({ timeout: 10_000 });
			await expect(schalter).not.toBeChecked();

			const put = page.waitForResponse(
				(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === hubApiPath(kind, hub.id)
			);
			await schalter.click();
			await expect(schalter).toBeChecked({ timeout: 5_000 });
			const antwort = await put;
			expect(antwort.ok(), `PUT nach Kanal-Schalter HTTP ${antwort.status()}`).toBeTruthy();
			expect(vi.telegramWert(antwort.request().postDataJSON() as Stand), 'der PUT trägt den gesetzten Kanal').toBe(true);
			await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			expect(vi.telegramWert(await stand(page, kind, hub.id)), 'Server-Stand trägt den Kanal').toBe(true);

			await oeffneVersand(page, kind, hub.id);
			await expect(abschnitt(page).locator(`[data-testid="${vi.telegram}"] input[type="checkbox"]`)).toBeChecked({
				timeout: 10_000
			});
		} finally {
			await page.unroute('**/api/auth/profile');
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
		// Nach dem finally (verdeckt keinen Primärfehler): das echte Profil des
		// worker-weit geteilten Zweitnutzers ist unverändert (KA-5/KA-5b/VA-3).
		const danach = (await (await page.request.get('/api/auth/profile')).json())?.telegram_chat_id ?? '';
		expect(danach, 'das Zweitnutzer-Profil darf durch den Fall nicht verändert sein').toBe(ausgang);
	});
}

// ─── VI-2..VI-6 (Admin-Sitzung) ─────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const vi = VI_SEL[kind];

	test.describe(`Hub · Versand inline bearbeiten (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// VI-2 (Alt AC-36) — fängt: der Uhrzeit-Handler navigiert nach /edit.
		test(`VI-2 (${kind}): Briefing-Uhrzeit ändert sich inline ohne Navigation, überlebt das Neuladen`, async ({ page }) => {
			const hub = await seedHub(page.request, kind);
			try {
				await oeffneVersand(page, kind, hub.id);
				const vorher = page.url();
				expect(vorher).not.toMatch(/\/edit/);

				const put = page.waitForResponse(
					(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === hubApiPath(kind, hub.id)
				);
				await morgenUhrzeit(page).selectOption('09:00');
				const antwort = await put;
				expect(antwort.ok(), `PUT nach Uhrzeit-Änderung HTTP ${antwort.status()}`).toBeTruthy();
				expect(String(vi.morgen(antwort.request().postDataJSON() as Stand)).slice(0, 5)).toBe('09:00');

				// Kernaussage AC-36: keine Navigation nach /edit.
				expect(page.url()).toBe(vorher);
				expect(page.url()).not.toMatch(/\/edit/);

				await oeffneVersand(page, kind, hub.id);
				await expect(morgenUhrzeit(page)).toHaveValue('09:00', { timeout: 10_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// VI-3 (gemeinsamer Teil von Alt AC-37/17/18) — fängt: Menüpunkt wechselt nach
		// dem Pausieren nicht bzw. Redirect.
		test(`VI-3 (${kind}): Kebab „Pausieren" → Menüpunkt „Fortsetzen", keine Navigation, Server pausiert; „Fortsetzen" zurück`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind);
			try {
				await oeffneVersand(page, kind, hub.id);
				// Status-Pille mit `data-status` nur im Vergleichs-Kopf
				// (CompareStatusPill); der Trip-Kopf hat das Attribut nicht und prüft
				// Menüpunkt und Server-Stand (Spec „Kind-Kontraste", Zeile Pausieren).
				if (kind === 'vergleich') await expect(statusPille(page)).toHaveAttribute('data-status', 'active', { timeout: 10_000 });
				const vorher = page.url();

				const pausiert = statusAntwort(page, kind, hub.id);
				await kebabWaehle(page, 'Pausieren');
				expect((await pausiert).ok(), 'Status-Schreibvorgang Pausieren').toBeTruthy();
				expect(page.url(), 'kein Redirect').toBe(vorher);
				expect(page.url()).not.toMatch(/\/edit/);
				await expect.poll(async () => vi.istPausiert(await stand(page, kind, hub.id)), { timeout: 10_000 }).toBe(true);
				await kebabZeigt(page, 'Fortsetzen', 'nach dem Pausieren bietet der Kebab „Fortsetzen" an');
				if (kind === 'vergleich') await expect(statusPille(page)).not.toHaveAttribute('data-status', 'active', { timeout: 10_000 });

				const fortgesetzt = statusAntwort(page, kind, hub.id);
				await kebabWaehle(page, 'Fortsetzen');
				expect((await fortgesetzt).ok(), 'Status-Schreibvorgang Fortsetzen').toBeTruthy();
				expect(page.url()).toBe(vorher);
				await expect.poll(async () => vi.istPausiert(await stand(page, kind, hub.id)), { timeout: 10_000 }).toBe(false);
				await kebabZeigt(page, 'Pausieren', 'nach dem Fortsetzen bietet der Kebab wieder „Pausieren" an');
			} finally {
				await hub.aufraeumen();
			}
		});

		// VI-4 / VI-5k — nur vergleich: die Aktivierungs-Karte ist Slot von VersandTab
		// nur im Vergleich-Hub (CompareTabs.svelte hubActivationCard, Einstieg
		// handleToggleActive); der Trip-Hub hat keine Karte (Spec „Kind-Kontraste",
		// Zeile Pausieren). Der Trip prüft dieselben Zusicherungen über den Kebab (VI-3/VI-5).
		if (kind === 'vergleich') {
			// VI-4 (Alt AC-37/17/18, Karten-Anteil) — fängt: Karten-CTA ohne PUT.
			test(`VI-4 (${kind}): Aktivierungs-Karte zeigt „Aktiv"/„bis du pausierst", CTA pausiert ohne Redirect und aktiviert wieder`, async ({
				page
			}) => {
				const hub = await seedHub(page.request, kind);
				try {
					await oeffneVersand(page, kind, hub.id);
					await expect(karte(page)).toBeVisible({ timeout: 10_000 });
					// AC-17: Status „Aktiv" + CTA „Pausieren"; AC-18: Copy, kein Enddatum-Feld in der Karte.
					await expect(karte(page)).toContainText('Aktiv');
					await expect(cta(page)).toHaveText('Pausieren');
					await expect(karte(page)).toContainText('bis du pausierst');
					await expect(karte(page).locator('input[type="date"], [data-testid^="compare-versand-enddate"]')).toHaveCount(0);
					await expect(statusPille(page)).toHaveAttribute('data-status', 'active', { timeout: 10_000 });

					const vorher = page.url();
					const put = statusAntwort(page, kind, hub.id);
					await cta(page).click();
					const antwort = await put;
					expect(antwort.ok(), `PUT nach Pausieren-Klick HTTP ${antwort.status()}`).toBeTruthy();
					expect(page.url(), 'AC-37: kein Redirect').toBe(vorher);
					expect(page.url()).not.toMatch(/\/edit/);
					await expect(cta(page)).toHaveText('Aktivieren', { timeout: 5_000 });
					await expect(statusPille(page), 'SF-2: die Kopf-Pille zieht mit').not.toHaveAttribute('data-status', 'active');
					expect(vi.istPausiert(await stand(page, kind, hub.id))).toBe(true);

					const zurueck = statusAntwort(page, kind, hub.id);
					await cta(page).click();
					expect((await zurueck).ok()).toBeTruthy();
					await expect(cta(page)).toHaveText('Pausieren', { timeout: 5_000 });
					expect(vi.istPausiert(await stand(page, kind, hub.id))).toBe(false);
				} finally {
					await hub.aufraeumen();
				}
			});

			// VI-5k (Alt F002, über die Karte) — Stresstest der gemeinsamen
			// Schreib-Warteschlange (hubPutQueue) am Einstieg handleToggleActive.
			test(`VI-5k (${kind}): Uhrzeit ändern + sofort Karten-„Pausieren" ohne Wartepunkt → nach Neuladen Uhrzeit UND pausiert`, async ({
				page
			}) => {
				const hub = await seedHub(page.request, kind);
				try {
					const { fertig } = protokolliereSchreiber(page, hubApiPath(kind, hub.id));
					await oeffneVersand(page, kind, hub.id);
					await expect(cta(page)).toHaveText('Pausieren');

					await morgenUhrzeit(page).selectOption('10:00');
					await cta(page).click();

					await expect(cta(page)).toHaveText('Aktivieren', { timeout: 10_000 });
					await expect.poll(() => fertig.length, { timeout: 10_000 }).toBe(2);
					await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

					await oeffneVersand(page, kind, hub.id);
					await expect(morgenUhrzeit(page)).toHaveValue('10:00', { timeout: 10_000 });
					await expect(cta(page)).toHaveText('Aktivieren', { timeout: 10_000 });
					const s = await stand(page, kind, hub.id);
					expect(String(vi.morgen(s))).toMatch(/^10:00/);
					expect(vi.istPausiert(s)).toBe(true);
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// VI-5 (Alt F002, Einstieg Kebab) — fängt: der Flush vor dem Statuswechsel fehlt.
		test(`VI-5 (${kind}): Uhrzeit ändern + sofort Kebab-„Pausieren" ohne Wartepunkt → nach Neuladen Uhrzeit UND pausiert`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind);
			try {
				const { fertig } = protokolliereSchreiber(page, hubApiPath(kind, hub.id));
				await oeffneVersand(page, kind, hub.id);

				await morgenUhrzeit(page).selectOption('10:00');
				await kebabWaehle(page, 'Pausieren');

				await expect.poll(() => fertig.length, { timeout: 10_000 }).toBe(2);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				await oeffneVersand(page, kind, hub.id);
				await expect(morgenUhrzeit(page), 'die Uhrzeit überlebt Pausieren und Neuladen').toHaveValue('10:00', { timeout: 10_000 });
				await kebabZeigt(page, 'Fortsetzen', 'nach dem Neuladen ist der Hub pausiert');
				const s = await stand(page, kind, hub.id);
				expect(String(vi.morgen(s))).toMatch(/^10:00/);
				expect(vi.istPausiert(s)).toBe(true);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VI-6 (Alt F004, Lost-Update) — fängt: der Pausier-Schreiber sendet aus einer
		// veralteten Baseline (überschreibt die zuvor gespeicherte Uhrzeit) bzw.
		// vertauschte Reihenfolge. Form am Ist-Stand #2375 siehe Kopfkommentar.
		test(`VI-6 (${kind}): F004 — Uhrzeit ändern, PUT abwarten, Kebab „Pausieren" → Status-Rumpf trägt nur den Status, Server: Uhrzeit UND pausiert`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const { alle, fertig } = protokolliereSchreiber(page, pfad);
				await oeffneVersand(page, kind, hub.id);

				// Feld-Änderung, PUT abwarten (eigener Commit-Pfad).
				const feldPut = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad);
				await morgenUhrzeit(page).selectOption('11:00');
				const feldAntwort = await feldPut;
				expect(feldAntwort.ok(), `PUT nach Uhrzeit-Änderung HTTP ${feldAntwort.status()}`).toBeTruthy();
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const status = statusAntwort(page, kind, hub.id);
				await kebabWaehle(page, 'Pausieren');
				const statusRes = await status;
				expect(statusRes.ok(), `Status-Schreibvorgang HTTP ${statusRes.status()}`).toBeTruthy();
				await expect.poll(() => fertig.length, { timeout: 10_000 }).toBe(2);

				expect(alle[0].method(), 'erster Schreibvorgang ist der Feld-PUT').toBe('PUT');
				expect(String(vi.morgen(alle[0].postDataJSON() as Stand))).toMatch(/^11:00/);
				expect(alle[1].method(), `Status-Schreibweg des kind: ${vi.statusMethode}`).toBe(vi.statusMethode);
				const statusRumpf = statusRes.request().postDataJSON() as Stand;
				expect(vi.statusPausiert(statusRumpf), 'der Status-Schreibvorgang pausiert').toBe(true);
				// #2375: der Status-Rumpf trägt NUR den Status — ein Voll-Spread aus einer
				// veralteten Baseline (der F004-Datenverlust) brächte `morning_time` mit.
				expect(Object.keys(statusRumpf).sort(), `Status-Rumpf trägt nur { ${vi.statusSchluessel.join(', ')} }`).toEqual(
					vi.statusSchluessel
				);
				await test.info().attach('vi6-status-rumpf', { body: JSON.stringify(statusRumpf), contentType: 'application/json' });

				await oeffneVersand(page, kind, hub.id);
				await expect(morgenUhrzeit(page)).toHaveValue('11:00', { timeout: 10_000 });
				await kebabZeigt(page, 'Fortsetzen', 'nach dem Neuladen ist der Hub pausiert');
				const s = await stand(page, kind, hub.id);
				expect(String(vi.morgen(s)), 'das Pausieren hat die gespeicherte Uhrzeit überschrieben').toMatch(/^11:00/);
				expect(vi.istPausiert(s)).toBe(true);

				// Aufräumen symmetrisch zum Alt-Fall: Kebab „Fortsetzen".
				const fortgesetzt = statusAntwort(page, kind, hub.id);
				await kebabWaehle(page, 'Fortsetzen');
				expect((await fortgesetzt).ok()).toBeTruthy();
				await expect.poll(async () => vi.istPausiert(await stand(page, kind, hub.id)), { timeout: 10_000 }).toBe(false);
				await expect(page).toHaveURL(sel.hubUrl(hub.id));
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
