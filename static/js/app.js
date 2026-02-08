const state = {
  clients: [],
  products: [],
  invoiceItems: [],
};

const fmt = (value) => `RD$ ${Number(value).toFixed(2)}`;

function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2200);
}

async function api(url, options = {}) {
  const config = { headers: { 'Content-Type': 'application/json' }, ...options };
  const res = await fetch(url, config);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Error inesperado');
  return data;
}

function setupNavigation() {
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.view).classList.add('active');
    });
  });
}

function renderClients() {
  const tbody = document.getElementById('clients-table');
  tbody.innerHTML = state.clients.map((c) => `
    <tr>
      <td>${c.name}</td>
      <td>${c.email || ''}</td>
      <td>${c.phone || ''}</td>
      <td>
        <button class="action-btn" onclick='editClient(${JSON.stringify(c)})'>Editar</button>
        <button onclick='deleteClient(${c.id})'>Eliminar</button>
      </td>
    </tr>
  `).join('');
}

window.editClient = (client) => {
  document.getElementById('client-id').value = client.id;
  document.getElementById('client-name').value = client.name;
  document.getElementById('client-email').value = client.email || '';
  document.getElementById('client-phone').value = client.phone || '';
  document.getElementById('client-address').value = client.address || '';
};

window.deleteClient = async (id) => {
  if (!confirm('¿Eliminar cliente?')) return;
  await api(`/api/clients/${id}`, { method: 'DELETE' });
  await loadClients();
  showToast('Cliente eliminado');
};

async function loadClients(search = '') {
  state.clients = await api(`/api/clients?search=${encodeURIComponent(search)}`);
  renderClients();
  const select = document.getElementById('invoice-client');
  select.innerHTML = '<option value="">Consumidor final</option>' + state.clients.map((c) => `<option value="${c.id}">${c.name}</option>`).join('');
}

function renderProducts() {
  const tbody = document.getElementById('products-table');
  tbody.innerHTML = state.products.map((p) => `
    <tr>
      <td>${p.name}</td>
      <td>${fmt(p.price)}</td>
      <td>${p.stock}</td>
      <td>
        <button class="action-btn" onclick='editProduct(${JSON.stringify(p)})'>Editar</button>
        <button onclick='deleteProduct(${p.id})'>Eliminar</button>
      </td>
    </tr>
  `).join('');

  const prodSelect = document.getElementById('invoice-product');
  prodSelect.innerHTML = state.products
    .filter((p) => p.stock > 0)
    .map((p) => `<option value="${p.id}">${p.name} (Stock: ${p.stock})</option>`)
    .join('');
}

window.editProduct = (product) => {
  document.getElementById('product-id').value = product.id;
  document.getElementById('product-name').value = product.name;
  document.getElementById('product-price').value = product.price;
  document.getElementById('product-stock').value = product.stock;
};

window.deleteProduct = async (id) => {
  if (!confirm('¿Eliminar producto?')) return;
  await api(`/api/products/${id}`, { method: 'DELETE' });
  await loadProducts();
  showToast('Producto eliminado');
};

async function loadProducts(search = '') {
  state.products = await api(`/api/products?search=${encodeURIComponent(search)}`);
  renderProducts();
}

function updateTotals() {
  const subtotal = state.invoiceItems.reduce((acc, item) => acc + item.line_total, 0);
  const itbis = subtotal * 0.18;
  const total = subtotal + itbis;
  document.getElementById('subtotal').textContent = fmt(subtotal);
  document.getElementById('itbis').textContent = fmt(itbis);
  document.getElementById('total').textContent = fmt(total);
}

function renderInvoiceItems() {
  const tbody = document.getElementById('invoice-items');
  tbody.innerHTML = state.invoiceItems.map((item, i) => `
    <tr>
      <td>${item.name}</td>
      <td>${item.quantity}</td>
      <td>${fmt(item.price)}</td>
      <td>${fmt(item.line_total)}</td>
      <td><button onclick='removeInvoiceItem(${i})'>Quitar</button></td>
    </tr>
  `).join('');
  updateTotals();
}

window.removeInvoiceItem = (index) => {
  state.invoiceItems.splice(index, 1);
  renderInvoiceItems();
};

