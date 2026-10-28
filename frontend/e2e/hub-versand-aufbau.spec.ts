// E2E — Issue #2347 S3b (Epic #2345, Etappe P6): Aufbau des Versand-Abschnitts
// (Reiter „Wetter-Metriken", `#versand`) — EINE Zusicherung für BEIDE Hubs (Trip
// und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3b_paritaets_e2e.md § AC-6 (VA-1..VA-4)
//
// Ersetzt aus versand-tab-vergleich.spec.ts (#1232 S2b, nur Vergleich, Regel-2-Altlast):
//   AC-1  Kanäle → Zeitplan → Laufzeit, keine Alert-Zustellung → VA-1 (je kind)
//   AC-4  Cooldown + Level-Tabelle nur im Alarme-Reiter       → VA-2 (je kind; der
//         feste 300-ms-Pause der Altdatei ist durch eine Wartebedingung auf die Tabelle ersetzt)
//   AC-7  alle Kanäle aus ⇒ Leerzustand                       → VA-3 (je kind; bestätigte
//         Adresse über testMitZustellbaremZiel, ohne `{force: true}`, ohne Admin-Profil-Änderung)
//   AC-10 mobil ohne horizontales Scrollen                    → VA-4 (je kind)
// Übrige Fälle der Altdatei: AC-2 → hub-versand-autosave-chip AC-1, AC-3/AC-3b →
// hub-versand-speichert-selbst VS-7/VS-8, AC-6 → compare-editor-slice3,
// Staging-F001 → hub-wetter-metriken-speichert-selbst MS-2.
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh). Aufräumen im finally.

import { test, expect, type Page } from '@playwright/test';
import {
	createTestLocation,
	HUB_KINDS,
	HUB_SEL,
	openHub,
	seedHub,
	testMitZustellbaremZiel,
	type HubKind
} from './helpers';

/** kind-Tabelle (Spec „Kind-Kontraste": Kanal-Testids, Laufzeit-Block, Seed mit aktiver Metrik). */
const VA_SEL: Record<
	HubKind,
	{
		email: string;
		laufzeit: string;
		/** alarmfähige Metrik, damit die Level-Tabelle im Alarme-Reiter rendert. */
		metrikSeed: Record<string, unknown>;
	}
> = {
	route: {
		email: 'channel-email',
		laufzeit: 'briefings-laufzeit',
		// Böen → wind_gust ist alarmfähig (Muster hub-alarme-wertprops.spec.ts AW, Trip-Seed).
		metrikSeed: { display_config: { metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }] } }
	},
	vergleich: {
		email: 'compare-step5-channel-email',
		laufzeit: 'briefings-laufzeit-vergleich',
		metrikSeed: { display_config: { active_metrics: ['wind_max_kmh'] } }
	}
};

const abschnitt = (page: Page) => page.locator('[data-testid="versand-abschnitt"]:visible');

async function oeffneVersand(page: Page, kind: HubKind, id: string): Promise<void> {
	await openHub(page, kind, id, { tab: 'wetter-metriken', hash: 'versand' });
	await expect(abschnitt(page)).toBeVisible({ timeout: 10_000 });
}

