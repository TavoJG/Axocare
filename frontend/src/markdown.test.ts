import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("renders common markdown blocks and inline formatting", () => {
    expect(renderMarkdown("# Status\n\n- **Stable**\n- `18.0 C`")).toBe(
      "<h1>Status</h1><ul><li><strong>Stable</strong></li><li><code>18.0 C</code></li></ul>"
    );
  });

  it("escapes embedded html and only keeps safe links", () => {
    expect(renderMarkdown("<script>alert(1)</script>\n[site](javascript:alert(1))")).toBe(
      "<p>&lt;script&gt;alert(1)&lt;/script&gt;<br>site</p>"
    );
  });
});
