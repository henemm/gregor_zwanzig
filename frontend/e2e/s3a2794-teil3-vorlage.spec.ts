// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Vorlage-Karte (AC-10, AC-11, AC-12, AC-13, AC-28 live).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich); AC-13 ist der vergleich-Lauf von AC-10/AC-11.
//
//   AC-10 — Picker: 7 Systemvorlagen mit Kurzbeschreibung (Metrikzahl aus /api/templates, nicht fest),
//           darunter „Eigene“ nur mit Vorlagen der passenden Art; Status „unverändert“ / „{n} Abweichungen“.
//   AC-11 — Wechsel mit Rueckfrage: Abbrechen aendert nichts, Uebernehmen ersetzt Auswahl/Grenzen/Alarmstufen,
//           Zustellung, Etappen und Orte bleiben (API-Zustand vorher/nachher); ohne Abweichungen kein Verlust-Satz.
//   AC-12 — „Auf ‚{Vorlage}‘ zuruecksetzen“: Zustand wie Vorlage, „unverändert“, Knopf verschwindet.
//   AC-28 — Picker zeigt die Zahl nach einer Eingabe sofort (vor dem Speichern).
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-vorlage

import { test, expect, type APIRequestContext } from '@playwright/test';
import { HUB_KINDS, type HubKind } from './helpers';
import {
	DESKTOP, WT, abgeleiteteKinder, abweichungen, aktiveDerVorlage, auswahlImStand, fremdeFelder, istWetterSchreiben,
	oeffneWetter, seedWetter, stand, vorlagen, warteAufSpeichern, type Json
} from './s3a2794-teil3.helpers';

/** Was der Vergleich ausgeben kann: `metric_id`s aus `/api/compare/metrics` (Trip: alles). */
const AUSGEBBAR: Record<HubKind, (request: APIRequestContext) => Promise<(id: string) => boolean>> = {
	route: async () => () => true,
	vergleich: async (request) => {
		const r = await request.get('/api/compare/metrics');
		expect(r.ok(), `GET /api/compare/metrics HTTP ${r.status()}`).toBeTruthy();
		const ids = new Set(((await r.json()) as { metrics: { metric_id?: string }[] }).metrics.map((m) => m.metric_id));
		return (id) => ids.has(id);
	}
};

/** Auswahl nach „Übernehmen“/„Zurücksetzen“ (#3193 AC-7, angeglichen an #3047 E6/E7): Trip mit den
 *  abgeleiteten Kindern, die p5c ausdruecklich in `metrics[]` schreibt; Vergleich nur ausgebbare Groessen
 *  (`temperature_night` fehlt dort gewollt). Die Abweichung `ampel.metrics` bleibt davon unberuehrt leer. */
async function auswahlNachVorlage(request: APIRequestContext, kind: HubKind, v: Json): Promise<string[]> {
	const aktiv = aktiveDerVorlage(v);
	const ausgebbar = await AUSGEBBAR[kind](request);
	return [...new Set([...aktiv, ...abgeleiteteKinder(kind, aktiv)])].filter(ausgebbar).sort();
}

/** 3 Abweichungen von Alpen-Trekking: zwei Alarmstufen, eine Gewitterfarbe. */
const DREI = { metrics: { gust: { alarm_ab: 'red' }, uv_index: { alarm_ab: 'red' } }, thunder: { mittel: 'red' } };
// #3111 AC-6 (Mockup Fassung 4): Rumpf der Bestätigung je Kontext (Orte: Einzahl oder Mehrzahl nach Ortezahl).
const ERSETZT: Record<HubKind, RegExp> = {
	route: /Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Trips\./,
	vergleich: /Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen für dies(en Ort|e Orte)\./
};
const ANDERE: Record<HubKind, HubKind> = { route: 'vergleich', vergleich: 'route' };

