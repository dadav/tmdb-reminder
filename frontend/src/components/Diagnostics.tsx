import { useGotifyTest, useStatus } from "../api/queries";
import { useI18n } from "../i18n/context";
import {
  formatInstant,
  formatNumber,
  formatReminderTime,
  isKnownJobName,
  isKnownOutcome,
  jobNameLabel,
  outcomeLabel,
} from "../lib/format";
import { Section } from "./Section";
import { StateMessage } from "./StateMessage";
import styles from "./Diagnostics.module.css";

export function Diagnostics() {
  const { t, formatLocale } = useI18n();
  const status = useStatus();
  const gotifyTest = useGotifyTest();

  if (status.isPending) {
    return (
      <Section title={t("diagnostics.section")}>
        <StateMessage tone="muted" title={t("diagnostics.loadingStatus")} />
      </Section>
    );
  }

  if (status.isError || !status.data) {
    return (
      <Section title={t("diagnostics.section")}>
        <StateMessage
          tone="error"
          title={t("diagnostics.statusUnavailable")}
          action={
            <button type="button" onClick={() => void status.refetch()}>
              {t("actions.retry")}
            </button>
          }
        />
      </Section>
    );
  }

  const statusData = status.data;
  const timeZone = statusData.config.app_timezone;
  const jobs = statusData.last_jobs ?? [];
  const recentErrors = statusData.recent_delivery_errors ?? 0;

  return (
    <Section title={t("diagnostics.section")}>
      <div className={styles.grid}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>{t("diagnostics.configTitle")}</h3>
          <dl className={styles.list}>
            <dt>{t("diagnostics.tmdb")}</dt>
            <dd>{statusData.config.tmdb_configured ? t("diagnostics.configured") : t("diagnostics.notConfigured")}</dd>
            <dt>{t("diagnostics.gotify")}</dt>
            <dd>{statusData.config.gotify_configured ? t("diagnostics.configured") : t("diagnostics.notConfigured")}</dd>
            <dt>{t("diagnostics.region")}</dt>
            <dd>{statusData.config.tmdb_region}</dd>
            <dt>{t("diagnostics.language")}</dt>
            <dd>{statusData.config.tmdb_language}</dd>
            <dt>{t("diagnostics.timezone")}</dt>
            <dd>{statusData.config.app_timezone}</dd>
            <dt>{t("diagnostics.reminderTime")}</dt>
            <dd>{formatReminderTime(statusData.config.reminder_time, formatLocale)}</dd>
            <dt>{t("diagnostics.availabilityDelay")}</dt>
            <dd>
              {t("diagnostics.days", {
                count: statusData.config.availability_delay_days,
              })}
            </dd>
            <dt>{t("diagnostics.priority")}</dt>
            <dd>{formatNumber(statusData.config.gotify_priority, formatLocale)}</dd>
          </dl>
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>{t("diagnostics.activityTitle")}</h3>
          <dl className={styles.list}>
            <dt>{t("diagnostics.active")}</dt>
            <dd>{formatNumber(statusData.tracked_active, formatLocale)}</dd>
            <dt>{t("diagnostics.history")}</dt>
            <dd>{formatNumber(statusData.tracked_history, formatLocale)}</dd>
            <dt>{t("diagnostics.pendingSends")}</dt>
            <dd>{formatNumber(statusData.pending_deliveries, formatLocale)}</dd>
            <dt>{t("diagnostics.recentErrors")}</dt>
            <dd data-alert={recentErrors > 0 ? "true" : undefined}>
              {formatNumber(recentErrors, formatLocale)}
            </dd>
          </dl>
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>{t("diagnostics.lastJobsTitle")}</h3>
          {jobs.length === 0 ? (
            <p className={styles.muted}>{t("diagnostics.noJobs")}</p>
          ) : (
            <ul className={styles.jobs}>
              {jobs.map((job) => (
                <li key={job.job_name}>
                  <strong>{jobNameLabel(job.job_name, t)}</strong>: {outcomeLabel(job.outcome, t)} ·{" "}
                  {formatInstant(job.finished_at, formatLocale, timeZone, t)} ·{" "}
                  {t("diagnostics.processed", {
                    n: formatNumber(job.processed_count, formatLocale),
                  })}
                  {(!isKnownJobName(job.job_name) || !isKnownOutcome(job.outcome)) && (
                    <>
                      {" "}· {t("diagnostics.technicalDetails")}: {job.job_name} /{" "}
                      {job.outcome ?? "running"}
                    </>
                  )}
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
          disabled={!statusData.config.gotify_configured || gotifyTest.isPending}
        >
          {gotifyTest.isPending ? t("diagnostics.sending") : t("diagnostics.sendGotifyTest")}
        </button>
        {gotifyTest.data?.sent && (
          <span className={styles.ok}>{t("diagnostics.sent", { id: gotifyTest.data.message_id })}</span>
        )}
        {gotifyTest.data && !gotifyTest.data.sent && (
          <span className={styles.err} role="alert">
            {t("diagnostics.sendFailed")}
            {gotifyTest.data.error
              ? ` (${t("diagnostics.technicalDetails")}: ${gotifyTest.data.error})`
              : ""}
          </span>
        )}
        {gotifyTest.isError && (
          <span className={styles.err} role="alert">
            {t("diagnostics.requestFailed")}
          </span>
        )}
      </div>
    </Section>
  );
}
