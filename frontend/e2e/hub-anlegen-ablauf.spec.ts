// E2E — Issue #2347 S4 (Epic #2345, Etappe P6): Anlege-Ablauf — EINE Zusicherung
// für die Anlege-Seite von Trip (/trips/new) UND Ortsvergleich (/compare/new) per
// Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s4_paritaets_e2e.md § „Fälle" (AN-1..AN-12),
// AC-7 bis AC-11; AN-13/AN-14 aus „Nachträge Teil D", AN-15 und die gesperrte CTA in
// AN-14 aus „Nachträge Teil E".
//
// Ersetzt (Zuordnung alt → neu): compare-editor-slice1 (AC-1..AC-5 → AN-1..AN-4),
// compare-editor-slice4 (AC-8/AC-9/AC-9b/AC-11/#1411 → AN-5/AN-6/AN-7/AN-12),
// issue-1093-compare-layout-crash (AC-1 → AN-11/AN-12), feat-1461-s3b2b (AC-14 →
// AN-6, vierte Fläche → AN-10), compare-flow-navigation (AC-26/27/29 → AN-6/AN-8,
// echter Klick auf „Neu" → AN-13) und compare-editor-fidelity-s8d (AC-15 → AN-9;
// AC-8..AC-12 Wortlaut je Pflichtschritt, gesperrte CTA ohne Namen und Punkte-Gate →
// AN-14; Desktop-Weiter-Füße AC-17/AC-18 → AN-15). Die beiden Trip-Lücken aus Teil D
// (CTA ohne Namen nicht `disabled`, fehlende Desktop-Weiter-Knöpfe) sind mit Teil E
// im Trip geschlossen (TripNewEditor.svelte, dem Vergleich angeglichen).
//
// Kind-Unterschiede stehen als Selektor-/Textdaten in ANLEGE_SEL (helpers.ts) bzw.
// in AN_SEL unten; jeder kind-Zweig trägt seinen Begründungskommentar (Spec
// „Kind-Kontraste"). AN-12 ist echtes Compare-Eigen (Stundenverlauf steht in
// COMPARE_ONLY_SECTIONS, #2346 S3) und läuft nur für den Vergleich.
//
// Kein fester Schlaf: gewartet wird auf Zustände (expect.poll, toHaveAttribute,
// toHaveCount), auf Aufrufe (waitForResponse) und das Stabilitätsfenster bleibtBei.
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts (Admin-Sitzung), kein UI-Login. Jeder Fall
// räumt die angelegten Objekte (Präfix E2E-GZ-) im `finally` ab; Test-Orte räumt
// cleanupTracked. Höchstens ein aktiver Vergleich je Fall (kein 409).

import { test, expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import {
	ANLEGE_SEL,
	anlegenPflicht,
	cleanupTracked,
	E2E_TEST_PREFIX,
	HUB_KINDS,
	HUB_SEL,
	hubApiPath,
	LISTE_SEL,
	openHub,
	type AnlegeReiterZustand,
	type HubKind
} from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };

type Rumpf = Record<string, unknown>;

/**
 * Schritt-Titel des mobilen Seitenkopfs je kind (fest, aus der Spec-Reiterfolge):
 * Trip „Route · Etappen & GPX · …", Vergleich „Vergleich · Orte · …".
 */
const SCHRITT_TITEL: Record<HubKind, Record<string, string>> = {
	route: {
		route: 'Route',
		etappen: 'Etappen & GPX',
		'wetter-metriken': 'Wetter-Metriken',
		wertebereiche: 'Wertebereiche',
		alarme: 'Alarme'
	},
	vergleich: {
		vergleich: 'Vergleich',
		orte: 'Orte',
		'wetter-metriken': 'Wetter-Metriken',
		wertebereiche: 'Wertebereiche',
		alarme: 'Alarme'
	}
};

/**
 * Spec-eigene Selektor-/Feldpfad-Unterschiede des vollen Durchlaufs (AN-6):
 * - Metrik-Auswahl: Trip schaltet in der Grundauswahl (Knopf, aktiv = Klasse `on`,
 *   Feldpfad display_config.metrics), der Vergleich per Zeilen-Checkbox (Feldpfad
 *   display_config.active_metrics) — dieselbe Unterscheidung wie MS_SEL in
 *   hub-wetter-metriken-speichert-selbst.spec.ts.
 * - Profil: Trip Aktivität per Dropdown, Vergleich per Kachel (Kind-Kontraste „AN Profil").
 */
const AN_SEL: Record<
	HubKind,
	{
		metrik: (page: Page) => Locator;
		metrikAn: (el: Locator) => Promise<boolean>;
		metrikImRumpf: (r: Rumpf) => boolean;
		profilWaehlen: (page: Page) => Promise<void>;
		erwarteProfil: (page: Page) => Promise<void>;
	}
> = {
	route: {
		metrik: (page) => page.locator('.tn-desktop [data-testid="wm2-grundauswahl"]').getByRole('button', { name: /Schneehöhe/ }),
		metrikAn: async (el) => /(^|\s)on(\s|$)/.test((await el.getAttribute('class')) ?? ''),
		metrikImRumpf: (r) =>
			(((r.display_config as Rumpf | undefined)?.metrics as Array<{ metric_id?: string; enabled?: boolean }> | undefined) ?? []).some(
				(m) => m.metric_id === 'snow_depth' && m.enabled === true
			),
		profilWaehlen: async (page) => {
			await page.locator('.tn-desktop').getByTestId('activity-dropdown').selectOption(ANLEGE_SEL.route.profilWert);
		},
		erwarteProfil: async (page) => {
			await expect(page.locator('.tn-desktop').getByTestId('activity-dropdown')).toHaveValue(ANLEGE_SEL.route.profilWert);
		}
	},
	vergleich: {
		metrik: (page) => page.locator('.cm-desktop [data-testid="weather-metrics-vergleich-row-snow_depth"] input[type="checkbox"]'),
		metrikAn: (el) => el.isChecked(),
		metrikImRumpf: (r) => JSON.stringify((r.display_config as Rumpf | undefined)?.active_metrics ?? []).includes('snow_depth'),
		profilWaehlen: async (page) => {
			await page.getByTestId(`compare-editor-profile-${ANLEGE_SEL.vergleich.profilWert}`).click();
		},
		erwarteProfil: async (page) => {
			await expect(page.getByTestId(`compare-editor-profile-${ANLEGE_SEL.vergleich.profilWert}`)).toHaveAttribute(
				'data-selected',
				'true'
			);
		}
	}
};

