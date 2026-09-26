import { Award, Boxes, ClipboardCheck, GraduationCap, LayoutDashboard, LogOut, Menu, PieChart, Settings, Sparkles, TrendingUp, UserRound, Users, X } from 'lucide-react'
import type { Role } from '../lib/api'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'

type NavItem = { to: string; label: string; icon: typeof Award; end?: boolean }
type NavSection = { title?: string; roles?: Role[]; items: NavItem[] }

const SECTIONS: NavSection[] = [
  {
    items: [
      { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/app/growth', label: 'Growth', icon: TrendingUp },
      { to: '/app/activities', label: 'Activities', icon: Award },
      { to: '/app/academics', label: 'Academics', icon: GraduationCap },
      { to: '/app/skills', label: 'Skills & Interests', icon: Sparkles },
      { to: '/app/profile', label: 'Profile', icon: UserRound },
    ],
  },
  {
    title: 'Educator',
    roles: ['educator', 'admin'],
    items: [
      { to: '/app/educator/queue', label: 'Review queue', icon: ClipboardCheck },
      { to: '/app/educator/learners', label: 'Learners', icon: Users },
      { to: '/app/educator/cohort', label: 'Cohort analytics', icon: PieChart },
      { to: '/app/educator/groups', label: 'Learner groups', icon: Boxes },
    ],
  },
  { title: 'Admin', roles: ['admin'], items: [{ to: '/app/admin', label: 'Administration', icon: Settings }] },
]

export function Layout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)

  const sections = SECTIONS.filter((s) => !s.roles || (user && s.roles.includes(user.role)))
  const nav = (
    <nav className="flex flex-col gap-1">
      {sections.map((section, i) => (
        <div key={i} className={`flex flex-col gap-1 ${i ? 'mt-4' : ''}`}>
          {section.title && <div className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{section.title}</div>}
          {section.items.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'
                }`
              }
            >
              <Icon className="size-4" /> {label}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  )

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            <button className="rounded p-1 md:hidden" onClick={() => setOpen(!open)} aria-label="Menu">
              {open ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
            <span className="font-semibold">Competency Evolution</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium">{user?.name}</div>
              <div className="text-xs capitalize text-slate-500">{user?.role}</div>
            </div>
            <button
              onClick={logout}
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
            >
              <LogOut className="size-4" /> <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
        {open && <div className="border-t border-slate-200 p-3 md:hidden">{nav}</div>}
      </header>

      <div className="mx-auto flex max-w-6xl gap-8 px-4 py-6">
        <aside className="hidden w-52 shrink-0 md:block">{nav}</aside>
        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