async function loadHistory() {
  const date = document.getElementById('filter-date').value;
  const client = document.getElementById('filter-client').value;
  const query = new URLSearchParams({ date, client });
  const invoices = await api(`/api/invoices?${query.toString()}`);

  const tbody = document.getElementById('history-table');
  tbody.innerHTML = invoices.map((inv) => `
    <tr>
      <td>${inv.invoice_number}</td>
      <td>${inv.client_name || 'Consumidor final'}</td>
      <td>${inv.created_at}</td>
      <td>${fmt(inv.total)}</td>
      <td>
        <button onclick='window.open("/api/invoices/${inv.id}/pdf", "_blank")'>PDF</button>
        <button onclick='window.open("/api/invoices/${inv.id}/pdf", "_blank"); setTimeout(()=>window.print(), 500)'>Imprimir</button>
      </td>
    </tr>
  `).join('');

  document.getElementById('stat-invoices').textContent = invoices.length;
  const totalSales = invoices.reduce((acc, i) => acc + i.total, 0);
  document.getElementById('stat-sales').textContent = fmt(totalSales);
}

function bindForms() {
  document.getElementById('client-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('client-id').value;
    const payload = {
      name: document.getElementById('client-name').value,
      email: document.getElementById('client-email').value,
      phone: document.getElementById('client-phone').value,
      address: document.getElementById('client-address').value,
    };

    if (id) {
      await api(`/api/clients/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Cliente actualizado');
    } else {
      await api('/api/clients', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Cliente registrado');
    }

    e.target.reset();
    document.getElementById('client-id').value = '';
    await loadClients();
    await loadDashboardStats();
  });

  document.getElementById('product-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('product-id').value;
    const payload = {
      name: document.getElementById('product-name').value,
      price: parseFloat(document.getElementById('product-price').value),
      stock: parseInt(document.getElementById('product-stock').value, 10),
    };

    if (id) {
      await api(`/api/products/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Producto actualizado');
    } else {
      await api('/api/products', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Producto registrado');
    }

    e.target.reset();
    document.getElementById('product-id').value = '';
    await loadProducts();
    await loadDashboardStats();
  });

  document.getElementById('search-clients').addEventListener('input', (e) => loadClients(e.target.value));
  document.getElementById('search-products').addEventListener('input', (e) => loadProducts(e.target.value));

  document.getElementById('add-item').addEventListener('click', (e) => {
    e.preventDefault();
    const productId = Number(document.getElementById('invoice-product').value);
    const quantity = Number(document.getElementById('invoice-qty').value);
    const product = state.products.find((p) => p.id === productId);

    if (!product || quantity < 1) return;
    if (quantity > product.stock) return showToast('Stock insuficiente para este producto');

    const found = state.invoiceItems.find((i) => i.product_id === productId);
    if (found) {
      const newQty = found.quantity + quantity;
      if (newQty > product.stock) return showToast('Stock insuficiente');
      found.quantity = newQty;
      found.line_total = found.quantity * found.price;
    } else {
      state.invoiceItems.push({
        product_id: product.id,
        name: product.name,
        quantity,
        price: Number(product.price),
        line_total: Number(product.price) * quantity,
      });
    }

    renderInvoiceItems();
  });

  document.getElementById('create-invoice').addEventListener('click', async () => {
    if (!state.invoiceItems.length) return showToast('Agrega al menos un producto.');

    const payload = {
      client_id: document.getElementById('invoice-client').value || null,
      payment_method: document.getElementById('invoice-payment').value,
      items: state.invoiceItems.map(({ product_id, quantity }) => ({ product_id, quantity })),
    };

    const invoice = await api('/api/invoices', { method: 'POST', body: JSON.stringify(payload) });
    showToast(`Factura ${invoice.invoice_number} generada`);
    state.invoiceItems = [];
    renderInvoiceItems();
    await loadProducts();
    await loadHistory();
    await loadDashboardStats();
    window.open(`/api/invoices/${invoice.id}/pdf`, '_blank');
  });

  document.getElementById('apply-filters').addEventListener('click', loadHistory);
}

async function loadDashboardStats() {
  const [clients, products] = await Promise.all([api('/api/clients'), api('/api/products')]);
  document.getElementById('stat-clients').textContent = clients.length;
  document.getElementById('stat-products').textContent = products.length;
}

async function bootstrap() {
  setupNavigation();
  bindForms();
  await Promise.all([loadClients(), loadProducts(), loadHistory(), loadDashboardStats()]);
}

bootstrap().catch((err) => showToast(err.message));
