// E2E — Issue #3122 Scheibe B3b: Karte „Was steht wo“ im Reiter Wetter gegen den echten Go- und Python-Server.
// Spec docs/specs/modules/feat_3122_was_steht_wo.md Teil B Nr. 10 bis 13; AC-20 (Browser), AC-22 bis AC-29,
// AC-31 bis AC-33, AC-37 (jeweils Oberflächen-Teil). Keine gemockten API-Antworten in den Kernfällen; einzige
// Ausnahme WS-5: die Profil-Lesung bekommt eine Test-Chat-ID (telegram_chat_id lässt sich seit #2141 nicht per
// API setzen, Muster hub-versand-inline-bearbeiten.spec.ts) — Schalter, PUT und Server-Stand bleiben echt.
//
//   WS-1  Trip, drei Orte, ein Ort: Spalten je Kontext; Haken entfernen -> neu laden -> bleibt entfernt (AC-22/23/37).
//   WS-2  Reihenfolge per Tastatur und Maus -> neu laden -> neue Folge; SMS-Beispiel und Marken ändern sich (AC-24/27).
//   WS-3  Roh/Einfach umschalten -> neu laden -> Wert steht, andere Stellen unverändert (AC-25).
//   WS-4  Blöcke und Ausblick Morgen/Abend -> neu laden (AC-29); Spalte eines ausgeschalteten Blocks ruht (AC-26).
//   WS-5  Kurzstil sperrt die Telegram-Spalte (AC-28).
//   WS-6  „−“/„+“ der Grundauswahl schreiben die Tabelle mit; ohne gespeicherte Tabelle legt „−“ keine an (AC-32).
//   WS-7  Konflikt: ein zweiter Client ändert das Abo, die Karte speichert -> Meldung, aktueller Stand (AC-20).
//   WS-8  Englischer Nutzer, 390 px, drei Orte: keine seitliche Seite, jede Spalte erreichbar, Kontrast;
//         fremde Tabelle (Admin) ist für ihn nicht lesbar und nicht schreibbar (AC-33, Mandantentrennung).
//   Fix-Loop (Adversary B3b):
//   WS-9  Schalter-PUT scheitert (500): Schalter springt zurück, Meldung; der nächste Schalter schreibt die
//         gescheiterte Änderung nicht mit (F1).
//   WS-10 Vorlagenwechsel: Zeilen weggefallener Metriken entfallen im selben Speichervorgang, Abwahlen
//         gemeinsamer Metriken bleiben, Zurückwechseln bringt die Metrik ohne alte Abwahl (F2).
//   WS-11 „+“ mit Altzeile kommt überall angehakt zurück (T4); Speichern des Reiters lädt die Karte neu (T5).
//   WS-12 Speichern im Reiter Zustellung (Übergangsblock) lässt die gespeicherte Tabelle unverändert.
//
//   cd frontend && npx playwright test e2e/was-steht-wo-karte.spec.ts --workers=1 --trace off

import { test, expect, request as pwRequest, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { createTestLocation, kontrastBericht, kontrastVerstoesse, messeKontrast, seedHub, type HubKind } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, MOBIL, WT, aktiveDerVorlage, oeffneWetter, stand, vorlagen, type Json } from './s3a2794-teil3.helpers';
import { oeffneZustellung } from './s3b2795-zustellung.helpers';

type Fall = { name: string; kind: HubKind; orte: number };
const FAELLE: Fall[] = [
	{ name: 'Trip', kind: 'route', orte: 0 },
	{ name: 'drei Orte', kind: 'vergleich', orte: 3 },
	{ name: 'ein Ort', kind: 'vergleich', orte: 1 }
];
const SPALTEN: Record<HubKind, string[]> = { route: ['email', 'telegram', 'sms', 'outlook'], vergleich: ['email', 'telegram', 'sms', 'hourly', 'outlook'] };

const tabellenPfad = (id: string) => `/api/briefings/${id}/placements`;
const tabellenUrl = (kind: HubKind, id: string) => `${tabellenPfad(id)}?kind=${kind}`;

type Abo = { kind: HubKind; id: string; ortNamen: string[]; aufraeumen: () => Promise<void> };

