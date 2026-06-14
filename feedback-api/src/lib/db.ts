import Database from "better-sqlite3";
import path from "path";
import fs from "fs";

// ── Types ──────────────────────────────────────────────────────────
export interface Feedback {
  id: string;
  text: string;
  rating: number;
  category: string;
  author: string;
  created_at: string;
  tags: string[];
}

export interface FeedbackQuery {
  category?: string;
  rating?: string;
  minRating?: string;
  maxRating?: string;
  tag?: string;
  author?: string;
  sort?: "newest" | "oldest" | "rating-asc" | "rating-desc";
  limit?: string;
  offset?: string;
}

export interface FeedbackSummary {
  totalCount: number;
  averageRating: number;
  ratingDistribution: Record<string, number>;
  categoryCounts: Record<string, number>;
  topTags: { tag: string; count: number }[];
  recentCount7d: number;
}

// ── Database initialization ────────────────────────────────────────
const DB_PATH = path.join(process.cwd(), "data", "feedback.db");

// Ensure data directory exists
const dataDir = path.dirname(DB_PATH);
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const db = new Database(DB_PATH);

// Enable WAL mode for better concurrent read performance
db.pragma("journal_mode = WAL");
db.pragma("foreign_keys = ON");

// Create table if it doesn't exist
db.exec(`
  CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    category TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tags TEXT NOT NULL
  )
`);

// Seed from JSON if the table is empty
const countRow = db.prepare("SELECT COUNT(*) as count FROM feedback").get() as {
  count: number;
};
if (countRow.count === 0) {
  const seedPath = path.join(process.cwd(), "data", "feedback.json");
  if (fs.existsSync(seedPath)) {
    const seedData: Feedback[] = JSON.parse(fs.readFileSync(seedPath, "utf-8"));
    const insert = db.prepare(
      "INSERT OR IGNORE INTO feedback (id, text, rating, category, author, created_at, tags) VALUES (?, ?, ?, ?, ?, ?, ?)"
    );
    const insertMany = db.transaction((items: Feedback[]) => {
      for (const item of items) {
        insert.run(
          item.id,
          item.text,
          item.rating,
          item.category,
          item.author,
          item.created_at,
          JSON.stringify(item.tags)
        );
      }
    });
    insertMany(seedData);
  }
}

// ── Helpers ────────────────────────────────────────────────────────
function rowToFeedback(row: Record<string, unknown>): Feedback {
  return {
    id: row.id as string,
    text: row.text as string,
    rating: row.rating as number,
    category: row.category as string,
    author: row.author as string,
    created_at: row.created_at as string,
    tags: JSON.parse(row.tags as string),
  };
}

