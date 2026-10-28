// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): die Alarme-Fläche (geteilter
// AlarmeTab) arbeitet auf Wertprops + Rückrufen — Verhaltensgleichheit am Hub für
// BEIDE kinds (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-2 (AW-1..AW-5)
//
// Ersetzt compare-alarme-wertprops.spec.ts (#2276 S6c, nur Vergleich):
//   AC-2 Amtliche Warnungen + Radar     → AW-1 (je kind, Amtliche Warnungen)
//                                        + AW-2 (nur vergleich, Radar + Amtliche, 1:1 Altfall)
//   AC-2 Kanal / Schwelle / Kurzstil    → AW-3 (je kind; Kurzstil nur vergleich)
//   AC-2 Empfindlichkeit/Cooldown/Stille→ AW-4 (je kind)
//   AC-2 übrige Einstellungen unberührt → AW-5 (je kind)
//
// Compare-eigen (Spec AC-2/AC-8): Radar-Alarm `radar_alert_enabled` und
// Telegram-Kurzstil `display_config.telegram_style` existieren nur im
// Vergleichs-Preset (alarmeTabSections.ts:11 — Abschnitt 'radar' nur bei
// context 'vergleich'; AlarmeTab.svelte:530 — Kurzstil nur bei 'vergleich').
// Alles andere läuft für beide kinds mit denselben Zusicherungen.
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts. Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, hubApiPath, openHub, seedHub, type HubKind } from './helpers';
// #1373 / ADR-0037: `display_config.active_metrics` wird in ZWEI Formen
// gespeichert (Kurzform und Paar {metric_id, aggregation}). Der Vergleich der
// Nachbar-Einstellungen im Ortsvergleich läuft deshalb über die
// Lesenormalisierung DES PRODUKTS, nicht über eigene Zeichenketten-Logik.
import {
	normalizeStoredActiveMetrics,
	toCompareSelectionEntries,
	type CompareSelectionEntry
} from '../src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts';

type Stand = Record<string, unknown>;

const dc = (body: Stand) => (body.display_config as Stand | undefined) ?? {};

/** kind-Tabelle: Seed, Auslöser für AW-5, Bezug der Stillen Stunden, Nachbarfelder. */
const AW_SEL: Record<
	HubKind,
	{
		seed: Record<string, unknown>;
		/** Bezugsgröße der Stillen Stunden (Prop `zonenBezug`, AlertQuietHoursCard.svelte:6-12). */
		zonenBezug: string;
		/** Auslöser für AW-5 (Vergleich wie Alt-Spec: Radar; Trip: Amtliche-Warnungen-Auslöser). */
		ausloeser: (page: Page) => Locator;
		ausloeserWert: (s: Stand) => unknown;
		ausloeserNeu: boolean;
		/** Nachbar-Einstellungen, die eine Alarm-Geste NICHT berühren darf (AW-5). */
		nachbarn: (page: Page, s: Stand) => Promise<Record<string, unknown>>;
	}
