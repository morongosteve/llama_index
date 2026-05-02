package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"time"

	anthropic "github.com/anthropics/anthropic-sdk-go"
	"github.com/anthropics/anthropic-sdk-go/option"
)

// claudeOpus46 is the model ID for Claude Opus 4.6.
// SDK v1.19.0 does not yet export a named constant for this model, so we
// define it locally as a typed string — the API accepts it.
const claudeOpus46 anthropic.Model = "claude-opus-4-6"

func main() {
	// ---------------------------------------------------------------------------
	// 1. Client configuration with functional options
	// ---------------------------------------------------------------------------
	// option.With* functions are closures that mutate a RequestConfig.
	// Passing them to NewClient applies them to every request; they can be
	// overridden on a per-request basis.
	client := anthropic.NewClient(
		// Reads ANTHROPIC_API_KEY from the environment by default.
		// Shown here explicitly; omit in production and rely on the env var.
		option.WithAPIKey(os.Getenv("ANTHROPIC_API_KEY")),

		// Retry up to 3 times on connection errors, 408, 409, 429, and >=500.
		option.WithMaxRetries(3),

		// Attach a custom header to every request made by this client.
		option.WithHeader("X-Demo-Header", "anthropic-go-demo"),
	)

	// ---------------------------------------------------------------------------
	// 2. Context-based cancellation — per-request total timeout
	// ---------------------------------------------------------------------------
	// context.WithTimeout wraps a parent context with a deadline.  If the
	// request (including all retries) does not complete within the deadline,
	// the SDK cancels the in-flight HTTP call and returns an error that wraps
	// context.DeadlineExceeded.
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel() // always release the timer

	// ---------------------------------------------------------------------------
	// 3. Per-request functional options (override client defaults)
	// ---------------------------------------------------------------------------
	// option.WithRequestTimeout sets a per-retry timeout that resets on each
	// retry attempt.  The context deadline (above) caps total wall-clock time
	// across all retries; WithRequestTimeout caps a single attempt.
	message, err := client.Messages.New(
		ctx,
		anthropic.MessageNewParams{
			Model:     claudeOpus46,
			MaxTokens: 256,
			Messages: []anthropic.MessageParam{
				anthropic.NewUserMessage(
					anthropic.NewTextBlock("In one sentence, what is a quaternion?"),
				),
			},
		},
		// Per-retry timeout (overrides the client default of no per-retry timeout).
		option.WithRequestTimeout(10*time.Second),
		// Override the custom header for just this request.
		option.WithHeader("X-Demo-Header", "per-request-override"),
	)
	if err != nil {
		handleError(err)
		os.Exit(1)
	}

	if len(message.Content) > 0 {
		fmt.Println("Response:", message.Content[0].Text)
	}

	// ---------------------------------------------------------------------------
	// 4. Explicit context cancellation
	// ---------------------------------------------------------------------------
	// Demonstrates how to cancel a request from application logic (e.g. on
	// SIGINT, HTTP disconnect, or user action).
	ctxCancel, cancelNow := context.WithCancel(context.Background())

	// Cancel immediately to exercise the error-handling path.
	cancelNow()

	_, err = client.Messages.New(
		ctxCancel,
		anthropic.MessageNewParams{
			Model:     claudeOpus46,
			MaxTokens: 64,
			Messages: []anthropic.MessageParam{
				anthropic.NewUserMessage(anthropic.NewTextBlock("Hello")),
			},
		},
	)
	if err != nil {
		if errors.Is(err, context.Canceled) {
			fmt.Println("Request correctly cancelled:", err)
		} else {
			fmt.Fprintf(os.Stderr, "unexpected error after cancel: %v\n", err)
		}
	}
}

// handleError demonstrates typed error handling with the Anthropic Go SDK.
// Use errors.As to unwrap *anthropic.Error and access the HTTP status code,
// request ID, and full request/response dumps for debugging.
func handleError(err error) {
	var apiErr *anthropic.Error
	if errors.As(err, &apiErr) {
		fmt.Fprintf(os.Stderr, "Anthropic API error\n")
		fmt.Fprintf(os.Stderr, "  Status:     %d\n", apiErr.StatusCode)
		fmt.Fprintf(os.Stderr, "  Request-ID: %s\n", apiErr.RequestID)
		// Pass true to include the request/response body in the dump.
		fmt.Fprintf(os.Stderr, "  Request:\n%s\n", apiErr.DumpRequest(true))
		fmt.Fprintf(os.Stderr, "  Response:\n%s\n", apiErr.DumpResponse(true))
		return
	}

	switch {
	case errors.Is(err, context.DeadlineExceeded):
		fmt.Fprintln(os.Stderr, "Request timed out:", err)
	case errors.Is(err, context.Canceled):
		fmt.Fprintln(os.Stderr, "Request was cancelled:", err)
	default:
		// Transport-level error, e.g. *url.Error wrapping *net.OpError.
		fmt.Fprintln(os.Stderr, "Unexpected error:", err)
	}
}
