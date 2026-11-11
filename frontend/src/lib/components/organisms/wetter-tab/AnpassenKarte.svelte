<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: eingeklappte Karte „Anpassen" mit dem Tagesfenster (AC-21,
	// ADR-0035); gespeichert wird ueber den Reiter (Trip report_config, Orte top-level).
	// #2913 Scheibe (c) (AC-4, AC-5, AC-6): Aufklapper (Mockup `details.adv`) mit der Zeile
	// „Tagesfenster" und zwei Uhrzeitfeldern im Stundenraster (ganze Stunden, `day_window_*_hour`).
	// Fenster ueber Mitternacht (Ende < Start) ist gueltig und zeigt einen Hinweis; Ende = Start
	// verhindert clampDayWindowEndHour (PO-Entscheidung #1361/#1372).
	import { Aufklapper, Einstellungszeile } from '$lib/components/molecules';
	// UhrzeitFeld steht (wie DatumFeld) bewusst nicht im Barrel (bits-ui nur, wo gebraucht).
	import UhrzeitFeld from '$lib/components/molecules/UhrzeitFeld.svelte';
	import { t } from '$lib/i18n';
	import type { Tagesfenster } from '../../shared/wetter-tab/wetterZustand.ts';
	import { stundeAlsUhrzeit as hhmm, tagesfensterSteuerung } from './tagesfensterEingabe.ts';

	interface Props {
		tagesfenster: Tagesfenster;
		onStart: (h: number) => void;
		onEnde: (h: number) => void;
	}
	let { tagesfenster, onStart, onEnde }: Props = $props();

	const ueberMitternacht = $derived(tagesfenster.end < tagesfenster.start);

	// Verdrahtung (Stunde, Klemme, onStart/onEnde, Neuaufbau) in tagesfensterEingabe.ts (F004).
	let endeAufbau = $state(0);
	const steuerung = $derived(tagesfensterSteuerung({ fenster: () => tagesfenster, onStart, onEnde, onNeuAufbau: () => (endeAufbau += 1) }));
</script>

<div class="wt-karte">
	<Aufklapper titel={$t('wetter.anpassen.titel')} testid="wetter-anpassen-karte" summaryTestid="wetter-anpassen-aufklappen">
		<Einstellungszeile titel={$t('wetter.anpassen.tagesfenster')} hinweis={$t('wetter.anpassen.hinweis')}>
			<UhrzeitFeld stundenraster value={hhmm(tagesfenster.start)} testid="day-window-start-hour" ariaLabel={$t('wetter.anpassen.von')} onchange={steuerung.beiStart} />
			<span class="wt-strich" aria-hidden="true">–</span>
			{#key endeAufbau}
				<UhrzeitFeld stundenraster value={hhmm(tagesfenster.end)} testid="day-window-end-hour" ariaLabel={$t('wetter.anpassen.bis')} onchange={steuerung.beiEnde} />
			{/key}
		</Einstellungszeile>
		{#if ueberMitternacht}
			<p class="wt-hinweis" role="status" data-testid="day-window-wrap-hint">{$t('wetter.anpassen.ueber_mitternacht')}</p>
		{/if}
	</Aufklapper>
</div>

<style>
	.wt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.wt-strich {
		color: var(--g-ink-2);
	}
	.wt-hinweis {
		margin: 0;
		padding: 0 var(--g-s-5) var(--g-size-14px);
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	@media (max-width: 899px) {
		.wt-hinweis {
			padding: 0 var(--g-s-4) var(--g-size-14px);
		}
	}
</style>
