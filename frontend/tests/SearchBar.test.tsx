import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SearchBar } from "../src/components/SearchBar";
import { renderWithClient } from "./utils";

describe("SearchBar", () => {
  it("exposes an accessible labelled search box in German", () => {
    renderWithClient(<SearchBar value="" onChange={() => {}} />);
    expect(
      screen.getByRole("searchbox", { name: /filme und serien suchen/i }),
    ).toBeInTheDocument();
  });

  it("calls onChange as the user types", async () => {
    const onChange = vi.fn();
    renderWithClient(<SearchBar value="" onChange={onChange} />);
    await userEvent.type(screen.getByRole("searchbox"), "hi");
    expect(onChange).toHaveBeenCalled();
  });

  it("hides the clear button when the field is empty", () => {
    renderWithClient(<SearchBar value="" onChange={() => {}} />);
    expect(screen.queryByRole("button", { name: /suche löschen/i })).not.toBeInTheDocument();
  });

  it("shows a clear button when there is text and clears on click", async () => {
    const onChange = vi.fn();
    renderWithClient(<SearchBar value="matrix" onChange={onChange} />);
    const clear = screen.getByRole("button", { name: /suche löschen/i });
    await userEvent.click(clear);
    expect(onChange).toHaveBeenCalledWith("");
  });
});
