<script lang="ts">
	// Issue #372 — BriefingTimelineRow-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Vergangenheits-/Zukunfts-Zeile: ein geplanter oder gesendeter Briefing-
	// Versand. Status-getrieben (sent / planned).
	//   dense=true — Mobile-Layout: 24×24 ChannelChip compact, kein
	//                "gesendet/geplant"-Suffix, etwas weniger Padding.
	// Nutzt Dot + ChannelChip.
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-5)

	import { Dot } from '$lib/components/atoms';
	import ChannelChip from './ChannelChip.svelte';

	interface Report {
		when: string;
		kind: string;
		etappe?: string;
		channels?: string[];
		status?: 'sent' | 'planned' | string;
	}

	interface Props {
		report: Report;
		dense?: boolean;
		class?: string;
	}

	let { report, dense = false, class: className = '' }: Props = $props();

	const isSent = $derived(report.status === 'sent');
</script>

<div
	class={className}
	style:display="flex"
	style:align-items="center"
	style:gap={dense ? '10px' : '12px'}
	style:padding="10px 12px"
	style:background={isSent ? 'var(--g-card-alt)' : 'var(--g-card)'}
	style:border="1px solid var(--g-rule-soft)"
	style:border-radius="var(--g-r-2)"
>
	<Dot tone={isSent ? 'good' : 'neutral'} />
	<div style:flex="1" style:min-width="0">
		<div style:display="flex" style:gap="8px" style:align-items="baseline">
			<span
				style:font-family="var(--g-font-mono)"
				style:font-size="12px"
				style:font-weight={dense ? 600 : 500}
			>{report.when}</span>
			<span style:font-size="12px" style:color="var(--g-ink-3)" style:text-transform="capitalize">
				{report.kind}{dense ? '' : '-Briefing'}
			</span>
		</div>
		{#if report.etappe}
			<div
				style:font-family="var(--g-font-mono)"
				style:font-size={dense ? '10px' : '11px'}
				style:color="var(--g-ink-3)"
				style:margin-top="2px"
				style:overflow={dense ? 'hidden' : undefined}
				style:text-overflow={dense ? 'ellipsis' : undefined}
				style:white-space={dense ? 'nowrap' : undefined}
			>{report.etappe}</div>
		{/if}
	</div>
	<div style:display="flex" style:gap={dense ? '2px' : '4px'}>
		{#each report.channels ?? [] as c (c)}
			<ChannelChip kind={c} compact={dense} />
		{/each}
	</div>
	{#if !dense}
		<span
			style:font-family="var(--g-font-mono)"
			style:font-size="11px"
			style:color={isSent ? 'var(--g-good)' : 'var(--g-ink-3)'}
			style:min-width="60px"
			style:text-align="right"
			style:text-transform="uppercase"
			style:letter-spacing="0.06em"
		>{isSent ? 'gesendet' : 'geplant'}</span>
	{/if}
</div>
