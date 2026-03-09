"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { StoreCard } from "@/components/StoreCard";
import { SummaryBar } from "@/components/SummaryBar";
import { FlagSummaryChart } from "@/components/FlagSummaryChart";
import { fetchDashboard, type DashboardData } from "@/lib/api";

export default function DashboardPage() {
  const { data: session } = useSession();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = (session as any)?.backendToken;
    fetchDashboard(token)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [session]);

  return (
    <>
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">Corporate Dashboard</h1>

        {loading && <p className="text-gray-500">Loading dashboard...</p>}
        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">
            {error}
          </div>
        )}

        {data && (
          <>
            <SummaryBar totals={data.totals} />

            <div className="grid md:grid-cols-2 gap-6 mb-6">
              <FlagSummaryChart stores={data.stores} />
            </div>

            <h2 className="text-lg font-semibold mb-4">Stores</h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.stores.map((store) => (
                <StoreCard key={store.id} store={store} />
              ))}
            </div>

            {data.stores.length === 0 && (
              <p className="text-gray-500">No stores found.</p>
            )}
          </>
        )}
      </main>
    </>
  );
}
