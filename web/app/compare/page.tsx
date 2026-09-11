import type { Metadata } from "next";
import { Compare } from "@/components/Compare";

export const metadata: Metadata = { title: "Compare" };

export default function ComparePage() {
  return <Compare />;
}