// ─── VA-1, VA-2, VA-4 (Admin-Sitzung) ───────────────────────────────────────
for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const va = VA_SEL[kind];

	test.describe(`Hub · Versand-Abschnitt Aufbau (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// VA-1 (Alt AC-1) — fängt: Alert-Zustellung im Versand-Abschnitt bzw.
		// fehlender/vertauschter Block.
		test(`VA-1 (${kind}): Versand-Abschnitt zeigt Kanäle → Zeitplan → Laufzeit, keine Alert-Zustellung`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: va.metrikSeed });
			try {
				await oeffneVersand(page, kind, hub.id);
				const kanal = abschnitt(page).locator(`[data-testid="${va.email}"]:visible`);
				const zeitplan = abschnitt(page).locator('[data-testid="morning-master-switch"]:visible');
				const laufzeit = abschnitt(page).locator(`[data-testid="${va.laufzeit}"]:visible`);
				await expect(kanal).toBeVisible({ timeout: 10_000 });
				await expect(zeitplan).toBeVisible();
				await expect(laufzeit).toBeVisible();
				await expect(page.locator('[data-testid="alert-cooldown-card"]:visible')).toHaveCount(0);
				await expect(abschnitt(page).locator('[data-testid="alert-cooldown-card"]')).toHaveCount(0);

				// Reihenfolge im Dokument: Kanäle vor Zeitplan vor Laufzeit.
				const vorher = async (a: typeof kanal, b: typeof kanal) =>
					a.evaluate(
						(x, y) => Boolean(x.compareDocumentPosition(y as Node) & Node.DOCUMENT_POSITION_FOLLOWING),
						await b.elementHandle()
					);
				expect(await vorher(kanal, zeitplan), 'Kanäle stehen vor dem Zeitplan').toBe(true);
				expect(await vorher(zeitplan, laufzeit), 'der Zeitplan steht vor der Laufzeit').toBe(true);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VA-2 (Alt AC-4) — fängt: Cooldown-Karte/Level-Tabelle im Versand-Abschnitt
		// bzw. fehlend im Alarme-Reiter. Derselbe Umweg über Wetter-Metriken wie im
		// Alt-Fall (activeMetricKeys hydratisiert beim Wetter-Metriken-Besuch); statt
		// der festen 300-ms-Pause wartet der Fall auf den sichtbaren Versand-Abschnitt
		// und danach per expect.poll auf die hydratisierte Level-Tabelle.
		test(`VA-2 (${kind}): Alarme-Reiter enthält Cooldown-Karte + Level-Tabelle, der Versand-Abschnitt keins von beidem`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: va.metrikSeed });
			try {
				await openHub(page, kind, hub.id);
				await page.locator(`[data-testid="${sel.reiter}-wetter-metriken"]:visible`).first().click();
				await expect(abschnitt(page)).toBeVisible({ timeout: 10_000 });
				await page.locator(`[data-testid="${sel.reiter}-alarme"]:visible`).first().click();
				await expect(page.locator('[data-testid="alarme-tab"]:visible').first()).toBeVisible({ timeout: 10_000 });

				const tabelle = page.locator('[data-testid="alert-metric-level-table"]:visible');
				await expect
					.poll(() => tabelle.count(), { timeout: 10_000, message: 'die Level-Tabelle (aktive Metrik) muss im Alarme-Reiter stehen' })
					.toBeGreaterThanOrEqual(1);
				await expect(page.locator('[data-testid="alert-cooldown-card"]:visible').first()).toBeVisible();

				await page.locator(`[data-testid="${sel.reiter}-wetter-metriken"]:visible`).first().click();
				await expect(abschnitt(page)).toBeVisible({ timeout: 10_000 });
				await expect(abschnitt(page).locator('[data-testid="alert-cooldown-card"]')).toHaveCount(0);
				await expect(abschnitt(page).locator('[data-testid="alert-metric-level-table"]')).toHaveCount(0);
				await expect(page.locator('[data-testid="alert-cooldown-card"]:visible')).toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VA-4 (Alt AC-10) — fängt: feste Mindestbreite im Versand-Abschnitt.
		test(`VA-4 (${kind}): mobiler Viewport 390×844 — Versand-Abschnitt ohne horizontales Scrollen`, async ({ page }) => {
			const hub = await seedHub(page.request, kind);
			try {
				await page.setViewportSize({ width: 390, height: 844 });
				await oeffneVersand(page, kind, hub.id);
				await expect(abschnitt(page).locator(`[data-testid="${va.email}"]:visible`)).toBeVisible({ timeout: 10_000 });
				const ohneQuerScroll = await page.evaluate(
					() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1
				);
				expect(ohneQuerScroll, 'horizontales Scrollen auf Mobile darf nicht auftreten').toBe(true);
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}

// ─── VA-3 (Zweitnutzer mit bestätigter Adresse) ─────────────────────────────
// Vorbedingung „E-Mail-Kanal schaltbar": die E-Mail-Checkbox ist nur mit
// bestätigter Konto-Adresse bedienbar (VTBriefingChannels.svelte, #1510). Der
// Env-Admin des CI-Stacks hat keine ⇒ bestätigter Zweitnutzer
// (testMitZustellbaremZiel); das Admin-Profil bleibt unberührt, kein `{force: true}`.
for (const kind of HUB_KINDS) {
	const va = VA_SEL[kind];
	// VA-3 (Alt AC-7) — fängt: Leerzustand entfernt bzw. Zeitplan-Karten trotz 0 Kanälen.
	testMitZustellbaremZiel(`VA-3 (${kind}): alle Kanäle aus → Leerzustand „Kein Kanal aktiv" statt Zeitplan-Karten`, async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		// Seed-Besonderheit (kind-Zweig nur für den Seed, Muster KA-5): die
		// e2e-loc-* aus global.setup.ts gehören dem Admin — der Zweitnutzer bekommt
		// für den Vergleich eigene Orte; der Trip braucht keine Orte.
		const orte =
			kind === 'vergleich'
				? [await createTestLocation(page.request, { name: 'VA3-A' }), await createTestLocation(page.request, { name: 'VA3-B' })]
				: [];
		const hub = await seedHub(page.request, kind, orte.length ? { extra: { location_ids: orte.map((o) => o.id) } } : {});
		try {
			await oeffneVersand(page, kind, hub.id);
			const email = abschnitt(page).locator(`[data-testid="${va.email}"] input[type="checkbox"]`);
			// Vorbedingung ausdrücklich (kein `if (isChecked)` — sonst wäre der Fall blind):
			// E-Mail an und bedienbar, Telegram/SMS ohne Kontaktfeld aus, kein Leerzustand.
			await expect(email).toBeVisible({ timeout: 10_000 });
			await expect(email).toBeEnabled({ timeout: 10_000 });
			await expect(email).toBeChecked();
			await expect(abschnitt(page).locator('[data-testid="briefings-channel-empty"]')).toHaveCount(0);
			await expect(abschnitt(page).locator('[data-testid="morning-master-switch"]:visible')).toBeVisible();
			const andere = abschnitt(page).locator(
				['channel-telegram', 'channel-sms', 'channel-premium-sms']
					.flatMap((k) => [`[data-testid="${k}"] input`, `[data-testid="compare-step5-${k}"] input`])
					.join(', ')
			);
			for (const cb of await andere.all()) {
				await expect(cb, 'Vorbedingung: außer E-Mail ist kein Kanal aktiv').not.toBeChecked();
			}

			await email.uncheck();
			await expect(email).not.toBeChecked();

			await expect(abschnitt(page).locator('[data-testid="briefings-channel-empty"]:visible')).toBeVisible({ timeout: 10_000 });
			await expect(abschnitt(page).locator('[data-testid="briefings-channel-empty"]')).toContainText('Kein Kanal aktiv');
			await expect(abschnitt(page).locator('[data-testid="morning-master-switch"]'), 'statt der Zeitplan-Karten').toHaveCount(0);
		} finally {
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
	});
}
