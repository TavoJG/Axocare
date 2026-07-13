import { describe, expect, it } from "vitest";
import { formatPercent, formatPressure, formatSpan, formatTemperature, sensorMessages } from "./formatters";
import { reading } from "./test/fixtures";

describe("dashboard formatters", () => {
  it("formats measurements and missing values", () => {
    expect(formatTemperature(18.256)).toBe("18.26 C");
    expect(formatTemperature(21.54, 1)).toBe("21.5 C");
    expect(formatTemperature(null)).toBe("No data");
    expect(formatPercent(62.44)).toBe("62.4 %");
    expect(formatPressure(1012.64)).toBe("1012.6 hPa");
  });

  it("formats every supported span style", () => {
    expect([15, 60, 180, 1440].map(formatSpan)).toEqual(["15 min", "1 hour", "3 hours", "24 hours"]);
  });

  it("combines tank and ambient sensor errors", () => {
    expect(sensorMessages({ ...reading, error: "tank <bad>", ambient_error: "ambient" })).toEqual(["tank <bad>", "ambient"]);
  });
});
