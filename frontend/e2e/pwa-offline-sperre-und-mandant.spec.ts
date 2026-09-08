// TDD RED — Issue #2131 (Scheibe 4 zu Epic #2127).
// Spec: docs/specs/modules/pwa_offline_ansicht_letzter_stand.md
// Abgedeckt: AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15
// Dazu das Adversary-Finding F005 (sichtbarer Sperr-Zustand am Element und
// Begruendung je Bedien-Gruppe).
//
// Zwei Zusicherungen, die nur zusammen tragen:
//   * Bearbeitungsflaechen sind ohne Netz sichtbar GESPERRT — nicht versteckt
//     (ADR-0034) und nicht scheinbar bedienbar (AC-9/AC-10/AC-11).
//   * Der Gerätespeicher bleibt je Nutzer streng getrennt und wird beim
//     Abmelden vollstaendig geleert (AC-12/AC-13/AC-14/AC-15, ADR-0003).
//
// Alles laeuft ueber echtes Browserverhalten und zwei echte Sitzungen auf
// EINEM Browserprofil — genau die Lage, die die Mandantentrennung bedroht.
//
// Ausfuehrung:
//   cd frontend && npx playwright test --project=pwa e2e/pwa-offline-sperre-und-mandant.spec.ts

import { test, expect, type BrowserContext, type Page } from '@playwright/test';
import * as fs from 'node:fs';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';
import {
	AUTH_STATE,
	activateServiceWorker,
	cacheNamenMitEintrag,
	cacheNames,
	readCacheEntries,
	storageAndRegistrationCount
} from './pwaHelpers.ts';
import { createTestComparePreset, createTestLocation, createTestTrip } from './helpers.ts';

test.use({ serviceWorkers: 'allow' });

test.beforeEach(({ baseURL }) => {
	assertNotProdBaseURL(baseURL ?? '');
});

const ADMIN = {
	username: process.env.E2E_USER ?? 'admin',
	password: process.env.E2E_PASS ?? 'test1234'
};

