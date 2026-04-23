// ================================================================
// Image upscaler - Alpine component
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('upscaleImgTool', () => ({
        step: 'upload',
        mode: 'general',
        scale: 2,
        dragover: false,
        uploadProgress: 0,
        uploadPhase: 'uploading',
        uploadSpeedText: '—',
        uploadRemainingText: '—',
        originalPreviewUrl: '',
        resultServerPath: null,
        originalSizeText: '-',
        upscaledSizeText: '-',
        toastVisible: false,
        toastMessage: '',
        toastTimer: null,

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

        handleBack() {
            this.step = 'upload';
        },

        goToUpload() {
            if (this.originalPreviewUrl) {
                URL.revokeObjectURL(this.originalPreviewUrl);
                this.originalPreviewUrl = '';
            }
            this.step = 'upload';
            this.resultServerPath = null;
            this.originalSizeText = '-';
            this.upscaledSizeText = '-';
            this.uploadSpeedText = '—';
            this.uploadRemainingText = '—';
        },

        async upscaleFile(file) {
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
            formData.append('mode', this.mode);
            formData.append('scale', String(this.scale));
            try {
                const data = await uploadXHR('/upscale-img', formData, (pct, detail) => {
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
                this.originalSizeText = this.formatBytes(file.size);
                this.upscaledSizeText = this.formatBytes(data.compressed_size || 0);
                this.step = 'result';
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
            if (file) this.upscaleFile(file);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) this.upscaleFile(file);
        },

        downloadResult() {
            if (!this.resultServerPath) return;
            const a = document.createElement('a');
            a.href = this.resultServerPath;
            a.download = `upscaled_${this.scale}x.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },
    }));
});
