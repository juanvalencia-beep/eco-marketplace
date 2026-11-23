// Orders page:
//  1. the "cart" form: choose customer + store, add product lines, place the order once
//  2. the order history table with customer/store filters
//  3. the order drawer: change the date, edit/remove/add lines, cancel the order
//
// Prices shown in the cart are only a preview: the API copies the current product
// price into each order line and calculates totals and points itself.

/* ============================== cart ============================== */

const cart = {
  lines: [], // [{ producto_id, cantidad_comprada }]
  stock: new Map(), // producto_id -> inventory row of the chosen store
};

async function loadOrdersPage() {
  try {
    await loadLookups();
  } catch (err) {
    showError(err);
  }
  fillSelect($("#cart-customer"), customerOptions("Elija un cliente"));
  fillSelect($("#cart-store"), storeOptions("Elija una tienda"));
  fillSelect($("#orders-filter-customer"), customerOptions("Todos los clientes"));
  fillSelect($("#orders-filter-store"), storeOptions("Todas las tiendas"));
  await loadCartStock();
  loadOrders();
}

// Loads the stock of the chosen store, so the cart can show what is available
async function loadCartStock() {
  const storeId = $("#cart-store").value;
  cart.stock = new Map();
  if (storeId) {
    try {
      const rows = await api.get("/inventario?tienda_id=" + storeId);
      rows.forEach((r) => cart.stock.set(r.producto_id, r));
    } catch (err) {
      showError(err);
    }
  }
  $("#cart-add").disabled = !storeId;
  renderProductPicker();
  renderCart();
}

// Product select: only products stocked at the store and not already in the cart
function renderProductPicker() {
  const select = $("#cart-product");
  const inCart = new Set(cart.lines.map((l) => l.producto_id));
  const options = lookups.products.map((p) => {
    const row = cart.stock.get(p.producto_id);
    const usable = row && row.cantidad_stock > 0 && !inCart.has(p.producto_id);
    const note = !row ? "no disponible en esta tienda" : inCart.has(p.producto_id) ? "ya está en el pedido" : row.cantidad_stock > 0 ? `quedan ${qty(row.cantidad_stock)} ${unitFor(row.cantidad_stock, p.unidad_medida)}` : "agotado";
    return `<option value="${p.producto_id}" ${usable ? "" : "disabled"}>${esc(p.nombre)}, ${esc(money(p.precio_unitario))}/${esc(perUnit(p.unidad_medida))} (${esc(note)})</option>`;
  });
  fillSelect(select, `<option value="">${$("#cart-store").value ? "Elija un producto" : "Primero elija una tienda"}</option>` + options.join(""));
  if (select.selectedOptions[0]?.disabled) select.value = "";
  updateAddHint();
}

function updateAddHint() {
  const product = findProduct($("#cart-product").value);
  $("#cart-unit").textContent = product ? product.unidad_medida : "";
  const hint = $("#cart-hint");
  hint.classList.remove("is-error");
  if (!$("#cart-store").value) {
    hint.textContent = "Elija una tienda para ver los productos que tiene en stock.";
  } else if (!product) {
    hint.textContent = cart.stock.size ? "Elija un producto y una cantidad, y luego agregue la línea." : "Esta tienda aún no tiene productos en stock.";
  } else {
    const row = cart.stock.get(product.producto_id);
    const q = Number($("#cart-qty").value);
    hint.textContent = `Disponible: ${qty(row.cantidad_stock)} ${unitFor(row.cantidad_stock, product.unidad_medida)} a ${money(product.precio_unitario)} por ${perUnit(product.unidad_medida)}.` +
      (q > 0 ? ` Esta línea: ${money(lineSubtotal(q, product.precio_unitario))}, ${plural(pointsFor(q), "eco-punto")}.` : "");
  }
}

function addCartLine() {
  const product = findProduct($("#cart-product").value);
  const q = Number($("#cart-qty").value);
  const hint = $("#cart-hint");
  const fail = (text, focus) => {
    hint.textContent = text;
    hint.classList.add("is-error");
    focus.focus();
  };
  if (!product) return fail("Primero elija un producto.", $("#cart-product"));
  if (!(q > 0)) return fail("Ingrese una cantidad mayor que 0.", $("#cart-qty"));
  const available = cart.stock.get(product.producto_id).cantidad_stock;
  if (q > available) return fail(`Solo hay ${qty(available)} ${unitFor(available, product.unidad_medida)} de ${product.nombre} disponibles en esta tienda.`, $("#cart-qty"));

  cart.lines.push({ producto_id: product.producto_id, cantidad_comprada: Math.round(q * 100) / 100 });
  $("#cart-qty").value = "";
  $("#cart-product").value = "";
  renderProductPicker();
  renderCart();
  $("#cart-product").focus();
}

