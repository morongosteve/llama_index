import { NextRequest } from "next/server";

/**
 * Validates the API key from the Authorization header.
 *
 * - Reads valid keys from the API_KEYS environment variable (comma-separated).
 * - If API_KEYS is not set, allows all requests (development mode).
 * - Expects header format: Authorization: Bearer <key>
 */
export function validateApiKey(request: NextRequest): boolean {
  const apiKeys = process.env.API_KEYS;

  // Development mode: no keys configured, allow all requests
  if (!apiKeys) {
    return true;
  }

  const validKeys = apiKeys
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);

  // If the env var is set but empty after parsing, allow all
  if (validKeys.length === 0) {
    return true;
  }

  const authHeader = request.headers.get("Authorization");
  if (!authHeader) {
    return false;
  }

  const match = authHeader.match(/^Bearer\s+(.+)$/);
  if (!match) {
    return false;
  }

  const providedKey = match[1];
  return validKeys.includes(providedKey);
}
