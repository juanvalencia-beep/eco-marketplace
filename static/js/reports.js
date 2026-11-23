// Reports page: the four /api/reportes endpoints with a date range,
// a chart and a table for each, plus CSV export and printing.

const reportData = { daily: [], stores: [], products: [], customers: [] };
let reportsReady = false;

function reportRange() {
  return { desde: $("#range-desde").value, hasta: $("#range-hasta").value };
}

function rangeQuery(extra = {}) {
  const { desde, hasta } = reportRange();
  const params = new URLSearchParams(extra);
  if (desde) params.set("desde", desde);
  if (hasta) params.set("hasta", hasta);
  return params.toString() ? "?" + params : "";
}

function rangeText() {
  const { desde, hasta } = reportRange();
  if (!desde && !hasta) return "All time";
  if (desde && hasta) return `${dayLabel(desde, true)} to ${dayLabel(hasta, true)}`;
  return desde ? `From ${dayLabel(desde, true)}` : `Until ${dayLabel(hasta, true)}`;
}

function setPreset(days) {
  $("#range-desde").value = days === "all" ? "" : daysAgo(Number(days) - 1);
  $("#range-hasta").value = days === "all" ? "" : daysAgo(0);
  markPreset();
}

// Highlights the preset chip that matches the dates in the inputs
function markPreset() {
  const { desde, hasta } = reportRange();
  $$(".presets .chip").forEach((chip) => {
    const d = chip.dataset.days;
    const match = d === "all" ? !desde && !hasta : desde === daysAgo(Number(d) - 1) && hasta === daysAgo(0);
    chip.setAttribute("aria-pressed", match);
  });
}

async function loadReportsPage() {
  if (!reportsReady) {
    setPreset(30);
    reportsReady = true;
  }
  runReports();
}

async function runReports() {
  const { desde, hasta } = reportRange();
  if (desde && hasta && desde > hasta) {
    toast("The “From” date must be on or before the “To” date.", "error");
    $("#range-desde").focus();
    return;
  }
  $("#print-range").textContent = `Eco-Marketplace reports, ${rangeText()}. Printed ${dayLabel(daysAgo(0), true)}.`;
  loadingRows($("#stores-report-body"), 4, 3);
  loadingRows($("#products-report-body"), 4, 5);
  loadingRows($("#customers-report-body"), 4, 5);

  await Promise.all([loadDailyReport(), loadStoresReport(), loadProductsReport(), loadCustomersReport()]);
}

/* ---------- revenue per day ---------- */

// /reportes/ventas-diarias only takes "dias" (the last N days up to today),
// so we ask for enough days to reach "desde" and cut the result to the range.
async function loadDailyReport() {
  const { desde, hasta } = reportRange();
  const today = daysAgo(0);
  let dias;
  let note = "";
  if (desde) {
    dias = Math.round((parseDay(today) - parseDay(desde)) / 86400000) + 1;
    if (dias > 365) {
      dias = 365;
      note = "The API covers at most the last 365 days.";
    }
  } else {
    dias = 365; // no start date: take the whole year the API allows
  }

  try {
    let rows = dias >= 1 ? await api.get("/reportes/ventas-diarias?dias=" + dias) : [];
    if (desde) rows = rows.filter((r) => r.fecha >= desde);
    if (hasta) rows = rows.filter((r) => r.fecha <= hasta);
    if (!desde) {
      // "All time": start at the first day with sales instead of a year of zeros
      const first = rows.findIndex((r) => r.pedidos > 0);
      rows = first === -1 ? [] : rows.slice(first);
      note = "Daily figures cover up to the last 365 days.";
    }
    if (hasta && hasta > today) note = "Days after today have no sales yet.";
    reportData.daily = rows;

    const total = rows.reduce((s, r) => s + r.ingresos, 0);
    const orders = rows.reduce((s, r) => s + r.pedidos, 0);
    const best = rows.reduce((b, r) => (r.ingresos > (b?.ingresos ?? -1) ? r : b), null);
    const active = rows.filter((r) => r.pedidos > 0).length;

    $("#daily-sub").textContent = note || "Every day in the range, including days without sales";
    $("#daily-stats").innerHTML = `
      <div><span>Revenue</span><strong>${esc(money(total))}</strong></div>
      <div><span>Orders</span><strong>${int(orders)}</strong></div>
      <div><span>Average per order</span><strong>${esc(money(orders ? total / orders : 0))}</strong></div>
      <div><span>Best day</span><strong>${best && best.ingresos ? esc(dayLabel(best.fecha)) + " <small>" + esc(money(best.ingresos)) + "</small>" : "–"}</strong></div>
      <div><span>Days with sales</span><strong>${int(active)} <small>of ${int(rows.length)}</small></strong></div>`;

    lineChart(
      $("#report-daily-chart"),
      rows.map((r) => ({ label: dayLabel(r.fecha), tooltip: dayLabel(r.fecha, true), value: r.ingresos, detail: plural(r.pedidos, "order") })),
      { height: 260 }
    );
    $("#daily-body").innerHTML = rows.length
      ? rows
          .slice()
          .reverse()
          .map((r) => `<tr class="${r.pedidos ? "" : "is-zero"}"><td>${esc(dayLabel(r.fecha, true))}</td><td class="num">${int(r.pedidos)}</td><td class="num">${esc(money(r.ingresos))}</td></tr>`)
          .join("")
      : emptyRow(3, "No days in this range");
  } catch (err) {
    showError(err);
    $("#report-daily-chart").innerHTML = emptyBlock("Could not load daily revenue", esc(err.message));
  }
}

