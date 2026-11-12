import { defineConfig } from 'vitepress';

import nav from '../nav.json';

// 中文为主，提供简要英文骨架。构建输出到 site/docs。
// GitHub Project Pages 默认 /LiberAstra/docs/。
// 嵌入 LiberAstra 应用时用 DOCS_BASE=/manual/（见 frontend/scripts/embed-manual.mjs）。
const navData = nav as {
  zh: { sections: { title: string; items: { title: string; slug: string }[] }[] };
  en: { sections: { title: string; items: { title: string; slug: string }[] }[] };
};

/** 侧栏与 nav.json 共用一份；slug=index 指向该语言的根路径。 */
function sidebarFor(locale: (typeof navData)['zh'], prefix = '') {
  return locale.sections.map((section) => ({
    text: section.title,
    items: section.items.map((item) => ({
      text: item.title,
      link: item.slug === 'index' ? `${prefix}/` : `${prefix}/${item.slug}`,
    })),
  }));
}

export default defineConfig({
  title: 'LiberAstra',
  description:
    'LiberAstra 编排台：自托管 AIGC 编排，对接 ComfyUI、Ollama 与 OpenAI 兼容 API。只编排，不推理。',
  // GitHub Project Pages 位于 /LiberAstra/ 前缀下
  base: process.env.DOCS_BASE || '/LiberAstra/docs/',
  cleanUrls: true,
  // 从 docs-src 根目录出发，输出到上级的 site/docs
  outDir: '../docs',
  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      themeConfig: {
        nav: [
          { text: '快速开始', link: '/' },
          { text: '安装', link: '/install' },
          { text: '指南', link: '/guides/image' },
          { text: '集成', link: '/integration/cli' },
          { text: '关于', link: '/about' }
        ],
        sidebar: {
          '/': sidebarFor(navData.zh)
        },
        socialLinks: [
          { icon: 'github', link: 'https://github.com/liberalchang/LiberAstra' }
        ]
      }
    },
    en: {
      label: 'English',
      lang: 'en',
      link: '/en/',
      themeConfig: {
        nav: [
          { text: 'Intro', link: '/en/' },
          { text: 'Install', link: '/en/install' },
          { text: 'Guides', link: '/en/guides/image' },
          { text: 'Integrations', link: '/en/integration/cli' },
          { text: 'About', link: '/en/about' }
        ],
        sidebar: {
          '/en/': sidebarFor(navData.en, '/en')
        },
        socialLinks: [
          { icon: 'github', link: 'https://github.com/liberalchang/LiberAstra' }
        ]
      }
    }
  }
});
