<script lang="ts">
	// Step 1 (Issue #300: "Route"): Eckdaten des Trips + GPX-Upload.
	// Quelle: docs/specs/modules/issue_300_wizard_redesign.md
	//
	// Verantwortlich fuer:
	//   - 3 Eingabefelder: Name (Pflicht), Region (optional, max 50),
	//     Startdatum (Pflicht, type=date)
	//   - GPX-Upload (AC-3 #300: von Step 2 hierher verschoben — Dropzone +
	//     Pending-Region + Commit-Button). Logik byte-gleich zu Step2Stages.
	//   - Bindung an WizardState (via getContext)
	//   - Hilfetext zum Enddatum (wird in Schritt 2 berechnet)
	//
	// AC-2 #300: Aktivitaetsprofil ist KEIN Pflichtfeld mehr — es wird in
	// Step 3 (Wetter) gewaehlt. Die Activity-Chips wurden hier entfernt.
	// AC-3 #300: Kuerzel-Feld entfernt; GPX-Upload nach hier verschoben.
	//
	// Validierungs-/Disabled-Logik liegt zentral in WizardState.canAdvanceStep1
	// und wird vom Shell-Footer ausgelesen.
	//
	// Safari/Factory: benannte Handler statt anonymer Closures.

	import { getContext } from 'svelte';
	import UploadIcon from '@lucide/svelte/icons/upload';
	import { uploadGpx } from '$lib/api';
	import { naturalSort } from '$lib/utils/naturalSort.js';
	import type { Stage } from '$lib/types';
	import type { WizardState } from '../wizardState.svelte';
	import { addDays } from '../wizardHelpers.ts';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// --- GPX-Upload State (aus Step2Stages verschoben) ----------------------

	let dragOver = $state(false);
	let pendingFiles = $state<File[]>([]);
	let bulkStartDate = $state('');
	let uploading = $state(false);
	let uploadProgress = $state('');
	let uploadError = $state('');
	let fileInputEl: HTMLInputElement | null = $state(null);

	const commitLabel = $derived(
		pendingFiles.length === 1 ? '1 Etappe anlegen' : `${pendingFiles.length} Etappen anlegen`
	);

	function defaultBulkDate(): string {
		if (typeof wizard.startDate === 'string' && wizard.startDate.length > 0) {
			return addDays(wizard.startDate, wizard.stages.length);
		}
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
			uploadError = 'Bitte Startdatum wählen.';
			return;
		}

		uploading = true;
		uploadError = '';
		const files = pendingFiles;
		const start = bulkStartDate;
		const total = files.length;
		pendingFiles = [];

		const uploaded: Stage[] = [];
		let added = 0;
		for (let i = 0; i < files.length; i++) {
			const file = files[i];
			uploadProgress = `Lade ${i + 1} von ${total} Dateien...`;
			const stageDate = addDays(start, added);
			try {
				const stage = await uploadGpx(file, stageDate, 8);
				uploaded.push(stage);
				added += 1;
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				uploadError += `${file.name}: ${msg}\n`;
				console.error('GPX upload failed', file.name, e);
			}
		}

		const sorted = naturalSort(uploaded, (s) => s.name);
		for (const stage of sorted) {
			wizard.addStage(stage);
		}

		uploading = false;
		uploadProgress = '';
		wizard.recomputeStageDates();
	}

	function cancelPending() {
		pendingFiles = [];
		uploadError = '';
	}

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
			input.value = '';
		}
	}
</script>

<div data-testid="trip-wizard-step1-profile" class="flex flex-col gap-6 py-4">
	<section class="flex flex-col gap-4">
		<span class="text-xs uppercase tracking-wide text-[var(--g-ink-muted)]">Eckdaten</span>

		<label class="flex flex-col gap-1 text-sm">
			<span>Name <span class="text-[var(--g-accent-deep)]">*</span></span>
			<input
				type="text"
				data-testid="trip-wizard-step1-name"
				bind:value={wizard.name}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</label>

		<label class="flex flex-col gap-1 text-sm">
			<span>Region <span class="text-[var(--g-ink-muted)]">(optional)</span></span>
			<input
				type="text"
				data-testid="trip-wizard-step1-region"
				maxlength="50"
				placeholder="z.B. Korsika, Mallorca"
				bind:value={wizard.region}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</label>

		<label class="flex flex-col gap-1 text-sm">
			<span>Startdatum <span class="text-[var(--g-accent-deep)]">*</span></span>
			<input
				type="date"
				data-testid="trip-wizard-step1-startdate"
				bind:value={wizard.startDate}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
			<span class="text-xs text-[var(--g-ink-muted)]"
				>Das Enddatum wird in Schritt 2 aus den Etappen berechnet.</span
			>
		</label>
	</section>

	<!-- GPX-Upload (AC-3 #300: von Step 2 hierher verschoben) -->
	<section class="flex flex-col gap-3">
		<span class="text-xs uppercase tracking-wide text-[var(--g-ink-muted)]">GPX-Upload</span>

		<!-- Drop-Zone -->
		<div
			data-testid="trip-wizard-step1-gpx-drop"
			role="button"
			tabindex="0"
			aria-label="GPX-Dateien hierher ziehen oder klicken zum Auswählen"
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
			<UploadIcon class="mx-auto mb-2 size-8 text-[var(--g-ink-muted)]" />
			<p class="font-medium">GPX-Dateien hierher ziehen</p>
			<p class="text-sm text-[var(--g-ink-muted)] mt-1">oder klicken zum Auswählen</p>
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
				data-testid="trip-wizard-step1-gpx-pending"
				class="rounded-md border border-[var(--g-ink-faint)]/30 p-4 space-y-3 bg-[var(--g-ink-faint)]/5"
			>
				<p class="text-sm" data-testid="trip-wizard-step1-gpx-pending-count">
					{pendingFiles.length} Datei(en) ausgewählt
				</p>
				<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
					<label class="sm:w-32 text-sm" for="step1-bulk-stage-start-date">Startdatum</label>
					<input
						id="step1-bulk-stage-start-date"
						data-testid="trip-wizard-step1-gpx-bulk-startdate"
						type="date"
						bind:value={bulkStartDate}
						class="h-9 rounded border border-[var(--g-ink-faint)]/40 bg-transparent px-2 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
					/>
				</div>
				<div class="flex items-center gap-2">
					<button
						type="button"
						data-testid="trip-wizard-step1-gpx-commit"
						onclick={commitPending}
						disabled={uploading}
						class="rounded-md bg-[var(--g-accent)] px-3 py-2 text-sm text-white disabled:opacity-50"
					>
						{commitLabel}
					</button>
					<button
						type="button"
						data-testid="trip-wizard-step1-gpx-cancel"
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
			<p class="text-sm text-[var(--g-ink-muted)]">{uploadProgress}</p>
		{/if}

		{#if uploadError}
			<p class="text-sm text-[var(--g-danger)] whitespace-pre-line">{uploadError}</p>
		{/if}
	</section>
</div>