/* ---------- sales by store ---------- */

async function loadStoresReport() {
  try {
    const rows = await api.get("/reportes/ventas-por-tienda" + rangeQuery());
    reportData.stores = rows;
    barList(
      $("#stores-chart"),
      rows.map((r) => ({ label: r.nombre_sucursal, value: r.ingresos })),
      { emptyTitle: "No sales in this period", emptyHint: "Try a wider date range." }
    );
    setRows(
      $("#stores-report-body"),
      rows.length
        ? rows
            .map(
              (r) => `<tr>
                <td class="strong">${esc(r.nombre_sucursal)}</td>
                <td class="num">${int(r.pedidos)}</td>
                <td class="num strong">${esc(money(r.ingresos))}</td>
                <td class="num">${esc(money(r.ticket_promedio))}</td>
              </tr>`
            )
            .join("") + totalRow(rows, ["pedidos", "ingresos"])
        : emptyRow(4, "No stores yet")
    );
  } catch (err) {
    showError(err);
    setRows($("#stores-report-body"), emptyRow(4, "Could not load this report", esc(err.message)));
  }
}

function totalRow(rows) {
  const orders = rows.reduce((s, r) => s + r.pedidos, 0);
  const revenue = rows.reduce((s, r) => s + r.ingresos, 0);
  return `<tr class="total-row">
    <td>All stores</td>
    <td class="num">${int(orders)}</td>
    <td class="num">${esc(money(revenue))}</td>
    <td class="num">${esc(money(orders ? revenue / orders : 0))}</td>
  </tr>`;
}

/* ---------- best-selling products ---------- */

async function loadProductsReport() {
  try {
    const rows = await api.get("/reportes/productos-mas-vendidos" + rangeQuery({ limite: $("#products-limit").value }));
    reportData.products = rows;
    barList(
      $("#products-chart"),
      rows.map((r) => ({ label: r.nombre, value: r.ingresos })),
      { emptyTitle: "No products sold in this period", emptyHint: "Try a wider date range." }
    );
    setRows(
      $("#products-report-body"),
      rows.length
        ? rows
            .map(
              (r, i) => `<tr>
                <td class="nowrap"><span class="rank">${i + 1}</span><span class="strong">${esc(r.nombre)}</span></td>
                <td class="num nowrap">${esc(qty(r.cantidad_vendida))} <span class="muted">${esc(r.unidad_medida)}</span></td>
                <td class="num">${int(r.pedidos)}</td>
                <td class="num strong">${esc(money(r.ingresos))}</td>
              </tr>`
            )
            .join("")
        : emptyRow(4, "No products sold in this period")
    );
  } catch (err) {
    showError(err);
    setRows($("#products-report-body"), emptyRow(4, "Could not load this report", esc(err.message)));
  }
}

/* ---------- top customers ---------- */

async function loadCustomersReport() {
  try {
    const rows = await api.get("/reportes/top-clientes" + rangeQuery({ limite: $("#customers-limit").value }));
    reportData.customers = rows;
    barList(
      $("#customers-chart"),
      rows.map((r) => ({ label: r.nombre_completo, value: r.total_gastado })),
      { emptyTitle: "No customers bought in this period", emptyHint: "Try a wider date range." }
    );
    setRows(
      $("#customers-report-body"),
      rows.length
        ? rows
            .map(
              (r, i) => `<tr>
                <td class="nowrap"><span class="rank">${i + 1}</span><span class="strong">${esc(r.nombre_completo)}</span></td>
                <td class="num">${int(r.pedidos)}</td>
                <td class="num strong">${esc(money(r.total_gastado))}</td>
                <td class="num"><span class="points">${int(r.puntos_ecologicos)}</span></td>
              </tr>`
            )
            .join("")
        : emptyRow(4, "No customers bought in this period")
    );
  } catch (err) {
    showError(err);
    setRows($("#customers-report-body"), emptyRow(4, "Could not load this report", esc(err.message)));
  }
}