function renderCart() {
  const body = $("#cart-body");
  if (!cart.lines.length) {
    body.innerHTML = emptyRow(7, "Aún no hay líneas", $("#cart-store").value ? "Agregue productos arriba. Cada producto puede aparecer una sola vez por pedido." : "Elija un cliente y una tienda, y luego agregue productos.");
  } else {
    body.innerHTML = cart.lines
      .map((line, i) => {
        const p = findProduct(line.producto_id);
        const row = cart.stock.get(line.producto_id);
        const available = row ? row.cantidad_stock : 0;
        return `<tr data-index="${i}">
          <td class="strong">${esc(p.nombre)}</td>
          <td class="num nowrap" data-label="Precio unitario"><span>${esc(money(p.precio_unitario))} <span class="muted">/ ${esc(perUnit(p.unidad_medida))}</span></span></td>
          <td class="num nowrap" data-label="En stock"><span>${esc(qty(available))} <span class="muted">${esc(unitFor(available, p.unidad_medida))}</span></span></td>
          <td class="num" data-label="Cantidad">
            <input type="number" class="qty-input" min="0.01" step="0.01" inputmode="decimal" value="${line.cantidad_comprada}"
              aria-label="Cantidad de ${esc(p.nombre)}">
          </td>
          <td class="num strong" data-cell="subtotal" data-label="Subtotal"></td>
          <td class="num" data-cell="points" data-label="Eco-puntos"></td>
          <td class="actions">
            <button type="button" class="icon-btn icon-btn-danger" data-remove="${i}" aria-label="Quitar ${esc(p.nombre)}">
              <svg class="icon"><use href="#i-trash"/></svg>
            </button>
          </td>
        </tr>`;
      })
      .join("");
    $$("tr[data-index]", body).forEach(updateCartRow);
  }
  updateSummary();
}

// Recalculates one line (called while typing, so the input keeps its focus)
function updateCartRow(tr) {
  const line = cart.lines[Number(tr.dataset.index)];
  const p = findProduct(line.producto_id);
  const row = cart.stock.get(line.producto_id);
  const available = row ? row.cantidad_stock : 0;
  const tooMuch = line.cantidad_comprada > available;
  const invalid = !(line.cantidad_comprada > 0) || tooMuch;
  tr.classList.toggle("is-invalid", invalid);
  tr.querySelector(".qty-input").setAttribute("aria-invalid", invalid);
  tr.querySelector('[data-cell="subtotal"]').textContent = money(lineSubtotal(line.cantidad_comprada || 0, p.precio_unitario));
  tr.querySelector('[data-cell="points"]').innerHTML = `<span class="points">${int(pointsFor(line.cantidad_comprada || 0))}</span>`;
  tr.title = tooMuch ? `Solo hay ${qty(available)} ${unitFor(available, p.unidad_medida)} disponibles` : "";
}

function updateSummary() {
  const customer = lookups.customers.find((c) => c.cliente_id === Number($("#cart-customer").value));
  const store = lookups.stores.find((s) => s.tienda_id === Number($("#cart-store").value));
  let total = 0;
  let points = 0;
  let valid = true;
  for (const line of cart.lines) {
    const p = findProduct(line.producto_id);
    const row = cart.stock.get(line.producto_id);
    total += lineSubtotal(line.cantidad_comprada || 0, p.precio_unitario);
    points += pointsFor(line.cantidad_comprada || 0);
    if (!(line.cantidad_comprada > 0) || !row || line.cantidad_comprada > row.cantidad_stock) valid = false;
  }
  $("#sum-customer").textContent = customer ? customer.nombre_completo : "Sin elegir";
  $("#sum-store").textContent = store ? store.nombre_sucursal : "Sin elegir";
  $("#sum-lines").textContent = cart.lines.length;
  $("#sum-total").textContent = money(total);
  $("#sum-points").textContent = int(points);
  $("#cart-submit").disabled = !(customer && store && cart.lines.length && valid);
  $("#cart-clear").disabled = !cart.lines.length;
}

$("#cart-customer").addEventListener("change", updateSummary);
$("#cart-store").addEventListener("change", loadCartStock);
$("#cart-product").addEventListener("change", updateAddHint);
$("#cart-qty").addEventListener("input", updateAddHint);
$("#cart-add-btn").addEventListener("click", addCartLine);
$("#cart-qty").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault(); // Enter adds the line instead of submitting the order
    addCartLine();
  }
});

