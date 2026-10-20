export type Chapter = {
  number: string;
  volume: number;
  urls: string[];
  at: string | null;
};
export type Book = {
  slug: string;
  title: string;
  english: string;
  aliases: string[];
  channel: string;
  cover: string;
  coverWidth: number;
  coverHeight: number;
  genres: string[];
  tone: string;
  description: string;
  about: string;
  reference: string;
  chapters: Chapter[];
  checkedAt: string | null;
};
export type BookSummary = Omit<Book, "chapters"> & {
  count: number;
  latest: string | null;
  latestAt: string | null;
};
