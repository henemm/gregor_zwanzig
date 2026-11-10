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

import { test, expect } from '@playwright/test';
import { HUB_KINDS, type HubKind } from './helpers';
import {
	DESKTOP, WT, abweichungen, aktiveDerVorlage, auswahlImStand, fremdeFelder, istWetterSchreiben,
	oeffneWetter, seedWetter, stand, vorlagen, warteAufSpeichern, type Json
} from './s3a2794-teil3.helpers';

/** 3 Abweichungen von Alpen-Trekking: zwei Alarmstufen, eine Gewitterfarbe. */
const DREI = { metrics: { gust: { alarm_ab: 'red' }, uv_index: { alarm_ab: 'red' } }, thunder: { mittel: 'red' } };
const KONTEXT_WORT: Record<HubKind, string> = { route: 'Trips', vergleich: 'Orts-Briefings' };
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
			await expect(dialog).toContainText(
				`‚${v.wandern.label}‘ übernehmen? Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses ${KONTEXT_WORT[kind]}.`
			);
			await expect(dialog).toContainText(`Deine 3 Abweichungen von ‚${v['alpen-trekking'].label}‘ gehen verloren.`);
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
			expect(auswahlImStand(kind, nachher)).toEqual([...aktiveDerVorlage(v.wandern)].sort());
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
			await expect(knopf).toHaveText(`Auf ‚${v['alpen-trekking'].label}‘ zurücksetzen`);
			const speichern = warteAufSpeichern(page, kind, hub.id);
			await knopf.click();
			await speichern;
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');
			await expect(reiter.getByTestId(WT.zuruecksetzen)).toHaveCount(0);

			const s = await stand(page.request, kind, hub.id);
			expect(s.display_config.ampel.template).toBe('alpen-trekking');
			expect(s.display_config.ampel.metrics ?? {}).toEqual({});
			expect(auswahlImStand(kind, s)).toEqual([...aktiveDerVorlage(v['alpen-trekking'])].sort());
		} finally {
			await hub.aufraeumen();
		}
	});
}
