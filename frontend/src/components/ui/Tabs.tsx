"use client";

import { useState, useCallback } from "react";

export interface TabItem {
  key: string;
  label: string;
  count?: number;
}

interface TabsProps {
  tabs: TabItem[];
  defaultTab?: string;
  onTabChange?: (key: string) => void;
  children: (activeTab: string) => React.ReactNode;
}

export function Tabs({ tabs, defaultTab, onTabChange, children }: TabsProps) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.key || "");

  const handleClick = useCallback(
    (key: string) => {
      setActive(key);
      onTabChange?.(key);
    },
    [onTabChange]
  );

  return (
    <div>
      <div className="border-b border-gray-200 mb-4">
        <nav className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => handleClick(tab.key)}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                active === tab.key
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
              {tab.count != null && (
                <span className="ml-1.5 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>
      {children(active)}
    </div>
  );
}
