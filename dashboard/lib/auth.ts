import { cookies } from "next/headers";
import { createHmac, timingSafeEqual } from "node:crypto";
export function equal(a: string, b: string) {
  const x = Buffer.from(a),
    y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}
function sign(exp: string) {
  const secret = process.env.DASHBOARD_SECRET;
  if (!secret) throw Error("Authentication not configured");
  return createHmac("sha256", secret).update(exp).digest("hex");
}
export function token() {
  const exp = String(Date.now() + 7 * 86400000);
  return exp + "." + sign(exp);
}
export async function authorized() {
  const value = (await cookies()).get("manhwa_session")?.value;
  if (!value) return false;
  const [exp, sig] = value.split(".");
  return (
    /^\d+$/.test(exp) &&
    Number(exp) > Date.now() &&
    !!sig &&
    equal(sign(exp), sig)
  );
}
export function sameOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const parsed = new URL(origin);
    return (
      parsed.host === request.headers.get("host") &&
      (parsed.protocol === "https:" ||
        process.env.NODE_ENV !== "production" ||
        parsed.hostname === "127.0.0.1" ||
        parsed.hostname === "localhost")
    );
  } catch {
    return false;
  }
}
