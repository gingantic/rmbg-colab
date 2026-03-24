// ================================================================
// Split + Reorder PDF — Alpine component
// ================================================================

document.addEventListener("alpine:init", () => {
    Alpine.data("splitReorderPdfTool", () => ({
        step: "upload",
        dragover: false,
        pdfFile: null,
        pageCount: 0,
        pages: [],
        splitMarkers: [],
        splitBlocks: [],
        exportMode: "single",
        resultServerPath: null,
        resultFileLabel: "—",
        originalBytes: 0,
        outputBytes: 0,
        toastVisible: false,
        toastMessage: "",
        toastTimer: null,

        MAX_SIZE_MB: 20,
        PDF_TYPE: "application/pdf",
        pdfLibLoadPromise: null,

        ensurePdfLibLoaded() {
            if (window.PDFLib && window.PDFLib.PDFDocument) return Promise.resolve();
            if (this.pdfLibLoadPromise) return this.pdfLibLoadPromise;
            this.pdfLibLoadPromise = new Promise((resolve, reject) => {
                const existing = document.querySelector('script[data-pdf-lib="split-reorder"]');
                if (existing) {
                    existing.addEventListener("load", () => resolve(), { once: true });
                    existing.addEventListener("error", () => reject(new Error("Failed to load PDF parser.")), { once: true });
                    return;
                }
                const s = document.createElement("script");
                s.src = "https://cdn.jsdelivr.net/npm/pdf-lib@1.17.1/dist/pdf-lib.min.js";
                s.defer = true;
                s.dataset.pdfLib = "split-reorder";
                s.onload = () => resolve();
                s.onerror = () => reject(new Error("Failed to load PDF parser."));
                document.head.appendChild(s);
            });
            return this.pdfLibLoadPromise;
        },

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

        async getPageCount(file) {
            await this.ensurePdfLibLoaded();
            if (!window.PDFLib || !window.PDFLib.PDFDocument) {
                throw new Error("PDF parser failed to load.");
            }
            const raw = await file.arrayBuffer();
            const pdfDoc = await window.PDFLib.PDFDocument.load(raw, { ignoreEncryption: true });
            return pdfDoc.getPageCount();
        },

        async setFile(file) {
            if (!this.isPdf(file)) {
                this.showError("PDF only.");
                return;
            }
            if (file.size > this.MAX_SIZE_MB * 1024 * 1024) {
                this.showError(`File too large (max ${this.MAX_SIZE_MB} MB).`);
                return;
            }
            try {
                const count = await this.getPageCount(file);
                this.pdfFile = file;
                this.pageCount = count;
                this.pages = Array.from({ length: count }, (_, i) => ({ num: i + 1 }));
                this.splitMarkers = [];
                this.splitBlocks = [];
                this.exportMode = "single";
            } catch (e) {
                this.showError(e.message || "Unable to parse PDF.");
            }
        },

        pickFile() {
            this.$refs.fileInput.click();
        },

        async onFileChange() {
            const input = this.$refs.fileInput;
            const file = input.files[0];
            if (file) await this.setFile(file);
            input.value = "";
        },

        async onDrop(e) {
            e.preventDefault();
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) await this.setFile(file);
        },

        movePageUp(idx) {
            if (idx <= 0 || idx >= this.pages.length) return;
            const tmp = this.pages[idx - 1];
            this.pages[idx - 1] = this.pages[idx];
            this.pages[idx] = tmp;
            this.rebuildSplitBlocksFromMarkers();
        },

        movePageDown(idx) {
            if (idx < 0 || idx >= this.pages.length - 1) return;
            const tmp = this.pages[idx + 1];
            this.pages[idx + 1] = this.pages[idx];
            this.pages[idx] = tmp;
            this.rebuildSplitBlocksFromMarkers();
        },

        hasSplitAt(boundary) {
            return this.splitMarkers.includes(boundary);
        },

        addSplitAt(boundary) {
            if (boundary < 1 || boundary >= this.pages.length) return;
            if (this.hasSplitAt(boundary)) return;
            this.splitMarkers.push(boundary);
            this.splitMarkers.sort((a, b) => a - b);
            this.rebuildSplitBlocksFromMarkers();
        },

        removeSplitAt(boundary) {
            this.splitMarkers = this.splitMarkers.filter((v) => v !== boundary);
            this.rebuildSplitBlocksFromMarkers();
        },

        moveSplitUp(boundary) {
            if (!this.hasSplitAt(boundary)) return;
            if (boundary <= 1) return;
            if (this.hasSplitAt(boundary - 1)) return;
            this.splitMarkers = this.splitMarkers
                .filter((v) => v !== boundary)
                .concat(boundary - 1)
                .sort((a, b) => a - b);
            this.rebuildSplitBlocksFromMarkers();
        },

        moveSplitDown(boundary) {
            if (!this.hasSplitAt(boundary)) return;
            if (boundary >= this.pages.length - 1) return;
            if (this.hasSplitAt(boundary + 1)) return;
            this.splitMarkers = this.splitMarkers
                .filter((v) => v !== boundary)
                .concat(boundary + 1)
                .sort((a, b) => a - b);
            this.rebuildSplitBlocksFromMarkers();
        },

        rebuildSplitBlocksFromMarkers() {
            const markers = Array.from(new Set(this.splitMarkers))
                .filter((m) => Number.isInteger(m) && m >= 1 && m < this.pages.length)
                .sort((a, b) => a - b);
            this.splitMarkers = markers;

            if (markers.length === 0) {
                this.splitBlocks = [];
                this.exportMode = "single";
                return;
            }

            const blocks = [];
            let start = 0;
            for (const boundary of markers) {
                blocks.push({ pages: this.pages.slice(start, boundary).map((p) => p.num) });
                start = boundary;
            }
            blocks.push({ pages: this.pages.slice(start).map((p) => p.num) });
            this.splitBlocks = blocks;
            // Product rule: when split exists, output is ZIP.
            this.exportMode = "zip";
        },

        async process() {
            if (!this.pdfFile) {
                this.showError("Upload one PDF first.");
                return;
            }
            this.step = "processing";
            const form = new FormData();
            form.append("pdf", this.pdfFile);
            form.append("page_order_json", JSON.stringify(this.pages.map((p) => p.num)));
            if (this.splitBlocks.length > 0) {
                form.append("split_blocks_json", JSON.stringify(this.splitBlocks.map((b) => b.pages)));
            }
            form.append("export_mode", this.splitBlocks.length > 0 ? "zip" : "single");

            try {
                const res = await fetch("/split-reorder-pdf", { method: "POST", body: form });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.error || `Server error (${res.status})`);
                }
                const data = await res.json();
                this.resultServerPath = data.result_url;
                this.resultFileLabel = data.filename || "output";
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
            a.download = this.resultFileLabel || "output";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },

        goToUpload() {
            this.step = "upload";
            this.pdfFile = null;
            this.pageCount = 0;
            this.pages = [];
            this.splitMarkers = [];
            this.splitBlocks = [];
            this.exportMode = "single";
            this.resultServerPath = null;
            this.resultFileLabel = "—";
            this.originalBytes = 0;
            this.outputBytes = 0;
            const input = this.$refs.fileInput;
            if (input) input.value = "";
        },

        init() {
            history.replaceState({ step: "upload" }, "", window.location.pathname);
        },
    }));
});
