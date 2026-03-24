// ================================================================
// PDF compressor — Alpine component
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('compressPdfTool', () => ({
        step: 'upload',
        mode: 'auto',
        quality: 85,
        dragover: false,
        originalBytes: 0,
        compressedBytes: 0,
        resultServerPath: null,
        lastPdfMode: 'auto',
        lastKeptOriginal: false,
        shareLink: '',
        showShareRow: false,
        showOpenTab: false,
        toastVisible: false,
        toastMessage: '',
        toastTimer: null,
        originalSizeText: '—',
        compressedSizeText: '—',
        savedPctText: '—',
        modeLineText: '',

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

        modeLabel(mode, keptOriginal) {
            let base;
            if (mode === 'text') {
                base = 'Used: text / vectors — Flate level 9, stream recompression, object streams (no linearization overhead); XMP stripped when present.';
            } else if (mode === 'image') {
                base = 'Used: images — embedded rasters recompressed as JPEG, then deflate recompression (no linearization overhead).';
            } else if (mode === 'bitmap') {
                base = 'Used: bitmap — each page rasterized to JPEG (PDFium + img2pdf). Text is not selectable; smallest files when combined with lower quality/DPI.';
            } else {
                base = `Used: ${mode || 'unknown'}`;
            }
            if (keptOriginal) {
                return `${base} Output matches upload size — file was already tight; nothing smaller without quality loss.`;
            }
            return base;
        },

        updateStats(orig, comp) {
            this.originalSizeText = orig > 0 ? this.formatBytes(orig) : '—';
            this.compressedSizeText = comp > 0 ? this.formatBytes(comp) : '—';
            if (orig > 0) {
                const saved = Math.max(0, orig - comp);
                const pct = (saved / orig) * 100;
                this.savedPctText = `${pct.toFixed(1)}% (${this.formatBytes(saved)})`;
            } else {
                this.savedPctText = '—';
            }
        },

        goBackToUpload() {
            this.step = 'upload';
            this.showShareRow = false;
            this.showOpenTab = false;
        },

        handleBack() {
            this.goBackToUpload();
        },

        goToUpload() {
            this.step = 'upload';
            this.originalBytes = 0;
            this.compressedBytes = 0;
            this.resultServerPath = null;
            this.modeLineText = '';
            this.showShareRow = false;
            this.showOpenTab = false;
            this.originalSizeText = '—';
            this.compressedSizeText = '—';
            this.savedPctText = '—';
        },

        goToResult(origSize, compSize, effectiveMode, keptOriginal) {
            this.lastPdfMode = effectiveMode;
            this.lastKeptOriginal = keptOriginal;
            this.originalBytes = origSize;
            this.compressedBytes = compSize;
            this.updateStats(origSize, compSize);
            this.modeLineText = this.modeLabel(effectiveMode, keptOriginal);
            this.step = 'result';
        },

        async compressPdf(file) {
            const err = this.validateFile(file);
            if (err) {
                this.showError(err);
                return;
            }
            this.step = 'processing';
            const formData = new FormData();
            formData.append('pdf', file);
            formData.append('quality', String(this.quality));
            formData.append('mode', this.mode);
            if (this.mode === 'bitmap') {
                const dpi = this.$refs.bitmapDpi;
                if (dpi) formData.append('bitmap_dpi', dpi.value);
            }
            try {
                const res = await fetch('/compress-pdf', { method: 'POST', body: formData });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.error || `Server error (${res.status})`);
                }
                const data = await res.json();
                this.resultServerPath = data.result_url;
                this.showOpenTab = true;
                this.goToResult(file.size, data.compressed_size, data.pdf_mode, data.kept_original);
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
            if (file) this.compressPdf(file);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) this.compressPdf(file);
        },

        downloadResult() {
            if (!this.resultServerPath) return;
            const a = document.createElement('a');
            a.href = this.resultServerPath;
            a.download = 'compressed.pdf';
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
