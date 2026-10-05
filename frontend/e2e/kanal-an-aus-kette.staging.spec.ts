// E2E (Staging) — Issue #2422 S3, AC-26 (Bein d) + Mutation M14.
//
// Spec: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md
//   AC-26: Nutzer hakt im Versand-Reiter "Abend aktiv" ab und speichert ->
//   GET /api/trips/{id} bestaetigt enabled=true / morning_enabled=true /
//   evening_enabled=false -> EIN Sammellauf fuer genau diesen Nutzer ->
//   im Test-Postfach liegt GENAU EINE Trip-Briefing-Mail (Morgen) und KEINE
//   Abend-Mail; die Mail besteht briefing_mail_validator.py mit Exit 0.
//
// M14 (Verdrahtung): streicht jemand in VersandTab.svelte `evening_enabled` aus
// dem Payload, bleibt der Bausteintest der reinen Funktion (AC-22) gruen --
// nur DIESER Test faengt es, weil er den echten Klick, den echten PUT und den
// echten Versand durchlaeuft.
//
// ---------------------------------------------------------------------------
// Aufbau (jede Entscheidung hat einen Grund)
//
// * WEGWERF-NUTZER, genau ein Trip. Der Sammellauf betrifft nur diesen Nutzer:
//   ausgeloest wird am Python-Kern von Staging (127.0.0.1:8001), dessen Route
//   `POST /api/scheduler/trip-reports?user_id=<id>` den Lauf per Pflicht-
//   Parameter auf einen Nutzer begrenzt. Der Go-Weg gleichen Namens ist seit
//   #2155 (ADR-0078, RequireAdmin) nur fuer Admins offen — auf Staging gibt es
//   keinen (GZ_ADMIN_USER_IDS leer), ein Wegwerf-Nutzer bekommt dort 403.
//   Kein Sammel-Versand ueber alle Nutzer/Trips.
//   Ein vorhandenes Konto (admin, Validator) haette weitere Trips.
//
// * SAMMELLAUF, nicht Einzelversand. Der Einzelversand
//   `/api/scheduler/trips/{id}/send` umgeht `_get_active_trips` — genau dort
//   sitzt der Fix. Ein Test darueber waere auch ohne Fix gruen.
//
// * `at=<ISO>` statt Uhr. Beide Slots (Morgen/Abend) stehen auf DIESELBE
//   Stunde; `at` liegt in dieser Ortsstunde des Trips (Europe/Vienna, Innsbruck-
//   Koordinaten, `trip_tz`). Die Stunde wird so gewaehlt, dass sie NICHT im
//   3-Stunden-Nachholfenster (NACHHOL_FENSTER_STUNDEN) der echten Uhr liegt —
//   so kann der echte Staging-Cron waehrend des Tests nicht zwischen Anlage und
//   Lauf schon feuern. Ohne Fix sind BEIDE Slots faellig: count == 2.
//
// * Mail landet im Test-Postfach: Staging erzwingt den Stalwart-Versand
//   (config.py `force_test`), Empfaenger = `mail_to` des Kontos. Das Konto wird
//   mit `gregor-test+<nutzer>@henemm.com` registriert (Plus-Adresse: die exakte
//   Adresse gehoert bereits einem echten Konto -> 409 email_taken; der
//   Stalwart-Empfaenger-Waechter laesst Plus-Adressen durch,
//   tests/tdd/test_stalwart_recipient_guard.py AC-3). NOCH NICHT GEMESSEN: dass
//   Stalwart die Plus-Adresse in das Postfach `gregor-test` ausliefert — die
//   Positivkontrolle (Morgen-Mail muss ankommen) faengt das ab: kommt sie nicht,
//   ist der Test ROT mit klarer Meldung, nie faelschlich gruen.
//
// * IMAP per Python-stdlib (execFileSync): im Frontend gibt es keine IMAP-
//   Bibliothek. Zugangsdaten NUR aus der Umgebung (GZ_TEST_IMAP_USER/_PASS,
//   NICHT die generischen GZ_IMAP_* — die zeigen auf das Inbound-Postfach),
//   nichts wird geschrieben oder ausgegeben. Filter: eindeutiges Token in
//   Etappen-/Trip-Name (das Postfach ist mit Parallelsitzungen geteilt).
//
// * "keine Abend-Mail" zaehlt nur MIT Positivkontrolle: erst muss die
//   Morgen-Mail da sein, dann wird nach einer Schonfrist neu gezaehlt.
//
// ---------------------------------------------------------------------------
// Selektoren-Strategie (Scoping): alles im Panel `trip-detail-panel-versand`
// (der Versand-Reiter), darin `evening-master-switch` -> native Checkbox.
// Klickpfad ueber `trip-detail-tab-versand` (kein goto mit ?tab=...).
// Speichern ist Autosave (BriefingScheduleTab, saveController): gewartet wird
// auf den echten `PUT /api/trips/{id}`, nicht auf eine Pause.
//
// ---------------------------------------------------------------------------
// Mail-Validator (PFLICHT vor "E2E bestanden", Trip-Briefing-Pfad):
//   uv run python3 .claude/hooks/briefing_mail_validator.py \
//     --mail-type trip-briefing --subject-contains <TOKEN>
// Der Test ruft ihn am Ende selbst auf (Exit 0 Pflicht); das Token steht in der
// Fehlermeldung / in test.info().annotations.
//
// Ausfuehren (gegen Staging, aus frontend/; Zugangsdaten nie im Klartext):
//   set -a
//   source /home/hem/gregor_zwanzig/.claude/validator.env        # nginx-Basic-Auth
//   source /home/hem/gregor_zwanzig_staging/.env                 # GZ_AUTH_*, GZ_TEST_IMAP_*
//   set +a
//   npx playwright test --config=e2e/playwright.kanal-an-aus-kette.staging.config.ts \
//     e2e/kanal-an-aus-kette.staging.spec.ts
//
// Diese Spec laeuft NICHT in der CI-Ampel und steht NICHT in
// .github/ci_e2e_specs.txt (Filter A schliesst *.staging.spec.ts aus; sie
// braucht Staging, echtes IMAP und einen Sammellauf). Sie wird in /e2e-verify
// nach Fix + Staging-Deploy gefahren. OHNE Fix ist sie beabsichtigt ROT
// (Sammellauf liefert count == 2, Abend-Mail liegt im Postfach).
//
// Bekannte Grenze: die Registrierung ist auf 5/Stunde je IP begrenzt
// (registerLimiter) — ein Test-Lauf verbraucht einen Platz.

