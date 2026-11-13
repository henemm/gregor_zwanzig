import { test as base, expect, type APIRequestContext, type APIResponse, type BrowserContext, type Locator, type Page } from '@playwright/test';
import * as path from 'node:path';
import { resolveE2EUser } from './testUser.ts';
import { wegwerfPasswort } from './stagingZugang';

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
 * Issue #2961 (ADR-0115): Adresswechsel und Passkey hinzufuegen/entfernen
 * verlangen einen frischen Nachweis, der 10 Minuten fuer genau die Sitzung gilt
 * (eine frische Anmeldung zaehlt selbst als Nachweis). Specs, die mit einer
 * gespeicherten Sitzung solche Aenderungen ausloesen, erbringen ihn hier mit
 * dem Passwort — ueber `page.request`, damit es dieselbe Sitzung ist wie die
 * der Seite.
 */
export async function bestaetigeKontoaenderung(request: APIRequestContext, passwort?: string): Promise<void> {
	const pass = passwort ?? resolveE2EUser().pass;
	const res = await request.post('/api/auth/reauth', { data: { password: pass } });
	if (!res.ok()) {
		throw new Error(`Nachweis vor Kontoaenderung fehlgeschlagen: ${res.status()} ${await res.text()}`);
	}
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
 *
 * Issue #2194 (ADR-0105): Der Zweitnutzer ist bewusst KEIN Testkonto (er braucht
 * ein zustellbares Ziel, Testkonten erhalten keine Mails). Ohne `is_test_user`
 * vergibt der Server die Konto-ID selbst (`u-<8hex>`) und ignoriert `username`;
 * alle Folgeschritte nutzen deshalb die `id` aus der Register-Antwort. `username`
 * bleibt der Namensstamm fuer die E-Mail-Adresse. Rueckgabe: die angelegte ID.
 */
export async function registriereBestaetigtenZweitnutzer(
	adminRequest: APIRequestContext,
	gastRequest: APIRequestContext,
	username: string,
	password: string
): Promise<string> {
	const email = `${username}@example.com`;
	const reg = await gastRequest.post('/api/auth/register', {
		data: { username, password, email }
	});
	if (![200, 201].includes(reg.status())) {
		throw new Error(`Registrierung ${username} fehlgeschlagen: ${reg.status()} ${await reg.text()}`);
	}
	const { id } = (await reg.json().catch(() => ({}))) as { id?: unknown };
	if (typeof id !== 'string' || id === '') {
		throw new Error(`Registrierung ${username} lieferte keine Konto-ID: ${await reg.text()}`);
	}

	const tokenAntwort = await adminRequest.post('/api/auth/verify-email/staging-token', {
		data: { username: id }
	});
	if (!tokenAntwort.ok()) {
		throw new Error(
			`Staging-Testweg antwortet ${tokenAntwort.status()} fuer ${id} — laeuft das Ziel mit GZ_ENV=staging, und ist die uebergebene Sitzung angemeldet?`
		);
	}
	const { token } = (await tokenAntwort.json()) as { token?: string };
	if (!token) throw new Error(`Staging-Testweg lieferte kein Token fuer ${id}`);

	const bestaetigung = await gastRequest.post('/api/auth/verify-email', {
		data: { user: id, token }
	});
	if (!bestaetigung.ok()) {
		throw new Error(`Bestaetigung ${id} fehlgeschlagen: ${bestaetigung.status()} ${await bestaetigung.text()}`);
	}

	const login = await gastRequest.post('/api/auth/login', { data: { username: id, password } });
	if (!login.ok()) {
		throw new Error(`Login ${id} fehlgeschlagen: ${login.status()} ${await login.text()}`);
	}
	return id;
}

type Sitzung = Awaited<ReturnType<BrowserContext['storageState']>>;

/**
 * Seed-Trip `e2e-cockpit-test` des zustellbaren Zweitnutzers (testMitZustellbaremZiel).
 * Herausgehoben (#2881), damit eine Spec, die den Leerzustand braucht, ihn danach
 * unverändert wiederherstellen kann. Keine Assertions; liefert die POST-Antwort.
 */
export async function seedeZweitnutzerTrip(request: APIRequestContext): Promise<APIResponse> {
	const heute = new Date().toISOString().slice(0, 10);
	const morgen = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
	return request.post('/api/trips', {
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
}

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
			const kennwort = wegwerfPasswort();
			try {
				await registriereBestaetigtenZweitnutzer(adminCtx.request, gastCtx.request, username, kennwort);
			} finally {
				await adminCtx.close();
			}
			const profil = await (await gastCtx.request.get('/api/auth/profile')).json();
			expect(profil?.mail_to, 'Vorbedingung: Zweitnutzer hat ein zustellbares mail_to').toBeTruthy();
			const trip = await seedeZweitnutzerTrip(gastCtx.request);
			expect(trip.ok(), `Seed-Trip des Zweitnutzers: ${trip.status()}`).toBeTruthy();
			await use(await gastCtx.storageState());
			await gastCtx.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gastCtx.close();
		},
		{ scope: 'worker' }
	]
});

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

