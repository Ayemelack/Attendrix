/* Shared bilingual (EN/FR) translation system for Attendrix */
(function() {
    window.i18n = window.i18n || { en: {}, fr: {} };
    var ns = window.i18n;

    function detectLang() {
        var stored = localStorage.getItem('attendrixLang');
        if (stored) return stored;
        return (navigator.language || 'en').startsWith('fr') ? 'fr' : 'en';
    }

    window.currentLang = detectLang();

    window.applyTranslations = function() {
        var lang = window.currentLang;
        document.querySelectorAll('[data-i18n]').forEach(function(el) {
            var key = el.getAttribute('data-i18n');
            var text = (ns[lang] && ns[lang][key]) || (ns.en && ns.en[key]) || key;
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                el.setAttribute('placeholder', text);
            } else {
                el.textContent = text;
            }
        });
        var toggle = document.getElementById('langToggle');
        if (toggle) toggle.textContent = lang === 'en' ? 'FR' : 'EN';
    };

    window.toggleLang = function() {
        window.currentLang = window.currentLang === 'en' ? 'fr' : 'en';
        localStorage.setItem('attendrixLang', window.currentLang);
        applyTranslations();
        document.documentElement.lang = window.currentLang;
        var toggle = document.getElementById('langToggle');
        if (toggle) toggle.textContent = window.currentLang === 'en' ? 'FR' : 'EN';
    };
})();
