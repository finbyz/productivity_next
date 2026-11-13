// echarts served from our own assets, like Frappe Insights (npm dependency, bundled at build time)
// instead of a CDN <script> on every desk page. Load it only where charts are drawn:
//   frappe.require("echarts.bundle.js", () => { ... echarts.init(...) ... });
import * as echarts from "echarts";

window.echarts = echarts;