// ─────────────────────────────────────────────────────────────────────────────
// Issue #2837 S1 (Epic #2345, ADR-0110): geteilter Hub-Kopf `shared/hub-kopf/HubKopf.svelte`.
// Seine testids sind für BEIDE Arten gleich (kein kind-Eintrag nötig) — deshalb ein
// eigenes Konstanten-Objekt statt neuer HUB_SEL-Felder; HUB_SEL bleibt unverändert.
// Reine Selektoren/Werte, keine Assertions.
// ─────────────────────────────────────────────────────────────────────────────

export const HUB_KOPF_SEL = {
	/** Leiste ganz oben: Breadcrumb bzw. Zurück-Pfeil, Senden, Kebab, Meldungen. */
	leiste: 'hub-kopf-leiste',
	/** Breadcrumb „Elternteil (Link) / Kind (kein Link)". */
	breadcrumb: 'hub-kopf-breadcrumb',
	/** Status-Badge samt Zusatz in der Titelzeile (status-Snippet). */
	status: 'hub-kopf-status',
	/** Senden-Knopf (stabil seit #2278). */
	senden: 'subscription-hub-send',
	/** Kebab (Desktop-Dropdown bzw. mobiler Knopf zum Aktionsblatt). */
	kebab: 'subscription-kebab',
	/** Überschrift: Trip trägt eine testid, der Vergleich nicht — gemeinsam über die Rolle. */
	titelRolle: { role: 'heading', level: 1 } as const
} as const;

/** Berechnete Token-Farben aus app.css (getComputedStyle-Form). */
export const TOKEN_RGB = {
	ink: 'rgb(26, 26, 24)',
	accent: 'rgb(196, 90, 42)',
	/** #2879: Accent unter/als Text (Weiter-Knopf, aktiver Handy-Reiter, Kürzel). */
	accentDeep: 'rgb(140, 62, 26)',
	paperDeep: 'rgb(236, 234, 217)',
	ink3: 'rgb(107, 103, 92)'
} as const;

/** WCAG-Kontrastverhältnis zweier `rgb(...)`/`rgba(...)`-Werte aus getComputedStyle. */
export function kontrastVerhaeltnis(vorne: string, hinten: string): number {
	const kanal = (c: string): number[] => {
		const m = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/.exec(c);
		if (!m) throw new Error(`kontrastVerhaeltnis: keine rgb-Farbe „${c}"`);
		return [m[1], m[2], m[3]].map(Number);
	};
	const lum = (c: string): number => {
		const [r, g, b] = kanal(c).map((v) => {
			const s = v / 255;
			return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
		});
		return 0.2126 * r + 0.7152 * g + 0.0722 * b;
	};
	const [a, b] = [lum(vorne), lum(hinten)].sort((x, y) => y - x);
	return (a + 0.05) / (b + 0.05);
}

// ─────────────────────────────────────────────────────────────────────────────
// Issue #2879 (WCAG-AA auf Trip-/Vergleichsseiten): Kontrast-Messhelfer, herausgehoben aus
// kuerzel-legende-lesbar.staging.spec.ts und um die Mischung transparenter Schichten erweitert.
// Spec: docs/specs/modules/fix_2879_kontrast_wcag_aa.md (Implementation Details 1, AC-6,
// Known Limitations „Messumfang").
//
// Gemessen wird jeder sichtbare Text: Textknoten, Werte von `input`/`textarea` (nicht der
// Platzhalter) und `::before`/`::after`-Inhalte mit Buchstaben oder Ziffern. Schriftfarbe (SVG:
// fill) gegen den EFFEKTIVEN Hintergrund — alle Hintergrundschichten der Vorfahrenkette von außen
// nach innen übereinandergelegt (Start Weiß), transluzente Schichten gemischt, Schrift-Alpha ×
// Opacity-Kette auf diesen Grund gemischt. Liegt von innen gesehen ein `background-image` vor dem
// ersten deckenden Grund, ist der Grund nicht berechenbar — das ist ein eigener Verstoß.
// Schwelle 4,5:1, großer Text (≥ 24 px oder ≥ 18,66 px bei Gewicht ≥ 700) 3:1.
// Ausnahmen werden mitgemeldet, nicht verschwiegen:
//   gesperrt     `[disabled]`, `aria-disabled="true"` (WCAG 1.4.3 „inactive UI component");
//   aria-hidden  nur Zeichen OHNE Buchstabe/Ziffer (·, ›, ×, ⓘ): aria-hidden macht sichtbaren
//                Text nicht unsichtbar, also keine Ausnahme für lesbaren Text;
//   logo         nur der Schriftzug (`.typo-row`) einer Wortmarke `[data-testid="brand-wordmark"]`
//                (WCAG 1.4.3 „Logotypes") — nicht die Unterzeile, nicht beliebige Träger der testid.
// ─────────────────────────────────────────────────────────────────────────────

export interface KontrastBefund {
	text: string;
	/** Tag des Elternelements (z. B. `code`, `span`; bei Eingaben `input`/`textarea`). */
	tag: string;
	/** Herkunft des Textes. */
	quelle: 'text' | 'eingabe' | '::before' | '::after';
	/** Berechnete Schriftfarbe, roh aus getComputedStyle. */
	farbeRoh: string;
	/** Schriftfarbe nach Alpha/Opacity-Mischung. */
	farbe: string;
	hintergrund: string;
	verhaeltnis: number;
	schwelle: number;
	schrift: string;
	pfad: string;
	/** false: von innen gesehen liegt ein `background-image` vor dem ersten deckenden Grund. */
	berechenbar: boolean;
	ausnahme: 'gesperrt' | 'aria-hidden' | 'logo' | null;
	/** Nur bei `logo`: Index der Wortmarke unter allen `[data-testid="brand-wordmark"]` der Seite. */
	logoInstanz: number | null;
}

