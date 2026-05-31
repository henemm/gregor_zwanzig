<script lang="ts">
	// Issue #472 — Eine Tabellenzeile der Orts-Vergleich-Übersicht (ComparePreset-basiert).
	//
	// Spec: docs/specs/modules/issue_472_compare_list_restore.md §4
	// Eltern-Komponente: CompareList.svelte (Delete wird dort gehandhabt).
	//
	// History: Ursprünglich #439 (Subscription); auf ComparePreset migriert in #472.

	import type { ComparePreset } from '$lib/types.js';
	import { Pill } from '$lib/components/atoms';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import {
		STATUS_MAP,
		deriveStatusFromPreset,
		presetScheduleLabel,
		presetLocationsLabel,
		formatLastSent
	} from './subscriptionHelpers.js';

	// Status-Dot-Tokens (single source: subscriptionHelpers.STATUS_MAP):
	//   active  → var(--g-accent)
	//   paused  → var(--g-ink-3)
	//   draft   → var(--g-ink-4)

	import PauseIcon from '@lucide/svelte/icons/pause';
	import EyeIcon from '@lucide/svelte/icons/eye';
	import SendIcon from '@lucide/svelte/icons/send';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';

	interface Props {
		preset: ComparePreset;
		ondelete?: () => void;
	}

	let { preset, ondelete }: Props = $props();

	let status = $derived(deriveStatusFromPreset(preset));
	let statusInfo = $derived(STATUS_MAP[status]);

	// Aus preset.empfaenger ableiten: enthält E-Mail-Adressen → "E-Mail";
	// Signal/Telegram aktuell nicht im ComparePreset abgebildet.
	let activeChannels = $derived(
		preset.empfaenger.length > 0 ? ['E-Mail'] : []
	);

	let sendOpen = $state(false);
	let previewOpen = $state(false);

	const ACTION_BTN =
		'inline-flex items-center justify-center w-[30px] h-[30px] rounded-[var(--g-r-2)] border border-[var(--g-rule-soft)] hover:bg-muted/60 transition-colors';
	const ACTION_BTN_DISABLED =
		'inline-flex items-center justify-center w-[30px] h-[30px] rounded-[var(--g-r-2)] border border-[var(--g-rule-soft)] text-[var(--g-ink-4)] opacity-50 cursor-not-allowed';
</script>

<Table.Row>
	<!-- Name + Status -->
	<Table.Cell>
		<div class="flex items-center gap-2 min-w-0">
			<span
				aria-hidden="true"
				class="inline-block shrink-0 rounded-full"
				style="width:8px;height:8px;background:{statusInfo.dot}"
			></span>
			<div class="flex flex-col min-w-0">
				<div class="flex items-center gap-2 min-w-0">
					<span class="font-semibold truncate">{preset.name || '(ohne Namen)'}</span>
					<Pill>{statusInfo.label}</Pill>
				</div>
			</div>
		</div>
	</Table.Cell>

	<!-- Orte (basiert auf preset.location_ids.length) -->
	<Table.Cell class="text-sm" data-location-count={preset.location_ids.length}
		>{presetLocationsLabel(preset)}</Table.Cell
	>

	<!-- Profil -->
	<Table.Cell class="text-sm">{preset.profil ?? '—'}</Table.Cell>

	<!-- Kanäle -->
	<Table.Cell>
		{#if activeChannels.length === 0}
			<span class="text-muted-foreground">—</span>
		{:else}
			<div class="flex flex-wrap gap-1">
				{#each activeChannels as ch}
					<Pill>{ch}</Pill>
				{/each}
			</div>
		{/if}
	</Table.Cell>

	<!-- Versand -->
	<Table.Cell>
		<div class="flex flex-col">
			<span class="font-mono tabular-nums text-sm">{presetScheduleLabel(preset)}</span>
			<span class="text-xs text-muted-foreground">Zuletzt: {formatLastSent(preset.letzter_versand)}</span>
		</div>
	</Table.Cell>

	<!-- Aktionen -->
	<Table.Cell class="text-right">
		<div class="inline-flex items-center gap-1">
			<button
				type="button"
				class={ACTION_BTN_DISABLED}
				title="Pause/Aktivieren — folgt"
				aria-label="Pause/Aktivieren — folgt"
				disabled
			>
				<PauseIcon class="size-3.5" />
			</button>
			<button
				type="button"
				class={ACTION_BTN}
				title="Jetzt senden"
				aria-label="Jetzt senden"
				onclick={() => (sendOpen = true)}
			>
				<SendIcon class="size-3.5" />
			</button>
			<button
				type="button"
				class={ACTION_BTN}
				title="Vorschau"
				aria-label="Vorschau"
				onclick={() => (previewOpen = true)}
			>
				<EyeIcon class="size-3.5" />
			</button>
			<span aria-hidden="true" class="text-muted-foreground mx-0.5">|</span>
			<button
				type="button"
				class={ACTION_BTN_DISABLED}
				title="Bearbeiten — folgt"
				aria-label="Bearbeiten — folgt"
				disabled
				data-edit-href={'/compare/' + preset.id + '/edit'}
			>
				<PencilIcon class="size-3.5" />
			</button>
			<button
				type="button"
				class={ACTION_BTN}
				title="Löschen"
				aria-label="Löschen"
				onclick={() => ondelete?.()}
			>
				<Trash2Icon class="size-3.5" />
			</button>
		</div>
	</Table.Cell>
</Table.Row>

<!-- Send-Stub (Issue #440) -->
<Dialog.Root open={sendOpen} onOpenChange={(o) => { if (!o) sendOpen = false; }}>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Sofort senden</Dialog.Title>
		</Dialog.Header>
		<p class="text-sm">Sofortversand folgt in #440</p>
	</Dialog.Content>
</Dialog.Root>

<!-- Preview-Stub (Issue #440) -->
<Dialog.Root open={previewOpen} onOpenChange={(o) => { if (!o) previewOpen = false; }}>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Vorschau</Dialog.Title>
		</Dialog.Header>
		<p class="text-sm">Vorschau folgt in #440</p>
	</Dialog.Content>
</Dialog.Root>
