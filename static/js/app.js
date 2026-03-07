// ================================================================
// RMBG 2.0 — Client-side Logic
// ================================================================

(() => {
    'use strict';

    // --- DOM Elements ---
    const dropZone       = document.getElementById('drop-zone');
    const fileInput      = document.getElementById('file-input');
    const uploadSection  = document.getElementById('upload-section');
    const processSection = document.getElementById('processing-section');
    const resultSection  = document.getElementById('result-section');
    const originalImg    = document.getElementById('original-image');
    const resultImg      = document.getElementById('result-image');
    const downloadBtn    = document.getElementById('download-btn');
    const newImageBtn    = document.getElementById('new-image-btn');
    const errorToast     = document.getElementById('error-toast');
    const errorText      = document.getElementById('error-text');

    const MAX_SIZE_MB   = 20;
    const ALLOWED_TYPES = new Set([
        'image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'image/tiff',
    ]);

    let resultBlobUrl = null;

    // --- Helpers ---
    function show(el)  { el.classList.remove('hidden'); }
    function hide(el)  { el.classList.add('hidden'); }

    function showError(msg) {
        errorText.textContent = msg;
        errorToast.classList.remove('hidden');
        // Force reflow for re-triggering animation
        void errorToast.offsetWidth;
        errorToast.classList.add('visible');
        setTimeout(() => {
            errorToast.classList.remove('visible');
            setTimeout(() => errorToast.classList.add('hidden'), 300);
        }, 4000);
    }

    function validateFile(file) {
        if (!file) return 'No file selected.';
        if (!ALLOWED_TYPES.has(file.type)) return `Unsupported type: ${file.type || 'unknown'}`;
        if (file.size > MAX_SIZE_MB * 1024 * 1024) return `File too large (max ${MAX_SIZE_MB} MB).`;
        return null;
    }

    // --- State transitions ---
    function goToUpload() {
        hide(processSection);
        hide(resultSection);
        show(uploadSection);
        if (resultBlobUrl) { URL.revokeObjectURL(resultBlobUrl); resultBlobUrl = null; }
        originalImg.src = '';
        resultImg.src = '';
    }

    function goToProcessing() {
        hide(uploadSection);
        hide(resultSection);
        show(processSection);
    }

    function goToResult(originalSrc, resultSrc) {
        hide(uploadSection);
        hide(processSection);
        originalImg.src = originalSrc;
        resultImg.src = resultSrc;
        show(resultSection);
    }

    // --- Core: Upload & process ---
    async function processImage(file) {
        const error = validateFile(file);
        if (error) { showError(error); return; }

        // Show original preview
        const originalUrl = URL.createObjectURL(file);

        goToProcessing();

        const formData = new FormData();
        formData.append('image', file);

        try {
            const res = await fetch('/remove-bg', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.error || `Server error (${res.status})`);
            }

            const blob = await res.blob();
            resultBlobUrl = URL.createObjectURL(blob);
            goToResult(originalUrl, resultBlobUrl);
        } catch (err) {
            showError(err.message || 'Something went wrong.');
            goToUpload();
            URL.revokeObjectURL(originalUrl);
        }
    }

    // --- Drag & Drop ---
    ['dragenter', 'dragover'].forEach(evt => {
        dropZone.addEventListener(evt, e => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, e => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
        });
    });

    dropZone.addEventListener('drop', e => {
        const file = e.dataTransfer.files[0];
        if (file) processImage(file);
    });

    // --- Click to browse ---
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) processImage(file);
        fileInput.value = '';
    });

    // --- Download ---
    downloadBtn.addEventListener('click', () => {
        if (!resultBlobUrl) return;
        const a = document.createElement('a');
        a.href = resultBlobUrl;
        a.download = 'rmbg_result.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });

    // --- New Image ---
    newImageBtn.addEventListener('click', goToUpload);
})();
