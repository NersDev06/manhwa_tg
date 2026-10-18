import { MongoClient } from "mongodb";
let client: MongoClient | undefined;
export async function db() {
  const uri = process.env.MONGODB_URI;
  if (!uri) throw Error("Database not configured");
  client ??= new MongoClient(uri, {
    maxPoolSize: 3,
    serverSelectionTimeoutMS: 10000,
  });
  await client.connect();
  return client.db(process.env.MONGODB_DATABASE || "manhwa_telegram");
}
