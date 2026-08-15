// Issue #1680 Scheibe 5b — AC-12 / AC-13: Herkunft der Gewitterstufe in der
// Gewitter-Vorschau, abgelesen im ECHTEN Browser auf der Vorschau-Flaeche
// `/trips/<id>?tab=preview` (Bildschirm-Nachweis, nicht Zwischendatei).
// Spec: docs/specs/modules/feat_1680_s5b_gewitter_herkunft_vorschau.md
//
// Warum ein eigener Spec (Spec, Risiko 1b): kein einziges Bestands-Spec oeffnet
// diese Flaeche und liest den iframe-Inhalt; `email-preview-header.spec.ts`
// haengt an der Dev-Route mit Mock-Daten und rendert nur den Kopfbereich.
// Das Renderer-Gate #811 schweigt hier strukturell (plain.py/html.py werden in
// dieser Scheibe nicht angefasst) — dieser Spec ist der Ersatz dafuer.
//
// LAEUFT GEGEN STAGING. Der Spec ist config-frei: baseURL, nginx-Schranke und
// storageState setzt er selbst per `test.use`, damit kein zusaetzliches
// Config-/Setup-Paar noetig ist. Aufruf:
//     cd frontend/e2e && npx playwright test trip-preview-thunder-origin.staging.spec.ts --reporter=line
//
// 🔴 GEHOERT NICHT IN `.github/ci_e2e_specs.txt` — und das ist kein Versaeumnis,
// sondern gemessen: Die Vermessung lief am 2026-08-15 mit 3 von 3 gruen
// (1,7 min / 17,6 s / 17,5 s). Aufgenommen wuerde er trotzdem scheitern, denn
// die `e2e`-Lane faehrt einen ISOLIERTEN OFFLINE-STACK (`ci-stack.sh start`),
// waehrend dieser Spec Staging braucht: GZ_VALIDATOR_* (nginx), GZ_AUTH_* aus
// der Staging-.env und eine storageState-Datei. Nichts davon existiert in der CI.
//
// Das Suffix `.staging.` ist deshalb ein WAECHTER, keine Kosmetik: Der
// Vermessungslauf schliesst genau dieses Muster aus (ci.yml:277,
// `--exclude='*.staging.spec.ts'`). Der zweite Filter (ci.yml:280, sucht
// `__dirname` oder absolute Pfade) greift hier NICHT — dieses Modul loest sein
// Verzeichnis ueber `fileURLToPath(import.meta.url)` auf. Ohne das Suffix waere
// der Spec beim naechsten Vermessungslauf still aufgenommen worden und haette
// die Ampel fuer alle rot gefaerbt.
//
// Drei Zugangsschichten, nicht verwechseln (CLAUDE.md):
//   nginx-Schranke  -> GZ_VALIDATOR_USER/PASS  (aus .claude/validator.env)
//   App-Anmeldung   -> GZ_AUTH_USER/PASS       (aus dem STAGING-.env,
//                      anderes Passwort als die .env des Arbeitsordners!)
import { test, expect, type FrameLocator, type Page, type PlaywrightWorkerArgs } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// gitignored (.gitignore: frontend/e2e/playwright/) — Session-Token gehoert
// NIE nach /tmp (henemm-security #199).
const AUTH_FILE = path.join(HERE, 'playwright/.auth/staging-1680-s5b.json');

const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
const TRIP_ID = 'e2e-1680-s5b-origin';
// Bewusst OHNE die Woerter "Gewitter"/"Vorschau" im Namen: der Trip-Name steht
// im Mail-Kopf, ein Treffer dort wuerde die Block-Suche verfaelschen.
const TRIP_NAME = 'E2E 1680 S5b Herkunft';