/** Läuft im Browser (selbstständig, keine Closures): misst allen sichtbaren Text unter `wurzel`. */
function messeTextknotenImBrowser(wurzel: Element): KontrastBefund[] {
	type Rgba = [number, number, number, number];
	const parse = (c: string): Rgba | null => {
		const srgb = /color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)/.exec(c);
		if (srgb) return [+srgb[1] * 255, +srgb[2] * 255, +srgb[3] * 255, srgb[4] ? +srgb[4] : 1];
		const m = /rgba?\(([^)]+)\)/.exec(c);
		if (m) {
			const t = m[1].split(/[\s,/]+/).filter(Boolean).map(parseFloat);
			return [t[0], t[1], t[2], t.length > 3 ? t[3] : 1];
		}
		// Andere Farbräume (color-mix() ⇒ oklab(…), oklch(…)): über eine 1×1-Leinwand nach sRGB.
		if (!/^(oklab|oklch|lab|lch|hsla?|hwb|color)\(/.test(c)) return null;
		leinwand.clearRect(0, 0, 1, 1);
		leinwand.fillStyle = c;
		leinwand.fillRect(0, 0, 1, 1);
		const [r, g, b, a] = leinwand.getImageData(0, 0, 1, 1).data;
		return [r, g, b, a / 255];
	};
	const leinwand = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!;
	const lin = (v: number) => {
		const s = v / 255;
		return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
	};
	const lum = (c: number[]) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
	const mische = (vorn: number[], a: number, hinten: number[]) => [0, 1, 2].map((i) => vorn[i] * a + hinten[i] * (1 - a));
	const rgb = (c: number[]) => `rgb(${c.slice(0, 3).map(Math.round).join(', ')})`;
	const hatZeichen = (t: string) => /[\p{L}\p{N}]/u.test(t);
	const pfadVon = (el: Element): string => {
		const teile: string[] = [];
		for (let e: Element | null = el; e && e !== document.body && teile.length < 5; e = e.parentElement) {
			const id = e.getAttribute('data-testid');
			const klasse = typeof e.className === 'string' ? e.className.trim().split(/\s+/)[0] : '';
			teile.unshift(`${e.tagName.toLowerCase()}${id ? `[data-testid="${id}"]` : klasse ? `.${klasse}` : ''}`);
		}
		return teile.join(' > ');
	};
	/** Rechteck `r` (Text bzw. Element) erreichbar: nicht winzig, nicht weggeschoben, nicht weggeschnitten. */
	const erreichbar = (el: Element, r: DOMRect): boolean => {
		if (r.width <= 1 || r.height <= 1) return false;
		// Außerhalb des scrollbaren Dokuments (z. B. left:-9999px) ist nicht erreichbar.
		if (r.right + scrollX <= 0 || r.bottom + scrollY <= 0) return false;
		// Von einem nicht scrollbaren Vorfahren (overflow hidden/clip) vollständig weggeschnitten?
		for (let e = el.parentElement; e; e = e.parentElement) {
			const cs = getComputedStyle(e);
			if (!/hidden|clip/.test(`${cs.overflowX} ${cs.overflowY}`)) continue;
			const b = e.getBoundingClientRect();
			if (r.right <= b.left || r.left >= b.right || r.bottom <= b.top || r.top >= b.bottom) return false;
		}
		return true;
	};
	const sichtbar = (el: Element) => el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
	/** Grund aus allen Schichten (außen → innen, Start Weiß), optional mit der Pseudo-Schicht obenauf. */
	const grundVon = (el: Element, pseudo: CSSStyleDeclaration | null) => {
		const kette: CSSStyleDeclaration[] = [];
		for (let e: Element | null = el; e; e = e.parentElement) kette.unshift(getComputedStyle(e));
		if (pseudo) kette.push(pseudo);
		let grund = [255, 255, 255];
		let opazitaet = 1;
		for (const cs of kette) {
			const b = parse(cs.backgroundColor);
			if (b && b[3] > 0) grund = mische(b, b[3], grund);
			opazitaet *= parseFloat(cs.opacity);
		}
		// Von innen nach außen: Bild/Verlauf vor dem ersten deckenden Grund ⇒ nicht berechenbar.
		let berechenbar = true;
		for (let i = kette.length - 1; i >= 0; i--) {
			if (kette[i].backgroundImage !== 'none') {
				berechenbar = false;
				break;
			}
			if ((parse(kette[i].backgroundColor)?.[3] ?? 0) >= 1) break;
		}
		return { grund, opazitaet, berechenbar };
	};
	const marken = Array.from(document.querySelectorAll('[data-testid="brand-wordmark"]'));
	const ausnahmeVon = (el: Element, text: string): Pick<KontrastBefund, 'ausnahme' | 'logoInstanz'> => {
		if (el.closest('[disabled], [aria-disabled="true"]')) return { ausnahme: 'gesperrt', logoInstanz: null };
		if (el.closest('[aria-hidden="true"]') && !hatZeichen(text)) return { ausnahme: 'aria-hidden', logoInstanz: null };
		const marke = el.closest('.typo-row')?.parentElement?.closest('[data-testid="brand-wordmark"]');
		if (marke) return { ausnahme: 'logo', logoInstanz: marken.indexOf(marke) };
		return { ausnahme: null, logoInstanz: null };
	};
	const befunde: KontrastBefund[] = [];
	/** `cs` liefert Schriftfarbe/-größe (Element oder Pseudoelement), `pseudo` die eigene Schicht. */
	const miss = (el: Element, text: string, quelle: KontrastBefund['quelle'], cs: CSSStyleDeclaration, pseudo: CSSStyleDeclaration | null) => {
		const { grund, opazitaet, berechenbar } = grundVon(el, pseudo);
		const farbeRoh = !pseudo && el instanceof SVGElement ? cs.fill : cs.color;
		const vorn = parse(farbeRoh);
		const farbe = vorn ? mische(vorn, vorn[3] * opazitaet, grund) : null;
		const l1 = farbe ? lum(farbe) : NaN;
		const l2 = lum(grund);
		const groesse = parseFloat(cs.fontSize);
		const gewicht = parseInt(cs.fontWeight, 10);
		const gross = groesse >= 24 || (groesse >= 18.66 && gewicht >= 700);
		befunde.push({
			text: text.slice(0, 60),
			tag: el.tagName.toLowerCase(),
			quelle,
			farbeRoh,
			farbe: farbe ? rgb(farbe) : farbeRoh,
			hintergrund: rgb(grund),
			verhaeltnis: Math.round(((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)) * 100) / 100,
			schwelle: gross ? 3 : 4.5,
			schrift: `${cs.fontSize}/${cs.fontWeight}`,
			pfad: pfadVon(el) + (quelle === 'text' || quelle === 'eingabe' ? '' : quelle),
			berechenbar,
			...ausnahmeVon(el, text)
		});
	};
	// 1. Textknoten.
	const gang = document.createTreeWalker(wurzel, NodeFilter.SHOW_TEXT);
	for (let n = gang.nextNode() as Text | null; n; n = gang.nextNode() as Text | null) {
		const text = (n.textContent ?? '').replace(/\s+/g, ' ').trim();
		const el = n.parentElement;
		if (!text || !el || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|OPTION|TITLE|TEXTAREA)$/.test(el.tagName)) continue;
		if (!sichtbar(el)) continue;
		const bereich = document.createRange();
		bereich.selectNodeContents(n);
		if (erreichbar(el, bereich.getBoundingClientRect())) miss(el, text, 'text', getComputedStyle(el), null);
	}
	// 2. Eingabewerte (nicht der Platzhalter: leerer Wert ⇒ nichts zu messen) und Pseudo-Inhalte.
	const ohneWerttext = /^(hidden|checkbox|radio|file|range|color|image)$/;
	const inhaltVon = (c: string, el: Element): string => {
		if (c === 'none' || c === 'normal') return '';
		let t = '';
		for (const m of c.matchAll(/"((?:[^"\\]|\\.)*)"|attr\(\s*([\w-]+)\s*\)|counters?\(/g)) {
			t += m[1] !== undefined ? m[1].replace(/\\(.)/g, '$1') : m[2] ? (el.getAttribute(m[2]) ?? '') : '0';
		}
		return t.replace(/\s+/g, ' ').trim();
	};
	for (const el of [wurzel, ...Array.from(wurzel.querySelectorAll('*'))]) {
		if (!sichtbar(el)) continue;
		const r = el.getBoundingClientRect();
		const eingabe = el instanceof HTMLTextAreaElement || (el instanceof HTMLInputElement && !ohneWerttext.test(el.type));
		const wert = eingabe ? (el as HTMLInputElement).value.replace(/\s+/g, ' ').trim() : '';
		if (wert && erreichbar(el, r)) miss(el, wert, 'eingabe', getComputedStyle(el), null);
		for (const art of ['::before', '::after'] as const) {
			const ps = getComputedStyle(el, art);
			if (ps.display === 'none' || ps.visibility !== 'visible') continue;
			const text = inhaltVon(ps.content, el);
			if (hatZeichen(text) && erreichbar(el, r)) miss(el, text, art, ps, ps);
		}
	}
	return befunde;
}