import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	test,
	expect,
	type APIRequestContext,
	type Browser,
	type BrowserContext,
	request as apiRequest
} from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');

const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
const NGINX_USER = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const NGINX_PASS = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';
const APP_USER = process.env.GZ_AUTH_USER ?? process.env.E2E_USER ?? 'admin';
const APP_PASS = process.env.GZ_AUTH_PASS ?? process.env.E2E_PASS ?? 'test1234';

// Trip-Zeitzone: Innsbruck-Koordinaten -> tz_for_coords == Europe/Vienna.
const TRIP_TZ = 'Europe/Vienna';
const NACHHOL_FENSTER_STUNDEN = 3; // src/services/trip_report_scheduler.py

// ---------------------------------------------------------------------------
// Zeit-Helfer: Ortszeit des Trips ausrechnen (nie UTC, nie Zone des Runners)
// ---------------------------------------------------------------------------

interface Ortszeit {
	datum: string; // YYYY-MM-DD
	stunde: number;
}

function ortszeit(instant: Date): Ortszeit {
	const teile = new Intl.DateTimeFormat('en-CA', {
		timeZone: TRIP_TZ,
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		hour: '2-digit',
		hourCycle: 'h23'
	}).formatToParts(instant);
	const feld = (typ: string) => teile.find((t) => t.type === typ)?.value ?? '';
	return {
		datum: `${feld('year')}-${feld('month')}-${feld('day')}`,
		stunde: Number(feld('hour'))
	};
}

