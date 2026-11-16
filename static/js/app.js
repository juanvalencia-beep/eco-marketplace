const $ = (selector) => document.querySelector(selector);

// Lists we keep in memory to fill the selects and find rows by id
let customers = [];
let stores = [];
let products = [];

const LOW_STOCK = 10;

function esc(value) {
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(value ?? "").replace(/[&<>"']/g, (c) => map[c]);
}

function num(value) {
  return Number(value).toFixed(2);
}

function formatDate(value) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

function emptyRow(cols, text) {
  return `<tr><td colspan="${cols}" class="empty">${text}</td></tr>`;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

/* ---------- messages and dialogs ---------- */

let messageTimer = null;

function showMessage(text, type = "success") {
  $("#message-text").textContent = text;
  $("#message").className = "message " + type;
  $("#message").hidden = false;
  clearTimeout(messageTimer);
  messageTimer = setTimeout(() => ($("#message").hidden = true), type === "error" ? 7000 : 4000);
}

function showError(err) {
  showMessage(err.message, "error");
}

$("#message-close").addEventListener("click", () => ($("#message").hidden = true));

function confirmAction(text, yesLabel = "Yes, delete") {
  const dialog = $("#confirm-dialog");
  $("#confirm-text").textContent = text;
  $("#confirm-yes").textContent = yesLabel;
  dialog.returnValue = "";
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "yes"), { once: true });
  });
}

// Edit dialog shared by customers, stores and products.
// fields: [{ name, label, type }], save: async function that receives the form values
let editSave = null;

function openEdit(title, fields, values, save) {
  $("#edit-title").textContent = title;
  $("#edit-fields").innerHTML = fields
    .map((f) => {
      const extra = f.type === "number" ? 'min="0" step="1"' : "";
      return `<label>${f.label}
        <input name="${f.name}" type="${f.type || "text"}" value="${esc(values[f.name])}" ${extra} ${f.list ? `list="${f.list}"` : ""} required>
      </label>`;
    })
    .join("");
  $("#edit-error").hidden = true;
  editSave = save;
  $("#edit-dialog").showModal();
  $("#edit-fields input").focus();
}

$("#edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await editSave(formData(e.target));
    $("#edit-dialog").close();
  } catch (err) {
    // the dialog sits on top of the page, so the error is shown inside it
    $("#edit-error").textContent = err.message;
    $("#edit-error").hidden = false;
  }
});

$("#edit-cancel").addEventListener("click", () => $("#edit-dialog").close());
$("#history-close").addEventListener("click", () => $("#history-dialog").close());

/* ---------- navigation ---------- */

const loaders = {
  dashboard: loadDashboard,
  customers: loadCustomers,
  stores: loadStores,
  products: loadProducts,
  inventory: loadInventoryPage,
  orders: loadOrdersPage,
};

function showSection() {
  let name = location.hash.slice(1);
  if (!loaders[name]) name = "dashboard";

  document.querySelectorAll(".section").forEach((s) => {
    s.hidden = s.id !== "section-" + name;
  });
  document.querySelectorAll(".nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.section === name);
  });
  loaders[name]();
}

window.addEventListener("hashchange", showSection);

/* ---------- dashboard ---------- */

async function loadDashboard() {
  try {
    const [summary, lowStock] = await Promise.all([api.get("/resumen"), api.get("/inventario/stock-bajo")]);

    for (const key of ["clientes", "tiendas", "productos", "pedidos", "stock_bajo"]) {
      $("#count-" + key).textContent = summary[key] ?? "-";
    }

    $("#lowstock-body").innerHTML = lowStock.length
      ? lowStock
          .map(
            (row) => `<tr class="low">
              <td>${esc(row.nombre_sucursal)}</td>
              <td>${esc(row.nombre_producto)}</td>
              <td class="num"><strong>${num(row.cantidad_stock)}</strong></td>
              <td>${esc(row.unidad_medida)}</td>
            </tr>`
          )
          .join("")
      : emptyRow(4, "All stores have enough stock.");
  } catch (err) {
    showError(err);
  }
}

