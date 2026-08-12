import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SearchBar } from "../src/components/SearchBar";

describe("SearchBar", () => {
  it("exposes an accessible labelled search box", () => {
    render(<SearchBar value="" onChange={() => {}} />);
    expect(screen.getByRole("searchbox", { name: /search movies and tv shows/i })).toBeInTheDocument();
  });

  it("calls onChange as the user types", async () => {
    const onChange = vi.fn();
    render(<SearchBar value="" onChange={onChange} />);
    await userEvent.type(screen.getByRole("searchbox"), "hi");
    expect(onChange).toHaveBeenCalled();
  });

  it("shows a clear button only when there is text and clears on click", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<SearchBar value="" onChange={onChange} />);
    expect(screen.queryByRole("button", { name: /clear search/i })).not.toBeInTheDocument();

    rerender(<SearchBar value="matrix" onChange={onChange} />);
    const clear = screen.getByRole("button", { name: /clear search/i });
    await userEvent.click(clear);
    expect(onChange).toHaveBeenCalledWith("");
  });
});
