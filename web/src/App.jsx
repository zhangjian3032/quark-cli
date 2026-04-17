import { Routes, Route, NavLink } from 'react-router-dom'
import { Film, Search, Star, Clapperboard, Activity, HardDrive, Globe, Settings } from 'lucide-react'
import LibraryPage from './pages/LibraryPage'
import SearchPage from './pages/SearchPage'
import DetailPage from './pages/DetailPage'
import DiscoverPage from './pages/DiscoverPage'
import MetaPage from './pages/MetaPage'
import DrivePage from './pages/DrivePage'
import ResourceSearchPage from './pages/ResourceSearchPage'
import ConfigPage from './pages/ConfigPage'
import TmdbDetailPage from './pages/TmdbDetailPage'

const NAV_SECTIONS = [
  {
    title: '网盘',
    items: [
      { to: '/drive',           icon: HardDrive,    label: '文件管理' },
      { to: '/resource-search', icon: Globe,         label: '搜索转存' },
      { to: '/config',          icon: Settings,      label: '配置' },
    ],
  },
  {
    title: '影视中心',
    items: [
      { to: '/',         icon: Film,         label: '媒体库' },
      { to: '/search',   icon: Search,       label: '搜索' },
      { to: '/discover', icon: Star,         label: '发现' },
      { to: '/meta',     icon: Clapperboard, label: '元数据' },
    ],
  },
]

function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[220px] bg-surface-1 border-r border-surface-3
                       flex flex-col z-30">
      {/* Logo */}
      <div className="h-16 flex items-center gap-3 px-5 border-b border-surface-3">
        <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center font-bold text-sm">
          Q
        </div>
        <div>
          <div className="font-semibold text-sm text-white">Quark CLI</div>
          <div className="text-[10px] text-gray-500">Dashboard</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 overflow-y-auto">
        {NAV_SECTIONS.map(section => (
          <div key={section.title} className="mb-4">
            <div className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
              {section.title}
            </div>
            <div className="space-y-0.5">
              {section.items.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
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
      <div className="px-5 py-3 border-t border-surface-3">
        <div className="flex items-center gap-2 text-[10px] text-gray-600">
          <Activity size={12} />
          <span>v2.3.0</span>
        </div>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 ml-[220px]">
        <div className="max-w-7xl mx-auto p-6">
          <Routes>
            <Route path="/" element={<LibraryPage />} />
            <Route path="/library/:libId" element={<LibraryPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/detail/:guid" element={<DetailPage />} />
            <Route path="/discover" element={<DiscoverPage />} />
            <Route path="/discover/:tmdbId" element={<TmdbDetailPage />} />
            <Route path="/meta" element={<MetaPage />} />
            <Route path="/drive" element={<DrivePage />} />
            <Route path="/resource-search" element={<ResourceSearchPage />} />
            <Route path="/config" element={<ConfigPage />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