/* ---------- customers ---------- */

async function loadCustomers() {
  const q = $("#customer-search").value.trim();
  const path = q ? "/clientes?q=" + encodeURIComponent(q) : "/clientes";
  try {
    const list = await api.get(path);
    if (!q) customers = list;
    renderCustomers(list);
  } catch (err) {
    showError(err);
  }
}

function renderCustomers(list) {
  $("#customers-body").innerHTML = list.length
    ? list
        .map(
          (c) => `<tr>
            <td>${c.cliente_id}</td>
            <td>${esc(c.nombre_completo)}</td>
            <td>${esc(c.correo_electronico)}</td>
            <td class="num">${c.puntos_ecologicos}</td>
            <td class="actions">
              <button class="btn btn-small" data-action="history" data-id="${c.cliente_id}">History</button>
              <button class="btn btn-small" data-action="edit" data-id="${c.cliente_id}">Edit</button>
              <button class="btn btn-small btn-danger-text" data-action="delete" data-id="${c.cliente_id}">Delete</button>
            </td>
          </tr>`
        )
        .join("")
    : emptyRow(5, "No customers found.");
}

$("#customer-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const created = await api.post("/clientes", formData(e.target));
    e.target.reset();
    showMessage(`Customer "${created.nombre_completo}" added.`);
    loadCustomers();
  } catch (err) {
    showError(err);
  }
});

let searchTimer = null;
$("#customer-search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadCustomers, 300);
});

$("#customers-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const customer = await api.get("/clientes/" + id).catch((err) => showError(err));
  if (!customer) return;

  if (btn.dataset.action === "history") {
    showHistory(customer);
  } else if (btn.dataset.action === "edit") {
    const fields = [
      { name: "nombre_completo", label: "Full name" },
      { name: "correo_electronico", label: "Email", type: "email" },
      { name: "puntos_ecologicos", label: "Eco-points", type: "number" },
    ];
    openEdit("Edit customer #" + id, fields, customer, async (data) => {
      data.puntos_ecologicos = Number(data.puntos_ecologicos);
      await api.put("/clientes/" + id, data);
      showMessage("Customer updated.");
      loadCustomers();
    });
  } else if (btn.dataset.action === "delete") {
    const ok = await confirmAction(`Delete customer "${customer.nombre_completo}"? This cannot be undone.`);
    if (!ok) return;
    try {
      await api.del("/clientes/" + id);
      showMessage("Customer deleted.");
      loadCustomers();
    } catch (err) {
      showError(err);
    }
  }
});

async function showHistory(customer) {
  try {
    const orders = await api.get(`/clientes/${customer.cliente_id}/pedidos`);
    $("#history-title").textContent = "Order history - " + customer.nombre_completo;
    $("#history-summary").textContent =
      `${orders.length} order(s). Current eco-points: ${customer.puntos_ecologicos}.`;
    $("#history-body").innerHTML = orders.length
      ? orders
          .map(
            (o) => `<tr>
              <td>${o.pedido_id}</td>
              <td>${formatDate(o.fecha_exacta)}</td>
              <td>${esc(o.nombre_sucursal)}</td>
              <td>${esc(o.nombre_producto)}</td>
              <td class="num">${num(o.cantidad_comprada)} ${esc(o.unidad_medida)}</td>
              <td class="num">${o.puntos_ganados}</td>
            </tr>`
          )
          .join("")
      : emptyRow(6, "This customer has no orders yet.");
    $("#history-dialog").showModal();
  } catch (err) {
    showError(err);
  }
}

/* ---------- stores ---------- */

