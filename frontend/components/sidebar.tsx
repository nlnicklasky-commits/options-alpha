"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Search,
  BarChart3,
  BookOpen,
  Menu,
  X,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/scanner", label: "Scanner", icon: Search },
  { href: "/backtest", label: "Backtest", icon: BarChart3 },
  { href: "/journal", label: "Journal", icon: BookOpen },
];

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const navContent = (
    <>
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-lg font-bold tracking-tight text-zinc-100">
          Options Alpha
        </h1>
        <button
          className="md:hidden text-zinc-400 hover:text-zinc-100"
          onClick={() => setOpen(false)}
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </>
  );

  return (
    <>
      {/* Mobile toggle */}
      <button
        className="fixed top-4 left-4 z-50 md:hidden rounded-md bg-zinc-900 p-2 text-zinc-400 hover:text-zinc-100 border border-zinc-800"
        onClick={() => setOpen(true)}
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-56 border-r border-zinc-800 bg-zinc-900 p-4 transition-transform md:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {navContent}
      </aside>

      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-56 flex-col border-r border-zinc-800 bg-zinc-900 p-4">
        {navContent}
      </aside>
    </>
  );
}
