import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import './custom.css'

const base = import.meta.env.BASE_URL || '/'
// Pages：/LiberAstra/docs/ → 站点首页 /LiberAstra/
// 应用内：/manual/ → LiberAstra 根路径 /
const homeHref = /\/docs\/$/.test(base) ? base.replace(/docs\/$/, '') || '/' : '/'

function goHome(event: MouseEvent) {
  event.preventDefault()
  event.stopPropagation()
  window.location.assign(homeHref)
}

function homeLink(className: string) {
  return h('a', {
    class: className,
    href: homeHref,
    'aria-label': '返回主页 / Back to home',
    onClick: goHome
  }, [
    h('span', { class: 'doc-home-arrow', 'aria-hidden': 'true' }, '←'),
    h('span', null, '返回主页 / Home')
  ])
}

function HomeLink() {
  return homeLink('doc-home-link')
}

function ScreenHomeLink() {
  return homeLink('doc-home-link doc-home-link--screen')
}

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'nav-bar-content-before': HomeLink,
      'nav-screen-content-before': ScreenHomeLink
    })
  }
}
