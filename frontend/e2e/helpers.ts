import { test as base, expect, type APIRequestContext, type BrowserContext, type Locator, type Page } from '@playwright/test';
import * as path from 'node:path';
import { resolveE2EUser } from './testUser.ts';

// ─────────────────────────────────────────────────────────────────────────────
// Issue #1771 Scheibe 1: geteilte, zustandsbasierte Ziehgeste für
// `svelte-dnd-action`-Zonen. Ersetzt 5 lokale Kopien in den Spec-Dateien.
//
// Spec: docs/specs/modules/fix_1771_s1_dnd_wartestrategie.md
//
// WARUM Pointer-Simulation statt `locator.dragTo()`: die Bibliothek schaltet
// natives HTML5-Drag bewusst ab (`draggableEl.draggable = false`) und hört nur
// auf Pointer-Events mit 3px-Bewegungsschwelle (MIN_MOVEMENT_BEFORE_DRAG_START_PX);
// `dragTo()` erzeugt nur EINEN Move-Schritt und reißt diese Schwelle nicht.
//
// WARUM auf `finalize` warten statt auf eine Frist: gemessen (4 Läufe gegen
// Staging, rohes DOM-CustomEvent-Log, unabhängig vom App-Code) feuert
// `svelte-dnd-action` das `finalize`-CustomEvent nach dem `mouseup`
// unzuverlässig — 2× gar nicht, 1× sofort, 1× erst nach ~1,9s. Ohne `finalize`
// ruft `SortableList.svelte::handleDndFinalize` nie `onDndReorder` auf: kein
// Edit, kein PUT, keine Persistenz. Eine feste `waitForTimeout`-Pause maskierte
// das — der Test las den `handleDndConsider`-Zwischenstand (lokal bereits neue
// Reihenfolge, nie committet) und hielt ihn für einen Speichervorgang.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Zieht ein `.sortable-item` per Maus-Sequenz auf ein Ziel und kehrt erst
 * zurück, wenn die zugehörige `.sortable-zone` das `finalize`-CustomEvent
 * gefeuert hat. Bleibt es binnen 5s aus, wirft die Funktion — statt lautlos
 * einen `consider`-Zwischenstand als Erfolg durchzureichen (#1771).
 */
export async function dragDndZoneItem(page: Page, source: Locator, target: Locator): Promise<void> {
	// Erst in den sichtbaren Bereich scrollen, DANN die Koordinaten lesen.
	// `boundingBox()` scrollt selbst nicht und liefert für Zeilen unterhalb des
	// Viewports Koordinaten außerhalb des Fensters — die Maus-Sequenz landet
	// dann im Leeren und der Drag passiert nie.
	await source.scrollIntoViewIfNeeded();
	await target.scrollIntoViewIfNeeded();

	// `.last()` trifft die NÄCHSTGELEGENE (innerste) Zone: `ancestor::*` liefert
	// Knoten in Dokumentreihenfolge von der Wurzel nach unten.
	const zone = source
		.locator('xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " sortable-zone ")]')
		.last();
	const zoneHandle = await zone.elementHandle();
	if (!zoneHandle) throw new Error('dragDndZoneItem: keine .sortable-zone-Ahnenzone gefunden');

	const before = await zoneHandle.evaluate((el) => {
		const marker = el as HTMLElement & { __gzFinalizeCount?: number };
		if (marker.__gzFinalizeCount === undefined) {
			marker.__gzFinalizeCount = 0;
			el.addEventListener('finalize', () => {
				marker.__gzFinalizeCount = (marker.__gzFinalizeCount ?? 0) + 1;
			});
		}
		return marker.__gzFinalizeCount;
	});

	const sourceBox = await source.boundingBox();
	const targetBox = await target.boundingBox();
	if (!sourceBox || !targetBox) throw new Error('dragDndZoneItem: source/target ohne BoundingBox');

	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
	await page.mouse.down();
	// Erster Zwischenschritt reißt sicher die 3px-Schwelle, damit dndzone den
	// Drag überhaupt als solchen erkennt (nicht als bloßen Klick).
	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2 - 12, {
		steps: 6
	});
	await page.waitForTimeout(120);
	await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2, {
		steps: 15
	});
	await page.waitForTimeout(120);
	await page.mouse.up();

	// Zeitfenster bewusst großzügig über dem gemessenen Worst Case (~1,9s) —
	// ein zu kurzes Fenster verlagert den Flake nur (Fehlschlag am Helfer statt
	// an der Fach-Assertion, obwohl `finalize` kurz danach gefeuert hätte).
	try {
		await page.waitForFunction(
			({ el, before }) =>
				((el as HTMLElement & { __gzFinalizeCount?: number }).__gzFinalizeCount ?? 0) > before,
			{ el: zoneHandle, before },
			{ timeout: 5_000, polling: 100 }
		);
	} catch {
		throw new Error(
			'dragDndZoneItem: kein finalize-Ereignis nach dem Ziehen (#1771) — svelte-dnd-action hat den Drag nicht committet'
		);
	}
}

