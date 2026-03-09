"use client";

import { useSession, signIn, signOut } from "next-auth/react";
import Link from "next/link";

export function Navbar() {
  const { data: session, status } = useSession();

  return (
    <nav className="bg-goac-dark text-white px-6 py-3 flex items-center justify-between">
      <Link href="/dashboard" className="text-xl font-bold tracking-tight">
        GOAC Asset Meeting Manager
      </Link>
      <div className="flex items-center gap-4">
        {status === "authenticated" && session?.user ? (
          <>
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
