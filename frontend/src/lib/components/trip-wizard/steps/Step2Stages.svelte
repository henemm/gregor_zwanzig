<script lang="ts">
	// Step 2: GPX-Multi-Upload + Drag-Sort + Pause (Epic #136 Sub-Spec #162).
	// Quelle: docs/specs/modules/epic_136_step2_stages.md
	//
	// Layout (Spec §1):
	//   - Drop-Zone (Multi-File-Drag-Drop, klick = File-Picker, Enter/Space)
	//   - Pending-Region (Bulk-Datumspicker + "X Etappen anlegen"-Button)
	//   - Etappen-Liste (DnD-sortierbar) mit Pause-Inserter zwischen Rows
	//
	// Logik:
	//   - commitPending: naturalSort -> uploadGpx (sequenziell) -> wizard.addStage
	//   - DnD via svelte-dnd-action; nach finalize: wizard.recomputeStageDates()
	//   - Pause-Inserter: wizard.addPauseStageAt(afterIndex)
	//   - Auto-Datierung in WizardState; manueller Override setzt dateOverridden=true
	//
	// Safari/Factory: benannte Handler statt anonymer Closures (Spec §6, §7).

	import { getContext } from 'svelte';
	import Upload from '@lucide/svelte/icons/upload';
	import Plus from '@lucide/svelte/icons/plus';
	import { dndzone, type DndEvent } from 'svelte-dnd-action';
	import { flip } from 'svelte/animate';
	import { uploadGpx } from '$lib/api';
	import { naturalSort } from '$lib/utils/naturalSort.js';
	import type { Stage } from '$lib/types';
	import type { WizardState } from '../wizardState.svelte';
	import { addDays, isPauseStage } from '../wizardHelpers.ts';
	import StageRow from './StageRow.svelte';
	import TemplatePicker from '../templates/TemplatePicker.svelte';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// --- Local UI-State -----------------------------------------------------

	let dragOver = $state(false);
	let pendingFiles = $state<File[]>([]);
	let bulkStartDate = $state('');
	let uploading = $state(false);
	let uploadProgress = $state('');
	let uploadError = $state('');
	let fileInputEl: HTMLInputElement | null = $state(null);

	// --- Derivations --------------------------------------------------------

	const commitLabel = $derived(
		pendingFiles.length === 1 ? '1 Etappe anlegen' : `${pendingFiles.length} Etappen anlegen`
	);

	// nonPauseIndex pro Stage berechnen (Spec §5): Position unter den
	// nicht-Pause-Stages — Pausen geben -1 zurueck.
	function computeNonPauseIndices(stages: Stage[]): number[] {
		let counter = 0;
		return stages.map((s) => (isPauseStage(s) ? -1 : counter++));
	}

	const nonPauseIndices = $derived(computeNonPauseIndices(wizard.stages));

	// --- File-Buffer-Logik --------------------------------------------------

	function defaultBulkDate(): string {
		// Default: wizard.startDate + wizard.stages.length Tage
		// (so reiht sich der Bulk lueckenlos an die bisherigen Etappen an).
		if (typeof wizard.startDate === 'string' && wizard.startDate.length > 0) {
			return addDays(wizard.startDate, wizard.stages.length);
		}
		// Fallback: heute
		const now = new Date();
		const yyyy = now.getFullYear();
		const mm = String(now.getMonth() + 1).padStart(2, '0');
		const dd = String(now.getDate()).padStart(2, '0');
		return `${yyyy}-${mm}-${dd}`;
	}

	function bufferFiles(files: FileList | File[]) {
		const arr = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.gpx'));
		if (arr.length === 0) return;
		const wasEmpty = pendingFiles.length === 0;
		pendingFiles = [...pendingFiles, ...arr];
		uploadError = '';
		if (wasEmpty) {
			bulkStartDate = defaultBulkDate();
		}
	}

	async function commitPending(): Promise<void> {
		if (pendingFiles.length === 0) return;
		if (!bulkStartDate) {
			uploadError = 'Bitte Startdatum waehlen.';
			return;
		}

		uploading = true;
		uploadError = '';
		const sorted = naturalSort(pendingFiles, (f) => f.name);
		const start = bulkStartDate;
		const total = sorted.length;
		pendingFiles = [];

		let added = 0;
		for (let i = 0; i < sorted.length; i++) {
			const file = sorted[i];
			uploadProgress = `Lade ${i + 1} von ${total} Dateien...`;
			const stageDate = addDays(start, added);
			try {
				const stage = await uploadGpx(file, stageDate, 8);
				// id-Vergabe passiert zentral in wizard.addStage()
				// (Backend liefert ggf. keine id; DnD braucht stage.id als Key).
				wizard.addStage(stage);
				added += 1;
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				uploadError += `${file.name}: ${msg}\n`;
				console.error('GPX upload failed', file.name, e);
			}
		}

		uploading = false;
		uploadProgress = '';

		// Nach Upload: Auto-Datierung greift, falls startDate gesetzt.
		wizard.recomputeStageDates();
	}

	function cancelPending() {
		pendingFiles = [];
		uploadError = '';
	}

	// --- DnD-Handler --------------------------------------------------------

	function handleDndConsider(e: CustomEvent<DndEvent<Stage>>) {
		wizard.stages = e.detail.items;
	}

	function handleDndFinalize(e: CustomEvent<DndEvent<Stage>>) {
		wizard.stages = e.detail.items;
		wizard.recomputeStageDates();
	}

	// --- Drop-Zone ----------------------------------------------------------

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		if (e.dataTransfer?.files) {
			bufferFiles(e.dataTransfer.files);
		}
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		dragOver = true;
	}

	function handleDragLeave() {
		dragOver = false;
	}

	function handleDropZoneClick() {
		fileInputEl?.click();
	}

	function handleDropZoneKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			fileInputEl?.click();
		}
	}

	function handleFileInput(e: Event) {
		const input = e.target as HTMLInputElement;
		if (input.files) {
			bufferFiles(input.files);
			input.value = ''; // erneutes Auswaehlen derselben Files erlauben
		}
	}

	// --- Stage-Row-Handler --------------------------------------------------

	function handleStageDateChange(id: string, newDate: string) {
		const idx = wizard.stages.findIndex((s) => s.id === id);
		if (idx < 0) return;
		const next = wizard.stages.slice();
		next[idx] = { ...next[idx], date: newDate, dateOverridden: true };
		wizard.stages = next;
	}

	function handleStageDelete(id: string) {
		wizard.deleteStage(id);
	}

	// --- Pause-Inserter -----------------------------------------------------

	function makePauseInsertHandler(afterIndex: number) {
		return function handlePauseInsert() {
			wizard.addPauseStageAt(afterIndex);
		};
	}