async function loadStores() {
  try {
    stores = await api.get("/tiendas");
    $("#stores-body").innerHTML = stores.length
      ? stores
          .map(
            (s) => `<tr>
              <td>${s.tienda_id}</td>
              <td>${esc(s.nombre_sucursal)}</td>
              <td>${esc(s.direccion)}</td>
              <td class="actions">
                <button class="btn btn-small" data-action="edit" data-id="${s.tienda_id}">Edit</button>
                <button class="btn btn-small btn-danger-text" data-action="delete" data-id="${s.tienda_id}">Delete</button>
              </td>
            </tr>`
          )
          .join("")
      : emptyRow(4, "No stores yet.");
  } catch (err) {
    showError(err);
  }
}

$("#store-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const created = await api.post("/tiendas", formData(e.target));
    e.target.reset();
    showMessage(`Store "${created.nombre_sucursal}" added.`);
    loadStores();
  } catch (err) {
    showError(err);
  }
});

$("#stores-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const store = stores.find((s) => s.tienda_id === id);

  if (btn.dataset.action === "edit") {
    const fields = [
      { name: "nombre_sucursal", label: "Branch name" },
      { name: "direccion", label: "Address" },
    ];
    openEdit("Edit store #" + id, fields, store, async (data) => {
      await api.put("/tiendas/" + id, data);
      showMessage("Store updated.");
      loadStores();
    });
  } else if (btn.dataset.action === "delete") {
    if (!(await confirmAction(`Delete store "${store.nombre_sucursal}"?`))) return;
    try {
      await api.del("/tiendas/" + id);
      showMessage("Store deleted.");
      loadStores();
    } catch (err) {
      showError(err);
    }
  }
});

/* ---------- products ---------- */

async function loadProducts() {
  try {
    products = await api.get("/productos");
    $("#products-body").innerHTML = products.length
      ? products
          .map(
            (p) => `<tr>
              <td>${p.producto_id}</td>
              <td>${esc(p.nombre)}</td>
              <td>${esc(p.unidad_medida)}</td>
              <td class="actions">
                <button class="btn btn-small" data-action="edit" data-id="${p.producto_id}">Edit</button>
                <button class="btn btn-small btn-danger-text" data-action="delete" data-id="${p.producto_id}">Delete</button>
              </td>
            </tr>`
          )
          .join("")
      : emptyRow(4, "No products yet.");
  } catch (err) {
    showError(err);
  }
}

$("#product-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const created = await api.post("/productos", formData(e.target));
    e.target.reset();
    showMessage(`Product "${created.nombre}" added.`);
    loadProducts();
  } catch (err) {
    showError(err);
  }
});

$("#products-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const product = products.find((p) => p.producto_id === id);

  if (btn.dataset.action === "edit") {
    const fields = [
      { name: "nombre", label: "Name" },
      { name: "unidad_medida", label: "Unit", list: "unit-options" },
    ];
    openEdit("Edit product #" + id, fields, product, async (data) => {
      await api.put("/productos/" + id, data);
      showMessage("Product updated.");
      loadProducts();
    });
  } else if (btn.dataset.action === "delete") {
    if (!(await confirmAction(`Delete product "${product.nombre}"?`))) return;
    try {
      await api.del("/productos/" + id);
      showMessage("Product deleted.");
      loadProducts();
    } catch (err) {
      showError(err);
    }
  }
});

/* ---------- selects shared by inventory and orders ---------- */

async function loadLookups() {
  [customers, stores, products] = await Promise.all([
    api.get("/clientes"),
    api.get("/tiendas"),
    api.get("/productos"),
  ]);

  const storeOptions = stores.map((s) => `<option value="${s.tienda_id}">${esc(s.nombre_sucursal)}</option>`).join("");
  const productOptions = products
    .map((p) => `<option value="${p.producto_id}">${esc(p.nombre)} (${esc(p.unidad_medida)})</option>`)
    .join("");

  fillSelects(".store-select", '<option value="">Select a store</option>' + storeOptions);
  fillSelects(".product-select", '<option value="">Select a product</option>' + productOptions);
  fillSelects("#inventory-filter", '<option value="">All stores</option>' + storeOptions);
  fillSelects(
    "#order-customer",
    '<option value="">Select a customer</option>' +
      customers
        .map((c) => `<option value="${c.cliente_id}">${esc(c.nombre_completo)} (${c.puntos_ecologicos} pts)</option>`)
        .join("")
  );
}

