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
	import { Field } from '$lib/components/molecules';
	import { Btn } from '$lib/components/atoms';
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

		<Field label="TRIP-NAME">
			<input
				type="text"
				data-testid="trip-wizard-step1-name"
				bind:value={wizard.name}
				class="w-full h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</Field>

		<Field label="REGION" side="(optional)">
			<input
				type="text"
				data-testid="trip-wizard-step1-region"
				maxlength="50"
				placeholder="z.B. Korsika, Mallorca"
				bind:value={wizard.region}
				class="w-full h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</Field>

		<Field
			label="STARTDATUM"
			hint="Das Enddatum wird in Schritt 2 aus den Etappen berechnet."
		>
			<input
				type="date"
				data-testid="trip-wizard-step1-startdate"
				bind:value={wizard.startDate}
				class="w-full h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</Field>
	</section>

	<!-- GPX-Upload (AC-3 #300: von Step 2 hierher verschoben) -->
	<!-- Issue #584: Drop-Zone 1:1 nach JSX (dashed accent, accent-tint, WizUploadGlyph) -->
	<section class="flex flex-col gap-3">
		<span class="text-xs uppercase tracking-wide text-[var(--g-ink-muted)]">GPX-Upload</span>

		{#if wizard.stages.length > 0}
			<!-- GPX geladen: Card mit Badge + "Andere Datei wählen" (AC-4 #584) -->
			<div style="padding: 18px 22px; border-radius: var(--g-r-3);
			            background: var(--g-card); border: 1px solid var(--g-rule);
			            display: flex; align-items: center; gap: 14px;">
				<div style="width: 36px; height: 36px; border-radius: 8px; background: var(--g-accent-tint);
				            display: flex; align-items: center; justify-content: center;
				            color: var(--g-accent-deep); font-family: var(--g-font-mono); font-size: 11px; font-weight: 700;">
					GPX
				</div>
				<div style="flex: 1;">
					<div style="font-size: 14px; font-weight: 600;">{wizard.stages.length} Etappe(n) geladen</div>
					<div class="mono" style="font-size: 11px; color: var(--g-ink-3); margin-top: 2px;">
						{wizard.stages.length} Etappe(n) erkannt
					</div>
				</div>
				<Btn variant="ghost" size="sm" onclick={handleDropZoneClick}>Andere Datei wählen</Btn>
			</div>
		{:else}
			<!-- Drop-Zone (AC-3 #584): dashed accent border + accent-tint bg + WizUploadGlyph -->
			<div
				data-testid="trip-wizard-step1-gpx-drop"
				role="button"
				tabindex="0"
				aria-label="GPX-Dateien hierher ziehen oder klicken zum Auswählen"
				class="border-dashed"
				style="padding: 44px 24px; border-radius: var(--g-r-3);
				       border: 1.5px dashed var(--g-accent); background: var(--g-accent-tint);
				       text-align: center; cursor: pointer; transition: background 120ms;"
				ondrop={handleDrop}
				ondragover={handleDragOver}
				ondragleave={handleDragLeave}
				onclick={handleDropZoneClick}
				onkeydown={handleDropZoneKeydown}
			>
				<!-- WizUploadGlyph SVG: Pfeil nach oben + Tray, stroke accent-deep -->
				<svg width="36" height="36" viewBox="0 0 24 24" fill="none"
				     stroke="var(--g-accent-deep)" stroke-width="1.6"
				     stroke-linecap="round" stroke-linejoin="round"
				     style="margin: 0 auto;">
					<path d="M12 16V4M7 9l5-5 5 5"/>
					<path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
				</svg>
				<p style="font-size: 15px; font-weight: 600; color: var(--g-ink); margin-top: 12px;">
					GPX-Datei hierher ziehen
				</p>
				<p style="font-size: 13px; color: var(--g-ink-3); margin-top: 4px;">
					oder <span style="color: var(--g-accent-deep); text-decoration: underline;">aus Dateisystem wählen</span>
				</p>
				<div class="mono" style="font-size: 10px; color: var(--g-ink-4); margin-top: 10px; letter-spacing: 0.04em;">
					.GPX · Komoot · Outdooractive · Garmin · FootPath
				</div>
			</div>
		{/if}

		<input
			bind:this={fileInputEl}
			type="file"
			accept=".gpx"
			multiple
			class="hidden"
			onchange={handleFileInput}
		/>

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
