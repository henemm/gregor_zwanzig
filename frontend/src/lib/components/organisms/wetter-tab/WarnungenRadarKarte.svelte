<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: Karte „Amtliche Warnungen & Radar" (AC-20, AC-21).
	// Ein Schalter fuer die amtlichen Warnungen (ODER-Regel beim Lesen, beide Felder beim Schreiben,
	// amtlicheWarnungen.ts); der Radar-Schalter nur, wenn der Aufrufer `mitRadar` setzt
	// (Orts-Briefing; Trip folgt mit S8 #2800).
	// #2913 Teil 2 (K-6): Zeilen aus dem Molekül Einstellungszeile.
	// #2913 Scheibe (c) (AC-2, AC-3, AC-6): Schalter aus dem Atom Switch (36×20, Tapfläche ≥ 44 px),
	// kein rohes Control und kein Eigen-Schalter-CSS mehr.
	import { Switch } from '$lib/components/atoms';
	import { Einstellungszeile } from '$lib/components/molecules';
	import { t } from '$lib/i18n';
	import { schalterZeilen } from './warnungenRadarZeilen.ts';

	interface Props {
		warnungenAn: boolean;
		radarAn: boolean;
		mitRadar: boolean;
		onWarnungen: (an: boolean) => void;
		onRadar: (an: boolean) => void;
	}
	let props: Props = $props();

	// Zuordnung Schalter → Handler als reine Daten (warnungenRadarZeilen.ts, ohne DOM geprüft). Das
	// Props-Objekt geht unverändert hinein (benannte Felder, keine einzeln vertauschbaren Argumente, F005).
	const zeilen = $derived(schalterZeilen(props));
</script>

<div class="wt-karte">
	{#each zeilen as z (z.testid)}
		<Einstellungszeile titel={$t(z.titel)} hinweis={$t(z.hinweis, { orte: $t('wetter.radar.deine_orte') })}>
			<Switch checked={z.an} testid={z.testid} tap aria-label={$t(z.titel)} onchange={z.umlegen} />
		</Einstellungszeile>
	{/each}
</div>

<style>
	.wt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
</style>
