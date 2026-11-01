<script lang="ts">
	// Issue #578 — MetricsEditorContextBar-Organism.
	// Kanonische Quelle: organisms.jsx::MetricsEditorContextBar
	//
	// Header oben im Metrics-Editor. Zeigt Profil-Name + Kontext + Counts.

	import { Eyebrow, Stat } from '$lib/components/atoms';
	import { t, type MessageKey } from '$lib/i18n';

	type Context = 'trip' | 'ort' | 'abo';

	interface Bucket {
		primary: string[];
		secondary: string[];
	}

	interface HorizonMap {
		[metricId: string]: { today?: boolean; tomorrow?: boolean; day_after?: boolean };
	}

	interface Props {
		context?: Context;
		preset?: { name: string; id?: string };
		buckets?: Bucket;
		horizons?: HorizonMap;
		score?: Record<string, boolean>;
		compact?: boolean;
		class?: string;
	}

	let {
		context = 'trip',
		preset = { name: '—' },
		buckets = { primary: [], secondary: [] },
		horizons,
		score,
		compact = false,
		class: className = ''
	}: Props = $props();

	// #2660: Katalog-Schluessel; Aufloesung zur Laufzeit ueber $t (folgt der Sprache).
	const CTX_LABEL: Record<Context, MessageKey> = {
		trip: 'bausteine.kontext.trip', ort: 'bausteine.kontext.ort', abo: 'bausteine.kontext.abo',
	};
	const ctxLabel = $derived($t(CTX_LABEL[context]));

	const CTX_DESC: Record<Context, MessageKey> = {
		trip: 'bausteine.kontext.trip_text', ort: 'bausteine.kontext.ort_text', abo: 'bausteine.kontext.abo_text',
	};
	const ctxDesc = $derived($t(CTX_DESC[context]));

	const horiCount = $derived(
		context === 'trip' && horizons
			? Object.values(horizons).reduce((acc, h) =>
				acc + (h?.today ? 1 : 0) + (h?.tomorrow ? 1 : 0) + (h?.day_after ? 1 : 0), 0)
			: 0
	);

	const scoreCount = $derived(
		context !== 'trip' && score
			? Object.values(score).filter(Boolean).length
			: 0
	);
</script>

<div
	style:display="flex"
	style:justify-content="space-between"
	style:align-items="flex-end"
	style:gap="16px"
	style:padding-bottom="12px"
	style:border-bottom="1px solid var(--g-rule-soft)"
	class={className}
>
	<div>
		<Eyebrow>{ctxLabel}</Eyebrow>
		<h2
			style:font-size={compact ? '18px' : '22px'}
			style:font-weight="600"
			style:letter-spacing="-0.01em"
			style:margin="2px 0 4px"
		>{preset.name}</h2>
		<div
			style:font-size={compact ? '11.5px' : '12.5px'}
			style:color="var(--g-ink-3)"
			style:max-width="620px"
			style:line-height="1.5"
		>{ctxDesc}</div>
	</div>

	<div style:display="flex" style:gap="18px" style:white-space="nowrap">
		<Stat label={$t('bausteine.metriken.spalten')} value={buckets.primary.length} size="md" mono />
		<Stat label={$t('bausteine.metriken.detail')} value={buckets.secondary.length} size="md" mono />
		{#if context === 'trip'}
			<Stat label={$t('bausteine.metriken.horizont_slots')} value={horiCount} size="md" mono tone="accent" />
		{:else}
			<Stat label={$t('bausteine.metriken.im_score')} value={scoreCount} size="md" mono tone="accent" />
		{/if}
	</div>
</div>