// Die vier Fusions-Zutaten (src/output/metric_format.py THUNDER_SIGNAL_LABEL_DE).
const ZUTAT = '(?:Wettercode|Blitzdichte|CAPE|Blitzpotenzial)';
// Herkunft steht unmittelbar hinter der Tagesaussage, Trenner " · ",
// mehrere Zutaten mit ", " verbunden (Spec, Abschnitt "Wortlaut").
const HERKUNFT_AM_TAGESTEIL = new RegExp(`· ${ZUTAT}(?:, ${ZUTAT})*$`);

const VALIDATOR = {
	username: process.env.GZ_VALIDATOR_USER ?? '',
	password: process.env.GZ_VALIDATOR_PASS ?? ''
};

test.use({
	baseURL: BASE,
	ignoreHTTPSErrors: true,
	httpCredentials: VALIDATOR,
	storageState: AUTH_FILE
});

/** Vollstaendige report_config — der Editor schreibt sie immer als Ganzes. */
function reportConfig(showOutlook: boolean) {
	return {
		enabled: true,
		send_email: true,
		email_format: 'full',
		multi_day_trend_reports: ['evening'],
		show_outlook: showOutlook
	};
}

test.beforeAll(async ({ playwright }) => {
	test.setTimeout(600_000);
	assertNotProdBaseURL(BASE);
	const appUser = process.env.GZ_AUTH_USER;
	const appPass = process.env.GZ_AUTH_PASS;
	expect(appUser, 'GZ_AUTH_USER fehlt (Staging-.env)').toBeTruthy();
	expect(VALIDATOR.username, 'GZ_VALIDATOR_USER fehlt (.claude/validator.env)').toBeTruthy();

	// `test.use({ storageState })` wirkt auch auf hier erzeugte Kontexte —
	// ohne Platzhalter scheitert schon der Anmelde-Kontext mit ENOENT.
	fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
	if (!fs.existsSync(AUTH_FILE)) {
		fs.writeFileSync(AUTH_FILE, JSON.stringify({ cookies: [], origins: [] }), { mode: 0o600 });
	}

	const ctx = await playwright.request.newContext({
		baseURL: BASE,
		ignoreHTTPSErrors: true,
		httpCredentials: VALIDATOR
	});
	const login = await ctx.post('/api/auth/login', { data: { username: appUser, password: appPass } });
	expect(login.ok(), `App-Anmeldung HTTP ${login.status()} — Passwort aus dem STAGING-.env?`).toBeTruthy();

	// Seed: drei aufeinanderfolgende KUENFTIGE Etappen. Ohne sie entsteht gar
	// keine Vorschau — `_build_thunder_forecast_from_trend_or_fetch()` baut
	// "+1"/"+2" nur fuer Tage, an denen eine Etappe liegt.
	const iso = (plusDays: number) => new Date(Date.now() + plusDays * 86_400_000).toISOString().slice(0, 10);
	const stages = [1, 2, 3].map((i) => ({
		id: `e2e-1680-s5b-stage-${i}`,
		name: `Etappe ${i}`,
		date: iso(i),
		waypoints: [
			{ id: `e2e-1680-s5b-wp-${i}-1`, name: 'Start', lat: 47.2692, lon: 11.4041, elevation_m: 574 },
			{ id: `e2e-1680-s5b-wp-${i}-2`, name: 'Ziel', lat: 47.2802, lon: 11.3907, elevation_m: 830 }
		]
	}));
	await ctx.delete(`/api/trips/${TRIP_ID}`);
	const created = await ctx.post('/api/trips', {
		data: { id: TRIP_ID, name: TRIP_NAME, region: 'Tirol', stages, report_config: reportConfig(true) }
	});
	expect(created.ok(), `Seed-Trip HTTP ${created.status()}`).toBeTruthy();

	// Warmlauf: der Go-Proxy bricht die Vorschau nach 30 s ab
	// (internal/handler/preview_proxy.go:81), ein kalter Wetterabruf ueber drei
	// Segmente dauert laenger und endet in 502. Erst nach dem Warmlauf ist die
	// Flaeche im Browser innerhalb der Frist bedienbar.
	for (const type of ['morning', 'evening']) {
		for (let attempt = 1; attempt <= 8; attempt++) {
			const res = await ctx.get(`/api/preview/${TRIP_ID}/email?type=${type}`, { timeout: 120_000 });
			if (res.ok()) break;
			expect(attempt, `Vorschau (${type}) bleibt nach ${attempt} Versuchen HTTP ${res.status()}`).toBeLessThan(8);
		}
	}

	await ctx.storageState({ path: AUTH_FILE });
	fs.chmodSync(AUTH_FILE, 0o600);
	await ctx.dispose();
});