/**
 * Touch-Variante von `dragDndZoneItem` (#2288 AC-10): zieht ein `.sortable-item`
 * per ECHTEN Touch-Ereignissen (Chrome-DevTools-Protokoll
 * `Input.dispatchTouchEvent`: touchStart → mehrere touchMove → touchEnd), nicht
 * per Maus. Gleiche zustandsbasierte Wartestrategie wie `dragDndZoneItem`: erst
 * zurück, wenn die `.sortable-zone` `finalize` gefeuert hat (#1771).
 *
 * Voraussetzung: Playwright-Kontext mit `hasTouch: true` (nur Chromium).
 * Gibt zurück, um wie viele Pixel die Seite während der Geste gescrollt hat
 * (`window.scrollY`-Delta) — eine Geste, die statt zu ziehen die Seite
 * scrollt, ist genau der Fehler, den AC-10 ausschließen soll.
 */
export async function dragDndZoneItemTouch(
	page: Page,
	source: Locator,
	target: Locator
): Promise<{ pageScrolledY: number }> {
	await source.scrollIntoViewIfNeeded();
	await target.scrollIntoViewIfNeeded();

	const zone = source
		.locator('xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " sortable-zone ")]')
		.last();
	const zoneHandle = await zone.elementHandle();
	if (!zoneHandle) throw new Error('dragDndZoneItemTouch: keine .sortable-zone-Ahnenzone gefunden');

	const before = await zoneHandle.evaluate((el) => {
		const marker = el as HTMLElement & { __gzFinalizeCount?: number };
		if (marker.__gzFinalizeCount === undefined) {
			marker.__gzFinalizeCount = 0;
			el.addEventListener('finalize', () => {
				marker.__gzFinalizeCount = (marker.__gzFinalizeCount ?? 0) + 1;
			});
		}
		return marker.__gzFinalizeCount;
	});

	const sourceBox = await source.boundingBox();
	const targetBox = await target.boundingBox();
	if (!sourceBox || !targetBox) throw new Error('dragDndZoneItemTouch: source/target ohne BoundingBox');

	const scrollBefore = await page.evaluate(() => window.scrollY);
	const cdp = await page.context().newCDPSession(page);
	const touch = (type: 'touchStart' | 'touchMove' | 'touchEnd', x?: number, y?: number) =>
		cdp.send('Input.dispatchTouchEvent', {
			type,
			touchPoints: type === 'touchEnd' ? [] : [{ x: x as number, y: y as number }]
		});

	const sx = sourceBox.x + sourceBox.width / 2;
	const sy = sourceBox.y + sourceBox.height / 2;
	const tx = targetBox.x + targetBox.width / 2;
	const ty = targetBox.y + targetBox.height / 2;

	await touch('touchStart', sx, sy);
	// Erste Bewegung reißt sicher die 3px-Schwelle, damit dndzone den Drag erkennt.
	for (let i = 1; i <= 6; i++) await touch('touchMove', sx, sy - 2 * i);
	await page.waitForTimeout(120);
	const steps = 15;
	for (let i = 1; i <= steps; i++) {
		await touch('touchMove', sx + ((tx - sx) * i) / steps, sy + ((ty - sy) * i) / steps);
	}
	await page.waitForTimeout(120);
	await touch('touchEnd');
	await cdp.detach().catch(() => {});

	try {
		await page.waitForFunction(
			({ el, before }) =>
				((el as HTMLElement & { __gzFinalizeCount?: number }).__gzFinalizeCount ?? 0) > before,
			{ el: zoneHandle, before },
			{ timeout: 5_000, polling: 100 }
		);
	} catch {
		throw new Error(
			'dragDndZoneItemTouch: kein finalize-Ereignis nach der Touch-Geste (#2288 AC-10) — svelte-dnd-action hat den Drag nicht committet'
		);
	}
	const scrollAfter = await page.evaluate(() => window.scrollY);
	return { pageScrolledY: Math.abs(scrollAfter - scrollBefore) };
}

