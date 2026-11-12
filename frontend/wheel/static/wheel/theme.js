/* Load synchronously in <head>, after the stylesheet and before the page body. */
(() => {
    'use strict';
    const key = 'fortuna-theme';
    const root = document.documentElement;
    let button;
    function readTheme() {
        try { return localStorage.getItem(key) === 'light' ? 'light' : 'dark'; }
        catch { return 'dark'; }
    }
    function paint(theme) {
        root.dataset.theme = theme;
        let meta = document.querySelector('meta[name="theme-color"]');
        if (!meta) {
            meta = document.createElement('meta');
            meta.name = 'theme-color';
            document.head.append(meta);
        }
        meta.content = theme === 'dark' ? '#101715' : '#f6f5f0';
        if (button) {
            const dark = theme === 'dark';
            const label = dark ? 'Светлая тема' : 'Тёмная тема';
            button.setAttribute('aria-label', 'Включить: ' + label.toLowerCase());
            button.title = 'Включить: ' + label.toLowerCase();
            button.querySelector('.theme-toggle-label').textContent = label;
            button.querySelector('svg').innerHTML = dark
                ? '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>'
                : '<path d="M20 15.5A8.5 8.5 0 0 1 8.5 4a8.5 8.5 0 1 0 11.5 11.5Z"/>';
        }
        window.dispatchEvent(new Event('fortune-theme-change'));
    }
    paint(readTheme());
    function mount() {
        if (document.getElementById('themeToggle')) return;
        button = document.createElement('button');
        button.id = 'themeToggle';
        button.type = 'button';
        button.className = 'icon-button theme-toggle';
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('viewBox', '0 0 24 24');
        icon.setAttribute('fill', 'none');
        icon.setAttribute('stroke', 'currentColor');
        icon.setAttribute('stroke-width', '1.8');
        icon.setAttribute('stroke-linecap', 'round');
        icon.setAttribute('stroke-linejoin', 'round');
        icon.setAttribute('aria-hidden', 'true');
        const label = document.createElement('span');
        label.className = 'theme-toggle-label';
        button.append(icon, label);
        const header = document.querySelector('header');
        if (header) header.insertBefore(button, document.getElementById('sound') || null);
        else {
            button.classList.add('theme-toggle-floating');
            document.body.append(button);
        }
        button.addEventListener('click', () => {
            const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
            try { localStorage.setItem(key, next); } catch {}
            paint(next);
        });
        paint(root.dataset.theme === 'light' ? 'light' : 'dark');
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
    else mount();
    window.addEventListener('storage', event => {
        if (event.key === key || event.key === null) paint(readTheme());
    });
})();
