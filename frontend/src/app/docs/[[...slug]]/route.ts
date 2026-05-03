import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";

const MIME: Record<string, string> = {
  html: "text/html; charset=utf-8",
  css: "text/css",
  js: "application/javascript",
  json: "application/json",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  svg: "image/svg+xml",
  ico: "image/x-icon",
  woff2: "font/woff2",
  woff: "font/woff",
  ttf: "font/ttf",
  eot: "application/vnd.ms-fontobject",
  txt: "text/plain",
  xml: "application/xml",
  webmanifest: "application/manifest+json",
};

export async function GET(
  req: Request,
  { params }: { params: Promise<{ slug?: string[] }> }
) {
  const { slug } = await params;
  const parts = slug ?? [];

  // Build the file path under public/docs/
  let filePath = path.join(process.cwd(), "public", "docs", ...parts);

  // No extension → directory request, serve index.html.
  // Redirect to trailing-slash URL first so relative CSS/JS paths resolve correctly.
  const last = parts[parts.length - 1] ?? "";
  const isDirectory = !last.includes(".");
  if (isDirectory) {
    filePath = path.join(filePath, "index.html");
  }

  try {
    const content = await readFile(filePath);
    const ext = filePath.split(".").pop() ?? "";
    const contentType = MIME[ext] ?? "application/octet-stream";

    // For HTML pages, rewrite ALL relative href/src values to absolute /docs/...
    // paths so links and assets resolve correctly whether or not the URL has a
    // trailing slash (Next.js strips trailing slashes before the handler runs).
    if (isDirectory) {
      const docsBase =
        "https://x/docs/" +
        (parts.length > 0 ? parts.join("/") + "/" : "");

      const html = content
        .toString("utf8")
        .replace(/(href|src)="([^"]+)"/g, (match, attr, value) => {
          // Leave absolute URLs, anchors, and protocol URLs untouched
          if (
            value.startsWith("/") ||
            value.startsWith("#") ||
            value.includes(":")
          ) {
            return match;
          }
          try {
            const resolved = new URL(value, docsBase).pathname;
            return `${attr}="${resolved}"`;
          } catch {
            return match;
          }
        });

      return new NextResponse(html, {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    return new NextResponse(content, {
      headers: { "Content-Type": contentType },
    });
  } catch {
    return new NextResponse("Page not found", { status: 404 });
  }
}