const einName = (tag: string) => `${E2E_TEST_PREFIX}AN-${tag}-${Date.now()}`;

/** Text als wörtliches Regex-Stück (z. B. das „+" in „+ Neuer Trip"). */
const regexText = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Mobile CTA-Kette auf den gemeinsamen Pflichtschritten (AN-14, Alt s8d AC-8..AC-12).
 * Kind-Kontraste (Spec „AN Pflichtangaben"/„AN Punkte-Schritt"): die Beschriftung folgt
 * den Pflichtangaben je Art — Trip Name + Startdatum und eine GPX je Etappe
 * (TripNewEditor.svelte tn-mobile-footer), Vergleich Name und mindestens zwei Orte
 * (CompareNewEditor.svelte cm-mobile-cta). Der Trip hat nach den Etappen den
 * OPTIONALEN Schritt „Wegpunkte prüfen"; der gemeinsame Pflichtweg führt über
 * „Direkt zu Wetter" in Wetter-Metriken, der Vergleich über „Wetter-Metriken →".
 * Ab Wetter-Metriken sind die Beschriftungen gleich (WEITER_GEMEINSAM).
 */
const CTA_KETTE: Record<HubKind, { ohneName: string; ersterWeiter: string; punkteGate: RegExp; punkteWeiter: string }> = {
	route: {
		ohneName: 'Trip-Name eingeben',
		ersterWeiter: 'Etappen anlegen →',
		punkteGate: /^\s*noch \d+ GPX nötig\s*$/,
		punkteWeiter: 'Direkt zu Wetter'
	},
	vergleich: {
		ohneName: 'Name eingeben',
		ersterWeiter: 'Orte hinzufügen →',
		punkteGate: /^\s*noch 2 Orte nötig\s*$/,
		punkteWeiter: 'Wetter-Metriken →'
	}
};
const WEITER_GEMEINSAM: ReadonlyArray<[von: string, cta: string, nach: string]> = [
	['wetter-metriken', 'Wertebereiche festlegen →', 'wertebereiche'],
	['wertebereiche', 'Alarme einrichten →', 'alarme']
];

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

/** Wartet, bis der Reiter die genannten Zustandsteile trägt (kind-neutral gelesen). */
async function erwarteZustand(
	page: Page,
	kind: HubKind,
	id: string,
	soll: Partial<AnlegeReiterZustand>,
	message: string,
	mobil = false
): Promise<void> {
	const reiter = ANLEGE_SEL[kind].reiter(page, id, mobil);
	await expect
		.poll(
			async () => {
				const z = await ANLEGE_SEL[kind].zustand(reiter);
				return Object.fromEntries(Object.keys(soll).map((k) => [k, z[k as keyof AnlegeReiterZustand]]));
			},
			{ message, timeout: 10_000 }
		)
		.toEqual(soll);
}

/** Öffnet einen Schritt per Reiter-Klick (Desktop) und wartet, bis er aktiv ist. */
async function schrittOeffnen(page: Page, kind: HubKind, id: string, mobil = false): Promise<void> {
	await ANLEGE_SEL[kind].reiter(page, id, mobil).click({ force: mobil });
	await erwarteZustand(page, kind, id, { aktiv: true }, `Schritt „${id}" wird nicht aktiv`, mobil);
}

/** Besucht die drei Schwanz-Schritte bis Alarme (Abschluss-Gate `canFinish`). */
async function bisAlarme(page: Page, kind: HubKind, mobil = false): Promise<void> {
	for (const id of ['wetter-metriken', 'wertebereiche', 'alarme']) await schrittOeffnen(page, kind, id, mobil);
}

/** Zählt die Anlege-POSTs der Art und sammelt die Kennungen der Antworten. */
function postMitschnitt(page: Page, kind: HubKind): { rumpfe: Rumpf[]; ids: string[] } {
	const rumpfe: Rumpf[] = [];
	const ids: string[] = [];
	const pfad = ANLEGE_SEL[kind].postPfad;
	page.on('request', (r) => {
		if (r.method() === 'POST' && new URL(r.url()).pathname === pfad) rumpfe.push((r.postDataJSON() ?? {}) as Rumpf);
	});
	page.on('response', async (r) => {
		if (r.request().method() !== 'POST' || new URL(r.url()).pathname !== pfad || !r.ok()) return;
		const id = ((await r.json().catch(() => ({}))) as { id?: string }).id;
		if (id) ids.push(id);
	});
	return { rumpfe, ids };
}

function anlegePost(page: Page, kind: HubKind) {
	const pfad = ANLEGE_SEL[kind].postPfad;
	return page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === pfad, {
		timeout: 30_000
	});
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

async function eintraegeMitNamen(request: APIRequestContext, kind: HubKind, name: string): Promise<string[]> {
	const res = await request.get(ANLEGE_SEL[kind].postPfad);
	expect(res.ok(), `GET ${ANLEGE_SEL[kind].postPfad} HTTP ${res.status()}`).toBeTruthy();
	return ((await res.json()) as Array<{ id: string; name: string }>).filter((e) => e.name === name).map((e) => e.id);
}

