// ================================================================
// Merge PDF — Alpine component
// ================================================================

document.addEventListener('alpine:init', () => {
    Alpine.data('mergePdfTool', () => ({
        step: 'upload',
        dragover: false,
        uploadProgress: 0,
        uploadPhase: 'uploading',
        selectedFiles: [],
        originalBytes: 0,
        mergedBytes: 0,
        mergedCount: 0,
        resultServerPath: null,
        showOpenTab: false,
        toastVisible: false,
        toastMessage: '',
        toastTimer: null,
        originalSizeText: '—',
        pdfSizeText: '—',
        fileCountText: '—',

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

        isPdf(file) {
            if (!file) return false;
            const t = (file.type || '').toLowerCase();
            if (t === this.PDF_TYPE) return true;
            return /\.pdf$/i.test(file.name);
        },

        fileKey(file, idx) {
            return `${idx}|${file.name}|${file.size}|${file.lastModified}`;
        },

        setFilesFromList(fileList) {
            const incoming = Array.from(fileList || []);
            const valid = incoming.filter((f) => this.isPdf(f));
            const skipped = incoming.length - valid.length;
            if (skipped > 0) this.showError(`${skipped} file(s) skipped (PDF only).`);

            const tooBig = valid.filter((f) => f.size > this.MAX_SIZE_MB * 1024 * 1024);
            if (tooBig.length > 0) {
                this.showError(`Each file must be under ${this.MAX_SIZE_MB} MB.`);
                return;
            }
            if (valid.length === 0) return;

            // Additive selection, deduplicated by name+size+mtime.
            const seen = new Set(this.selectedFiles.map((f) => `${f.name}|${f.size}|${f.lastModified}`));
            for (const f of valid) {
                const key = `${f.name}|${f.size}|${f.lastModified}`;
                if (!seen.has(key)) {
                    this.selectedFiles.push(f);
                    seen.add(key);
                }
            }
        },

        formatBytes(n) {
            if (n < 1024) return `${n} B`;
            if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
            return `${(n / (1024 * 1024)).toFixed(2)} MB`;
        },

        moveUp(idx) {
            if (idx <= 0 || idx >= this.selectedFiles.length) return;
            const tmp = this.selectedFiles[idx - 1];
            this.selectedFiles[idx - 1] = this.selectedFiles[idx];
            this.selectedFiles[idx] = tmp;
        },

        moveDown(idx) {
            if (idx < 0 || idx >= this.selectedFiles.length - 1) return;
            const tmp = this.selectedFiles[idx + 1];
            this.selectedFiles[idx + 1] = this.selectedFiles[idx];
            this.selectedFiles[idx] = tmp;
        },

        removeAt(idx) {
            if (idx < 0 || idx >= this.selectedFiles.length) return;
            this.selectedFiles.splice(idx, 1);
        },

        clearFiles() {
            this.selectedFiles = [];
            const input = this.$refs.fileInput;
            if (input) input.value = '';
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

        goBackToUpload() {
            this.step = 'upload';
            this.showOpenTab = false;
        },

        goToUpload() {
            this.step = 'upload';
            this.selectedFiles = [];
            this.originalBytes = 0;
            this.mergedBytes = 0;
            this.mergedCount = 0;
            this.resultServerPath = null;
            this.showOpenTab = false;
            this.originalSizeText = '—';
            this.pdfSizeText = '—';
            this.fileCountText = '—';
            const input = this.$refs.fileInput;
            if (input) input.value = '';
        },

        goToResult(totalIn, mergedSize, count) {
            this.originalBytes = totalIn;
            this.mergedBytes = mergedSize;
            this.mergedCount = count;
            this.originalSizeText = this.formatBytes(totalIn);
            this.pdfSizeText = this.formatBytes(mergedSize);
            this.fileCountText = String(count);
            this.showOpenTab = true;
            this.step = 'result';
        },

        async mergePdfs() {
            if (this.selectedFiles.length < 2) {
                this.showError('Add at least two PDF files.');
                return;
            }

            this.uploadProgress = 0;
            this.uploadPhase = 'uploading';
            this.step = 'processing';
            const formData = new FormData();
            for (const f of this.selectedFiles) formData.append('pdfs', f);
            const totalIn = this.selectedFiles.reduce((sum, f) => sum + f.size, 0);
            const count = this.selectedFiles.length;

            try {
                const data = await uploadXHR('/merge-pdf', formData, (pct) => {
                    this.uploadProgress = pct;
                    if (pct >= 100) this.uploadPhase = 'processing';
                });
                this.resultServerPath = data.result_url;
                this.goToResult(totalIn, data.compressed_size, count);
            } catch (e) {
                this.showError(e.message || 'Something went wrong.');
                this.step = 'upload';
            }
        },

        downloadResult() {
            if (!this.resultServerPath) return;
            const a = document.createElement('a');
            a.href = this.resultServerPath;
            a.download = 'merged.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },

        init() {
            history.replaceState({ step: 'upload' }, '', window.location.pathname);
        },
    }));
});
