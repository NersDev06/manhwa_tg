import { authorized } from "@/lib/auth";
import Control from "./control";
export const dynamic = "force-dynamic";
export default async function Page() {
  return <Control initialAuth={await authorized()} />;
}
