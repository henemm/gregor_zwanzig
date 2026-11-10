// E2E — Issue #2881 Lieferung A (ADR-0111): Design-System auf Trip- und Vergleichsseiten.
//
// Spec: docs/specs/modules/rework_2881_design_system_bereinigung.md — DS-Nummer = AC.
//   DS-5  Anlege-Aktion „Neuer Trip"/„Neuer Vergleich" auf Trip-Liste, Vergleichsliste (gefüllt
//         und leer) und Startseite (leer), Computer und Handy: überall `Btn primary`, Ink-Fläche
//         rgb(26, 26, 24), helle Schrift (R4, ADR-0110 „Hauptaktion = Ink").
//   DS-7  `.mono` (Fortschrittszähler beim Anlegen) trägt die Mono-Schrift aus --g-font-mono und
//         font-feature-settings mit "tnum"; `.tnum` schaltet tabellarische Ziffern (R6, TOKENS §12).
//   DS-8  Hub-Reiterleiste am Computer nach ADR-0111 Punkt 1: kein Kasten (oben/links/rechts kein
//         Rahmen, kein Radius, keine Trennstriche), eine 1-px-Grundlinie --g-rule, Reiter 13 px/500
//         --g-ink, aktiv 600 mit 2-px-Unterstrich --g-accent, Zähler Mono 10 px neutral, Radius 3 px;
//         Trip und Vergleich gleich.
//   DS-9  Fortschritts-Segmente beim Anlegen (ADR-0111 Punkt 4): erledigt gefüllt --g-accent, offen
//         ohne Füllung mit 1-px-Kontur --g-ink-3, beide ≥ 3:1 gegen den Seitengrund; Zähler als Text.
//   DS-10 Tabu-Begriffe: „Drafts", „Alert-Trigger", „Alerts justieren" erscheinen auf Trip-Liste und
//         Trip-Übersicht (de) nicht; dort stehen „Entwürfe", „Alarm-Auslöser", „Alarme einstellen".
//   (AC-11 ist der Kern-Test tests/test_adr_index_drift.py.)
//
// Lieferung B (R2 native Felder → Bausteine, R3 ✓/⊘ → Dot + Text, R5 Tippflächen):
//   DS-1  Startdatum beim Trip-Anlegen über molecules/DatumFeld (bits-ui DatePicker): Kalender
//         öffnen, 19.11.2026 anklicken ⇒ Feld „19.11.2026" (en „19/11/2026", Tag zuerst wie im
//         übrigen UI), Kalender beginnt Montag, gespeichert `2026-11-19` (API), Anzeige im Hub
//         nach Neuladen; Handy: Kalender + Anzeige.
//   DS-2  Etappen-Reiter: Datum und Startzeit über DatumFeld/UhrzeitFeld (Segmente per Tastatur)
//         ⇒ API `2026-11-20`/`07:30`, nach Neuladen „20.11.2026"/„07:30" ohne AM/PM; 1280 und 390.
//   DS-3  Trip-/Vergleichsliste, beide Hubs (Übersicht, Etappen/Orte, Zustellung = Versand-
//         Abschnitt + Mail-Inhalt + Speicher-Chip) und beide Anlege-Abläufe (erster Schritt,
//         Punkte-Schritt, Zustellung), 1280/390, de/en: kein input[type=date|time|radio] im DOM,
//         kein sichtbares natives <select>, kein „✓"/„⊘" im innerText.
//   DS-4  Aktivität beim Trip-Anlegen = listbox (Maus, Enter/Pfeil/Enter, Fokus sichtbar) und
//         Mail-Format im Trip-Hub = radiogroup (Maus, Pfeil links) ⇒ Wert nach Neuladen gespeichert.
//   DS-6  390 × 844: Zurück-Link (Hub, Anlegen), „Mit Standardwerten speichern", jedes ⓘ,
//         jeder Schnellwahl-Chip der Zustellung ≥ 44 × 44 (Rahmen), kein waagerechtes Überlaufen.
//   Fix-Loop (Adversary F-B1..F-B6), Zusicherungen an der Wirkstelle:
//   DS-1 Leeren   Startdatum beim Anlegen leeren ⇒ „Startdatum fehlt", Etappen gesperrt.
//   DS-2 Etappenwechsel  Datum/Zeit in Etappe 2 tippen, sofort Etappe 1 ⇒ keine Vermischung, API + Neuladen.
//   DS-2 Zwischenstände  langsam getippt (Pause > Entprellung) ⇒ kein halbes Segment im PUT.
//   DS-2 Leeren   Startzeit leeren ⇒ 08:00 ohne gespeicherte Startzeit; Datum leeren ⇒ gespeichertes bleibt.
//   DS-2 (en)     24 h im englischen UI.  DS-4 Standard-Option zurückwählen ⇒ ohne Aktivität gespeichert;
//                 Mail-Format mit rollendem tabindex (Umschalt+Tab verlässt die Gruppe).
//   Fix-Loop 2 (Adversary Runde 2, F-C1..F-C3), je Schutzstelle der Segmentfelder ein Fall an der
//   Wirkstelle (Mutationsbeleg docs/artifacts/rework-2881-design-system/mutationen-B.txt):
//   DS-2 Jahr angefangen „202" verlassen ⇒ kein PUT, Anzeige zurück.  DS-2 dasselbe Datum und
//                 dieselbe Startzeit neu getippt ⇒ kein PUT.  DS-2 Rückkehr ins fertige Segment und
//                 Rücktaste ⇒ angefangen, kein Zwischenstand.  DS-2 Rücknahme beim Tippen (Datum/
//                 Startzeit): gescheitertes Speichern, Verlassen schreibt nichts nach.  DS-2 Etappen-
//                 wechsel Startzeit (fertig/angefangen).  DS-2 Startzeit neu tippen (Stunde geleert ⇒
//                 kein PUT bis zur neuen Zeit).  DS-1 Jahr angefangen ⇒ „Startdatum fehlt"; geleert
//                 und neu getippt ⇒ Hinweis erscheint nie.
//
// Pflicht-Mutationen (Spec Implementation Details 4, Lieferung A): (a) MTabBar-Rahmen-Reset
// entfernt ⇒ DS-8 rot; (b) `.mono`-Regel gelöscht ⇒ DS-7 rot; (c) „+ Neuer Trip" im Leerzustand
// zurück auf accent ⇒ DS-5 rot. Lieferung B: (d) BackLink-Höhe am Handy zurück auf 36 px ⇒ DS-6
// rot; (e) DatumFeld gibt `MM/DD/YYYY` nach außen ⇒ DS-1 rot (gespeicherter Wert/Anzeige nach
// Neuladen); (f) ein ✓ in SaveIndicator zurück ⇒ DS-3 rot (Speicher-Chip im Hub, innerText).
//
// Leerzustände (DS-5) brauchen ein Konto ohne Trips und Vergleiche: je Fall ein frisch
// registriertes, bestätigtes Konto (Fix-Loop F-B6) unter EIGENER X-Real-IP (Muster sprachwechsel,
// die Registrierungsbremse 5/h je IP bleibt den übrigen Specs) — der Leerzustand wird per API
// geprüft, nicht aus dem Zustand fremder Specs abgeleitet; das Konto wird im finally gelöscht.
// Kein fester Schlaf, kein networkidle: gewartet wird auf sichtbare Elemente.
// Sprachwechsel über PUT /api/auth/profile, im finally zurück auf de (Muster kontrast-trip-vergleich).

import { test, expect, request as pwRequest, type APIRequestContext, type BrowserContext, type Locator, type Page } from '@playwright/test';

type Sitzung = Awaited<ReturnType<BrowserContext['storageState']>>;
import {
	ANLEGE_SEL,
	HUB_KINDS,
	HUB_SEL,
	TOKEN_RGB,
	anlegenPflicht,
	cleanupTracked,
	kontrastVerhaeltnis,
	openHub,
	registerForCleanup,
	seedHub,
	feldEingabe,
	tippeDatum,
	tippeUhrzeit,
	tripGpxHochladen,
	waehleOption,
	type HubKind
} from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };
const BREITEN = [DESKTOP, MOBIL] as const;

/** Festwerte aus ADR-0111 / TOKENS.md (getComputedStyle-Form). */
const RULE = 'rgb(216, 211, 194)';
const PAPER = 'rgb(246, 244, 238)';
const TRANSPARENT = 'rgba(0, 0, 0, 0)';

/** Sichtbare Anlege-Knöpfe (Btn-Baustein) mit „Neuer Trip"/„Neuer Vergleich" (optional „+ "). */
const anlegeKnoepfe = (page: Page): Locator =>
	page.locator('[data-slot="btn"]:visible').filter({ hasText: /^\s*(\+\s*)?Neuer (Trip|Vergleich)\s*$/ });

interface KnopfBefund {
	text: string;
	variante: string | null;
	grund: string;
	schrift: string;
}

