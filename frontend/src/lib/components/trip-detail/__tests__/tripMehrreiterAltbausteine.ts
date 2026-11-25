// Issue #3020 S1 — vom Mehrreiter-Pruefstand abgetrennter Teil: die Alt-Reiter Wetter-Metriken
// (WeatherMetricsTab) und Versand (BriefingScheduleTab), die kein Nutzer mehr sieht. Nutzer sind nur noch
// Tests, die ausschliesslich diese Oberflaechen pruefen. Faellt mit S3. Pfadregel #1409 wie im Pruefstand.

import { join } from 'node:path';
import { effekteVon } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import * as P from './tripMehrreiterPruefstand.ts';

export * from './tripMehrreiterPruefstand.ts';

const KOMPONENTEN = join(P.FRONTEND, 'src/lib/components');
export const DATEI = {
	...P.DATEI,
	wetterMetriken: join(KOMPONENTEN, 'shared/WeatherMetricsTab.svelte'),
	versand: join(KOMPONENTEN, 'trip-detail/BriefingScheduleTab.svelte')
} as const;

/** Wetter-Metriken-Reiter (route). `userTouched` = die Nutzergeste, ohne die der
 *  Reiter nie schreibt (`weatherSaveGate`). */
export async function wetterMetrikenReiter(a: P.Aufbau): Promise<{
	inst: P.Instanz;
	/** Metrik-Katalog-Geste: loest `scheduleAutoSave()` (/weather-config + Trip-PUT) aus. */
	metrikenSpeichern(): void;
	/** Nur Inhalt/Tagesfenster (`report_config`): `scheduleReportConfigOnlySave()`. */
	reportConfigSpeichern(aenderung: Record<string, unknown>): void;
}> {
	const inst = await P.bauen(DATEI.wetterMetriken, {
		...P.gemeinsam(a),
		context: 'route',
		createMode: false,
		catalogLoaded: true,
		untrack: (fn: () => unknown) => fn()
	});
	inst.u.userTouched = true;
	return {
		inst,
		metrikenSpeichern() {
			(inst.u.scheduleAutoSave as () => void)();
		},
		reportConfigSpeichern(aenderung) {
			inst.u.reportConfig = { ...(inst.u.reportConfig as Record<string, unknown>), ...aenderung };
			(inst.u.scheduleReportConfigOnlySave as () => void)();
		}
	};
}

/** Versand-Reiter (BriefingScheduleTab): Speichern haengt an einem `$effect`. */
export async function versandReiter(a: P.Aufbau): Promise<{
	inst: P.Instanz;
	/** Eine Aenderung an `report_config` (z. B. Versandzeit) und der Speicher-Effekt. */
	aendern(aenderung: Record<string, unknown>): void;
}> {
	const inst = await P.bauen(DATEI.versand, P.gemeinsam(a));
	inst.u.userTouched = true;
	return {
		inst,
		aendern(aenderung) {
			inst.u.reportConfig = { ...(inst.u.reportConfig as Record<string, unknown>), ...aenderung };
			for (const e of effekteVon(inst.ast, inst.quelle, inst.u, '_lastReportConfig')) e();
		}
	};
}
