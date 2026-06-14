const express = require("express");
const stripe = require("stripe")(process.env.STRIPE_SECRET_KEY);
const fs = require("fs");
const path = require("path");
const os = require("os");

const app = express();
const PORT = process.env.WEBHOOK_PORT || 3001;
const SUBSCRIBERS_PATH = path.resolve(
  __dirname,
  "config",
  "subscribers.json"
);
const WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timestamp() {
  return new Date().toISOString();
}

function log(message) {
  console.log(`[${timestamp()}] ${message}`);
}

/**
 * Read subscribers.json and return the parsed object.
 * Returns a default structure when the file is missing or corrupt.
 */
function readSubscribers() {
  try {
    const raw = fs.readFileSync(SUBSCRIBERS_PATH, "utf-8");
    const data = JSON.parse(raw);
    if (!Array.isArray(data.premium_users)) {
      data.premium_users = [];
    }
    return data;
  } catch (err) {
    log(`Warning: could not read subscribers file (${err.message}), starting fresh`);
    return { premium_users: [] };
  }
}

/**
 * Write subscribers.json atomically — write to a temp file in the same
 * directory, then rename so the operation is all-or-nothing.
 */
function writeSubscribers(data) {
  const dir = path.dirname(SUBSCRIBERS_PATH);
  const tmpFile = path.join(dir, `.subscribers_${process.pid}_${Date.now()}.tmp`);
  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(tmpFile, JSON.stringify(data, null, 2) + "\n", "utf-8");
    fs.renameSync(tmpFile, SUBSCRIBERS_PATH);
  } catch (err) {
    // Clean up the temp file on failure
    try {
      fs.unlinkSync(tmpFile);
    } catch (_) {
      // ignore
    }
    throw err;
  }
}

/**
 * Add a Telegram user ID to the premium list (idempotent).
 */
function addPremiumUser(telegramUserId) {
  const data = readSubscribers();
  const id = String(telegramUserId);
  if (!data.premium_users.includes(id)) {
    data.premium_users.push(id);
    writeSubscribers(data);
    log(`Added premium user: ${id}`);
  } else {
    log(`User ${id} is already premium — no change`);
  }
}

/**
 * Remove a Telegram user ID from the premium list (idempotent).
 */
function removePremiumUser(telegramUserId) {
  const data = readSubscribers();
  const id = String(telegramUserId);
  const idx = data.premium_users.indexOf(id);
  if (idx !== -1) {
    data.premium_users.splice(idx, 1);
    writeSubscribers(data);
    log(`Removed premium user: ${id}`);
  } else {
    log(`User ${id} was not in premium list — no change`);
  }
}

// ---------------------------------------------------------------------------
// Stripe webhook endpoint
// ---------------------------------------------------------------------------

// Stripe requires the raw body for signature verification, so we use
// express.raw() instead of express.json() on this route.
app.post(
  "/webhook",
  express.raw({ type: "application/json" }),
  (req, res) => {
    let event;

    // ---- Signature verification ----
    if (WEBHOOK_SECRET) {
      const sig = req.headers["stripe-signature"];
      try {
        event = stripe.webhooks.constructEvent(req.body, sig, WEBHOOK_SECRET);
      } catch (err) {
        log(`Webhook signature verification failed: ${err.message}`);
        return res.status(400).send(`Webhook Error: ${err.message}`);
      }
    } else {
      // In development without a secret, parse the raw body directly.
      log("WARNING: STRIPE_WEBHOOK_SECRET is not set — skipping signature verification");
      try {
        event = JSON.parse(req.body.toString());
      } catch (err) {
        log(`Failed to parse webhook body: ${err.message}`);
        return res.status(400).send("Invalid JSON");
      }
    }

    log(`Received event: ${event.type} (${event.id})`);

    // ---- Handle relevant events ----
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object;
        const telegramUserId =
          session.metadata && session.metadata.telegram_user_id;

        if (!telegramUserId) {
          log(
            `checkout.session.completed: no telegram_user_id in metadata — ignoring`
          );
          break;
        }

        log(
          `checkout.session.completed: activating premium for Telegram user ${telegramUserId}`
        );
        addPremiumUser(telegramUserId);
        break;
      }

      case "customer.subscription.deleted": {
        const subscription = event.data.object;
        const telegramUserId =
          subscription.metadata && subscription.metadata.telegram_user_id;

        if (!telegramUserId) {
          log(
            `customer.subscription.deleted: no telegram_user_id in metadata — ignoring`
          );
          break;
        }

        log(
          `customer.subscription.deleted: revoking premium for Telegram user ${telegramUserId}`
        );
        removePremiumUser(telegramUserId);
        break;
      }

      default:
        log(`Unhandled event type: ${event.type}`);
    }

    // Acknowledge receipt to Stripe
    res.json({ received: true });
  }
);

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: timestamp() });
});

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  log(`Stripe webhook server listening on port ${PORT}`);
  log(`Subscribers file: ${SUBSCRIBERS_PATH}`);
});