/**
 * Login helper — authenticates via the login form and returns the page
 * with a valid session cookie set.
 */
export async function login(page: Page) {
	await page.goto('/');
	if (!page.url().includes('/login')) return;
	const { user, pass } = resolveE2EUser();
	await page.fill('input[name="username"]', user);
	await page.fill('input[name="password"]', pass);
	await page.click('form[action="?/login"] button[type="submit"]');
	// Issue #2248: die Anmeldung haengt einen Marker an die Zieladresse
	// (`/?passkey_angebot=1`); der Pfad bleibt `/`.
	await page.waitForURL((url) => url.pathname === '/');
}

/**
 * Legt einen zweiten, sofort anmeldbaren Nutzer an (Issue #2271).
 *
 * Seit der Scharfschaltung des Login-Gates stellt `issueSession` nur noch fuer
 * bestaetigte Adressen ein Merkmal aus. Ein zur Laufzeit registriertes Konto
 * mit Zeitstempel-Suffix kann seine Bestaetigungsmail auf Staging nie empfangen
 * (Egress-Sperre #1337) — ohne diesen Umweg waere jede Zwei-Nutzer-Spec
 * strukturell nie wieder gruen.
 *
 * 🔴 Die Reihenfolge ist zwingend: registrieren → Token holen → bestaetigen →
 * ERST DANN anmelden. Und das Token holt die BEREITS ANGEMELDETE fremde
 * Sitzung (`adminRequest`), nicht der neue Nutzer: der Testweg ist
 * anmeldepflichtig (staging_verify_token.go), und genau das kann das neue
 * Konto in diesem Moment nicht. Moeglich ist es, weil der Handler die Kennung
 * aus der Nutzlast nimmt und `email_verified_at` selbst nicht anfasst — das
 * setzt weiterhin allein der regulaere Verifikations-Endpunkt.
 *
 * Braucht `GZ_ENV=staging` im Ziel-Stack (Staging und der isolierte
 * CI-Stack erfuellen das, frontend/e2e/ci-stack.sh:66).
 */
export async function registriereBestaetigtenZweitnutzer(
	adminRequest: APIRequestContext,
	gastRequest: APIRequestContext,
	username: string,
	password: string
): Promise<void> {
	const reg = await gastRequest.post('/api/auth/register', {
		data: { username, password, email: `${username}@example.com` }
	});
	if (![200, 201].includes(reg.status())) {
		throw new Error(`Registrierung ${username} fehlgeschlagen: ${reg.status()} ${await reg.text()}`);
	}

	const tokenAntwort = await adminRequest.post('/api/auth/verify-email/staging-token', {
		data: { username }
	});
	if (!tokenAntwort.ok()) {
		throw new Error(
			`Staging-Testweg antwortet ${tokenAntwort.status()} fuer ${username} — laeuft das Ziel mit GZ_ENV=staging, und ist die uebergebene Sitzung angemeldet?`
		);
	}
	const { token } = (await tokenAntwort.json()) as { token?: string };
	if (!token) throw new Error(`Staging-Testweg lieferte kein Token fuer ${username}`);

	const bestaetigung = await gastRequest.post('/api/auth/verify-email', {
		data: { user: username, token }
	});
	if (!bestaetigung.ok()) {
		throw new Error(
			`Bestaetigung ${username} fehlgeschlagen: ${bestaetigung.status()} ${await bestaetigung.text()}`
		);
	}

	const login = await gastRequest.post('/api/auth/login', { data: { username, password } });
	if (!login.ok()) {
		throw new Error(`Login ${username} fehlgeschlagen: ${login.status()} ${await login.text()}`);
	}
}