function tagPlus(datum: string, tage: number): string {
	const [j, m, t] = datum.split('-').map(Number);
	return new Date(Date.UTC(j, m - 1, t + tage)).toISOString().slice(0, 10);
}

/** UTC-Zeitpunkt, an dem es in Wien am Ortstag `datum` genau `stunde`:00 ist. */
function utcFuerOrtszeit(datum: string, stunde: number): Date {
	const [j, m, t] = datum.split('-').map(Number);
	const roh = Date.UTC(j, m - 1, t, stunde, 0, 0);
	for (const offsetStunden of [1, 2]) {
		const kandidat = new Date(roh - offsetStunden * 3_600_000);
		const o = ortszeit(kandidat);
		if (o.datum === datum && o.stunde === stunde) return kandidat;
	}
	throw new Error(`Kein UTC-Zeitpunkt fuer ${datum} ${stunde}:00 ${TRIP_TZ} gefunden`);
}

/** Versandstunde (beide Slots gleich) + Laufzeitpunkt `at`. Die Stunde liegt
 * ausserhalb des Nachholfensters der echten Ortsstunde -> der echte Cron kann
 * diesen Trip zwischen Anlage und Sammellauf nicht ausliefern. */
function planeLauf(): { heute: string; morgen: string; stunde: number; at: string } {
	const jetzt = ortszeit(new Date());
	// Echte Ortsstunde 04..11 -> Versandstunde 15 (Fenster 15..17); sonst 07 (Fenster 07..09).
	const stunde = jetzt.stunde >= 4 && jetzt.stunde < 12 ? 15 : 7;
	if (jetzt.stunde >= stunde && jetzt.stunde < stunde + NACHHOL_FENSTER_STUNDEN) {
		throw new Error(`Interner Planungsfehler: Stunde ${stunde} liegt im echten Fenster`);
	}
	return {
		heute: jetzt.datum,
		morgen: tagPlus(jetzt.datum, 1),
		stunde,
		// ISO-8601 mit Offset, ohne Millisekunden — von `fromisoformat` in jeder Python-Version lesbar.
		at: utcFuerOrtszeit(jetzt.datum, stunde).toISOString().replace(/\.\d{3}Z$/, '+00:00')
	};
}

// ---------------------------------------------------------------------------
// Wegwerf-Nutzer (registrieren -> Token (Admin-Sitzung) -> bestaetigen -> anmelden)
// ---------------------------------------------------------------------------

async function neuerKontext(): Promise<APIRequestContext> {
	return apiRequest.newContext({
		baseURL: BASE,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: NGINX_USER, password: NGINX_PASS }
	});
}

/** Wie helpers.ts::registriereBestaetigtenZweitnutzer, aber mit frei
 * waehlbarer Adresse (dort fest `@example.com`, die kein Postfach erreicht). */
async function registriereMitAdresse(
	admin: APIRequestContext,
	gast: APIRequestContext,
	username: string,
	password: string,
	email: string
): Promise<void> {
	const reg = await gast.post('/api/auth/register', { data: { username, password, email } });
	if (![200, 201].includes(reg.status())) {
		throw new Error(`Registrierung fehlgeschlagen: HTTP ${reg.status()} ${await reg.text()}`);
	}
	const tokenAntwort = await admin.post('/api/auth/verify-email/staging-token', {
		data: { username }
	});
	if (!tokenAntwort.ok()) {
		throw new Error(`Staging-Token-Testweg antwortet HTTP ${tokenAntwort.status()}`);
	}
	const { token } = (await tokenAntwort.json()) as { token?: string };
	if (!token) throw new Error('Staging-Token-Testweg lieferte kein Token');
	const ok = await gast.post('/api/auth/verify-email', { data: { user: username, token } });
	if (!ok.ok()) throw new Error(`Bestaetigung fehlgeschlagen: HTTP ${ok.status()}`);
	const login = await gast.post('/api/auth/login', { data: { username, password } });
	if (!login.ok()) throw new Error(`Login fehlgeschlagen: HTTP ${login.status()}`);
}

