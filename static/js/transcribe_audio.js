// ================================================================
// Audio transcription + diarization — Alpine component
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('transcribeAudioTool', () => ({
        step: 'upload',
        dragover: false,
        format: 'json',
        uploadProgress: 0,
        uploadPhase: 'uploading',
        uploadSpeedText: '—',
        uploadRemainingText: '—',
        processingMessage: 'Submitting background transcription job...',
        toastVisible: false,
        toastMessage: '',
        toastTimer: null,
        jobId: '',
        statusStream: null,
        reconnectTimer: null,
        resultToken: '',
        downloadUrl: '',
        outputFilename: '',
        originalSizeText: '—',
        transcriptText: '',
        jsonBlobUrl: '',

        formatBytes(n) {
            if (n < 1024) return `${n} B`;
            if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
            return `${(n / (1024 * 1024)).toFixed(2)} MB`;
        },

        showError(msg) {
            this.toastMessage = msg;
            this.toastVisible = true;
            clearTimeout(this.toastTimer);
            this.$nextTick(() => {
                const el = this.$refs.errorToast;
                if (el) void el.offsetWidth;
            });
            this.toastTimer = setTimeout(() => { this.toastVisible = false; }, 200000);
        },

        closeToast() {
            clearTimeout(this.toastTimer);
            this.toastVisible = false;
        },

        clearStatusConnection() {
            if (this.statusStream) {
                this.statusStream.close();
                this.statusStream = null;
            }
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
        },

        clearResultData() {
            this.downloadUrl = '';
            this.resultToken = '';
            this.outputFilename = '';
            this.transcriptText = '';
            if (this.jsonBlobUrl) {
                URL.revokeObjectURL(this.jsonBlobUrl);
                this.jsonBlobUrl = '';
            }
        },

        goToUpload() {
            this.clearStatusConnection();
            this.clearResultData();
            this.jobId = '';
            this.step = 'upload';
            this.uploadProgress = 0;
            this.uploadPhase = 'uploading';
            this.uploadSpeedText = '—';
            this.uploadRemainingText = '—';
            this.processingMessage = 'Submitting background transcription job...';
        },

        pickFile() {
            this.$refs.fileInput.click();
        },

        onFileChange() {
            const input = this.$refs.fileInput;
            const file = input.files && input.files[0];
            if (file) this.submitJob(file);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            const file = e.dataTransfer.files && e.dataTransfer.files[0];
            if (file) this.submitJob(file);
        },

        async submitJob(file) {
            this.clearStatusConnection();
            this.clearResultData();
            this.uploadProgress = 0;
            this.uploadPhase = 'uploading';
            this.uploadSpeedText = '—';
            this.uploadRemainingText = this.formatBytes(file.size || 0);
            this.step = 'processing';
            this.originalSizeText = this.formatBytes(file.size || 0);
            this.processingMessage = 'Submitting background transcription job...';
            try {
                const uploadStartedAt = Date.now();
                const formData = new FormData();
                formData.append('audio', file);
                formData.append('format', this.format);
                const data = await uploadXHR('/transcribe-audio/async', formData, (pct, detail) => {
                    this.uploadProgress = pct;
                    if (detail && detail.lengthComputable) {
                        const elapsedSeconds = Math.max((Date.now() - uploadStartedAt) / 1000, 0.001);
                        const bytesPerSecond = detail.loaded / elapsedSeconds;
                        const remainingBytes = Math.max(detail.total - detail.loaded, 0);
                        this.uploadSpeedText = `${this.formatBytes(Math.max(Math.round(bytesPerSecond), 0))}/s`;
                        this.uploadRemainingText = this.formatBytes(remainingBytes);
                    }
                    if (pct >= 100) this.uploadPhase = 'processing';
                });
                this.jobId = data.job_id || '';
                if (!this.jobId) throw new Error('No job ID returned by server.');
                this.processingMessage = 'Job submitted. Waiting for transcription result...';
                this.startStatusStream();
            } catch (e) {
                this.showError(e.message || 'Failed to submit transcription job.');
                this.goToUpload();
            }
        },

        startStatusStream() {
            if (!this.jobId) return;
            this.clearStatusConnection();
            const streamUrl = `/transcribe-audio/jobs/${encodeURIComponent(this.jobId)}/stream`;
            const stream = new EventSource(streamUrl);
            this.statusStream = stream;

            stream.onmessage = (event) => {
                if (!event.data) return;
                try {
                    const data = JSON.parse(event.data);
                    this.applyJobStatus(data);
                } catch (_) {
                    // Ignore malformed stream frames and wait for next update.
                }
            };

            stream.onerror = async () => {
                if (this.statusStream !== stream) return;
                stream.close();
                this.statusStream = null;
                if (this.step !== 'processing') return;
                this.processingMessage = 'Connection interrupted. Reconnecting...';
                try {
                    await this.pollJobOnce();
                } catch (e) {
                    this.showError(e.message || 'Failed to reconnect to job status stream.');
                    this.goToUpload();
                    return;
                }
                if (this.step === 'processing') {
                    this.reconnectTimer = setTimeout(() => this.startStatusStream(), 2000);
                }
            };
        },

        async pollJobOnce() {
            if (!this.jobId) return;
            try {
                const res = await fetch(`/transcribe-audio/jobs/${this.jobId}`, { method: 'GET' });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.error || `Status error (${res.status})`);
                }
                const data = await res.json();
                this.applyJobStatus(data);
            } catch (e) {
                throw new Error(e.message || 'Failed to fetch job status.');
            }
        },

        applyJobStatus(data) {
            const status = data.status;
            if (status === 'queued') {
                this.processingMessage = 'Job queued...';
                return;
            }
            if (status === 'running') {
                this.processingMessage = 'Transcribing and diarizing audio...';
                return;
            }
            if (status === 'failed') {
                this.clearStatusConnection();
                this.showError(data.error || 'Transcription job failed.');
                this.goToUpload();
                return;
            }
            if (status === 'succeeded') {
                this.handleSuccess(data.result || {});
            }
        },

        handleSuccess(result) {
            this.clearStatusConnection();
            if (result.output_format === 'json' && result.payload) {
                const payload = result.payload;
                const segments = Array.isArray(payload.segments) ? payload.segments : [];
                this.transcriptText = segments.map((s) => {
                    const spk = s.speaker ? `[${s.speaker}] ` : '';
                    return `${spk}${s.text || ''}`.trim();
                }).join('\n');
                const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
                this.jsonBlobUrl = URL.createObjectURL(blob);
                this.outputFilename = 'transcript.json';
            } else {
                this.downloadUrl = result.result_url || '';
                this.resultToken = result.token || '';
                this.outputFilename = result.filename || `transcript.${this.format}`;
            }
            this.step = 'result';
        },

        downloadResult() {
            let href = this.downloadUrl;
            if (!href && this.jsonBlobUrl) {
                href = this.jsonBlobUrl;
            }
            if (!href) return;
            const a = document.createElement('a');
            a.href = href;
            a.download = this.outputFilename || `transcript.${this.format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },

        init() {
            history.replaceState({ step: 'upload' }, '', window.location.pathname);
        },
    }));
});