async function messeAnlegeKnoepfe(page: Page, seite: string, mindestens: number): Promise<KnopfBefund[]> {
	const knoepfe = anlegeKnoepfe(page);
	await expect
		.poll(() => knoepfe.count(), { message: `${seite}: zu wenige sichtbare Anlege-Knöpfe`, timeout: 15_000 })
		.toBeGreaterThanOrEqual(mindestens);
	// Hover-Farbe ausschließen: Maus in eine leere Ecke.
	await page.mouse.move(1, 1);
	const befunde: KnopfBefund[] = [];
	for (let i = 0; i < (await knoepfe.count()); i++) {
		const k = knoepfe.nth(i);
		befunde.push({
			text: ((await k.textContent()) ?? '').trim(),
			variante: await k.getAttribute('data-variant'),
			...(await k.evaluate((el) => {
				const s = getComputedStyle(el);
				return { grund: s.backgroundColor, schrift: s.color };
			}))
		});
	}
	return befunde;
}

function pruefeInk(befunde: KnopfBefund[], seite: string, fehler: string[]): void {
	for (const b of befunde) {
		if (b.variante !== 'primary') fehler.push(`${seite} „${b.text}": data-variant=${b.variante}, erwartet primary`);
		if (b.grund !== TOKEN_RGB.ink) fehler.push(`${seite} „${b.text}": Fläche ${b.grund}, erwartet Ink ${TOKEN_RGB.ink}`);
		if (b.schrift !== PAPER) fehler.push(`${seite} „${b.text}": Schrift ${b.schrift}, erwartet hell ${PAPER}`);
	}
}

// ─── DS-5 (AC-5) ────────────────────────────────────────────────────────────

test.describe('DS-5: Anlege-Aktion überall Btn primary (Ink)', () => {
	for (const breite of BREITEN) {
		test(`DS-5 gefüllt (${breite.width} px): Trip-Liste und Vergleichsliste`, async ({ page }) => {
			await page.setViewportSize(breite);
			const hubs = [await seedHub(page.request, 'route'), await seedHub(page.request, 'vergleich')];
			const fehler: string[] = [];
			try {
				for (const kind of HUB_KINDS) {
					await page.goto(HUB_SEL[kind].liste.url);
					await expect(page.getByTestId(HUB_SEL[kind].liste.zeile(hubs[kind === 'route' ? 0 : 1].id)).first()).toBeAttached({
						timeout: 15_000
					});
					pruefeInk(await messeAnlegeKnoepfe(page, `${kind}-Liste gefüllt ${breite.width}`, 1), `${kind}-Liste gefüllt ${breite.width}`, fehler);
				}
			} finally {
				for (const h of hubs) await h.aufraeumen();
			}
			expect(fehler, fehler.join('\n')).toEqual([]);
		});
	}
});

