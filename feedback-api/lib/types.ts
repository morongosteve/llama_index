export type Sentiment = "positive" | "neutral" | "negative";
export type Category = "bug" | "feature" | "praise" | "question" | "other";

export interface Feedback {
  id: string;
  message: string;
  rating: number;
  sentiment: Sentiment;
  category: Category;
  user: string;
  createdAt: string;
}

export type NewFeedback = Omit<Feedback, "id" | "createdAt">;
export type FeedbackPatch = Partial<NewFeedback>;
