<script lang="ts">
	// Issue #582 — CompareTile Rewrite 1:1 nach molecules.jsx#CompareTile.
	//
	// Neu gegenüber #488:
	//   – Führender Status-Dot (good/neutral je Status)
	//   – Mono-Status-Eyebrow (9.5 px uppercase) + "· {Region}"
	//   – Meta-Zeile mono "{N} Orte · {Profil-Label}"
	//   – Kanal-Pills exakt wie JSX (kein ChannelChip-Atom)
	//   – Vollständiger Status-Fuß mit Rhythmus-Kurzlabel + "zuletzt {relativ}"
	//   – Aktiv-Akzentrand (3 px var(--g-accent))
	//
	// Unverändert gegenüber #488:
	//   – Props: sub, dense, compact, accent, onclick, onAction, class
	//   – data-testid="compare-tile-{id}"
	//   – Kebab stopPropagation (Muster #486/#626)
	//
	// Spec: docs/specs/modules/issue_582_compare_list_fidelity.md

	import type { ComparePreset } from '$lib/types.js';
	import {
		deriveStatusFromPreset,
		presetLocationsLabel,
		presetProfileLabel,
		presetTileScheduleLabel,
		relativeLastSent,
		presetChannels
	} from './subscriptionHelpers.js';
	import CompareKebab from './CompareKebab.svelte';

	// Status-Labels analog molecules.jsx COMPARE_STATUS_LABEL
	const STATUS_LABEL: Record<string, string> = {
		active: 'aktiv',
		paused: 'pausiert',
		draft: 'draft'
	};

	interface Props {
		sub: ComparePreset;
		dense?: boolean;
		compact?: boolean;
		accent?: boolean;
		onclick?: () => void;
		onAction?: (id: string) => void;
		class?: string;
	}

	let {
		sub,
		dense = false,
		compact = false,
		accent = false,
		onclick,
		onAction,
		class: className = ''
	}: Props = $props();

	const status = $derived(deriveStatusFromPreset(sub));
	const active = $derived(status === 'active');
	const draft  = $derived(status === 'draft');

	const channels     = $derived(presetChannels(sub));
	const profileLabel = $derived(presetProfileLabel(sub.profil));
	const locationsText = $derived(presetLocationsLabel(sub));
	const scheduleText  = $derived(presetTileScheduleLabel(sub));
	const lastSentText  = $derived(relativeLastSent(sub.letzter_versand));
	const region = $derived(
		((sub.display_config as Record<string, unknown> | undefined)?.region as string | undefined) ?? ''
	);

	let hover = $state(false);

	function handleClick() { onclick?.(); }
	function handleKey(e: KeyboardEvent) {
		if (!onclick) return;
		if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onclick(); }
	}

	// Dot-Farbe analog atoms.jsx Dot
	function dotColor(tone: 'good' | 'neutral'): string {
		return tone === 'good' ? 'var(--g-accent-good, #22c55e)' : 'var(--g-ink-4)';
	}
</script>

<div
	class={'compare-tile' + (className ? ' ' + className : '')}
	data-testid="compare-tile-{sub.id}"
	data-status={status}
	role={onclick ? 'button' : undefined}
	tabindex={onclick ? 0 : undefined}
	onclick={onclick ? handleClick : undefined}
	onkeydown={onclick ? handleKey : undefined}
	onmouseenter={() => (hover = true)}
	onmouseleave={() => (hover = false)}
	style:cursor={onclick ? 'pointer' : 'default'}
	style:text-align="left"
	style:width="100%"
	style:background="var(--g-card)"
	style:border-top="1px solid var(--g-rule)"
	style:border-right="1px solid var(--g-rule)"
	style:border-bottom="1px solid var(--g-rule)"
	style:border-color={hover && !dense ? 'var(--g-ink-3)' : 'var(--g-rule)'}
	style:border-left={active && accent ? '3px solid var(--g-accent)' : '1px solid var(--g-rule)'}
	style:border-radius="var(--g-r-3)"
	style:box-shadow={dense ? 'none' : hover ? 'var(--g-shadow-2, 0 6px 20px rgba(0,0,0,0.10))' : 'var(--g-shadow-1)'}
	style:transition="box-shadow 120ms, border-color 120ms"
	style:padding={dense ? '14px 14px' : '16px 18px'}
	style:min-height="44px"
	style:display="flex"
	style:flex-direction="column"
	style:gap={dense ? '10px' : '12px'}
	style:opacity={draft && !dense ? '0.94' : '1'}