/** Frisches, bestätigtes Konto unter eigener X-Real-IP; liefert seinen Anmeldezustand. */
async function leeresKonto(admin: APIRequestContext, baseURL: string, ip: string): Promise<{ zustand: Sitzung; aufraeumen: () => Promise<void> }> {
	const name = `e2egzleer${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
	const passwort = 'Test1234!x';
	const gast = await pwRequest.newContext({ baseURL, storageState: { cookies: [], origins: [] }, extraHTTPHeaders: { 'X-Real-IP': ip } });
	const reg = await gast.post('/api/auth/register', { data: { username: name, password: passwort, email: `${name}@example.com` } });
	expect([200, 201], `Registrierung: ${reg.status()} ${await reg.text()}`).toContain(reg.status());
	const { id } = (await reg.json()) as { id: string };
	const tok = await admin.post('/api/auth/verify-email/staging-token', { data: { username: id } });
	expect(tok.ok(), `Staging-Token: ${tok.status()}`).toBeTruthy();
	const { token } = (await tok.json()) as { token: string };
	expect((await gast.post('/api/auth/verify-email', { data: { user: id, token } })).ok(), 'Bestätigung').toBeTruthy();
	expect((await gast.post('/api/auth/login', { data: { username: id, password: passwort } })).ok(), 'Anmeldung').toBeTruthy();
	const zustand = await gast.storageState();
	return {
		zustand,
		aufraeumen: async () => {
			await gast.post('/api/auth/account/delete', { data: { password: passwort } }).catch(() => {});
			await gast.dispose();
		}
	};
}

test.describe('DS-5: Leerzustände (frisches Konto ohne Trips und Vergleiche)', () => {
	for (const breite of BREITEN) {
		test(`DS-5 leer (${breite.width} px): Trip-Liste, Vergleichsliste, Startseite`, async ({ browser, request, baseURL }) => {
			const ip = `10.28.${1 + Math.floor(Math.random() * 250)}.${breite === MOBIL ? 2 : 1}`;
			const konto = await leeresKonto(request, baseURL as string, ip);
			const ctx = await browser.newContext({ storageState: konto.zustand, serviceWorkers: 'block', viewport: breite });
			const page = await ctx.newPage();
			const req = page.request;
			const fehler: string[] = [];
			try {
				// Vorbedingung Leerzustand — geprüft, nicht angenommen.
				expect(await (await req.get('/api/trips')).json(), 'frisches Konto ohne Trips').toEqual([]);
				expect((await (await req.get('/api/compare/presets')).json()) ?? [], 'frisches Konto ohne Vergleiche').toEqual([]);
				// Trip-Liste leer: Kopf-Knopf + Leerzustands-Knopf.
				await page.goto('/trips');
				await expect(page.getByText('Noch keine Trips').first()).toBeVisible({ timeout: 15_000 });
				pruefeInk(await messeAnlegeKnoepfe(page, `Trip-Liste leer ${breite.width}`, 2), `Trip-Liste leer ${breite.width}`, fehler);
				// Vergleichsliste leer: Kopf-Knopf.
				await page.goto('/compare');
				await expect(page.getByText('Noch keine Vergleiche angelegt.').first()).toBeAttached({ timeout: 15_000 });
				pruefeInk(await messeAnlegeKnoepfe(page, `Vergleichsliste leer ${breite.width}`, 1), `Vergleichsliste leer ${breite.width}`, fehler);
				// Startseite leer, BEIDE Zweige der EmptyKachel: Willkommen (neues Konto) und normaler
				// Leerzustand (Willkommen ausgeblendet) — je Kopfleiste (2) + Kachel (2) Anlege-Knöpfe.
				for (const ausblenden of [false, true]) {
					const r = await req.put('/api/auth/profile', { data: { onboarding_dismissed: ausblenden } });
					expect(r.ok(), `onboarding_dismissed=${ausblenden} setzen: ${r.status()}`).toBeTruthy();
					await page.goto('/');
					const willkommen = page.getByTestId('onboarding-willkommen');
					if (ausblenden) await expect(willkommen, 'Leerzustand ohne Willkommen erwartet').toHaveCount(0, { timeout: 15_000 });
					else await expect(willkommen, 'neues Konto zeigt das Willkommen').toBeVisible({ timeout: 15_000 });
					const seite = `Startseite leer (${ausblenden ? 'Leerzustand' : 'Willkommen'}) ${breite.width}`;
					pruefeInk(await messeAnlegeKnoepfe(page, seite, 4), seite, fehler);
				}
			} finally {
				await ctx.close();
				await konto.aufraeumen();
			}
			expect(fehler, fehler.join('\n')).toEqual([]);
		});
	}
});

// ─── DS-7 (AC-7) ────────────────────────────────────────────────────────────

test('DS-7: .mono = Mono-Schrift aus --g-font-mono mit "tnum"; .tnum = tabellarische Ziffern', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto(ANLEGE_SEL.route.url);
	const fortschritt = ANLEGE_SEL.route.fortschritt(page);
	await expect(fortschritt).toBeVisible({ timeout: 15_000 });
	const zaehler = fortschritt.locator('.mono');
	await expect(zaehler).toHaveCount(1);
	const mass = await zaehler.evaluate((el) => {
		const s = getComputedStyle(el);
		// Wert von --g-font-mono an derselben Stelle aufgelöst (Variablen-Kette font-mono → font-data).
		const probe = document.createElement('span');
		probe.style.fontFamily = 'var(--g-font-mono)';
		el.parentElement!.appendChild(probe);
		const soll = getComputedStyle(probe).fontFamily;
		probe.remove();
		// .tnum am echten Dokument (app.css), ohne Schriftwechsel.
		const tnum = document.createElement('span');
		tnum.className = 'tnum';
		tnum.textContent = '0123';
		el.parentElement!.appendChild(tnum);
		const tnumStil = getComputedStyle(tnum);
		const tnumWerte = { numeric: tnumStil.fontVariantNumeric, familie: tnumStil.fontFamily };
		const elternFamilie = getComputedStyle(el.parentElement!).fontFamily;
		tnum.remove();
		return { familie: s.fontFamily, features: s.fontFeatureSettings, soll, tnumWerte, elternFamilie };
	});
	expect(mass.soll, '--g-font-mono ist nicht die Mono-Schrift').toContain('JetBrains Mono');
	expect(mass.familie, 'Schrift des .mono-Zählers').toBe(mass.soll);
	expect(mass.features, 'font-feature-settings des .mono-Zählers').toContain('"tnum"');
	expect(mass.features).toContain('"zero"');
	expect(mass.tnumWerte.numeric, '.tnum ohne tabellarische Ziffern').toContain('tabular-nums');
	expect(mass.tnumWerte.familie, '.tnum wechselt die Schrift').toBe(mass.elternFamilie);
});

// ─── DS-8 (AC-8) ────────────────────────────────────────────────────────────

interface ReiterMass {
	leiste: Record<string, string>;
	inaktiv: Record<string, string>[];
	aktiv: Record<string, string>;
	zaehler: Record<string, string>;
}

async function messeReiterleiste(page: Page, kind: HubKind): Promise<ReiterMass> {
	const leiste = page.getByTestId(HUB_SEL[kind].reiterListe).locator('.mtabbar');
	// #2794 S3a: vier Hub-Reiter (Übersicht, Etappen/Orte, Wetter, Zustellung).
	await expect(leiste.getByRole('tab')).toHaveCount(4);
	await expect(leiste.locator('[data-slot="segmented-badge"]').first()).toBeVisible();
	await page.mouse.move(1, 1);
	return leiste.evaluate((el) => {
		const cs = (e: Element) => getComputedStyle(e);
		const rahmen = (e: Element) => {
			const s = cs(e);
			return {
				borderTopWidth: s.borderTopWidth,
				borderLeftWidth: s.borderLeftWidth,
				borderRightWidth: s.borderRightWidth,
				borderBottomWidth: s.borderBottomWidth,
				borderBottomColor: s.borderBottomColor
			};
		};
		const s = cs(el);
		const reiter = (e: Element) => ({
			...rahmen(e),
			fontSize: cs(e).fontSize,
			fontWeight: cs(e).fontWeight,
			color: cs(e).color,
			backgroundColor: cs(e).backgroundColor
		});
		const badge = el.querySelector('[data-slot="segmented-badge"]')!;
		return {
			leiste: {
				...rahmen(el),
				borderRadius: `${s.borderTopLeftRadius} ${s.borderTopRightRadius} ${s.borderBottomRightRadius} ${s.borderBottomLeftRadius}`
			},
			inaktiv: Array.from(el.querySelectorAll('[data-slot="segmented-item"][data-state="inactive"]')).map(reiter),
			aktiv: reiter(el.querySelector('[data-slot="segmented-item"][data-state="active"]')!),
			zaehler: {
				fontFamily: cs(badge).fontFamily,
				fontSize: cs(badge).fontSize,
				backgroundColor: cs(badge).backgroundColor,
				color: cs(badge).color,
				borderRadius: cs(badge).borderTopLeftRadius
			}
		};
	});
}

test('DS-8: Hub-Reiterleiste am Computer ohne Kasten, Grundlinie --g-rule, 13 px/500, aktiv 600 — Trip = Vergleich', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	const mass = {} as Record<HubKind, ReiterMass>;
	for (const kind of HUB_KINDS) {
		const hub = await seedHub(page.request, kind);
		try {
			await openHub(page, kind, hub.id, { tab: 'uebersicht' });
			mass[kind] = await messeReiterleiste(page, kind);
		} finally {
			await hub.aufraeumen();
		}
	}
	for (const kind of HUB_KINDS) {
		const m = mass[kind];
		// Kein Kasten: oben/links/rechts kein Rahmen, kein Radius; unten eine 1-px-Linie --g-rule.
		expect(m.leiste, `${kind}: Leiste trägt einen Kasten`).toEqual({
			borderTopWidth: '0px',
			borderLeftWidth: '0px',
			borderRightWidth: '0px',
			borderBottomWidth: '1px',
			borderBottomColor: RULE,
			borderRadius: '0px 0px 0px 0px'
		});
		expect(m.inaktiv.length, `${kind}: inaktive Reiter`).toBe(3);
		for (const r of m.inaktiv) {
			expect(r, `${kind}: inaktiver Reiter`).toMatchObject({
				fontSize: '13px',
				fontWeight: '500',
				color: TOKEN_RGB.ink,
				borderTopWidth: '0px',
				borderLeftWidth: '0px',
				borderRightWidth: '0px'
			});
			expect(r.borderBottomColor, `${kind}: inaktiver Reiter trägt Accent`).not.toBe(TOKEN_RGB.accent);
		}
		expect(m.aktiv, `${kind}: aktiver Reiter`).toMatchObject({
			fontSize: '13px',
			fontWeight: '600',
			color: TOKEN_RGB.ink,
			backgroundColor: TRANSPARENT,
			borderBottomWidth: '2px',
			borderBottomColor: TOKEN_RGB.accent,
			borderTopWidth: '0px',
			borderLeftWidth: '0px',
			borderRightWidth: '0px'
		});
		expect(m.zaehler.fontFamily, `${kind}: Zähler nicht Mono`).toContain('JetBrains Mono');
		expect(m.zaehler, `${kind}: Zähler`).toMatchObject({
			fontSize: '10px',
			backgroundColor: TOKEN_RGB.paperDeep,
			color: TOKEN_RGB.ink3,
			borderRadius: '3px'
		});
	}
	expect(mass.vergleich, 'Reiterleiste Trip ≠ Vergleich').toEqual(mass.route);
});

// ─── DS-9 (AC-9) ────────────────────────────────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`DS-9 (${kind}): Fortschritt — erledigt gefüllt --g-accent, offen nur 1-px-Kontur --g-ink-3, beide ≥ 3:1`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		try {
			await anlegenPflicht(page, kind, { name: `E2E-GZ-DS9-${kind}-${Date.now()}` });
			const segmente = ANLEGE_SEL[kind].fortschrittSegment(page);
			await expect(segmente).toHaveCount(ANLEGE_SEL[kind].fortschrittSegmente);
			const fortschritt = ANLEGE_SEL[kind].fortschritt(page);
			// #2794 S3a: Anlege-Kette mit vier Pflicht-Abschnitten.
			await expect(fortschritt).toContainText(`2 / ${ANLEGE_SEL[kind].fortschrittSegmente} Abschnitte eingerichtet`, { timeout: 10_000 });
			await expect(segmente.and(page.locator('[data-done="true"]'))).toHaveCount(2);
			// Farbwechsel laufen mit `transition: 350ms` — erst messen, wenn keine Animation mehr läuft.
			await page.evaluate(() =>
				Promise.all(
					document
						.getAnimations()
						.filter((a) => a instanceof CSSTransition)
						.map((a) => a.finished.catch(() => undefined))
				)
			);
			const werte = await segmente.evaluateAll((els) =>
				els.map((el) => {
					const s = getComputedStyle(el);
					return {
						erledigt: el.getAttribute('data-done') === 'true',
						grund: s.backgroundColor,
						rahmen: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth],
						rahmenFarbe: [s.borderTopColor, s.borderRightColor, s.borderBottomColor, s.borderLeftColor],
						rahmenStil: s.borderTopStyle
					};
				})
			);
			const seitenGrund = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
			for (const [i, w] of werte.entries()) {
				if (w.erledigt) {
					expect(w.grund, `Segment ${i} erledigt: Füllung`).toBe(TOKEN_RGB.accent);
					expect(kontrastVerhaeltnis(w.grund, seitenGrund), `Segment ${i} erledigt: Kontrast`).toBeGreaterThanOrEqual(3);
				} else {
					expect(w.grund, `Segment ${i} offen: Füllung`).toBe(TRANSPARENT);
					expect(w.rahmen, `Segment ${i} offen: Kontur`).toEqual(['1px', '1px', '1px', '1px']);
					expect(w.rahmenStil, `Segment ${i} offen: Konturstil`).toBe('solid');
					expect(w.rahmenFarbe, `Segment ${i} offen: Konturfarbe`).toEqual(Array(4).fill(TOKEN_RGB.ink3));
					expect(kontrastVerhaeltnis(TOKEN_RGB.ink3, seitenGrund), `Segment ${i} offen: Kontrast`).toBeGreaterThanOrEqual(3);
				}
			}
		} finally {
			await cleanupTracked(page.request);
		}
	});
}

// ─── DS-10 (AC-10) ──────────────────────────────────────────────────────────

test('DS-10: Trip-Liste und Trip-Übersicht (de) ohne „Drafts", „Alert-Trigger", „Alerts justieren"', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const sprache = await page.request.put('/api/auth/profile', { data: { language: 'de' } });
	expect(sprache.ok(), `Sprache de setzen: ${sprache.status()}`).toBeTruthy();
	const hub = await seedHub(page.request, 'route');
	try {
		await page.goto('/trips');
		await expect(page.getByTestId(HUB_SEL.route.liste.zeile(hub.id)).first()).toBeAttached({ timeout: 15_000 });
		// innerText folgt text-transform (Stat-Beschriftungen in Großbuchstaben) — Vergleich ohne Groß/Klein.
		const liste = (await page.locator('body').innerText()).toLowerCase();
		await openHub(page, 'route', hub.id, { tab: 'uebersicht' });
		const panel = page.locator(`[data-testid="${HUB_SEL.route.panel}-uebersicht"]:visible`).first();
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel).toContainText('Morgen-Briefing');
		const uebersicht = (await page.locator('body').innerText()).toLowerCase();
		for (const [seite, text] of [
			['Trip-Liste', liste],
			['Trip-Übersicht', uebersicht]
		] as const) {
			for (const tabu of ['Drafts', 'Alert-Trigger', 'Alerts justieren']) {
				expect(text.includes(tabu.toLowerCase()), `${seite} zeigt „${tabu}"`).toBe(false);
			}
		}
		expect(liste, 'Trip-Liste: Zähler „Entwürfe"').toContain('entwürfe');
		expect(liste, 'Trip-Liste: Einleitung „Alarme einstellen"').toContain('alarme einstellen');
		expect(uebersicht, 'Trip-Übersicht: Zeile „Alarm-Auslöser"').toContain('alarm-auslöser');
	} finally {
		await hub.aufraeumen();
	}
});

