import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ReadingsTable from "./ReadingsTable.vue";
import RelayEvents from "./RelayEvents.vue";
import StatusGrid from "./StatusGrid.vue";
import { dashboard, reading } from "../test/fixtures";

describe("dashboard display components", () => {
  it("renders metric and error content as text", () => {
    const payload = { ...dashboard, current: { ...reading, error: "<script>unsafe()</script>" } };
    const wrapper = mount(StatusGrid, { props: { payload } });
    expect(wrapper.text()).toContain("18.25 C");
    expect(wrapper.text()).toContain("<script>unsafe()</script>");
    expect(wrapper.find("script").exists()).toBe(false);
  });

  it("shows only the latest twelve readings newest first", async () => {
    const readings = Array.from({ length: 14 }, (_, index) => ({ ...reading, id: index + 1, sensor_id: `sensor-${index + 1}` }));
    const wrapper = mount(ReadingsTable, { props: { readings } });
    expect(wrapper.text()).not.toContain("sensor-14");
    await wrapper.get("button").trigger("click");
    const rows = wrapper.findAll("tbody tr");
    expect(rows).toHaveLength(12);
    expect(rows[0].text()).toContain("sensor-14");
    expect(wrapper.text()).not.toContain("sensor-1 ");
  });

  it("renders relay reasons and the empty state", async () => {
    const wrapper = mount(RelayEvents, { props: { events: dashboard.relay_events } });
    expect(wrapper.text()).not.toContain("temperature high");
    await wrapper.get("button").trigger("click");
    expect(wrapper.text()).toContain("temperature high");
    await wrapper.setProps({ events: [] });
    expect(wrapper.text()).toContain("No relay events recorded.");
  });
});