/** Misst allen sichtbaren Text der Seite (`Page`) bzw. unter einem Element (`Locator`). */
export async function messeKontrast(ziel: Page | Locator): Promise<KontrastBefund[]> {
	const wurzel = 'goto' in ziel ? ziel.locator('body') : ziel;
	return wurzel.evaluate(messeTextknotenImBrowser);
}

/** Verstöße: unter der Schwelle, Farbe nicht lesbar oder Grund nicht berechenbar — und keine Ausnahme. */
export function kontrastVerstoesse(befunde: KontrastBefund[]): KontrastBefund[] {
	return befunde.filter((b) => b.ausnahme === null && (!b.berechenbar || !(b.verhaeltnis >= b.schwelle)));
}

/** Eine Zeile je Verstoß: Seite, Text, Farben, Verhältnis, CSS-Pfad (doppelte zusammengefasst). */
export function kontrastBericht(seite: string, verstoesse: KontrastBefund[]): string[] {
	const zeilen = verstoesse.map((v) =>
		v.berechenbar
			? `${seite} · ${JSON.stringify(v.text)}: ${v.verhaeltnis}:1 < ${v.schwelle} ` +
				`(${v.farbe} auf ${v.hintergrund}, ${v.schrift}) @ ${v.pfad}`
			: `${seite} · ${JSON.stringify(v.text)}: nicht berechenbar (background-image unter dem Text, ` +
				`${v.farbe}, ${v.schrift}) @ ${v.pfad}`
	);
	return [...new Set(zeilen)];
}

