import { useI18n } from "../i18n/context";
import styles from "./SearchBar.module.css";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
}

export function SearchBar({ value, onChange }: SearchBarProps) {
  const { t } = useI18n();
  return (
    <div className={styles.wrap}>
      <label htmlFor="search-input" className={styles.label}>
        {t("search.label")}
      </label>
      <div className={styles.field}>
        <input
          id="search-input"
          type="search"
          className={styles.input}
          placeholder={t("search.placeholder")}
          value={value}
          autoComplete="off"
          onChange={(event) => onChange(event.target.value)}
        />
        {value && (
          <button
            type="button"
            className={styles.clear}
            aria-label={t("search.clear")}
            onClick={() => onChange("")}
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}
