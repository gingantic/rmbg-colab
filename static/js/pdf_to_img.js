// ================================================================
// PDF to images (ZIP) — Alpine component
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('pdfToImgTool', () => ({
        step: 'upload',
        format: 'png',
        quality: 85,
        dragover: false,
        originalBytes: 0,
        outputBytes: 0,
        resultServerPath: null,
        shareLink: '',
        showShareRow: false,
        toastVisible: false,
        toastMessage: '',
        toastTimer: null,
        originalSizeText: '—',
        outputSizeText: '—',
        deltaPctText: '—',

        MAX_SIZE_MB: 20,
        PDF_TYPE: 'application/pdf',

        showError(msg) {
            this.toastMessage = msg;
            this.toastVisible = true;
            clearTimeout(this.toastTimer);
            this.$nextTick(() => {
                const el = this.$refs.errorToast;
                if (el) void el.offsetWidth;
            });
            this.toastTimer = setTimeout(() => { this.toastVisible = false; }, 4000);
        },

        validateFile(file) {
            if (!file) return 'No file selected.';
            const okType = file.type === this.PDF_TYPE || /\.pdf$/i.test(file.name);
            if (!okType) return 'Please choose a PDF file.';
            if (file.size > this.MAX_SIZE_MB * 1024 * 1024) return `File too large (max ${this.MAX_SIZE_MB} MB).`;
            return null;
        },

        formatBytes(n) {
            if (n < 1024) return `${n} B`;
            if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
            return `${(n / (1024 * 1024)).toFixed(2)} MB`;
        },

        updateStats(orig, out) {
            this.originalSizeText = orig > 0 ? this.formatBytes(orig) : '—';
            this.outputSizeText = out > 0 ? this.formatBytes(out) : '—';
            if (orig > 0) {
                const pct = ((out - orig) / orig) * 100;
                const delta = out - orig;
                const sign = delta > 0 ? '+' : '';
                this.deltaPctText = `${sign}${pct.toFixed(1)}% (${sign}${this.formatBytes(Math.abs(delta))})`;
            } else {
                this.deltaPctText = '—';
            }
        },

        goBackToUpload() {
            this.step = 'upload';
            this.showShareRow = false;
        },

        handleBack() {
            this.goBackToUpload();
        },

        goToUpload() {
            this.step = 'upload';
            this.originalBytes = 0;
            this.outputBytes = 0;
            this.resultServerPath = null;
            this.showShareRow = false;
            this.originalSizeText = '—';
            this.outputSizeText = '—';
            this.deltaPctText = '—';
        },

        goToResult(origSize, outSize) {
            this.originalBytes = origSize;
            this.outputBytes = outSize;
            this.updateStats(origSize, outSize);
            this.step = 'result';
        },

        async runExport(file) {
            const err = this.validateFile(file);
            if (err) {
                this.showError(err);
                return;
            }
            this.step = 'processing';
            const formData = new FormData();
            formData.append('pdf', file);
            formData.append('format', this.format);
            formData.append('quality', String(this.quality));
            const dpiEl = this.$refs.dpiSelect;
            formData.append('dpi', dpiEl ? dpiEl.value : '150');
            try {
                const res = await fetch('/pdf-to-img', { method: 'POST', body: formData });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.error || `Server error (${res.status})`);
                }
                const data = await res.json();
                this.resultServerPath = data.result_url;
                this.goToResult(file.size, data.compressed_size);
            } catch (e) {
                this.showError(e.message || 'Something went wrong.');
                this.goToUpload();
            }
        },

        init() {
            history.replaceState({ step: 'upload' }, '', window.location.pathname);
        },

        pickFile() {
            this.$refs.fileInput.click();
        },

        onFileChange() {
            const input = this.$refs.fileInput;
            const file = input.files[0];
            if (file) this.runExport(file);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) this.runExport(file);
        },

        downloadResult() {
            if (!this.resultServerPath) return;
            const a = document.createElement('a');
            a.href = this.resultServerPath;
            a.download = 'pages.zip';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },

        async copyShareLink() {
            const text = this.shareLink;
            if (!text) return;
            const btn = this.$refs.copyBtn;
            try {
                await navigator.clipboard.writeText(text);
                if (btn) {
                    btn.textContent = 'Copied';
                    setTimeout(() => { btn.textContent = 'Copy link'; }, 2000);
                }
            } catch {
                const inp = this.$refs.shareInput;
                if (inp) {
                    inp.select();
                    document.execCommand('copy');
                }
            }
        },
    }));
});
