// ================================================================
// Shared XHR upload helper — used by all file-upload Alpine tools
// ================================================================

/**
 * Upload formData to url via XHR, calling onProgress(0-100, detail) as bytes are sent.
 * Resolves with the parsed JSON response body, rejects on network or HTTP errors.
 *
 * @param {string} url
 * @param {FormData} formData
 * @param {(pct: number, detail?: { loaded: number, total: number, lengthComputable: boolean }) => void} onProgress
 * @returns {Promise<object>}
 */
function uploadXHR(url, formData, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', url);

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                onProgress(Math.round((e.loaded / e.total) * 100), {
                    loaded: e.loaded,
                    total: e.total,
                    lengthComputable: e.lengthComputable,
                });
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    resolve(JSON.parse(xhr.responseText));
                } catch {
                    reject(new Error('Invalid JSON response from server.'));
                }
            } else {
                try {
                    const d = JSON.parse(xhr.responseText);
                    reject(new Error(d.error || `Server error (${xhr.status})`));
                } catch {
                    reject(new Error(`Server error (${xhr.status})`));
                }
            }
        });

        xhr.addEventListener('error', () => reject(new Error('Network error — check your connection.')));
        xhr.addEventListener('abort', () => reject(new Error('Upload aborted.')));

        xhr.send(formData);
    });
}