// ═══ Lieferung B (R2 native Felder, R3 Symbole, R5 Tippflächen) ════════════════

/** Vertrag der neuen Bausteine molecules/DatumFeld und molecules/UhrzeitFeld (data-slot). */
const DATUM = {
	eingabe: '[data-slot="datum-feld-eingabe"]',
	knopf: '[data-slot="datum-feld-kalender-knopf"]',
	kalender: '[data-slot="datum-feld-kalender"]',
	wochentag: '[data-slot="datum-feld-wochentag"]',
	zurueck: '[data-slot="datum-feld-zurueck"]',
	weiter: '[data-slot="datum-feld-weiter"]'
} as const;
const UHRZEIT_EINGABE = '[data-slot="uhrzeit-feld-eingabe"]';

/** Startdatum der Trip-Anlege-Seite (Computer/Handy). */
const tripDatumFeld = (page: Page, mobil: boolean): Locator =>
	page.getByTestId(mobil ? 'trip-new-date-input' : 'trip-new-date-input-desktop');

async function setzeSprache(page: Page, lang: 'de' | 'en'): Promise<void> {
	const r = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(r.ok(), `Sprache ${lang} setzen: ${r.status()}`).toBeTruthy();
}

/** Kalender des Datumsfelds öffnen, zum Monat blättern, Tag anklicken; liefert die Wochentags-Köpfe. */
async function waehleImKalender(page: Page, feld: Locator, iso: string): Promise<string[]> {
	await feld.locator(DATUM.knopf).click({ timeout: 10_000 });
	const kalender = page.locator(`${DATUM.kalender}:visible`);
	await expect(kalender, 'Kalender-Popover öffnet nicht').toBeVisible();
	const koepfe = (await kalender.locator(DATUM.wochentag).allInnerTexts()).map((s) => s.trim());
	const ziel = kalender.locator(`[data-value="${iso}"]:not([data-outside-month])`);
	const ersterTag = kalender.locator('[data-value]:not([data-outside-month])').first();
	for (let i = 0; i < 36 && (await ziel.count()) === 0; i++) {
		const erster = (await ersterTag.getAttribute('data-value')) ?? '';
		await kalender.locator(erster > iso ? DATUM.zurueck : DATUM.weiter).click();
		await expect(ersterTag).not.toHaveAttribute('data-value', erster);
	}
	await ziel.getByRole('button').click();
	await expect(kalender, 'Kalender schließt nach der Wahl nicht').toBeHidden();
	return koepfe;
}

async function postId(page: Page, pfad: string, ausloesen: () => Promise<void>): Promise<string> {
	const antwort = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === pfad, {
		timeout: 30_000
	});
	await ausloesen();
	const res = await antwort;
	expect(res.ok(), `POST ${pfad}: ${res.status()}`).toBeTruthy();
	const id = ((await res.json()) as { id: string }).id;
	registerForCleanup(pfad === '/api/trips' ? 'trip' : 'preset', id);
	return id;
}

async function tripStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/trips/${id}`);
	expect(res.ok(), `GET /api/trips/${id}: ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

// ─── DS-1 (AC-1) ────────────────────────────────────────────────────────────

for (const [lang, anzeige, montag] of [
	['de', '19.11.2026', /^Mo/],
	['en', '19/11/2026', /^Mon/]
] as const) {
	test(`DS-1 (${lang}): Startdatum per Kalender 19.11.2026, Wochenbeginn Montag, gespeichert als 2026-11-19, Anzeige nach Neuladen`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		await setzeSprache(page, lang);
		try {
			await page.goto(ANLEGE_SEL.route.url);
			const feld = tripDatumFeld(page, false);
			await expect(feld).toBeVisible({ timeout: 15_000 });
			await ANLEGE_SEL.route.name(page).fill(`E2E-GZ-DS1-${lang}-${Date.now()}`);
			const koepfe = await waehleImKalender(page, feld, '2026-11-19');
			expect(koepfe[0], `Kalender beginnt nicht mit Montag: ${koepfe.join(' ')}`).toMatch(montag);
			await expect(feld.locator(DATUM.eingabe), 'Anzeige im Feld').toHaveText(anzeige);
			await page.getByTestId('trip-new-tab-etappen').click();
			await tripGpxHochladen(page);
			const knopf = ANLEGE_SEL.route.standardwerte(page);
			await expect(knopf).toBeEnabled({ timeout: 15_000 });
			const id = await postId(page, '/api/trips', () => knopf.click());
			const stages = (await tripStand(page, id)).stages as { date: string }[];
			expect(stages[0]?.date, 'gespeichertes Startdatum').toBe('2026-11-19');
			// Neuladen: das Etappen-Datum im Hub zeigt dasselbe Datum im Format der Sprache.
			await openHub(page, 'route', id, { tab: 'etappen' });
			const etappe = page.locator('[data-testid="stage-date-field"]:visible').first();
			await expect(etappe.locator(DATUM.eingabe), 'Anzeige nach Neuladen').toHaveText(anzeige, { timeout: 15_000 });
		} finally {
			await setzeSprache(page, 'de');
			await cleanupTracked(page.request);
		}
	});
}

test('DS-1 (390 px): Startdatum am Handy per Kalender, Anzeige 19.11.2026, Wochenbeginn Montag', async ({ page }) => {
	await page.setViewportSize(MOBIL);
	await setzeSprache(page, 'de');
	await page.goto(ANLEGE_SEL.route.url);
	const feld = tripDatumFeld(page, true);
	await expect(feld).toBeVisible({ timeout: 15_000 });
	await ANLEGE_SEL.route.name(page, true).fill(`E2E-GZ-DS1-mobil-${Date.now()}`);
	const koepfe = await waehleImKalender(page, feld, '2026-11-19');
	expect(koepfe[0], `Kalender beginnt nicht mit Montag: ${koepfe.join(' ')}`).toMatch(/^Mo/);
	await expect(feld.locator(DATUM.eingabe)).toHaveText('19.11.2026');
	// Name + Datum erfüllt ⇒ der Weiter-Knopf des ersten Schritts ist frei.
	await expect(page.getByTestId('tn-mobile-route-cta').getByRole('button')).toBeEnabled();
});

// ─── DS-2 (AC-2) ────────────────────────────────────────────────────────────