// ---------------------------------------------------------------------------
// IMAP (Python-stdlib; Zugangsdaten nur aus der Umgebung, keine Ausgabe davon)
// ---------------------------------------------------------------------------

interface Mail {
	subject: string;
	to: string;
	mailType: string;
}

const IMAP_SNIPPET = `
import email, imaplib, json, os, sys
from email.header import decode_header, make_header
token = sys.argv[1]
imap = imaplib.IMAP4_SSL(
    os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
    int(os.environ.get("GZ_IMAP_PORT", "993")),
    timeout=20,
)
imap.login(os.environ["GZ_TEST_IMAP_USER"], os.environ["GZ_TEST_IMAP_PASS"])
imap.select("INBOX", readonly=True)
_, data = imap.search(None, "ALL")
treffer = []
ids = data[0].split()[-200:]
if ids:
    # EIN FETCH ueber den ganzen Bereich (nicht 200 Einzelabrufe je Poll-Runde).
    _, teile = imap.fetch(ids[0].decode() + ":" + ids[-1].decode(),
                          "(BODY.PEEK[HEADER.FIELDS (SUBJECT TO X-GZ-MAIL-TYPE)])")
    for teil in teile:
        if not isinstance(teil, tuple):
            continue
        msg = email.message_from_bytes(teil[1])
        subject = str(make_header(decode_header(msg.get("Subject", ""))))
        if token in subject:
            treffer.append({
                "subject": subject,
                "to": str(make_header(decode_header(msg.get("To", "")))),
                "mailType": msg.get("X-GZ-Mail-Type", ""),
            })
imap.logout()
print(json.dumps(treffer))
`;

function mailsMitToken(token: string): Mail[] {
	for (const pflicht of ['GZ_TEST_IMAP_USER', 'GZ_TEST_IMAP_PASS']) {
		if (!process.env[pflicht]) {
			throw new Error(`${pflicht} fehlt in der Umgebung (Test-Postfach gregor-test, nicht GZ_IMAP_*)`);
		}
	}
	const out = execFileSync('python3', ['-c', IMAP_SNIPPET, token], {
		env: process.env,
		encoding: 'utf-8',
		timeout: 60_000
	});
	return JSON.parse(out.trim().split('\n').pop() ?? '[]') as Mail[];
}

const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

