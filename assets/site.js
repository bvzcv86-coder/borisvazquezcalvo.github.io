'use strict';

// Native details remain usable without this optional enhancement.
(() => {
  const menus = [...document.querySelectorAll('header details')];
  menus.forEach(menu => menu.addEventListener('toggle', () => {
    if (menu.open) menus.forEach(other => {
      if (other !== menu && !other.contains(menu) && !menu.contains(other)) other.open = false;
    });
  }));
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const open = menus.find(menu => menu.open && menu.contains(document.activeElement)) || menus.find(menu => menu.open);
    menus.forEach(menu => { menu.open = false; });
    if (open) open.querySelector('summary').focus();
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('header details') || event.target.closest('header details a')) {
      menus.forEach(menu => { menu.open = false; });
    }
  });
})();