/* ---------- CSV export ---------- */

const csvReports = {
  daily: {
    name: "revenue-per-day",
    columns: [
      { label: "Date", value: (r) => r.fecha },
      { label: "Orders", value: (r) => r.pedidos },
      { label: "Revenue (USD)", value: (r) => r.ingresos.toFixed(2) },
    ],
  },
  stores: {
    name: "sales-by-store",
    columns: [
      { label: "Store ID", value: (r) => r.tienda_id },
      { label: "Store", value: (r) => r.nombre_sucursal },
      { label: "Orders", value: (r) => r.pedidos },
      { label: "Revenue (USD)", value: (r) => r.ingresos.toFixed(2) },
      { label: "Average ticket (USD)", value: (r) => r.ticket_promedio.toFixed(2) },
    ],
  },
  products: {
    name: "best-selling-products",
    columns: [
      { label: "Rank", value: (r) => reportData.products.indexOf(r) + 1 },
      { label: "Product ID", value: (r) => r.producto_id },
      { label: "Product", value: (r) => r.nombre },
      { label: "Unit", value: (r) => r.unidad_medida },
      { label: "Quantity sold", value: (r) => r.cantidad_vendida },
      { label: "Orders", value: (r) => r.pedidos },
      { label: "Revenue (USD)", value: (r) => r.ingresos.toFixed(2) },
    ],
  },
  customers: {
    name: "top-customers",
    columns: [
      { label: "Rank", value: (r) => reportData.customers.indexOf(r) + 1 },
      { label: "Customer ID", value: (r) => r.cliente_id },
      { label: "Customer", value: (r) => r.nombre_completo },
      { label: "Orders", value: (r) => r.pedidos },
      { label: "Spent (USD)", value: (r) => r.total_gastado.toFixed(2) },
      { label: "Eco-points held", value: (r) => r.puntos_ecologicos },
    ],
  },
};

$("#page-reports").addEventListener("click", (e) => {
  const csvBtn = e.target.closest("[data-csv]");
  if (csvBtn) {
    const report = csvReports[csvBtn.dataset.csv];
    const rows = reportData[csvBtn.dataset.csv];
    if (!rows.length) {
      toast("This report has no rows to export for the chosen dates.", "error");
      return;
    }
    const { desde, hasta } = reportRange();
    const suffix = desde || hasta ? `_${desde || "start"}_${hasta || "today"}` : "_all-time";
    downloadCSV(`${report.name}${suffix}.csv`, report.columns, rows);
    toast(`Exported ${plural(rows.length, "row")} to ${report.name}${suffix}.csv.`);
    return;
  }

  const printBtn = e.target.closest("[data-print]");
  if (printBtn) printReports(printBtn.dataset.print);
});

/* ---------- printing ---------- */

// Prints one report (or all of them). The print stylesheet hides the sidebar,
// buttons and filters; body[data-print] hides the other reports.
function printReports(id) {
  const details = $("#report-daily details");
  const wasOpen = details.open;
  if (id) {
    document.body.dataset.print = id;
    $("#" + id).classList.add("print-target");
  }
  if (!id || id === "report-daily") details.open = true; // print the daily table too
  window.addEventListener(
    "afterprint",
    () => {
      delete document.body.dataset.print;
      $$(".print-target").forEach((el) => el.classList.remove("print-target"));
      details.open = wasOpen;
    },
    { once: true }
  );
  window.print();
}

$("#print-all").addEventListener("click", () => printReports(null));

/* ---------- range form ---------- */

$("#range-form").addEventListener("submit", (e) => {
  e.preventDefault();
  markPreset();
  runReports();
});

$$(".presets .chip").forEach((chip) =>
  chip.addEventListener("click", () => {
    setPreset(chip.dataset.days);
    runReports();
  })
);

$("#range-desde").addEventListener("input", markPreset);
$("#range-hasta").addEventListener("input", markPreset);
$("#products-limit").addEventListener("change", loadProductsReport);
$("#customers-limit").addEventListener("change", loadCustomersReport);
