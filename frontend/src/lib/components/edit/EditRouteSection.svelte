<script lang="ts">
	import type { Stage } from '$lib/types.js';
	import { uploadGpx } from '$lib/api.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { naturalSort } from '$lib/utils/naturalSort.js';
	import UploadIcon from '@lucide/svelte/icons/upload';

	interface Props {
		tripName: string;
		stages: Stage[];
		mode: 'create' | 'edit';
	}
	let { tripName = $bindable(), stages = $bindable(), mode }: Props = $props();

	const newId = (): string => crypto.randomUUID().slice(0, 8);
	const today = (): string => new Date().toISOString().slice(0, 10);

	function addDays(iso: string, days: number): string {
		const d = new Date(iso + 'T00:00:00Z');
		d.setUTCDate(d.getUTCDate() + days);
		return d.toISOString().slice(0, 10);
	}

	function computeDefaultStartDate(stages: Stage[]): string {
		if (stages.length === 0) return today();
		const last = stages[stages.length - 1];
		if (!last?.date) return today();
		return addDays(last.date, 1);
	}

	let uploading = $state(false);
	let uploadProgress = $state('');
	let uploadError = $state('');
	let dragOver = $state(false);

	// Buffer-State: GPX-Files warten bis User Startdatum bestaetigt.
	let pendingFiles = $state<File[]>([]);
	let bulkStartDate = $state(today());

	function handleFiles(files: FileList | File[]) {
		const fileArray = Array.from(files).filter(f => f.name.endsWith('.gpx'));
		if (fileArray.length === 0) return;

		// Append to buffer (multiple drops accumulate). Recompute default date
		// only when the buffer becomes non-empty for the first time.
		const wasEmpty = pendingFiles.length === 0;
		pendingFiles = [...pendingFiles, ...fileArray];
		uploadError = '';
		if (wasEmpty) {
			bulkStartDate = computeDefaultStartDate(stages);
		}
	}

	async function commitPending() {
		if (pendingFiles.length === 0) return;
		if (!bulkStartDate) {
			uploadError = 'Bitte Startdatum waehlen.\n';
			return;
		}

		uploading = true;
		uploadError = '';

		// Snapshot + clear buffer so the picker disappears immediately.
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
				stages.push(stage);
				added += 1;
			} catch (e) {
				uploadError += `${file.name}: ${e instanceof Error ? e.message : 'Fehler'}\n`;
			}
		}

		if (!tripName && stages.length > 0) {
			tripName = sorted[0].name.replace(/\.gpx$/i, '');
		}

		uploading = false;
		uploadProgress = '';
	}

	function cancelPending() {
		pendingFiles = [];
		uploadError = '';
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		if (e.dataTransfer?.files) {
			handleFiles(e.dataTransfer.files);
		}
	}

	function onDragOver(e: DragEvent) {
		e.preventDefault();
		dragOver = true;
	}

	function onDragLeave() {
		dragOver = false;
	}

	function onFileInput(e: Event) {
		const input = e.target as HTMLInputElement;
		if (input.files) {
			handleFiles(input.files);
			input.value = ''; // allow re-selecting same files
		}
	}

	function addManualStage() {
		stages.push({
			id: newId(),
			name: `Etappe ${stages.length + 1}`,
			date: today(),
			waypoints: []
		});
	}

	let fileInput: HTMLInputElement;
	let commitLabel = $derived(
		pendingFiles.length === 1
			? '1 Etappe anlegen'
			: `${pendingFiles.length} Etappen anlegen`
	);
</script>

<div class="space-y-6">
	<div>
		<Label for="wizard-trip-name">Trip Name</Label>
		<Input
			id="wizard-trip-name"
			data-testid="trip-name-input"
			placeholder="Name des Trips"
			bind:value={tripName}
		/>
	</div>

	<div
		data-testid="gpx-drop-zone"
		role="button"
		tabindex="0"
		class="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
			{dragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/30 hover:border-primary/50'}"
		ondrop={onDrop}
		ondragover={onDragOver}
		ondragleave={onDragLeave}
		onclick={() => fileInput.click()}
		onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); }}
	>
		<UploadIcon class="mx-auto mb-2 size-8 text-muted-foreground" />
		<p class="font-medium">GPX-Dateien hierher ziehen</p>
		<p class="text-sm text-muted-foreground mt-1">oder klicken zum Auswaehlen</p>
		<input
			bind:this={fileInput}
			type="file"
			accept=".gpx"
			multiple
			class="hidden"
			onchange={onFileInput}
		/>
	</div>

	{#if pendingFiles.length > 0}
		<div class="rounded-md border p-4 space-y-3 bg-muted/30">
			<p class="text-sm" data-testid="bulk-stage-pending-count">
				{pendingFiles.length} Datei(en) ausgewaehlt
			</p>
			<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
				<Label for="bulk-stage-start-date" class="sm:w-32">Startdatum</Label>
				<Input
					id="bulk-stage-start-date"
					data-testid="bulk-stage-start-date"
					type="date"
					bind:value={bulkStartDate}
					class="sm:w-44"
				/>
			</div>
			<div class="flex items-center gap-2">
				<Btn
					data-testid="bulk-stage-commit"
					onclick={commitPending}
					disabled={uploading}
				>
					{commitLabel}
				</Btn>
				<Btn
					variant="outline"
					data-testid="bulk-stage-cancel"
					onclick={cancelPending}
					disabled={uploading}
				>
					Abbrechen
				</Btn>
			</div>
		</div>
	{/if}

	{#if uploading}
		<p class="text-sm text-muted-foreground">{uploadProgress}</p>
	{/if}

	{#if uploadError}
		<p class="text-sm text-destructive whitespace-pre-line">{uploadError}</p>
	{/if}

	{#if stages.length > 0}
		<p class="text-sm text-muted-foreground">{stages.length} Etappe(n) geladen</p>
	{/if}

	<div class="flex items-center gap-3">
		<span class="text-sm text-muted-foreground">oder</span>
		<Btn variant="outline" onclick={addManualStage}>Manuell anlegen</Btn>
	</div>
</div>
