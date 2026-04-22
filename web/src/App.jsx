import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { Film, Star, Clapperboard, Activity, HardDrive, Globe, Settings, CalendarClock, FolderSync, LayoutDashboard, History, Menu, X, Tv, Rss, Download, Cloud } from 'lucide-react'
import DashboardPage from './pages/DashboardPage'
import HistoryPage from './pages/HistoryPage'
import LibraryPage from './pages/LibraryPage'
import DetailPage from './pages/DetailPage'
import DiscoverPage from './pages/DiscoverPage'
import MetaPage from './pages/MetaPage'
import DrivePage from './pages/DrivePage'
import ResourceSearchPage from './pages/ResourceSearchPage'
import ConfigPage from './pages/ConfigPage'
import TmdbDetailPage from './pages/TmdbDetailPage'
import PersonDetailPage from './pages/PersonDetailPage'
import SchedulerPage from './pages/SchedulerPage'
import SyncPage from './pages/SyncPage'
import SubscriptionPage from './pages/SubscriptionPage'
import RssPage from './pages/RssPage'
import TorrentPage from './pages/TorrentPage'
import GuangyaPage from './pages/GuangyaPage'

const NAV_SECTIONS = [
  {
    title: '总览',
    items: [
      { to: '/',         icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/history',  icon: History,          label: '执行历史' },
    ],
  },
  {
    title: '网盘',
    items: [
      { to: '/drive',           icon: HardDrive,    label: '夸克网盘' },
      { to: '/guangya',        icon: Cloud,          label: '光鸭云盘' },
      { to: '/resource-search', icon: Globe,         label: '搜索转存' },
      { to: '/config',          icon: Settings,      label: '配置' },
    ],
  },
  {
    title: '影视中心',
    items: [
      { to: '/library',  icon: Film,         label: '媒体库' },
      { to: '/discover', icon: Star,         label: '发现' },
      { to: '/meta',     icon: Clapperboard, label: '元数据' },
    ],
  },
  {
    title: '自动化',
    items: [
      { to: '/scheduler',     icon: CalendarClock, label: '定时任务' },
      { to: '/subscriptions', icon: Tv,            label: '订阅追剧' },
      { to: '/rss',           icon: Rss,           label: 'RSS 订阅' },
      { to: '/torrent',       icon: Download,      label: 'qBittorrent' },
      { to: '/sync',          icon: FolderSync,    label: '文件同步' },
    ],
  },
]

function Sidebar({ open, onClose }) {
  const location = useLocation()

  // 路由变化时自动关闭移动端菜单
  useEffect(() => {
    onClose()
  }, [location.pathname]) // eslint-disable-line

  return (
    <>
      {/* 移动端遮罩 */}
      {open && (
        <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={onClose} />
      )}

      <aside className={`
        fixed left-0 top-0 bottom-0 w-[220px] bg-surface-1 border-r border-surface-3
        flex flex-col z-50
        transition-transform duration-200 ease-in-out
        ${open ? 'translate-x-0' : '-translate-x-full'}
        lg:translate-x-0
      `}>
        {/* Logo + 移动端关闭按钮 */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-surface-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center font-bold text-sm">
              Q
            </div>
            <div>
              <div className="font-semibold text-sm text-white">Quark CLI</div>
              <div className="text-[10px] text-gray-500">Dashboard</div>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-surface-3 lg:hidden">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-3 px-2.5 overflow-y-auto">
          {NAV_SECTIONS.map(section => (
            <div key={section.title} className="mb-3">
              <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
                {section.title}
              </div>
              <div className="space-y-0.5">
                {section.items.map(({ to, icon: Icon, label }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                      ${isActive
                        ? 'bg-brand-600/15 text-brand-400'
                        : 'text-gray-400 hover:text-white hover:bg-surface-2'
                      }`
                    }
                  >
                    <Icon size={18} />
                    {label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-2.5 border-t border-surface-3">
          <div className="flex items-center gap-2 text-[10px] text-gray-600">
            <Activity size={12} />
            <span>v2.4.0</span>
          </div>
        </div>
      </aside>
    </>
  )
}

/* 移动端顶栏 */
function MobileHeader({ onMenuToggle }) {
  return (
    <header className="fixed top-0 left-0 right-0 h-14 bg-surface-1 border-b border-surface-3
                        flex items-center px-4 z-30 lg:hidden">
      <button onClick={onMenuToggle} className="p-2 -ml-2 rounded-lg hover:bg-surface-2 transition">
        <Menu className="w-5 h-5" />
      </button>
      <div className="flex items-center gap-2 ml-3">
        <div className="w-6 h-6 bg-brand-600 rounded flex items-center justify-center font-bold text-[10px]">Q</div>
        <span className="font-semibold text-sm">Quark CLI</span>
      </div>
    </header>
  )
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <MobileHeader onMenuToggle={() => setSidebarOpen(o => !o)} />

      {/* 主内容区: lg 以上有侧边栏偏移, 移动端有顶栏偏移 */}
      <main className="flex-1 lg:ml-[220px] pt-14 lg:pt-0">
        <div className="max-w-7xl mx-auto p-4 sm:p-6">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/library/:libId" element={<LibraryPage />} />
            <Route path="/detail/:guid" element={<DetailPage />} />
            <Route path="/discover" element={<DiscoverPage />} />
            <Route path="/discover/person/:personId" element={<PersonDetailPage />} />
            <Route path="/discover/:tmdbId" element={<TmdbDetailPage />} />
            <Route path="/meta" element={<MetaPage />} />
            <Route path="/drive" element={<DrivePage />} />
            <Route path="/resource-search" element={<ResourceSearchPage />} />
            <Route path="/scheduler" element={<SchedulerPage />} />
            <Route path="/subscriptions" element={<SubscriptionPage />} />
            <Route path="/rss" element={<RssPage />} />
            <Route path="/torrent" element={<TorrentPage />} />
            <Route path="/guangya" element={<GuangyaPage />} />
            <Route path="/sync" element={<SyncPage />} />
            <Route path="/config" element={<ConfigPage />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
