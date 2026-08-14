import tmdbLogo from "../assets/tmdb-logo.svg";
import { useI18n } from "../i18n/context";
import styles from "./Footer.module.css";

/**
 * TMDB attribution (required, do not remove). Uses the official, unmodified
 * primary long blue logo from TMDB's approved logo collection and the prescribed
 * "not endorsed or certified" notice. In German the notice shows a translation
 * followed by the exact English sentence, as required by TMDB guidance.
 */
export function Footer() {
  const { t } = useI18n();
  return (
    <footer className={styles.footer}>
      <a
        href="https://www.themoviedb.org/"
        target="_blank"
        rel="noreferrer noopener"
        className={styles.logoLink}
        aria-label={t("footer.tmdbLink")}
      >
        <img className={styles.logo} src={tmdbLogo} alt="" />
      </a>
      <p className={styles.notice}>{t("footer.notice")}</p>
      <p className={styles.notice}>
        {t("footer.justwatchNotice")}{" "}
        <a
          href="https://www.justwatch.com/"
          target="_blank"
          rel="noreferrer noopener"
          className={styles.providerLink}
        >
          JustWatch
        </a>
      </p>
    </footer>
  );
}
