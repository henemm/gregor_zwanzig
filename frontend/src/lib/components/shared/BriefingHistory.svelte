<script lang="ts">
	// Issue #2281 — Versand-Historie als Inline-Liste im Reiter Übersicht.
	// EIN Baustein für Trip (kind="route") und Ortsvergleich (kind="vergleich").
	// Spec: docs/specs/modules/feat_2281_vergleich_versand_historie.md (AC-2)
	import { Card, Eyebrow } from '$lib/components/atoms';
	import { api } from '$lib/api.js';
	import {
		briefingHistoryUrl,
		type BriefingHistoryEntry,
		type BriefingHistoryKind
	} from './briefingHistory.ts';
	import type { BriefingHistoryLader } from './briefingHistoryLader.svelte.ts';

	interface Props {
		id: string;
		kind: BriefingHistoryKind;
		/** Gesetzt => direkt rendern, kein Abruf. */
		entries?: BriefingHistoryEntry[];
		/** Issue #2682: gesetzt => Liste aus diesem Lader (EIN Abruf, geteilt mit „Zuletzt raus"). */
		lader?: BriefingHistoryLader;
	}

	let { id, kind, entries = undefined, lader = undefined }: Props = $props();

	let eigeneGeladen = $state<BriefingHistoryEntry[]>([]);
	let eigenLoading = $state(false);
	let eigenError = $state<string | null>(null);
	const FEHLERTEXT = 'Versand-Historie konnte nicht geladen werden.';
	const geladen = $derived(lader ? lader.eintraege : eigeneGeladen);
	const loading = $derived(lader ? lader.zustand === 'laedt' : eigenLoading);
	const error = $derived(lader ? (lader.zustand === 'fehler' ? FEHLERTEXT : null) : eigenError);

	const SLOT_LABELS: Record<string, string> = { morning: 'Morgen', evening: 'Abend' };

	function formatDate(isoStr: string): string {
		const d = new Date(isoStr);
		if (isNaN(d.getTime())) return isoStr;
		const p = (n: number) => String(n).padStart(2, '0');
		return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
	}

	$effect(() => {
		if (entries !== undefined || lader || !id) return;
		const angefragt = id;
		eigenLoading = true;
		eigenError = null;
		api
			.get<BriefingHistoryEntry[]>(briefingHistoryUrl(id, kind))
			.then((data) => {
				if (angefragt !== id) return; // Stale-Guard
				eigeneGeladen = data ?? [];
				eigenLoading = false;
			})
			.catch(() => {
				if (angefragt !== id) return;
				eigenError = FEHLERTEXT;
				eigenLoading = false;
			});
	});

	// Neueste zuerst (der Log wird chronologisch angehängt).
	const liste = $derived([...(entries ?? geladen)].reverse());
</script>

<div data-testid="briefing-history" data-kind={kind}>
	<Card padding={18}>
		<Eyebrow style="margin-bottom: 10px;">Versand-Historie</Eyebrow>
		{#if entries === undefined && loading}
			<p class="bh-text">Lade Versand-Historie…</p>
		{:else if entries === undefined && error}
			<p class="bh-text">{error}</p>
		{:else if liste.length === 0}
			<p data-testid="briefing-history-empty" class="bh-text">Noch keine Briefings zugestellt.</p>
		{:else}
			<ul class="bh-list">
				{#each liste as entry, i (entry.sent_at + entry.kind + i)}
					<li
						data-testid="briefing-history-entry"
						data-channels={(entry.channels ?? []).join(',')}
						class="bh-row"
					>
						<span class="bh-slot">
							{SLOT_LABELS[entry.kind] ?? entry.kind}{#if entry.on_demand === true}<span class="bh-hand">
									· von Hand</span
								>{/if}
						</span>
						<time datetime={entry.sent_at} class="bh-meta">{formatDate(entry.sent_at)}</time>
						<span class="bh-meta bh-channels">{(entry.channels ?? []).join(', ')}</span>
					</li>
				{/each}
			</ul>
		{/if}
	</Card>
</div>

<style>
	.bh-text {
		font-size: 13px;
		color: var(--g-ink-2);
		margin: 0;
	}
	.bh-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
	}
	.bh-row {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 12px;
		padding: 8px 0;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.bh-slot {
		font-size: 13px;
		font-weight: 600;
		color: var(--g-ink);
	}
	.bh-hand {
		font-weight: 400;
		color: var(--g-ink-2);
	}
	.bh-meta {
		font-size: 12px;
		font-family: var(--g-font-mono);
		color: var(--g-ink-2);
	}
	.bh-channels {
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
</style>