$("#cart-body").addEventListener("input", (e) => {
  if (!e.target.classList.contains("qty-input")) return;
  const tr = e.target.closest("tr");
  cart.lines[Number(tr.dataset.index)].cantidad_comprada = Number(e.target.value);
  updateCartRow(tr);
  updateSummary();
});

$("#cart-body").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-remove]");
  if (!btn) return;
  cart.lines.splice(Number(btn.dataset.remove), 1);
  renderProductPicker();
  renderCart();
  $("#cart-product").focus();
});

$("#cart-clear").addEventListener("click", () => {
  cart.lines = [];
  renderProductPicker();
  renderCart();
});

$("#cart-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    cliente_id: Number($("#cart-customer").value),
    tienda_id: Number($("#cart-store").value),
    detalles: cart.lines.map((l) => ({ producto_id: l.producto_id, cantidad_comprada: l.cantidad_comprada })),
  };
  await busy($("#cart-submit"), async () => {
    try {
      const order = await api.post("/pedidos", body);
      toast(`Pedido #${order.pedido_id} registrado: ${money(order.total)}. ${order.nombre_completo} ganó ${plural(order.puntos_ganados, "eco-punto")}.`);
      cart.lines = [];
      await loadLookups(); // customer points changed
      fillSelect($("#cart-customer"), customerOptions("Elija un cliente"));
      await loadCartStock(); // stock changed
      loadOrders();
    } catch (err) {
      showError(err);
    }
  });
  updateSummary();
});

/* ============================== order history ============================== */

async function loadOrders() {
  const params = new URLSearchParams();
  if ($("#orders-filter-customer").value) params.set("cliente_id", $("#orders-filter-customer").value);
  if ($("#orders-filter-store").value) params.set("tienda_id", $("#orders-filter-store").value);
  const filtered = params.toString() !== "";

  loadingRows($("#orders-body"), 8, 6);
  try {
    const orders = await api.get("/pedidos" + (filtered ? "?" + params : ""));
    const total = orders.reduce((sum, o) => sum + o.total, 0);
    $("#orders-count").textContent = `${plural(orders.length, "pedido")}, ${money(total)}${filtered ? " (filtrado)" : ""}, más recientes primero`;
    setRows(
      $("#orders-body"),
      orders.length
        ? orders.map((o) => orderRow(o, true)).join("")
        : filtered
          ? emptyRow(8, "Ningún pedido coincide con estos filtros", "Elija “Todos los clientes” o “Todas las tiendas” para ampliar la lista.")
          : emptyRow(8, "Aún no hay pedidos", "Registre el primero con el formulario de arriba.")
    );
  } catch (err) {
    showError(err);
    setRows($("#orders-body"), emptyRow(8, "No se pudieron cargar los pedidos", esc(err.message)));
  }
}

$("#orders-filter-customer").addEventListener("change", loadOrders);
$("#orders-filter-store").addEventListener("change", loadOrders);

// Any "View" button anywhere (dashboard, orders, customer history) opens the drawer
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-view-order]");
  if (!btn) return;
  const history = btn.closest("#history-dialog");
  if (history) closeDialog(history);
  openOrder(Number(btn.dataset.viewOrder));
});

/* ============================== order drawer ============================== */

let currentOrder = null;
let drawerStock = new Map(); // stock of the order's store, for the "add product" select

async function openOrder(id) {
  try {
    const order = await api.get("/pedidos/" + id);
    const stock = await api.get("/inventario?tienda_id=" + order.tienda_id);
    currentOrder = order;
    drawerStock = new Map(stock.map((r) => [r.producto_id, r]));
    if (!lookups.products.length) await loadLookups();
    renderDrawer();
    const drawer = $("#order-drawer");
    if (!drawer.open) {
      drawer.showModal();
      $("#drawer-body").scrollTop = 0;
    }
  } catch (err) {
    showError(err);
  }
}

