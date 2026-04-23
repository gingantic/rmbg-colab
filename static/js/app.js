// ================================================================
// RMBG 2.0 — Alpine component (registered on alpine:init)
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('rmbgTool', () => ({
        step: 'upload',
        dragover: false,
        isBatchMode: false,
        batchCount: 0,
        batchFileNames: [],
        batchOriginalSizeText: '—',
        batchOutputSizeText: '—',
        batchZipUrl: null,
        batchZipFilename: 'rmbg_batch.zip',
        originalPreviewUrl: '',
        resultBlobUrl: null,
        activeBgColor: null,
        uploadProgress: 0,
        uploadPhase: 'uploading',
        uploadSpeedText: '—',
        uploadRemainingText: '—',
        toastVisible: false,
        toastMessage: '',
        toastHideTimer: null,

        MAX_SIZE_MB: 20,
        ALLOWED_TYPES: ['image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'image/tiff'],

        formatBytes(n) {
            if (n < 1024) return `${n} B`;
            if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
            return `${(n / (1024 * 1024)).toFixed(2)} MB`;
        },

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

        isAllowedType(file) {
            if (this.ALLOWED_TYPES.includes(file.type)) return true;
            return /\.(png|jpe?g|webp|bmp|tiff?)$/i.test(file.name || '');
        },

        validateFile(file) {
            if (!file) return 'No file selected.';
            if (!this.isAllowedType(file)) return `Unsupported type: ${file.type || file.name || 'unknown'}`;
            if (file.size > this.MAX_SIZE_MB * 1024 * 1024) return `File too large (max ${this.MAX_SIZE_MB} MB).`;
            return null;
        },

        resetBatchState() {
            this.isBatchMode = false;
            this.batchCount = 0;
            this.batchFileNames = [];
            this.batchOriginalSizeText = '—';
            this.batchOutputSizeText = '—';
            this.batchZipUrl = null;
            this.batchZipFilename = 'rmbg_batch.zip';
        },

        clearResultUrls() {
            if (this.resultBlobUrl) {
                URL.revokeObjectURL(this.resultBlobUrl);
                this.resultBlobUrl = null;
            }
            if (this.originalPreviewUrl) {
                URL.revokeObjectURL(this.originalPreviewUrl);
                this.originalPreviewUrl = '';
            }
        },

        goToUpload() {
            this.clearResultUrls();
            this.resetBatchState();
            this.step = 'upload';
            this.activeBgColor = null;
            this.uploadSpeedText = '—';
            this.uploadRemainingText = '—';
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

        async processSelection(files) {
            const pickedFiles = Array.from(files || []);
            if (!pickedFiles.length) return;

            for (const file of pickedFiles) {
                const err = this.validateFile(file);
                if (err) {
                    this.showError(`${file.name}: ${err}`);
                    return;
                }
            }

            this.clearResultUrls();
            this.resetBatchState();
            this.uploadProgress = 0;
            this.uploadPhase = 'uploading';
            this.step = 'processing';
            const totalInputBytes = pickedFiles.reduce((sum, file) => sum + file.size, 0);
            this.uploadSpeedText = '—';
            this.uploadRemainingText = this.formatBytes(totalInputBytes);
            const uploadStartedAt = Date.now();

            if (pickedFiles.length === 1) {
                const file = pickedFiles[0];
                const originalUrl = URL.createObjectURL(file);
                this.originalPreviewUrl = originalUrl;
                try {
                    const formData = new FormData();
                    formData.append('image', file);
                    const xhr = new XMLHttpRequest();
                    const blobData = await new Promise((resolve, reject) => {
                        xhr.open('POST', '/remove-bg');
                        xhr.responseType = 'blob';
                        xhr.upload.addEventListener('progress', (e) => {
                            if (e.lengthComputable) {
                                this.uploadProgress = Math.round((e.loaded / e.total) * 100);
                                const elapsedSeconds = Math.max((Date.now() - uploadStartedAt) / 1000, 0.001);
                                const bytesPerSecond = e.loaded / elapsedSeconds;
                                const remainingBytes = Math.max(e.total - e.loaded, 0);
                                this.uploadSpeedText = `${this.formatBytes(Math.max(Math.round(bytesPerSecond), 0))}/s`;
                                this.uploadRemainingText = this.formatBytes(remainingBytes);
                                if (this.uploadProgress >= 100) this.uploadPhase = 'processing';
                            }
                        });
                        xhr.addEventListener('load', () => {
                            if (xhr.status >= 200 && xhr.status < 300) {
                                resolve(xhr.response);
                            } else {
                                const reader = new FileReader();
                                reader.onload = () => {
                                    try {
                                        const d = JSON.parse(reader.result);
                                        reject(new Error(d.error || `Server error (${xhr.status})`));
                                    } catch {
                                        reject(new Error(`Server error (${xhr.status})`));
                                    }
                                };
                                reader.readAsText(xhr.response);
                            }
                        });
                        xhr.addEventListener('error', () => reject(new Error('Network error — check your connection.')));
                        xhr.send(formData);
                    });
                    this.resultBlobUrl = URL.createObjectURL(blobData);
                    this.isBatchMode = false;
                    this.step = 'result';
                    this.$nextTick(() => this.resetResultBackground());
                } catch (e) {
                    this.showError(e.message || 'Something went wrong.');
                    this.goToUpload();
                }
                return;
            }

            this.isBatchMode = true;
            this.batchCount = pickedFiles.length;
            this.batchFileNames = pickedFiles.map((file) => file.name);
            this.batchOriginalSizeText = this.formatBytes(totalInputBytes);

            try {
                const formData = new FormData();
                pickedFiles.forEach((file) => formData.append('images', file));
                const data = await uploadXHR('/remove-bg', formData, (pct, detail) => {
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
                this.batchZipUrl = data.result_url || null;
                this.batchZipFilename = data.filename || 'rmbg_batch.zip';
                this.batchOutputSizeText = this.formatBytes(data.compressed_size || 0);
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
            const files = Array.from(input.files || []);
            if (files.length) this.processSelection(files);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            e.stopPropagation();
            this.dragover = false;
            const files = Array.from(e.dataTransfer.files || []);
            if (files.length) this.processSelection(files);
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

        downloadBatchZip() {
            if (!this.batchZipUrl) return;
            const a = document.createElement('a');
            a.href = this.batchZipUrl;
            a.download = this.batchZipFilename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },
    }));
});
