<script lang="ts">
	import { t, locale } from '$lib/i18n';
	import { fmtWeekday } from '$lib/i18n/format';
	import DatumFeld from '$lib/components/molecules/DatumFeld.svelte';
	// Issue #498 — Etappen-Datum nachträglich bearbeiten.
	// Spec: docs/design-requests/stage_date_edit.md
	//
	// Dünner Wrapper um den Baustein molecules/DatumFeld (#2881 Lieferung B, vorher
	// natives <input type="date">) mit:
	//   - kleinem "DATUM"-Label (uppercase, muted, mono)
	//   - Wochentag-Chip (Mo/Di/…/So) aus ISO-Datum abgeleitet
	//   - optional "· TRIP-START"-Marker für die erste Etappe
	//
	// Svelte-5: $props, $bindable, $derived. Kein Legacy-Event-Handler-Syntax.
	//
	// onchange-Callback gibt den neuen ISO-String direkt zurück — so kann der
	// Parent (EditStagesPanelNew / PauseStageView) das Datum entweder via
	// bind ODER via Handler-Pattern übernehmen, ohne aus dem Event zu fischen.

	interface Props {
		value: string;
		isFirst?: boolean;
		onchange?: (newValue: string) => void;
		/** #2496: 'inline' = Label-los fuer Kartenkontext (mobile StageCardM). */
		variant?: 'default' | 'inline';
	}

	let { value = $bindable(''), isFirst = false, onchange, variant = 'default' }: Props = $props();

	// i18n F9: Wochentag je Sprache aus S2 (de `So`/`Mo` …, en `Sun`/`Mon` …).
	const wd = $derived(value ? fmtWeekday(new Date(value + 'T00:00:00'), $locale, true) : '—');

	function handleChange(newVal: string): void {
		value = newVal;
		onchange?.(newVal);
	}
</script>

{#if variant === 'inline'}
	<div class="box inline" data-testid="stage-date-field">
		<span class="wd">{wd}</span>
		<DatumFeld {value} onchange={handleChange} groesse="kompakt" ariaLabel={$t('trip.datum')} />
		{#if isFirst}<span class="trip-start">· {$t('trip.trip_start')}</span>{/if}
	</div>
{:else}
	<div class="stage-date" data-testid="stage-date-field">
		<span class="label">
			{$t('trip.datum')}{#if isFirst} · <em>{$t('trip.trip_start')}</em>{/if}
		</span>
		<div class="box">
			<span class="wd">{wd}</span>
			<DatumFeld {value} onchange={handleChange} groesse="kompakt" ariaLabel={$t('trip.datum')} />
		</div>
	</div>
{/if}

<style>
	.stage-date {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 4px;
		min-width: 168px;
	}

	.label {
		font-family: var(--g-font-data);
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--g-ink-muted);
	}

	.label em {
		font-style: normal;
		color: var(--g-ink);
	}

	.box {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 4px 6px 4px 4px;
		background: var(--g-card, #ffffff);
		border: 1px solid var(--g-rule);
		border-radius: 4px;
	}

	.wd {
		display: inline-block;
		padding: 3px 7px;
		background: var(--g-accent-tint);
		color: var(--g-accent-deep);
		font-family: var(--g-font-data);
		font-size: 11px;
		font-weight: 700;
		border-radius: 3px;
		font-variant-numeric: tabular-nums;
	}

	.box.inline {
		min-width: 0;
	}

	/* #2601: Touch — Trefferhöhe >= 36px (16 px gegen iOS-Auto-Zoom setzt DatumFeld selbst). */
	@media (max-width: 899px), (pointer: coarse) {
		.box {
			min-height: 36px;
		}
	}

	.trip-start {
		font-family: var(--g-font-data);
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--g-ink-muted);
		white-space: nowrap;
	}
</style>