// ─────────────────────────────────────────────────────────────────────────────
// Issue #2347 S4 (Epic #2345, Etappe P6): Anlege-Seite und Listenseite je kind.
// Spec: docs/specs/modules/feat_2347_s4_paritaets_e2e.md § „Kind-Kontraste".
//
// Beide Anlege-Seiten bauen ihre Reiterfolge aus `anlegeKette(kind)` und teilen
// das Abschluss-Gate `canFinish`; die SELEKTOREN sind aber je Seite verschieden
// (Befund 2). Diese Tabellen halten nur die Selektor-/Text-Unterschiede — keine
// Assertions, keine Erwartungswerte aus dem Produkt (Werte stehen fest hier).
// ─────────────────────────────────────────────────────────────────────────────

/** Zustand eines Anlege-Reiters, kind-neutral gelesen (Aufrufer pollt). */
export interface AnlegeReiterZustand {
	gesperrt: boolean;
	aktiv: boolean;
	erledigt: boolean;
}

const TRIP_ANLEGE_LABEL: Record<string, string> = {
	route: 'Route',
	etappen: 'Etappen & GPX',
	wegpunkte: 'Wegpunkte prüfen',
	// #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-6): Schritte Wetter und Zustellung.
	wetter: 'Wetter',
	zustellung: 'Zustellung'
};

export const ANLEGE_SEL: Record<
	HubKind,
	{
		url: string;
		/** Sammel-Endpunkt des Anlege-POST. */
		postPfad: string;
		/** Die vier Pflicht-Schritte in Reihenfolge (Trip ohne den optionalen Schritt „Wegpunkte prüfen", #2794 S3a). */
		schritte: readonly string[];
		ersterSchritt: string;
		punkteSchritt: 'etappen' | 'orte';
		/** Spec AN-2 / #2794 S3a: „Fortschritt hat genau 4 Segmente" — fester Wert, nicht aus dem Produkt. */
		fortschrittSegmente: number;
		reiter: (page: Page, id: string, mobil?: boolean) => Locator;
		alleReiterMobil: (page: Page) => Locator;
		zustand: (reiter: Locator) => Promise<AnlegeReiterZustand>;
		fortschritt: (page: Page) => Locator;
		fortschrittSegment: (page: Page) => Locator;
		name: (page: Page, mobil?: boolean) => Locator;
		weiterErsterSchritt: (page: Page) => Locator;
		abschluss: (page: Page, mobil?: boolean) => Locator;
		abschlussLabel: string;
		abschlussHinweis: string;
		mobilFooter: (page: Page) => Locator;
		/**
		 * Desktop-Fuß des geteilten AnlegeRahmen (#2837 S2, AC-16): Trip `tn-desktop-footer`,
		 * Vergleich `cm-desktop-footer` (neu). Trägt Abbrechen (links), Standardwerte, Hinweis
		 * und Hauptaktion (rechts).
		 */
		desktopFuss: (page: Page) => Locator;
		/** Standardwerte-Knopf am Desktop (im Fuß, #2837 S2 AC-10). */
		standardwerte: (page: Page) => Locator;
		/**
		 * Desktop-Abbruch (#2837 S2, AC-5): bei BEIDEN Arten „Abbrechen" (`Btn ghost`) unten links im
		 * Desktop-Fuß. Trip: onCancel (kein Autosave), Vergleich: Link auf /compare. Vorher Trip
		 * „Zurück: Trips" im Kopf, Vergleich „Abbrechen" oben rechts in der Kopfleiste.
		 */
		abbrechen: (page: Page) => Locator;
		/**
		 * Inhalt der geteilten Schwanz-Schritte (Desktop), benannt nach dem INHALT: Metrik-Oberfläche
		 * und Wertebereiche im Schritt Wetter, Alarme im Schritt Zustellung (#2794 S3a).
		 */
		inhalt: Record<'wetter-metriken' | 'wertebereiche' | 'alarme', (page: Page) => Locator>;
		/**
		 * Desktop-Weiter-Fuß der Schwanz-Schritte, benannt nach dem ZIEL (AN-15, Alt s8d
		 * AC-17/AC-18). #2794 S3a: nur noch im Schritt Wetter „Zustellung einrichten →" Richtung Zustellung.
		 */
		weiterNach: Record<'zustellung', (page: Page) => Locator>;
		/** Kennungs-Präfix aller Desktop-Weiter-Füße der Art (AN-15: im letzten Schritt keiner sichtbar). */
		weiterPraefix: string;
		/** Profil/Aktivität: gültiger Zielwert, verschieden vom Startwert. */
		profilWert: string;
	}
