// ================================================================
// Image compressor — Alpine component
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('compressImgTool', () => ({
        step: 'upload',
        format: 'jpeg',
        quality: 85,
        dragover: false,
        uploadProgress: 0,
        uploadPhase: 'uploading',
        uploadSpeedText: '—',
        uploadRemainingText: '—',
        originalPreviewUrl: '',
        originalBytes: 0,
        compressedBytes: 0,
        downloadExt: 'jpg',
        resultServerPath: null,
        shareLink: '',
        showShareRow: false,
        showOriginalColumn: true,
        resultCheckered: true,
        toastVisible: false,
        toastMessage: '',
        toastTimer: null,
        originalSizeText: '—',
        compressedSizeText: '—',
        savedPctText: '—',

        MAX_SIZE_MB: 20,
        ALLOWED_TYPES: ['image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'image/tiff'],

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
            if (!this.ALLOWED_TYPES.includes(file.type)) return `Unsupported type: ${file.type || 'unknown'}`;
            if (file.size > this.MAX_SIZE_MB * 1024 * 1024) return `File too large (max ${this.MAX_SIZE_MB} MB).`;
            return null;
        },

        formatBytes(n) {
            if (n < 1024) return `${n} B`;
            if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
            return `${(n / (1024 * 1024)).toFixed(2)} MB`;
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

        syncResultWrapperForFormat() {
            if (this.format === 'jpeg') {
                this.resultCheckered = false;
            } else {
                this.resultCheckered = true;
            }
        },

        goBackToUpload() {
            this.step = 'upload';
            this.showShareRow = false;
            this.showOriginalColumn = true;
        },

        handleBack() {
            this.goBackToUpload();
        },

        goToUpload() {
            if (this.originalPreviewUrl) {
                URL.revokeObjectURL(this.originalPreviewUrl);
                this.originalPreviewUrl = '';
            }
            this.step = 'upload';
            this.originalBytes = 0;
            this.compressedBytes = 0;
            this.resultServerPath = null;
            this.showShareRow = false;
            this.showOriginalColumn = true;
            this.resultCheckered = true;
            this.originalSizeText = '—';
            this.compressedSizeText = '—';
            this.savedPctText = '—';
            this.uploadSpeedText = '—';
            this.uploadRemainingText = '—';
        },

        goToResult(originalSrc, resultSrc, origSize, compSize, optionsFromLink) {
            if (this.originalPreviewUrl && this.originalPreviewUrl !== originalSrc) {
                URL.revokeObjectURL(this.originalPreviewUrl);
            }
            this.originalPreviewUrl = originalSrc || '';
            this.resultServerPath = resultSrc;
            this.originalBytes = origSize;
            this.compressedBytes = compSize;
            this.updateStats(origSize, compSize);
            this.showOriginalColumn = !optionsFromLink;
            this.syncResultWrapperForFormat();
            this.step = 'result';
        },

        async compressFile(file) {
            const err = this.validateFile(file);
            if (err) {
                this.showError(err);
                return;
            }
            const originalUrl = URL.createObjectURL(file);
            this.originalPreviewUrl = originalUrl;
            this.uploadProgress = 0;
            this.uploadPhase = 'uploading';
            this.uploadSpeedText = '—';
            this.uploadRemainingText = this.formatBytes(file.size || 0);
            this.step = 'processing';
            const uploadStartedAt = Date.now();
            const formData = new FormData();
            formData.append('image', file);
            formData.append('format', this.format);
            formData.append('quality', String(this.quality));
            if (this.format === 'jpeg') this.downloadExt = 'jpg';
            else if (this.format === 'webp') this.downloadExt = 'webp';
            else this.downloadExt = 'png';
            try {
                const data = await uploadXHR('/compress-img', formData, (pct, detail) => {
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
                this.resultServerPath = data.result_url;
                this.goToResult(originalUrl, this.resultServerPath, file.size, data.compressed_size, false);
            } catch (e) {
                this.showError(e.message || 'Something went wrong.');
                this.goToUpload();
                URL.revokeObjectURL(originalUrl);
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
            if (file) this.compressFile(file);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) this.compressFile(file);
        },

        downloadResult() {
            if (!this.resultServerPath) return;
            const a = document.createElement('a');
            a.href = this.resultServerPath;
            a.download = `compressed.${this.downloadExt}`;
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
