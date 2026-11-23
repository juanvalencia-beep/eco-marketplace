// Orders page:
//  1. the "cart" form: choose customer + store, add product lines, place the order once
//  2. the order history table with customer/store filters
//  3. the order drawer: change the date, edit/remove/add lines, cancel the order
//
// Prices shown in the cart are only a preview: the API copies the current product
// price into each order line and calculates totals and points itself.

/* ============================== cart ============================== */

const cart = {
  lines: [], // [{ producto_id, cantidad }]
  stock: new Map(), // producto_id -> inventory row of the chosen store
};

async function loadOrdersPage() {
  try {
    await loadLookups();
  } catch (err) {
    showError(err);
  }
  fillSelect($("#cart-customer"), customerOptions("Choose a customer"));
  fillSelect($("#cart-store"), storeOptions("Choose a store"));
  fillSelect($("#orders-filter-customer"), customerOptions("All customers"));
  fillSelect($("#orders-filter-store"), storeOptions("All stores"));
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
    const note = !row ? "not stocked here" : inCart.has(p.producto_id) ? "in the order" : row.cantidad_stock > 0 ? `${qty(row.cantidad_stock)} ${p.unidad_medida} left` : "out of stock";
    return `<option value="${p.producto_id}" ${usable ? "" : "disabled"}>${esc(p.nombre)}, ${esc(money(p.precio_unitario))}/${esc(p.unidad_medida)} (${esc(note)})</option>`;
  });
  fillSelect(select, `<option value="">${$("#cart-store").value ? "Choose a product" : "Choose a store first"}</option>` + options.join(""));
  if (select.selectedOptions[0]?.disabled) select.value = "";
  updateAddHint();
}