test.describe('Issue #2422 S3 AC-26: Abend aus im Editor => kein Abend-Briefing auf Staging', () => {
	let admin: APIRequestContext;
	let gast: APIRequestContext;
	let gastKontext: BrowserContext | undefined;
	const GAST_PASSWORT = 'test1234';
	let username = '';
	let tripId = '';

	test.afterAll(async () => {
		// Aufraeumen in dieser Reihenfolge: Trip, dann Konto (loescht alle
		// Nutzerdaten) — ein mail-faehiger Rest wuerde sonst weiter feuern.
		if (gast && tripId) await gast.delete(`/api/trips/${tripId}`).catch(() => {});
		// #2160: Kontoloeschung verlangt Re-Auth - der Gast ist ein Passwort-Konto.
		if (gast && username) {
			const geloescht = await gast.post('/api/auth/account/delete', {
				data: { password: GAST_PASSWORT }
			});
			// AC-20: der Aufraeumschritt muss das Konto wirklich wegraeumen -
			// ein stilles 403/400 liesse einen mail-faehigen Rest zurueck.
			expect(geloescht.status(), `Konto-Aufraeumen HTTP ${geloescht.status()}`).toBe(200);
		}
		await gastKontext?.close().catch(() => {});
		await gast?.dispose().catch(() => {});
		await admin?.dispose().catch(() => {});
	});

	test('AC-26: "Abend aktiv" abhaken + speichern -> GET bestaetigt -> Sammellauf -> genau EINE Morgen-Mail, keine Abend-Mail, Validator Exit 0', async ({
		browser
	}: {
		browser: Browser;
	}) => {
		assertNotProdBaseURL(BASE);

		const suffix = randomBytes(4).toString('hex');
		const token = `KAK${suffix.toUpperCase()}`; // eindeutig im Betreff (Trip- UND Etappenname)
		username = `e2e2422s3${suffix}`;
		tripId = `e2e-2422-s3-${suffix}`;
		const passwort = GAST_PASSWORT;
		const plan = planeLauf();
		test.info().annotations.push({ type: 'mail-token', description: token });

		// --- Wegwerf-Nutzer -------------------------------------------------
		admin = await neuerKontext();
		const adminLogin = await admin.post('/api/auth/login', {
			data: { username: APP_USER, password: APP_PASS }
		});
		expect(adminLogin.ok(), `Admin-Login HTTP ${adminLogin.status()}`).toBeTruthy();
		gast = await neuerKontext();
		const empfaenger = `gregor-test+${username}@henemm.com`;
		await registriereMitAdresse(admin, gast, username, passwort, empfaenger);

		// Empfaenger-Vorbedingung: sonst waere "keine Mail" ohne Aussage.
		const profil = await gast.get('/api/auth/profile');
		expect(profil.ok(), `GET profile HTTP ${profil.status()}`).toBeTruthy();
		const profilJson = (await profil.json()) as { id?: string; mail_to?: string };
		expect(profilJson.mail_to, 'mail_to des Wegwerf-Nutzers').toBe(empfaenger);
		const nutzerId = profilJson.id ?? '';
		expect(nutzerId, 'Profil des Wegwerf-Nutzers traegt eine Kennung').not.toBe('');

		// --- Genau EIN Trip: Etappen heute + morgen, beide Slots gleiche Stunde ---
		const zeit = `${String(plan.stunde).padStart(2, '0')}:00:00`;
		const etappe = (nr: 0 | 1, datum: string) => ({
			id: `${tripId}-s${nr}`,
			name: `Etappe ${token} ${nr === 0 ? 'heute' : 'morgen'}`,
			date: datum,
			waypoints: [
				{ id: `${tripId}-s${nr}a`, name: 'Start', lat: 47.2692 + nr * 0.02, lon: 11.4041 + nr * 0.02, elevation_m: 600 + nr * 300 },
				{ id: `${tripId}-s${nr}b`, name: 'Ziel', lat: 47.2892 + nr * 0.02, lon: 11.4241 + nr * 0.02, elevation_m: 900 + nr * 300 }
			]
		});
		const anlage = await gast.post('/api/trips', {
			data: {
				id: tripId,
				name: `E2E 2422 S3 ${token}`,
				stages: [etappe(0, plan.heute), etappe(1, plan.morgen)],
				report_config: {
					enabled: true,
					morning_enabled: true,
					evening_enabled: true,
					morning_time: zeit,
					evening_time: zeit,
					send_email: true,
					send_telegram: false,
					send_sms: false,
					send_premium_sms: false
				}
			}
		});
		expect([200, 201], `Trip-Anlage HTTP ${anlage.status()}`).toContain(anlage.status());
		const trips = await (await gast.get('/api/trips')).json();
		expect(
			(trips as Array<{ id: string }>).map((t) => t.id),
			'Wegwerf-Nutzer hat genau EINEN Trip'
		).toEqual([tripId]);

		// --- Echter Browser: Versand-Reiter, "Abend aktiv" abhaken ------------
		gastKontext = await browser.newContext({
			baseURL: BASE,
			ignoreHTTPSErrors: true,
			httpCredentials: { username: NGINX_USER, password: NGINX_PASS },
			storageState: await gast.storageState()
		});
		const page = await gastKontext.newPage();
		await page.setViewportSize({ width: 1440, height: 900 });
		await page.goto(`/trips/${tripId}`);
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 15_000 });
		await page.getByTestId('trip-detail-tab-versand').first().click();
		const panel = page.getByTestId('trip-detail-panel-versand');
		await expect(panel).toBeVisible();

		const morgenSchalter = panel.getByTestId('morning-master-switch').locator('input[type="checkbox"]');
		const abendSchalter = panel.getByTestId('evening-master-switch').locator('input[type="checkbox"]');
		await expect(morgenSchalter).toBeChecked();
		await expect(abendSchalter).toBeChecked();

		// Nur ein PUT, dessen Nutzlast "Abend aus" traegt, zaehlt (ein Mount-PUT
		// darf den Wartepunkt nicht erfuellen). Bleibt er aus (M14: Payload-Funktion
		// nicht mehr aufgerufen -> Inhalt unveraendert -> kein PUT), wird das NICHT
		// als Timeout-Flake verbucht, sondern beim GET unten benannt.
		const abendPut = page
			.waitForResponse(
				(r) =>
					r.url().includes(`/api/trips/${tripId}`) &&
					r.request().method() === 'PUT' &&
					r.request().postDataJSON()?.report_config?.evening_enabled === false,
				{ timeout: 15_000 }
			)
			.then((r) => r)
			.catch(() => null);
		await abendSchalter.click();
		const put = await abendPut;
		if (put) expect(put.ok(), `Autosave PUT HTTP ${put.status()}`).toBeTruthy();
		await expect(abendSchalter).not.toBeChecked();
		await expect(morgenSchalter).toBeChecked();

		// --- Gespeicherter Stand (hier wird M14 rot) --------------------------
		await expect
			.poll(
				async () =>
					((await (await gast.get(`/api/trips/${tripId}`)).json()).report_config ?? {}).evening_enabled,
				{
					timeout: 10_000,
					message:
						'M14: der Klick auf "Abend aktiv" hat evening_enabled=false NICHT gespeichert ' +
						`(kein PUT mit evening_enabled=false gesehen: ${put ? 'doch gesehen' : 'ausgeblieben'}) — ` +
						'Payload-Verdrahtung in VersandTab/die frühere Report-Config-Section (#2277 S5 entfernt) pruefen'
				}
			)
			.toBe(false);
		const gespeichert = await (await gast.get(`/api/trips/${tripId}`)).json();
		const rc = gespeichert.report_config ?? {};
		expect(rc.enabled, 'enabled bleibt an (ein Slot ist noch aktiv)').toBe(true);
		expect(rc.morning_enabled, 'morning_enabled').toBe(true);
		expect(rc.evening_enabled, 'evening_enabled wurde im Editor abgehakt').toBe(false);
		expect(rc.send_email, 'E-Mail-Kanal bleibt an').toBe(true);
		expect(rc.send_telegram, 'Telegram bleibt aus').not.toBe(true);
		expect(String(rc.morning_time).slice(0, 2), 'Versandzeit unveraendert').toBe(String(plan.stunde).padStart(2, '0'));

		// --- EIN Sammellauf, nur fuer diesen Nutzer --------------------------------
		// Der Go-Weg `/api/scheduler/trip-reports` ist seit #2155 (ADR-0078) nur
		// fuer Admins offen (RequireAdmin, fail-closed) und Staging kennt keinen
		// Admin. Ausgeloest wird deshalb direkt am Python-Kern von Staging — genau
		// die Route, die der Go-Proxy weiterreicht. `user_id` ist dort Pflicht-
		// Parameter und begrenzt den Lauf auf diesen einen Nutzer. Der Fix sitzt in
		// `send_due_reports`/`_get_active_trips` und wird damit an seinem Wirkort
		// gemessen; Klick, PUT und Speicherung davor liefen ueber den echten Go-Weg.
		const kernUrl = process.env.GZ_STAGING_CORE_URL ?? 'http://127.0.0.1:8001';
		// Prod-Sperre: der Produktiv-Kern liegt auf Port 8000, Staging auf 8001.
		expect(new URL(kernUrl).port, 'Kern-URL darf nicht der Produktiv-Kern (8000) sein').not.toBe('8000');
		// Der Kern verlangt das gemeinsame Geheimnis (api/main.py, CORE_AUTH_HEADER);
		// es kommt aus der Staging-Umgebung, wird nie ausgegeben oder geschrieben.
		const kernGeheimnis = process.env.GZ_CORE_SHARED_SECRET ?? '';
		expect(kernGeheimnis, 'GZ_CORE_SHARED_SECRET (Staging-.env) fehlt').not.toBe('');
		const kern = await apiRequest.newContext({
			baseURL: kernUrl,
			extraHTTPHeaders: { 'X-GZ-Core-Auth': kernGeheimnis }
		});
		const lauf = await kern.post(
			`/api/scheduler/trip-reports?user_id=${encodeURIComponent(nutzerId)}&at=${encodeURIComponent(plan.at)}`,
			{ timeout: 150_000 }
		);
		const laufStatus = lauf.status();
		const laufOk = lauf.ok();
		// Antwort VOR dem Schliessen des Kontexts lesen (danach ist sie entsorgt).
		const laufText = await lauf.text();
		await kern.dispose();
		expect(laufOk, `Sammellauf HTTP ${laufStatus}: ${laufText.slice(0, 200)}`).toBeTruthy();
		const ergebnis = JSON.parse(laufText) as { status: string; count: number; failed: number };
		expect(ergebnis.failed, `Sammellauf meldet Fehlschlaege: ${JSON.stringify(ergebnis)}`).toBe(0);
		// Kernaussage: nur der Morgen-Slot war faellig. Ohne Fix: count == 2.
		expect(ergebnis.count, `Sammellauf: genau EIN Versand (Morgen) — ${JSON.stringify(ergebnis)}`).toBe(1);

		// --- Postfach: Positivkontrolle zuerst (Morgen-Mail muss ankommen) ------
		let mails: Mail[] = [];
		for (let i = 0; i < 20; i++) {
			mails = mailsMitToken(token);
			if (mails.some((m) => /—\s*Morgen/.test(m.subject))) break;
			await pause(3_000);
		}
		expect(
			mails.some((m) => /—\s*Morgen/.test(m.subject)),
			`Positivkontrolle: Morgen-Mail mit Token ${token} nicht im Test-Postfach (Lauf: ${JSON.stringify(ergebnis)}; ` +
				`Empfaenger ${empfaenger} — Plus-Adress-Zustellung in Stalwart noch nicht gemessen)`
		).toBeTruthy();

		// Schonfrist, dann neu zaehlen: eine verspaetete Abend-Mail darf nicht durchrutschen.
		await pause(10_000);
		mails = mailsMitToken(token);
		const briefings = mails.filter((m) => m.mailType === 'trip-briefing');
		expect(
			briefings.map((m) => m.subject),
			'genau EINE Trip-Briefing-Mail im Postfach'
		).toHaveLength(1);
		expect(mails.map((m) => m.subject), 'genau EINE Mail mit Token insgesamt').toHaveLength(1);
		expect(briefings[0].subject, 'die eine Mail ist die des Morgens').toMatch(/—\s*Morgen/);
		expect(
			mails.filter((m) => /—\s*Abend/.test(m.subject)).map((m) => m.subject),
			'keine Abend-Mail mit Token'
		).toEqual([]);

		// --- Validator (Trip-Briefing-Pfad), Exit 0 Pflicht -------------------
		await test.step('briefing_mail_validator.py --mail-type trip-briefing (Exit 0)', async () => {
			try {
				execFileSync(
					'uv',
					[
						'run',
						'python3',
						'.claude/hooks/briefing_mail_validator.py',
						'--mail-type',
						'trip-briefing',
						'--subject-contains',
						token
					],
					{
						cwd: REPO_ROOT,
						env: { ...process.env, GZ_IMAP_HOST: process.env.GZ_IMAP_HOST ?? 'mail.henemm.com' },
						encoding: 'utf-8',
						timeout: 180_000,
						stdio: ['ignore', 'pipe', 'pipe']
					}
				);
			} catch (e) {
				const err = e as { status?: number; stdout?: string; stderr?: string };
				throw new Error(
					`briefing_mail_validator.py Exit ${err.status} (Token ${token}):\n` +
						`${(err.stdout ?? '').slice(-1500)}\n${(err.stderr ?? '').slice(-800)}`
				);
			}
		});
	});
});
