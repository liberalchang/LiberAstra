/* LiberAstra site — booklet reader, cover, demo rows, access tabs, lightbox. */
(function () {
  'use strict';

  var root = document.documentElement;
  root.classList.add('js');

  var $ = function (selector, scope) { return (scope || document).querySelector(selector); };
  var $$ = function (selector, scope) { return Array.prototype.slice.call((scope || document).querySelectorAll(selector)); };
  var body = document.body;
  var stage = $('#stage');
  var leaves = $$('.leaf');
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

  var current = 0;
  var isBook = true;
  var turnTimer = 0;
  var foldFrame = 0;
  var coverHideTimer = 0;

  var contents = $('#contents');
  var bandEl = $('.book-band');
  var pageSelect = $('#page-select');
  var statusEl = $('[data-status]');
  var prevBtn = $('[data-prev]');
  var nextBtn = $('[data-next]');
  var motionBtn = $('[data-motion-toggle]');
  var langBtn = $('[data-lang-toggle]');
  var themeBtn = $('[data-theme-toggle]');

  var purposeDemo = $('.purpose-demo');
  var coverBtn = $('.book-cover');
  var coverBtns = $$('[data-cover-open]');
  var inlineCoverBtn = $('.btn-ink[data-cover-open]');
  var replayBtn = $('[data-cover-replay]');

  var demoPages = [];
  var demoByLeaf = new Map();

  var lightbox = $('#lightbox');
  var lightboxImage = $('[data-lightbox-image]');
  var lightboxCaption = $('[data-lightbox-caption]');
  var lightboxItems = [];
  var lightboxIndex = 0;

  /* ---------------------------------------------------------------- */
  /* Small helpers                                                     */
  /* ---------------------------------------------------------------- */

  function lang() {
    return root.getAttribute('data-lang') === 'en' ? 'en' : 'zh';
  }

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (e) {}
  }

  function readStore(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  function titleOf(leaf) {
    return lang() === 'en' ? leaf.dataset.titleEn : leaf.dataset.titleZh;
  }

  function themeName() {
    return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function imagePath(name) {
    return 'assets/images/' + themeName() + '/' + name;
  }

  function syncThemeImages() {
    $$('[data-theme-img]').forEach(function (img) {
      var name = img.getAttribute('data-theme-img');
      if (name) img.setAttribute('src', imagePath(name));
    });
  }

  /* ---------------------------------------------------------------- */
  /* Motion                                                            */
  /* ---------------------------------------------------------------- */

  var savedMotion = readStore('la_motion');
  var motionPaused = savedMotion ? savedMotion === 'paused' : reduced.matches;

  function applyMotion() {
    body.classList.toggle('motion-paused', motionPaused);
    if (motionBtn) {
      motionBtn.setAttribute('aria-pressed', String(motionPaused));
      var zh = $('.zh', motionBtn);
      var en = $('.en', motionBtn);
      if (zh) zh.textContent = motionPaused ? '继续动效' : '暂停动效';
      if (en) en.textContent = motionPaused ? 'Resume motion' : 'Pause motion';
    }
  }

  if (motionBtn) {
    motionBtn.addEventListener('click', function () {
      motionPaused = !motionPaused;
      store('la_motion', motionPaused ? 'paused' : 'on');
      applyMotion();
    });
  }
  if (typeof reduced.addEventListener === 'function') {
    reduced.addEventListener('change', function (event) {
      if (readStore('la_motion')) return;
      motionPaused = event.matches;
      applyMotion();
    });
  }
  applyMotion();

  /* ---------------------------------------------------------------- */
  /* Theme                                                             */
  /* ---------------------------------------------------------------- */

  function syncTheme() {
    var theme = root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    if (themeBtn) {
      themeBtn.setAttribute('aria-label', theme === 'dark'
        ? '切换到亮色主题 / Switch to light theme'
        : '切换到暗色主题 / Switch to dark theme');
    }
    var meta = $('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#17161a' : '#f8f4e9');
    syncThemeImages();
  }

  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      store('la_theme', next);
      syncTheme();
    });
  }
  syncTheme();

  /* ---------------------------------------------------------------- */
  /* Docs + language                                                   */
  /* ---------------------------------------------------------------- */

  function syncDocs() {
    var english = lang() === 'en';
    $$('[data-docs-zh]').forEach(function (link) {
      var href = english ? (link.dataset.docsEn || link.dataset.docsZh) : link.dataset.docsZh;
      if (href) link.setAttribute('href', href);
    });
  }

  function syncLanguage() {
    var next = lang();
    root.lang = next === 'en' ? 'en' : 'zh-CN';
    if (langBtn) {
      langBtn.dataset.current = next;
      langBtn.setAttribute('aria-label', next === 'en'
        ? '中文/EN · 切换到中文 / Switch to Chinese'
        : '中文/EN · Switch to English / 切换到英文');
    }
    document.title = next === 'en'
      ? 'LiberAstra — Orchestrate. Don\'t infer.'
      : 'LiberAstra — 只编排，不推理';
    syncDocs();
    renderPageOptions();
    renderAllDemos();
    if (lightbox && lightbox.open) renderLightbox();
    updateNav();
  }

  if (langBtn) {
    langBtn.addEventListener('click', function () {
      root.setAttribute('data-lang', lang() === 'en' ? 'zh' : 'en');
      store('la_lang', root.getAttribute('data-lang'));
      syncLanguage();
    });
  }

  /* ---------------------------------------------------------------- */
  /* Page navigation                                                   */
  /* ---------------------------------------------------------------- */

  function setLeafState(leaf, active) {
    leaf.hidden = !active;
    leaf.inert = !active;
    leaf.classList.toggle('is-active', active);
    if (active) leaf.removeAttribute('aria-hidden');
    else leaf.setAttribute('aria-hidden', 'true');
  }

  function updateNav() {
    if (prevBtn) prevBtn.disabled = current === 0;
    if (nextBtn) nextBtn.disabled = current === leaves.length - 1;
    if (bandEl && leaves[current]) bandEl.setAttribute('data-band', leaves[current].id);
    if (pageSelect) pageSelect.value = String(current);
    if (statusEl && leaves[current]) {
      var title = titleOf(leaves[current]);
      statusEl.textContent = lang() === 'en'
        ? 'Page ' + (current + 1) + ' of ' + leaves.length + '. ' + title
        : '第 ' + (current + 1) + ' 页，共 ' + leaves.length + ' 页。' + title;
    }
    $$('[data-chapter-link]').forEach(function (link) {
      var on = leaves[current] && link.dataset.chapterLink === leaves[current].dataset.chapter;
      link.classList.toggle('is-current', on);
      if (on) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }

  function renderPageOptions() {
    if (!pageSelect) return;
    pageSelect.innerHTML = '';
    leaves.forEach(function (leaf, index) {
      var option = document.createElement('option');
      option.value = String(index);
      option.textContent = String(index + 1).padStart(2, '0') + ' / ' +
        String(leaves.length).padStart(2, '0') + ' · ' + titleOf(leaf);
      pageSelect.appendChild(option);
    });
    pageSelect.value = String(current);
  }

  function finishTurn() {
    if (turnTimer) {
      window.clearTimeout(turnTimer);
      turnTimer = 0;
    }
    if (foldFrame) {
      window.cancelAnimationFrame(foldFrame);
      foldFrame = 0;
    }
    $$('.fold-layer, .turn-sheet', stage).forEach(function (node) { node.remove(); });
    leaves.forEach(function (leaf) { leaf.style.opacity = ''; });
  }

  function smoothStep(from, to, value) {
    var unit = Math.max(0, Math.min(1, (value - from) / (to - from)));
    return unit * unit * (3 - 2 * unit);
  }

  function startTurn(oldLeaf, forward, newLeaf) {
    finishTurn();
    var width = stage.clientWidth;
    var height = stage.clientHeight;
    var third = width / 3;
    var layer = document.createElement('div');
    layer.className = 'fold-layer';
    layer.setAttribute('aria-hidden', 'true');

    var parent = layer;
    var panels = [];
    for (var i = 0; i < 3; i++) {
      var panel = document.createElement('div');
      panel.className = 'fold-panel';
      panel.style.width = third + 'px';
      panel.style.height = height + 'px';

      var face = document.createElement('div');
      face.className = 'fold-slice ' + (i === 0 ? 'fold-leading' : i === 1 ? 'fold-mountain' : 'fold-valley');
      var snapshot = oldLeaf.cloneNode(true);
      snapshot.removeAttribute('id');
      snapshot.hidden = false;
      snapshot.inert = true;
      snapshot.setAttribute('aria-hidden', 'true');
      snapshot.classList.remove('is-active', 'leaf-enter-next', 'leaf-enter-prev', 'turn-sheet');
      $$('[id]', snapshot).forEach(function (node) { node.removeAttribute('id'); });
      snapshot.style.inset = 'auto';
      snapshot.style.left = (-i * third) + 'px';
      snapshot.style.top = '0';
      snapshot.style.width = width + 'px';
      snapshot.style.height = height + 'px';
      snapshot.style.boxShadow = 'none';
      snapshot.style.opacity = '1';
      face.appendChild(snapshot);

      var light = document.createElement('span');
      light.className = 'fold-light';
      face.appendChild(light);
      if (i > 0) {
        var crease = document.createElement('span');
        crease.className = 'fold-crease';
        face.appendChild(crease);
      }
      var edge = null;
      if (i === 0 || i === 2) {
        edge = document.createElement('span');
        edge.className = 'fold-edge ' + (i === 0 ? 'fold-edge-left' : 'fold-edge-right');
        face.appendChild(edge);
      }

      panel.appendChild(face);
      parent.appendChild(panel);
      parent = panel;
      panels.push({ panel: panel, light: light, crease: face.querySelector('.fold-crease'), edge: edge });
    }

    var ground = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    ground.classList.add('fold-ground');
    ground.setAttribute('aria-hidden', 'true');
    ground.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    var groundPath = document.createElementNS(ground.namespaceURI, 'path');
    ground.appendChild(groundPath);
    layer.insertBefore(ground, layer.firstChild);
    stage.appendChild(layer);

    var oldInner = $('.leaf-inner', oldLeaf);
    $$('.leaf-inner', layer).forEach(function (inner) {
      if (oldInner) inner.scrollTop = oldInner.scrollTop;
    });

    newLeaf.style.opacity = '0';
    var started = 0;
    var distance = width;
    var duration = 1180;
    var shadowSide = forward ? 1 : -1;

    function draw(now) {
      if (!started) started = now;
      var progress = Math.min(1, (now - started) / duration);
      var opening = smoothStep(0.1, 0.6, progress);
      var departure = smoothStep(0.5, 1, progress);
      var angle = 50 * opening + 24 * departure;
      var radians = angle * Math.PI / 180;
      var lift = 20 * smoothStep(0, 0.16, progress) + 10 * opening - 24 * departure;
      var shift = (distance - distance * Math.cos(radians)) * 0.22 + (forward ? -0.58 : 1.12) * distance * departure;
      var sin = Math.sin(radians);
      var cos = Math.cos(radians);

      panels.forEach(function (item, index) {
        var relative = (index === 0 ? 1 : index === 1 ? -2 : 2) * -1;
        item.panel.style.transform =
          'translateX(' + (index === 0 ? shift : 0) + 'px) ' +
          'translateZ(' + (index === 0 ? lift : 0) + 'px) ' +
          'rotateY(' + (relative * angle) + 'deg)';
        var illumination = 0.78 * cos + (index === 1 ? -0.48 : 0.48) * sin;
        var dark = Math.max(0, 1 - illumination / 0.78) * 0.68;
        item.light.style.background = illumination < 0.78 ? '#28251f' : '#fffbed';
        item.light.style.opacity = illumination < 0.78
          ? String(dark)
          : String(Math.min(0.13, (illumination - 0.78) * 0.65));
        if (item.crease) item.crease.style.opacity = String(Math.min(1, sin * 1.12));
        if (item.edge) {
          var showEdge = (forward && index === 2) || (!forward && index === 0);
          item.edge.style.opacity = showEdge ? String(Math.min(1, sin * 1.2) * 0.72) : '0';
        }
      });

      var vertices = [];
      for (var vi = 0; vi < 4; vi++) {
        vertices.push({ u: shift + vi * third * cos, z: lift + (vi % 2) * third * sin });
      }
      var shadowPath = '';
      for (var si = 0; si < 3; si++) {
        var v1 = vertices[si];
        var v2 = vertices[si + 1];
        var points = [
          [v1.u + shadowSide * v1.z * 0.42, v1.z * 0.30],
          [v2.u + shadowSide * v2.z * 0.42, v2.z * 0.30],
          [v2.u + shadowSide * v2.z * 0.42, height + v2.z * 0.30],
          [v1.u + shadowSide * v1.z * 0.42, height + v1.z * 0.30]
        ];
        var area = 0;
        for (var qi = 0; qi < 4; qi++) {
          var nextPoint = points[(qi + 1) % 4];
          area += points[qi][0] * nextPoint[1] - nextPoint[0] * points[qi][1];
        }
        if (area < 0) points.reverse();
        shadowPath += 'M' + points.map(function (point) {
          return point[0].toFixed(2) + ',' + point[1].toFixed(2);
        }).join('L') + 'Z';
      }
      groundPath.setAttribute('d', shadowPath);
      ground.style.opacity = String((0.13 + 0.13 * sin) * smoothStep(0, 0.14, progress) * (1 - smoothStep(0.82, 1, progress)));
      ground.style.filter = 'blur(' + (2.5 + lift * 0.14 + sin * 3.5) + 'px)';
      newLeaf.style.opacity = String(smoothStep(0.42, 0.72, progress));
      layer.style.opacity = String(1 - smoothStep(0.82, 1, progress));

      if (progress < 1) {
        foldFrame = window.requestAnimationFrame(draw);
      } else {
        finishTurn();
      }
    }

    foldFrame = window.requestAnimationFrame(draw);
  }

  function go(index, options) {
    options = options || {};
    index = Math.max(0, Math.min(leaves.length - 1, index));

    if (!isBook) {
      if (index === current) {
        leaves[index].scrollIntoView({ behavior: motionPaused ? 'auto' : 'smooth', block: 'start' });
        if (options.focus) leaves[index].focus({ preventScroll: true });
        return;
      }
      current = index;
      leaves[index].scrollIntoView({ behavior: motionPaused ? 'auto' : 'smooth', block: 'start' });
      if (options.hash !== false) {
        try { history.replaceState(null, '', '#' + leaves[index].id); } catch (e) {}
      }
      if (options.focus) leaves[index].focus({ preventScroll: true });
      updateNav();
      return;
    }

    if (index === current) {
      var inner = $('.leaf-inner', leaves[index]);
      if (inner) inner.scrollTo({ top: 0, behavior: motionPaused ? 'auto' : 'smooth' });
      if (options.focus) leaves[index].focus({ preventScroll: true });
      return;
    }

    var oldLeaf = leaves[current];
    var newLeaf = leaves[index];
    var forward = index > current;
    var animate = !motionPaused && Math.abs(index - current) === 1;
    var shouldFocus = options.focus || oldLeaf.contains(document.activeElement);

    if (animate) startTurn(oldLeaf, forward, newLeaf);

    setLeafState(oldLeaf, false);
    setLeafState(newLeaf, true);

    var newInner = $('.leaf-inner', newLeaf);
    if (newInner) newInner.scrollTop = 0;
    if (!animate) newLeaf.style.opacity = '';

    current = index;
    updateNav();
    if (contents) contents.open = false;
    if (options.hash !== false) {
      try { history.replaceState(null, '', '#' + newLeaf.id); } catch (e) {}
    }
    if (shouldFocus) newLeaf.focus({ preventScroll: true });
  }

  /* ---------------------------------------------------------------- */
  /* Cover                                                             */
  /* ---------------------------------------------------------------- */

  function openCover(open) {
    if (!purposeDemo || !coverBtn) return;
    var wasFocused = document.activeElement && document.activeElement.matches('[data-cover-open]');
    if (coverHideTimer) {
      window.clearTimeout(coverHideTimer);
      coverHideTimer = 0;
    }
    purposeDemo.classList.toggle('is-open', open);
    coverBtn.classList.toggle('is-open', open);
    coverBtns.forEach(function (button) {
      if (button.hasAttribute('aria-expanded')) button.setAttribute('aria-expanded', String(open));
    });
    coverBtn.tabIndex = open ? -1 : 0;
    if (replayBtn) replayBtn.hidden = !open;
    if (inlineCoverBtn) inlineCoverBtn.hidden = open;
    if (open) {
      coverHideTimer = window.setTimeout(function () {
        if (coverBtn.classList.contains('is-open')) coverBtn.classList.add('is-hidden');
      }, motionPaused ? 40 : 1150);
      if (wasFocused && replayBtn) replayBtn.focus({ preventScroll: true });
    } else {
      coverBtn.classList.remove('is-hidden');
    }
  }

  coverBtns.forEach(function (button) {
    button.addEventListener('click', function () { openCover(true); });
  });
  if (replayBtn) {
    replayBtn.addEventListener('click', function () {
      openCover(false);
      if (coverBtn) coverBtn.focus({ preventScroll: true });
    });
  }

  /* ---------------------------------------------------------------- */
  /* Demo pages                                                        */
  /* ---------------------------------------------------------------- */

  function demoCaption(page) {
    var row = page.active;
    if (!row) return '';
    return lang() === 'en' ? row.dataset.captionEn : row.dataset.captionZh;
  }

  function renderDemo(page) {
    var caption = demoCaption(page);
    if (page.caption) page.caption.textContent = caption;
    if (page.img) page.img.alt = caption;
    if (page.count) {
      page.count.textContent = String(page.rows.indexOf(page.active) + 1).padStart(2, '0');
    }
  }

  function renderAllDemos() {
    demoPages.forEach(renderDemo);
  }

  function setupDemos() {
    $$('[data-demo-list]').forEach(function (list) {
      var leaf = list.closest('.leaf');
      var rows = $$('.row', list);
      if (!leaf || !rows.length) return;
      var page = {
        leaf: leaf,
        rows: rows,
        img: $('[data-demo-image]', leaf),
        caption: $('[data-demo-caption]', leaf),
        count: $('[data-demo-index]', leaf),
        active: rows[0]
      };

      function activate(row, focus) {
        if (!row) return;
        page.active = row;
        rows.forEach(function (item) {
          var on = item === row;
          item.classList.toggle('is-active', on);
          item.setAttribute('aria-pressed', String(on));
        });
        if (page.img) {
          var imgName = row.dataset.img;
          var nextSrc = imgName ? imagePath(imgName) : '';
          if (imgName) page.img.setAttribute('data-theme-img', imgName);
          if (nextSrc && page.img.getAttribute('src') !== nextSrc) {
            page.img.classList.add('is-fading');
            window.setTimeout(function () {
              page.img.src = nextSrc;
              var clear = function () { page.img.classList.remove('is-fading'); };
              page.img.onload = clear;
              window.setTimeout(clear, 260);
            }, 90);
          }
        }
        renderDemo(page);
        if (focus) row.focus();
      }

      rows.forEach(function (row) {
        row.addEventListener('click', function () { activate(row, false); });
        row.addEventListener('mouseenter', function () { activate(row, false); });
        row.addEventListener('focus', function () { activate(row, false); });
        row.addEventListener('keydown', function (event) {
          if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp' &&
              event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
          event.preventDefault();
          var at = rows.indexOf(row);
          var delta = (event.key === 'ArrowDown' || event.key === 'ArrowRight') ? 1 : -1;
          var next = rows[(at + delta + rows.length) % rows.length];
          activate(next, true);
        });
      });

      page.activate = activate;
      demoPages.push(page);
      demoByLeaf.set(leaf, page);
      activate(rows[0], false);
    });
  }

  /* ---------------------------------------------------------------- */
  /* Access tabs                                                       */
  /* ---------------------------------------------------------------- */

  function setupTabs() {
    var tabs = $$('[data-access-tab]');
    var panels = $$('[data-access-panel]');
    if (!tabs.length) return;
    panels.forEach(function (panel) { panel.tabIndex = 0; });

    function activate(index, focus) {
      tabs.forEach(function (tab, at) {
        var on = at === index;
        tab.classList.toggle('is-active', on);
        tab.setAttribute('aria-selected', String(on));
        tab.tabIndex = on ? 0 : -1;
      });
      panels.forEach(function (panel, at) {
        var on = at === index;
        panel.classList.toggle('is-active', on);
        panel.hidden = !on;
      });
      if (focus) tabs[index].focus();
    }

    tabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () { activate(index, false); });
      tab.addEventListener('keydown', function (event) {
        var forward = event.key === 'ArrowRight' || event.key === 'ArrowDown';
        var backward = event.key === 'ArrowLeft' || event.key === 'ArrowUp';
        if (!forward && !backward) return;
        event.preventDefault();
        activate((index + (forward ? 1 : -1) + tabs.length) % tabs.length, true);
      });
    });
    activate(0, false);
  }

  /* ---------------------------------------------------------------- */
  /* Lightbox                                                          */
  /* ---------------------------------------------------------------- */

  function renderLightbox() {
    var item = lightboxItems[lightboxIndex];
    if (!item) return;
    var caption = lang() === 'en' ? item.captionEn : item.captionZh;
    if (lightboxImage) {
      lightboxImage.setAttribute('data-theme-img', item.img);
      lightboxImage.src = imagePath(item.img);
      lightboxImage.alt = caption;
    }
    if (lightboxCaption) lightboxCaption.textContent = caption;
  }

  function openLightbox(button) {
    var leaf = button.closest('.leaf');
    var page = leaf ? demoByLeaf.get(leaf) : null;
    if (!page || !page.rows.length) return;
    lightboxItems = page.rows.map(function (row) {
      return {
        img: row.dataset.img,
        captionZh: row.dataset.captionZh,
        captionEn: row.dataset.captionEn
      };
    });
    lightboxIndex = Math.max(0, page.rows.indexOf(page.active));
    renderLightbox();
    if (lightbox && !lightbox.open) lightbox.showModal();
  }

  function stepLightbox(delta) {
    if (!lightboxItems.length) return;
    lightboxIndex = (lightboxIndex + delta + lightboxItems.length) % lightboxItems.length;
    renderLightbox();
  }

  $$('[data-lightbox-open]').forEach(function (button) {
    button.addEventListener('click', function () { openLightbox(button); });
  });
  var lbClose = $('[data-lightbox-close]');
  var lbPrev = $('[data-lightbox-prev]');
  var lbNext = $('[data-lightbox-next]');
  if (lbClose) lbClose.addEventListener('click', function () { lightbox.close(); });
  if (lbPrev) lbPrev.addEventListener('click', function () { stepLightbox(-1); });
  if (lbNext) lbNext.addEventListener('click', function () { stepLightbox(1); });
  if (lightbox) {
    lightbox.addEventListener('click', function (event) {
      if (event.target === lightbox || event.target.classList.contains('lightbox-inner')) {
        lightbox.close();
      }
    });
  }

  /* ---------------------------------------------------------------- */
  /* Copy                                                              */
  /* ---------------------------------------------------------------- */

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand('copy');
        resolve();
      } catch (error) {
        reject(error);
      } finally {
        area.remove();
      }
    });
  }

  $$('.copy-btn').forEach(function (button) {
    var zh = $('.zh', button);
    var en = $('.en', button);
    var originalZh = zh ? zh.textContent : '';
    var originalEn = en ? en.textContent : '';
    button.addEventListener('click', function () {
      var target = document.getElementById(button.dataset.copyTarget);
      if (!target) return;
      copyText(target.textContent.trim()).then(function () {
        button.classList.add('is-copied');
        if (zh) zh.textContent = '已复制';
        if (en) en.textContent = 'Copied';
        window.setTimeout(function () {
          button.classList.remove('is-copied');
          if (zh) zh.textContent = originalZh;
          if (en) en.textContent = originalEn;
        }, 1400);
      }).catch(function () {
        if (zh) zh.textContent = '复制失败';
        if (en) en.textContent = 'Copy failed';
        window.setTimeout(function () {
          if (zh) zh.textContent = originalZh;
          if (en) en.textContent = originalEn;
        }, 1400);
      });
    });
  });

  /* ---------------------------------------------------------------- */
  /* Links, controls, hash                                             */
  /* ---------------------------------------------------------------- */

  document.addEventListener('click', function (event) {
    var link = event.target.closest('[data-page-link]');
    if (link) {
      var id = link.dataset.goto || (link.getAttribute('href') || '').replace(/^#/, '');
      var index = leaves.findIndex(function (leaf) { return leaf.id === id; });
      if (index >= 0) {
        event.preventDefault();
        if (contents) contents.open = false;
        go(index, { focus: true });
      }
      return;
    }
    if (contents && contents.open && !contents.contains(event.target)) contents.open = false;
  });

  if (prevBtn) prevBtn.addEventListener('click', function () { go(current - 1); });
  if (nextBtn) nextBtn.addEventListener('click', function () { go(current + 1); });
  if (pageSelect) {
    pageSelect.addEventListener('change', function () {
      go(Number(pageSelect.value), { focus: true });
    });
  }
  window.addEventListener('hashchange', function () {
    var id = location.hash.slice(1);
    var index = leaves.findIndex(function (leaf) { return leaf.id === id; });
    if (index >= 0 && index !== current) go(index, { hash: false });
  });

  /* ---------------------------------------------------------------- */
  /* Keyboard, wheel, swipe                                            */
  /* ---------------------------------------------------------------- */

  function isTyping(target) {
    return target && target.closest && target.closest('input, textarea, select, [contenteditable="true"]');
  }

  function isControl(target) {
    return target && target.closest && target.closest('button, a, summary, [role="tab"], [role="tabpanel"], pre');
  }

  document.addEventListener('keydown', function (event) {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    if (lightbox && lightbox.open) {
      if (event.key === 'ArrowLeft') { event.preventDefault(); stepLightbox(-1); }
      else if (event.key === 'ArrowRight') { event.preventDefault(); stepLightbox(1); }
      return;
    }
    if (event.key === 'Escape' && contents && contents.open) {
      contents.open = false;
      return;
    }
    if (!isBook) return;
    if (isTyping(event.target)) return;

    if (current === 0 && purposeDemo && !purposeDemo.classList.contains('is-open') &&
        (event.key === 'ArrowRight' || event.key === 'PageDown')) {
      event.preventDefault();
      openCover(true);
      return;
    }
    if (isControl(event.target)) return;

    if (event.key === 'ArrowRight' || event.key === 'PageDown') {
      event.preventDefault();
      go(current + 1, { focus: true });
    } else if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
      event.preventDefault();
      go(current - 1, { focus: true });
    } else if (event.key === 'Home') {
      event.preventDefault();
      go(0, { focus: true });
    } else if (event.key === 'End') {
      event.preventDefault();
      go(leaves.length - 1, { focus: true });
    }
  });

  var wheelAccum = 0;
  var wheelLockUntil = 0;
  stage.addEventListener('wheel', function (event) {
    if (!isBook || (lightbox && lightbox.open) || (contents && contents.open)) return;
    if (event.ctrlKey) return;
    if (isTyping(event.target)) return;
    var pre = event.target.closest && event.target.closest('pre');
    if (pre && pre.scrollHeight > pre.clientHeight + 2) return;

    if (current === 0 && purposeDemo && !purposeDemo.classList.contains('is-open') && event.deltaY > 0) {
      var coverNow = performance.now();
      if (coverNow < wheelLockUntil) return;
      wheelLockUntil = coverNow + 700;
      openCover(true);
      return;
    }

    var inner = $('.leaf-inner', leaves[current]);
    if (inner && inner.scrollHeight > inner.clientHeight + 4) {
      var atTop = inner.scrollTop <= 0;
      var atBottom = inner.scrollTop + inner.clientHeight >= inner.scrollHeight - 1;
      if ((event.deltaY > 0 && !atBottom) || (event.deltaY < 0 && !atTop)) return;
    }

    var now = performance.now();
    if (now < wheelLockUntil) return;
    if (wheelAccum && Math.sign(event.deltaY) !== Math.sign(wheelAccum)) wheelAccum = 0;
    wheelAccum += event.deltaY;
    if (Math.abs(wheelAccum) < 55) return;
    var forward = wheelAccum > 0;
    wheelAccum = 0;
    wheelLockUntil = now + 900;
    go(current + (forward ? 1 : -1));
  }, { passive: true });

  var touchStart = null;
  stage.addEventListener('pointerdown', function (event) {
    if (event.pointerType !== 'touch' || !isBook) return;
    if (event.target.closest('button, a, select, summary, pre')) return;
    touchStart = { x: event.clientX, y: event.clientY };
  }, { passive: true });
  stage.addEventListener('pointerup', function (event) {
    if (!touchStart) return;
    var dx = event.clientX - touchStart.x;
    var dy = event.clientY - touchStart.y;
    touchStart = null;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      go(current + (dx < 0 ? 1 : -1));
    }
  }, { passive: true });
  stage.addEventListener('pointercancel', function () { touchStart = null; }, { passive: true });

  /* ---------------------------------------------------------------- */
  /* Skip + boot                                                       */
  /* ---------------------------------------------------------------- */

  var skipLink = $('.skip');
  if (skipLink) {
    skipLink.addEventListener('click', function (event) {
      event.preventDefault();
      var leaf = leaves[current];
      if (!isBook) leaf.scrollIntoView({ behavior: motionPaused ? 'auto' : 'smooth', block: 'start' });
      leaf.focus({ preventScroll: true });
    });
  }

  var initialHash = location.hash.slice(1);
  var initialIndex = leaves.findIndex(function (leaf) { return leaf.id === initialHash; });
  if (initialIndex >= 0) current = initialIndex;

  body.classList.add('is-book');
  leaves.forEach(function (leaf, index) { setLeafState(leaf, index === current); });
  setupDemos();
  setupTabs();
  syncLanguage();
  updateNav();
  root.classList.remove('book-early');
})();
