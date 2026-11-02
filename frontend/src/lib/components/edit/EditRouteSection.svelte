<script lang="ts">
	import type { Stage } from '$lib/types.js';
	import { uploadGpx } from '$lib/api.js';
	import { Btn, Input } from '$lib/components/atoms';
	import { Label } from '$lib/components/ui/label/index.js';
	import { naturalSort } from '$lib/utils/naturalSort.js';
	import UploadIcon from '@lucide/svelte/icons/upload';
	import { t, tn } from '$lib/i18n';

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
	// i18n F9: Fortschritt und Fehler als Daten, die Texte entstehen beim Rendern.
	let uploadProgress = $state<{ nr: number; gesamt: number } | null>(null);
	let fehlerOhneDatum = $state(false);
	let dateiFehler = $state<{ name: string; text: string | null }[]>([]);
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
		fehlerOhneDatum = false;
		dateiFehler = [];
		if (wasEmpty) {
			bulkStartDate = computeDefaultStartDate(stages);
		}
	}

	async function commitPending() {
		if (pendingFiles.length === 0) return;
		if (!bulkStartDate) {
			fehlerOhneDatum = true;
			return;
		}

		uploading = true;
		fehlerOhneDatum = false;
		dateiFehler = [];

		// Snapshot + clear buffer so the picker disappears immediately.
		const files = pendingFiles;
		const start = bulkStartDate;
		const total = files.length;
		pendingFiles = [];

		const uploaded: Stage[] = [];
		let uploadIndex = 0;
		for (let i = 0; i < files.length; i++) {
			const file = files[i];
			uploadProgress = { nr: i + 1, gesamt: total };
			const stageDate = addDays(start, uploadIndex);
			try {
				const stage = await uploadGpx(file, stageDate, 8);
				uploaded.push(stage);
				uploadIndex += 1;
			} catch (e) {
				dateiFehler = [...dateiFehler, { name: file.name, text: e instanceof Error ? e.message : null }];
			}
		}

		const sorted = naturalSort(uploaded, (s) => s.name);
		for (const stage of sorted) {
			stages.push(stage);
		}

		if (!tripName && sorted.length > 0) {
			tripName = sorted[0].name;
		}

		uploading = false;
		uploadProgress = null;
	}

	function cancelPending() {
		pendingFiles = [];
		fehlerOhneDatum = false;
		dateiFehler = [];
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
	let commitLabel = $derived($tn('trip.route.anlegen', pendingFiles.length));
</script>

<div class="space-y-6">
	<div>
		<Label for="wizard-trip-name">{$t('trip.route.trip_name')}</Label>
		<Input
			id="wizard-trip-name"
			data-testid="trip-name-input"
			placeholder={$t('trip.route.name_platzhalter')}
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
		<p class="font-medium">{$t('trip.route.ziehen')}</p>
		<p class="text-sm text-muted-foreground mt-1">{$t('trip.route.klicken')}</p>
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
				{$t('trip.route.ausgewaehlt', { anzahl: pendingFiles.length })}
			</p>
			<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
				<Label for="bulk-stage-start-date" class="sm:w-32">{$t('trip.startdatum')}</Label>
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
					{$t('aktionen.abbrechen')}
				</Btn>
			</div>
		</div>
	{/if}

	{#if uploading}
		<p class="text-sm text-muted-foreground">{uploadProgress ? $t('trip.route.lade_dateien', uploadProgress) : ''}</p>
	{/if}

	{#if fehlerOhneDatum || dateiFehler.length > 0}
		<p class="text-sm text-destructive whitespace-pre-line">{fehlerOhneDatum ? $t('trip.route.startdatum_waehlen') : dateiFehler.map((f) => `${f.name}: ${f.text ?? $t('trip.route.fehler')}\n`).join('')}</p>
	{/if}

	{#if stages.length > 0}
		<p class="text-sm text-muted-foreground">{$t('trip.route.geladen', { anzahl: stages.length })}</p>
	{/if}

	<div class="flex items-center gap-3">
		<span class="text-sm text-muted-foreground">{$t('trip.route.oder')}</span>
		<Btn variant="outline" onclick={addManualStage}>{$t('trip.route.manuell')}</Btn>
	</div>
</div>