for (const breite of BREITEN) {
	test(`DS-2 (${breite.width} px): Etappe — Datum 20.11.2026 und Startzeit 07:30 über die neuen Felder, nach Neuladen gespeichert (24 h)`, async ({
		page
	}) => {
		await page.setViewportSize(breite);
		await setzeSprache(page, 'de');
		const hub = await seedHub(page.request, 'route');
		try {
			await openHub(page, 'route', hub.id, { tab: 'etappen' });
			const datum = page.locator('[data-testid="stage-date-field"]:visible').first();
			const zeit = page.locator('[data-testid="stage-start-time-field"]:visible').first();
			await tippeDatum(page, datum, '2026-11-20');
			await tippeUhrzeit(page, zeit, '07:30');
			await expect
				.poll(
					async () => {
						const s = ((await tripStand(page, hub.id)).stages as { date: string; start_time?: string }[])[0];
						return `${s?.date} ${s?.start_time}`;
					},
					{ message: 'Datum/Startzeit nicht gespeichert', timeout: 15_000 }
				)
				.toBe('2026-11-20 07:30');
			await openHub(page, 'route', hub.id, { tab: 'etappen' });
			const datumNeu = page.locator('[data-testid="stage-date-field"]:visible').first();
			const zeitNeu = page.locator('[data-testid="stage-start-time-field"]:visible').first();
			await expect(datumNeu.locator(DATUM.eingabe)).toHaveText('20.11.2026', { timeout: 15_000 });
			await expect(zeitNeu.locator(UHRZEIT_EINGABE)).toHaveText('07:30');
			await expect(zeitNeu.locator('[data-segment="dayPeriod"]'), '24 h: kein AM/PM-Segment').toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── Fix-Loop (F-B1/F-B2/F-B3/F-B5): Zusicherungen an der Wirkstelle ────────────

const ZWEI_ETAPPEN = [
	{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 }, { id: 'b', name: 'b', lat: 42.04, lon: 9.0, elevation_m: 1200 }] },
	{ id: 's2', name: 'Tag 2', date: '2027-08-02', waypoints: [{ id: 'c', name: 'c', lat: 42.1, lon: 9.0, elevation_m: 900 }, { id: 'd', name: 'd', lat: 42.14, lon: 9.0, elevation_m: 1300 }] }
];
type Etappe = { id: string; date?: string; start_time?: string };
const etappen = async (page: Page, id: string) => (await tripStand(page, id)).stages as Etappe[];
const datumFeld = (page: Page) => page.locator('[data-testid="stage-date-field"]:visible').first();
const zeitFeld = (page: Page) => page.locator('[data-testid="stage-start-time-field"]:visible').first();
const waehleEtappe = (page: Page, i: number) => page.getByTestId('etappen-strip').getByTestId(`stage-card-${i}`).click();
/** Feld verlassen (Fokus weg vom Segment — Tab bliebe im nächsten Segment desselben Felds). */
const verlasseFeld = (page: Page) => page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

test('DS-2 Etappenwechsel (1280 px): Datum/Zeit in Etappe 2 tippen, sofort zu Etappe 1 — keine Vermischung, nach Neuladen beides richtig', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route', { extra: { stages: ZWEI_ETAPPEN } });
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await waehleEtappe(page, 1);
		await expect(feldEingabe(datumFeld(page))).toHaveText('02.08.2027', { timeout: 15_000 });
		await tippeUhrzeit(page, zeitFeld(page), '06:45');
		await tippeDatum(page, datumFeld(page), '2027-08-20');
		await waehleEtappe(page, 0); // sofort wechseln — der Fokus steht noch im Jahr-Segment
		await expect(feldEingabe(datumFeld(page)), 'Etappe 1 zeigt ihr eigenes Datum').toHaveText('01.08.2027');
		await expect(feldEingabe(zeitFeld(page)), 'Etappe 1 zeigt ihre eigene Startzeit').toHaveText('08:00');
		await expect
			.poll(async () => JSON.stringify((await etappen(page, hub.id)).map((e) => [e.id, e.date, e.start_time ?? null])), {
				message: 'gespeicherter Stand beider Etappen',
				timeout: 15_000
			})
			.toBe(JSON.stringify([['s1', '2027-08-01', null], ['s2', '2027-08-20', '06:45']]));
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await waehleEtappe(page, 1);
		await expect(feldEingabe(datumFeld(page))).toHaveText('20.08.2027', { timeout: 15_000 });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('06:45');
		await waehleEtappe(page, 0);
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027');
		await expect(feldEingabe(zeitFeld(page))).toHaveText('08:00');
		// Mitten im Segment wechseln (Tag „3" angefangen): Etappe 1 bekommt weder die angefangene
		// Ziffer angezeigt noch zurückgeschrieben.
		await waehleEtappe(page, 1);
		await expect(feldEingabe(datumFeld(page))).toHaveText('20.08.2027');
		await datumFeld(page).locator('[data-segment="day"]').click();
		await page.keyboard.type('3');
		await waehleEtappe(page, 0);
		await expect(feldEingabe(datumFeld(page)), 'Etappe 1 nach Wechsel mitten im Segment').toHaveText('01.08.2027');
		await page.getByTestId('save-indicator').waitFor();
		await expect
			.poll(async () => (await etappen(page, hub.id))[0]?.date, { message: 'Etappe 1 darf nichts abbekommen', timeout: 5_000 })
			.toBe('2027-08-01');
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027', { timeout: 15_000 });
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-2 Zwischenstände (1280 px): langsam getippt geht kein halbes Segment (Tag „2", Monat „1", Stunde „0") als PUT hinaus', async ({
	page
}) => {
	test.setTimeout(90_000);
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route');
	const gesendet: Etappe[] = [];
	page.on('request', (r) => {
		if (r.method() !== 'PUT' || new URL(r.url()).pathname !== `/api/trips/${hub.id}`) return;
		const stages = (r.postDataJSON() as { stages?: Etappe[] } | null)?.stages;
		if (stages?.[0]) gesendet.push(stages[0]);
	});
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027', { timeout: 15_000 });
		// Pause zwischen den Ziffern länger als die Speicher-Entprellung: ein Zwischenstand ginge hinaus.
		await datumFeld(page).locator('[data-segment="day"]').click();
		await page.keyboard.type('20112026', { delay: 1_500 });
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.date, { timeout: 15_000 }).toBe('2026-11-20');
		await zeitFeld(page).locator('[data-segment="hour"]').click();
		await page.keyboard.type('0730', { delay: 1_500 });
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.start_time, { timeout: 15_000 }).toBe('07:30');
		// Erlaubt sind nur Stände mit fertigen Segmenten.
		const daten = [...new Set(gesendet.map((e) => e.date))];
		const zeiten = [...new Set(gesendet.map((e) => e.start_time ?? null))];
		expect(daten.filter((d) => !['2027-08-01', '2027-08-20', '2027-11-20', '2026-11-20'].includes(d ?? '')), `halbe Datumsstände gesendet: ${daten}`).toEqual([]);
		expect(zeiten.filter((z) => ![null, '07:00', '07:30'].includes(z)), `halbe Uhrzeiten gesendet: ${zeiten}`).toEqual([]);
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-2 Leeren (1280 px): Startzeit leeren ⇒ 08:00 (gespeichert ohne Startzeit); Datum leeren ⇒ gespeichertes Datum bleibt und wird wieder angezeigt', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route', {
		extra: { stages: [{ ...ZWEI_ETAPPEN[0], start_time: '07:30' }] }
	});
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('07:30', { timeout: 15_000 });
		await zeitFeld(page).locator('[data-segment="hour"]').click();
		await page.keyboard.press('Backspace');
		await page.keyboard.press('Backspace');
		await verlasseFeld(page);
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.start_time ?? null, { message: 'Startzeit nicht geleert', timeout: 15_000 }).toBeNull();
		await expect(feldEingabe(zeitFeld(page)), 'geleerte Startzeit zeigt den Standard').toHaveText('08:00');
		// Schon Standard (keine Startzeit gespeichert) und erneut geleert: der Wert ändert sich nicht,
		// das Feld muss sich trotzdem wieder mit 08:00 zeigen statt mit „––".
		await zeitFeld(page).locator('[data-segment="hour"]').click();
		await page.keyboard.press('Backspace');
		await page.keyboard.press('Backspace');
		await verlasseFeld(page);
		await expect(feldEingabe(zeitFeld(page)), 'erneut geleerte Standard-Startzeit').toHaveText('08:00');

		await datumFeld(page).locator('[data-segment="day"]').click();
		await page.keyboard.press('Backspace');
		await page.keyboard.press('Backspace');
		await verlasseFeld(page);
		await expect(feldEingabe(datumFeld(page)), 'Anzeige zurück auf das gespeicherte Datum').toHaveText('01.08.2027');
		expect((await etappen(page, hub.id))[0]?.date, 'kein Datenverlust').toBe('2027-08-01');
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027', { timeout: 15_000 });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('08:00');
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-2 (en, 1280 px): Startzeit 17:30 im englischen UI in 24 h, ohne AM/PM, gespeichert', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'en');
	const hub = await seedHub(page.request, 'route');
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('08:00', { timeout: 15_000 });
		await expect(zeitFeld(page).locator('[data-segment="dayPeriod"]'), '24 h: kein AM/PM-Segment').toHaveCount(0);
		await tippeUhrzeit(page, zeitFeld(page), '17:30');
		await verlasseFeld(page);
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.start_time, { timeout: 15_000 }).toBe('17:30');
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('17:30', { timeout: 15_000 });
		await expect(zeitFeld(page).locator('[data-segment="dayPeriod"]')).toHaveCount(0);
	} finally {
		await setzeSprache(page, 'de');
		await hub.aufraeumen();
	}
});

test('DS-1 Leeren (1280 px): Startdatum beim Anlegen leeren ⇒ „Startdatum fehlt", Etappen gesperrt', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	await page.goto(ANLEGE_SEL.route.url);
	const feld = tripDatumFeld(page, false);
	await expect(feld).toBeVisible({ timeout: 15_000 });
	await ANLEGE_SEL.route.name(page).fill(`E2E-GZ-DS1-leer-${Date.now()}`);
	await tippeDatum(page, feld, '2026-11-19');
	const etappenReiter = page.getByTestId('trip-new-tab-etappen');
	await expect(etappenReiter).not.toHaveAttribute('aria-disabled', 'true');
	await feld.locator('[data-segment="day"]').click();
	await page.keyboard.press('Backspace');
	await page.keyboard.press('Backspace');
	await verlasseFeld(page);
	await expect(page.getByText('Startdatum fehlt'), 'Hinweis nach dem Leeren').toBeVisible();
	await expect(etappenReiter, 'Etappen ohne Startdatum gesperrt').toHaveAttribute('aria-disabled', 'true');
	await expect(ANLEGE_SEL.route.weiterErsterSchritt(page)).toBeDisabled();
});

/** Zählt die PUTs auf den Trip ab jetzt. */
function zaehlePuts(page: Page, id: string): { anzahl: number; staende: Etappe[] } {
	const z = { anzahl: 0, staende: [] as Etappe[] };
	page.on('request', (r) => {
		if (r.method() !== 'PUT' || new URL(r.url()).pathname !== `/api/trips/${id}`) return;
		z.anzahl += 1;
		const st = (r.postDataJSON() as { stages?: Etappe[] } | null)?.stages?.[0];
		if (st) z.staende.push(st);
	});
	return z;
}

