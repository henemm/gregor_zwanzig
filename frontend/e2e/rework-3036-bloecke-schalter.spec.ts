// E2E (Staging) — Issue #3036: Übergangsblock aufgelöst, zwei neue Block-Schalter Kurz-Zusammenfassung
// (show_compact_summary) und Großwetterlage (show_stability) in der Karte „Was steht wo“ (nur Trip).
// Spec docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md, AC-1, AC-2 (inkl. zweiter Nutzer), AC-4,
// AC-6 (EN-Nutzer), AC-7 (Reiter Zustellung), AC-10 (keine Oberfläche für die Altfelder, Werte bleiben).
// AC-3 (zugestellte Mail ohne/mit Block) prüft /e2e-verify mit briefing_mail_validator gegen das Stalwart-
// Testpostfach; AC-9 der Elementlisten-Abgleich `--scope zustellung --abnahme` (DE und EN, Prüfkonto).
// Keine gemockten Antworten: echter Go-Server (Merge von report_config), echter Python-Kern (blocks).
//
//   B-1  Trip: beide Schalter sichtbar, Startwert aus dem gespeicherten Stand; Orts-Vergleich: keine (AC-1).
//   B-2  Trip: Schalter umlegen -> PUT nur mit diesem Feld; Neuladen zeigt den Stand; alle übrigen
//        report_config-Felder inkl. der vier Altfelder bleiben; Trip eines zweiten Nutzers unberührt (AC-2, AC-10).
//   B-3  Trip: E-Mail-Format Kompakt sperrt beide Schalter mit „nur ausführlich“ (AC-4).
//   B-4  Englischer Nutzer: Titel der Schalter englisch (AC-6).
//   B-5  Reiter Zustellung Trip/Orte: kein Übergangsblock; Beispiel-Alarm am Ende; bei Orten Pausieren/Aktivieren
//        oben vor den Briefing-Zeiten und bedienbar (AC-7).
//
//   cd frontend && npx playwright test e2e/rework-3036-bloecke-schalter.spec.ts --workers=1 --trace off

import { test, expect, request as pwRequest, type APIRequestContext, type Browser, type Locator, type Page } from '@playwright/test';
import { createTestLocation, seedHub, type HubKind } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, oeffneWetter, stand, type Json } from './s3a2794-teil3.helpers';
import { oeffneZustellung } from './s3b2795-zustellung.helpers';

const NEU = ['show_compact_summary', 'show_stability'] as const;
const ALT = ['show_quick_take_tags', 'show_metrics_summary', 'show_highlights', 'daily_summary_metrics'] as const;
/** Gespeicherte report_config mit Altfeldern; die zwei neuen Felder fehlen (= an). */
const RC: Json = {
	enabled: true, morning_enabled: true, evening_enabled: true, morning_time: '07:00:00', evening_time: '18:00:00', send_email: true,
	email_format: 'full', show_stage_stats: false, show_quick_take_tags: false, show_metrics_summary: false, show_highlights: false,
	daily_summary_metrics: ['thunder'], wind_exposition_min_elevation_m: 1800
};
/** SMS-Schwellen liegen je Metrik in display_config.metrics[].sms_threshold (ohne Oberfläche, AC-10). */
const DC: Json = { metrics: [{ metric_id: 'wind', enabled: true, sms_threshold: 30 }, { metric_id: 'gust', enabled: true, sms_threshold: 50 }] };
const schwellen = (dc: Json) => Object.fromEntries(((dc?.metrics ?? []) as Json[]).map((m) => [m.metric_id, m.sms_threshold ?? null]));

type Abo = { kind: HubKind; id: string; aufraeumen: () => Promise<void> };