// keeps the selected value when the options are rebuilt
function fillSelects(selector, html) {
  document.querySelectorAll(selector).forEach((select) => {
    const current = select.value;
    select.innerHTML = html;
    select.value = current;
  });
}

/* ---------- inventory ---------- */

async function loadInventoryPage() {
  try {
    await loadLookups();
    await loadInventory();
  } catch (err) {
    showError(err);
  }
}

async function loadInventory() {
  const storeId = $("#inventory-filter").value;
  try {
    const rows = await api.get("/inventario" + (storeId ? "?tienda_id=" + storeId : ""));
    $("#inventory-body").innerHTML = rows.length
      ? rows
          .map((r) => {
            const low = r.cantidad_stock < LOW_STOCK;
            return `<tr class="${low ? "low" : ""}">
              <td>${esc(r.nombre_sucursal)}</td>
              <td>${esc(r.nombre_producto)}${low ? ' <span class="tag">Low</span>' : ""}</td>
              <td class="num">
                <input type="number" class="stock-input" min="0" step="0.01" value="${num(r.cantidad_stock)}"
                  data-tienda="${r.tienda_id}" data-producto="${r.producto_id}">
              </td>
              <td>${esc(r.unidad_medida)}</td>
              <td class="actions">
                <button class="btn btn-small" data-action="save" data-tienda="${r.tienda_id}" data-producto="${r.producto_id}">Update</button>
                <button class="btn btn-small btn-danger-text" data-action="delete" data-tienda="${r.tienda_id}" data-producto="${r.producto_id}">Delete</button>
              </td>
            </tr>`;
          })
          .join("")
      : emptyRow(5, "No inventory rows for this filter.");
  } catch (err) {
    showError(err);
  }
}

$("#inventory-filter").addEventListener("change", loadInventory);

$("#inventory-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = formData(e.target);
  try {
    await api.post("/inventario", {
      tienda_id: Number(data.tienda_id),
      producto_id: Number(data.producto_id),
      cantidad_stock: Number(data.cantidad_stock),
    });
    e.target.cantidad_stock.value = "";
    showMessage("Inventory row added.");
    loadInventory();
  } catch (err) {
    showError(err);
  }
});

$("#inventory-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const { tienda, producto } = btn.dataset;
  const path = `/inventario/${tienda}/${producto}`;
  const row = btn.closest("tr");
  const label = `${row.cells[1].firstChild.textContent.trim()} at ${row.cells[0].textContent}`;

  if (btn.dataset.action === "save") {
    const input = row.querySelector(".stock-input");
    if (input.value === "") {
      showMessage("Please enter a quantity.", "error");
      return;
    }
    try {
      await api.put(path, { cantidad_stock: Number(input.value) });
      showMessage(`Stock updated: ${label}.`);
      loadInventory();
    } catch (err) {
      showError(err);
    }
  } else if (btn.dataset.action === "delete") {
    if (!(await confirmAction(`Remove ${label} from the inventory?`))) return;
    try {
      await api.del(path);
      showMessage("Inventory row deleted.");
      loadInventory();
    } catch (err) {
      showError(err);
    }
  }
});

// pressing Enter inside a stock input works like clicking "Update"
$("#inventory-body").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.classList.contains("stock-input")) {
    e.target.closest("tr").querySelector('[data-action="save"]').click();
  }
});

/* ---------- orders ---------- */