</script>

<div
	data-testid="trip-wizard-step2-layout"
	class="grid gap-6 py-4 step2-grid"
>
	<div data-testid="trip-wizard-step2-stages" class="flex flex-col gap-6">
	<!-- Drop-Zone -->
	<div
		data-testid="trip-wizard-step2-dropzone"
		role="button"
		tabindex="0"
		aria-label="GPX-Dateien hierher ziehen oder klicken zum Auswaehlen"
		class="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
			{dragOver
			? 'border-[var(--g-accent)] bg-[var(--g-accent)]/5'
			: 'border-[var(--g-ink-faint)]/30 hover:border-[var(--g-accent)]/50'}"
		ondrop={handleDrop}
		ondragover={handleDragOver}
		ondragleave={handleDragLeave}
		onclick={handleDropZoneClick}
		onkeydown={handleDropZoneKeydown}
	>
		<Upload class="mx-auto mb-2 size-8 text-[var(--g-ink-faint)]" />
		<p class="font-medium">GPX-Dateien hierher ziehen</p>
		<p class="text-sm text-[var(--g-ink-faint)] mt-1">oder klicken zum Auswaehlen</p>
		<input
			bind:this={fileInputEl}
			type="file"
			accept=".gpx"
			multiple
			class="hidden"
			onchange={handleFileInput}
		/>
	</div>

	<!-- Pending-Region -->
	{#if pendingFiles.length > 0}
		<div
			data-testid="trip-wizard-step2-pending"
			class="rounded-md border border-[var(--g-ink-faint)]/30 p-4 space-y-3 bg-[var(--g-ink-faint)]/5"
		>
			<p class="text-sm" data-testid="trip-wizard-step2-pending-count">
				{pendingFiles.length} Datei(en) ausgewaehlt
			</p>
			<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
				<label class="sm:w-32 text-sm" for="bulk-stage-start-date">Startdatum</label>
				<input
					id="bulk-stage-start-date"
					data-testid="trip-wizard-step2-bulk-startdate"
					type="date"
					bind:value={bulkStartDate}
					class="h-9 rounded border border-[var(--g-ink-faint)]/40 bg-transparent px-2 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
				/>
			</div>
			<div class="flex items-center gap-2">
				<button
					type="button"
					data-testid="trip-wizard-step2-bulk-commit"
					onclick={commitPending}
					disabled={uploading}
					class="rounded-md bg-[var(--g-accent)] px-3 py-2 text-sm text-white disabled:opacity-50"
				>
					{commitLabel}
				</button>
				<button
					type="button"
					data-testid="trip-wizard-step2-bulk-cancel"
					onclick={cancelPending}
					disabled={uploading}
					class="rounded-md border border-[var(--g-ink-faint)]/40 px-3 py-2 text-sm disabled:opacity-50"
				>
					Abbrechen
				</button>
			</div>
		</div>
	{/if}

	{#if uploading}
		<p class="text-sm text-[var(--g-ink-faint)]">{uploadProgress}</p>
	{/if}

	{#if uploadError}
		<p class="text-sm text-[var(--g-danger)] whitespace-pre-line">{uploadError}</p>
	{/if}

	<!-- Etappen-Liste mit DnD + Pause-Inserter -->
	{#if wizard.stages.length > 0}
		<div
			data-testid="trip-wizard-step2-stage-list"
			class="flex flex-col gap-1"
			use:dndzone={{ items: wizard.stages, flipDurationMs: 200, dropTargetStyle: {} }}
			onconsider={handleDndConsider}
			onfinalize={handleDndFinalize}
		>
			{#each wizard.stages as stage, i (stage.id)}
				<div animate:flip={{ duration: 200 }} class="flex flex-col">
					<StageRow
						{stage}
						index={i}
						nonPauseIndex={nonPauseIndices[i]}
						onDateChange={handleStageDateChange}
						onDelete={handleStageDelete}
					/>
					<div class="flex justify-center py-1">
						<button
							type="button"
							data-testid="trip-wizard-step2-pause-after-{i}"
							onclick={makePauseInsertHandler(i)}
							class="opacity-0 hover:opacity-100 focus-visible:opacity-100 transition-opacity inline-flex items-center gap-1 rounded-full border border-[var(--g-ink-faint)]/30 bg-white/60 px-2 py-0.5 text-xs text-[var(--g-ink-faint)]"
							aria-label="Pausentag nach dieser Etappe einfuegen"
						>
							<Plus class="size-3" />
							Pause
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
	</div>

	<!-- Rechte Spalte: Vorlagen-Picker (Sub-Spec #165) -->
	<div>
		<TemplatePicker />
	</div>
</div>

<style>
	.step2-grid {
		grid-template-columns: 2fr minmax(0, 220px);
	}
	@media (max-width: 640px) {
		.step2-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
