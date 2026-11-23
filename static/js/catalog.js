// CRUD pages for the basic tables: customers, stores, products and inventory.
// Each page has a create form, a list, an edit dialog and delete with confirmation.

/* ============================== customers ============================== */

async function loadCustomers() {
  const q = $("#customer-search").value.trim();
  loadingRows($("#customers-body"), 5);
  try {
    const list = await api.get(q ? "/clientes?q=" + encodeURIComponent(q) : "/clientes");
    $("#customers-count").textContent = q
      ? `${plural(list.length, "coincidencia")} para “${q}”`
      : plural(list.length, "cliente");
    setRows(
      $("#customers-body"),
      list.length
        ? list
            .map(
              (c) => `<tr>
                <td class="id">${c.cliente_id}</td>
                <td class="strong">${esc(c.nombre_completo)}</td>
                <td>${esc(c.correo_electronico)}</td>
                <td class="num"><span class="points">${int(c.puntos_ecologicos)}</span></td>
                <td class="actions">
                  <button type="button" class="btn btn-sm btn-ghost" data-action="history" data-id="${c.cliente_id}">Pedidos</button>
                  <button type="button" class="btn btn-sm" data-action="edit" data-id="${c.cliente_id}">Editar</button>
                  <button type="button" class="btn btn-sm btn-danger-text" data-action="delete" data-id="${c.cliente_id}">Eliminar</button>
                </td>
              </tr>`
            )
            .join("")
        : q
          ? emptyRow(5, "Ningún cliente coincide con esa búsqueda", "Pruebe con parte del nombre o del correo.")
          : emptyRow(5, "Aún no hay clientes", "Agregue el primero con el formulario de arriba.")
    );
  } catch (err) {
    showError(err);
    setRows($("#customers-body"), emptyRow(5, "No se pudieron cargar los clientes", esc(err.message)));
  }
}

$("#customer-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  await busy(form.querySelector("button"), async () => {
    try {
      const created = await api.post("/clientes", formData(form));
      form.reset();
      toast(`Cliente “${created.nombre_completo}” agregado.`);
      loadCustomers();
    } catch (err) {
      showError(err);
    }
  });
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
  let customer;
  try {
    customer = await api.get("/clientes/" + id);
  } catch (err) {
    showError(err);
    return;
  }

  if (btn.dataset.action === "history") {
    showHistory(customer);
  } else if (btn.dataset.action === "edit") {
    const fields = [
      { name: "nombre_completo", label: "Nombre completo", maxlength: 100 },
      { name: "correo_electronico", label: "Correo electrónico", type: "email", maxlength: 120 },
      { name: "puntos_ecologicos", label: "Eco-puntos", type: "number", min: 0, step: 1 },
    ];
    openEdit(`Editar cliente #${id}`, fields, customer, async (data) => {
      data.puntos_ecologicos = Number(data.puntos_ecologicos);
      await api.put("/clientes/" + id, data);
      toast("Cliente guardado.");
      loadCustomers();
    });
  } else if (btn.dataset.action === "delete") {
    const ok = await confirmAction(`¿Eliminar a “${customer.nombre_completo}”? Los clientes con pedidos no se pueden eliminar.`, {
      title: "Eliminar cliente",
      yes: "Eliminar cliente",
    });
    if (!ok) return;
    try {
      await api.del("/clientes/" + id);
      toast("Cliente eliminado.");
      loadCustomers();
    } catch (err) {
      showError(err);
    }
  }
});