/** Räumt jedes angelegte Objekt ab — mitgeschnittene Kennungen UND alles mit dem Testnamen. */
async function aufraeumen(request: APIRequestContext, kind: HubKind, name: string, ids: string[]): Promise<void> {
	const alle = new Set(ids);
	const res = await request.get(ANLEGE_SEL[kind].postPfad).catch(() => null);
	if (res?.ok()) {
		for (const e of (await res.json()) as Array<{ id: string; name: string }>) if (e.name === name) alle.add(e.id);
	}
	for (const id of alle) {
		const del = await request.delete(hubApiPath(kind, id));
		if (!del.ok() && del.status() !== 404) console.error(`[e2e-cleanup] DELETE ${hubApiPath(kind, id)} -> HTTP ${del.status()}`);
	}
}

async function stand(request: APIRequestContext, kind: HubKind, id: string): Promise<Rumpf> {
	const res = await request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Rumpf;
}

const schwellen = (r: Rumpf) => (r.alert_channel_thresholds as Record<string, string> | undefined) ?? {};

// ─── AN-1 .. AN-8 (Desktop 1280) ──────────────────────────────────────────────
test.describe('Anlege-Ablauf (Desktop 1280)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(DESKTOP);
	});

	for (const kind of HUB_KINDS) {
		const sel = ANLEGE_SEL[kind];

		test(`AN-1 (${kind}): 2. Schritt gesperrt, Klick wechselt nicht; nach den Pflichtangaben frei, 1. Schritt „done"`, async ({
			page
		}) => {
			await page.goto(sel.url);
			const zweiter = sel.reiter(page, sel.punkteSchritt);
			await expect(zweiter).toBeVisible({ timeout: 15_000 });
			await erwarteZustand(page, kind, sel.punkteSchritt, { gesperrt: true }, 'AN-1: 2. Schritt muss leer gesperrt sein');
			await zweiter.click({ force: true });
			await erwarteZustand(page, kind, sel.ersterSchritt, { aktiv: true }, 'AN-1: Klick auf den gesperrten Schritt darf nicht wechseln');
			await erwarteZustand(page, kind, sel.punkteSchritt, { aktiv: false }, 'AN-1: gesperrter Schritt wurde aktiv');

			await anlegenPflicht(page, kind, { name: einName('AN1'), nurKopf: true });
			await erwarteZustand(page, kind, sel.punkteSchritt, { gesperrt: false }, 'AN-1: Pflichtangaben schalten den 2. Schritt nicht frei');
			await schrittOeffnen(page, kind, sel.punkteSchritt);
			await erwarteZustand(page, kind, sel.ersterSchritt, { erledigt: true }, 'AN-1: 1. Schritt ist nach den Pflichtangaben nicht „done"');
		});

		test(`AN-2 (${kind}): Fortschritt hat genau 5 Segmente und steigt mit der Pflichteingabe auf „1 / 5"`, async ({
			page
		}) => {
			await page.goto(sel.url);
			await expect(sel.fortschrittSegment(page), 'AN-2: Segmentzahl des Fortschritts').toHaveCount(sel.fortschrittSegmente, {
				timeout: 15_000
			});
			await expect(sel.fortschritt(page)).not.toContainText(`1 / ${sel.fortschrittSegmente}`);
			await anlegenPflicht(page, kind, { name: einName('AN2'), nurKopf: true });
			await expect(sel.fortschritt(page), 'AN-2: Fortschritt steigt nicht mit der Pflichteingabe').toContainText(
				`1 / ${sel.fortschrittSegmente}`,
				{ timeout: 10_000 }
			);
			await expect(sel.fortschrittSegment(page)).toHaveCount(sel.fortschrittSegmente);
		});

		test(`AN-3 (${kind}): Profil bzw. Aktivität bleibt nach Schrittwechsel und Rückkehr gewählt`, async ({ page }) => {
			await anlegenPflicht(page, kind, { name: einName('AN3'), nurKopf: true });
			await AN_SEL[kind].profilWaehlen(page);
			await AN_SEL[kind].erwarteProfil(page);
			await schrittOeffnen(page, kind, sel.punkteSchritt);
			await schrittOeffnen(page, kind, sel.ersterSchritt);
			await AN_SEL[kind].erwarteProfil(page);
		});

		test(`AN-4 (${kind}): Weiter-Knopf des 1. Schritts wechselt aktiv auf den Punkte-Schritt`, async ({ page }) => {
			await anlegenPflicht(page, kind, { name: einName('AN4'), nurKopf: true });
			await expect(sel.weiterErsterSchritt(page)).toBeEnabled({ timeout: 10_000 });
			await sel.weiterErsterSchritt(page).click();
			await erwarteZustand(page, kind, sel.punkteSchritt, { aktiv: true }, 'AN-4: Weiter-Knopf führt nicht in den Punkte-Schritt');
			await erwarteZustand(page, kind, sel.ersterSchritt, { aktiv: false }, 'AN-4: 1. Schritt bleibt aktiv');
		});

		test(`AN-5 (${kind}): Abschluss gesperrt mit Hinweis, bis alle Pflichtschritte bis Alarme besucht sind`, async ({
			page
		}) => {
			await anlegenPflicht(page, kind, { name: einName('AN5') });
			const abschluss = sel.abschluss(page);
			await expect(abschluss).toBeVisible({ timeout: 15_000 });
			await expect(abschluss, 'AN-5: Abschluss vor den Pflichtschritten frei').toBeDisabled();
			await expect(
				page.getByText(sel.abschlussHinweis).filter({ visible: true }).first(),
				'AN-5: Hinweistext am gesperrten Abschluss fehlt'
			).toBeVisible();

			await schrittOeffnen(page, kind, 'wetter-metriken');
			await schrittOeffnen(page, kind, 'wertebereiche');
			await expect(abschluss, 'AN-5: Abschluss vor dem Alarme-Schritt frei').toBeDisabled();
			await schrittOeffnen(page, kind, 'alarme');
			await expect(abschluss, 'AN-5: Abschluss nach Besuch aller Pflichtschritte noch gesperrt').toBeEnabled({
				timeout: 10_000
			});
		});

		test(`AN-6 (${kind}): voller Durchlauf ⇒ genau EIN POST ohne id, Körper trägt jede Auswahl, Hub des NEUEN Objekts, Roundtrip + Anzeige`, async ({
			page
		}) => {
			const name = einName('AN6');
			const post = postMitschnitt(page, kind);
			try {
				await anlegenPflicht(page, kind, { name });

				await schrittOeffnen(page, kind, 'wetter-metriken');
				const metrik = AN_SEL[kind].metrik(page);
				await expect(metrik, 'AN-6: Metrik-Umschalter im Schritt Wetter-Metriken fehlt').toBeVisible({ timeout: 15_000 });
				const warAn = await AN_SEL[kind].metrikAn(metrik);
				await metrik.click();
				await expect.poll(() => AN_SEL[kind].metrikAn(metrik), { message: 'AN-6: Metrik schaltet nicht um' }).toBe(!warAn);
				// Compare-eigen (Kind-Kontraste AN-12/AN-6): Stundenverlauf steht nur im
				// Vergleich (COMPARE_ONLY_SECTIONS, #2346 S3) — der Trip hat keinen Zweig.
				if (kind === 'vergleich') {
					const stunde = page.locator('.cm-desktop [data-testid="compare-layout-hourly-metric-temp_c"] input').first();
					await expect(stunde).toBeVisible({ timeout: 10_000 });
					await stunde.click();
				}

				await schrittOeffnen(page, kind, 'wertebereiche');
				await expect(sel.inhalt.wertebereiche(page), 'AN-6: Wertebereiche-Inhalt fehlt').toBeVisible({ timeout: 15_000 });

				await schrittOeffnen(page, kind, 'alarme');
				const hoch = page.locator('[data-testid="alert-channel-threshold-telegram-HIGH"]:visible').first();
				await expect(hoch, 'AN-6: Kanal-Stufe im Alarme-Schritt fehlt').toBeVisible({ timeout: 15_000 });
				await hoch.click();
				await expect(hoch).toHaveAttribute('aria-pressed', 'true');

				const antwortKommt = anlegePost(page, kind);
				await sel.abschluss(page).click();
				const antwort = await antwortKommt;
				expect([200, 201], `AN-6: POST ${sel.postPfad} HTTP ${antwort.status()}`).toContain(antwort.status());
				const rumpf = (antwort.request().postDataJSON() ?? {}) as Rumpf;
				expect(rumpf.id, 'AN-6: der Anlege-POST darf keine id tragen').toBeUndefined();
				expect(rumpf.name).toBe(name);
				expect(AN_SEL[kind].metrikImRumpf(rumpf), 'AN-6: Metrik-Auswahl fehlt im POST').toBe(!warAn);
				expect((rumpf.corridors as unknown[] | undefined)?.length ?? 0, 'AN-6: Wertebereiche fehlen im POST').toBeGreaterThan(0);
				expect(schwellen(rumpf).telegram, 'AN-6: Kanal-Stufe fehlt im POST').toBe('HIGH');
				if (kind === 'vergleich') {
					const stunden = (rumpf.display_config as Rumpf | undefined)?.hourly_metrics as unknown[] | undefined;
					expect(stunden?.length ?? 0, 'AN-6: Stundenverlauf-Auswahl fehlt im POST').toBeGreaterThan(0);
					// Alt slice4 AC-11 (Kind-Kontrast AN-12): im Vergleich ist `channel_layouts`
					// Ballast (#1351) — der Anlege-POST darf die Attrappe nicht wieder senden.
					// Beim Trip ist das Feld eine echte Kanal-Auswahl (#1575), daher kein Zweig.
					expect(
						(rumpf.display_config as Rumpf | undefined)?.channel_layouts,
						'AN-6: Anlege-POST des Vergleichs trägt wieder die channel_layouts-Attrappe'
					).toBeUndefined();
				}

				const id = ((await antwort.json()) as { id: string }).id;
				await expect(page, 'AN-6: Seite landet nicht im Hub des NEUEN Objekts').toHaveURL(HUB_SEL[kind].hubUrl(id), {
					timeout: 15_000
				});
				await bleibtBei(() => post.rumpfe.length, 1, 1_500, 'AN-6: genau EIN Anlege-POST');
				// Rumpf-Abgleich compare-flow-navigation AC-26/AC-29: der Hub zeigt das NEUE Objekt.
				await expect(
					page.getByText(name).filter({ visible: true }).first(),
					'AN-6: der Hub zeigt den Namen des neuen Objekts nicht'
				).toBeVisible({ timeout: 10_000 });

				const s = await stand(page.request, kind, id);
				expect(AN_SEL[kind].metrikImRumpf(s), 'AN-6: Roundtrip verliert die Metrik-Auswahl').toBe(!warAn);
				expect((s.corridors as unknown[] | undefined)?.length ?? 0, 'AN-6: Roundtrip verliert die Wertebereiche').toBeGreaterThan(0);
				expect(schwellen(s).telegram, 'AN-6: Roundtrip verliert die Kanal-Stufe').toBe('HIGH');
				if (kind === 'vergleich') {
					expect((s.display_config as Rumpf).hourly_metrics).toEqual((rumpf.display_config as Rumpf).hourly_metrics);
					// Rumpf-Abgleich compare-layout-tab-dissolution AC-6 (#1360 F002): das Feld
					// des abgeschafften Layout-Reiters taucht am Anlege-Pfad nicht wieder auf.
					expect(
						(s.display_config as Rumpf).top_n,
						'AN-6: angelegter Vergleich trägt wieder display_config.top_n'
					).toBeUndefined();
					expect(
						(s.display_config as Rumpf).channel_layouts,
						'AN-6: angelegter Vergleich trägt im Roundtrip die channel_layouts-Attrappe'
					).toBeUndefined();
				}

				await openHub(page, kind, id, { tab: 'alarme' });
				await expect(
					page.locator('[data-testid="alert-channel-threshold-telegram-HIGH"]:visible').first(),
					'AN-6: Reiter Alarme zeigt die gewählte Stufe nicht'
				).toHaveAttribute('aria-pressed', 'true', { timeout: 15_000 });
			} finally {
				await aufraeumen(page.request, kind, name, post.ids);
			}
		});

		test(`AN-7 (${kind}): Doppelklick auf den Abschluss ⇒ genau EIN POST, genau EIN neues Objekt`, async ({ page }) => {
			const name = einName('AN7');
			const post = postMitschnitt(page, kind);
			try {
				await anlegenPflicht(page, kind, { name });
				await bisAlarme(page, kind);
				const abschluss = sel.abschluss(page);
				await expect(abschluss).toBeEnabled({ timeout: 15_000 });
				const antwortKommt = anlegePost(page, kind);
				await abschluss.dblclick();
				const antwort = await antwortKommt;
				expect([200, 201]).toContain(antwort.status());
				await bleibtBei(() => post.rumpfe.length, 1, 2_000, 'AN-7: Doppelklick löst mehr als EINEN POST aus');
				expect(await eintraegeMitNamen(page.request, kind, name), 'AN-7: genau ein neues Objekt in der Liste').toHaveLength(1);
			} finally {
				await aufraeumen(page.request, kind, name, post.ids);
			}
		});

		test(`AN-8 (${kind}): Abbrechen aus dem fertigen Zustand ⇒ Liste, KEIN POST, kein neues Objekt`, async ({ page }) => {
			const name = einName('AN8');
			const post = postMitschnitt(page, kind);
			try {
				await anlegenPflicht(page, kind, { name });
				// Fertiger Zustand: der Trip speichert beim Verlassen sonst selbst (beforeNavigate).
				await bisAlarme(page, kind);
				await expect(sel.abschluss(page)).toBeEnabled({ timeout: 15_000 });
				await sel.abbrechen(page).click();
				await expect.poll(() => new URL(page.url()).pathname, { message: 'AN-8: Abbrechen führt nicht zur Liste' }).toBe(
					LISTE_SEL[kind].url
				);
				await bleibtBei(() => post.rumpfe.length, 0, 1_500, 'AN-8: Abbrechen darf keinen POST senden');
				expect(await eintraegeMitNamen(page.request, kind, name), 'AN-8: Abbrechen hat ein Objekt angelegt').toHaveLength(0);
			} finally {
				await aufraeumen(page.request, kind, name, post.ids);
			}
		});

		// AN-13 — #2347 S4 Teil D: Alt compare-flow-navigation AC-26/AC-27 „echter Klick auf
		// ‚+ Neuer Vergleich' statt goto". AN-6/AN-8 öffnen die Anlege-Seite per goto; hier
		// der Einstieg über den Knopf der Desktop-Liste und das Abbrechen aus dem leeren Zustand.
		test(`AN-13 (${kind}): echter Klick auf „Neu" in der Desktop-Liste ⇒ Anlege-Seite im 1. Schritt; Abbrechen ⇒ Liste, KEIN POST`, async ({
			page
		}) => {
			const liste = LISTE_SEL[kind];
			const post = postMitschnitt(page, kind);
			await page.goto(liste.url);
			const neu = page
				.locator('a:visible, button:visible')
				.filter({ hasText: new RegExp(`^\\s*${regexText(liste.neuDesktop)}\\s*$`) });
			await expect(neu, `AN-13: genau ein Desktop-Knopf „${liste.neuDesktop}" in der Liste`).toHaveCount(1, {
				timeout: 15_000
			});
			await neu.click();
			await expect
				.poll(() => new URL(page.url()).pathname, { message: 'AN-13: „Neu" führt nicht zur Anlege-Seite' })
				.toBe(liste.anlegeUrl);
			await expect(sel.reiter(page, sel.ersterSchritt)).toBeVisible({ timeout: 15_000 });
			await erwarteZustand(page, kind, sel.ersterSchritt, { aktiv: true }, 'AN-13: Anlege-Seite startet nicht im 1. Schritt');

			await sel.abbrechen(page).click();
			await expect
				.poll(() => new URL(page.url()).pathname, { message: 'AN-13: Abbrechen führt nicht zur Liste' })
				.toBe(liste.url);
			await bleibtBei(() => post.rumpfe.length, 0, 1_500, 'AN-13: Einstieg und Abbrechen dürfen keinen POST senden');
		});

		// AN-15 — #2347 S4 Teil E: Alt compare-editor-fidelity-s8d AC-17/AC-18 (Desktop-
		// Weiter-Füße der Schwanz-Schritte). Rumpf-Abgleich: Weiter aus Wetter-Metriken ⇒
		// Wertebereiche, Weiter aus Wertebereiche ⇒ Alarme, danach kein weiterer Schritt
		// (alt: kein „continue-versand"/Versand-Reiter; hier strenger: im Alarme-Schritt
		// ist GAR KEIN Weiter-Fuß der Art sichtbar) und der Abschluss ist frei. Zusätzlich:
		// der Weg über die Weiter-Füße legt nichts an. Trip-Kennungen sind mit Teil E
		// nachgetragen (TripNewEditor.svelte, dem Vergleich angeglichen).
		test(`AN-15 (${kind}): Desktop-Weiter-Füße — Wetter-Metriken ⇒ Wertebereiche ⇒ Alarme, danach kein Weiter mehr, Abschluss frei`, async ({
			page
		}) => {
			const name = einName('AN15');
			const post = postMitschnitt(page, kind);
			try {
				await anlegenPflicht(page, kind, { name });
				await schrittOeffnen(page, kind, 'wetter-metriken');
				const zuWertebereichen = sel.weiterNach.wertebereiche(page);
				await expect(zuWertebereichen, 'AN-15: Weiter-Fuß „Wertebereiche festlegen →" fehlt').toBeVisible({ timeout: 15_000 });
				await expect(zuWertebereichen).toHaveText(/Wertebereiche festlegen →/);
				await expect(sel.weiterNach.alarme(page), 'AN-15: Alarme-Fuß schon im Schritt Wetter-Metriken').toBeHidden();
				await zuWertebereichen.click();
				await erwarteZustand(page, kind, 'wertebereiche', { aktiv: true }, 'AN-15: Weiter-Fuß führt nicht nach Wertebereiche');

				const zuAlarmen = sel.weiterNach.alarme(page);
				await expect(zuAlarmen, 'AN-15: Weiter-Fuß „Alarme einrichten →" fehlt').toBeVisible({ timeout: 15_000 });
				await expect(zuAlarmen).toHaveText(/Alarme einrichten →/);
				await expect(sel.weiterNach.wertebereiche(page), 'AN-15: Wertebereiche-Fuß bleibt im Schritt Wertebereiche stehen').toBeHidden();
				await zuAlarmen.click();
				await erwarteZustand(page, kind, 'alarme', { aktiv: true }, 'AN-15: Weiter-Fuß führt nicht nach Alarme');

				await expect(
					page.locator(`[data-testid^="${sel.weiterPraefix}"]:visible`),
					'AN-15: im letzten Schritt Alarme steht noch ein Weiter-Fuß'
				).toHaveCount(0);
				await expect(sel.abschluss(page), 'AN-15: Abschluss nach dem Weg über die Weiter-Füße gesperrt').toBeEnabled({
					timeout: 10_000
				});
				await bleibtBei(() => post.rumpfe.length, 0, 1_500, 'AN-15: der Weg über die Weiter-Füße darf nichts anlegen');
			} finally {
				await aufraeumen(page.request, kind, name, post.ids);
			}
		});
	}
});

