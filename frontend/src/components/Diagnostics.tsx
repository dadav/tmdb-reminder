import { useGotifyTest, useStatus } from "../api/queries";
import { Section } from "./Section";
import { StateMessage } from "./StateMessage";
import styles from "./Diagnostics.module.css";

function formatTime(value: string | null | undefined): string {
  if (!value) return "never";
  return new Date(value).toLocaleString();
}

export function Diagnostics() {
  const status = useStatus();
  const gotifyTest = useGotifyTest();

  if (status.isPending) {
    return (
      <Section title="Diagnostics">
        <StateMessage tone="muted" title="Loading status…" />
      </Section>
    );
  }

  if (status.isError || !status.data) {
    return (
      <Section title="Diagnostics">
        <StateMessage
          tone="error"
          title="Status unavailable."
          action={
            <button type="button" onClick={() => void status.refetch()}>
              Retry
            </button>
          }
        />
      </Section>
    );
  }

  const s = status.data;
  const jobs = s.last_jobs ?? [];
  const recentErrors = s.recent_delivery_errors ?? 0;

  return (
    <Section title="Diagnostics">
      <div className={styles.grid}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Configuration</h3>
          <dl className={styles.list}>
            <dt>TMDB</dt>
            <dd>{s.config.tmdb_configured ? "configured" : "not configured"}</dd>
            <dt>Gotify</dt>
            <dd>{s.config.gotify_configured ? "configured" : "not configured"}</dd>
            <dt>Region</dt>
            <dd>{s.config.tmdb_region}</dd>
            <dt>Language</dt>
            <dd>{s.config.tmdb_language}</dd>
            <dt>Timezone</dt>
            <dd>{s.config.app_timezone}</dd>
            <dt>Reminder time</dt>
            <dd>{s.config.reminder_time}</dd>
            <dt>Priority</dt>
            <dd>{s.config.gotify_priority}</dd>
          </dl>
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Activity</h3>
          <dl className={styles.list}>
            <dt>Active</dt>
            <dd>{s.tracked_active}</dd>
            <dt>History</dt>
            <dd>{s.tracked_history}</dd>
            <dt>Pending sends</dt>
            <dd>{s.pending_deliveries}</dd>
            <dt>Recent errors</dt>
            <dd data-alert={recentErrors > 0 ? "true" : undefined}>{recentErrors}</dd>
          </dl>
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Last jobs</h3>
          {jobs.length === 0 ? (
            <p className={styles.muted}>No jobs have run yet.</p>
          ) : (
            <ul className={styles.jobs}>
              {jobs.map((job) => (
                <li key={job.job_name}>
                  <strong>{job.job_name}</strong>: {job.outcome ?? "running"} ·{" "}
                  {formatTime(job.finished_at)} · {job.processed_count} processed
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className={styles.testRow}>
        <button
          type="button"
          onClick={() => gotifyTest.mutate()}
          disabled={!s.config.gotify_configured || gotifyTest.isPending}
        >
          {gotifyTest.isPending ? "Sending…" : "Send Gotify test"}
        </button>
        {gotifyTest.data?.sent && (
          <span className={styles.ok}>Sent (message #{gotifyTest.data.message_id}).</span>
        )}
        {gotifyTest.data && !gotifyTest.data.sent && (
          <span className={styles.err} role="alert">
            {gotifyTest.data.error ?? "Failed to send."}
          </span>
        )}
        {gotifyTest.isError && (
          <span className={styles.err} role="alert">
            Request failed.
          </span>
        )}
      </div>
    </Section>
  );
}