function generateId(): string {
  return `fb-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
}

// ── Prepared statements ────────────────────────────────────────────
const stmtGetById = db.prepare("SELECT * FROM feedback WHERE id = ?");

const stmtInsert = db.prepare(
  "INSERT INTO feedback (id, text, rating, category, author, created_at, tags) VALUES (?, ?, ?, ?, ?, ?, ?)"
);

const stmtDelete = db.prepare("DELETE FROM feedback WHERE id = ?");

const stmtCountAll = db.prepare("SELECT COUNT(*) as count FROM feedback");

const stmtAvgRating = db.prepare(
  "SELECT AVG(rating) as avg FROM feedback"
);

const stmtRatingDist = db.prepare(
  "SELECT rating, COUNT(*) as count FROM feedback GROUP BY rating ORDER BY rating"
);

const stmtCategoryCounts = db.prepare(
  "SELECT category, COUNT(*) as count FROM feedback GROUP BY category ORDER BY count DESC"
);

const stmtAllTags = db.prepare("SELECT tags FROM feedback");

const stmtRecent7d = db.prepare(
  "SELECT COUNT(*) as count FROM feedback WHERE created_at >= ?"
);

// ── Exports ────────────────────────────────────────────────────────

export function getAll(
  query: FeedbackQuery
): { items: Feedback[]; total: number } {
  const conditions: string[] = [];
  const params: unknown[] = [];

  if (query.category) {
    conditions.push("category = ?");
    params.push(query.category);
  }

  if (query.rating) {
    conditions.push("rating = ?");
    params.push(Number(query.rating));
  }

  if (query.minRating) {
    conditions.push("rating >= ?");
    params.push(Number(query.minRating));
  }

  if (query.maxRating) {
    conditions.push("rating <= ?");
    params.push(Number(query.maxRating));
  }

  if (query.author) {
    conditions.push("author = ?");
    params.push(query.author);
  }

  if (query.tag) {
    // Search within the JSON array stored as text
    conditions.push("tags LIKE ?");
    params.push(`%"${query.tag}"%`);
  }

  const whereClause =
    conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

  // Determine sort order
  let orderClause = "ORDER BY created_at DESC"; // default: newest
  switch (query.sort) {
    case "oldest":
      orderClause = "ORDER BY created_at ASC";
      break;
    case "rating-asc":
      orderClause = "ORDER BY rating ASC, created_at DESC";
      break;
    case "rating-desc":
      orderClause = "ORDER BY rating DESC, created_at DESC";
      break;
    case "newest":
    default:
      orderClause = "ORDER BY created_at DESC";
      break;
  }

  // Get total count for pagination
  const countSql = `SELECT COUNT(*) as count FROM feedback ${whereClause}`;
  const totalRow = db.prepare(countSql).get(...params) as { count: number };
  const total = totalRow.count;

  // Pagination
  const limit = query.limit ? Number(query.limit) : 20;
  const offset = query.offset ? Number(query.offset) : 0;

  const dataSql = `SELECT * FROM feedback ${whereClause} ${orderClause} LIMIT ? OFFSET ?`;
  const rows = db
    .prepare(dataSql)
    .all(...params, limit, offset) as Record<string, unknown>[];

  return {
    items: rows.map(rowToFeedback),
    total,
  };
}

export function getById(id: string): Feedback | undefined {
  const row = stmtGetById.get(id) as Record<string, unknown> | undefined;
  return row ? rowToFeedback(row) : undefined;
}

export function create(
  data: Omit<Feedback, "id" | "created_at">
): Feedback {
  const id = generateId();
  const created_at = new Date().toISOString();
  const tagsStr = JSON.stringify(data.tags);

  stmtInsert.run(
    id,
    data.text,
    data.rating,
    data.category,
    data.author,
    created_at,
    tagsStr
  );

  return {
    id,
    text: data.text,
    rating: data.rating,
    category: data.category,
    author: data.author,
    created_at,
    tags: data.tags,
  };
}

export function update(
  id: string,
  data: Partial<Omit<Feedback, "id" | "created_at">>
): Feedback | undefined {
  const existing = getById(id);
  if (!existing) return undefined;

  const updated = { ...existing, ...data };
  if (data.tags !== undefined) {
    updated.tags = data.tags;
  }

  const stmt = db.prepare(
    "UPDATE feedback SET text = ?, rating = ?, category = ?, author = ?, tags = ? WHERE id = ?"
  );
  stmt.run(
    updated.text,
    updated.rating,
    updated.category,
    updated.author,
    JSON.stringify(updated.tags),
    id
  );

  return updated;
}

export function remove(id: string): boolean {
  const result = stmtDelete.run(id);
  return result.changes > 0;
}

export function getSummary(): FeedbackSummary {
  const totalRow = stmtCountAll.get() as { count: number };
  const totalCount = totalRow.count;

  const avgRow = stmtAvgRating.get() as { avg: number | null };
  const averageRating = avgRow.avg ? Math.round(avgRow.avg * 100) / 100 : 0;

  // Rating distribution
  const ratingRows = stmtRatingDist.all() as {
    rating: number;
    count: number;
  }[];
  const ratingDistribution: Record<string, number> = {
    "1": 0,
    "2": 0,
    "3": 0,
    "4": 0,
    "5": 0,
  };
  for (const row of ratingRows) {
    ratingDistribution[String(row.rating)] = row.count;
  }

  // Category counts
  const categoryRows = stmtCategoryCounts.all() as {
    category: string;
    count: number;
  }[];
  const categoryCounts: Record<string, number> = {};
  for (const row of categoryRows) {
    categoryCounts[row.category] = row.count;
  }

  // Top tags — aggregate across all feedback
  const tagRows = stmtAllTags.all() as { tags: string }[];
  const tagCounts: Record<string, number> = {};
  for (const row of tagRows) {
    const tags: string[] = JSON.parse(row.tags);
    for (const tag of tags) {
      tagCounts[tag] = (tagCounts[tag] || 0) + 1;
    }
  }
  const topTags = Object.entries(tagCounts)
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  // Recent 7 days count
  const sevenDaysAgo = new Date(
    Date.now() - 7 * 24 * 60 * 60 * 1000
  ).toISOString();
  const recentRow = stmtRecent7d.get(sevenDaysAgo) as { count: number };
  const recentCount7d = recentRow.count;

  return {
    totalCount,
    averageRating,
    ratingDistribution,
    categoryCounts,
    topTags,
    recentCount7d,
  };
}
