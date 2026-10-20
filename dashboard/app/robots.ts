import type { MetadataRoute } from "next";
import { SITE } from "@/lib/library";
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/catalog",
      disallow: ["/api/", "/_next/webpack-hmr"],
    },
    sitemap: SITE + "/sitemap.xml",
  };
}