function renderDrawer() {
  const o = currentOrder;
  $("#drawer-title").textContent = `Pedido #${o.pedido_id}`;
  $("#drawer-sub").textContent = `${o.nombre_completo} en ${o.nombre_sucursal}`;
  const onlyOne = o.detalles.length === 1;
  const inOrder = new Set(o.detalles.map((d) => d.producto_id));

  const addOptions = lookups.products
    .filter((p) => !inOrder.has(p.producto_id))
    .map((p) => {
      const row = drawerStock.get(p.producto_id);
      const usable = row && row.cantidad_stock > 0;
      const note = !row ? "no disponible en esta tienda" : usable ? `quedan ${qty(row.cantidad_stock)} ${unitFor(row.cantidad_stock, p.unidad_medida)}` : "agotado";
      return `<option value="${p.producto_id}" ${usable ? "" : "disabled"}>${esc(p.nombre)}, ${esc(money(p.precio_unitario))}/${esc(perUnit(p.unidad_medida))} (${esc(note)})</option>`;
    })
    .join("");

  $("#drawer-body").innerHTML = `
    <section class="drawer-section">
      <dl class="facts">
        <div><dt>Cliente</dt><dd>${esc(o.nombre_completo)}</dd></div>
        <div><dt>Tienda</dt><dd>${esc(o.nombre_sucursal)}</dd></div>
        <div><dt>Total</dt><dd class="fact-big">${esc(money(o.total))}</dd></div>
        <div><dt>Eco-puntos</dt><dd class="fact-big points-text">${int(o.puntos_ganados)}</dd></div>
      </dl>
    </section>

    <form class="drawer-section date-form" id="date-form">
      <label class="field grow">Fecha y hora del pedido
        <input type="datetime-local" step="1" id="order-date" value="${esc(o.fecha_exacta.slice(0, 19))}" required>
      </label>
      <button type="submit" class="btn">Guardar fecha</button>
    </form>

    <section class="drawer-section">
      <h3>Productos <span class="muted">${o.num_productos} ${o.num_productos === 1 ? "línea" : "líneas"}, cantidad total ${esc(qty(o.cantidad_total))}</span></h3>
      <div class="table-wrap">
        <table class="lines-table stack-mobile">
          <thead>
            <tr><th>Producto</th><th class="num">Cantidad</th><th class="num">Precio</th><th class="num">Subtotal</th><th class="num">Puntos</th><th class="actions"><span class="sr-only">Acciones</span></th></tr>
          </thead>
          <tbody>
            ${o.detalles
              .map(
                (d) => `<tr data-producto="${d.producto_id}" data-name="${esc(d.nombre_producto)}">
                  <td><span class="strong">${esc(d.nombre_producto)}</span><span class="cell-sub">${esc(d.unidad_medida)}</span></td>
                  <td class="num" data-label="Cantidad">
                    <input type="number" class="qty-input" min="0.01" step="0.01" inputmode="decimal" value="${d.cantidad_comprada}"
                      data-original="${d.cantidad_comprada}" aria-label="Cantidad de ${esc(d.nombre_producto)} en ${esc(d.unidad_medida)}">
                  </td>
                  <td class="num nowrap" data-label="Precio">${esc(money(d.precio_unitario))}</td>
                  <td class="num strong nowrap" data-label="Subtotal">${esc(money(d.subtotal))}</td>
                  <td class="num" data-label="Eco-puntos"><span class="points">${int(d.puntos)}</span></td>
                  <td class="actions nowrap">
                    <button type="button" class="btn btn-sm" data-line="save" disabled>Guardar</button>
                    <button type="button" class="icon-btn icon-btn-danger" data-line="remove" ${onlyOne ? "disabled" : ""}
                      aria-label="Quitar ${esc(d.nombre_producto)}" title="${onlyOne ? "Un pedido necesita al menos un producto" : "Quitar línea"}">
                      <svg class="icon"><use href="#i-trash"/></svg>
                    </button>
                  </td>
                </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
      ${onlyOne ? '<p class="hint">Es el único producto, así que no se puede quitar. Si es necesario, anule el pedido.</p>' : ""}
      <p class="hint">Los precios quedaron fijos al registrar el pedido. Las líneas nuevas usan el precio actual.</p>
    </section>

    <form class="drawer-section add-line" id="add-line-form">
      <h3>Agregar un producto</h3>
      <div class="field-row">
        <label class="field grow">Producto
          <select name="producto_id" required>
            <option value="">${addOptions ? "Elija un producto" : "Todos los productos ya están en este pedido"}</option>${addOptions}
          </select>
        </label>
        <label class="field field-qty">Cantidad
          <input name="cantidad_comprada" type="number" min="0.01" step="0.01" inputmode="decimal" required placeholder="0,00">
        </label>
        <button type="submit" class="btn"><svg class="icon"><use href="#i-plus"/></svg>Agregar línea</button>
      </div>
    </form>

    <section class="drawer-section danger-zone">
      <div>
        <h3>Anular pedido</h3>
        <p class="hint">El stock vuelve a ${esc(o.nombre_sucursal)} y se le descuentan ${plural(o.puntos_ganados, "eco-punto")} a ${esc(o.nombre_completo)}.</p>
      </div>
      <button type="button" class="btn btn-danger" id="cancel-order">Anular pedido</button>
    </section>`;
}

// After a change: reload the order in the drawer and refresh the page behind it
async function afterOrderChange() {
  await openOrder(currentOrder.pedido_id);
  refreshBehindDrawer();
}

function refreshBehindDrawer() {
  const page = currentPage();
  if (page === "orders") {
    loadOrders();
    loadLookups().then(loadCartStock).catch(() => {});
  } else if (page === "dashboard") {
    loadDashboard();
  } else if (page === "customers") {
    loadCustomers();
  }
}

$("#drawer-body").addEventListener("input", (e) => {
  if (!e.target.classList.contains("qty-input")) return;
  const input = e.target;
  const changed = Number(input.value) > 0 && Number(input.value) !== Number(input.dataset.original);
  input.closest("tr").querySelector('[data-line="save"]').disabled = !changed;
});

$("#drawer-body").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.classList.contains("qty-input")) {
    e.preventDefault();
    e.target.closest("tr").querySelector('[data-line="save"]').click();
  }
});

$("#drawer-body").addEventListener("click", async (e) => {
  const lineBtn = e.target.closest("[data-line]");
  if (lineBtn) {
    const tr = lineBtn.closest("tr");
    const productId = tr.dataset.producto;
    const path = `/pedidos/${currentOrder.pedido_id}/detalles/${productId}`;
    const name = tr.dataset.name;

    if (lineBtn.dataset.line === "save") {
      const value = Number(tr.querySelector(".qty-input").value);
      await busy(lineBtn, async () => {
        try {
          const line = await api.put(path, { cantidad_comprada: value });
          toast(`${name}: cantidad cambiada a ${qty(line.cantidad_comprada)} ${unitFor(line.cantidad_comprada, line.unidad_medida)}.`);
          await afterOrderChange();
        } catch (err) {
          showError(err);
        }
      });
    } else {
      const ok = await confirmAction(`¿Quitar ${name} del pedido #${currentOrder.pedido_id}? Su stock vuelve a la tienda.`, {
        title: "Quitar producto",
        yes: "Quitar producto",
      });
      if (!ok) return;
      try {
        await api.del(path);
        toast(`${name} se quitó del pedido #${currentOrder.pedido_id}.`);
        await afterOrderChange();
      } catch (err) {
        showError(err);
      }
    }
    return;
  }

  if (e.target.closest("#cancel-order")) {
    const o = currentOrder;
    const ok = await confirmAction(
      `¿Anular el pedido #${o.pedido_id} (${money(o.total)})? El stock vuelve a ${o.nombre_sucursal} y se le descuentan ${plural(o.puntos_ganados, "eco-punto")} a ${o.nombre_completo}.`,
      { title: "Anular pedido", yes: "Anular pedido" }
    );
    if (!ok) return;
    try {
      await api.del("/pedidos/" + o.pedido_id);
      closeDialog($("#order-drawer"));
      toast(`Pedido #${o.pedido_id} anulado.`);
      refreshBehindDrawer();
    } catch (err) {
      showError(err);
    }
  }
});

$("#drawer-body").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }
  const button = form.querySelector('[type="submit"]');

  if (form.id === "date-form") {
    await busy(button, async () => {
      try {
        await api.put("/pedidos/" + currentOrder.pedido_id, { fecha_exacta: $("#order-date").value });
        toast(`Fecha del pedido #${currentOrder.pedido_id} guardada.`);
        await afterOrderChange();
      } catch (err) {
        showError(err);
      }
    });
  } else if (form.id === "add-line-form") {
    const data = formData(form);
    await busy(button, async () => {
      try {
        const line = await api.post(`/pedidos/${currentOrder.pedido_id}/detalles`, {
          producto_id: Number(data.producto_id),
          cantidad_comprada: Number(data.cantidad_comprada),
        });
        toast(`${line.nombre_producto} agregado: ${qty(line.cantidad_comprada)} ${unitFor(line.cantidad_comprada, line.unidad_medida)}, +${plural(line.puntos, "eco-punto")}.`);
        await afterOrderChange();
      } catch (err) {
        showError(err);
      }
    });
  }
});