/** Abo mit Grundauswahl einer Vorlage (Trip: Alpen-Trekking, Orte: Allgemein mit vielen Metriken). */
async function seed(request: APIRequestContext, fall: Fall, opts: { ohne?: string[]; placements?: Json } = {}): Promise<Abo> {
	const vorlageId = fall.kind === 'route' ? 'alpen-trekking' : 'allgemein';
	const auswahl = aktiveDerVorlage((await vorlagen(request))[vorlageId]).filter((m) => !(opts.ohne ?? []).includes(m));
	const extraDc = opts.placements ? { placements: opts.placements } : {};
	const ampel = { template: vorlageId };
	if (fall.kind === 'route') {
		const hub = await seedHub(request, 'route', {
			extra: { display_config: { preset_name: vorlageId, metrics: auswahl.map((metric_id) => ({ metric_id, enabled: true })), ampel, ...extraDc } }
		});
		return { kind: 'route', id: hub.id, ortNamen: [], aufraeumen: hub.aufraeumen };
	}
	const orte = [];
	for (let i = 0; i < fall.orte; i++) orte.push(await createTestLocation(request, { name: `WSW-Ort-${i}`, lat: 47.1 + i * 0.1, lon: 11.2 + i * 0.1 }));
	const hub = await seedHub(request, 'vergleich', {
		extra: { location_ids: orte.map((o) => o.id), display_config: { ampel, active_metrics: auswahl.map((metric_id) => ({ metric_id, aggregation: 'max' })), ...extraDc } }
	});
	return {
		kind: 'vergleich',
		id: hub.id,
		ortNamen: orte.map((o) => o.name),
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
const zeile = (karte: Locator, metrik: string) => karte.locator(`[data-slot="et-zeile"][data-metrik="${metrik}"]`);
const zelle = (karte: Locator, metrik: string, stelle: string) => zeile(karte, metrik).locator(`[data-slot="et-zelle"][data-stelle="${stelle}"]`);
const haken = (karte: Locator, metrik: string, stelle: string) => zelle(karte, metrik, stelle).locator('input[type="checkbox"]');
const knopf = (karte: Locator, metrik: string, stelle: string) => zelle(karte, metrik, stelle).locator('[data-slot="roh-einfach"]');
const folge = (karte: Locator) => karte.locator('[data-slot="et-zeile"]').evaluateAll((z) => z.map((e) => e.getAttribute('data-metrik')!));

/** Antwort des Endpoints (als dieser Nutzer). */
async function tabelle(request: APIRequestContext, abo: Abo): Promise<Json> {
	const r = await request.get(tabellenUrl(abo.kind, abo.id));
	expect(r.ok(), `GET Tabelle: ${r.status()}`).toBeTruthy();
	return r.json();
}
/** Wartet auf den erfolgreichen PUT der Tabelle und das folgende GET (Karte aktualisiert). */
function tabelleGespeichert(page: Page, abo: Abo): Promise<unknown> {
	const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === tabellenPfad(abo.id), { timeout: 20_000 });
	return put.then(async (r) => {
		expect(r.status(), `PUT Tabelle: ${r.status()}`).toBe(200);
		await page.waitForResponse((g) => g.request().method() === 'GET' && new URL(g.url()).pathname === tabellenPfad(abo.id), { timeout: 20_000 });
	});
}
/** Erste Zeile, deren Zelle an `stelle` angehakt und bedienbar ist. */
async function ersteAngehakte(karte: Locator, stelle: string, ohne: string[] = []): Promise<string> {
	for (const m of await folge(karte)) {
		if (ohne.includes(m)) continue;
		const h = haken(karte, m, stelle);
		if ((await h.count()) && (await h.isChecked()) && (await h.isEnabled())) return m;
	}
	throw new Error(`keine angehakte Zelle in ${stelle}`);
}
const rowVon = (p: Json, m: string) => (p.rows as Json[]).find((r) => r.metric_id === m);

test.describe('Karte „Was steht wo“', () => {
	for (const fall of FAELLE) {
		test(`WS-1 (${fall.name}): Spalten je Kontext; Haken entfernen bleibt nach Neuladen entfernt`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const abo = await seed(page.request, fall);
			try {
				let karte = await oeffneKarte(page, abo);
				await expect(karte).toHaveAttribute('data-abschnitt', 'was-steht-wo');
				const koepfe = await karte.locator('[data-slot="et-kopf-stelle"]').evaluateAll((k) => k.map((e) => e.getAttribute('data-stelle')));
				expect(koepfe).toEqual(SPALTEN[abo.kind]);
				const emailKopf = karte.locator('[data-slot="et-kopf-stelle"][data-stelle="email"]');
				await expect(emailKopf).toContainText(abo.kind === 'route' ? 'Stundentabelle' : 'Übersicht');
				// keine Spalte Premium-SMS: die Liste der Stellen oben ist vollständig; Premium-SMS steht nur als Unterzeile der SMS.
				await expect(karte.locator('[data-slot="et-kopf-stelle"][data-stelle="sms"]')).toContainText('und Premium-SMS');
				if (fall.orte === 1) {
					await expect(karte).toContainText('Stunden-Tabelle unter der Übersicht, nur in der E-Mail.');
					await expect(karte).not.toContainText('je Ort');
					// Text des Beispiels kommt aus der Antwort; der SMS-Anfang „{Ort} TT.MM.:“ ist Sache von B5 (Renderer).
					const sms = (await tabelle(page.request, abo)).sms_example.text as string;
					await expect(karte.getByTestId('was-steht-wo-sms-text')).toHaveText(sms);
					expect(sms).toContain(abo.ortNamen[0]);
				}
				if (fall.orte === 3) await expect(karte).toContainText('Stunden-Tabelle je Ort unter der Übersicht, nur in der E-Mail.');

				// T2 (AC-28): ohne verbundenes Telegram (Profil ohne Chat-ID) ist der Kurzstil gesperrt.
				await expect(karte.getByTestId('was-steht-wo-kurzstil')).toHaveAttribute('aria-disabled', 'true');
				const m = await ersteAngehakte(karte, 'telegram');
				const gespeichert = tabelleGespeichert(page, abo);
				await haken(karte, m, 'telegram').click();
				await expect(haken(karte, m, 'telegram')).not.toBeChecked();
				await gespeichert;
				const server = await tabelle(page.request, abo);
				expect(server.stored, 'AC-23: Tabelle gespeichert').toBe(true);
				expect(rowVon(server.placements, m)?.places?.telegram, 'abgewählt = false').toBe(false);

				await page.reload();
				karte = await oeffneKarte(page, abo);
				await expect(haken(karte, m, 'telegram')).not.toBeChecked();
				await expect(haken(karte, m, 'email')).toBeChecked();
				expect(kontrastBericht(`Karte ${fall.name}`, kontrastVerstoesse(await messeKontrast(karte)))).toEqual([]);
			} finally {
				await abo.aufraeumen();
			}
		});
	}

	for (const fall of [FAELLE[0], FAELLE[1]]) {
		test(`WS-2 (${fall.name}): Reihenfolge per Tastatur und Maus, SMS-Beispiel und Marken folgen`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const abo = await seed(page.request, fall);
			try {
				let karte = await oeffneKarte(page, abo);
				const start = await folge(karte);
				const smsVorher = await karte.getByTestId('was-steht-wo-sms-text').innerText();
				// Tastatur: die erste Zeile mit SMS-Wert, deren Nachbar auch einen hat, eine Stelle nach unten.
				const vorher = await tabelle(page.request, abo);
				// Beide mit eigenem, verschiedenem SMS-Wert (ein Tageshöchst-/Tiefstwert teilt sich ein Token wie „D14/18“).
				const sms = (j: number) => (vorher.rows[j]?.cells?.sms?.example as string | null) ?? null;
				const i = start.findIndex((_m, j) => sms(j) && sms(j + 1) && sms(j) !== sms(j + 1) && !sms(j)!.includes(sms(j + 1)!) && !sms(j + 1)!.includes(sms(j)!));
				expect(i, 'Messaufbau: zwei benachbarte Zeilen mit SMS-Wert').toBeGreaterThanOrEqual(0);
				let gespeichert = tabelleGespeichert(page, abo);
				await zeile(karte, start[i]).getByTestId('drag-handle').focus();
				await page.keyboard.press('Space');
				await page.keyboard.press('ArrowDown');
				await page.keyboard.press('Space');
				const nachTaste = [...start.slice(0, i), start[i + 1], start[i], ...start.slice(i + 2)];
				await expect.poll(() => folge(karte)).toEqual(nachTaste);
				await gespeichert;
				expect((await tabelle(page.request, abo)).rows.map((r: Json) => r.metric_id)).toEqual(nachTaste);
				await expect(karte.getByTestId('was-steht-wo-sms-text')).not.toHaveText(smsVorher);

				// Maus: dritte Zeile am Griff über die erste ziehen.
				const mitte = async (l: Locator) => {
					const b = (await l.boundingBox())!;
					return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
				};
				gespeichert = tabelleGespeichert(page, abo);
				await zeile(karte, nachTaste[0]).scrollIntoViewIfNeeded();
				const von = await mitte(zeile(karte, nachTaste[2]).getByTestId('drag-handle'));
				const nach = await mitte(zeile(karte, nachTaste[0]).getByTestId('drag-handle'));
				await page.mouse.move(von.x, von.y);
				await page.mouse.down();
				await page.mouse.move(von.x, von.y - 12, { steps: 6 });
				await page.mouse.move(nach.x, nach.y, { steps: 15 });
				const nachMaus = [nachTaste[2], nachTaste[0], nachTaste[1], ...nachTaste.slice(3)];
				await expect.poll(() => folge(karte)).toEqual(nachMaus);
				await page.mouse.up();
				await gespeichert;

				// Marke „passt nicht mehr“: die letzte markierte Metrik per Tastatur ganz nach oben.
				const marken = async () =>
					karte.locator('[data-slot="et-zelle"][data-stelle="sms"]:has([data-slot="et-marke"])').evaluateAll((z) => z.map((e) => e.closest('[data-slot="et-zeile"]')!.getAttribute('data-metrik')!));
				const markiert = await marken();
				expect(markiert.length, 'Messaufbau: mindestens eine Metrik passt nicht mehr in die SMS').toBeGreaterThan(0);
				const hoch = markiert[markiert.length - 1];
				const position = (await folge(karte)).indexOf(hoch);
				gespeichert = tabelleGespeichert(page, abo);
				await zeile(karte, hoch).getByTestId('drag-handle').focus();
				await page.keyboard.press('Space');
				for (let i = 0; i < position; i++) await page.keyboard.press('ArrowUp');
				await page.keyboard.press('Space');
				await gespeichert;
				await expect(zelle(karte, hoch, 'sms').locator('[data-slot="et-marke"]')).toHaveCount(0);

				await page.reload();
				karte = await oeffneKarte(page, abo);
				expect((await folge(karte))[0]).toBe(hoch);
				expect((await folge(karte)).slice(1, 4)).toEqual(nachMaus.filter((x) => x !== hoch).slice(0, 3));
			} finally {
				await abo.aufraeumen();
			}
		});
	}

	for (const fall of [FAELLE[0], FAELLE[1]]) {
		test(`WS-3 (${fall.name}): Roh/Einfach umschalten bleibt nach Neuladen, andere Stellen unverändert`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const abo = await seed(page.request, fall);
			try {
				let karte = await oeffneKarte(page, abo);
				await expect(karte.locator('[data-slot="et-zelle"][data-stelle="sms"] [data-slot="roh-einfach"]')).toHaveCount(0);
				const vorher = { email: await knopf(karte, 'wind', 'email').getAttribute('data-wert'), telegram: await knopf(karte, 'wind', 'telegram').getAttribute('data-wert'), outlook: await knopf(karte, 'wind', 'outlook').getAttribute('data-wert') };
				const neu = vorher.email === 'raw' ? 'simplified' : 'raw';
				const gespeichert = tabelleGespeichert(page, abo);
				await knopf(karte, 'wind', 'email').click();
				await expect(knopf(karte, 'wind', 'email')).toHaveAttribute('data-wert', neu);
				await gespeichert;
				expect(rowVon((await tabelle(page.request, abo)).placements, 'wind')?.formats?.email).toBe(neu);
				await page.reload();
				karte = await oeffneKarte(page, abo);
				await expect(knopf(karte, 'wind', 'email')).toHaveAttribute('data-wert', neu);
				await expect(knopf(karte, 'wind', 'telegram')).toHaveAttribute('data-wert', vorher.telegram!);
				await expect(knopf(karte, 'wind', 'outlook')).toHaveAttribute('data-wert', vorher.outlook!);
			} finally {
				await abo.aufraeumen();
			}
		});
	}

	test('WS-4 (drei Orte): Stundenverlauf aus und Ausblick morgens an bleiben nach Neuladen; Spalte ruht', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seed(page.request, FAELLE[1]);
		try {
			let karte = await oeffneKarte(page, abo);
			const stunden = karte.getByTestId('was-steht-wo-stundenverlauf');
			await expect(stunden).toHaveAttribute('aria-checked', 'true');
			const preset = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/compare/presets/${abo.id}`);
			await stunden.click();
			expect((await preset).status()).toBe(200);
			const m = await ersteAngehakte(karte, 'email');
			await expect(haken(karte, m, 'hourly')).toBeDisabled();
			const morgen = karte.getByTestId('was-steht-wo-ausblick-morning');
			const vorher = await morgen.getAttribute('aria-checked');
			const gespeichert = tabelleGespeichert(page, abo);
			await morgen.click();
			await gespeichert;
			expect((await stand(page.request, 'vergleich', abo.id)).hourly_enabled).toBe(false);
			await page.reload();
			karte = await oeffneKarte(page, abo);
			await expect(karte.getByTestId('was-steht-wo-stundenverlauf')).toHaveAttribute('aria-checked', 'false');
			await expect(karte.getByTestId('was-steht-wo-ausblick-morning')).toHaveAttribute('aria-checked', vorher === 'true' ? 'false' : 'true');
			await expect(haken(karte, m, 'hourly')).toBeDisabled();
		} finally {
			await abo.aufraeumen();
		}
	});

	test('WS-4 (Trip): Etappen-Kennzahlen, Vortag-Vergleich, Nacht-Stundentabelle und Ausblick abends', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seed(page.request, FAELLE[0]);
		try {
			let karte = await oeffneKarte(page, abo);
			for (const feld of ['show_stage_stats', 'show_yesterday_comparison', 'show_night_block']) {
				const s = karte.getByTestId(`was-steht-wo-${feld}`);
				await expect(s).toHaveAttribute('aria-checked', 'true');
				const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${abo.id}`);
				await s.click();
				expect((await put).status()).toBe(200);
			}
			const abend = karte.getByTestId('was-steht-wo-ausblick-evening');
			const vorher = await abend.getAttribute('aria-checked');
			const gespeichert = tabelleGespeichert(page, abo);
			await abend.click();
			await gespeichert;
			const t = await stand(page.request, 'route', abo.id);
			expect([t.report_config.show_stage_stats, t.report_config.show_yesterday_comparison, t.display_config.show_night_block]).toEqual([false, false, false]);
			await page.reload();
			karte = await oeffneKarte(page, abo);
			for (const feld of ['show_stage_stats', 'show_yesterday_comparison', 'show_night_block'])
				await expect(karte.getByTestId(`was-steht-wo-${feld}`)).toHaveAttribute('aria-checked', 'false');
			await expect(karte.getByTestId('was-steht-wo-ausblick-evening')).toHaveAttribute('aria-checked', vorher === 'true' ? 'false' : 'true');
		} finally {
			await abo.aufraeumen();
		}
	});

	test('WS-5 (Trip): Kurzstil sperrt die Telegram-Spalte und bleibt nach Neuladen', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seed(page.request, FAELLE[0]);
		await page.route('**/api/auth/profile', async (route) => {
			if (route.request().method() !== 'GET') return route.continue();
			const echt = await route.fetch();
			await route.fulfill({ response: echt, json: { ...((await echt.json()) as Json), telegram_chat_id: 'e2e-wsw-test-chat' } });
		});
		try {
			let karte = await oeffneKarte(page, abo);
			const kurz = karte.getByTestId('was-steht-wo-kurzstil');
			await expect(kurz).not.toHaveAttribute('aria-disabled', 'true');
			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${abo.id}`);
			await kurz.click();
			expect((await put).status()).toBe(200);
			const kopf = karte.locator('[data-slot="et-kopf-stelle"][data-stelle="telegram"]');
			await expect(kopf).toContainText('Kurzstil: wie SMS');
			const tg = karte.locator('[data-slot="et-zelle"][data-stelle="telegram"] input[type="checkbox"]');
			for (let i = 0; i < (await tg.count()); i++) await expect(tg.nth(i)).toBeDisabled();
			expect((await stand(page.request, 'route', abo.id)).report_config.telegram_style).toBe('kurzform');
			await page.reload();
			karte = await oeffneKarte(page, abo);
			await expect(karte.locator('[data-slot="et-kopf-stelle"][data-stelle="telegram"]')).toContainText('Kurzstil: wie SMS');
			await expect(karte.getByTestId('was-steht-wo-kurzstil')).toHaveAttribute('aria-checked', 'true');
		} finally {
			await abo.aufraeumen();
		}
	});

	for (const fall of [FAELLE[0], FAELLE[1]]) {
		test(`WS-6 (${fall.name}): „−“ und „+“ schreiben die Tabelle mit; ohne gespeicherte Tabelle legt „−“ keine an`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const abo = await seed(page.request, fall);
			try {
				const reiter = await oeffneWetter(page, abo.kind, abo.id);
				let karte = reiter.getByTestId('was-steht-wo');
				await expect(karte.getByTestId('was-steht-wo-tabelle')).toBeVisible({ timeout: 20_000 });
				const wetterPut = () =>
					page.waitForResponse((r) => {
						const p = new URL(r.url()).pathname;
						return r.request().method() === 'PUT' && (p === `/api/trips/${abo.id}/weather-config` || p === `/api/compare/presets/${abo.id}`);
					});
				// 1. Ohne gespeicherte Tabelle: „−“ an Böen schreibt keine Tabelle.
				let put = wetterPut();
				await reiter.getByTestId(WT.entfernen('gust')).click();
				expect((await put).status()).toBe(200);
				expect('placements' in ((await stand(page.request, abo.kind, abo.id)).display_config ?? {}), 'stored: false bleibt').toBe(false);
				await expect(zeile(karte, 'gust')).toHaveCount(0);
				// T1: auch „+“ legt ohne gespeicherte Tabelle keine an.
				put = wetterPut();
				await reiter.getByTestId(WT.plus('gust')).click();
				const plusRumpf = (await put).request().postDataJSON();
				expect('placements' in (plusRumpf.display_config ?? plusRumpf), '„+“ sendet keine Tabelle').toBe(false);
				expect('placements' in ((await stand(page.request, abo.kind, abo.id)).display_config ?? {}), 'stored: false bleibt nach „+“').toBe(false);
				await expect(zeile(karte, 'gust')).toHaveCount(1, { timeout: 20_000 });

				// 2. Tabelle speichern (Haken ab), dann „−“ an Wind: Zeile im selben Speichervorgang weg.
				const m = await ersteAngehakte(karte, 'sms', ['wind']);
				const gespeichert = tabelleGespeichert(page, abo);
				await haken(karte, m, 'sms').click();
				await gespeichert;
				put = wetterPut();
				await reiter.getByTestId(WT.entfernen('wind')).click();
				const antwort = await put;
				expect(antwort.status()).toBe(200);
				const gesendet = antwort.request().postDataJSON();
				const dc = gesendet.display_config ?? gesendet;
				expect(dc.placements, 'placements im Rumpf des Reiters').toBeTruthy();
				expect(rowVon(dc.placements, 'wind'), 'Zeile Wind im selben Speichervorgang entfernt').toBeUndefined();
				await expect(zeile(karte, 'wind')).toHaveCount(0);

				// 3. „+“ Wind: hinten, überall angehakt, Meldung nach §5 Punkt 8.
				put = wetterPut();
				await reiter.getByTestId(WT.plus('wind')).click();
				await expect(reiter.getByTestId(WT.hinzuMeldung)).toContainText('ist jetzt im Briefing und in jedem Kanal angehakt');
				expect((await put).status()).toBe(200);
				await page.reload();
				karte = await oeffneKarte(page, abo);
				const nachher = await folge(karte);
				expect(nachher[nachher.length - 1], 'Wind ist die letzte Zeile').toBe('wind');
				for (const s of ['email', 'telegram', 'sms']) await expect(haken(karte, 'wind', s)).toBeChecked();
				const server = await tabelle(page.request, abo);
				expect(rowVon(server.placements, 'wind')?.places ?? {}, 'überall angehakt').toEqual({});
				expect(rowVon(server.placements, m)?.places?.sms, 'andere Abwahl bleibt').toBe(false);
			} finally {
				await abo.aufraeumen();
			}
		});
	}

	test('WS-7 (Trip): Konflikt — ein zweiter Client ändert das Abo, die Karte überschreibt nichts', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seed(page.request, FAELLE[0]);
		try {
			const karte = await oeffneKarte(page, abo);
			const fremd = await ersteAngehakte(karte, 'sms');
			const eigen = await ersteAngehakte(karte, 'telegram', [fremd]);
			// Zweiter Client: liest Tabelle samt Stempel und schreibt eine eigene Änderung.
			const zweiter = await pwRequest.newContext({ baseURL: new URL(page.url()).origin, storageState: await page.context().storageState() });
			const g = await zweiter.get(tabellenUrl('route', abo.id));
			const stempel = g.headers()['etag'];
			const p = (await g.json()).placements;
			const neu = { ...p, rows: p.rows.map((r: Json) => (r.metric_id === fremd ? { ...r, places: { ...(r.places ?? {}), sms: false } } : r)) };
			const w = await zweiter.put(tabellenUrl('route', abo.id), { data: neu, headers: { 'If-Match': stempel } });
			expect(w.status(), 'zweiter Client speichert').toBe(200);
			await zweiter.dispose();

			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === tabellenPfad(abo.id));
			await haken(karte, eigen, 'telegram').click();
			expect((await put).status(), 'veralteter Stand -> 412').toBe(412);
			await expect(karte.getByTestId('was-steht-wo-meldung')).toHaveAttribute('data-art', 'konflikt');
			await expect(haken(karte, fremd, 'sms')).not.toBeChecked();
			await expect(haken(karte, eigen, 'telegram')).toBeChecked();
			const server = await tabelle(page.request, abo);
			expect(rowVon(server.placements, fremd)?.places?.sms).toBe(false);
			expect(rowVon(server.placements, eigen)?.places?.telegram, 'nichts überschrieben').not.toBe(false);
			// T3: der nächste Klick speichert sauber, die Meldung verschwindet.
			const nochmal = tabelleGespeichert(page, abo);
			await haken(karte, eigen, 'telegram').click();
			await nochmal;
			await expect(karte.getByTestId('was-steht-wo-meldung')).toHaveCount(0);
			expect(rowVon((await tabelle(page.request, abo)).placements, eigen)?.places?.telegram).toBe(false);
		} finally {
			await abo.aufraeumen();
		}
	});

	test('WS-9 (Trip): Schalter-PUT scheitert — Schalter springt zurück, nächster Schalter schreibt nur sich selbst', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seed(page.request, FAELLE[0]);
		try {
			const karte = await oeffneKarte(page, abo);
			const pfad = `/api/trips/${abo.id}`;
			await page.route(`**${pfad}`, (route) =>
				route.request().method() === 'PUT' ? route.fulfill({ status: 500, json: { error: 'kaputt' } }) : route.continue()
			);
			const etappen = karte.getByTestId('was-steht-wo-show_stage_stats');
			const fehlschlag = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad);
			await etappen.click();
			expect((await fehlschlag).status()).toBe(500);
			await expect(etappen).toHaveAttribute('aria-checked', 'true');
			await expect(karte.getByTestId('was-steht-wo-meldung')).toHaveAttribute('data-art', 'fehler');
			await page.unroute(`**${pfad}`);
			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad);
			await karte.getByTestId('was-steht-wo-show_night_block').click();
			const antwort = await put;
			expect(antwort.status()).toBe(200);
			expect(antwort.request().postDataJSON(), 'gescheiterte Änderung fährt nicht mit').toEqual({ display_config: { show_night_block: false } });
			const t = await stand(page.request, 'route', abo.id);
			expect(t.report_config.show_stage_stats ?? true).toBe(true);
			expect(t.display_config.show_night_block).toBe(false);
		} finally {
			await abo.aufraeumen();
		}
	});

	test('WS-10 (drei Orte): Vorlagenwechsel entfernt Zeilen weggefallener Metriken, gemeinsame Abwahlen bleiben', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const v = await vorlagen(page.request);
		const alt = aktiveDerVorlage(v.allgemein);
		// Zielvorlage: die erste, der eine Metrik von „Allgemein“ fehlt und die eine mit ihr teilt.
		const zielId = Object.keys(v).find((id) => id !== 'allgemein' && alt.some((m) => !aktiveDerVorlage(v[id]).includes(m)) && alt.some((m) => aktiveDerVorlage(v[id]).includes(m)))!;
		const neu = aktiveDerVorlage(v[zielId] ?? { ampel: { metrics: {} } });
		const nurAlt = alt.find((m) => !neu.includes(m));
		const gemeinsam = alt.find((m) => neu.includes(m));
		expect(nurAlt && gemeinsam, 'Messaufbau: Vorlagen unterscheiden sich und überschneiden sich').toBeTruthy();
		const abo = await seed(page.request, FAELLE[1], {
			placements: { version: 1, rows: [{ metric_id: gemeinsam, places: { telegram: false } }, { metric_id: nurAlt, places: { sms: false } }] }
		});
		try {
			const reiter = await oeffneWetter(page, 'vergleich', abo.id);
			const karte = reiter.getByTestId('was-steht-wo');
			await expect(karte.getByTestId('was-steht-wo-tabelle')).toBeVisible({ timeout: 20_000 });
			const wechsel = async (id: string) => {
				const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/compare/presets/${abo.id}`);
				await reiter.getByTestId(WT.picker).click();
				await reiter.getByTestId(WT.vorlageOption(id)).click();
				await reiter.getByTestId(WT.wechselUebernehmen).click();
				const a = await put;
				expect(a.status()).toBe(200);
				return a.request().postDataJSON();
			};
			const rumpf = await wechsel(zielId);
			expect(rowVon(rumpf.display_config.placements, nurAlt!), 'Zeile im selben Speichervorgang entfernt').toBeUndefined();
			await expect.poll(async () => rowVon((await tabelle(page.request, abo)).placements, nurAlt!)).toBeUndefined();
			expect(rowVon((await tabelle(page.request, abo)).placements, gemeinsam!)?.places?.telegram, 'gemeinsame Abwahl bleibt').toBe(false);
			await wechsel('allgemein');
			await expect.poll(async () => rowVon((await tabelle(page.request, abo)).placements, nurAlt!)?.places ?? null).toEqual(null);
			const server = await tabelle(page.request, abo);
			expect(rowVon(server.placements, nurAlt!), 'zurück, ohne alte Abwahl').toEqual({ metric_id: nurAlt });
			expect(rowVon(server.placements, gemeinsam!)?.places?.telegram).toBe(false);
		} finally {
			await abo.aufraeumen();
		}
	});

	test('WS-11 (drei Orte): „+“ mit Altzeile kommt überall angehakt zurück; Speichern des Reiters lädt die Karte neu', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seed(page.request, FAELLE[1], {
			ohne: ['gust'],
			placements: { version: 1, rows: [{ metric_id: 'wind', places: { sms: false } }, { metric_id: 'gust', places: { telegram: false, sms: false } }] }
		});
		try {
			const reiter = await oeffneWetter(page, 'vergleich', abo.id);
			let karte = reiter.getByTestId('was-steht-wo');
			await expect(karte.getByTestId('was-steht-wo-tabelle')).toBeVisible({ timeout: 20_000 });
			await expect(zeile(karte, 'gust')).toHaveCount(0);
			// T5: Amtliche Warnungen aus -> nach dem Speichern des Reiters verschwindet die feste Zeile ohne Neuladen.
			await expect(karte.locator('[data-slot="et-fest"]')).toHaveCount(1);
			await reiter.getByTestId(WT.warnungen).click();
			await expect(karte.locator('[data-slot="et-fest"]')).toHaveCount(0, { timeout: 20_000 });
			// T4: „+“ Böen.
			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/compare/presets/${abo.id}`);
			await reiter.getByTestId(WT.plus('gust')).click();
			expect((await put).status()).toBe(200);
			await expect.poll(async () => rowVon((await tabelle(page.request, abo)).placements, 'gust')).toEqual({ metric_id: 'gust' });
			await page.reload();
			karte = await oeffneKarte(page, abo);
			for (const s of ['email', 'telegram', 'sms']) await expect(haken(karte, 'gust', s)).toBeChecked();
			await expect(haken(karte, 'wind', 'sms')).not.toBeChecked();
		} finally {
			await abo.aufraeumen();
		}
	});

	test('WS-12 (Trip): Speichern im Reiter Zustellung lässt die gespeicherte Tabelle unverändert', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seed(page.request, FAELLE[0]);
		try {
			const karte = await oeffneKarte(page, abo);
			const m = await ersteAngehakte(karte, 'sms');
			const gespeichert = tabelleGespeichert(page, abo);
			await haken(karte, m, 'sms').click();
			await gespeichert;
			const vorher = (await stand(page.request, 'route', abo.id)).display_config.placements;
			expect(vorher, 'Messaufbau: Tabelle gespeichert').toBeTruthy();
			const zustellung = await oeffneZustellung(page, 'route', abo.id);
			const trend = zustellung.getByTestId('report-morning-trend').locator('input[type="checkbox"]');
			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${abo.id}`, { timeout: 20_000 });
			await trend.click();
			expect((await put).status()).toBe(200);
			expect((await stand(page.request, 'route', abo.id)).display_config.placements).toEqual(vorher);
		} finally {
			await abo.aufraeumen();
		}
	});

	test('WS-8: englischer Nutzer, 390 px, drei Orte — Spalten erreichbar, Kontrast, fremde Tabelle gesperrt', async ({ browser, page }) => {
		const admin = await seed(page.request, FAELLE[1]);
		const basis = new URL((await page.goto('/'))!.url()).origin;
		const name = `e2ewswen${Date.now()}`;
		const passwort = wegwerfPasswort();
		const gast = await pwRequest.newContext({ baseURL: basis, storageState: { cookies: [], origins: [] }, extraHTTPHeaders: { 'X-Real-IP': '10.31.22.8' } });
		const reg = await gast.post('/api/auth/register', { data: { username: name, password: passwort, email: `${name}@example.com`, language: 'en' } });
		expect([200, 201]).toContain(reg.status());
		const { id: nutzer } = (await reg.json()) as { id: string };
		const tok = (await (await page.request.post('/api/auth/verify-email/staging-token', { data: { username: nutzer } })).json()) as { token: string };
		expect((await gast.post('/api/auth/verify-email', { data: { user: nutzer, token: tok.token } })).ok()).toBeTruthy();
		await gast.dispose();
		const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', viewport: MOBIL, hasTouch: true, isMobile: true });
		const en = await ctx.newPage();
		try {
			await en.goto('/login');
			await en.fill('input[name="username"]', `${name}@example.com`);
			await en.fill('input[name="password"]', passwort);
			await en.click('form[action="?/login"] button[type="submit"]');
			await en.waitForURL((u) => u.pathname === '/', { timeout: 15_000 });

			// Mandantentrennung: die Tabelle des Admins ist für ihn weder lesbar noch schreibbar.
			expect((await en.request.get(tabellenUrl('vergleich', admin.id))).status()).toBe(404);
			expect((await en.request.put(tabellenUrl('vergleich', admin.id), { data: { version: 1, rows: [] } })).status()).toBe(404);

			const eigen = await seed(en.request, FAELLE[1]);
			const karte = await oeffneKarte(en, eigen);
			await expect(karte).toContainText('What goes where');
			await expect(karte).toContainText('Abbreviations explained');
			for (const w of ['Was steht wo', 'Übersicht', 'Zeichen', 'Kürzel erklärt', 'Einstellungen je Kanal']) await expect(karte).not.toContainText(w);
			await expect(karte.getByTestId('was-steht-wo-sms-text')).toHaveText(/ W \d+ km\/h/);
			const breiten = await en.evaluate(() => ({ seite: document.documentElement.scrollWidth, fenster: window.innerWidth }));
			expect(breiten.seite, 'Seite scrollt seitlich').toBeLessThanOrEqual(breiten.fenster);
			for (const s of SPALTEN.vergleich) {
				const b = (await karte.locator(`[data-slot="et-kopf-stelle"][data-stelle="${s}"]`).boundingBox())!;
				expect(b.x).toBeGreaterThanOrEqual(0);
				expect(b.x + b.width).toBeLessThanOrEqual(MOBIL.width);
			}
			const m = await ersteAngehakte(karte, 'outlook');
			const gespeichert = tabelleGespeichert(en, eigen);
			await haken(karte, m, 'outlook').tap();
			await gespeichert;
			expect(rowVon((await tabelle(en.request, eigen)).placements, m)?.places?.outlook).toBe(false);
			expect((await tabelle(page.request, admin)).stored, 'Abo des Admins unberührt').toBe(false);
			await karte.getByTestId('was-steht-wo-legende-auf').tap();
			expect(kontrastBericht('Karte en 390 px', kontrastVerstoesse(await messeKontrast(karte)))).toEqual([]);
			await eigen.aufraeumen();
		} finally {
			await en.request.post('/api/auth/account/delete', { data: { password: passwort } }).catch(() => {});
			await ctx.close();
			await admin.aufraeumen();
		}
	});
});
