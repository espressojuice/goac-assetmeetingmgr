"use client";

import { useSession, signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function HomePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") {
      router.push("/dashboard");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-goac-dark">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-white mb-2">
          GOAC Asset Meeting Manager
        </h1>
        <p className="text-gray-400 mb-8">
          Corporate asset review &amp; accountability dashboard
        </p>
        <button
          onClick={() => signIn("google")}
          className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg text-lg font-medium transition-colors"
        >
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
