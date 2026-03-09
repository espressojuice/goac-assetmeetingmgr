"use client";

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { FlagTrendMeeting } from "@/lib/api";

function formatDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function FlagTrendChart({ data }: { data: FlagTrendMeeting[] }) {
  const chartData = data.map((d) => ({
    ...d,
    label: formatDate(d.date),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} />
        <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
        <YAxis
          yAxisId="right"
          orientation="right"
          domain={[0, 100]}
          tick={{ fontSize: 12 }}
          tickFormatter={(v: number) => `${v}%`}
        />
        <Tooltip
          formatter={(value: number, name: string) => {
            if (name === "Response Rate") return [`${value}%`, name];
            return [value, name];
          }}
        />
        <Legend />
        <Bar
          yAxisId="left"
          dataKey="red"
          name="Red Flags"
          stackId="flags"
          fill="#dc2626"
          radius={[0, 0, 0, 0]}
        />
        <Bar
          yAxisId="left"
          dataKey="yellow"
          name="Yellow Flags"
          stackId="flags"
          fill="#f59e0b"
          radius={[2, 2, 0, 0]}
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="response_rate"
          name="Response Rate"
          stroke="#16a34a"
          strokeWidth={2}
          dot={{ fill: "#16a34a", r: 4 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