// ─── AN-9, AN-10 (mobil 390×844) ──────────────────────────────────────────────
test.describe('Anlege-Ablauf (mobil 390)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(MOBIL);
	});

	for (const kind of HUB_KINDS) {
		const sel = ANLEGE_SEL[kind];
		const kopf = (page: Page) => page.locator('[data-slot="page-header"]:visible');

		test(`AN-9 (${kind}): CTA wechselt je Schritt, Abschluss erst im letzten Schritt im Sticky-Footer, ein Kopf, Titel wechselt, Zurück ⇒ Liste`, async ({
			page
		}) => {
			const name = einName('AN9');
			const post = postMitschnitt(page, kind);
			try {
				await page.goto(sel.url);
				await expect(kopf(page), 'AN-9: genau ein Seitenkopf').toHaveCount(1, { timeout: 15_000 });
				await expect(kopf(page).locator('h1')).toHaveText(SCHRITT_TITEL[kind][sel.ersterSchritt]);
				// Rumpf-Abgleich s8d AC-15: keine App-Leiste neben dem Seitenkopf.
				await expect(page.getByTestId('top-app-bar'), 'AN-9: App-Leiste zusätzlich zum Seitenkopf').toHaveCount(0);
				await expect(sel.abschluss(page, true), 'AN-9: Abschluss schon im 1. Schritt sichtbar').toBeHidden();

				await anlegenPflicht(page, kind, { name, mobil: true });
				const ctaTexte: string[] = [];
				for (const id of [sel.punkteSchritt, 'wetter-metriken', 'wertebereiche']) {
					if (id !== sel.punkteSchritt) await schrittOeffnen(page, kind, id, true);
					await expect(kopf(page)).toHaveCount(1);
					await expect(kopf(page).locator('h1'), `AN-9: Titel im Schritt „${id}"`).toHaveText(SCHRITT_TITEL[kind][id]);
					await expect(sel.abschluss(page, true), `AN-9: Abschluss schon im Schritt „${id}" sichtbar`).toBeHidden();
					ctaTexte.push((await sel.mobilFooter(page).innerText()).trim());
				}
				expect(new Set(ctaTexte).size, `AN-9: CTA-Beschriftung wechselt nicht je Schritt: ${JSON.stringify(ctaTexte)}`).toBe(
					ctaTexte.length
				);

				await schrittOeffnen(page, kind, 'alarme', true);
				await expect(kopf(page).locator('h1')).toHaveText(SCHRITT_TITEL[kind].alarme);
				await expect(sel.alleReiterMobil(page).last(), 'AN-9: Alarme ist nicht der letzte Schritt').toContainText('Alarme');
				const abschluss = sel.abschluss(page, true);
				await expect(abschluss, 'AN-9: Abschluss fehlt im letzten Schritt').toBeVisible();
				await expect(
					sel.mobilFooter(page).filter({ has: abschluss }),
					'AN-9: Abschluss steht nicht im Sticky-Footer'
				).toHaveCount(1);
				await expect(abschluss).toContainText(sel.abschlussLabel);
				// Rumpf-Abgleich s8d AC-15: im letzten Schritt ist der Abschluss frei.
				await expect(abschluss, 'AN-9: Abschluss im letzten Schritt gesperrt').toBeEnabled();

				await page.locator('[aria-label^="Zurück"]:visible').first().click();
				await expect.poll(() => new URL(page.url()).pathname, { message: 'AN-9: Zurück führt nicht zur Liste' }).toBe(
					LISTE_SEL[kind].url
				);
				// Rumpf-Abgleich s8d AC-15: nach der Rück-Navigation steht genau der Listen-Kopf,
				// kein Anlege-Kopf hängt nach.
				await expect(kopf(page), 'AN-9: nach Zurück mehr als ein Seitenkopf').toHaveCount(1, { timeout: 10_000 });
				await expect(kopf(page).locator('h1'), 'AN-9: nach Zurück steht nicht der Listen-Kopf').toHaveText(
					LISTE_SEL[kind].titel
				);
			} finally {
				await aufraeumen(page.request, kind, name, post.ids);
			}
		});

		test(`AN-10 (${kind}): Alarme-Schritt zeigt die Stufen-Auswahl auf „gering", ohne Geste ist im POST keine Stufe gesetzt`, async ({
			page
		}) => {
			const name = einName('AN10');
			const post = postMitschnitt(page, kind);
			try {
				await anlegenPflicht(page, kind, { name, mobil: true });
				await bisAlarme(page, kind, true);
				const gruppe = page.locator('[data-testid="alert-channel-threshold-telegram"]:visible').first();
				await expect(gruppe, 'AN-10: Stufen-Auswahl im Alarme-Schritt fehlt').toBeVisible({ timeout: 15_000 });
				const gering = gruppe.locator('[data-testid="alert-channel-threshold-telegram-LOW"]');
				await expect(gering).toHaveText('gering');
				await expect(gering, 'AN-10: Startwert ist nicht „gering"').toHaveAttribute('aria-pressed', 'true');

				const antwortKommt = anlegePost(page, kind);
				await sel.abschluss(page, true).click();
				const antwort = await antwortKommt;
				expect([200, 201]).toContain(antwort.status());
				const gesetzt = Object.entries(schwellen((antwort.request().postDataJSON() ?? {}) as Rumpf)).filter(
					([, stufe]) => stufe !== 'LOW'
				);
				expect(gesetzt, 'AN-10: ohne Geste darf keine Kanal-Stufe vom Startwert abweichen').toEqual([]);
			} finally {
				await aufraeumen(page.request, kind, name, post.ids);
			}
		});

		// AN-14 — #2347 S4 Teil D: Alt compare-editor-fidelity-s8d AC-8..AC-12 (mobile CTA je
		// Schritt mit festem Wortlaut). AN-9 prüft nur „Beschriftung wechselt"; hier der
		// Wortlaut je Pflichtschritt, der Weg per CTA-Klick (nicht per Reiter), die
		// gesperrte CTA ohne Namen (Alt s8d AC-8, Teil E: beim Trip nachgezogen) und das
		// gesperrte Punkte-Gate.
		test(`AN-14 (${kind}): mobile CTA-Kette — fester Wortlaut je Pflichtschritt, CTA-Klick führt weiter, Punkte-Gate gesperrt, Abschluss erst im Alarme-Schritt`, async ({
			page
		}) => {
			const k = CTA_KETTE[kind];
			const name = einName('AN14');
			const post = postMitschnitt(page, kind);
			const cta = (text: string | RegExp) =>
				sel.mobilFooter(page).getByRole('button', typeof text === 'string' ? { name: text, exact: true } : { name: text });
			try {
				await page.goto(sel.url);
				await expect(cta(k.ohneName), 'AN-14: CTA ohne Namen trägt nicht den Hinweis').toBeVisible({ timeout: 15_000 });
				await expect(cta(k.ersterWeiter), 'AN-14: Weiter-CTA schon ohne Namen').toHaveCount(0);
				// Alt s8d AC-8: echtes `disabled`-Attribut, kein reiner Stil-Zustand.
				await expect(cta(k.ohneName), 'AN-14: CTA ohne Namen ist nicht gesperrt').toBeDisabled();
				await cta(k.ohneName).click({ force: true });
				await erwarteZustand(page, kind, sel.ersterSchritt, { aktiv: true }, 'AN-14: CTA ohne Namen wechselt den Schritt', true);
				await erwarteZustand(page, kind, sel.punkteSchritt, { aktiv: false }, 'AN-14: CTA ohne Namen öffnet den Punkte-Schritt', true);

				await anlegenPflicht(page, kind, { name, mobil: true, nurKopf: true });
				await expect(cta(k.ersterWeiter), 'AN-14: Weiter-CTA nach den Pflichtangaben').toBeEnabled({ timeout: 10_000 });
				await cta(k.ersterWeiter).click();
				await erwarteZustand(page, kind, sel.punkteSchritt, { aktiv: true }, 'AN-14: Weiter-CTA führt nicht in den Punkte-Schritt', true);
				await expect(cta(k.punkteGate), 'AN-14: Punkte-Gate ohne GPX bzw. Orte fehlt').toBeVisible({ timeout: 10_000 });
				await expect(cta(k.punkteGate), 'AN-14: Punkte-Gate ist nicht gesperrt').toBeDisabled();
				await expect(cta(k.punkteWeiter), 'AN-14: Weiter aus dem Punkte-Schritt ohne GPX bzw. Orte').toHaveCount(0);

				await anlegenPflicht(page, kind, { name, mobil: true });
				await erwarteZustand(page, kind, sel.punkteSchritt, { aktiv: true }, 'AN-14: Pflichtangaben enden nicht im Punkte-Schritt', true);
				await expect(cta(k.punkteGate), 'AN-14: Punkte-Gate bleibt nach GPX bzw. Orten stehen').toHaveCount(0, {
					timeout: 15_000
				});
				await expect(cta(k.punkteWeiter)).toBeEnabled();
				await cta(k.punkteWeiter).click();
				await erwarteZustand(page, kind, 'wetter-metriken', { aktiv: true }, 'AN-14: Weiter aus dem Punkte-Schritt führt nicht in Wetter-Metriken', true);

				for (const [von, text, nach] of WEITER_GEMEINSAM) {
					await expect(cta(text), `AN-14: CTA „${text}" fehlt im Schritt „${von}"`).toBeEnabled({ timeout: 10_000 });
					await expect(sel.abschluss(page, true), `AN-14: Abschluss schon im Schritt „${von}"`).toBeHidden();
					await cta(text).click();
					await erwarteZustand(page, kind, nach, { aktiv: true }, `AN-14: CTA „${text}" führt nicht nach „${nach}"`, true);
				}
				const abschluss = sel.abschluss(page, true);
				await expect(abschluss, 'AN-14: Abschluss im Alarme-Schritt fehlt').toBeVisible();
				await expect(sel.mobilFooter(page).filter({ has: abschluss }), 'AN-14: Abschluss nicht im Sticky-Footer').toHaveCount(1);
				await expect(abschluss).toContainText(sel.abschlussLabel);
				await expect(abschluss, 'AN-14: Abschluss nach dem Pflichtweg per CTA gesperrt').toBeEnabled();
				expect(post.rumpfe, 'AN-14: der CTA-Weg darf nichts anlegen').toHaveLength(0);
			} finally {
				await aufraeumen(page.request, kind, name, post.ids);
			}
		});
	}
});

