/* 语言与主题切换、轻量灯箱 */
(function () {
  const root = document.documentElement;
  const savedLang = localStorage.getItem('la_lang');
  const savedTheme = localStorage.getItem('la_theme');
  if (savedLang) root.setAttribute('data-lang', savedLang);
  if (savedTheme) root.setAttribute('data-theme', savedTheme);
})();

function toggleLang() {
  const root = document.documentElement;
  const cur = root.getAttribute('data-lang') || 'zh';
  const next = cur === 'zh' ? 'en' : 'zh';
  root.setAttribute('data-lang', next);
  localStorage.setItem('la_lang', next);
}

function toggleTheme() {
  const root = document.documentElement;
  const cur = root.getAttribute('data-theme') || 'dark';
  const next = cur === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('la_theme', next);
}

// 简易灯箱
let lightboxDiv;
function openLightbox(src) {
  if (!lightboxDiv) {
    lightboxDiv = document.createElement('div');
    lightboxDiv.className = 'lightbox';
    lightboxDiv.innerHTML = '<img alt="lightbox" />';
    lightboxDiv.addEventListener('click', () => lightboxDiv.classList.remove('open'));
    document.body.appendChild(lightboxDiv);
  }
  const img = lightboxDiv.querySelector('img');
  img.src = src;
  lightboxDiv.classList.add('open');
}

document.addEventListener('click', (e) => {
  const target = e.target;
  if (target && target.matches('[data-lightbox]')) {
    e.preventDefault();
    openLightbox(target.getAttribute('data-lightbox'));
  }
});

// 暴露到全局供按钮调用
window.LA = { toggleLang, toggleTheme };

