/**
 * Site-wide JS: HTMX + Alpine integration, header tools nav, and other shared UI.
 *
 * Alpine: init directives on swapped content (see Alpine docs / HTMX cookbook).
 * initTree(swapTarget) walks the whole subtree; do not init per [x-data] with _x_dataStack
 * skips — that can leave child directives (e.g. x-show) uninitialized after navigation.
 */
(function () {
    'use strict';

    const FEATURE_NAV_COLLAPSED = 'feature-nav--collapsed';

    function featureNavFirstRowHeight(linksEl) {
        const first = linksEl.querySelector('.feature-nav__link');
        if (!first) return 36;
        const gap = parseFloat(getComputedStyle(linksEl).gap) || 6;
        return Math.ceil(first.getBoundingClientRect().height + gap);
    }

    function featureNavSetCollapsedHeightVar(nav) {
        const links = nav.querySelector('.feature-nav__links');
        if (!links) return;
        const h = featureNavFirstRowHeight(links);
        nav.style.setProperty('--feature-nav-collapsed-max', `${h}px`);
    }

    function featureNavSetToggleAria(btn, collapsed) {
        btn.setAttribute('aria-label', collapsed ? 'Show more tools' : 'Show fewer tools');
    }

    function featureNavSyncToggle(nav) {
        if (nav._featureNavSyncing) return;
        const links = nav.querySelector('.feature-nav__links');
        const btn = nav.querySelector('.feature-nav__toggle');
        if (!links || !btn) return;

        nav._featureNavSyncing = true;
        try {
            featureNavSetCollapsedHeightVar(nav);

            const wasCollapsed = nav.classList.contains(FEATURE_NAV_COLLAPSED);
            if (wasCollapsed) {
                nav.classList.remove(FEATURE_NAV_COLLAPSED);
                void links.offsetHeight;
            }

            const rowH = featureNavFirstRowHeight(links);
            const multiLine = links.scrollHeight > rowH + 1;

            if (wasCollapsed && multiLine) {
                nav.classList.add(FEATURE_NAV_COLLAPSED);
            }

            if (!multiLine) {
                nav.classList.remove(FEATURE_NAV_COLLAPSED);
                btn.hidden = true;
                btn.setAttribute('aria-expanded', 'true');
                featureNavSetToggleAria(btn, false);
                return;
            }

            btn.hidden = false;
            const collapsed = nav.classList.contains(FEATURE_NAV_COLLAPSED);
            btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            featureNavSetToggleAria(btn, collapsed);
        } finally {
            nav._featureNavSyncing = false;
        }
    }

    function featureNavObserve(nav) {
        const links = nav.querySelector('.feature-nav__links');
        if (!links) return;
        if (nav._featureNavResizeObserver) {
            nav._featureNavResizeObserver.disconnect();
        }
        let debounceTimer = null;
        const ro = new ResizeObserver(function () {
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                debounceTimer = null;
                featureNavSyncToggle(nav);
            }, 50);
        });
        ro.observe(links);
        nav._featureNavResizeObserver = ro;
    }

    function initFeatureNav(nav) {
        if (!nav || !nav.classList.contains('feature-nav')) return;
        featureNavObserve(nav);
        featureNavSyncToggle(nav);
    }

    function initAllFeatureNavs() {
        document.querySelectorAll('.feature-nav').forEach(initFeatureNav);
    }

    document.addEventListener('DOMContentLoaded', function () {
        requestAnimationFrame(initAllFeatureNavs);
    });

    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.feature-nav__toggle');
        if (!btn) return;
        const nav = btn.closest('.feature-nav');
        if (!nav) return;
        e.preventDefault();
        nav.classList.toggle(FEATURE_NAV_COLLAPSED);
        featureNavSyncToggle(nav);
    });

    document.body.addEventListener('htmx:afterSwap', function (evt) {
        const target = evt.detail && evt.detail.target;
        if (!target) return;

        if (target.id === 'htmx-page' && window.Alpine && typeof window.Alpine.initTree === 'function') {
            window.Alpine.initTree(target);
        }

        if (target.id === 'feature-nav') {
            requestAnimationFrame(function () {
                initFeatureNav(target);
            });
        } else if (typeof target.querySelector === 'function') {
            const innerNav = target.querySelector('#feature-nav');
            if (innerNav) {
                requestAnimationFrame(function () {
                    initFeatureNav(innerNav);
                });
            }
        }
    });
})();
