// Issue #2049 — AC-14: der bisherige Bestandstest
// (`epic-138-metriken-editor.spec.ts`, AC-5b) prueft nur, dass der PUT das
// neue Feld `display_config.outlook_metric_formats` traegt und dass der
// Schalter selbst seinen `data-active`-Zustand wechselt — beides reine
// Frontend-Eigenschaften. Er koennte GRUEN bleiben, auch wenn der Backend-
// Zweig in `format_outlook_value()` nie greift. Dieser Spec schliesst genau
// diese Luecke: er klickt "Einfach" tatsaechlich und liest die WIRKUNG an der
// ECHT gerenderten Ausblick-Zelle auf der Vorschau-Flaeche
// `/trips/<id>?tab=preview` (Bildschirm-Nachweis, nicht Zwischendatei).
// Spec: docs/specs/modules/fix_2049_ausblick_darstellungsform.md, AC-14
//
// LAEUFT GEGEN STAGING. Der Spec ist config-frei: baseURL, nginx-Schranke und
// storageState setzt er selbst per `test.use`, damit kein zusaetzliches
// Config-/Setup-Paar noetig ist (Bauart 1:1 aus
// trip-preview-thunder-origin.staging.spec.ts uebernommen). Aufruf:
//     cd frontend/e2e && npx playwright test ausblick-einfach-wirkt.staging.spec.ts --reporter=line
//
// 🔴 GEHOERT NICHT IN `.github/ci_e2e_specs.txt` — und das ist kein
// Versaeumnis, sondern Absicht: die `e2e`-Lane faehrt einen ISOLIERTEN
// OFFLINE-STACK (`ci-stack.sh start`), waehrend dieser Spec Staging braucht:
// GZ_VALIDATOR_* (nginx), GZ_AUTH_* aus der Staging-.env und eine
// storageState-Datei. Nichts davon existiert in der CI.
//
// Das Suffix `.staging.` ist deshalb ein WAECHTER, keine Kosmetik: Der
// Vermessungslauf schliesst genau dieses Muster aus (ci.yml:277,
// `--exclude='*.staging.spec.ts'`). Der zweite Filter (ci.yml:280, sucht
// `__dirname` oder absolute Pfade) greift hier NICHT — dieses Modul loest sein
// Verzeichnis ueber `fileURLToPath(import.meta.url)` auf. Ohne das Suffix
// waere der Spec beim naechsten Vermessungslauf still aufgenommen worden und
// haette die Ampel fuer alle rot gefaerbt.
//
// Drei Zugangsschichten, nicht verwechseln (CLAUDE.md):
//   nginx-Schranke  -> GZ_VALIDATOR_USER/PASS  (aus .claude/validator.env)
//   App-Anmeldung   -> GZ_AUTH_USER/PASS       (aus dem STAGING-.env,
//                      anderes Passwort als die .env des Arbeitsordners!)
import { test, expect, type FrameLocator, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// gitignored (.gitignore: frontend/e2e/playwright/) — Session-Token gehoert
// NIE nach /tmp (henemm-security #199).
const AUTH_FILE = path.join(HERE, 'playwright/.auth/staging-2049-ausblick.json');

const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
const TRIP_ID = 'e2e-2049-ausblick-einfach';
const TRIP_NAME = 'E2E 2049 Ausblick Einfach';

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

	// Seed: drei aufeinanderfolgende KUENFTIGE Etappen (dieselbe Koordinate wie
	// die Vorlage) — ohne sie entsteht gar kein Ausblick, `show_outlook`
	// braucht ein Tagesfenster, in dem tatsaechlich eine Etappe liegt.
	const iso = (plusDays: number) => new Date(Date.now() + plusDays * 86_400_000).toISOString().slice(0, 10);
	const stages = [1, 2, 3].map((i) => ({
		id: `e2e-2049-ausblick-stage-${i}`,
		name: `Etappe ${i}`,
		date: iso(i),
		waypoints: [
			{ id: `e2e-2049-ausblick-wp-${i}-1`, name: 'Start', lat: 47.2692, lon: 11.4041, elevation_m: 574 },
			{ id: `e2e-2049-ausblick-wp-${i}-2`, name: 'Ziel', lat: 47.2802, lon: 11.3907, elevation_m: 830 }
		]
	}));
	await ctx.delete(`/api/trips/${TRIP_ID}`);
	const created = await ctx.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: TRIP_NAME,
			region: 'Tirol',
			stages,
			// `gust` traegt Rang 3 der Trip-Anlege-Standardauswahl
			// (metric_catalog.py, trip_default_rank=3) und ist im Ausblick
			// faehig (Wortstufe ueber format_wind_strength) — sie steht also
			// ohne Preset-Klick sowohl in der Grundauswahl als auch im
			// Ausblick. `outlook_metrics` bleibt unangetastet (None = "kein
			// Vokabular gesetzt" -> ganze Grundauswahl, #1848 A3).
			report_config: {
				enabled: true,
				send_email: true,
				email_format: 'full',
				multi_day_trend_reports: ['evening'],
				show_outlook: true
			}
		}
	});
	expect(created.ok(), `Seed-Trip HTTP ${created.status()}`).toBeTruthy();

	// Warmlauf: der Go-Proxy bricht die Vorschau nach 30 s ab
	// (internal/handler/preview_proxy.go:81), ein kalter Wetterabruf ueber drei
	// Segmente dauert laenger und endet in 502. Erst nach dem Warmlauf ist die
	// Flaeche im Browser innerhalb der Frist bedienbar.
	for (let attempt = 1; attempt <= 8; attempt++) {
		const res = await ctx.get(`/api/preview/${TRIP_ID}/email?type=evening`, { timeout: 120_000 });
		if (res.ok()) break;
		expect(attempt, `Vorschau (evening) bleibt nach ${attempt} Versuchen HTTP ${res.status()}`).toBeLessThan(8);
	}

	await ctx.storageState({ path: AUTH_FILE });
	fs.chmodSync(AUTH_FILE, 0o600);
	await ctx.dispose();
});