> = {
	route: {
		url: '/trips/new',
		postPfad: '/api/trips',
		schritte: ['route', 'etappen', 'wetter', 'zustellung'],
		ersterSchritt: 'route',
		punkteSchritt: 'etappen',
		fortschrittSegmente: 4,
		// Trip-Reiter: <div role="tab">/<button role="tab"> ohne Kennung (Kind-Kontraste
		// „AN Reiter-Zustand") — Auswahl über die Beschriftung.
		reiter: (page, id, mobil = false) =>
			page
				.locator(mobil ? '[data-testid="tn-mobile-tabbar"] [role="tab"]' : '.tn-desktop [role="tab"]')
				.filter({ hasText: new RegExp(`^\\s*${regexEscape(TRIP_ANLEGE_LABEL[id] ?? id)}`) }),
		alleReiterMobil: (page) => page.locator('[data-testid="tn-mobile-tabbar"] [role="tab"]'),
		// Geteilter Baustein AnlegeReiter (#2880): seit #2881 Lieferung B Punkte statt ✓/⊘ — Zustand
		// über aria-disabled (gesperrt), aria-selected (aktiv) und data-done (erledigt).
		zustand: async (reiter) => ({
			gesperrt: (await reiter.getAttribute('aria-disabled')) === 'true',
			aktiv: (await reiter.getAttribute('aria-selected')) === 'true',
			erledigt: (await reiter.getAttribute('data-done')) === 'true'
		}),
		// Rein attributive Kennungen, im Zuge von AC-20 nachgetragen (TripNewEditor.svelte,
		// Fortschrittsbalken `trip-new-progress`/`trip-new-progress-segment`, Spec „AC-20-Nachträge").
		fortschritt: (page) => page.locator('[data-testid="trip-new-progress"]:visible'),
		fortschrittSegment: (page) => page.locator('[data-testid="trip-new-progress-segment"]:visible'),
		name: (page, mobil = false) => page.getByTestId(`trip-new-name-input-${mobil ? 'mobile' : 'desktop'}`),
		weiterErsterSchritt: (page) => page.getByTestId('trip-new-continue-etappen'),
		abschluss: (page, mobil = false) => page.getByTestId(mobil ? 'tn-mobile-save' : 'trip-new-save-btn'),
		// #2837 S2 AC-12: Desktop UND mobil „Trip speichern" (vorher mobil „Speichern").
		abschlussLabel: 'Trip speichern',
		abschlussHinweis: 'Alarme einrichten zum Speichern',
		mobilFooter: (page) => page.getByTestId('tn-mobile-footer'),
		desktopFuss: (page) => page.getByTestId('tn-desktop-footer'),
		standardwerte: (page) => page.getByTestId('trip-new-standardwerte-btn'),
		abbrechen: (page) =>
			page.getByTestId('tn-desktop-footer').locator('[data-slot="btn"]').filter({ hasText: /^\s*Abbrechen\s*$/ }),
		inhalt: {
			// #2794 Teil 3 (Spec feat_2794_s3a_teil3_wetter.md §4): Schritt Wetter = WetterTab; die
			// Wertebereiche sind die Ampel-Grenzen der Metrik-Zeilen („Grenzen ändern").
			'wetter-metriken': (page) => page.locator('.tn-desktop [data-testid="wetter-tab"][data-context="route"]'),
			wertebereiche: (page) =>
				page.locator('.tn-desktop [data-testid="wetter-tab"][data-context="route"] [data-testid^="wetter-grenzen-aendern-"]').first(),
			alarme: (page) => page.locator('.tn-desktop [data-testid="alarme-tab"]')
		},
		weiterNach: {
			zustellung: (page) => page.locator('.tn-desktop [data-testid="trip-new-continue-zustellung"]')
		},
		weiterPraefix: 'trip-new-continue-',
		profilWert: 'hochtour'
	},
	vergleich: {
		url: '/compare/new',
		postPfad: '/api/compare/presets',
		schritte: ['vergleich', 'orte', 'wetter', 'zustellung'],
		ersterSchritt: 'vergleich',
		punkteSchritt: 'orte',
		fortschrittSegmente: 4,
		reiter: (page, id, mobil = false) =>
			page.getByTestId(mobil ? `cm-mobile-tab-${id}` : `compare-editor-tab-${id}`),
		alleReiterMobil: (page) => page.locator('[data-testid^="cm-mobile-tab-"]'),
		zustand: async (reiter) => ({
			gesperrt: (await reiter.getAttribute('data-locked')) === 'true',
			aktiv: (await reiter.getAttribute('data-active')) === 'true',
			erledigt: (await reiter.getAttribute('data-done')) === 'true'
		}),
		fortschritt: (page) => page.locator('[data-testid="compare-editor-progress"]:visible'),
		fortschrittSegment: (page) => page.locator('[data-testid="compare-editor-progress-segment"]:visible'),
		name: (page, mobil = false) => page.getByTestId(mobil ? 'compare-editor-name-mobile' : 'compare-editor-name'),
		weiterErsterSchritt: (page) => page.getByTestId('compare-editor-continue-orte'),
		abschluss: (page, mobil = false) => page.getByTestId(mobil ? 'cm-mobile-activate' : 'compare-editor-activate'),
		abschlussLabel: 'Briefing aktivieren',
		abschlussHinweis: 'Alarme einrichten zum Aktivieren',
		mobilFooter: (page) => page.getByTestId('cm-mobile-cta'),
		desktopFuss: (page) => page.getByTestId('cm-desktop-footer'),
		standardwerte: (page) => page.getByTestId('compare-editor-standardwerte'),
		abbrechen: (page) =>
			page.getByTestId('cm-desktop-footer').locator('[data-slot="btn"]').filter({ hasText: /^\s*Abbrechen\s*$/ }),
		inhalt: {
			// #2794 Teil 3 (Spec feat_2794_s3a_teil3_wetter.md §4): Schritt Wetter = WetterTab; die
			// Wertebereiche sind die Ampel-Grenzen der Metrik-Zeilen („Grenzen ändern").
			'wetter-metriken': (page) => page.locator('.cm-desktop [data-testid="wetter-tab"][data-context="vergleich"]'),
			wertebereiche: (page) =>
				page.locator('.cm-desktop [data-testid="wetter-tab"][data-context="vergleich"] [data-testid^="wetter-grenzen-aendern-"]').first(),
			alarme: (page) => page.locator('.cm-desktop [data-testid="alarme-tab"]')
		},
		weiterNach: {
			zustellung: (page) => page.locator('.cm-desktop [data-testid="compare-editor-continue-zustellung"]')
		},
		weiterPraefix: 'compare-editor-continue-',
		profilWert: 'wintersport'
	}
};

