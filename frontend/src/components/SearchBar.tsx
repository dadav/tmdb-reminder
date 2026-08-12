import styles from "./SearchBar.module.css";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
}

export function SearchBar({ value, onChange }: SearchBarProps) {
  return (
    <div className={styles.wrap}>
      <label htmlFor="search-input" className={styles.label}>
        Search movies and TV shows
      </label>
      <div className={styles.field}>
        <input
          id="search-input"
          type="search"
          className={styles.input}
          placeholder="Start typing a title…"
          value={value}
          autoComplete="off"
          onChange={(event) => onChange(event.target.value)}
        />
        {value && (
          <button
            type="button"
            className={styles.clear}
            aria-label="Clear search"
            onClick={() => onChange("")}
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}
