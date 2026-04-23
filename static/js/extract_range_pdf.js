// ================================================================
// Extract page range PDF — Alpine component
// ================================================================

document.addEventListener("alpine:init", () => {
    Alpine.data("extractRangePdfTool", () => ({
        step: "upload",
        dragover: false,
        uploadProgress: 0,
        uploadPhase: "uploading",
        uploadSpeedText: "—",
        uploadRemainingText: "—",
        pdfFile: null,
        pageRange: "",
        originalBytes: 0,
        outputBytes: 0,
        resultServerPath: null,
        resultFileLabel: "—",
        toastVisible: false,
        toastMessage: "",
        toastTimer: null,

        MAX_SIZE_MB: 20,
        PDF_TYPE: "application/pdf",

        showError(msg) {
            this.toastMessage = msg;
            this.toastVisible = true;
            clearTimeout(this.toastTimer);
            this.$nextTick(() => {
                const el = this.$refs.errorToast;
                if (el) void el.offsetWidth;
            });
            this.toastTimer = setTimeout(() => {
                this.toastVisible = false;
            }, 4000);
        },

        formatBytes(n) {
            if (n < 1024) return `${n} B`;
            if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
            return `${(n / (1024 * 1024)).toFixed(2)} MB`;
        },

        isPdf(file) {
            if (!file) return false;
            const t = (file.type || "").toLowerCase();
            if (t === this.PDF_TYPE) return true;
            return /\.pdf$/i.test(file.name);
        },

        validateFile(file) {
            if (!file) return "No file selected.";
            if (!this.isPdf(file)) return "Please choose a PDF file.";
            if (file.size > this.MAX_SIZE_MB * 1024 * 1024) {
                return `File too large (max ${this.MAX_SIZE_MB} MB).`;
            }
            return null;
        },

        pickFile() {
            this.$refs.fileInput.click();
        },

        onFileChange() {
            const input = this.$refs.fileInput;
            const file = input.files[0];
            if (file) {
                const err = this.validateFile(file);
                if (err) {
                    this.showError(err);
                } else {
                    this.pdfFile = file;
                }
            }
            input.value = "";
        },

        onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (!file) return;
            const err = this.validateFile(file);
            if (err) {
                this.showError(err);
                return;
            }
            this.pdfFile = file;
        },

        async process() {
            if (!this.pdfFile) {
                this.showError("Upload one PDF first.");
                return;
            }
            const range = (this.pageRange || "").trim();
            if (!range) {
                this.showError("Enter a page like 5 or a range like 3-7.");
                return;
            }

            this.uploadProgress = 0;
            this.uploadPhase = "uploading";
            this.uploadSpeedText = "—";
            this.uploadRemainingText = this.formatBytes(this.pdfFile.size || 0);
            this.step = "processing";
            const uploadStartedAt = Date.now();
            const form = new FormData();
            form.append("pdf", this.pdfFile);
            form.append("page_range", range);

            try {
                const data = await uploadXHR("/extract-range-pdf", form, (pct, detail) => {
                    this.uploadProgress = pct;
                    if (detail && detail.lengthComputable) {
                        const elapsedSeconds = Math.max((Date.now() - uploadStartedAt) / 1000, 0.001);
                        const bytesPerSecond = detail.loaded / elapsedSeconds;
                        const remainingBytes = Math.max(detail.total - detail.loaded, 0);
                        this.uploadSpeedText = `${this.formatBytes(Math.max(Math.round(bytesPerSecond), 0))}/s`;
                        this.uploadRemainingText = this.formatBytes(remainingBytes);
                    }
                    if (pct >= 100) this.uploadPhase = "processing";
                });
                this.resultServerPath = data.result_url;
                this.resultFileLabel = data.filename || "output.pdf";
                this.originalBytes = this.pdfFile.size;
                this.outputBytes = data.compressed_size || 0;
                this.step = "result";
            } catch (e) {
                this.showError(e.message || "Something went wrong.");
                this.step = "upload";
            }
        },

        downloadResult() {
            if (!this.resultServerPath) return;
            const a = document.createElement("a");
            a.href = this.resultServerPath;
            a.download = this.resultFileLabel || "output.pdf";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },

        goToUpload() {
            this.step = "upload";
            this.pdfFile = null;
            this.pageRange = "";
            this.originalBytes = 0;
            this.outputBytes = 0;
            this.resultServerPath = null;
            this.resultFileLabel = "—";
            this.uploadSpeedText = "—";
            this.uploadRemainingText = "—";
            const input = this.$refs.fileInput;
            if (input) input.value = "";
        },

        init() {
            history.replaceState({ step: "upload" }, "", window.location.pathname);
        },
    }));
});

