(function() {
  'use strict';

  var sidebar = document.querySelector('.sidebar, #sidebar, #institutionalSidebar, #lecturerSidebar, #studentSidebar');
  if (!sidebar) return;

  var overlay = document.querySelector('.sidebar-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);
  }

  function syncOverlay() {
    var isOpen = sidebar.classList.contains('open');
    overlay.classList.toggle('active', isOpen);
    document.body.style.overflow = isOpen ? 'hidden' : '';
  }

  var observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(m) {
      if (m.attributeName === 'class') syncOverlay();
    });
  });
  observer.observe(sidebar, { attributes: true });

  overlay.addEventListener('click', function() {
    sidebar.classList.remove('open');
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && sidebar.classList.contains('open')) {
      sidebar.classList.remove('open');
    }
  });

  var mql = window.matchMedia('(min-width: 768px)');
  mql.addListener(function(e) {
    if (e.matches) sidebar.classList.remove('open');
  });

  window.addEventListener('popstate', function() {
    sidebar.classList.remove('open');
  });

  history.pushState = (function(original) {
    return function() {
      sidebar.classList.remove('open');
      return original.apply(this, arguments);
    };
  })(history.pushState);

  syncOverlay();
})();