async function showHistory(customer) {
  try {
    const orders = await api.get(`/clientes/${customer.cliente_id}/pedidos`);
    const spent = orders.reduce((sum, o) => sum + o.total, 0);
    $("#history-title").textContent = customer.nombre_completo;
    $("#history-summary").textContent =
      `${plural(orders.length, "pedido")}, ${money(spent)} gastados, ${int(customer.puntos_ecologicos)} eco-puntos acumulados`;
    $("#history-body").innerHTML = orders.length
      ? orders
          .map(
            (o) => `<tr>
              <td class="id">${o.pedido_id}</td>
              <td class="nowrap">${esc(dateTime(o.fecha_exacta))}</td>
              <td>${esc(o.nombre_sucursal)}</td>
              <td>${o.detalles.map((d) => `${esc(d.nombre_producto)} <span class="muted">${esc(qty(d.cantidad_comprada))} ${esc(unitFor(d.cantidad_comprada, d.unidad_medida))}</span>`).join("<br>")}</td>
              <td class="num strong">${esc(money(o.total))}</td>
              <td class="num"><span class="points">${int(o.puntos_ganados)}</span></td>
              <td class="actions"><button type="button" class="btn btn-sm" data-view-order="${o.pedido_id}">Ver</button></td>
            </tr>`
          )
          .join("")
      : emptyRow(7, "Aún no hay pedidos", "Los pedidos de este cliente aparecerán aquí.");
    $("#history-dialog").showModal();
  } catch (err) {
    showError(err);
  }
}

/* ============================== stores ============================== */

let storeRows = [];

async function loadStores() {
  loadingRows($("#stores-body"), 4);
  try {
    storeRows = await api.get("/tiendas");
    $("#stores-count").textContent = plural(storeRows.length, "tienda");
    setRows(
      $("#stores-body"),
      storeRows.length
        ? storeRows
            .map(
              (s) => `<tr>
                <td class="id">${s.tienda_id}</td>
                <td class="strong">${esc(s.nombre_sucursal)}</td>
                <td>${esc(s.direccion)}</td>
                <td class="actions">
                  <button type="button" class="btn btn-sm" data-action="edit" data-id="${s.tienda_id}">Editar</button>
                  <button type="button" class="btn btn-sm btn-danger-text" data-action="delete" data-id="${s.tienda_id}">Eliminar</button>
                </td>
              </tr>`
            )
            .join("")
        : emptyRow(4, "Aún no hay tiendas", "Agregue la primera estación de recarga con el formulario de arriba.")
    );
  } catch (err) {
    showError(err);
    setRows($("#stores-body"), emptyRow(4, "No se pudieron cargar las tiendas", esc(err.message)));
  }
}

$("#store-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  await busy(form.querySelector("button"), async () => {
    try {
      const created = await api.post("/tiendas", formData(form));
      form.reset();
      toast(`Tienda “${created.nombre_sucursal}” agregada.`);
      loadStores();
    } catch (err) {
      showError(err);
    }
  });
});

$("#stores-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const store = storeRows.find((s) => s.tienda_id === id);

  if (btn.dataset.action === "edit") {
    const fields = [
      { name: "nombre_sucursal", label: "Nombre de la sucursal", maxlength: 100 },
      { name: "direccion", label: "Dirección", maxlength: 200 },
    ];
    openEdit(`Editar tienda #${id}`, fields, store, async (data) => {
      await api.put("/tiendas/" + id, data);
      toast("Tienda guardada.");
      loadStores();
    });
  } else if (btn.dataset.action === "delete") {
    const ok = await confirmAction(`¿Eliminar “${store.nombre_sucursal}”? Las tiendas con inventario o pedidos no se pueden eliminar.`, {
      title: "Eliminar tienda",
      yes: "Eliminar tienda",
    });
    if (!ok) return;
    try {
      await api.del("/tiendas/" + id);
      toast("Tienda eliminada.");
      loadStores();
    } catch (err) {
      showError(err);
    }
  }
});

/* ============================== products ============================== */

let productRows = [];