test('DS-2 Jahr angefangen (1280 px): „202" ins Jahr getippt und Feld verlassen ⇒ nichts gespeichert, Anzeige zurück', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route');
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027', { timeout: 15_000 });
		const puts = zaehlePuts(page, hub.id);
		await datumFeld(page).locator('[data-segment="year"]').click();
		await page.keyboard.type('202');
		await verlasseFeld(page);
		await expect(feldEingabe(datumFeld(page)), 'Anzeige zurück auf das gespeicherte Datum').toHaveText('01.08.2027');
		await expect.poll(() => puts.anzahl, { timeout: 2_000 }).toBe(0);
		expect((await etappen(page, hub.id))[0]?.date, 'kein Jahr 0202 gespeichert').toBe('2027-08-01');
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-2 dasselbe Datum (1280 px): gespeichertes Datum und gespeicherte Startzeit unverändert neu getippt ⇒ kein Schreibvorgang', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route', { extra: { stages: [{ ...ZWEI_ETAPPEN[0], start_time: '07:30' }] } });
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027', { timeout: 15_000 });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('07:30');
		const puts = zaehlePuts(page, hub.id);
		await tippeDatum(page, datumFeld(page), '2027-08-01');
		await verlasseFeld(page);
		await tippeUhrzeit(page, zeitFeld(page), '07:30');
		await verlasseFeld(page);
		// Stabilitätsfenster: 2 s lang kein PUT (Speicher-Entprellung 700 ms).
		const ende = Date.now() + 2_000;
		await expect.poll(() => (Date.now() < ende ? `warte ${puts.anzahl}` : puts.anzahl), { timeout: 5_000, intervals: [200] }).toBe(0);
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-2 Rückkehr ins fertige Segment (1280 px): Tag „1" nachgetippt ist angefangen, geht nicht als Zwischenstand hinaus', async ({
	page
}) => {
	test.setTimeout(60_000);
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route');
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027', { timeout: 15_000 });
		await tippeDatum(page, datumFeld(page), '2027-08-20');
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.date, { timeout: 15_000 }).toBe('2027-08-20');
		const puts = zaehlePuts(page, hub.id);
		// Später zurück in das fertige Tag-Segment: „1", Pause länger als die Entprellung, dann „5".
		await datumFeld(page).locator('[data-segment="day"]').click();
		await page.keyboard.type('15', { delay: 1_500 });
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.date, { timeout: 15_000 }).toBe('2027-08-15');
		expect(puts.staende.map((e) => e.date).filter((d) => d !== '2027-08-15'), 'Zwischenstand Tag 01 gesendet').toEqual([]);
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-2 Rücktaste (1280 px): eine Ziffer im fertigen Tag gelöscht ist angefangen, geht nicht als Zwischenstand hinaus', async ({
	page
}) => {
	test.setTimeout(60_000);
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route');
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027', { timeout: 15_000 });
		await tippeDatum(page, datumFeld(page), '2027-08-20');
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.date, { timeout: 15_000 }).toBe('2027-08-20');
		const puts = zaehlePuts(page, hub.id);
		// „20" ⇒ Rücktaste ⇒ „2": bits-ui setzt schon Tag 02 — das darf nicht gespeichert werden.
		await datumFeld(page).locator('[data-segment="day"]').click();
		await page.keyboard.press('Backspace');
		// Stabilitätsfenster länger als die Speicher-Entprellung (700 ms): kein PUT.
		const ende = Date.now() + 2_000;
		await expect.poll(() => (Date.now() < ende ? `warte ${puts.anzahl}` : puts.anzahl), { timeout: 5_000, intervals: [200] }).toBe(0);
		await page.keyboard.type('5');
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.date, { timeout: 15_000 }).toBe('2027-08-25');
		expect(puts.staende.map((e) => e.date).filter((d) => d !== '2027-08-25'), 'Zwischenstand Tag 02 gesendet').toEqual([]);
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-2 Rücknahme beim Tippen (1280 px): scheitert das Speichern, während ein Segment angefangen ist, schreibt das Verlassen nichts nach', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route');
	let putNr = 0;
	await page.route(`**/api/trips/${hub.id}`, async (route) => {
		if (route.request().method() === 'PUT' && ++putNr === 1) {
			await route.fulfill({ status: 500, body: JSON.stringify({ error: 'Serverfehler' }) });
			return;
		}
		await route.continue();
	});
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027', { timeout: 15_000 });
		// Tag fertig (wird gespeichert und scheitert), Monat gleich danach angefangen („1").
		await datumFeld(page).locator('[data-segment="day"]').click();
		await page.keyboard.type('25');
		await page.keyboard.type('1');
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', { timeout: 15_000 });
		await expect(feldEingabe(datumFeld(page)), 'Rücknahme sichtbar').toHaveText('01.08.2027');
		await verlasseFeld(page);
		await expect(feldEingabe(datumFeld(page))).toHaveText('01.08.2027');
		// Der angefangene Stand von vor der Rücknahme darf nicht nachträglich gespeichert werden.
		const ende = Date.now() + 2_000;
		await expect.poll(() => (Date.now() < ende ? `warte ${putNr}` : putNr), { timeout: 5_000, intervals: [200] }).toBe(1);
		expect((await etappen(page, hub.id))[0]?.date).toBe('2027-08-01');
	} finally {
		await page.unroute(`**/api/trips/${hub.id}`);
		await hub.aufraeumen();
	}
});

test('DS-2 Etappenwechsel Startzeit (1280 px): Startzeit in Etappe 2 fertig bzw. angefangen, sofort zu Etappe 1 — keine Vermischung', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route', { extra: { stages: ZWEI_ETAPPEN } });
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await waehleEtappe(page, 1);
		await expect(feldEingabe(datumFeld(page))).toHaveText('02.08.2027', { timeout: 15_000 });
		await tippeUhrzeit(page, zeitFeld(page), '06:45');
		await waehleEtappe(page, 0); // sofort wechseln — der Fokus steht noch im Minuten-Segment
		await expect(feldEingabe(zeitFeld(page)), 'Etappe 1 zeigt ihre eigene Startzeit').toHaveText('08:00');
		// Mitten im Segment wechseln (Stunde „1" angefangen).
		await waehleEtappe(page, 1);
		await expect(feldEingabe(zeitFeld(page))).toHaveText('06:45', { timeout: 15_000 });
		await zeitFeld(page).locator('[data-segment="hour"]').click();
		await page.keyboard.type('1');
		await waehleEtappe(page, 0);
		await expect(feldEingabe(zeitFeld(page)), 'Etappe 1 nach Wechsel mitten im Segment').toHaveText('08:00');
		await verlasseFeld(page);
		await expect
			.poll(async () => JSON.stringify((await etappen(page, hub.id)).map((e) => [e.id, e.start_time ?? null])), {
				message: 'gespeicherte Startzeiten beider Etappen',
				timeout: 15_000
			})
			.toBe(JSON.stringify([['s1', null], ['s2', '06:45']]));
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('08:00', { timeout: 15_000 });
		await waehleEtappe(page, 1);
		await expect(feldEingabe(zeitFeld(page))).toHaveText('06:45');
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-2 Rücknahme Startzeit (1280 px): scheitert das Speichern, während die Minute angefangen ist, schreibt das Verlassen nichts nach', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route', { extra: { stages: [{ ...ZWEI_ETAPPEN[0], start_time: '07:30' }] } });
	let putNr = 0;
	await page.route(`**/api/trips/${hub.id}`, async (route) => {
		if (route.request().method() === 'PUT' && ++putNr === 1) {
			await route.fulfill({ status: 500, body: JSON.stringify({ error: 'Serverfehler' }) });
			return;
		}
		await route.continue();
	});
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('07:30', { timeout: 15_000 });
		// Stunde fertig (wird gespeichert und scheitert), Minute gleich danach angefangen („1").
		await zeitFeld(page).locator('[data-segment="hour"]').click();
		await page.keyboard.type('09');
		await page.keyboard.type('1');
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', { timeout: 15_000 });
		await expect(feldEingabe(zeitFeld(page)), 'Rücknahme sichtbar').toHaveText('07:30');
		await verlasseFeld(page);
		await expect(feldEingabe(zeitFeld(page))).toHaveText('07:30');
		const ende = Date.now() + 2_000;
		await expect.poll(() => (Date.now() < ende ? `warte ${putNr}` : putNr), { timeout: 5_000, intervals: [200] }).toBe(1);
		expect((await etappen(page, hub.id))[0]?.start_time).toBe('07:30');
	} finally {
		await page.unroute(`**/api/trips/${hub.id}`);
		await hub.aufraeumen();
	}
});

test('DS-2 Startzeit neu tippen (1280 px): Stunde per Rücktaste geleert ⇒ bis zur neuen Zeit kein Schreibvorgang', async ({ page }) => {
	test.setTimeout(60_000);
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route', { extra: { stages: [{ ...ZWEI_ETAPPEN[0], start_time: '07:30' }] } });
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		await expect(feldEingabe(zeitFeld(page))).toHaveText('07:30', { timeout: 15_000 });
		const puts = zaehlePuts(page, hub.id);
		await zeitFeld(page).locator('[data-segment="hour"]').click();
		await page.keyboard.press('Backspace');
		await page.keyboard.press('Backspace');
		// Stabilitätsfenster länger als die Speicher-Entprellung (700 ms): weder „" noch ein Rest geht hinaus.
		const ende = Date.now() + 2_000;
		await expect.poll(() => (Date.now() < ende ? `warte ${puts.anzahl}` : puts.anzahl), { timeout: 5_000, intervals: [200] }).toBe(0);
		await page.keyboard.type('0915');
		await verlasseFeld(page);
		await expect.poll(async () => (await etappen(page, hub.id))[0]?.start_time, { timeout: 15_000 }).toBe('09:15');
		expect(puts.staende.map((e) => e.start_time ?? null).filter((z) => !['09:15', '09:30'].includes(z ?? '')), 'leere oder halbe Startzeit gesendet').toEqual([]);
	} finally {
		await hub.aufraeumen();
	}
});