type Sitzung = Awaited<ReturnType<BrowserContext['storageState']>>;

/**
 * Issue #2278 AC-10: Spec-Basis fuer Versand-Specs, deren Nutzer ein ZUSTELLBARES Ziel braucht.
 *
 * Der Sende-Dialog sperrt "Senden" ohne `mail_to` (sendTargetLabel.ts). Der Env-Admin des
 * CI-Stacks hat keins und bekommt auch keins per `PUT /api/auth/profile {mail_to}`: er ist
 * bestaetigt, die neue Adresse landet als Pending-Adresse (auth.go, Zweig `default:` der
 * Adressaenderung) samt Bestaetigungsmail. Deshalb EIN bestaetigter Zweitnutzer je Worker
 * (Registrierungsbremse: 5/h je IP, router.go) — `page`/`context` laufen als dieser Nutzer, der
 * Admin bleibt unberuehrt. Der Nutzer bekommt den Seed-Trip `e2e-cockpit-test` mit demselben
 * Namen wie beim Admin (global.setup.ts), damit die Specs ihre Kennungen behalten. Der Versand
 * selbst wird in den Specs per `page.route` abgefangen.
 */
export const testMitZustellbaremZiel = base.extend<object, { zustellbareSitzung: Sitzung }>({
	storageState: ({ zustellbareSitzung }, use) => use(zustellbareSitzung),
	zustellbareSitzung: [
		async ({ browser }, use, workerInfo) => {
			const baseURL = workerInfo.project.use.baseURL;
			const neu = { baseURL, storageState: undefined, serviceWorkers: 'block' as const };
			// Admin-Sitzung des Projekts (global.setup.ts) holt das Staging-Token.
			const adminCtx = await browser.newContext({ ...neu, storageState: workerInfo.project.use.storageState });
			const gastCtx = await browser.newContext(neu);
			const username = `e2ezustellbar${Date.now()}w${workerInfo.workerIndex}`;
			const kennwort = 'Test1234!x';
			try {
				await registriereBestaetigtenZweitnutzer(adminCtx.request, gastCtx.request, username, kennwort);
			} finally {
				await adminCtx.close();
			}
			const profil = await (await gastCtx.request.get('/api/auth/profile')).json();
			expect(profil?.mail_to, 'Vorbedingung: Zweitnutzer hat ein zustellbares mail_to').toBeTruthy();
			const heute = new Date().toISOString().slice(0, 10);
			const morgen = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
			const trip = await gastCtx.request.post('/api/trips', {
				data: {
					id: 'e2e-cockpit-test',
					name: 'E2E Cockpit Test Trip',
					region: 'Korsika',
					stages: [
						{ id: 'e2e-stage-2', name: 'Heute', date: heute, waypoints: [
							{ id: 'e2e-wp-2', name: 'Mitte', lat: 42.2, lon: 9.1, elevation_m: 1200 },
							{ id: 'e2e-wp-3', name: 'Ziel', lat: 42.3, lon: 9.2, elevation_m: 600 }
						] },
						{ id: 'e2e-stage-3', name: 'Morgen', date: morgen, waypoints: [] }
					],
					report_config: { enabled: true, morning_time: '06:00:00', evening_time: '18:00:00' }
				}
			});
			expect(trip.ok(), `Seed-Trip des Zweitnutzers: ${trip.status()}`).toBeTruthy();
			await use(await gastCtx.storageState());
			await gastCtx.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gastCtx.close();
		},
		{ scope: 'worker' }
	]
});

/**
 * Eingabe-Vertrag fuer Trip-Wizard Step 1 (Sub-Spec #161 §9).
 * Wiederverwendet in `trip-wizard-step1.spec.ts` und `trip-wizard-shell.spec.ts`.
 */
export interface Step1Input {
	activity: 'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb';
	name: string;
	shortcode?: string;
	startDate: string; // 'YYYY-MM-DD'
}

/**
 * Fuellt die drei Pflicht- und das optionale Feld in Step 1 des Trip-Wizards.
 * Quelle: docs/specs/modules/epic_136_step1_profile.md §9.
 */