>
	<!-- Kopf -->
	<div style:display="flex" style:align-items="flex-start" style:gap="10px">

		<!-- Status-Dot -->
		<span style:margin-top={dense ? '5px' : '6px'} style:flex-shrink="0">
			<svg width="7" height="7" viewBox="0 0 7 7" style:display="block">
				<circle cx="3.5" cy="3.5" r="3.5" fill={dotColor(active ? 'good' : 'neutral')} />
			</svg>
		</span>

		<!-- Name + Eyebrow + Region -->
		<div style:flex="1" style:min-width="0">
			<div
				style:font-size={dense ? '15px' : '15.5px'}
				style:font-weight="600"
				style:letter-spacing="-0.01em"
				style:line-height="1.25"
				style:white-space="nowrap"
				style:overflow="hidden"
				style:text-overflow="ellipsis"
			>{sub.name || '(ohne Namen)'}</div>

			<div style:display="flex" style:align-items="center" style:gap="7px" style:margin-top="3px">
				<span
					style:font-family="var(--g-font-mono)"
					style:font-size="9.5px"
					style:color="var(--g-ink-4)"
					style:text-transform="uppercase"
					style:letter-spacing="0.14em"
				>{STATUS_LABEL[status] ?? 'draft'}</span>
				{#if region}
					<span
						style:font-size="12px"
						style:color="var(--g-ink-3)"
						style:white-space="nowrap"
						style:overflow="hidden"
						style:text-overflow="ellipsis"
					>· {region}</span>
				{/if}
			</div>
		</div>

		<!-- Kebab — stopPropagation am Wrapper + im CompareKebab selbst (#486/#626) -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div
			style:flex-shrink="0"
			style:margin-top="2px"
			onclick={(e) => e.stopPropagation()}
		>
			<CompareKebab {status} onSelect={(id) => onAction?.(id)} />
		</div>
	</div>

	<!-- Meta mono: "N Orte · Profil-Label" -->
	<div
		style:font-family="var(--g-font-mono)"
		style:font-size={dense ? '11px' : '11.5px'}
		style:color="var(--g-ink-2)"
		style:letter-spacing="0.02em"
		style:padding-left="17px"
	>{locationsText}{profileLabel ? ` · ${profileLabel}` : ''}</div>

	<!-- Kanal-Pills (nicht im compact-Modus) -->
	{#if !compact}
		<div
			style:display="flex"
			style:flex-wrap="wrap"
			style:gap={dense ? '4px' : '5px'}
			style:padding-left="17px"
			style:min-height={dense ? '18px' : '20px'}
		>
			{#if channels.length === 0}
				<span
					style:font-family="var(--g-font-mono)"
					style:font-size={dense ? '10px' : '11px'}
					style:color="var(--g-ink-4)"
				>noch keine Kanäle</span>
			{:else}
				{#each channels as ch (ch)}
					<span
						style:font-family="var(--g-font-mono)"
						style:padding="2px 7px"
						style:font-size={dense ? '9.5px' : '10px'}
						style:letter-spacing="0.04em"
						style:border="1px solid var(--g-rule)"
						style:border-radius="var(--g-r-pill)"
						style:background="var(--g-card-alt)"
						style:color="var(--g-ink-2)"
					>{ch}</span>
				{/each}
			{/if}
		</div>
	{/if}

	<!-- Status-Fuß -->
	<div
		style:display="flex"
		style:align-items="center"
		style:justify-content="space-between"
		style:gap="8px"
		style:padding-left="17px"
		style:padding-top="11px"
		style:border-top="1px dashed var(--g-rule-soft)"
	>
		<span
			style:font-family="var(--g-font-mono)"
			style:font-size="11px"
			style:color="var(--g-ink-3)"
			style:letter-spacing="0.02em"
		>{draft ? 'Setup unvollständig' : scheduleText}</span>

		{#if !draft}
			<span
				style:display="inline-flex"
				style:align-items="center"
				style:gap="6px"
				style:font-size="11px"
				style:color="var(--g-ink-3)"
				style:flex-shrink="0"
			>
				<svg width="6" height="6" viewBox="0 0 6 6" style:display="block">
					<circle cx="3" cy="3" r="3" fill={dotColor(active ? 'good' : 'neutral')} />
				</svg>
				zuletzt {lastSentText || '—'}
			</span>
		{/if}
	</div>
</div>