test('DS-1 Jahr angefangen und Neueintippen (1280 px): „202" ⇒ „Startdatum fehlt"; geleert und neu getippt ⇒ Hinweis erscheint nie', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	await page.goto(ANLEGE_SEL.route.url);
	const feld = tripDatumFeld(page, false);
	await expect(feld).toBeVisible({ timeout: 15_000 });
	await ANLEGE_SEL.route.name(page).fill(`E2E-GZ-DS1-jahr-${Date.now()}`);
	await tippeDatum(page, feld, '2026-11-19');
	const etappenReiter = page.getByTestId('trip-new-tab-etappen');
	await expect(etappenReiter).not.toHaveAttribute('aria-disabled', 'true');
	// Neueintippen (Rücktaste leert, dann neue Ziffern): bis zum Verlassen kein kurzes „Startdatum fehlt".
	await page.evaluate(() => {
		const w = window as unknown as { __fehltGesehen: boolean };
		w.__fehltGesehen = false;
		new MutationObserver(() => {
			if (document.body.innerText.includes('Startdatum fehlt')) w.__fehltGesehen = true;
		}).observe(document.body, { childList: true, subtree: true, characterData: true });
	});
	await feld.locator('[data-segment="day"]').click();
	await page.keyboard.press('Backspace');
	await page.keyboard.press('Backspace');
	// bits-ui leert mit dem Tag das ganze Datum (alle Segmente) — also vollständig neu tippen.
	await page.keyboard.type('20112026');
	await verlasseFeld(page);
	await expect(feld.locator('[data-slot="datum-feld-eingabe"]')).toHaveText('20.11.2026');
	expect(await page.evaluate(() => (window as unknown as { __fehltGesehen: boolean }).__fehltGesehen), 'Hinweis flackerte beim Neueintippen').toBe(false);
	// Jahr nur dreistellig: beim Verlassen fehlt das Startdatum.
	await feld.locator('[data-segment="year"]').click();
	await page.keyboard.type('202');
	await verlasseFeld(page);
	await expect(page.getByText('Startdatum fehlt'), 'Hinweis nach angefangenem Jahr').toBeVisible();
	await expect(etappenReiter).toHaveAttribute('aria-disabled', 'true');
});

test('DS-4 Aktivität Standard (1280 px): „Wandern (Standard)" zurückwählen und anlegen ⇒ ohne Aktivität gespeichert', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	try {
		await anlegenPflicht(page, 'route', { name: `E2E-GZ-DS4-std-${Date.now()}` });
		await page.getByTestId('trip-new-tab-route').click();
		const ausloeser = page.getByTestId('activity-dropdown');
		await waehleOption(page, ausloeser, 'Hochtour');
		await expect(ausloeser).toHaveText('Hochtour');
		await waehleOption(page, ausloeser, 'Wandern (Standard)');
		await expect(ausloeser).toHaveText('Wandern (Standard)');
		const knopf = ANLEGE_SEL.route.standardwerte(page);
		await expect(knopf).toBeEnabled({ timeout: 15_000 });
		const id = await postId(page, '/api/trips', () => knopf.click());
		expect((await tripStand(page, id)).activity ?? '', 'Standard = keine Aktivität').toBe('');
	} finally {
		await cleanupTracked(page.request);
	}
});

// ─── DS-3 (AC-3) ────────────────────────────────────────────────────────────

/** Zustellung im Hub/Anlegen: Versand-Abschnitt, Mail-Inhalt-Karte, Speicher-Chip. */
const ZUSTELLUNG =
	'[data-testid="versand-abschnitt"], [data-testid="report-mail-content"], [data-testid="save-indicator"]';

/** Native Datums-/Uhrzeit-/Radio-Felder (im DOM), sichtbare native <select>, ✓/⊘ im sichtbaren Text. */
async function pruefeSeite(page: Page, seite: string, fehler: string[], bereich: string | null = null): Promise<void> {
	const r = await page.evaluate((bereich) => {
		const wurzeln = bereich ? Array.from(document.querySelectorAll<HTMLElement>(bereich)) : [document.body];
		const sichtbar = (el: Element) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
		const nativ: string[] = [];
		const symbole: string[] = [];
		for (const w of wurzeln) {
			for (const el of w.querySelectorAll('input[type="date"], input[type="time"], input[type="radio"]')) {
				nativ.push(`input[type=${el.getAttribute('type')}] ${el.getAttribute('data-testid') ?? el.getAttribute('name') ?? ''}`);
			}
			for (const el of w.querySelectorAll('select')) if (sichtbar(el)) nativ.push(`select ${el.getAttribute('data-testid') ?? ''}`);
			const text = w.innerText;
			for (const z of ['✓', '⊘']) {
				for (let i = text.indexOf(z); i >= 0; i = text.indexOf(z, i + 1)) {
					symbole.push(`${z} in „${text.slice(Math.max(0, i - 25), i + 25).replace(/\s+/g, ' ')}"`);
				}
			}
		}
		return { anzahl: wurzeln.length, nativ, symbole };
	}, bereich);
	if (r.anzahl === 0) fehler.push(`${seite}: Prüfbereich ${bereich} fehlt`);
	for (const n of r.nativ) fehler.push(`${seite}: natives Feld ${n}`);
	for (const s of r.symbole) fehler.push(`${seite}: Symbol ${s}`);
}

const ANLEGE_REITER = (kind: HubKind, id: string, mobil: boolean): string =>
	kind === 'route' ? `${mobil ? 'tn-mobile-tab' : 'trip-new-tab'}-${id}` : `${mobil ? 'cm-mobile-tab' : 'compare-editor-tab'}-${id}`;

for (const breite of BREITEN) {
	for (const lang of ['de', 'en'] as const) {
		test(`DS-3 (${breite.width} px, ${lang}): Listen, Hubs (Übersicht, Etappen/Orte, Zustellung) und Anlegen ohne native Datum/Uhrzeit/Radio/Select, ohne ✓/⊘`, async ({
			page
		}) => {
			test.setTimeout(180_000);
			const mobil = breite === MOBIL;
			await page.setViewportSize(breite);
			await setzeSprache(page, lang);
			const hubs = { route: await seedHub(page.request, 'route'), vergleich: await seedHub(page.request, 'vergleich') };
			const fehler: string[] = [];
			try {
				for (const kind of HUB_KINDS) {
					await page.goto(HUB_SEL[kind].liste.url);
					await expect(page.getByTestId(HUB_SEL[kind].liste.zeile(hubs[kind].id)).first()).toBeAttached({ timeout: 15_000 });
					await pruefeSeite(page, `${kind}-Liste`, fehler);
				}
				for (const kind of HUB_KINDS) {
					for (const tab of ['uebersicht', HUB_SEL[kind].punkteReiter]) {
						await openHub(page, kind, hubs[kind].id, { tab });
						await expect(page.locator(`[data-testid="${HUB_SEL[kind].panel}-${tab}"]:visible`).first()).toBeVisible({
							timeout: 15_000
						});
						await expect(page.getByTestId('save-indicator')).toBeVisible();
						await pruefeSeite(page, `${kind}-Hub ${tab}`, fehler);
					}
					// #2794 S3a: Versand und Mail-Inhalt stehen im Hub-Reiter „Zustellung".
					await openHub(page, kind, hubs[kind].id, { tab: 'zustellung' });
					await expect(page.locator('[data-testid="versand-abschnitt"]:visible').first()).toBeVisible({ timeout: 15_000 });
					await pruefeSeite(page, `${kind}-Hub Zustellung`, fehler, ZUSTELLUNG);
				}
				for (const kind of HUB_KINDS) {
					await page.goto(ANLEGE_SEL[kind].url);
					await expect(page.getByTestId(ANLEGE_REITER(kind, ANLEGE_SEL[kind].ersterSchritt, mobil))).toBeVisible({
						timeout: 15_000
					});
					await pruefeSeite(page, `${kind}-Anlegen erster Schritt`, fehler);
					// Der Pflichtangaben-Helfer klickt am Handy deutsche Beschriftungen ⇒ Folge-Schritte am Handy nur de.
					if (mobil && lang === 'en') continue;
					await anlegenPflicht(page, kind, { name: `E2E-GZ-DS3-${kind}-${Date.now()}`, mobil });
					await pruefeSeite(page, `${kind}-Anlegen ${ANLEGE_SEL[kind].punkteSchritt}`, fehler);
					// #2794 S3a: Anlege-Kette … → Wetter → Zustellung (Zustellung erst nach Wetter frei).
					await page.getByTestId(ANLEGE_REITER(kind, 'wetter', mobil)).click({ force: mobil });
					await page.getByTestId(ANLEGE_REITER(kind, 'zustellung', mobil)).click({ force: mobil });
					await expect(page.locator('[data-testid="versand-abschnitt"]:visible').first()).toBeVisible({ timeout: 15_000 });
					await pruefeSeite(page, `${kind}-Anlegen Zustellung`, fehler, ZUSTELLUNG);
				}
			} finally {
				await setzeSprache(page, 'de');
				for (const h of Object.values(hubs)) await h.aufraeumen();
				await cleanupTracked(page.request);
			}
			expect(fehler, fehler.join('\n')).toEqual([]);
		});
	}
}

// ─── DS-4 (AC-4) ────────────────────────────────────────────────────────────

