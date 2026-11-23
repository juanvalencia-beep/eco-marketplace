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
  if (!desde && !hasta) return "todo el historial";
  if (desde && hasta) return `del ${dayLabel(desde, true)} al ${dayLabel(hasta, true)}`;
  return desde ? `desde el ${dayLabel(desde, true)}` : `hasta el ${dayLabel(hasta, true)}`;
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
    toast("La fecha “Desde” debe ser igual o anterior a la fecha “Hasta”.", "error");
    $("#range-desde").focus();
    return;
  }
  $("#print-range").textContent = `Reportes de Eco-Marketplace, ${rangeText()}. Impreso el ${dayLabel(daysAgo(0), true)}.`;
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
      note = "La API cubre como máximo los últimos 365 días.";
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
      note = "Las cifras diarias cubren como máximo los últimos 365 días.";
    }
    if (hasta && hasta > today) note = "Los días posteriores a hoy aún no tienen ventas.";
    reportData.daily = rows;

    const total = rows.reduce((s, r) => s + r.ingresos, 0);
    const orders = rows.reduce((s, r) => s + r.pedidos, 0);
    const best = rows.reduce((b, r) => (r.ingresos > (b?.ingresos ?? -1) ? r : b), null);
    const active = rows.filter((r) => r.pedidos > 0).length;

    $("#daily-sub").textContent = note || "Todos los días del rango, incluso los días sin ventas";
    $("#daily-stats").innerHTML = `
      <div><span>Ingresos</span><strong>${esc(money(total))}</strong></div>
      <div><span>Pedidos</span><strong>${int(orders)}</strong></div>
      <div><span>Promedio por pedido</span><strong>${esc(money(orders ? total / orders : 0))}</strong></div>
      <div><span>Mejor día</span><strong>${best && best.ingresos ? esc(dayLabel(best.fecha)) + " <small>" + esc(money(best.ingresos)) + "</small>" : "–"}</strong></div>
      <div><span>Días con ventas</span><strong>${int(active)} <small>de ${int(rows.length)}</small></strong></div>`;

    lineChart(
      $("#report-daily-chart"),
      rows.map((r) => ({ label: dayLabel(r.fecha), tooltip: dayLabel(r.fecha, true), value: r.ingresos, detail: plural(r.pedidos, "pedido") })),
      { height: 260 }
    );
    $("#daily-body").innerHTML = rows.length
      ? rows
          .slice()
          .reverse()
          .map((r) => `<tr class="${r.pedidos ? "" : "is-zero"}"><td>${esc(dayLabel(r.fecha, true))}</td><td class="num">${int(r.pedidos)}</td><td class="num">${esc(money(r.ingresos))}</td></tr>`)
          .join("")
      : emptyRow(3, "No hay días en este rango");
  } catch (err) {
    showError(err);
    $("#report-daily-chart").innerHTML = emptyBlock("No se pudieron cargar los ingresos diarios", esc(err.message));
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
      { emptyTitle: "Sin ventas en este periodo", emptyHint: "Pruebe con un rango de fechas más amplio." }
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
        : emptyRow(4, "Aún no hay tiendas")
    );
  } catch (err) {
    showError(err);
    setRows($("#stores-report-body"), emptyRow(4, "No se pudo cargar este reporte", esc(err.message)));
  }
}

function totalRow(rows) {
  const orders = rows.reduce((s, r) => s + r.pedidos, 0);
  const revenue = rows.reduce((s, r) => s + r.ingresos, 0);
  return `<tr class="total-row">
    <td>Todas las tiendas</td>
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
      { emptyTitle: "No se vendieron productos en este periodo", emptyHint: "Pruebe con un rango de fechas más amplio." }
    );
    setRows(
      $("#products-report-body"),
      rows.length
        ? rows
            .map(
              (r, i) => `<tr>
                <td class="nowrap"><span class="rank">${i + 1}</span><span class="strong">${esc(r.nombre)}</span></td>
                <td class="num nowrap">${esc(qty(r.cantidad_vendida))} <span class="muted">${esc(unitFor(r.cantidad_vendida, r.unidad_medida))}</span></td>
                <td class="num">${int(r.pedidos)}</td>
                <td class="num strong">${esc(money(r.ingresos))}</td>
              </tr>`
            )
            .join("")
        : emptyRow(4, "No se vendieron productos en este periodo")
    );
  } catch (err) {
    showError(err);
    setRows($("#products-report-body"), emptyRow(4, "No se pudo cargar este reporte", esc(err.message)));
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
      { emptyTitle: "Ningún cliente compró en este periodo", emptyHint: "Pruebe con un rango de fechas más amplio." }
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
        : emptyRow(4, "Ningún cliente compró en este periodo")
    );
  } catch (err) {
    showError(err);
    setRows($("#customers-report-body"), emptyRow(4, "No se pudo cargar este reporte", esc(err.message)));
  }
}

/* ---------- CSV export ---------- */

const csvReports = {
  daily: {
    name: "ingresos-por-dia",
    columns: [
      { label: "Fecha", value: (r) => r.fecha },
      { label: "Pedidos", value: (r) => r.pedidos },
      { label: "Ingresos (USD)", value: (r) => r.ingresos.toFixed(2) },
    ],
  },
  stores: {
    name: "ventas-por-tienda",
    columns: [
      { label: "ID tienda", value: (r) => r.tienda_id },
      { label: "Tienda", value: (r) => r.nombre_sucursal },
      { label: "Pedidos", value: (r) => r.pedidos },
      { label: "Ingresos (USD)", value: (r) => r.ingresos.toFixed(2) },
      { label: "Ticket promedio (USD)", value: (r) => r.ticket_promedio.toFixed(2) },
    ],
  },
  products: {
    name: "productos-mas-vendidos",
    columns: [
      { label: "Puesto", value: (r) => reportData.products.indexOf(r) + 1 },
      { label: "ID producto", value: (r) => r.producto_id },
      { label: "Producto", value: (r) => r.nombre },
      { label: "Unidad", value: (r) => r.unidad_medida },
      { label: "Cantidad vendida", value: (r) => r.cantidad_vendida },
      { label: "Pedidos", value: (r) => r.pedidos },
      { label: "Ingresos (USD)", value: (r) => r.ingresos.toFixed(2) },
    ],
  },
  customers: {
    name: "mejores-clientes",
    columns: [
      { label: "Puesto", value: (r) => reportData.customers.indexOf(r) + 1 },
      { label: "ID cliente", value: (r) => r.cliente_id },
      { label: "Cliente", value: (r) => r.nombre_completo },
      { label: "Pedidos", value: (r) => r.pedidos },
      { label: "Gastado (USD)", value: (r) => r.total_gastado.toFixed(2) },
      { label: "Eco-puntos acumulados", value: (r) => r.puntos_ecologicos },
    ],
  },
};

$("#page-reports").addEventListener("click", (e) => {
  const csvBtn = e.target.closest("[data-csv]");
  if (csvBtn) {
    const report = csvReports[csvBtn.dataset.csv];
    const rows = reportData[csvBtn.dataset.csv];
    if (!rows.length) {
      toast("Este reporte no tiene filas para exportar en las fechas elegidas.", "error");
      return;
    }
    const { desde, hasta } = reportRange();
    const suffix = desde || hasta ? `_${desde || "inicio"}_${hasta || "hoy"}` : "_historico";
    downloadCSV(`${report.name}${suffix}.csv`, report.columns, rows);
    toast(`Se exportó ${report.name}${suffix}.csv (${plural(rows.length, "fila")}).`);
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