test.afterAll(async ({ playwright }) => {
	// Auch bei Fehlschlag aufraeumen — ausschliesslich der eigene Test-Trip.
	const ctx = await playwright.request.newContext({
		baseURL: BASE,
		ignoreHTTPSErrors: true,
		httpCredentials: VALIDATOR,
		storageState: AUTH_FILE
	});
	await ctx.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	await ctx.dispose();
});

/**
 * Oeffnet die Vorschau-Flaeche, schaltet den Demo-Modus ab (TripTabs startet
 * mit Fixture-Daten, #483) und waehlt den Abend-Report. Liefert den iframe-
 * Rahmen, sobald die ECHTE (demo-freie) Antwort da ist.
 */
async function openPreview(page: Page): Promise<FrameLocator> {
	await page.goto(`/trips/${TRIP_ID}?tab=preview`, { waitUntil: 'domcontentloaded' });
	await expect(page.getByTestId('trip-detail-panel-preview')).toBeVisible({ timeout: 30_000 });

	// Erwartete Antwort VOR den Klicks registrieren — sonst Rennen.
	const echteAntwort = page.waitForResponse(
		(r) =>
			r.url().includes(`/api/preview/${TRIP_ID}/email`) &&
			r.url().includes('type=evening') &&
			!r.url().includes('demo=1'),
		{ timeout: 120_000 }
	);

	const demoAus = page.getByTestId('preview-demo-disable');
	if (await demoAus.count()) await demoAus.click();
	await page.getByTestId('preview-controls').locator('input[type="radio"][value="evening"]').check();

	const res = await echteAntwort;
	expect(res.status(), `Vorschau-Abruf (evening) HTTP ${res.status()}`).toBe(200);
	await expect(page.getByTestId('email-iframe')).toBeVisible({ timeout: 30_000 });
	return page.frameLocator('[data-testid="email-iframe"]');
}

/**
 * Liest die Zellentexte der Spalte "Böen" aus der Ausblick-Tabelle. Die
 * Tabelle wird ueber ihre sichtbare Ueberschrift "Ausblick ... 3 Tage"
 * gefunden (wie in der Vorlage), damit keine andere Tabelle der Mail
 * versehentlich getroffen wird; die Spaltenposition wird aus dem
 * Kopfzeilentext ermittelt, statt eine feste Spaltennummer zu unterstellen.
 */
