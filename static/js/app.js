// ================================================================
// RMBG 2.0 — Alpine component (registered on alpine:init)
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('rmbgTool', () => ({
        step: 'upload',
        dragover: false,
        originalPreviewUrl: '',
        resultBlobUrl: null,
        activeBgColor: null,
        toastVisible: false,
        toastMessage: '',
        toastHideTimer: null,

        MAX_SIZE_MB: 20,
        ALLOWED_TYPES: ['image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'image/tiff'],

        showError(msg) {
            this.toastMessage = msg;
            this.toastVisible = true;
            clearTimeout(this.toastHideTimer);
            this.$nextTick(() => {
                const el = this.$refs.errorToast;
                if (el) void el.offsetWidth;
            });
            this.toastHideTimer = setTimeout(() => {
                this.toastVisible = false;
            }, 4000);
        },

        validateFile(file) {
            if (!file) return 'No file selected.';
            if (!this.ALLOWED_TYPES.includes(file.type)) return `Unsupported type: ${file.type || 'unknown'}`;
            if (file.size > this.MAX_SIZE_MB * 1024 * 1024) return `File too large (max ${this.MAX_SIZE_MB} MB).`;
            return null;
        },

        goToUpload() {
            if (this.resultBlobUrl) {
                URL.revokeObjectURL(this.resultBlobUrl);
                this.resultBlobUrl = null;
            }
            if (this.originalPreviewUrl) {
                URL.revokeObjectURL(this.originalPreviewUrl);
                this.originalPreviewUrl = '';
            }
            this.step = 'upload';
            this.activeBgColor = null;
            this.$nextTick(() => this.resetResultBackground());
        },

        resetResultBackground() {
            const w = this.$refs.resultWrapper;
            const picker = this.$refs.bgColorPicker;
            const hex = this.$refs.bgHexInput;
            if (w) {
                w.classList.add('checkered-bg');
                w.style.background = '';
            }
            if (picker) picker.value = '#ffffff';
            if (hex) hex.value = '';
        },

        applyResultBackground(color) {
            const w = this.$refs.resultWrapper;
            if (!w) return;
            if (!color) {
                this.resetResultBackground();
                return;
            }
            w.classList.remove('checkered-bg');
            w.style.background = color;
        },

        onBgColorInput() {
            const picker = this.$refs.bgColorPicker;
            const hexIn = this.$refs.bgHexInput;
            if (!picker) return;
            this.activeBgColor = picker.value;
            this.applyResultBackground(this.activeBgColor);
            if (hexIn) hexIn.value = this.activeBgColor.replace('#', '').toLowerCase();
        },

        onBgHexInput() {
            const hexIn = this.$refs.bgHexInput;
            const picker = this.$refs.bgColorPicker;
            if (!hexIn) return;
            const raw = hexIn.value.replace(/[^0-9a-fA-F]/g, '').slice(0, 6);
            if (raw !== hexIn.value) hexIn.value = raw;
            const hexRegex = /^[0-9a-fA-F]{6}$/;
            if (hexRegex.test(raw)) {
                const normalized = `#${raw.toLowerCase()}`;
                this.activeBgColor = normalized;
                this.applyResultBackground(normalized);
                if (picker) picker.value = normalized;
            }
        },

        onBgHexBlur() {
            const hexIn = this.$refs.bgHexInput;
            if (!hexIn) return;
            const hexRegex = /^[0-9a-fA-F]{6}$/;
            const value = hexIn.value.trim();
            if (!hexRegex.test(value)) {
                if (this.activeBgColor) {
                    hexIn.value = this.activeBgColor.replace('#', '').toLowerCase();
                } else {
                    hexIn.value = '';
                }
            }
        },

        async processImage(file) {
            const err = this.validateFile(file);
            if (err) {
                this.showError(err);
                return;
            }
            const originalUrl = URL.createObjectURL(file);
            this.originalPreviewUrl = originalUrl;
            this.step = 'processing';
            const formData = new FormData();
            formData.append('image', file);
            try {
                const res = await fetch('/remove-bg', { method: 'POST', body: formData });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.error || `Server error (${res.status})`);
                }
                const blob = await res.blob();
                this.resultBlobUrl = URL.createObjectURL(blob);
                this.step = 'result';
            } catch (e) {
                this.showError(e.message || 'Something went wrong.');
                this.goToUpload();
            }
        },

        pickFile() {
            this.$refs.fileInput.click();
        },

        onFileChange() {
            const input = this.$refs.fileInput;
            const file = input.files[0];
            if (file) this.processImage(file);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            e.stopPropagation();
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) this.processImage(file);
        },

        downloadPng() {
            if (!this.resultBlobUrl) return;
            const a = document.createElement('a');
            a.href = this.resultBlobUrl;
            a.download = 'rmbg_result.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },

        async downloadColored() {
            if (!this.resultBlobUrl) return;
            const bgColor = this.activeBgColor || '#ffffff';
            try {
                const img = new Image();
                img.crossOrigin = 'anonymous';
                img.src = this.resultBlobUrl;
                await new Promise((resolve, reject) => {
                    img.onload = () => resolve();
                    img.onerror = () => reject(new Error('Failed to load processed image.'));
                });
                const canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth || img.width;
                canvas.height = img.naturalHeight || img.height;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = bgColor;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                canvas.toBlob((blob) => {
                    if (!blob) return;
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'rmbg_result_colored.png';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }, 'image/png');
            } catch (e) {
                this.showError(e.message || 'Failed to generate background image.');
            }
        },
    }));
});