/** Schreibende Anfragen — genau die, die es offline nicht geben darf. */
const SCHREIBEND = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/** Legt einen Trip mit einer Etappe an — ohne ihn aufzurufen. */
async function tripAnlegen(page: Page): Promise<string> {
	const trip = await createTestTrip(page.request, {
		stages: [
			{
				id: `stage-${Date.now()}`,
				name: 'Etappe',
				date: new Date().toISOString().slice(0, 10),
				waypoints: [{ id: `wp-${Date.now()}`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
			}
		]
	});
	return trip.id;
}

/** Legt einen Trip an und ruft ihn MIT Netz auf, bis er im Speicher liegt. */
async function tripAblegen(page: Page): Promise<string> {
	const trip = { id: await tripAnlegen(page) };
	await page.goto(`/trips/${trip.id}`);
	await page.waitForLoadState('networkidle');
	await expect
		.poll(async () => (await cacheNamenMitEintrag(page, `/trips/${trip.id}`)).length, {
			timeout: 15_000
		})
		.toBeGreaterThan(0);
	return trip.id;
}

/** Meldet den Stamm-Testnutzer in DIESEM Kontext wieder an (Sitzung, nicht Datei). */
async function wiederAnmelden(page: Page): Promise<void> {
	const res = await page.request.post('/api/auth/login', { data: ADMIN });
	expect(res.ok(), `Wiederanmeldung fehlgeschlagen: ${res.status()}`).toBeTruthy();
}

/**
 * Beschafft den ZWEITEN Nutzer und meldet ihn im SELBEN Kontext an.
 *
 * Fester Name statt Zeitstempel: `/api/auth/register` laesst nur 5 Anlagen je
 * Stunde und IP zu (internal/router/router.go:41). Ein neuer Name je Lauf
 * verbraucht dieses Budget, und der Nachweis scheiterte dann an der
 * Anlage-Bremse statt an seiner Zusicherung — ein rotes Ergebnis, das ueber
 * die Mandantentrennung nichts aussagt. Wiederverwendet wird ein Nutzer, der
 * NICHT der Stamm-Testnutzer ist; genau darauf kommt es hier an.
 */
const NUTZER_B = { username: 'e2e2131nutzerb', password: 'test1234' };

async function zweiterNutzerAnmelden(page: Page): Promise<string> {
	const reg = await page.request.post('/api/auth/register', {
		data: { ...NUTZER_B, email: `${NUTZER_B.username}@example.com` }
	});
	// 200/201 = neu angelegt · 409 = liegt aus einem frueheren Lauf vor ·
	// 429 = Anlage-Budget erschoepft. Ueber die Lauffaehigkeit entscheidet in
	// allen drei Faellen erst die Anmeldung unten — sie ist die eigentliche
	// Voraussetzung des Nachweises.
	expect(
		[200, 201, 409, 429],
		`unerwartete Antwort beim Anlegen von B: ${reg.status()}`
	).toContain(reg.status());
	const login = await page.request.post('/api/auth/login', { data: NUTZER_B });
	expect(login.ok(), `Anmeldung B fehlgeschlagen: ${login.status()}`).toBeTruthy();
	return NUTZER_B.username;
}

/** Zeichnet jede schreibende Anfrage des Kontexts auf (auch die des Workers). */
function schreibversucheMitschneiden(context: BrowserContext): string[] {
	const treffer: string[] = [];
	context.on('request', (r) => {
		if (SCHREIBEND.has(r.method())) treffer.push(`${r.method()} ${new URL(r.url()).pathname}`);
	});
	return treffer;
}

// ===========================================================================
// AC-9 — offline sind die Bearbeitungsflaechen sichtbar, aber gesperrt
// ===========================================================================

test('AC-9: die ohne Netz gezeigte Trip-Ansicht sperrt ihre Bearbeitungsflaechen sichtbar und begruendet', async ({
	page,
	context
}) => {
	test.setTimeout(120_000);

	await activateServiceWorker(page);
	const tripId = await tripAblegen(page);

	await context.setOffline(true);
	try {
		await page.goto(`/trips/${tripId}`);
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 15_000 });

		const hinweis = page.getByTestId('offline-sperre-hinweis').first();
		await expect(
			hinweis,
			'die Sperre traegt keine sichtbare Begruendung — gesperrt ohne Grund ist eine kaputte App'
		).toBeVisible();
		expect((await hinweis.innerText()).trim().length, 'die Begruendung ist leer').toBeGreaterThan(10);

		// Die drei schreibenden Bedienelemente der Kopfzeile.
		for (const beschriftung of ['Pausieren', 'Archivieren', 'Test-Briefing senden']) {
			await expect(
				page.getByRole('button', { name: beschriftung }),
				`"${beschriftung}" ist ohne Netz weiterhin sichtbar — richtig (ADR-0034)`
			).toBeVisible();
			await expect(
				page.getByRole('button', { name: beschriftung }),
				`"${beschriftung}" ist ohne Netz bedienbar, obwohl der Schreibweg fehlt`
			).toBeDisabled();
		}

		// Etappen-Tab: die Aktivitaets-Auswahl schreibt sofort per PUT.
		await page.getByTestId('trip-detail-tab-stages').first().click();
		await expect(page.getByTestId('edit-activity-dropdown')).toBeVisible();
		await expect(
			page.getByTestId('edit-activity-dropdown'),
			'die Aktivitaets-Auswahl ist ohne Netz bedienbar'
		).toBeDisabled();

		// Alarm-Tab: dort schreibt JEDES Eingabefeld in die Trip-Konfiguration.
		await page.getByTestId('trip-detail-tab-alarme').first().click();
		const panel = page.getByTestId('trip-detail-panel-alarme');
		await expect(panel).toBeVisible();
		const bedienbar = panel.locator(
			'input:not([disabled]), select:not([disabled]), textarea:not([disabled])'
		);
		expect(
			await bedienbar.count(),
			'im Alarm-Tab sind Eingabefelder ohne Netz weiterhin bedienbar — ' +
				'das Sperr-Inventar dieser Route ist unvollstaendig (Spec, Abschnitt H)'
		).toBe(0);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// Adversary-Finding F005 — die Sperre muss AM Element sichtbar sein
//
// Der AC-9-Nachweis oben misst das DOM-Attribut `disabled` und den einen
// Balken oben. Live gemessen waren zwar alle 60 Schaltflaechen des Alarm-Tabs
// gesperrt, ihr berechneter Stil aber identisch zum bedienbaren Zustand
// (`cursor: pointer`, keine Abdunklung) — das Autoren-CSS der Bausteine setzt
// `cursor: pointer` ohne jede `:disabled`-Praezisierung und schlaegt damit die
// Voreinstellung des Browsers. Gemessen wird deshalb der BERECHNETE Stil, und
// zwar gegen denselben Knopf im bedienbaren Zustand.
// ===========================================================================

interface Sperrbild {
	gefunden: boolean;
	gesperrt: boolean;
	cursor: string;
	hintergrund: string;
	grundText: string;
	grundSichtbar: boolean;
	abstand: number;
}

/** Liest den sichtbaren Sperr-Zustand und die Begruendung der Bedien-Gruppe. */
async function sperrbild(page: Page, auswahl: string): Promise<Sperrbild> {
	return page.evaluate((sel) => {
		const leer: Sperrbild = {
			gefunden: false,
			gesperrt: false,
			cursor: '',
			hintergrund: '',
			grundText: '',
			grundSichtbar: false,
			abstand: -1
		};
		const el = document.querySelector(sel);
		if (!el) return leer;
		const stil = getComputedStyle(el);
		const gruppe = el.closest('[data-gz-sperr-gruppe]');
		const grund = gruppe?.querySelector(':scope > [data-gz-offline-grund]') ?? null;
		const r = el.getBoundingClientRect();
		const g = grund?.getBoundingClientRect();
		return {
			gefunden: true,
			gesperrt: el.hasAttribute('data-gz-offline-gesperrt'),
			cursor: stil.cursor,
			hintergrund: stil.backgroundImage,
			grundText: (grund?.textContent ?? '').trim(),
			grundSichtbar: !!g && g.height > 0 && g.width > 0,
			abstand: g ? Math.abs(g.top - r.bottom) : -1
		};
	}, auswahl);
}

/** Oeffnet den Alarm-Reiter der Trip-Ansicht. */
async function alarmReiterOeffnen(page: Page): Promise<void> {
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	await page.getByTestId('trip-detail-tab-alarme').first().click();
	await expect(page.getByTestId('trip-detail-panel-alarme')).toBeVisible();
	await expect(page.locator('[data-testid^="alert-level-"]').first()).toBeVisible();
}

/**
 * Drei Bedienelemente aus drei verschiedenen Bedien-Gruppen: Metrik-Zeile und
 * Quickset-Leiste (die ~56 Schaltflaechen aus dem Finding) sowie die Kopfzeile
 * der Ansicht — damit der Nachweis nicht an einer einzelnen Stelle haengt.
 */
const SPERR_PROBEN = [
	'[data-testid^="alert-level-"]',
	'[data-testid^="alert-quickset-"]',
	'[data-testid="test-briefing-menu-toggle"]'
];

test('F005: gesperrte Bedienelemente sind sichtbar gesperrt und ihre Gruppe traegt die Begruendung', async ({
	page,
	context
}) => {
	test.setTimeout(120_000);

	await activateServiceWorker(page);
	const tripId = await tripAblegen(page);

	// Messgrundlage zuerst: derselbe Knopf MIT Netz. Ohne diesen Vergleich
	// bewiese der Nachweis unten nur, dass irgendein Stil anliegt — nicht, dass
	// gesperrt und bedienbar auseinanderzuhalten sind.
	await page.goto(`/trips/${tripId}`);
	await alarmReiterOeffnen(page);
	const bedienbar = await sperrbild(page, SPERR_PROBEN[0]);
	expect(bedienbar.gefunden, 'kein Empfindlichkeits-Knopf im Alarm-Reiter gefunden').toBe(true);
	expect(bedienbar.gesperrt, 'der Knopf ist MIT Netz gesperrt — die Messgrundlage taugt nicht').toBe(
		false
	);
	expect(bedienbar.grundText, 'mit Netz steht eine Sperr-Begruendung an der Gruppe').toBe('');

	await context.setOffline(true);
	try {
		await page.goto(`/trips/${tripId}`);
		await alarmReiterOeffnen(page);

		for (const auswahl of SPERR_PROBEN) {
			const bild = await sperrbild(page, auswahl);
			expect(bild.gefunden, `kein Bedienelement fuer "${auswahl}"`).toBe(true);
			expect(bild.gesperrt, `"${auswahl}" ist ohne Netz nicht gesperrt`).toBe(true);

			expect(
				bild.cursor,
				`"${auswahl}" zeigt ohne Netz den Zeiger "${bild.cursor}" — wie im bedienbaren Zustand "${bedienbar.cursor}"`
			).toBe('not-allowed');
			expect(
				bild.cursor,
				'gesperrt und bedienbar sehen gleich aus'
			).not.toBe(bedienbar.cursor);
			expect(
				bild.hintergrund,
				`"${auswahl}" traegt ohne Netz kein sichtbares Sperr-Merkmal (Hintergrund "${bild.hintergrund}")`
			).not.toBe(bedienbar.hintergrund);

			// AC-9 „jeweils": die Begruendung steht AN der Bedien-Gruppe des
			// Elements, nicht nur einmal ganz oben ausser Sicht.
			expect(
				bild.grundText.length,
				`die Bedien-Gruppe von "${auswahl}" traegt keine Begruendung — der Balken oben ist beim Blick auf dieses Element laengst weggescrollt`
			).toBeGreaterThan(10);
			expect(bild.grundSichtbar, `die Begruendung an "${auswahl}" ist nicht sichtbar`).toBe(true);
			expect(
				bild.abstand,
				`die Begruendung liegt ${Math.round(bild.abstand)}px von "${auswahl}" entfernt — nicht mehr im selben Blick`
			).toBeLessThan(400);
		}
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-10 — ein Bedienversuch loest keinen Schreibvorgang aus
// ===========================================================================

test('AC-10: der Bedienversuch an einer gesperrten Flaeche schickt keine schreibende Anfrage', async ({
	page,
	context
}) => {
	test.setTimeout(120_000);

	await activateServiceWorker(page);
	const tripId = await tripAblegen(page);

	// Positivkontrolle ZUERST, mit Netz: dasselbe Antippen MUSS hier schreiben.
	// Ohne sie waere der Nachweis unten auch dann gruen, wenn das Bedienelement
	// gar nicht mehr existiert oder ueberhaupt nie geschrieben haette.
	const mitNetz = schreibversucheMitschneiden(context);
	await page.getByRole('button', { name: 'Pausieren' }).click();
	await expect
		.poll(() => mitNetz.length, { timeout: 15_000 })
		.toBeGreaterThan(0);
	context.removeAllListeners('request');

	await context.setOffline(true);
	try {
		await page.goto(`/trips/${tripId}`);
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 15_000 });

		const ohneNetz = schreibversucheMitschneiden(context);

		// `force`: der Nutzer tippt trotzdem. Genau dieser Versuch darf nichts
		// ausloesen — der Nachweis umgeht deshalb bewusst die Bedienbarkeits-
		// pruefung von Playwright.
		for (const beschriftung of ['Pausieren', 'Archivieren', 'Test-Briefing senden']) {
			await page.getByRole('button', { name: beschriftung }).click({ force: true });
		}
		await page.getByTestId('trip-detail-tab-stages').first().click();
		await page
			.getByTestId('edit-activity-dropdown')
			.selectOption('skitour', { force: true })
			.catch(() => {
				// Ein gesperrtes Auswahlfeld nimmt gar keinen Wert an — das ist der
				// erwuenschte Ausgang, kein Befund.
			});
		await page.waitForTimeout(3_000);

		expect(
			ohneNetz,
			'ein Bedienversuch an einer gesperrten Flaeche hat einen Schreibvorgang ausgeloest'
		).toEqual([]);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-11 — Netzverlust an der LIVE geladenen Seite sperrt ohne Bedienversuch
// ===========================================================================

test('AC-11: faellt das Netz an der live geladenen Ansicht weg, sperrt sie ohne vorherigen Bedienversuch', async ({
	page,
	context
}) => {
	test.setTimeout(120_000);

	await activateServiceWorker(page);
	// BEWUSST ohne Ablage im Gerätespeicher: dieser Nachweis gilt der LIVE
	// geladenen Seite. Haenge er an der Ablage, koennte er seine eigene
	// Zusicherung gar nicht erreichen, solange die Ablage noch fehlt.
	const tripId = await tripAnlegen(page);

	await page.goto(`/trips/${tripId}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	// Ausgangslage: bedienbar. Ohne diese Messung waere der Nachweis unten auch
	// von einer Seite erfuellt, die von vornherein alles sperrt.
	await expect(page.getByRole('button', { name: 'Pausieren' })).toBeEnabled();
	await expect(page.getByTestId('offline-sperre-hinweis')).toHaveCount(0);

	const schreibversuche = schreibversucheMitschneiden(context);

	// KEIN Neuladen, KEIN Bedienversuch — nur das Netz faellt weg.
	await context.setOffline(true);
	try {
		await expect(
			page.getByRole('button', { name: 'Pausieren' }),
			'die live geladene Ansicht bleibt nach dem Netzverlust bedienbar'
		).toBeDisabled({ timeout: 15_000 });
		await expect(
			page.getByTestId('offline-sperre-hinweis').first(),
			'die Sperre erscheint ohne sichtbare Begruendung'
		).toBeVisible();

		expect(
			schreibversuche,
			'die Sperre entstand erst durch einen fehlgeschlagenen Schreibversuch — ' +
				'genau dieser Versuch darf nach AC-10 nicht ins Leere laufen'
		).toEqual([]);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-13 — ohne Mandantenkennung wird nicht abgelegt (fail-closed)
// ===========================================================================

test('AC-13: fehlt der Mandanten-Header, legt der Worker die Antwort nicht ab', async ({
	page,
	context
}) => {
	test.setTimeout(120_000);

	await activateServiceWorker(page);

	// Positivkontrolle im selben Lauf: derselbe Weg MIT Kopfzeilen legt ab.
	const mitKennung = await tripAblegen(page);
	expect(
		await cacheNamenMitEintrag(page, `/trips/${mitKennung}`),
		'schon der ungestoerte Weg legt nichts ab — der Nachweis unten pruefte nichts'
	).not.toEqual([]);

	const trip = await createTestTrip(page.request, {});
	// Die Antwort wird durchgereicht, aber OHNE ihre Kopfzeilen neu gestellt.
	// Bewusst ohne den Header beim Namen zu nennen: ein Nachweis, der ihn
	// nennt, prueft die Benennung; dieser prueft die Zusicherung „ohne Kennung
	// keine Ablage" — gleich, wie die Kennung heisst.
	await context.route(`**/trips/${trip.id}`, async (route) => {
		const antwort = await route.fetch();
		await route.fulfill({
			status: antwort.status(),
			contentType: 'text/html; charset=utf-8',
			body: await antwort.text()
		});
	});
	try {
		await page.goto(`/trips/${trip.id}`);
		await page.waitForLoadState('networkidle');
		await page.waitForTimeout(3_000);

		expect(
			await cacheNamenMitEintrag(page, `/trips/${trip.id}`),
			'eine Antwort ohne Mandantenkennung wurde abgelegt — sie liesse sich keinem ' +
				'Nutzer zuordnen und der naechste saehe sie (ADR-0003)'
		).toEqual([]);
	} finally {
		await context.unroute(`**/trips/${trip.id}`);
	}
});

// ===========================================================================
// AC-14 — der Nutzerwechsel OHNE Abmelden raeumt beim ersten Online-Abruf
// ===========================================================================

test('AC-14: meldet sich B ohne As Abmeldung an, faellt As Speicherbereich beim ersten Abruf', async ({
	page
}) => {
	test.setTimeout(120_000);

	await activateServiceWorker(page);
	const tripA = await tripAblegen(page);
	const speicherA = await cacheNamenMitEintrag(page, `/trips/${tripA}`);
	expect(speicherA.length, 'As Ansicht liegt gar nicht im Speicher').toBeGreaterThan(0);

	// Nutzerwechsel OHNE Abmelde-Vorgang: nur die Sitzung wechselt, der
	// Gerätespeicher bleibt zunaechst liegen — genau die gefaehrliche Lage.
	await zweiterNutzerAnmelden(page);
	expect(
		await cacheNames(page),
		'Aufbau misslungen: As Bereich ist schon vor Bs erstem Abruf fort'
	).toEqual(expect.arrayContaining(speicherA));

	// Bs erster Online-Abruf einer Trip-Ansicht.
	const tripB = await tripAblegen(page);
	expect(
		await cacheNamenMitEintrag(page, `/trips/${tripB}`),
		'Bs eigene Ansicht wurde nicht abgelegt'
	).not.toEqual([]);

	const jetzt = await cacheNames(page);
	for (const name of speicherA) {
		expect(
			jetzt,
			`As Speicherbereich "${name}" liegt nach Bs erstem Abruf noch da — ` +
				'B koennte fremde Inhalte sehen (ADR-0003)'
		).not.toContain(name);
	}
	expect(
		(await readCacheEntries(page)).map((e) => new URL(e.url).pathname),
		'As Ansicht ist weiterhin abgelegt'
	).not.toContain(`/trips/${tripA}`);
});

// ===========================================================================
// AC-12 — nach ordnungsgemaessem Abmelden sieht B nichts von A
// ===========================================================================
//
// Ab hier melden die Nachweise den Stamm-Testnutzer wirklich ab. Sie stehen
// deshalb am Ende der Datei, und jeder von ihnen meldet ihn vorher neu an —
// die abgelegte Anmeldung in playwright/.auth/admin.json traegt zwar noch das
// Cookie, die Sitzung dahinter ist nach dem ersten Abmelden aber fort.

test('AC-12: nach As Abmeldung sieht der angemeldete B ohne Netz keinen Inhalt von A', async ({
	page,
	context
}) => {
	test.setTimeout(180_000);

	await wiederAnmelden(page);
	await activateServiceWorker(page);
	const tripA = await tripAblegen(page);
	const ort = await createTestLocation(page.request, {});
	const presetA = await createTestComparePreset(page.request, { locationIds: [ort.id] });
	await page.goto(`/compare/${presetA.id}`);
	await page.waitForLoadState('networkidle');

	// Ordnungsgemaess abmelden — ueber die Seitenleiste.
	const sidebar = page.getByTestId('desktop-sidebar');
	await sidebar.locator('button').last().click();
	await sidebar.locator('form[action="/logout"] button[type="submit"]').click();
	await page.waitForURL(/\/login/);

	await zweiterNutzerAnmelden(page);
	await activateServiceWorker(page);
	const tripB = await tripAblegen(page);

	await context.setOffline(true);
	try {
		await page.goto(`/trips/${tripA}`);
		await expect(
			page.getByTestId('offline-uebersicht'),
			'B bekommt As Ansicht aus dem Gerätespeicher statt der Offline-Uebersicht'
		).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('trip-detail-tab-list')).toHaveCount(0);

		const gelistet = await page
			.getByTestId('offline-uebersicht-eintrag')
			.evaluateAll((els) => els.map((e) => e.querySelector('a')?.getAttribute('href') ?? ''));
		expect(gelistet, 'die Uebersicht bietet B As Ansicht an').not.toContain(`/trips/${tripA}`);
		expect(gelistet, 'Bs eigene Ansicht fehlt — geraeumt wurde zu viel').toContain(
			`/trips/${tripB}`
		);
	} finally {
		await context.setOffline(false);
	}

	expect(
		await cacheNamenMitEintrag(page, `/trips/${tripA}`),
		'As Ansicht liegt nach seiner Abmeldung noch im Gerätespeicher'
	).toEqual([]);
});

// ===========================================================================
// AC-15 — beide Abmelde-Wege leeren AUCH den Inhaltsspeicher
// ===========================================================================

test('AC-15: Abmelden ueber die Seitenleiste leert auch den Inhaltsspeicher', async ({ page }) => {
	test.setTimeout(120_000);

	await wiederAnmelden(page);
	await activateServiceWorker(page);
	const tripId = await tripAblegen(page);
	expect(
		await cacheNamenMitEintrag(page, `/trips/${tripId}`),
		'kein Inhaltsspeicher aufgebaut — es gaebe nichts zu leeren'
	).not.toEqual([]);

	const sidebar = page.getByTestId('desktop-sidebar');
	await sidebar.locator('button').last().click();
	await sidebar.locator('form[action="/logout"] button[type="submit"]').click();
	await page.waitForURL(/\/login/);

	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

test('AC-15: "Auf allen Geraeten abmelden" leert auch den Inhaltsspeicher', async ({ page }) => {
	test.setTimeout(120_000);

	await wiederAnmelden(page);
	await activateServiceWorker(page);
	const tripId = await tripAblegen(page);
	expect(await cacheNamenMitEintrag(page, `/trips/${tripId}`)).not.toEqual([]);

	await page.goto('/account');
	await page.getByRole('button', { name: 'Auf allen Geräten abmelden' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Abmelden', exact: true }).click();
	await page.waitForURL(/\/login/);

	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

// Die Abmelde-Nachweise beenden AUCH die Anmeldung, die global.setup.ts in
// playwright/.auth/admin.json abgelegt hat. Ohne Reparatur liefen alle spaeter
// startenden Specs in den Auth-Guard. `baseURL` ist test-scoped und in afterAll
// nicht verfuegbar — darum derselbe lokale Vorschau-Port wie in der Config.
const LOKALE_BASIS = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:4173';

test.afterAll(async ({ browser }) => {
	if (!fs.existsSync(AUTH_STATE)) return;
	assertNotProdBaseURL(LOKALE_BASIS);
	const context = await browser.newContext({ baseURL: LOKALE_BASIS, serviceWorkers: 'block' });
	try {
		const page = await context.newPage();
		await page.goto('/login');
		await page.fill('input[name="username"]', ADMIN.username);
		await page.fill('input[name="password"]', ADMIN.password);
		await page.click('button[type="submit"]');
		await page.waitForURL('/');
		await context.storageState({ path: AUTH_STATE });
	} finally {
		await context.close();
	}
});
