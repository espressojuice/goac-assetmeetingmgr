"use client";

import { useSession, signIn, signOut } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NotificationBell } from "./NotificationBell";

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href || pathname?.startsWith(href + "/");
  return (
    <Link
      href={href}
      className={`text-sm px-3 py-1 rounded ${
        active ? "bg-gray-700 text-white" : "text-gray-300 hover:text-white hover:bg-gray-700"
      }`}
    >
      {children}
    </Link>
  );
}

export function Navbar() {
  const { data: session, status } = useSession();
  const role = (session as any)?.role;

  return (
    <nav className="bg-goac-dark text-white px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link href="/dashboard" className="text-xl font-bold tracking-tight">
          GOAC Asset Meeting Manager
        </Link>
        {status === "authenticated" && (
          <div className="hidden sm:flex items-center gap-1">
            <NavLink href="/dashboard">Dashboard</NavLink>
            <NavLink href="/flags">My Flags</NavLink>
          </div>
        )}
      </div>
      <div className="flex items-center gap-4">
        {status === "authenticated" && session?.user ? (
          <>
            <NotificationBell />
            {role && (
              <span className="text-xs text-gray-400 uppercase">{role}</span>
            )}
            <span className="text-sm text-gray-300">
              {session.user.name}
            </span>
            {session.user.image && (
              <img
                src={session.user.image}
                alt=""
                className="w-8 h-8 rounded-full"
              />
            )}
            <button
              onClick={() => signOut()}
              className="text-sm bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded"
            >
              Sign Out
            </button>
          </>
        ) : (
          <button
            onClick={() => signIn("google")}
            className="text-sm bg-blue-600 hover:bg-blue-500 px-4 py-1.5 rounded"
          >
            Sign in with Google
          </button>
        )}
      </div>
    </nav>
  );
}
