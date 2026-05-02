export default function Home() {
  return (
    <main>
      <h1>Feedback API</h1>
      <p>
        A tiny demo API for product feedback. Backed by a JSON file. Built with
        Next.js App Router.
      </p>
      <h2>Endpoints</h2>
      <ul>
        <li>
          <code>GET /api/feedback</code> &mdash; list feedback (filters:{" "}
          <code>category</code>, <code>sentiment</code>, <code>user</code>,{" "}
          <code>minRating</code>, <code>maxRating</code>, <code>q</code>,{" "}
          <code>limit</code>)
        </li>
        <li>
          <code>POST /api/feedback</code> &mdash; create feedback
        </li>
        <li>
          <code>GET /api/feedback/[id]</code> &mdash; get one
        </li>
        <li>
          <code>PATCH /api/feedback/[id]</code> &mdash; partial update
        </li>
        <li>
          <code>DELETE /api/feedback/[id]</code> &mdash; delete
        </li>
        <li>
          <code>GET /api/feedback/summary</code> &mdash; aggregate stats
        </li>
        <li>
          <code>GET /llms.txt</code> &mdash; agent-friendly docs
        </li>
      </ul>
    </main>
  );
}