// ─── AN-11 (Desktop) ──────────────────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	const sel = ANLEGE_SEL[kind];
	test(`AN-11 (${kind}): alle fünf Schritte mit echten Etappen bzw. Orten ⇒ kein pageerror, Inhalt sichtbar`, async ({
		page
	}) => {
		const fehler: string[] = [];
		page.on('pageerror', (e) => fehler.push(e.message));
		await page.setViewportSize(DESKTOP);
		await anlegenPflicht(page, kind, { name: einName('AN11') });
		for (const id of sel.schritte) {
			await schrittOeffnen(page, kind, id);
			if (id === 'wetter-metriken' || id === 'wertebereiche' || id === 'alarme') {
				await expect(sel.inhalt[id](page), `AN-11: Inhalt des Schritts „${id}" fehlt`).toBeVisible({ timeout: 15_000 });
			}
		}
		expect(fehler, 'AN-11: pageerror beim Durchklicken').toEqual([]);
	});
}

// ─── AN-12 (nur vergleich, Kind-Kontrast) ─────────────────────────────────────
// Echtes Compare-Eigen (Spec „Kind-Kontraste" AN-12): der Stundenverlauf steht in
// COMPARE_ONLY_SECTIONS (#2346 S3), Temperatur Max/Min ist Vergleichs-Vokabular
// (Trip führt eine Zeile `temperature`), die Layout-Attrappe war Vergleichs-
// spezifisch (#1301). Der Trip hat keinen Zweig.
test('AN-12 (vergleich): Stundenverlauf-Schalter da, keine Layout-Attrappe, Temperatur Max/Min je eine eigene, unabhängig anhakbare Zeile', async ({
	page
}) => {
	const kind: HubKind = 'vergleich';
	await page.setViewportSize(DESKTOP);
	await anlegenPflicht(page, kind, { name: einName('AN12') });
	await schrittOeffnen(page, kind, 'wetter-metriken');

	await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible').first()).toBeVisible({
		timeout: 15_000
	});
	// Rumpf-Abgleich compare-flow-navigation AC-8: auch die Metrik-Auswahl des Stundenverlaufs ist da.
	await expect(page.locator('[data-testid="compare-layout-hourly-metrics"]:visible').first()).toBeVisible();

	// Alt slice4 AC-11 / flow Slice 4 AC-9 „keine channel_layouts-Attrappe". Die frühere
	// DOM-Aussage `channel-tab-email` count 0 ist seit #1703 S8 überholt: der geteilte
	// LayoutTab-Organism (LTChannelPicker, `channel-tab-<kanal>`) steht legitim im
	// Abschnitt „Reihenfolge" von Wetter-Metriken und schreibt die kanal-eigene Auswahl
	// nach `display_config.channel_active_metrics` (compareEditorSave.ts
	// buildNewComparePresetPayload) — NICHT nach `channel_layouts`, das im Vergleich
	// Ballast ist (#1301-Grundbefund, #1351: kein Compare-Renderer liest es). Was heute
	// wirkt, wird deshalb so geprüft: (1) der Kanal-Umschalter existiert genau einmal und
	// nur im LayoutTab, der die Reihenfolge-Karte trägt — kein eigener Kanal-Reiter, kein
	// Anlege-Schritt „Layout"/„Versand", keine Layout-Vorschau; (2) der Anlege-POST und
	// der Roundtrip tragen keine `channel_layouts`-Attrappe (AN-6, Zweig vergleich).
	const reihenfolgeKarte = page.locator('.cm-desktop [data-testid="weather-metrics-vergleich-reihenfolge"]');
	const layoutHuelle = page.locator('.cm-desktop [data-testid="layout-tab"]').filter({ has: reihenfolgeKarte });
	await expect(layoutHuelle, 'AN-12: der Kanal-Umschalter hängt nicht an der Reihenfolge-Karte').toHaveCount(1);
	await expect(
		layoutHuelle.locator('[data-testid="channel-tab-email"]'),
		'AN-12: Kanal-Umschalter fehlt im Abschnitt Reihenfolge'
	).toHaveCount(1);
	await expect(
		page.locator('.cm-desktop [data-testid="channel-tab-email"]'),
		'AN-12: Kanal-Umschalter außerhalb des Abschnitts Reihenfolge (Attrappe/eigener Kanal-Reiter)'
	).toHaveCount(1);
	await expect(page.locator('[data-testid="compare-editor-tab-layout"]'), 'AN-12: eigener Anlege-Schritt „Layout"').toHaveCount(0);
	await expect(page.locator('[data-testid="compare-editor-tab-versand"]'), 'AN-12: eigener Anlege-Schritt „Versand"').toHaveCount(0);
	await expect(page.locator('[data-testid="compare-step4-layout-preview"]')).toHaveCount(0);

	const maxBox = page.locator('.cm-desktop [data-testid="weather-metrics-vergleich-option-temperature-max"] input').first();
	const minBox = page.locator('.cm-desktop [data-testid="weather-metrics-vergleich-option-temperature-min"] input').first();
	await expect(maxBox).toBeVisible({ timeout: 10_000 });
	await expect(minBox).toBeVisible();
	if (!(await maxBox.isChecked())) await maxBox.click();
	if (!(await minBox.isChecked())) await minBox.click();
	await expect(maxBox).toBeChecked();
	await expect(minBox).toBeChecked();

	const reihenfolge = page.locator('.cm-desktop [data-testid="weather-metrics-vergleich-reihenfolge"]').first();
	const maxZeile = reihenfolge.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temp_max_c"]');
	const minZeile = reihenfolge.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temp_min_c"]');
	await expect(maxZeile).toHaveCount(1);
	await expect(minZeile).toHaveCount(1);
	await expect(maxZeile).toContainText('Maximum');
	await expect(minZeile).toContainText('Minimum');

	// unabhängig: Höchstwert abwählen lässt den Tiefstwert stehen.
	await maxBox.click();
	await expect(maxBox).not.toBeChecked();
	await expect(minBox, 'AN-12: Tiefstwert hängt am Höchstwert').toBeChecked();
	await expect(minZeile).toHaveCount(1);
});