export async function fillStep1(page: Page, input: Step1Input): Promise<void> {
	await page.getByTestId(`trip-wizard-step1-chip-${input.activity}`).click();
	await page.getByTestId('trip-wizard-step1-name').fill(input.name);
	if (input.shortcode !== undefined) {
		await page.getByTestId('trip-wizard-step1-shortcode').fill(input.shortcode);
	}
	await page.getByTestId('trip-wizard-step1-startdate').fill(input.startDate);
}

/**
 * Eingabe-Vertrag fuer Trip-Wizard Step 2 (Sub-Spec #162 §11.2).
 * Default-Files: `['test-trip.gpx']` aus `frontend/e2e/fixtures/`.
 */
export interface Step2Input {
	files?: string[];
}

/**
 * Laedt eine oder mehrere GPX-Dateien in den Step-2-Drop-Bereich
 * und triggert anschliessend "Etappen anlegen" — wartet auf erscheinen
 * der ersten Stage-Row.
 *
 * Voraussetzung: Wizard ist auf Step 2 (TripWizardShell hat Step2Stages gemountet).
 */
export async function fillStep2(page: Page, input?: Step2Input): Promise<void> {
	const files = (input?.files ?? ['test-trip.gpx']).map((f) =>
		path.resolve('./e2e/fixtures', f)
	);
	const fileInput = page.locator('input[type="file"][accept=".gpx"]');
	await fileInput.setInputFiles(files);
	// Pending-Region erwartet — Bulk-Commit-Button erscheint nach setInputFiles.
	const commit = page.getByTestId('trip-wizard-step2-bulk-commit');
	await commit.waitFor({ state: 'visible' });
	await commit.click();
	// Erste Stage-Row muss sichtbar werden.
	await page.getByTestId('trip-wizard-step2-stage-row-0').waitFor({ state: 'visible' });
}

/**
 * Eingabe-Vertrag fuer Trip-Wizard Step 3 (Sub-Spec #163 §10).
 * Default-Verhalten: keine Aktion — alle Waypoints bleiben suggested
 * (canAdvanceStep3 = true), nur Weiter-Klick.
 */
export interface Step3Input {
	confirmAll?: boolean;
	rejectByName?: string[];
}

/**
 * Step-3-Helper: optional Bestaetigen/Verwerfen, dann Weiter-Klick.
 * Voraussetzung: Wizard ist auf Step 3 (Step3Waypoints gemountet).
 */
export async function fillStep3(page: Page, input: Step3Input = {}): Promise<void> {
	await page.getByTestId('trip-wizard-step3-container').waitFor({ state: 'visible' });

	if (input.confirmAll) {
		// Solange ein Confirm-Button sichtbar ist, ersten klicken — nach Klick
		// verschwindet der Button und folgende Indizes ruecken nicht (kein Reorder),
		// aber `first()` greift immer den ersten verbliebenen Button.
		const confirmBtns = page.getByTestId(/^trip-wizard-step3-confirm-/);
		// Sicherheits-Cap, falls etwas schief laeuft.
		for (let i = 0; i < 50; i++) {
			const count = await confirmBtns.count();
			if (count === 0) break;
			await confirmBtns.first().click();
		}
	}

	if (input.rejectByName && input.rejectByName.length > 0) {
		for (const name of input.rejectByName) {
			const row = page.locator('[data-testid^="trip-wizard-step3-waypoint-row-"]', {
				hasText: name
			});
			const idx = await row.getAttribute('data-waypoint-index');
			if (idx) {
				await page.getByTestId(`trip-wizard-step3-reject-${idx}`).click();
			}
		}
	}

	await page.getByTestId('trip-wizard-next').click();
}

// ─────────────────────────────────────────────────────────────────────────────
// #1329 Maßnahme B: geteilter, auto-registrierender E2E-Datenanlage-Helfer.
//
// Spec: docs/specs/modules/fix_1329_e2e_data_hygiene.md
//
// Jede Funktion vergibt einen Namen/ID mit reserviertem Präfix `E2E-GZ-` +
// kollisionsfreiem Zeitstempel/Random-Suffix, ruft die passende REST-API auf
// und registriert die erzeugte ID modul-intern (`registerForCleanup`). Das
// eigentliche Sicherheitsnetz ist `global.teardown.ts` (Präfix-Sweep nach
// Suite-Ende) — `cleanupTracked()` ist ein optionaler Zusatz für Specs, die
// zusätzlich pro Testfall/Datei aufräumen wollen.
// ─────────────────────────────────────────────────────────────────────────────

