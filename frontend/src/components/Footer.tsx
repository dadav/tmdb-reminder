import styles from "./Footer.module.css";

/**
 * TMDB attribution. TMDB's terms require showing their logo and the notice that
 * the product uses the TMDB API but is not endorsed or certified by TMDB.
 *
 * The logo below is an inline rendition using TMDB's brand gradient. If you have
 * the official downloadable asset, drop it in and reference it here instead.
 */
export function Footer() {
  return (
    <footer className={styles.footer}>
      <a
        href="https://www.themoviedb.org/"
        target="_blank"
        rel="noreferrer noopener"
        className={styles.logoLink}
        aria-label="The Movie Database (TMDB)"
      >
        <svg
          className={styles.logo}
          viewBox="0 0 273 35"
          role="img"
          aria-hidden="true"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="tmdbGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#90cea1" />
              <stop offset="0.56" stopColor="#3cbec9" />
              <stop offset="1" stopColor="#00b3e5" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="273" height="35" rx="8" fill="url(#tmdbGradient)" />
          <text
            x="18"
            y="25"
            fill="#032541"
            fontFamily="system-ui, sans-serif"
            fontWeight="800"
            fontSize="22"
            letterSpacing="1"
          >
            TMDB
          </text>
        </svg>
      </a>
      <p className={styles.notice}>
        This product uses the TMDB API but is not endorsed or certified by TMDB.
      </p>
    </footer>
  );
}
