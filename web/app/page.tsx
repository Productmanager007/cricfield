import type { Metadata } from "next";
import { Leaderboard } from "@/components/Leaderboard";

export const metadata: Metadata = { title: "Fielding leaderboard" };

export default function LeaderboardPage() {
  return <Leaderboard />;
}
