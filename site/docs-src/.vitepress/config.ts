import { defineConfig } from 'vitepress';

// 中文为主，提供简要英文骨架。构建输出到 site/docs。
// 本地预览用 DOCS_BASE=/docs/；GitHub Project Pages 默认 /LiberAstra/docs/。
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
          '/': [
            {
              text: '介绍',
              items: [
                { text: '项目目的与非目标', link: '/' },
                { text: '快速开始', link: '/quickstart' }
              ]
            },
            {
              text: '安装与部署',
              items: [
                { text: '安装 / 下载', link: '/install' }
              ]
            },
            {
              text: '指南',
              items: [
                { text: '图像', link: '/guides/image' },
                { text: '视频', link: '/guides/video' },
                { text: '语音', link: '/guides/speech' },
                { text: '作品与任务', link: '/guides/works' }
              ]
            },
            {
              text: '集成',
              items: [
                { text: 'CLI', link: '/integration/cli' },
                { text: 'API', link: '/integration/api' },
                { text: 'MCP', link: '/integration/mcp' }
              ]
            },
            {
              text: '服务提供方',
              items: [{ text: 'Providers', link: '/providers' }]
            },
            {
              text: '关于',
              items: [{ text: 'MIT / 安全 / FAQ', link: '/about' }]
            }
          ]
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
          '/en/': [
            {
              text: 'Introduction',
              items: [
                { text: 'Purpose and non-goals', link: '/en/' },
                { text: 'Quick start', link: '/en/quickstart' }
              ]
            },
            {
              text: 'Install & Deploy',
              items: [{ text: 'Install / Download', link: '/en/install' }]
            },
            {
              text: 'Guides',
              items: [
                { text: 'Image', link: '/en/guides/image' },
                { text: 'Video', link: '/en/guides/video' },
                { text: 'Speech', link: '/en/guides/speech' },
                { text: 'Works & Tasks', link: '/en/guides/works' }
              ]
            },
            {
              text: 'Integration',
              items: [
                { text: 'CLI', link: '/en/integration/cli' },
                { text: 'API', link: '/en/integration/api' },
                { text: 'MCP', link: '/en/integration/mcp' }
              ]
            },
            {
              text: 'Providers',
              items: [{ text: 'Providers', link: '/en/providers' }]
            },
            {
              text: 'About',
              items: [{ text: 'MIT / Security / FAQ', link: '/en/about' }]
            }
          ]
        },
        socialLinks: [
          { icon: 'github', link: 'https://github.com/liberalchang/LiberAstra' }
        ]
      }
    }
  }
});
