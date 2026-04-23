// ================================================================
// Image converter — Alpine component
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('convertImgTool', () => ({
        step: 'upload',
        format: 'png',
        quality: 85,
        scalePercent: 100,
        dragover: false,
        uploadProgress: 0,
        uploadPhase: 'uploading',
        uploadSpeedText: '—',
        uploadRemainingText: '—',
        originalPreviewUrl: '',
        originalBytes: 0,
        convertedBytes: 0,
        downloadExt: 'png',
        resultServerPath: null,
        shareLink: '',
        showShareRow: false,
        showOriginalColumn: true,
        resultCheckered: true,
        toastVisible: false,
        toastMessage: '',
        toastTimer: null,
        originalSizeText: '—',
        convertedSizeText: '—',
        deltaPctText: '—',

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

        updateStats(orig, converted) {
            this.originalSizeText = orig > 0 ? this.formatBytes(orig) : '—';
            this.convertedSizeText = converted > 0 ? this.formatBytes(converted) : '—';
            if (orig > 0) {
                const pct = ((converted - orig) / orig) * 100;
                const delta = converted - orig;
                const sign = delta > 0 ? '+' : '';
                this.deltaPctText = `${sign}${pct.toFixed(1)}% (${sign}${this.formatBytes(Math.abs(delta))})`;
            } else {
                this.deltaPctText = '—';
            }
        },

        syncResultWrapperForFormat() {
            this.resultCheckered = this.format !== 'jpeg' && this.format !== 'bmp';
        },

        goBackToUpload() {
            if (this.originalPreviewUrl) {
                URL.revokeObjectURL(this.originalPreviewUrl);
                this.originalPreviewUrl = '';
            }
            this.step = 'upload';
            this.showShareRow = false;
            this.resultServerPath = null;
            this.originalBytes = 0;
            this.convertedBytes = 0;
            this.originalSizeText = '—';
            this.convertedSizeText = '—';
            this.deltaPctText = '—';
            this.scalePercent = 100;
            this.showOriginalColumn = true;
            this.resultCheckered = true;
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
            this.convertedBytes = 0;
            this.resultServerPath = null;
            this.showShareRow = false;
            this.showOriginalColumn = true;
            this.resultCheckered = true;
            this.originalSizeText = '—';
            this.convertedSizeText = '—';
            this.deltaPctText = '—';
            this.scalePercent = 100;
            this.uploadSpeedText = '—';
            this.uploadRemainingText = '—';
        },

        goToResult(originalSrc, resultSrc, origSize, outSize, optionsFromLink) {
            if (this.originalPreviewUrl && this.originalPreviewUrl !== originalSrc) {
                URL.revokeObjectURL(this.originalPreviewUrl);
            }
            this.originalPreviewUrl = originalSrc || '';
            this.resultServerPath = resultSrc;
            this.originalBytes = origSize;
            this.convertedBytes = outSize;
            this.updateStats(origSize, outSize);
            this.showOriginalColumn = !optionsFromLink;
            this.syncResultWrapperForFormat();
            this.step = 'result';
        },

        async convertFile(file) {
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
            formData.append('scale_percent', String(this.scalePercent));
            if (this.format === 'jpeg') this.downloadExt = 'jpg';
            else this.downloadExt = this.format;
            try {
                const data = await uploadXHR('/convert-img', formData, (pct, detail) => {
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
            if (file) this.convertFile(file);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) this.convertFile(file);
        },

        downloadResult() {
            if (!this.resultServerPath) return;
            const a = document.createElement('a');
            a.href = this.resultServerPath;
            a.download = `converted.${this.downloadExt}`;
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