/** Setzt show_outlook ueber die API (die "Given"-Haelfte von AC-13). */
async function setOutlook(playwright: PlaywrightWorkerArgs['playwright'], showOutlook: boolean) {
	const ctx = await playwright.request.newContext({
		baseURL: BASE,
		ignoreHTTPSErrors: true,
		httpCredentials: VALIDATOR,
		storageState: AUTH_FILE
	});
	const res = await ctx.put(`/api/trips/${TRIP_ID}`, { data: { report_config: reportConfig(showOutlook) } });
	expect(res.ok(), `show_outlook=${showOutlook} setzen HTTP ${res.status()}`).toBeTruthy();
	await ctx.dispose();
}

/**
 * Oeffnet die Vorschau-Flaeche, schaltet den Demo-Modus ab (TripTabs startet
 * mit Fixture-Daten, #483) und waehlt Morgen/Abend. Liefert den iframe-Rahmen,
 * sobald die ECHTE (demo-freie) Antwort fuer genau diese Ansicht da ist.
 */
async function openPreview(page: Page, type: 'morning' | 'evening'): Promise<FrameLocator> {
	await page.goto(`/trips/${TRIP_ID}?tab=preview`, { waitUntil: 'domcontentloaded' });
	await expect(page.getByTestId('trip-detail-panel-preview')).toBeVisible({ timeout: 30_000 });

	// Erwartete Antwort VOR den Klicks registrieren — sonst Rennen.
	const echteAntwort = page.waitForResponse(
		(r) =>
			r.url().includes(`/api/preview/${TRIP_ID}/email`) &&
			r.url().includes(`type=${type}`) &&
			!r.url().includes('demo=1'),
		{ timeout: 120_000 }
	);

	const demoAus = page.getByTestId('preview-demo-disable');
	if (await demoAus.count()) await demoAus.click();
	await page
		.getByTestId('preview-controls')
		.locator(`input[type="radio"][value="${type}"]`)
		.check();

	const res = await echteAntwort;
	expect(res.status(), `Vorschau-Abruf (${type}) HTTP ${res.status()}`).toBe(200);
	await expect(page.getByTestId('email-iframe')).toBeVisible({ timeout: 30_000 });
	return page.frameLocator('[data-testid="email-iframe"]');
}

// Geschuetztes Leerzeichen auf ein normales abbilden, damit die Pruefung des
// Trenners " · " nicht an der Schreibweise scheitert.
const norm = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim();

/** Die Zeilen des Blocks "⚡ Gewitter-Vorschau" (leer, wenn es ihn nicht gibt). */
async function vorschauZeilen(frame: FrameLocator): Promise<string[]> {
	const li = frame.locator('xpath=//h3[contains(., "Gewitter-Vorschau")]/following-sibling::ul[1]/li');
	return (await li.allInnerTexts()).map(norm);
}

/**
 * Der Tagesteil einer Vorschau-Zeile: ohne Datum/Blitz-Symbol, ohne
 * Nacht-Halbsatz (der beginnt stets mit ", nachts") und ohne den vom Renderer
 * angehaengten Hagel-Zusatz. Genau hinter diesem Teil muss die Herkunft stehen.
 */
function tagesteil(zeile: string): string {
	let t = zeile.replace(/^\d{2}\.\d{2}\.\d{4}:\s*/, '').replace(/^⚡\s*/, '');
	const nacht = t.indexOf(', nachts');
	if (nacht >= 0) t = t.slice(0, nacht);
	return t.replace(/\s·\sHagel:.*$/, '').trim();
}

