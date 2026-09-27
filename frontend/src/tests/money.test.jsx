import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Change, Money, formatINR } from "../components/Money";

describe("money formatting", () => {
  it("groups rupees the Indian way, not in thousands", () => {
    // 1,00,000 rather than 100,000 -- this is read by Indian students
    expect(formatINR("100000.00")).toBe("₹1,00,000.00");
    expect(formatINR("1234567.89")).toBe("₹12,34,567.89");
    expect(formatINR("999.50")).toBe("₹999.50");
  });

  it("prints the exact string it was given, digit for digit", () => {
    // The whole point. A float round trip turns this into 49999.990000000002;
    // the formatter only ever manipulates the string.
    expect(formatINR("49999.99")).toBe("₹49,999.99");
    expect(formatINR("0.10")).toBe("₹0.10");
    // A value with more precision than a float can hold survives untouched.
    // Indian grouping pairs digits all the way up after the first three, so
    // this is 1,23,45,67,89,01,234 and not the Western 12,345,678,901,234.
    expect(formatINR("12345678901234.56")).toBe("₹1,23,45,67,89,01,234.56");
  });

  it("marks negatives with a minus sign", () => {
    expect(formatINR("-250.75")).toBe("−₹250.75");
  });

  it("renders a gain with a + sign as well as colour", () => {
    // Colour alone is invisible to a colourblind reader, so the sign matters.
    render(<Change amount="196.62" percent="0.98" />);
    const element = screen.getByText(/196\.62/);
    expect(element).toHaveTextContent("+₹196.62");
    expect(element).toHaveTextContent("+0.98%");
    expect(element.className).toContain("gain");
  });

  it("renders a loss with a minus sign and the loss colour", () => {
    render(<Change amount="-89.83" percent="-0.45" />);
    const element = screen.getByText(/89\.83/);
    expect(element).toHaveTextContent("−₹89.83");
    expect(element.className).toContain("loss");
  });

  it("shows a dash rather than crashing on a missing value", () => {
    render(<Money value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