/** Listenseite je kind (HL): Texte fest, Strukturaussagen gemeinsam (Kind-Kontraste „HL Liste"). */
export const LISTE_SEL: Record<
	HubKind,
	{
		url: string;
		titel: string;
		anlegeUrl: string;
		/** Mobiler „Neu"-Knopf im Seitenkopf (Trip: im Zuge von AC-20 nachgetragen, routes/trips/+page.svelte). */
		neuMobil: string;
		/**
		 * Beschriftung des Desktop-„Neu"-Knopfs im Listenkopf (AN-13). Trip: `<button>` mit
		 * goto, Vergleich: Link — die Aussage (Klick führt zur Anlege-Seite) ist gleich.
		 */
		neuDesktop: string;
		introKurz: string;
		introLang: string;
		suche: string;
		statLabel: string;
	}
> = {
	route: {
		url: '/trips',
		titel: 'Trips',
		anlegeUrl: '/trips/new',
		neuMobil: 'trip-list-new-mobile',
		neuDesktop: '+ Neuer Trip',
		introKurz: 'Mehrtages-Trips mit Briefings je Etappe — morgens für heute, abends für morgen.',
		introLang: 'Alle aktiven, geplanten und abgeschlossenen Mehrtages-Trips.',
		suche: 'Suchen...',
		statLabel: 'Aktiv'
	},
	vergleich: {
		url: '/compare',
		titel: 'Orts-Vergleiche',
		anlegeUrl: '/compare/new',
		neuMobil: 'compare-list-new-mobile',
		neuDesktop: '+ Neuer Vergleich',
		introKurz: 'Ohne Ranking — läuft, bis du stoppst.',
		introLang: 'Morgen-Briefing für heute, Abend-Briefing für morgen',
		suche: 'Suchen…',
		statLabel: 'Aktiv'
	}
};

const ANLEGE_GPX = path.resolve('./e2e/fixtures/test-trip.gpx');

/**
 * Datum in den Baustein molecules/DatumFeld tippen (#2881 Lieferung B, ersetzt `fill()` auf
 * `input[type="date"]`): Tag-Segment anklicken, dann TTMMJJJJ — de und en zeigen beide den Tag
 * zuerst. `feld` ist der Baustein (data-slot="datum-feld") oder ein Behälter mit genau einem.
 */
export async function tippeDatum(page: Page, feld: Locator, iso: string): Promise<void> {
	const [jahr, monat, tag] = iso.split('-');
	await feld.locator('[data-segment="day"]').click();
	await page.keyboard.type(`${tag}${monat}${jahr}`);
}

/** Anzeige des Bausteins DatumFeld (de) für ein ISO-Datum: `2026-11-19` → `19.11.2026`. */
export const datumAnzeige = (iso: string): string => iso.split('-').reverse().join('.');

/** Eingabebereich (Segmente) eines DatumFeld/UhrzeitFeld — für toHaveText statt toHaveValue. */
export const feldEingabe = (feld: Locator): Locator =>
	feld.locator('[data-slot="datum-feld-eingabe"], [data-slot="uhrzeit-feld-eingabe"]');

/** Uhrzeit `HH:MM` in den Baustein molecules/UhrzeitFeld tippen (#2881 Lieferung B). */
export async function tippeUhrzeit(page: Page, feld: Locator, hhmm: string): Promise<void> {
	await feld.locator('[data-segment="hour"]').click();
	await page.keyboard.type(hhmm.replace(':', ''));
}

/**
 * Wert im Auswahl-Baustein ui/select (bits-ui Select, #2881 Lieferung B) wählen — ersetzt
 * `selectOption()` auf dem früheren nativen <select>. `ausloeser` ist der Knopf (aria-haspopup="listbox").
 */