async function seedTrip(request: APIRequestContext, rc: Json = RC): Promise<Abo> {
	const hub = await seedHub(request, 'route', { extra: { report_config: rc, display_config: DC } });
	return { kind: 'route', id: hub.id, aufraeumen: hub.aufraeumen };
}
async function seedOrte(request: APIRequestContext): Promise<Abo> {
	const orte = [];
	for (let i = 0; i < 2; i++) orte.push(await createTestLocation(request, { name: `R3036-${Date.now()}-${i}`, lat: 47.1 + i * 0.1, lon: 11.2 + i * 0.1 }));
	const hub = await seedHub(request, 'vergleich', { extra: { location_ids: orte.map((o) => o.id) } });
	return {
		kind: 'vergleich',
		id: hub.id,
		aufraeumen: async () => {
			await hub.aufraeumen();
			for (const o of orte) await request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
	};
}
async function oeffneKarte(page: Page, abo: Abo): Promise<Locator> {
	const reiter = await oeffneWetter(page, abo.kind, abo.id);
	const karte = reiter.getByTestId('was-steht-wo');
	await expect(karte.getByTestId('was-steht-wo-tabelle')).toBeVisible({ timeout: 20_000 });
	return karte;
}
const tripPut = (page: Page, id: string) =>
	page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${id}`, { timeout: 20_000 });
/** report_config ohne die zwei neuen Felder und ohne Server-Zeitstempel (Vergleich „übrige Felder bleiben“). */
const uebrige = (rc: Json) => Object.fromEntries(Object.entries(rc ?? {}).filter(([k]) => !(NEU as readonly string[]).includes(k) && k !== 'updated_at'));

/** Zweiter, frisch registrierter und angemeldeter Nutzer (Muster was-steht-wo-karte.spec.ts). */
async function zweitNutzer(browser: Browser, admin: Page, o: { sprache: 'de' | 'en'; ip: string }): Promise<{ seite: Page; aufraeumen: () => Promise<void> }> {
	const basis = new URL((await admin.goto('/'))!.url()).origin;
	const name = `e2e3036${o.sprache}${Date.now()}`;
	const passwort = wegwerfPasswort();
	const gast = await pwRequest.newContext({ baseURL: basis, storageState: { cookies: [], origins: [] }, extraHTTPHeaders: { 'X-Real-IP': o.ip } });
	const reg = await gast.post('/api/auth/register', { data: { username: name, password: passwort, email: `${name}@example.com`, language: o.sprache } });
	expect([200, 201]).toContain(reg.status());
	const { id: nutzer } = (await reg.json()) as { id: string };
	const tok = (await (await admin.request.post('/api/auth/verify-email/staging-token', { data: { username: nutzer } })).json()) as { token: string };
	expect((await gast.post('/api/auth/verify-email', { data: { user: nutzer, token: tok.token } })).ok()).toBeTruthy();
	await gast.dispose();
	const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', locale: o.sprache === 'de' ? 'de-DE' : 'en-US', viewport: DESKTOP });
	const seite = await ctx.newPage();
	await seite.goto('/login');
	await seite.fill('input[name="username"]', `${name}@example.com`);
	await seite.fill('input[name="password"]', passwort);
	await seite.click('form[action="?/login"] button[type="submit"]');
	await seite.waitForURL((u) => u.pathname === '/', { timeout: 15_000 });
	return {
		seite,
		aufraeumen: async () => {
			await seite.request.post('/api/auth/account/delete', { data: { password: passwort } }).catch(() => {});
			await ctx.close();
		}
	};
}

test.describe('#3036 Karte „Was steht wo“: Kurz-Zusammenfassung und Großwetterlage', () => {
	test('B-1: Trip zeigt beide Schalter mit gespeichertem Startwert, Orts-Vergleich keinen (AC-1)', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const trip = await seedTrip(page.request, { ...RC, show_stability: false });
		const orte = await seedOrte(page.request);
		try {
			const karte = await oeffneKarte(page, trip);
			await expect(karte.getByTestId('was-steht-wo-show_compact_summary')).toHaveAttribute('aria-checked', 'true');
			await expect(karte.getByTestId('was-steht-wo-show_stability')).toHaveAttribute('aria-checked', 'false');
			await expect(karte.getByText('Kurz-Zusammenfassung', { exact: true })).toHaveCount(1);
			await expect(karte.getByText('Großwetterlage', { exact: true })).toHaveCount(1);
			const kOrte = await oeffneKarte(page, orte);
			for (const f of NEU) await expect(kOrte.getByTestId(`was-steht-wo-${f}`)).toHaveCount(0);
		} finally {
			await orte.aufraeumen();
			await trip.aufraeumen();
		}
	});

	test('B-2: Umlegen speichert nur das Feld, Neuladen zeigt den Stand, Altfelder bleiben, zweiter Nutzer unberührt (AC-2, AC-10)', async ({ browser, page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seedTrip(page.request);
		const zweit = await zweitNutzer(browser, page, { sprache: 'de', ip: '10.30.36.1' });
		const fremd = await seedTrip(zweit.seite.request);
		try {
			const vorher = await stand(page.request, 'route', abo.id);
			const fremdVorher = await stand(zweit.seite.request, 'route', fremd.id);
			for (const k of ALT) expect(vorher.report_config[k], `Messaufbau: Altfeld ${k} gespeichert`).toEqual(RC[k]);
			let karte = await oeffneKarte(page, abo);
			// AC-10: für die Altfelder gibt es keine Bedienstelle
			for (const k of ALT) await expect(page.getByTestId(`was-steht-wo-${k}`)).toHaveCount(0);

			for (const f of NEU) {
				const put = tripPut(page, abo.id);
				await karte.getByTestId(`was-steht-wo-${f}`).click();
				const antwort = await put;
				expect(antwort.status()).toBe(200);
				expect(antwort.request().postDataJSON(), `PUT trägt nur ${f}`).toEqual({ report_config: { [f]: false } });
			}
			const nachher = await stand(page.request, 'route', abo.id);
			for (const f of NEU) expect(nachher.report_config[f], f).toBe(false);
			expect(uebrige(nachher.report_config), 'übrige report_config-Felder unverändert').toEqual(uebrige(vorher.report_config));
			expect(schwellen(vorher.display_config), 'Messaufbau: SMS-Schwellen gespeichert').toMatchObject({ wind: 30, gust: 50 });
			expect(schwellen(nachher.display_config), 'SMS-Schwellen unverändert').toEqual(schwellen(vorher.display_config));

			await page.reload();
			karte = await oeffneKarte(page, abo);
			for (const f of NEU) await expect(karte.getByTestId(`was-steht-wo-${f}`), `${f} nach Neuladen aus`).toHaveAttribute('aria-checked', 'false');

			const wieder = tripPut(page, abo.id);
			await karte.getByTestId('was-steht-wo-show_stability').click();
			expect((await wieder).request().postDataJSON()).toEqual({ report_config: { show_stability: true } });
			expect((await stand(page.request, 'route', abo.id)).report_config.show_stability).toBe(true);

			const fremdNachher = await stand(zweit.seite.request, 'route', fremd.id);
			expect(fremdNachher.report_config, 'Trip des zweiten Nutzers').toEqual(fremdVorher.report_config);
			expect((await page.request.get(`/api/briefings/${fremd.id}/placements?kind=route`)).status(), 'fremdes Abo nicht lesbar').toBe(404);
		} finally {
			await fremd.aufraeumen();
			await zweit.aufraeumen();
			await abo.aufraeumen();
		}
	});

	test('B-3: E-Mail-Format Kompakt sperrt beide Schalter mit „nur ausführlich“, Werte bleiben (AC-4)', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seedTrip(page.request, { ...RC, email_format: 'compact', show_compact_summary: false });
		try {
			const karte = await oeffneKarte(page, abo);
			for (const f of NEU) await expect(karte.getByTestId(`was-steht-wo-${f}`), f).toHaveAttribute('aria-disabled', 'true');
			await expect(karte.getByTestId('was-steht-wo-show_compact_summary')).toHaveAttribute('aria-checked', 'false');
			await expect(karte.getByTestId('was-steht-wo-show_stability')).toHaveAttribute('aria-checked', 'true');
			// drei bisherige Block-Schalter + zwei neue
			await expect(karte.getByText('Wirkt nur in der ausführlichen E-Mail.', { exact: false })).toHaveCount(5);
		} finally {
			await abo.aufraeumen();
		}
	});

	test('B-4: englischer Nutzer sieht die Schalter englisch beschriftet (AC-6)', async ({ browser, page }) => {
		const zweit = await zweitNutzer(browser, page, { sprache: 'en', ip: '10.30.36.2' });
		const abo = await seedTrip(zweit.seite.request);
		try {
			const karte = await oeffneKarte(zweit.seite, abo);
			for (const f of NEU) {
				const sw = karte.getByTestId(`was-steht-wo-${f}`);
				await expect(sw).toBeVisible();
				const label = (await sw.getAttribute('aria-label')) ?? '';
				expect(label, `${f}: aria-label`).not.toBe('');
				expect(label, `${f}: nicht deutsch`).not.toMatch(/Kurz-Zusammenfassung|Großwetterlage/);
			}
		} finally {
			await abo.aufraeumen();
			await zweit.aufraeumen();
		}
	});
});

test.describe('#3036 Reiter Zustellung ohne Übergangsblock (AC-7)', () => {
	for (const kind of ['route', 'vergleich'] as const) {
		// #3458: B-5 umgedreht — der Beispiel-Alarm ist entfernt (Test-Alarm #3441), letzter Abschnitt ist Stille Stunden.
		test(`B-5 (${kind}): kein „Vorübergehend hier“, kein Beispiel-Alarm, endet bei Stille Stunden${kind === 'vergleich' ? ', Pausieren oben und bedienbar' : ''}`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const abo = kind === 'route' ? await seedTrip(page.request) : await seedOrte(page.request);
			try {
				const z = await oeffneZustellung(page, abo.kind, abo.id);
				await expect(z.getByTestId('zustellung-uebergang')).toHaveCount(0);
				await expect(z).not.toContainText('Vorübergehend hier');
				await expect(z.locator('[data-abschnitt="stille-stunden"]')).toBeVisible();
				await expect(z.getByTestId('zustellung-beispiel-alarm')).toHaveCount(0);
				await expect(z.getByTestId('alert-preview-card')).toHaveCount(0);
				await expect(z.getByTestId('alert-preview-load-btn')).toHaveCount(0);
				const abschnitte = await z.locator('[data-abschnitt]').evaluateAll((e) => e.map((x) => x.getAttribute('data-abschnitt')));
				expect(abschnitte.at(-1), 'Stille Stunden ist der letzte Abschnitt').toBe('stille-stunden');
				if (kind === 'vergleich') {
					const aktiv = z.getByTestId('zustellung-aktivierung');
					await expect(aktiv.getByTestId('compare-hub-activation-card')).toBeVisible();
					expect(abschnitte.indexOf('aktivierung'), 'Aktivierung vor den Briefing-Zeiten').toBeLessThan(abschnitte.indexOf('briefing-zeiten'));
					const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/compare/presets/${abo.id}`, { timeout: 20_000 });
					await aktiv.getByTestId('compare-hub-activation-cta').click();
					expect((await put).status()).toBe(200);
					expect((await stand(page.request, 'vergleich', abo.id)).schedule, 'Pausieren speichert').toBe('manual');
				} else {
					await expect(z.getByTestId('zustellung-aktivierung')).toHaveCount(0);
				}
			} finally {
				await abo.aufraeumen();
			}
		});
	}
});
