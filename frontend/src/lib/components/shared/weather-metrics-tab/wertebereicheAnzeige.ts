// Issue #2654 (i18n F5, Epic #2644) — Anzeige-Ableitungen des Wertebereiche-/
// Wetter-Metriken-Reiters in EINER Sprache (Parameter `lang`, nie `get(locale)`:
// der Aufrufer liest `$locale` und rechnet damit bei einem Sprachwechsel neu).
// Nur Beschriftungen werden sprachabhaengig; Kennungen (`id`, `metric`, `key`,
// `aggregation`), Werte (`float`), Kurzform (`col_label`) und Kuerzel (`sms_code`)
// bleiben byte-gleich — die gespeicherte Nutzlast haengt nie an diesen Texten.
// Spec: docs/specs/modules/i18n_f5_wertebereiche_tab_2654.md

import { trFor, type Lang, type MessageKey } from '../../../i18n/index.ts';
import { metricLabel, metricAggregationLabel, type MetricLabelFields } from '../../../i18n/metricLabel.ts';
import { vergleichsMetrikLabel } from '../corridor-editor/compareMetricCatalogLoader.ts';
import { groupCompareCatalog, type CompareAggregationGroup } from './compareAggregationGrouping.ts';
import type { CompareSelectionEntry } from './compareMetricSelection.ts';

/** Vergleichs-Grundauswahl (eine Zeile je Groesse) mit denselben Namen/Auswertungen. */
export function vergleichsGruppen(
	katalog: CompareSelectionEntry[],
	register: Record<string, MetricLabelFields>,
	lang: Lang
): CompareAggregationGroup[] {
	return groupCompareCatalog(katalog).map((g) => ({
		...g,
		label: vergleichsMetrikLabel({ label: g.label, metric_id: g.metric_id }, register, lang),
		options: g.options.map((o) => ({
			...o,
			aggregation_label: o.aggregation_label ? metricAggregationLabel(o.aggregation, o.aggregation_label, lang) : ''
		}))
	}));
}

const STUFE: Record<'sensibel' | 'standard' | 'robust', MessageKey> = {
	sensibel: 'wertebereiche.schwelle.stufe.sensibel',
	standard: 'wertebereiche.schwelle.stufe.standard',
	robust: 'wertebereiche.schwelle.stufe.robust'
};

/** Die drei SMS-Schwellen-Stufen einer Groesse; `id` und `float` sind Bestandsdaten. */
export function schwellenStufen(sensibel: number, standard: number, robust: number, lang: Lang) {
	return [
		{ id: 'sensibel', label: trFor(lang, STUFE.sensibel), float: sensibel },
		{ id: 'standard', label: trFor(lang, STUFE.standard), float: standard },
		{ id: 'robust', label: trFor(lang, STUFE.robust), float: robust }
	];
}

/** Name einer Mehrfach-Symbol-Zeile aus dem Register; ohne Eintrag der deutsche Rueckfall. */
export function symbolZeilenName(register: Record<string, MetricLabelFields>, id: string, rueckfall: string, lang: Lang): string {
	const m = register[id];
	return m ? metricLabel(m, lang) : rueckfall;
}