async function loadProducts() {
  loadingRows($("#products-body"), 5);
  try {
    productRows = await api.get("/productos");
    $("#products-count").textContent = plural(productRows.length, "producto");
    setRows(
      $("#products-body"),
      productRows.length
        ? productRows
            .map(
              (p) => `<tr>
                <td class="id">${p.producto_id}</td>
                <td class="strong">${esc(p.nombre)}</td>
                <td>${esc(p.unidad_medida)}</td>
                <td class="num">${esc(money(p.precio_unitario))} <span class="muted">/ ${esc(perUnit(p.unidad_medida))}</span></td>
                <td class="actions">
                  <button type="button" class="btn btn-sm" data-action="edit" data-id="${p.producto_id}">Editar</button>
                  <button type="button" class="btn btn-sm btn-danger-text" data-action="delete" data-id="${p.producto_id}">Eliminar</button>
                </td>
              </tr>`
            )
            .join("")
        : emptyRow(5, "Aún no hay productos", "Agregue el primer producto con el formulario de arriba.")
    );
  } catch (err) {
    showError(err);
    setRows($("#products-body"), emptyRow(5, "No se pudieron cargar los productos", esc(err.message)));
  }
}

$("#product-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = formData(form);
  await busy(form.querySelector('[type="submit"]'), async () => {
    try {
      const created = await api.post("/productos", { ...data, precio_unitario: Number(data.precio_unitario) });
      form.reset();
      toast(`Producto “${created.nombre}” agregado a ${money(created.precio_unitario)} por ${perUnit(created.unidad_medida)}.`);
      loadProducts();
    } catch (err) {
      showError(err);
    }
  });
});

$("#products-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const product = productRows.find((p) => p.producto_id === id);

  if (btn.dataset.action === "edit") {
    const fields = [
      { name: "nombre", label: "Nombre", maxlength: 100 },
      { name: "unidad_medida", label: "Unidad", list: "unit-options", maxlength: 20 },
      { name: "precio_unitario", label: "Precio por unidad (USD)", type: "number", min: 0, step: "0.01", prefix: "$" },
    ];
    const values = { ...product, precio_unitario: Number(product.precio_unitario).toFixed(2) };
    openEdit(`Editar producto #${id}`, fields, values, async (data) => {
      await api.put("/productos/" + id, { ...data, precio_unitario: Number(data.precio_unitario) });
      toast("Producto guardado. Los pedidos anteriores conservan el precio con el que se vendieron.");
      loadProducts();
    });
  } else if (btn.dataset.action === "delete") {
    const ok = await confirmAction(`¿Eliminar “${product.nombre}”? Los productos con stock o que ya se pidieron no se pueden eliminar.`, {
      title: "Eliminar producto",
      yes: "Eliminar producto",
    });
    if (!ok) return;
    try {
      await api.del("/productos/" + id);
      toast("Producto eliminado.");
      loadProducts();
    } catch (err) {
      showError(err);
    }
  }
});

/* ============================== inventory ============================== */

async function loadInventoryPage() {
  try {
    await loadLookups();
  } catch (err) {
    showError(err);
  }
  fillSelect($("#inventory-store"), storeOptions("Elija una tienda"));
  fillSelect(
    $("#inventory-product"),
    '<option value="">Elija un producto</option>' +
      lookups.products.map((p) => `<option value="${p.producto_id}">${esc(p.nombre)} (${esc(p.unidad_medida)})</option>`).join("")
  );
  fillSelect($("#inventory-filter"), storeOptions("Todas las tiendas"));
  loadInventory();
}