async function gustSpalte(frame: FrameLocator): Promise<string[]> {
	const tabelle = frame.locator(
		'xpath=//span[contains(., "Ausblick") and contains(., "3 Tage")]/../following-sibling::table[1]'
	);
	await expect(tabelle, 'Keine Ausblick-Tabelle in der Abend-Ansicht gefunden').toBeVisible({
		timeout: 30_000
	});
	return tabelle.evaluate((el) => {
		const headers = Array.from(el.querySelectorAll('thead th')).map((th) => (th.textContent ?? '').trim());
		const idx = headers.indexOf('Böen');
		if (idx < 0) return [];
		return Array.from(el.querySelectorAll('tbody tr')).map((tr) => {
			const zelle = tr.children[idx];
			return (zelle?.textContent ?? '').trim();
		});
	});
}

const ROH_MUSTER = /^\d+(?:[.,]\d+)?\s*km\/h$/;
const EINFACH_WORTSCHATZ = new Set(['schwach', 'mäßig', 'stark', 'sehr stark']);

test('vorschau_zelle_wechselt_von_rohzahl_auf_wortstufe (#2049 AC-14)', async ({ page }) => {
	test.setTimeout(300_000);

	// 1./2. Vorher: die Ausblick-Zelle fuer "Böen" zeigt die Rohzahl in km/h.
	const rohFrame = await openPreview(page);
	const rohZellen = await gustSpalte(rohFrame);
	expect(rohZellen.length, 'Kein "Böen"-Spalte in der Ausblick-Tabelle gefunden').toBeGreaterThan(0);

	const rohMitWert = rohZellen.filter((z) => ROH_MUSTER.test(z));
	// Anti-Vakuum: ohne einen echten km/h-Wert waere die Zelle korrekt "–"
	// und der Nachweis liefe ins Leere.
	expect(
		rohMitWert.length,
		`Kein Vorschau-Tag traegt heute einen Böen-Wert (${JSON.stringify(rohZellen)}) — ` +
			'der Nachweis liefe ins Leere. Anderen Trip/andere Koordinaten waehlen.'
	).toBeGreaterThan(0);

	// 3. In den Metriken-Editor wechseln, "Einfach" fuer "gust" klicken.
	await page.getByTestId('trip-detail-tab-weather').click();
	const ausblick = page.getByTestId('weather-metrics-ausblick');
	await expect(ausblick).toBeVisible();
	const gustRow = ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]');
	await expect(gustRow, 'Vorbedingung: "Böen" ist aktiv im Ausblick').toBeVisible();
	const einfachBtn = gustRow.getByRole('tab', { name: 'Einfach' });
	await expect(einfachBtn).toBeVisible();

	// Kurzes Zeitfenster statt der vollen Testfrist: bleibt der PUT aus, ist
	// das ein klarer Befund (Handler wirkungslos), kein Netzwerk-Flake — ein
	// langes Warten wuerde diesen Unterschied nur verschleiern.
	const putPromise = page.waitForRequest(
		(req) => req.method() === 'PUT' && req.url().includes('/weather-config'),
		{ timeout: 20_000 }
	);
	await einfachBtn.click();
	await putPromise;
	await expect(einfachBtn).toHaveAttribute('data-active', 'true');

	// 4. Vorschau erneut laden: dieselbe Zelle zeigt jetzt die Wortstufe statt
	// der km/h-Zahl. Frischer `page.goto` statt bloßem Tab-Wechsel, damit die
	// Radio-Auswahl "evening" wieder einen echten Klick (und damit einen
	// echten Refetch) ausloest, statt am bereits gesetzten Wert No-Op zu sein.
	const einfachFrame = await openPreview(page);
	const einfachZellen = await gustSpalte(einfachFrame);
	expect(
		einfachZellen.length,
		'Kein "Böen"-Spalte in der Ausblick-Tabelle nach der Umschaltung gefunden'
	).toBeGreaterThan(0);

	for (let i = 0; i < rohZellen.length; i++) {
		if (!ROH_MUSTER.test(rohZellen[i])) continue; // nur Tage mit echtem Vorher-Wert vergleichen
		const zelle = einfachZellen[i];
		expect(
			EINFACH_WORTSCHATZ.has(zelle),
			`AC-14 FAIL: Tag ${i} zeigt nach "Einfach" nicht eine Wortstufe, sondern "${zelle}"`
		).toBe(true);
		expect(zelle, `AC-14 FAIL: Tag ${i} enthaelt nach "Einfach" noch km/h: "${zelle}"`).not.toMatch(/km\/h/);
	}
});