test('DS-4 Aktivität: Auswahl beim Trip-Anlegen ist eine listbox, per Maus und Tastatur bedienbar, Fokus sichtbar, gespeichert', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	try {
		await anlegenPflicht(page, 'route', { name: `E2E-GZ-DS4-${Date.now()}` });
		await page.getByTestId('trip-new-tab-route').click();
		const ausloeser = page.getByTestId('activity-dropdown');
		await expect(ausloeser).toBeVisible({ timeout: 10_000 });
		const liste = page.getByRole('listbox');
		// Maus
		await ausloeser.click();
		await expect(liste, 'Auswahl öffnet keine listbox').toBeVisible({ timeout: 5_000 });
		await liste.getByRole('option', { name: 'Hochtour' }).click();
		await expect(liste).toBeHidden();
		await expect(ausloeser).toContainText('Hochtour');
		// Tastatur: Enter öffnet, Pfeil runter, Enter wählt
		await ausloeser.focus();
		await page.keyboard.press('Enter');
		await expect(liste).toBeVisible();
		await page.keyboard.press('ArrowDown');
		await page.keyboard.press('Enter');
		await expect(liste).toBeHidden();
		await expect(ausloeser).toContainText('Klettersteig');
		await expect(ausloeser).toBeFocused();
		const fokus = await ausloeser.evaluate((el) => {
			const s = getComputedStyle(el);
			return { sichtbar: el.matches(':focus-visible'), stil: s.outlineStyle, breite: s.outlineWidth };
		});
		expect(fokus.sichtbar && fokus.stil !== 'none' && fokus.breite !== '0px', `Fokus nicht sichtbar: ${JSON.stringify(fokus)}`).toBe(true);
		const knopf = ANLEGE_SEL.route.standardwerte(page);
		await expect(knopf).toBeEnabled({ timeout: 15_000 });
		const id = await postId(page, '/api/trips', () => knopf.click());
		expect((await tripStand(page, id)).activity, 'gespeicherte Aktivität').toBe('klettersteig');
	} finally {
		await cleanupTracked(page.request);
	}
});

test('DS-4 Mail-Format: Zustellung im Trip-Hub ist eine radiogroup, per Maus und Pfeiltaste bedienbar, Fokus sichtbar, gespeichert', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await setzeSprache(page, 'de');
	const hub = await seedHub(page.request, 'route');
	const format = async () =>
		((await tripStand(page, hub.id)).report_config as { email_format?: string } | undefined)?.email_format ?? 'full';
	const gruppe = page.getByTestId('report-email-format-switcher');
	const voll = gruppe.getByRole('radio', { name: /Ausführlich/ });
	const kompakt = gruppe.getByRole('radio', { name: /Kompakt/ });
	try {
		await openHub(page, 'route', hub.id, { tab: 'zustellung' });
		await expect(gruppe).toBeVisible({ timeout: 15_000 });
		await expect(gruppe, 'Mail-Format ist keine radiogroup').toHaveAttribute('role', 'radiogroup');
		await expect(voll).toBeChecked();
		// Maus
		await kompakt.click();
		await expect(kompakt).toBeChecked();
		await expect.poll(format, { message: 'Kompakt nicht gespeichert', timeout: 15_000 }).toBe('compact');
		await openHub(page, 'route', hub.id, { tab: 'zustellung' });
		await expect(kompakt).toBeChecked({ timeout: 15_000 });
		// Fix-Loop F-B3: nur der gewählte Eintrag liegt in der Tab-Reihenfolge (WAI-ARIA-Radiogroup) —
		// Umschalt+Tab vom gewählten verlässt die Gruppe, statt auf „Ausführlich" zu landen.
		await kompakt.focus();
		await page.keyboard.press('Shift+Tab');
		await expect(voll, 'Umschalt+Tab landet im nicht gewählten Eintrag (kein rollendes tabindex)').not.toBeFocused();
		await expect(kompakt).not.toBeFocused();
		// Tastatur: Pfeil links wählt das vorherige Format
		await kompakt.focus();
		await page.keyboard.press('ArrowLeft');
		await expect(voll).toBeFocused();
		await expect(voll).toBeChecked();
		const fokus = await voll.evaluate((el) => {
			const s = getComputedStyle(el);
			return { sichtbar: el.matches(':focus-visible'), stil: s.outlineStyle, breite: s.outlineWidth };
		});
		expect(fokus.sichtbar && fokus.stil !== 'none' && fokus.breite !== '0px', `Fokus nicht sichtbar: ${JSON.stringify(fokus)}`).toBe(true);
		await expect.poll(format, { message: 'Ausführlich nicht gespeichert', timeout: 15_000 }).toBe('full');
		await openHub(page, 'route', hub.id, { tab: 'zustellung' });
		await expect(voll).toBeChecked({ timeout: 15_000 });
	} finally {
		await hub.aufraeumen();
	}
});

// ─── DS-6 (AC-6) ────────────────────────────────────────────────────────────

async function messeTippflaechen(ziel: Locator, seite: string, mindestens: number, fehler: string[]): Promise<void> {
	// In EINEM Schritt gemessen (Rahmen wie boundingBox): Bereiche, die nach dem Laden neu aufbauen
	// (Wertebereiche im Reiter Wetter), tauschen sonst zwischen Zählen und Messen ihre Knoten.
	const boxen = await ziel.evaluateAll((els) =>
		els.map((el, i) => {
			const r = el.getBoundingClientRect();
			return { name: el.getAttribute('data-testid') ?? `#${i}`, breite: r.width, hoehe: r.height };
		})
	);
	if (boxen.length < mindestens) fehler.push(`${seite}: ${boxen.length} statt mindestens ${mindestens} Tippflächen gefunden`);
	for (const b of boxen) {
		if (b.breite + 0.01 < 44 || b.hoehe + 0.01 < 44) {
			fehler.push(`${seite} ${b.name}: ${b.breite.toFixed(1)} × ${b.hoehe.toFixed(1)} px (< 44 × 44)`);
		}
	}
}

async function pruefeUeberlauf(page: Page, seite: string, fehler: string[]): Promise<void> {
	const zuviel = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
	if (zuviel > 0) fehler.push(`${seite}: läuft waagerecht ${zuviel} px über`);
}

test('DS-6: Tippflächen am Handy (390 × 844) mindestens 44 × 44 — Zurück, Standardwerte, ⓘ, Schnellwahl, Wetter-Knöpfe — kein waagerechtes Überlaufen', async ({
	page
}) => {
	test.setTimeout(120_000);
	await page.setViewportSize(MOBIL);
	await setzeSprache(page, 'de');
	const fehler: string[] = [];
	const hubs = { route: await seedHub(page.request, 'route'), vergleich: await seedHub(page.request, 'vergleich') };
	try {
		for (const kind of HUB_KINDS) {
			const id = hubs[kind].id;
			await openHub(page, kind, id, { tab: 'uebersicht' });
			const zurueck = page.locator('[data-testid="back-link"]:visible');
			await expect(zurueck.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(zurueck, `${kind}-Hub Zurück`, 1, fehler);
			await pruefeUeberlauf(page, `${kind}-Hub Übersicht`, fehler);

			await openHub(page, kind, id, { tab: 'zustellung' });
			const chips = page.locator(
				'[data-testid^="report-morning-quickpick-"]:visible, [data-testid^="report-evening-quickpick-"]:visible'
			);
			await expect(chips.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(chips, `${kind}-Hub Schnellwahl`, 4, fehler);
			await pruefeUeberlauf(page, `${kind}-Hub Zustellung`, fehler);

			// ⓘ (Begriffserklärung) im Reiter Zustellung.
			const ii = page.locator('[data-testid^="begriff-erklaerung-"]:visible');
			await expect(ii.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(ii, `${kind}-Hub ⓘ`, 1, fehler);

			// #2794 Teil 3 (Spec feat_2794_s3a_teil3_wetter.md §4, AC-15): der Reiter Wetter ist der
			// WetterTab ohne ⓘ-Wertebereiche (CorridorEditor entfällt dort); gemessen werden seine
			// Tippflächen „−" (aus dem Briefing nehmen) und „Grenzen ändern".
			await openHub(page, kind, id, { tab: 'wetter' });
			const reiter = page.locator('[data-testid="wetter-tab"]:visible');
			await expect(reiter.getByTestId('wetter-tab-laden')).toHaveCount(0, { timeout: 15_000 });
			const wetterKnoepfe = reiter.locator('[data-testid^="wetter-zeile-entfernen-"], [data-testid^="wetter-grenzen-aendern-"]');
			await expect(wetterKnoepfe.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(wetterKnoepfe, `${kind}-Hub Wetter-Knöpfe`, 2, fehler);
			await pruefeUeberlauf(page, `${kind}-Hub Wetter`, fehler);
		}
		for (const kind of HUB_KINDS) {
			await page.goto(ANLEGE_SEL[kind].url);
			const zurueck = page.locator('[data-testid="back-link"]:visible');
			await expect(zurueck.first()).toBeVisible({ timeout: 15_000 });
			await messeTippflaechen(zurueck, `${kind}-Anlegen Zurück`, 1, fehler);
			const standard = page.locator(
				`[data-testid="${kind === 'route' ? 'tn-mobile-standardwerte' : 'cm-mobile-standardwerte'}"]:visible`
			);
			await messeTippflaechen(standard, `${kind}-Anlegen Standardwerte`, 1, fehler);
			await pruefeUeberlauf(page, `${kind}-Anlegen`, fehler);
		}
	} finally {
		for (const h of Object.values(hubs)) await h.aufraeumen();
	}
	expect(fehler, fehler.join('\n')).toEqual([]);
});