> = {
	route: {
		seed: {
			official_warnings: { enabled: true },
			// Telegram startet aus — reconstructTripAlertChannels liest alert_channels zuerst.
			alert_channels: { email: true, telegram: false, sms: false, premium_sms: false },
			// nicht-leere Metrik-Auswahl, damit AW-5 etwas bewacht. Bewusst eine
			// ALARMFÄHIGE Metrik (Böen → wind_gust, ALERTABLE_METRICS): die
			// Empfindlichkeits-Tabelle (AW-4) zeigt nur alarmfähige Größen der Auswahl
			// (tripAlertMetricsFromCatalog.ts) — eine reine Schneehöhe ließe sie leer.
			display_config: { metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }] }
		},
		zonenBezug: 'der Trip',
		ausloeser: (page) =>
			page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"] input[type="checkbox"]').first(),
		ausloeserWert: (s) => (s.official_warnings as { enabled?: boolean } | undefined)?.enabled,
		ausloeserNeu: false,
		// Trip-Gegenstück zu Empfängern/Orten/Metrik-Auswahl: Etappen, Versand-Konfiguration, Metrik-Auswahl.
		nachbarn: async (_page, s) => ({ stages: s.stages, report_config: s.report_config, auswahl: dc(s).metrics ?? [] })
	},
	vergleich: {
		seed: {
			radar_alert_enabled: false,
			send_telegram: false,
			display_config: { active_metrics: ['wind_max_kmh'], telegram_style: 'rich' }
		},
		zonenBezug: 'des ersten Orts',
		ausloeser: (page) => page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first(),
		ausloeserWert: (s) => s.radar_alert_enabled,
		ausloeserNeu: true,
		// Empfänger, Orte und Metrik-Auswahl in Vergleichs-Form (Lesenormalisierung #1373).
		nachbarn: async (page, s) => ({
			empfaenger: s.empfaenger,
			location_ids: s.location_ids,
			auswahl: normalizeStoredActiveMetrics(dc(s).active_metrics, await metrikKatalog(page)) ?? []
		})
	}
};

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

/** Der Metrik-Katalog des Servers für den Ortsvergleich — Schlüsselbund der Lesenormalisierung. */
async function metrikKatalog(page: Page): Promise<CompareSelectionEntry[]> {
	const res = await page.request.get('/api/compare/metrics');
	expect(res.ok(), 'GET /api/compare/metrics HTTP ' + res.status()).toBeTruthy();
	const katalog = toCompareSelectionEntries(await res.json());
	expect(
		katalog.length,
		'Vorbedingung: der Metrik-Katalog ist leer — ohne ihn kann die Paar-Form nicht ' +
			'aufgelöst werden und der Vergleich unten würde Formen statt Auswahl prüfen.'
	).toBeGreaterThan(0);
	return katalog;
}

/** Zählt die PUTs auf genau dieses Objekt. */
function zaehlePuts(page: Page, pfad: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) puts.push(r);
	});
	return puts;
}

/** Stabilitätsfenster statt festem Schlaf: `lies()` muss `ms` lang `soll` liefern. */
async function bleibtBei(lies: () => number, soll: number, ms: number, message: string): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				const n = lies();
				if (n !== soll) {
					seit = 0;
					return n;
				}
				seit ||= Date.now();
				return Date.now() - seit >= ms ? 'stabil' : n;
			},
			{ message, timeout: ms + 8_000, intervals: [200] }
		)
		.toBe('stabil');
}

async function oeffneAlarme(page: Page, kind: HubKind, id: string): Promise<Locator> {
	await openHub(page, kind, id, { tab: 'alarme' });
	const reiter = page.locator('[data-testid="alarme-tab"]').first();
	await expect(reiter, 'Der Alarme-Reiter muss erscheinen').toBeVisible({ timeout: 10_000 });
	return reiter;
}

async function warteAufGespeichert(page: Page): Promise<void> {
	await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
		timeout: 15_000
	});
}

const amtlichSchalter = (page: Page) =>
	page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"] input[type="checkbox"]').first();
const radarSchalter = (page: Page) =>
	page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first();
const telegramSchalter = (page: Page) =>
	page.locator('[data-testid="alert-channel-toggle-telegram"]').first().getByRole('switch');
const amtlichGespeichert = (s: Stand) => (s.official_warnings as { enabled?: boolean } | undefined)?.enabled;