async function loadOrdersPage() {
  try {
    await loadLookups();
    updateOrderHint();
    await loadOrders();
  } catch (err) {
    showError(err);
  }
}

async function loadOrders() {
  try {
    const orders = await api.get("/pedidos");
    $("#orders-body").innerHTML = orders.length
      ? orders
          .map(
            (o) => `<tr>
              <td>${o.pedido_id}</td>
              <td>${formatDate(o.fecha_exacta)}</td>
              <td>${esc(o.nombre_completo)}</td>
              <td>${esc(o.nombre_sucursal)}</td>
              <td>${esc(o.nombre_producto)}</td>
              <td class="num">${num(o.cantidad_comprada)} ${esc(o.unidad_medida)}</td>
              <td class="num">${o.puntos_ganados}</td>
              <td class="actions">
                <button class="btn btn-small btn-danger-text" data-id="${o.pedido_id}" data-points="${o.puntos_ganados}">Cancel</button>
              </td>
            </tr>`
          )
          .join("")
      : emptyRow(8, "No orders registered yet.");
  } catch (err) {
    showError(err);
  }
}

// Shows the unit next to the quantity, the stock available and the points the order would give
async function updateOrderHint() {
  const product = products.find((p) => p.producto_id === Number($("#order-product").value));
  $("#order-unit").textContent = product ? product.unidad_medida : "";

  const storeId = $("#order-store").value;
  const productId = $("#order-product").value;
  const qty = Number($("#order-qty").value);
  const parts = [];

  if (storeId && productId) {
    try {
      // asking for the whole store avoids a 404 when the product is not stocked there
      const rows = await api.get("/inventario?tienda_id=" + storeId);
      const row = rows.find((r) => r.producto_id === Number(productId));
      parts.push(
        row
          ? `Available at this store: ${num(row.cantidad_stock)} ${row.unidad_medida}.`
          : "This store does not stock this product."
      );
    } catch (err) {
      parts.push(err.message);
    }
  }
  if (qty > 0) {
    parts.push(`This order gives ${Math.floor(qty * 10)} eco-points.`);
  }
  $("#order-hint").textContent = parts.join(" ");
}

$("#order-store").addEventListener("change", updateOrderHint);
$("#order-product").addEventListener("change", updateOrderHint);
$("#order-qty").addEventListener("input", updateOrderHint);

$("#order-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = formData(e.target);
  const body = {
    cliente_id: Number(data.cliente_id),
    tienda_id: Number(data.tienda_id),
    producto_id: Number(data.producto_id),
    cantidad_comprada: Number(data.cantidad_comprada),
  };

  try {
    const order = await api.post("/pedidos", body);
    const result = $("#order-result");
    result.innerHTML = `Order #${order.pedido_id} registered: ${num(order.cantidad_comprada)} ${esc(order.unidad_medida)}
      of ${esc(order.nombre_producto)} at ${esc(order.nombre_sucursal)}.
      <strong>${esc(order.nombre_completo)} earned ${order.puntos_ganados} eco-points.</strong>`;
    result.hidden = false;
    showMessage(`Order #${order.pedido_id} saved. +${order.puntos_ganados} eco-points.`);

    $("#order-qty").value = "";
    await loadLookups(); // customer points changed
    updateOrderHint();
    loadOrders();
  } catch (err) {
    $("#order-result").hidden = true;
    showError(err);
  }
});

$("#orders-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-id]");
  if (!btn) return;
  const id = btn.dataset.id;
  const ok = await confirmAction(
    `Cancel order #${id}? The stock goes back to the store and ${btn.dataset.points} eco-points are removed from the customer.`,
    "Yes, cancel order"
  );
  if (!ok) return;

  try {
    await api.del("/pedidos/" + id);
    showMessage(`Order #${id} cancelled.`);
    $("#order-result").hidden = true;
    await loadLookups();
    updateOrderHint();
    loadOrders();
  } catch (err) {
    showError(err);
  }
});

showSection();
