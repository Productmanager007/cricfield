import type { Metadata } from "next";
import { ProvenanceView } from "@/components/Provenance";

export const metadata: Metadata = { title: "Provenance" };

export default function ProvenancePage() {
  return <ProvenanceView />;
}
