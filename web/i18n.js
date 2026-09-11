/* Commscribe - språk i grensesnittet.
   Lastes før app.js. Én JSON-fil per språk under /lang/; engelsk er
   reserven for nøkler et annet språk mangler, så en halvferdig oversettelse
   viser engelsk der den er tom, ikke nøkkelnavnet. */

const I18N = (() => {
  // Rekkefølgen er rekkefølgen i velgeren. Navnet vises på språket selv.
  const AVAILABLE = ["en", "nb", "sv", "de", "fr", "es"];
  const FALLBACK = "en";

  let current = FALLBACK;
  let strings = {};
  let fallback = {};

  async function fetchLang(code) {
    const res = await fetch(`/lang/${code}.json`, { cache: "no-cache" });
    if (!res.ok) throw new Error(`lang ${code}: ${res.status}`);
    return res.json();
  }

  /** Last et språk. Ukjent kode faller tilbake til engelsk. */
  async function load(code) {
    const lang = AVAILABLE.includes(code) ? code : FALLBACK;
    if (!Object.keys(fallback).length) fallback = await fetchLang(FALLBACK);
    strings = lang === FALLBACK ? fallback : await fetchLang(lang);
    current = lang;
    document.documentElement.lang = lang;
    return lang;
  }

  /** Tekst for en nøkkel, med {navn}-plassholdere fylt inn. */
  function t(key, vars) {
    let text = strings[key] ?? fallback[key];
    if (text == null) return key;
    if (vars) {
      for (const [name, value] of Object.entries(vars)) {
        text = text.split(`{${name}}`).join(String(value));
      }
    }
    return text;
  }

  /** Sett statisk tekst i dokumentet fra data-i18n-attributter.
      data-i18n        -> textContent
      data-i18n-html   -> innerHTML (for tekster med <kbd> og <b>)
      data-i18n-title, -placeholder, -aria-label -> attributtet */
  function apply(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-html]").forEach((el) => {
      el.innerHTML = t(el.dataset.i18nHtml);
    });
    for (const attr of ["title", "placeholder", "aria-label"]) {
      const key = `i18n${attr.replace(/(^|-)(\w)/g, (_, __, c) => c.toUpperCase())}`;
      root.querySelectorAll(`[data-i18n-${attr}]`).forEach((el) => {
        el.setAttribute(attr, t(el.dataset[key]));
      });
    }
  }

  /** Navnet på et språk, slik det heter på det språket selv. */
  const names = { en: "English", nb: "Norsk", sv: "Svenska", de: "Deutsch",
                  fr: "Français", es: "Español" };

  return {
    t, load, apply,
    get current() { return current; },
    available: AVAILABLE,
    name: (code) => names[code] || code,
  };
})();

const t = I18N.t;
