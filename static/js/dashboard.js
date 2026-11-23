// Dashboard: key figures, revenue per day, revenue by store, top products,
// low stock and the newest orders. Everything loads in parallel.

async function loadDashboard() {
  loadingRows($("#dash-recent"), 7, 6);

  let data;
  try {
    const [summary, daily, stores, top, low, orders] = await Promise.all([
      api.get("/resumen"),
      api.get("/reportes/ventas-diarias?dias=30"),
      api.get("/reportes/ventas-por-tienda"),
      api.get("/reportes/productos-mas-vendidos?limite=5"),
      api.get("/inventario/stock-bajo"),
      api.get("/pedidos"),
    ]);
    data = { summary, daily, stores, top, low, orders };
  } catch (err) {
    showError(err);
    setRows($("#dash-recent"), emptyRow(7, "No se pudo cargar el panel", esc(err.message)));
    return;
  }

  // key figures, counted up from zero
  const s = data.summary;
  countUp($("#kpi-ingresos"), s.ingresos, money);
  for (const key of ["pedidos", "clientes", "tiendas", "productos", "puntos_ecologicos", "stock_bajo"]) {
    countUp($("#kpi-" + key), s[key], int);
  }
  $(".kpi-alert").classList.toggle("is-ok", s.stock_bajo === 0);

  // revenue per day (last 30 days)
  const total = data.daily.reduce((sum, d) => sum + d.ingresos, 0);
  const orderCount = data.daily.reduce((sum, d) => sum + d.pedidos, 0);
  $("#daily-total").innerHTML = `${esc(money(total))}<span>${esc(plural(orderCount, "pedido"))}</span>`;
  lineChart(
    $("#dash-daily-chart"),
    data.daily.map((d) => ({
      label: dayLabel(d.fecha),
      tooltip: dayLabel(d.fecha, true),
      value: d.ingresos,
      detail: plural(d.pedidos, "pedido"),
    }))
  );

  barList(
    $("#dash-stores"),
    data.stores.map((r) => ({ label: r.nombre_sucursal, value: r.ingresos, note: `${plural(r.pedidos, "pedido")}, ticket promedio ${money(r.ticket_promedio)}` })),
    { emptyTitle: "Aún no hay tiendas", emptyHint: '<a href="#stores">Agregue una tienda</a> para empezar a vender.' }
  );

  barList(
    $("#dash-top"),
    data.top.map((r) => ({ label: r.nombre, value: r.ingresos, note: `${qty(r.cantidad_vendida)} ${unitFor(r.cantidad_vendida, r.unidad_medida)} en ${plural(r.pedidos, "pedido")}` })),
    { emptyTitle: "Aún no hay ventas", emptyHint: "Los más vendidos aparecerán después del primer pedido." }
  );

  // low stock: a jar per row, filled relative to the 10 unit threshold
  $("#dash-low").innerHTML = data.low.length
    ? data.low
        .slice(0, 6)
        .map(
          (r) => `<li>
            ${jar(r.cantidad_stock / LOW_STOCK, true)}
            <span class="stock-name"><strong>${esc(r.nombre_producto)}</strong><span>${esc(r.nombre_sucursal)}</span></span>
            <span class="stock-qty">${esc(qty(r.cantidad_stock))} <small>${esc(unitFor(r.cantidad_stock, r.unidad_medida))}</small></span>
          </li>`
        )
        .join("") +
      (data.low.length > 6 ? `<li class="stock-more"><a href="#inventory">${esc(plural(data.low.length - 6, "registro más", "registros más"))} en el inventario</a></li>` : "")
    : `<li class="stock-ok">${emptyBlock("Todas las tiendas tienen buen stock", "Nada está por debajo de 10 unidades.")}</li>`;

  // recent orders
  setRows(
    $("#dash-recent"),
    data.orders.length
      ? data.orders.slice(0, 6).map((o) => orderRow(o)).join("")
      : emptyRow(7, "Aún no hay pedidos", '<a href="#orders">Registre el primer pedido</a>.')
  );
}

// One row of an orders table (used here and in the Orders page)
function orderRow(o, withProducts = false) {
  return `<tr>
    <td class="id">${o.pedido_id}</td>
    <td class="nowrap">${esc(dateTime(o.fecha_exacta))}</td>
    <td>${esc(o.nombre_completo)}</td>
    <td>${esc(o.nombre_sucursal)}</td>
    ${withProducts ? `<td class="num">${o.num_productos}</td>` : ""}
    <td class="num strong">${esc(money(o.total))}</td>
    <td class="num"><span class="points">${int(o.puntos_ganados)}</span></td>
    <td class="actions"><button type="button" class="btn btn-sm" data-view-order="${o.pedido_id}">Ver<span class="sr-only"> pedido ${o.pedido_id}</span></button></td>
  </tr>`;
}