for (const kind of HUB_KINDS) {
	test(`AC-10/AC-13 (${kind}): Picker mit 7 Systemvorlagen, Metrikzahl aus /api/templates, „Eigene“ nur passende Art`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking' });
		const name = `E2E-GZ-Eigene-${kind}-${Date.now()}`;
		const fremd = `E2E-GZ-Fremd-${kind}-${Date.now()}`;
		const angelegt: string[] = [];
		try {
			for (const [n, k] of [[name, kind], [fremd, ANDERE[kind]]] as const) {
				const r = await page.request.post('/api/metric-presets', { data: { name: n, kind: k, metrics: [{ metric_id: 'wind', enabled: true, use_friendly_format: false }] } });
				expect(r.ok(), `Eigene Vorlage ${n}: ${r.status()}`).toBeTruthy();
				angelegt.push(((await r.json()) as Json).id);
			}
			const v = await vorlagen(page.request);
			const reiter = await oeffneWetter(page, kind, hub.id);
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');
			await expect(reiter.getByTestId(WT.picker)).toContainText(v['alpen-trekking'].label);
			await reiter.getByTestId(WT.picker).click();
			const optionen = page.locator('[data-testid^="wetter-vorlage-option-"]:visible');
			await expect(optionen).toHaveCount(7);
			for (const [id, t] of Object.entries(v)) {
				await expect(page.getByTestId(WT.vorlageOption(id))).toContainText(t.label);
				await expect(page.getByTestId(WT.vorlageBeschreibung(id))).toContainText(`${aktiveDerVorlage(t).length} Metriken`);
			}
			const eigene = page.getByTestId(WT.eigeneGruppe);
			await expect(eigene).toContainText('Eigene');
			await expect(eigene).toContainText(name);
			await expect(eigene, `AC-10: Vorlage der Art ${ANDERE[kind]} erscheint im Kontext ${kind}`).not.toContainText(fremd);
		} finally {
			for (const id of angelegt) await page.request.delete(`/api/metric-presets/${id}`).catch(() => {});
			await hub.aufraeumen();
		}
	});

	test(`AC-11/AC-13 (${kind}): Wechsel Alpen-Trekking -> Wandern mit 3 Abweichungen: Abbrechen aendert nichts, Uebernehmen ersetzt`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking', ampel: DREI });
		try {
			const v = await vorlagen(page.request);
			const vorher = await stand(page.request, kind, hub.id);
			const reiter = await oeffneWetter(page, kind, hub.id);
			expect(await abweichungen(reiter)).toBe(3);

			const schreib: string[] = [];
			page.on('request', (r) => istWetterSchreiben(kind, hub.id)(r) && schreib.push(r.url()));

			await reiter.getByTestId(WT.picker).click();
			await page.getByTestId(WT.vorlageOption('wandern')).click();
			const dialog = page.getByTestId(WT.wechselDialog);
			await expect(dialog.locator('b')).toHaveText(`„${v.wandern.label}“ übernehmen?`);
			await expect(dialog).toContainText(ERSETZT[kind]);
			await expect(dialog).toContainText(`Deine 3 Abweichungen von „${v['alpen-trekking'].label}“ gehen verloren.`);
			await expect(dialog).toContainText('Zustellung, Etappen und Orte bleiben unverändert.');
			await dialog.getByTestId(WT.wechselAbbrechen).click();
			await expect(dialog).toHaveCount(0);
			expect(await abweichungen(reiter)).toBe(3);
			await page.reload();
			const r2 = await oeffneWetter(page, kind, hub.id);
			expect(schreib, 'AC-11: „Abbrechen“ hat gespeichert').toEqual([]);
			expect((await stand(page.request, kind, hub.id)).display_config).toEqual(vorher.display_config);

			await r2.getByTestId(WT.picker).click();
			await page.getByTestId(WT.vorlageOption('wandern')).click();
			const speichern = warteAufSpeichern(page, kind, hub.id);
			await page.getByTestId(WT.wechselDialog).getByTestId(WT.wechselUebernehmen).click();
			await speichern;
			await expect(r2.getByTestId(WT.pickerStatus)).toHaveText('unverändert');
			await expect(r2.getByTestId(WT.picker)).toContainText(v.wandern.label);

			const nachher = await stand(page.request, kind, hub.id);
			expect(nachher.display_config.ampel.template).toBe('wandern');
			expect(nachher.display_config.ampel.metrics ?? {}, 'alte Abweichungen ueberleben').toEqual({});
			expect(nachher.display_config.ampel.thunder ?? {}).toEqual({});
			expect(auswahlImStand(kind, nachher)).toEqual(await auswahlNachVorlage(page.request, kind, v.wandern));
			expect(fremdeFelder(kind, nachher), 'AC-11: Zustellung/Etappen/Orte veraendert').toEqual(fremdeFelder(kind, vorher));
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-11 (${kind}): ohne Abweichungen entfaellt der Verlust-Satz`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking' });
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			await reiter.getByTestId(WT.picker).click();
			await page.getByTestId(WT.vorlageOption('wandern')).click();
			const dialog = page.getByTestId(WT.wechselDialog);
			await expect(dialog).toContainText('Zustellung, Etappen und Orte bleiben unverändert.');
			await expect(dialog).not.toContainText('gehen verloren');
			await dialog.getByTestId(WT.wechselAbbrechen).click();
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-12/AC-28 (${kind}): Zaehler sofort, Zuruecksetzen auf die Vorlage, Knopf verschwindet`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking' });
		try {
			const v = await vorlagen(page.request);
			const reiter = await oeffneWetter(page, kind, hub.id);
			await expect(reiter.getByTestId(WT.zuruecksetzen)).toHaveCount(0);
			// AC-28: eine Eingabe -> Zahl sofort (ohne auf das Speichern zu warten)
			await reiter.getByTestId(WT.zeile('gust')).getByTestId(WT.alarmAbStufe('gust', 'red')).click();
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('1 Abweichung');
			await reiter.getByTestId(WT.zeile('wind')).getByTestId(WT.alarmAbStufe('wind', 'red')).click();
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('2 Abweichungen');
			await warteAufSpeichern(page, kind, hub.id);

			const knopf = reiter.getByTestId(WT.zuruecksetzen);
			await expect(knopf).toHaveText(`Auf „${v['alpen-trekking'].label}“ zurücksetzen`);
			const speichern = warteAufSpeichern(page, kind, hub.id);
			await knopf.click();
			await speichern;
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');
			await expect(reiter.getByTestId(WT.zuruecksetzen)).toHaveCount(0);

			const s = await stand(page.request, kind, hub.id);
			expect(s.display_config.ampel.template).toBe('alpen-trekking');
			expect(s.display_config.ampel.metrics ?? {}).toEqual({});
			expect(auswahlImStand(kind, s)).toEqual(await auswahlNachVorlage(page.request, kind, v['alpen-trekking']));
		} finally {
			await hub.aufraeumen();
		}
	});

	// #3192 AC-8 (#3111 Adversary F004): frisch gespeicherte eigene Vorlage steht ohne Neuladen im Menü,
	// Unterzeile „eigene · <Beschreibung>“ (Mockup Fassung 4). Schreibend, eigener Datensatz, Aufräumen im finally.
	test(`#3192 AC-8 (${kind}): eigene Vorlage mit Beschreibung speichern, ohne Neuladen „eigene · <Beschreibung>“ im Menü`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking' });
		const name = `E2E-GZ-F004-${kind}-${Date.now()}`;
		const beschreibung = `F004 Beschreibung ${kind}`;
		let presetId: string | null = null;
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			await reiter.getByTestId(WT.alsEigene).click();
			const dialog = page.getByTestId(WT.dialog);
			await dialog.getByTestId(WT.dialogName).fill(name);
			await dialog.getByTestId(WT.dialogBeschreibung).fill(beschreibung);
			const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/metric-presets');
			await dialog.getByTestId(WT.dialogSpeichern).click();
			const antwort = await post;
			expect(antwort.ok(), `POST /api/metric-presets: ${antwort.status()}`).toBeTruthy();
			presetId = String(((await antwort.json()) as Json).id);
			await expect(page.getByTestId(WT.dialogErfolg)).toBeVisible({ timeout: 15_000 });

			// ohne page.reload(): Menü öffnen und die neue Zeile lesen
			await reiter.getByTestId(WT.picker).click();
			const zeile = page.getByTestId(WT.eigeneOption(presetId));
			await expect(zeile).toContainText(name);
			await expect(zeile).toContainText(`eigene · ${beschreibung}`);
			await page.keyboard.press('Escape');
		} finally {
			if (presetId) await page.request.delete(`/api/metric-presets/${presetId}`).catch(() => {});
			else
				for (const p of (await (await page.request.get('/api/metric-presets')).json().catch(() => [])) as Json[])
					if (p.name === name) await page.request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
			await hub.aufraeumen();
		}
	});
}