export async function waehleOption(page: Page, ausloeser: Locator, beschriftung: string | RegExp): Promise<void> {
	await ausloeser.click();
	const liste = page.getByRole('listbox');
	await expect(liste).toBeVisible();
	await liste.getByRole('option', { name: beschriftung, exact: typeof beschriftung === 'string' }).click();
	// Geschlossen = keine offene Liste mehr. Nicht toBeHidden: bei angehaltener Seiten-Uhr
	// (page.clock, z. B. VS-1) bleibt die Liste im Ausblend-Zustand (data-state="closed") stehen.
	await expect(page.locator('[role="listbox"][data-state="open"]')).toHaveCount(0);
	await expect(ausloeser).toHaveAttribute('data-state', 'closed');
}

/**
 * Trip-Anlegen, Schritt Etappen (bereits geöffnet): je Etappe eine GPX hochladen und auf
 * `/api/gpx/parse` warten (herausgehoben aus anlegenPflicht, #2881 Lieferung B).
 */
export async function tripGpxHochladen(page: Page, mobil = false): Promise<void> {
	const eingaben = page.locator(`${mobil ? '.tn-mobile' : '.tn-desktop'} input[type="file"][accept=".gpx"]`);
	await expect(eingaben.first()).toBeAttached();
	let rest = await eingaben.count();
	while (rest > 0) {
		const geparst = page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 });
		await eingaben.first().setInputFiles(ANLEGE_GPX);
		await geparst;
		rest -= 1;
		await expect(eingaben).toHaveCount(rest);
	}
}

export interface AnlegenPflichtOpts {
	name: string;
	/** Trip-Pflichtfeld Startdatum (YYYY-MM-DD); Standard: in 7 Tagen. */
	datum?: string;
	mobil?: boolean;
	/** Viewport vor dem Öffnen setzen (Aufrufer mit eigenen Maßen, z. B. 375×812). */
	viewport?: { width: number; height: number };
	/** Nur der erste Schritt (Name; Trip zusätzlich Datum) — der Punkte-Schritt bleibt offen. */
	nurKopf?: boolean;
	/**
	 * Vergleich: zu wählende Orte (Standard: zwei frische Test-Orte, Präfix E2E-GZ-).
	 * Eigene Orte müssen vor dem Aufruf angelegt sein (die Bibliothek lädt beim goto).
	 */
	orte?: TestLocation[];
}

/**
 * Pflichtangaben der Anlege-Seite je kind (Kind-Kontraste „AN Pflichtangaben"):
 * Trip = Name + Startdatum, je Etappe eine GPX (`/api/gpx/parse`);
 * Vergleich = Name, dann zwei Orte aus der Bibliothek.
 * Herausgehoben aus `tripPflicht` (standardwerte-und-hilfe.spec.ts) — Trip-Verhalten
 * unverändert. Öffnet die Anlege-Seite selbst; keine Assertions über das Ergebnis.
 */
export async function anlegenPflicht(page: Page, kind: HubKind, opts: AnlegenPflichtOpts): Promise<void> {
	const mobil = opts.mobil ?? false;
	if (opts.viewport) await page.setViewportSize(opts.viewport);
	// Vergleich: die Orte-Bibliothek lädt der SSR-Loader von /compare/new
	// (routes/compare/new/+page.server.ts) genau einmal beim Seitenaufruf — Test-Orte
	// müssen daher VOR dem goto existieren, sonst stehen sie nie in der Bibliothek.
	const orte =
		kind === 'vergleich' && !opts.nurKopf
			? (opts.orte ?? [
					await createTestLocation(page.request, { lat: 47.1, lon: 11.2 }),
					await createTestLocation(page.request, { lat: 47.2, lon: 11.3 })
				])
			: [];
	await page.goto(ANLEGE_SEL[kind].url);
	if (kind === 'route') {
		const datum = opts.datum ?? new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10);
		// Reiter über die Kennung (sprachunabhängig, #2881 Lieferung B; vorher Beschriftung /Etappen/).
		const etappen = page.getByTestId(mobil ? 'tn-mobile-tab-etappen' : 'trip-new-tab-etappen');
		await expect(async () => {
			await ANLEGE_SEL.route.name(page, mobil).fill(opts.name);
			await tippeDatum(page, page.getByTestId(mobil ? 'trip-new-date-input' : 'trip-new-date-input-desktop'), datum);
			await expect(etappen).not.toHaveAttribute('aria-disabled', 'true', { timeout: 500 });
		}).toPass({ timeout: 10_000 });
		if (opts.nurKopf) return;
		await etappen.click({ force: mobil });
		await tripGpxHochladen(page, mobil);
		return;
	}
	await expect(page.getByTestId('compare-editor')).toBeVisible({ timeout: 15_000 });
	await ANLEGE_SEL.vergleich.name(page, mobil).fill(opts.name);
	if (opts.nurKopf) return;
	await ANLEGE_SEL.vergleich.reiter(page, 'orte', mobil).click();
	if (mobil) {
		await page.getByTestId('compare-step2-mobile-library-btn').click();
		for (const ort of orte) await page.getByTestId(`compare-step2-mobile-lib-check-${ort.id}`).click();
		await page.locator('button[aria-label="Schliessen"]:visible').click();
		return;
	}
	const bibliothek = page.locator('[data-testid="compare-step2-library"]:visible').first();
	await expect(bibliothek).toBeVisible({ timeout: 10_000 });
	for (const ort of orte) await bibliothek.getByText(ort.name, { exact: true }).click();
}