test('vorschau_morgen_zeigt_herkunft (AC-12)', async ({ page, playwright }) => {
	test.setTimeout(300_000);
	await setOutlook(playwright, true); // Standard-Konfiguration
	const frame = await openPreview(page, 'morning');

	const zeilen = await vorschauZeilen(frame);
	expect(zeilen.length, 'Kein "Gewitter-Vorschau"-Block in der Morgen-Ansicht').toBeGreaterThan(0);

	const mitStufe = zeilen.filter((z) => !z.includes('Kein Gewitter erwartet'));
	// Anti-Vakuum: ohne Gewitterstufe waere die Zeile korrekt OHNE Herkunft —
	// der Test wuerde nichts messen. Dann muss er scheitern, nicht bestehen.
	expect(
		mitStufe.length,
		`Kein Vorschau-Tag traegt heute eine Gewitterstufe (${JSON.stringify(zeilen)}) — ` +
			'der Nachweis liefe ins Leere. Anderen Trip/andere Koordinaten waehlen.'
	).toBeGreaterThan(0);

	for (const zeile of mitStufe) {
		expect(tagesteil(zeile), `Herkunft fehlt in: "${zeile}"`).toMatch(HERKUNFT_AM_TAGESTEIL);
	}
});

test('vorschau_abend_ohne_ausblick_zeigt_herkunft (AC-13)', async ({ page, playwright }) => {
	test.setTimeout(300_000);
	await setOutlook(playwright, false); // Ausblick aus -> Primaerpfad (Trend-Zeile)
	const frame = await openPreview(page, 'evening');

	const zeilen = await vorschauZeilen(frame);
	expect(
		zeilen.length,
		'Kein "Gewitter-Vorschau"-Block in der Abend-Ansicht bei abgeschaltetem Ausblick'
	).toBeGreaterThan(0);

	const mitStufe = zeilen.filter((z) => !z.includes('Kein Gewitter erwartet'));
	expect(
		mitStufe.length,
		`Kein Vorschau-Tag traegt heute eine Gewitterstufe (${JSON.stringify(zeilen)}) — ` +
			'der Nachweis liefe ins Leere. Anderen Trip/andere Koordinaten waehlen.'
	).toBeGreaterThan(0);

	for (const zeile of mitStufe) {
		expect(tagesteil(zeile), `Herkunft fehlt in: "${zeile}"`).toMatch(HERKUNFT_AM_TAGESTEIL);
	}
});

test('mit_ausblick_verschwindet_der_block (AC-13 Gegenprobe)', async ({ page, playwright }) => {
	test.setTimeout(300_000);
	await setOutlook(playwright, true); // Ausblick an -> Vorschau unterdrueckt (#1313)
	const frame = await openPreview(page, 'evening');

	// 1. Der Block ist gar nicht da.
	expect(
		await vorschauZeilen(frame),
		'Bei eingeschaltetem Ausblick darf es keinen "Gewitter-Vorschau"-Block geben'
	).toEqual([]);

	// 2. Stattdessen steht die Ausblick-Tabelle da — Beleg, dass die Flaeche
	//    reagiert und der Nachweis oben nicht ins Leere lief.
	const ausblick = frame.locator(
		'xpath=//span[contains(., "Ausblick") and contains(., "3 Tage")]/../following-sibling::table[1]'
	);
	await expect(ausblick).toBeVisible({ timeout: 30_000 });

	// 3. Und dort traegt die Gewitterstufe ihre Herkunft (S5a, bereits live).
	const tabelle = norm(await ausblick.innerText());
	if (/\b(leicht|mittel|hoch)\s*@\s*\d/.test(tabelle)) {
		expect(tabelle, `Ausblick-Tabelle ohne Herkunft: "${tabelle}"`).toMatch(new RegExp(`· ${ZUTAT}`));
	}
});