export const E2E_TEST_PREFIX = 'E2E-GZ-';

type CleanupKind = 'preset' | 'trip' | 'location';

// Reihenfolge referenzierender vor referenzierten Objekten (behebt 409-Waisen,
// AC-3): Presets/Trips referenzieren Orte, nie umgekehrt.
const CLEANUP_ORDER: CleanupKind[] = ['preset', 'trip', 'location'];

const tracked: Record<CleanupKind, Set<string>> = {
	preset: new Set(),
	trip: new Set(),
	location: new Set()
};

function uniqueSuffix(): string {
	return `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
}

/** Trägt eine ID modul-intern zur späteren Bereinigung ein (s. `cleanupTracked`). */
export function registerForCleanup(kind: CleanupKind, id: string): void {
	tracked[kind].add(id);
}

async function deleteById(request: APIRequestContext, kind: CleanupKind, id: string): Promise<void> {
	const urlPath =
		kind === 'preset'
			? `/api/compare/presets/${id}`
			: kind === 'trip'
				? `/api/trips/${id}`
				: `/api/locations/${id}`;
	try {
		const res = await request.delete(urlPath);
		if (!res.ok() && res.status() !== 404) {
			// DELETE-Fehler werden GELOGGT statt stillschweigend verschluckt
			// (Root Cause #3, Kontext-Dokument #1329) — kein `.catch(() => {})`.
			console.error(`[e2e-cleanup] DELETE ${urlPath} -> HTTP ${res.status()}`);
		}
	} catch (err) {
		console.error(`[e2e-cleanup] DELETE ${urlPath} threw:`, err);
	}
}

/** Löscht alle bislang registrierten Test-Objekte, Reihenfolge Preset/Trip → Ort. */
export async function cleanupTracked(request: APIRequestContext): Promise<void> {
	for (const kind of CLEANUP_ORDER) {
		const ids = Array.from(tracked[kind]);
		tracked[kind].clear();
		for (const id of ids) {
			await deleteById(request, kind, id);
		}
	}
}

export interface TestLocationOpts {
	name?: string;
	lat?: number;
	lon?: number;
	elevation_m?: number;
	region?: string;
	group?: string;
}

export interface TestLocation {
	id: string;
	name: string;
}

/**
 * Stellt sicher, dass ein Name mit dem reservierten Präfix beginnt — idempotent.
 * Aufrufer, die das Präfix selbst schon einbauen (und per exact-Match darauf prüfen),
 * dürfen NICHT doppelt präfixiert werden (`E2E-GZ-E2E-GZ-…`).
 */
function ensureTestPrefix(name: string): string {
	return name.startsWith(E2E_TEST_PREFIX) ? name : `${E2E_TEST_PREFIX}${name}`;
}

/** Legt einen Test-Ort mit reserviertem Präfix an und registriert ihn zur Bereinigung. */
export async function createTestLocation(
	request: APIRequestContext,
	opts: TestLocationOpts = {}
): Promise<TestLocation> {
	const suffix = uniqueSuffix();
	const name = opts.name ? ensureTestPrefix(opts.name) : `${E2E_TEST_PREFIX}Loc-${suffix}`;
	const res = await request.post('/api/locations', {
		data: {
			name,
			lat: opts.lat ?? 47.0 + Math.random() * 0.5,
			lon: opts.lon ?? 11.0 + Math.random() * 0.5,
			...(opts.elevation_m !== undefined ? { elevation_m: opts.elevation_m } : {}),
			...(opts.region !== undefined ? { region: opts.region } : {}),
			...(opts.group !== undefined ? { group: opts.group } : {})
		}
	});
	if (!res.ok()) {
		throw new Error(`createTestLocation fehlgeschlagen: HTTP ${res.status()} — ${await res.text()}`);
	}
	const body = (await res.json()) as { id: string; name: string };
	registerForCleanup('location', body.id);
	return { id: body.id, name: body.name };
}

export interface TestComparePresetOpts {
	name?: string;
	locationIds: string[];
	schedule?: 'daily' | 'weekly' | 'manual';
	profil?: string;
	hourFrom?: number;
	hourTo?: number;
	empfaenger?: string[];
}

export interface TestComparePreset {
	id: string;
	name: string;
}

/** Legt ein Test-Compare-Preset mit reserviertem Präfix an und registriert es zur Bereinigung. */
export async function createTestComparePreset(
	request: APIRequestContext,
	opts: TestComparePresetOpts
): Promise<TestComparePreset> {
	const suffix = uniqueSuffix();
	const name = opts.name ? ensureTestPrefix(opts.name) : `${E2E_TEST_PREFIX}Preset-${suffix}`;
	const res = await request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: opts.locationIds,
			schedule: opts.schedule ?? 'daily',
			profil: opts.profil ?? 'wandern',
			hour_from: opts.hourFrom ?? 7,
			hour_to: opts.hourTo ?? 18,
			empfaenger: opts.empfaenger ?? ['urlauber@example.com']
		}
	});
	if (!res.ok()) {
		throw new Error(`createTestComparePreset fehlgeschlagen: HTTP ${res.status()} — ${await res.text()}`);
	}
	const body = (await res.json()) as { id: string; name: string };
	registerForCleanup('preset', body.id);
	return { id: body.id, name: body.name };
}

export interface TestTripOpts {
	id?: string;
	name?: string;
	stages?: unknown[];
}

export interface TestTrip {
	id: string;
	name: string;
}

/** Legt einen Test-Trip mit reserviertem Präfix an und registriert ihn zur Bereinigung. */
export async function createTestTrip(request: APIRequestContext, opts: TestTripOpts = {}): Promise<TestTrip> {
	const suffix = uniqueSuffix();
	const id = opts.id ?? `e2e-gz-trip-${suffix}`;
	const name = opts.name ? ensureTestPrefix(opts.name) : `${E2E_TEST_PREFIX}Trip-${suffix}`;
	const res = await request.post('/api/trips', {
		data: { id, name, stages: opts.stages ?? [] }
	});
	if (!res.ok()) {
		throw new Error(`createTestTrip fehlgeschlagen: HTTP ${res.status()} — ${await res.text()}`);
	}
	const body = (await res.json()) as { id: string; name: string };
	registerForCleanup('trip', body.id);
	return { id: body.id, name: body.name };
}

// ─────────────────────────────────────────────────────────────────────────────
// Issue #2347 S1 (Epic #2345, Etappe P6): kind-Helfer für Paritäts-Specs —
// EINE Spec prüft dieselbe Zusicherung für Trip- und Vergleichs-Hub per
// Schleife über HUB_KINDS. Bewusst dünn: keine Assertions. Die gemeinsamen
// Selektor-Unterschiede stehen seit #2347 S2 als HUB_SEL[kind] hier; nur
// spec-eigene Abweichungen (z. B. hub-versand-autosave-chip) bleiben lokal.
// ─────────────────────────────────────────────────────────────────────────────

/** = `context`-Parameter der geteilten Bausteine. */
export type HubKind = 'route' | 'vergleich';
export const HUB_KINDS: readonly HubKind[] = ['route', 'vergleich'];

const regexEscape = (s: string): string => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Selektor-/Feld-Unterschiede je kind (#2347 S2). Reines Konstanten-Objekt —
 * keine Assertions, keine Wartelogik.
 */
export const HUB_SEL: Record<
	HubKind,
	{
		/** Testid-Präfix des SubscriptionHeader. */
		kopf: 'trip' | 'compare-hub';
		/** Reiter `${reiter}-<id>`, Panel `${panel}-<id>`. */
		reiter: string;
		panel: string;
		reiterListe: string;
		/** kind-eigener Punkte-Reiter. */
		punkteReiter: 'etappen' | 'orte';
		/** Feld hinter dem Profil im gespeicherten Stand. */
		profilFeld: 'activity' | 'profil';
		/** gültiger, vom Seed-Startwert verschiedener Zielwert. */
		profilWert: string;
		liste: { url: string; zeile: (id: string) => string; menue: string };
		hubUrl: (id: string) => RegExp;
	}
> = {
	route: {
		kopf: 'trip',
		reiter: 'trip-detail-tab',
		panel: 'trip-detail-panel',
		reiterListe: 'trip-detail-tab-list',
		punkteReiter: 'etappen',
		profilFeld: 'activity',
		profilWert: 'skitour',
		liste: { url: '/trips', zeile: (id) => `trip-row-${id}`, menue: 'trip-row-menu-btn' },
		hubUrl: (id) => new RegExp(`/trips/${regexEscape(id)}(\\?|$)`)
	},
	vergleich: {
		kopf: 'compare-hub',
		reiter: 'compare-detail-tab',
		panel: 'compare-detail-panel',
		reiterListe: 'compare-detail-tab-list',
		punkteReiter: 'orte',
		profilFeld: 'profil',
		profilWert: 'wandern',
		liste: { url: '/compare', zeile: (id) => `compare-tile-${id}`, menue: 'compare-row-kebab' },
		hubUrl: (id) => new RegExp(`/compare/${regexEscape(id)}(\\?|$)`)
	}
};

export interface SeededHub {
	kind: HubKind;
	id: string;
	aufraeumen(): Promise<void>;
}

export const hubApiPath = (kind: HubKind, id: string): string =>
	kind === 'route' ? `/api/trips/${id}` : `/api/compare/presets/${id}`;

const hubWp = (id: string, lat: number, elevation_m: number) => ({ id, name: id, lat, lon: 9.0, elevation_m });

function seedRumpf(kind: HubKind, suffix: string): Record<string, unknown> {
	if (kind === 'route') {
		return {
			id: `e2e-gz-hub-${suffix}`,
			name: `${E2E_TEST_PREFIX}Hub-Trip-${suffix}`,
			stages: [
				{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [hubWp('a', 42.0, 800), hubWp('b', 42.04, 1200)] }
			],
			report_config: {
				enabled: true,
				morning_enabled: true,
				evening_enabled: false,
				morning_time: '06:00:00',
				evening_time: '18:00:00'
			}
		};
	}
	return {
		name: `${E2E_TEST_PREFIX}Hub-Vergleich-${suffix}`,
		// Seed-Orte aus global.setup.ts
		location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 7,
		hour_to: 16,
		empfaenger: ['hub-paritaet@example.com'],
		morning_enabled: true,
		morning_time: '06:00:00',
		evening_enabled: false,
		evening_time: '18:00:00'
	};
}

/** Legt Trip bzw. Vergleich per REST an (Präfix E2E-GZ-, Versand 06:00); wirft bei !ok. */
export async function seedHub(
	request: APIRequestContext,
	kind: HubKind,
	opts: { extra?: Record<string, unknown> } = {}
): Promise<SeededHub> {
	const sammel = kind === 'route' ? '/api/trips' : '/api/compare/presets';
	const res = await request.post(sammel, { data: { ...seedRumpf(kind, uniqueSuffix()), ...opts.extra } });
	if (!res.ok()) {
		throw new Error(`seedHub(${kind}) fehlgeschlagen: HTTP ${res.status()} — ${await res.text()}`);
	}
	const { id } = (await res.json()) as { id: string };
	return { kind, id, aufraeumen: () => deleteById(request, kind === 'route' ? 'trip' : 'preset', id) };
}

/** Öffnet den Hub (+ ?tab=…, #hash) und wartet nur auf die sichtbare Reiterleiste. */
export async function openHub(
	page: Page,
	kind: HubKind,
	id: string,
	opts: { tab?: string; hash?: string } = {}
): Promise<void> {
	const basis = kind === 'route' ? `/trips/${id}` : `/compare/${id}`;
	await page.goto(`${basis}${opts.tab ? `?tab=${opts.tab}` : ''}${opts.hash ? `#${opts.hash}` : ''}`);
	const prefix = kind === 'route' ? 'trip-detail-tab' : 'compare-detail-tab';
	const reiter = page
		.locator(opts.tab ? `[data-testid="${prefix}-${opts.tab}"]:visible` : `[data-testid^="${prefix}-"]:visible`)
		.first();
	await reiter.waitFor({ state: 'visible', timeout: 15_000 });
	// Vergleich: Reiter zusätzlich anklicken (doppelte Knoten, Muster oeffneVersand).
	if (kind === 'vergleich' && opts.tab) await reiter.click();
}