async function loadInventory() {
  const storeId = $("#inventory-filter").value;
  const lowOnly = $("#inventory-low-only").checked;
  loadingRows($("#inventory-body"), 5, 6);
  try {
    let rows = await api.get("/inventario" + (storeId ? "?tienda_id=" + storeId : ""));
    // the jar is filled relative to the biggest stock in the list
    const max = Math.max(...rows.map((r) => r.cantidad_stock), LOW_STOCK);
    if (lowOnly) rows = rows.filter((r) => r.cantidad_stock < LOW_STOCK);

    setRows(
      $("#inventory-body"),
      rows.length
        ? rows
            .map((r) => {
              const low = r.cantidad_stock < LOW_STOCK;
              return `<tr class="${low ? "is-low" : ""}">
                <td>${esc(r.nombre_sucursal)}</td>
                <td class="strong">${esc(r.nombre_producto)}${low ? ' <span class="tag tag-low">Bajo</span>' : ""}</td>
                <td>${jar(r.cantidad_stock / max, low)}</td>
                <td class="num">
                  <span class="stock-edit">
                    <input type="number" class="stock-input" min="0" step="0.01" inputmode="decimal"
                      value="${Number(r.cantidad_stock).toFixed(2)}" data-original="${Number(r.cantidad_stock).toFixed(2)}"
                      aria-label="Stock de ${esc(r.nombre_producto)} en ${esc(r.nombre_sucursal)}">
                    <span class="unit">${esc(r.unidad_medida)}</span>
                  </span>
                </td>
                <td class="actions">
                  <button type="button" class="btn btn-sm" data-action="save" data-tienda="${r.tienda_id}" data-producto="${r.producto_id}" disabled>Guardar</button>
                  <button type="button" class="btn btn-sm btn-danger-text" data-action="delete" data-tienda="${r.tienda_id}" data-producto="${r.producto_id}"
                    data-label="${esc(r.nombre_producto)} en ${esc(r.nombre_sucursal)}">Quitar</button>
                </td>
              </tr>`;
            })
            .join("")
        : lowOnly
          ? emptyRow(5, "Nada está por agotarse", "Todos los registros tienen al menos 10 unidades.")
          : emptyRow(5, "Aún no hay registros de inventario", "Use el formulario de arriba para agregar stock de un producto a una tienda.")
    );
  } catch (err) {
    showError(err);
    setRows($("#inventory-body"), emptyRow(5, "No se pudo cargar el inventario", esc(err.message)));
  }
}

$("#inventory-filter").addEventListener("change", loadInventory);
$("#inventory-low-only").addEventListener("change", loadInventory);

$("#inventory-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = formData(form);
  await busy(form.querySelector('[type="submit"]'), async () => {
    try {
      const row = await api.post("/inventario", {
        tienda_id: Number(data.tienda_id),
        producto_id: Number(data.producto_id),
        cantidad_stock: Number(data.cantidad_stock),
      });
      form.cantidad_stock.value = "";
      toast(`Stock agregado: ${row.nombre_producto} en ${row.nombre_sucursal}, ${qty(row.cantidad_stock)} ${unitFor(row.cantidad_stock, row.unidad_medida)}.`);
      loadInventory();
    } catch (err) {
      showError(err);
    }
  });
});

// The Save button only turns on when the number was changed
$("#inventory-body").addEventListener("input", (e) => {
  if (!e.target.classList.contains("stock-input")) return;
  const input = e.target;
  const changed = input.value !== "" && Number(input.value) !== Number(input.dataset.original);
  input.closest("tr").querySelector('[data-action="save"]').disabled = !changed;
});

// Pressing Enter inside a stock input works like clicking Save
$("#inventory-body").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.classList.contains("stock-input")) {
    e.preventDefault();
    e.target.closest("tr").querySelector('[data-action="save"]').click();
  }
});

$("#inventory-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const { tienda, producto } = btn.dataset;
  const path = `/inventario/${tienda}/${producto}`;
  const row = btn.closest("tr");

  if (btn.dataset.action === "save") {
    const input = row.querySelector(".stock-input");
    if (input.value === "" || Number(input.value) < 0) {
      toast("Ingrese un stock de 0 o más.", "error");
      input.focus();
      return;
    }
    await busy(btn, async () => {
      try {
        const saved = await api.put(path, { cantidad_stock: Number(input.value) });
        toast(`Stock guardado: ${saved.nombre_producto} en ${saved.nombre_sucursal} ahora tiene ${qty(saved.cantidad_stock)} ${unitFor(saved.cantidad_stock, saved.unidad_medida)}.`);
        loadInventory();
      } catch (err) {
        showError(err);
      }
    });
  } else if (btn.dataset.action === "delete") {
    const ok = await confirmAction(`¿Quitar ${btn.dataset.label} del inventario?`, {
      title: "Quitar registro de inventario",
      yes: "Quitar registro",
    });
    if (!ok) return;
    try {
      await api.del(path);
      toast("Registro de inventario quitado.");
      loadInventory();
    } catch (err) {
      showError(err);
    }
  }
});