for (const kind of HUB_KINDS) {
	const aw = AW_SEL[kind];

	test.describe(`Hub · Alarme auf Wertprops (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// AW-1 — Alt AC-2 „Amtliche Warnungen": genau EIN PUT, gespeichert, überlebt Neuladen.
		test(`AW-1 (${kind}): Amtliche Warnungen wirken, genau ein PUT, Stand überlebt das Neuladen`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: aw.seed });
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				await oeffneAlarme(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

				const warVorher = await amtlichSchalter(page).isChecked();
				await amtlichSchalter(page).setChecked(!warVorher);
				await warteAufGespeichert(page);
				await expect
					.poll(async () => amtlichGespeichert(await stand(page, kind, hub.id)), {
						timeout: 15_000,
						message: 'AW-1 FAIL: „Amtliche Warnungen" wurde nicht gespeichert.'
					})
					.toBe(!warVorher);
				await bleibtBei(() => puts.length, 1, 1_200, 'AW-1 FAIL: genau EIN PUT je Alarm-Änderung');

				await oeffneAlarme(page, kind, hub.id);
				await expect(
					amtlichSchalter(page),
					'AW-1 FAIL: „Amtliche Warnungen" steht nach dem Neuladen wieder auf dem alten Wert.'
				).toBeChecked({ checked: !warVorher });
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-2 — nur vergleich (compare-eigen): der Radar-Alarm existiert nur im
		// Vergleichs-Preset (alarmeTabSections.ts:11, compare_preset.go:60) — der Trip
		// hat kein Gegenstück im Produkt. 1:1 der Alt-Fall „Amtliche Warnungen + Radar".
		if (kind === 'vergleich') {
			test(`AW-2 (${kind}): Amtliche Warnungen + Radar-Alarm wirken, genau ein PUT je Änderung, Stand überlebt das Neuladen`, async ({
				page
			}) => {
				const hub = await seedHub(page.request, kind, { extra: aw.seed });
				try {
					const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
					await oeffneAlarme(page, kind, hub.id);
					expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

					await radarSchalter(page).check();
					await expect(radarSchalter(page), 'AW-2 FAIL: der Radar-Schalter nimmt die Geste nicht an.').toBeChecked();
					await warteAufGespeichert(page);
					expect(puts.length, 'AW-2 FAIL: genau EIN PUT je Alarm-Änderung').toBe(1);
					expect(
						(await stand(page, kind, hub.id)).radar_alert_enabled,
						'AW-2 FAIL: der Radar-Alarm ist nicht gespeichert worden — fehlt der Rückruf am Mount, verpufft die Geste.'
					).toBe(true);

					const warVorher = await amtlichSchalter(page).isChecked();
					await amtlichSchalter(page).setChecked(!warVorher);
					await warteAufGespeichert(page);
					await expect
						.poll(async () => amtlichGespeichert(await stand(page, kind, hub.id)), {
							timeout: 15_000,
							message: 'AW-2 FAIL: „Amtliche Warnungen" wurde nicht gespeichert.'
						})
						.toBe(!warVorher);

					await oeffneAlarme(page, kind, hub.id);
					await expect(
						radarSchalter(page),
						'AW-2 FAIL: der Radar-Alarm steht nach dem Neuladen wieder auf „aus" — dann zeigt die Fläche den Vorgabewert statt des gespeicherten Standes.'
					).toBeChecked();
					await expect(
						amtlichSchalter(page),
						'AW-2 FAIL: „Amtliche Warnungen" steht nach dem Neuladen wieder auf dem alten Wert.'
					).toBeChecked({ checked: !warVorher });
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// AW-3 — Alt AC-2 „Kanal, Kanal-Schwelle, Telegram-Kurzstil".
		test(`AW-3 (${kind}): Kanal und Kanal-Schwelle wirken und überstehen das Neuladen`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: aw.seed });
			try {
				await oeffneAlarme(page, kind, hub.id);

				// AlertChannelPicker rendert das Atom <Switch> (role="switch", aria-checked) —
				// KEIN <input type="checkbox">. Deshalb Klick-Geste und aria-checked.
				await expect(
					telegramSchalter(page),
					'Vorbedingung: der Telegram-Kanal startet aus — ein Klick schaltet ihn sonst AUS statt AN.'
				).toHaveAttribute('aria-checked', 'false');
				await telegramSchalter(page).click();
				await expect(telegramSchalter(page), 'AW-3 FAIL: der Telegram-Schalter nimmt die Geste nicht an.').toHaveAttribute(
					'aria-checked',
					'true'
				);
				await warteAufGespeichert(page);
				// Issue #2293 S2: der Alarme-Reiter schreibt `alert_channels.telegram`.
				await expect
					.poll(
						async () => ((await stand(page, kind, hub.id)).alert_channels as Record<string, boolean> | undefined)?.telegram,
						{ timeout: 15_000, message: 'AW-3 FAIL: der Telegram-Kanal wurde nicht gespeichert.' }
					)
					.toBe(true);

				// Kanal-Schwelle: Stufen LOW/MODERATE/HIGH (alarme-tab/alertChannelState.ts:95).
				await page.locator('[data-testid="alert-channel-threshold-telegram-HIGH"]').first().click();
				await warteAufGespeichert(page);
				await expect
					.poll(
						async () =>
							((await stand(page, kind, hub.id)).alert_channel_thresholds as Record<string, string> | undefined)
								?.telegram,
						{ timeout: 15_000, message: 'AW-3 FAIL: die Kanal-Schwelle wurde nicht gespeichert.' }
					)
					.toBe('HIGH');

				// compare-eigen: Telegram-Kurzstil (`display_config.telegram_style`) liegt im
				// Vergleichs-Preset; AlarmeTab.svelte:530 rendert ihn nur bei context 'vergleich'.
				// Der Trip prüft den Kanal-Teil oben, den sein Hub tatsächlich führt.
				if (kind === 'vergleich') {
					const kurzstil = page.locator('[data-testid="telegram-kurzstil-toggle"] input[type="checkbox"]').first();
					await expect(kurzstil, 'AW-3 FAIL: der Kurzstil-Schalter fehlt im Alarme-Reiter des Vergleichs.').toBeVisible();
					await kurzstil.check();
					await warteAufGespeichert(page);
					await expect
						.poll(async () => dc(await stand(page, kind, hub.id)).telegram_style, {
							timeout: 15_000,
							message: 'AW-3 FAIL: der Telegram-Kurzstil wurde nicht gespeichert.'
						})
						.toBe('kurzform');
				}

				await oeffneAlarme(page, kind, hub.id);
				await expect(telegramSchalter(page), 'AW-3 FAIL: der Telegram-Kanal ist nach dem Neuladen wieder aus.').toHaveAttribute(
					'aria-checked',
					'true'
				);
				// compare-eigen (Begründung s. o.): Kurzstil nur im Vergleichs-Preset.
				if (kind === 'vergleich') {
					await expect(
						page.locator('[data-testid="telegram-kurzstil-toggle"] input[type="checkbox"]').first(),
						'AW-3 FAIL: der Kurzstil ist nach dem Neuladen wieder aus.'
					).toBeChecked();
				}
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-4 — Alt AC-2 „Empfindlichkeit, Cooldown, Stille Stunden".
		test(`AW-4 (${kind}): Empfindlichkeit, Cooldown und Stille Stunden wirken (je Einzelgeste genau ein PUT) und überstehen das Neuladen`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: aw.seed });
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				await oeffneAlarme(page, kind, hub.id);

				// Stufen off/entspannt/standard/sensibel — „sensibel" weicht vom Startwert ab.
				await page.locator('[data-testid="alert-quickset-sensibel"]').first().click();
				await warteAufGespeichert(page);
				await expect
					.poll(
						async () =>
							Object.values((dc(await stand(page, kind, hub.id)).metric_alert_levels as Record<string, string>) ?? {}),
						{
							timeout: 15_000,
							message:
								'AW-4 FAIL: die Alarm-Empfindlichkeit wurde nicht gespeichert — fehlt `onMetricLevelChange` am Mount, verpufft die Geste.'
						}
					)
					.toContain('sensibel');
				await bleibtBei(() => puts.length, 1, 1_200, 'AW-4 FAIL: die Empfindlichkeits-Geste darf nur EINEN PUT auslösen');

				const cooldown = page.locator('[data-testid="alert-cooldown-input"]').first();
				await expect(cooldown, 'Vorbedingung: Cooldown startet nicht auf dem Zielwert').not.toHaveValue('45');
				await cooldown.fill('45');
				await cooldown.blur();
				await warteAufGespeichert(page);
				await expect
					.poll(async () => (await stand(page, kind, hub.id)).alert_cooldown_minutes, {
						timeout: 15_000,
						message: 'AW-4 FAIL: der Cooldown wurde nicht gespeichert (Funktions-Bindung defekt?).'
					})
					.toBe(45);
				await bleibtBei(() => puts.length, 2, 1_200, 'AW-4 FAIL: die Cooldown-Geste darf nur EINEN PUT auslösen');

				// AlertQuietHoursCard spreizt die Testid auf das <input type="checkbox"> selbst.
				// Mehrschrittige Bedienfolge (Schalter + Von + Bis) — hier keine PUT-Zählung,
				// wie im Altfall; geprüft wird der gespeicherte Stand.
				const stilleAn = page.locator('[data-testid="alert-quiet-hours-toggle"]').first();
				if (!(await stilleAn.isChecked())) await stilleAn.check();
				const von = page.locator('[data-testid="alert-quiet-from"]').first();
				const bis = page.locator('[data-testid="alert-quiet-to"]').first();
				await von.fill('23:00');
				await bis.fill('06:00');
				await bis.blur();
				await warteAufGespeichert(page);
				await expect
					.poll(
						async () => {
							const s = await stand(page, kind, hub.id);
							return `${s.alert_quiet_from ?? '—'}/${s.alert_quiet_to ?? '—'}`;
						},
						{
							timeout: 15_000,
							message:
								'AW-4 FAIL: die Stillen Stunden wurden nicht gespeichert — die zweiwegige Bindung ist eine Funktions-Bindung, genau hier fällt ein Fehler darin auf.'
						}
					)
					.toContain('23:00');

				const reiter = await oeffneAlarme(page, kind, hub.id);
				await expect(
					page.locator('[data-testid="alert-cooldown-input"]').first(),
					'AW-4 FAIL: der Cooldown steht nach dem Neuladen wieder auf dem Vorgabewert.'
				).toHaveValue('45');
				await expect(
					page.locator('[data-testid="alert-quiet-from"]').first(),
					'AW-4 FAIL: die Stillen Stunden stehen nach dem Neuladen wieder auf dem Vorgabewert.'
				).toHaveValue('23:00');
				await expect(
					reiter.locator('[data-testid="alert-quiet-hours-card"]'),
					`AW-4 FAIL: die Stillen Stunden nennen nicht den Bezug „${aw.zonenBezug}" — die Prop \`zonenBezug\` fehlt oder trägt den falschen Wert.`
				).toContainText(aw.zonenBezug);
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-5 — Alt AC-2 „eine Alarm-Geste lässt die übrigen Einstellungen unangetastet".
		test(`AW-5 (${kind}): eine Alarm-Geste lässt die übrigen Einstellungen unangetastet`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: aw.seed });
			try {
				const vorher = await stand(page, kind, hub.id);
				const nachbarnVorher = await aw.nachbarn(page, vorher);
				await oeffneAlarme(page, kind, hub.id);

				await aw.ausloeser(page).setChecked(aw.ausloeserNeu);
				await warteAufGespeichert(page);

				const nachher = await stand(page, kind, hub.id);
				expect(aw.ausloeserWert(nachher), 'Vorbedingung: die Geste muss gespeichert sein').toBe(aw.ausloeserNeu);
				const nachbarnNachher = await aw.nachbarn(page, nachher);
				expect(
					(nachbarnVorher.auswahl as unknown[]).length,
					'Vorbedingung: der Ausgangsstand hat eine nicht-leere Metrik-Auswahl — sonst wäre der Vergleich leer gegen leer.'
				).toBeGreaterThan(0);
				for (const key of Object.keys(nachbarnVorher)) {
					expect(nachbarnNachher[key], `AW-5 FAIL: „${key}" hat sich durch die Alarm-Geste verändert.`).toEqual(
						nachbarnVorher[key]
					);
				}
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
