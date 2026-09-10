import type { Metadata } from "next";
import { PlayerView } from "@/components/PlayerView";
import { readSeasonIndex } from "@/lib/season-index";

type Props = { params: Promise<{ slug: string }> };

// One static page per exported player. Any other slug is a 404.
export const dynamicParams = false;

export function generateStaticParams() {
  return Object.values(readSeasonIndex()).map((slug) => ({ slug }));
}

function fielderFor(slug: string): string {
  const entry = Object.entries(readSeasonIndex()).find(([, s]) => s === slug);
  if (!entry) throw new Error(`No player with slug ${slug} in public/data/seasons/index.json`);
  return entry[0];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  return { title: fielderFor(slug) };
}

export default async function PlayerPage({ params }: Props) {
  const { slug } = await params;
  return <PlayerView slug={slug} fielder={fielderFor(slug)} />;
}
