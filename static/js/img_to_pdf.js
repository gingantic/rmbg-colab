// ================================================================
// Images to PDF — Alpine component
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('imgToPdfTool', () => ({
        step: 'upload',
        dragover: false,
        selectedFiles: [],
        fileNames: [],
        originalBytes: 0,
        pdfBytes: 0,
        lastPageCount: 0,
        resultServerPath: null,
        shareLink: '',
        showShareRow: false,
        showOpenTab: false,
        toastVisible: false,
        toastMessage: '',
        toastTimer: null,
        originalSizeText: '—',
        pdfSizeText: '—',
        pageCountText: '—',

        MAX_SIZE_MB: 20,
        // Include image/jpg — some browsers/OSes send it instead of image/jpeg
        ALLOWED_TYPES: [
            'image/png',
            'image/jpeg',
            'image/jpg',
            'image/pjpeg',
            'image/webp',
            'image/bmp',
            'image/x-ms-bmp',
            'image/tiff',
            'image/x-tiff',
        ],

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

        isAllowedFile(file) {
            if (!file) return false;
            const t = (file.type || '').toLowerCase();
            if (this.ALLOWED_TYPES.includes(t)) return true;
            // Some pickers leave type empty; match common raster extensions only
            return /\.(png|jpe?g|jfif|jpe|webp|bmp|tiff?)$/i.test(file.name);
        },

        fileKey(file, idx) {
            return `${idx}|${file.name}|${file.size}|${file.lastModified}`;
        },

        setFilesFromList(fileList) {
            const incoming = Array.from(fileList || []);
            const arr = incoming.filter((f) => this.isAllowedFile(f));
            const skipped = incoming.length - arr.length;
            if (skipped > 0) this.showError(`${skipped} file(s) skipped (unsupported type).`);
            const tooBig = arr.filter((f) => f.size > this.MAX_SIZE_MB * 1024 * 1024);
            if (tooBig.length) {
                this.showError(`Each file must be under ${this.MAX_SIZE_MB} MB.`);
                return;
            }
            if (arr.length === 0) return;

            // Additive browse/drop: keep existing files and append new unique ones.
            const seen = new Set(this.selectedFiles.map((f) => `${f.name}|${f.size}|${f.lastModified}`));
            for (const f of arr) {
                const key = `${f.name}|${f.size}|${f.lastModified}`;
                if (!seen.has(key)) {
                    this.selectedFiles.push(f);
                    seen.add(key);
                }
            }
            this.fileNames = this.selectedFiles.map((f) => f.name);
        },

        moveUp(idx) {
            if (idx <= 0 || idx >= this.selectedFiles.length) return;
            const tmp = this.selectedFiles[idx - 1];
            this.selectedFiles[idx - 1] = this.selectedFiles[idx];
            this.selectedFiles[idx] = tmp;
            this.fileNames = this.selectedFiles.map((f) => f.name);
        },

        moveDown(idx) {
            if (idx < 0 || idx >= this.selectedFiles.length - 1) return;
            const tmp = this.selectedFiles[idx + 1];
            this.selectedFiles[idx + 1] = this.selectedFiles[idx];
            this.selectedFiles[idx] = tmp;
            this.fileNames = this.selectedFiles.map((f) => f.name);
        },

        removeAt(idx) {
            if (idx < 0 || idx >= this.selectedFiles.length) return;
            this.selectedFiles.splice(idx, 1);
            this.fileNames = this.selectedFiles.map((f) => f.name);
        },

        formatBytes(n) {
            if (n < 1024) return `${n} B`;
            if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
            return `${(n / (1024 * 1024)).toFixed(2)} MB`;
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
            this.selectedFiles = [];
            this.fileNames = [];
            this.originalBytes = 0;
            this.pdfBytes = 0;
            this.lastPageCount = 0;
            this.resultServerPath = null;
            this.showShareRow = false;
            this.showOpenTab = false;
            this.originalSizeText = '—';
            this.pdfSizeText = '—';
            this.pageCountText = '—';
            const input = this.$refs.fileInput;
            if (input) input.value = '';
        },

        goToResult(totalIn, pdfSize, pages) {
            this.originalBytes = totalIn;
            this.pdfBytes = pdfSize;
            this.lastPageCount = pages;
            this.originalSizeText = this.formatBytes(totalIn);
            this.pdfSizeText = this.formatBytes(pdfSize);
            this.pageCountText = String(pages);
            this.showOpenTab = true;
            this.step = 'result';
        },

        pickFile() {
            this.$refs.fileInput.click();
        },

        onFileChange() {
            const input = this.$refs.fileInput;
            this.setFilesFromList(input.files);
            input.value = '';
        },

        onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            this.setFilesFromList(e.dataTransfer.files);
        },

        clearFiles() {
            this.selectedFiles = [];
            this.fileNames = [];
            const input = this.$refs.fileInput;
            if (input) input.value = '';
        },

        async buildPdf() {
            if (this.selectedFiles.length === 0) {
                this.showError('Add at least one image.');
                return;
            }
            this.step = 'processing';
            const formData = new FormData();
            this.selectedFiles.forEach((f) => formData.append('images', f));
            const totalIn = this.selectedFiles.reduce((s, f) => s + f.size, 0);
            const pageCount = this.selectedFiles.length;
            try {
                const res = await fetch('/img-to-pdf', { method: 'POST', body: formData });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.error || `Server error (${res.status})`);
                }
                const data = await res.json();
                this.resultServerPath = data.result_url;
                this.goToResult(totalIn, data.compressed_size, pageCount);
            } catch (e) {
                this.showError(e.message || 'Something went wrong.');
                this.step = 'upload';
            }
        },

        init() {
            history.replaceState({ step: 'upload' }, '', window.location.pathname);
        },

        downloadResult() {
            if (!this.resultServerPath) return;
            const a = document.createElement('a');
            a.href = this.resultServerPath;
            a.download = 'document.pdf';
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
