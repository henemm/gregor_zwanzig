<script lang="ts">
	// Issue #559 — Briefing-Verlauf Modal für eine archivierte Tour (AC-1, AC-5, AC-6).
	// Spec: docs/specs/modules/issue_559_archiv_fertigstellen.md

	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Btn } from '$lib/components/atoms';

	interface BriefingEntry {
		sent_at: string;
		kind: string;
		channels: string[];
	}

	interface Props {
		open: boolean;
		tripId: string;
		tripName: string;
		onclose: () => void;
	}

	let { open, tripId, tripName, onclose }: Props = $props();

	let entries = $state<BriefingEntry[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);

	const KIND_LABELS: Record<string, string> = {
		morning: 'Morgen-Briefing',
		evening: 'Abend-Briefing'
	};

	function formatDate(isoStr: string): string {
		const d = new Date(isoStr);
		if (isNaN(d.getTime())) return isoStr;
		const dd = String(d.getDate()).padStart(2, '0');
		const mm = String(d.getMonth() + 1).padStart(2, '0');
		const yyyy = d.getFullYear();
		const hh = String(d.getHours()).padStart(2, '0');
		const min = String(d.getMinutes()).padStart(2, '0');
		return `${dd}.${mm}.${yyyy} ${hh}:${min}`;
	}

	$effect(() => {
		if (!open || !tripId) return;
		loading = true;
		error = null;
		entries = [];
		fetch(`/api/trips/${tripId}/briefing-history`)
			.then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
			.then((data: BriefingEntry[]) => {
				entries = data ?? [];
				loading = false;
			})
			.catch(() => {
				error = 'Fehler beim Laden des Briefing-Verlaufs.';
				loading = false;
			});
	});
</script>

<Dialog.Root
	{open}
	onOpenChange={(o) => {
		if (!o) onclose();
	}}
>
	<Dialog.Content style="max-width:540px;max-height:80vh;overflow-y:auto">
		<Dialog.Header>
			<Dialog.Title>Briefing-Verlauf — {tripName}</Dialog.Title>
			<Dialog.Description>Alle versendeten Briefings für diese Tour, neueste zuerst.</Dialog.Description>
		</Dialog.Header>

		{#if loading}
			<p style="padding:20px 0;font-size:13px;color:var(--g-ink-3)">Lade Briefing-Verlauf…</p>
		{:else if error}
			<p style="padding:20px 0;font-size:13px;color:var(--g-accent-deep)">{error}</p>
		{:else if entries.length === 0}
			<p style="padding:20px 0;font-size:13px;color:var(--g-ink-3)">
				Für diese Tour wurden noch keine Briefings versendet.
			</p>
		{:else}
			<div style="margin-top:8px;display:flex;flex-direction:column;gap:8px">
				{#each [...entries].reverse() as entry (entry.sent_at + entry.kind)}
					<div
						style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--g-paper-deep);border-radius:var(--g-r-2);border:1px solid var(--g-rule-soft)"
					>
						<div style="display:flex;flex-direction:column;gap:2px">
							<span style="font-size:13px;font-weight:600;color:var(--g-ink)">
								{KIND_LABELS[entry.kind] ?? entry.kind}
							</span>
							<span
								style="font-size:11px;font-family:var(--g-font-mono);color:var(--g-ink-3);letter-spacing:0.04em"
							>
								{formatDate(entry.sent_at)}
							</span>
						</div>
						<span
							style="font-size:11px;font-family:var(--g-font-mono);color:var(--g-ink-3);text-transform:uppercase;letter-spacing:0.12em"
						>
							{(entry.channels ?? []).join(', ')}
						</span>
					</div>
				{/each}
			</div>
		{/if}

		<Dialog.Footer style="margin-top:16px">
			<Btn variant="outline" onclick={onclose}>Schließen</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