function updateAddHint() {
  const product = findProduct($("#cart-product").value);
  $("#cart-unit").textContent = product ? product.unidad_medida : "";
  const hint = $("#cart-hint");
  hint.classList.remove("is-error");
  if (!$("#cart-store").value) {
    hint.textContent = "Choose a store to see the products it stocks.";
  } else if (!product) {
    hint.textContent = cart.stock.size ? "Pick a product and a quantity, then add the line." : "This store has no products in stock yet.";
  } else {
    const row = cart.stock.get(product.producto_id);
    const q = Number($("#cart-qty").value);
    hint.textContent = `${qty(row.cantidad_stock)} ${product.unidad_medida} available at ${money(product.precio_unitario)} per ${product.unidad_medida}.` +
      (q > 0 ? ` This line: ${money(lineSubtotal(q, product.precio_unitario))}, ${plural(pointsFor(q), "eco-point")}.` : "");
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
  if (!product) return fail("Choose a product first.", $("#cart-product"));
  if (!(q > 0)) return fail("Enter a quantity greater than 0.", $("#cart-qty"));
  const available = cart.stock.get(product.producto_id).cantidad_stock;
  if (q > available) return fail(`Only ${qty(available)} ${product.unidad_medida} of ${product.nombre} available here.`, $("#cart-qty"));

  cart.lines.push({ producto_id: product.producto_id, cantidad: Math.round(q * 100) / 100 });
  $("#cart-qty").value = "";
  $("#cart-product").value = "";
  renderProductPicker();
  renderCart();
  $("#cart-product").focus();
}

function renderCart() {
  const body = $("#cart-body");
  if (!cart.lines.length) {
    body.innerHTML = emptyRow(7, "No lines yet", $("#cart-store").value ? "Add products above. Each product can appear once per order." : "Choose a customer and a store, then add products.");
  } else {
    body.innerHTML = cart.lines
      .map((line, i) => {
        const p = findProduct(line.producto_id);
        const row = cart.stock.get(line.producto_id);
        const available = row ? row.cantidad_stock : 0;
        return `<tr data-index="${i}">
          <td class="strong">${esc(p.nombre)}</td>
          <td class="num nowrap" data-label="Unit price"><span>${esc(money(p.precio_unitario))} <span class="muted">/ ${esc(p.unidad_medida)}</span></span></td>
          <td class="num nowrap" data-label="In stock"><span>${esc(qty(available))} <span class="muted">${esc(p.unidad_medida)}</span></span></td>
          <td class="num" data-label="Quantity">
            <input type="number" class="qty-input" min="0.01" step="0.01" inputmode="decimal" value="${line.cantidad}"
              aria-label="Quantity of ${esc(p.nombre)}">
          </td>
          <td class="num strong" data-cell="subtotal" data-label="Subtotal"></td>
          <td class="num" data-cell="points" data-label="Eco-points"></td>
          <td class="actions">
            <button type="button" class="icon-btn icon-btn-danger" data-remove="${i}" aria-label="Remove ${esc(p.nombre)}">
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
  const tooMuch = line.cantidad > available;
  const invalid = !(line.cantidad > 0) || tooMuch;
  tr.classList.toggle("is-invalid", invalid);
  tr.querySelector(".qty-input").setAttribute("aria-invalid", invalid);
  tr.querySelector('[data-cell="subtotal"]').textContent = money(lineSubtotal(line.cantidad || 0, p.precio_unitario));
  tr.querySelector('[data-cell="points"]').innerHTML = `<span class="points">${int(pointsFor(line.cantidad || 0))}</span>`;
  tr.title = tooMuch ? `Only ${qty(available)} ${p.unidad_medida} available` : "";
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
    total += lineSubtotal(line.cantidad || 0, p.precio_unitario);
    points += pointsFor(line.cantidad || 0);
    if (!(line.cantidad > 0) || !row || line.cantidad > row.cantidad_stock) valid = false;
  }
  $("#sum-customer").textContent = customer ? customer.nombre_completo : "Not chosen";
  $("#sum-store").textContent = store ? store.nombre_sucursal : "Not chosen";
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
  cart.lines[Number(tr.dataset.index)].cantidad = Number(e.target.value);
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
    detalles: cart.lines.map((l) => ({ producto_id: l.producto_id, cantidad: l.cantidad })),
  };
  await busy($("#cart-submit"), async () => {
    try {
      const order = await api.post("/pedidos", body);
      toast(`Order #${order.pedido_id} placed: ${money(order.total)}. ${order.nombre_completo} earned ${plural(order.puntos_ganados, "eco-point")}.`);
      cart.lines = [];
      await loadLookups(); // customer points changed
      fillSelect($("#cart-customer"), customerOptions("Choose a customer"));
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
    $("#orders-count").textContent = `${plural(orders.length, "order")}, ${money(total)}${filtered ? " (filtered)" : ""}, newest first`;
    setRows(
      $("#orders-body"),
      orders.length
        ? orders.map((o) => orderRow(o, true)).join("")
        : filtered
          ? emptyRow(8, "No orders match these filters", "Choose “All customers” or “All stores” to widen the list.")
          : emptyRow(8, "No orders yet", "Place the first one with the form above.")
    );
  } catch (err) {
    showError(err);
    setRows($("#orders-body"), emptyRow(8, "Could not load orders", esc(err.message)));
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
  $("#drawer-title").textContent = `Order #${o.pedido_id}`;
  $("#drawer-sub").textContent = `${o.nombre_completo} at ${o.nombre_sucursal}`;
  const onlyOne = o.detalles.length === 1;
  const inOrder = new Set(o.detalles.map((d) => d.producto_id));

  const addOptions = lookups.products
    .filter((p) => !inOrder.has(p.producto_id))
    .map((p) => {
      const row = drawerStock.get(p.producto_id);
      const usable = row && row.cantidad_stock > 0;
      const note = !row ? "not stocked here" : usable ? `${qty(row.cantidad_stock)} ${p.unidad_medida} left` : "out of stock";
      return `<option value="${p.producto_id}" ${usable ? "" : "disabled"}>${esc(p.nombre)}, ${esc(money(p.precio_unitario))}/${esc(p.unidad_medida)} (${esc(note)})</option>`;
    })
    .join("");

  $("#drawer-body").innerHTML = `
    <section class="drawer-section">
      <dl class="facts">
        <div><dt>Customer</dt><dd>${esc(o.nombre_completo)}</dd></div>
        <div><dt>Store</dt><dd>${esc(o.nombre_sucursal)}</dd></div>
        <div><dt>Total</dt><dd class="fact-big">${esc(money(o.total))}</dd></div>
        <div><dt>Eco-points</dt><dd class="fact-big points-text">${int(o.puntos_ganados)}</dd></div>
      </dl>
    </section>

    <form class="drawer-section date-form" id="date-form">
      <label class="field grow">Order date and time
        <input type="datetime-local" step="1" id="order-date" value="${esc(o.fecha_exacta.slice(0, 19))}" required>
      </label>
      <button type="submit" class="btn">Save date</button>
    </form>

    <section class="drawer-section">
      <h3>Products <span class="muted">${o.num_productos} ${o.num_productos === 1 ? "line" : "lines"}, ${esc(qty(o.cantidad_total))} units</span></h3>
      <div class="table-wrap">
        <table class="lines-table stack-mobile">
          <thead>
            <tr><th>Product</th><th class="num">Quantity</th><th class="num">Price</th><th class="num">Subtotal</th><th class="num">Points</th><th class="actions"><span class="sr-only">Actions</span></th></tr>
          </thead>
          <tbody>
            ${o.detalles
              .map(
                (d) => `<tr data-producto="${d.producto_id}" data-name="${esc(d.nombre_producto)}">
                  <td><span class="strong">${esc(d.nombre_producto)}</span><span class="cell-sub">${esc(d.unidad_medida)}</span></td>
                  <td class="num" data-label="Quantity">
                    <input type="number" class="qty-input" min="0.01" step="0.01" inputmode="decimal" value="${d.cantidad}"
                      data-original="${d.cantidad}" aria-label="Quantity of ${esc(d.nombre_producto)} in ${esc(d.unidad_medida)}">
                  </td>
                  <td class="num nowrap" data-label="Price">${esc(money(d.precio_unitario))}</td>
                  <td class="num strong nowrap" data-label="Subtotal">${esc(money(d.subtotal))}</td>
                  <td class="num" data-label="Eco-points"><span class="points">${int(d.puntos)}</span></td>
                  <td class="actions nowrap">
                    <button type="button" class="btn btn-sm" data-line="save" disabled>Save</button>
                    <button type="button" class="icon-btn icon-btn-danger" data-line="remove" ${onlyOne ? "disabled" : ""}
                      aria-label="Remove ${esc(d.nombre_producto)}" title="${onlyOne ? "An order needs at least one product" : "Remove line"}">
                      <svg class="icon"><use href="#i-trash"/></svg>
                    </button>
                  </td>
                </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
      ${onlyOne ? '<p class="hint">This is the only product, so it can’t be removed. Cancel the order instead.</p>' : ""}
      <p class="hint">Prices were fixed when the order was placed. New lines use today’s price.</p>
    </section>

    <form class="drawer-section add-line" id="add-line-form">
      <h3>Add a product</h3>
      <div class="field-row">
        <label class="field grow">Product
          <select name="producto_id" required>
            <option value="">${addOptions ? "Choose a product" : "Every product is already in this order"}</option>${addOptions}
          </select>
        </label>
        <label class="field field-qty">Quantity
          <input name="cantidad" type="number" min="0.01" step="0.01" inputmode="decimal" required placeholder="0.00">
        </label>
        <button type="submit" class="btn"><svg class="icon"><use href="#i-plus"/></svg>Add line</button>
      </div>
    </form>

    <section class="drawer-section danger-zone">
      <div>
        <h3>Cancel order</h3>
        <p class="hint">Stock returns to ${esc(o.nombre_sucursal)} and ${plural(o.puntos_ganados, "eco-point")} are taken back from ${esc(o.nombre_completo)}.</p>
      </div>
      <button type="button" class="btn btn-danger" id="cancel-order">Cancel order</button>
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
          const line = await api.put(path, { cantidad: value });
          toast(`${name} changed to ${qty(line.cantidad)} ${line.unidad_medida}.`);
          await afterOrderChange();
        } catch (err) {
          showError(err);
        }
      });
    } else {
      const ok = await confirmAction(`Remove ${name} from order #${currentOrder.pedido_id}? Its stock goes back to the store.`, {
        title: "Remove product",
        yes: "Remove product",
      });
      if (!ok) return;
      try {
        await api.del(path);
        toast(`${name} removed from order #${currentOrder.pedido_id}.`);
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
      `Cancel order #${o.pedido_id} (${money(o.total)})? The stock goes back to ${o.nombre_sucursal} and ${plural(o.puntos_ganados, "eco-point")} are removed from ${o.nombre_completo}.`,
      { title: "Cancel order", yes: "Cancel order" }
    );
    if (!ok) return;
    try {
      await api.del("/pedidos/" + o.pedido_id);
      closeDialog($("#order-drawer"));
      toast(`Order #${o.pedido_id} cancelled.`);
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
        toast(`Order #${currentOrder.pedido_id} date saved.`);
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
          cantidad: Number(data.cantidad),
        });
        toast(`${line.nombre_producto} added: ${qty(line.cantidad)} ${line.unidad_medida}, +${plural(line.puntos, "eco-point")}.`);
        await afterOrderChange();
      } catch (err) {
        showError(err);
      }
    });
  }
});
