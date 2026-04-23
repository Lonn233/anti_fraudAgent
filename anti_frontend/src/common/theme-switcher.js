/**
 * Theme Switcher — loads saved theme from localStorage on init
 * and exposes a simple API for switching themes.
 *
 * Usage (in any page's <script>):
 *   import { initTheme, setTheme, getTheme, THEMES } from '/ui/src/common/theme-switcher.js';
 *
 * Theme classes on <html>:
 *   theme-dark   — default, no class needed
 *   theme-light  — <html class="theme-light">
 *   theme-pink   — <html class="theme-pink">
 *
 * Drop-in UI: call mountThemeSwitcher(container) to append a theme picker button.
 */

const THEME_KEY = 'sentinel-theme';

/** Map of display name → class name */
export const THEMES = {
  dark:  '',
  light: 'theme-light',
  pink:  'theme-pink',
};

let _current = THEMES.dark;

/** Apply a theme by key name ('dark' | 'light' | 'pink') */
export function setTheme(name) {
  const cls = THEMES[name] || '';
  const html = document.documentElement;

  // Remove all theme classes
  Object.values(THEMES).forEach(c => {
    if (c) html.classList.remove(c);
  });

  // Apply the new one (empty string = default/no class)
  if (cls) html.classList.add(cls);

  _current = name;
  localStorage.setItem(THEME_KEY, name);

  // Notify listeners (e.g. ECharts charts) that theme changed
  window.dispatchEvent(new CustomEvent('sentinel-theme-change', { detail: { theme: name } }));
}

/** Return the currently active theme key */
export function getTheme() {
  return _current;
}

/** Initialise: read localStorage and apply saved theme */
export function initTheme() {
  const saved = localStorage.getItem(THEME_KEY) || 'dark';
  setTheme(saved);
  return saved;
}

/**
 * Mount a theme-switcher button into `container`.
 * The button cycles through dark → light → pink → dark.
 * Accessible label updates on each click.
 */
export function mountThemeSwitcher(container) {
  const btn = document.createElement('button');
  btn.setAttribute('aria-label', '切换主题');
  btn.setAttribute('title', '切换主题');
  btn.className = 'theme-switcher-btn';

  const ICONS = { dark: 'dark_mode', light: 'light_mode', pink: 'gradient' };
  const LABELS = { dark: '深色主题', light: '浅色主题', pink: '粉紫主题' };

  function refresh() {
    const current = getTheme();
    btn.innerHTML = `<span class="material-symbols-outlined text-xl">${ICONS[current] || ICONS.dark}</span>`;
    btn.setAttribute('aria-label', LABELS[current] || LABELS.dark);
  }

  btn.addEventListener('click', () => {
    const order = ['dark', 'light', 'pink'];
    const idx = order.indexOf(getTheme());
    setTheme(order[(idx + 1) % order.length]);
    refresh();
  });

  refresh();
  container.appendChild(btn);
}

// Auto-init when this script is loaded as a module
// (Pages that import it will call initTheme() manually if needed,
//  but we also try to self-initialize for classic <script> use.)
if (typeof document !== 'undefined') {
  // Wait for DOM so we can safely manipulate <html>
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
  } else {
    initTheme();
  }
}
