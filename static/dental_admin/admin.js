'use strict';
const passwordToggle = document.querySelector('[data-password-toggle]');
if (passwordToggle) {
  const password = document.getElementById('id_password');
  passwordToggle.addEventListener('click', () => {
    const reveal = password.type === 'password';
    password.type = reveal ? 'text' : 'password';
    passwordToggle.setAttribute('aria-pressed', String(reveal));
    passwordToggle.setAttribute('aria-label', reveal ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور');
  });
}

const sidebarToggle = document.getElementById('toggle-nav-sidebar');
if (sidebarToggle) {
  const main = document.getElementById('main');
  const sidebar = document.getElementById('nav-sidebar');
  const mobile = window.matchMedia('(max-width: 767px)');
  const backdrop = document.querySelector('.dh-sidebar-backdrop');
  const syncSidebar = () => {
    const expanded = mobile.matches ? main.classList.contains('mobile-nav-open') : main.classList.contains('shifted');
    sidebar.setAttribute('aria-expanded', String(expanded));
    sidebarToggle.setAttribute('aria-expanded', String(expanded));
  };
  sidebarToggle.addEventListener('click', () => {
    if (mobile.matches) main.classList.toggle('mobile-nav-open');
    syncSidebar();
  });
  backdrop.addEventListener('click', () => sidebarToggle.click());
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && mobile.matches && main.classList.contains('mobile-nav-open')) {
      sidebarToggle.click();
      sidebarToggle.focus();
    }
  });
  mobile.addEventListener('change', () => {
    main.classList.remove('mobile-nav-open');
    syncSidebar();
  });
  syncSidebar();
}
