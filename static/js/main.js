/* =============================================
   MAIN.JS — Sonnac Lanka Car Sale System
   ============================================= */

/* ── Quotation Dynamic Line Items ── */
let itemIndex = 0;

function addQuoteItem(desc = '', qty = 1, price = 0) {
  itemIndex++;
  const tbody = document.getElementById('quote-items-body');
  if (!tbody) return;
  const tr = document.createElement('tr');
  tr.className = 'quote-item-row';
  tr.innerHTML = `
    <td><input type="text" class="form-control" name="item_desc[]" value="${escHtml(desc)}" placeholder="Description" required></td>
    <td style="width:90px"><input type="number" class="form-control item-qty" name="item_qty[]" value="${qty}" min="1" step="1"></td>
    <td style="width:130px"><input type="number" class="form-control item-price" name="item_price[]" value="${price}" min="0" step="0.01"></td>
    <td style="width:130px" class="item-total fw-bold text-end pe-2">0.00</td>
    <td style="width:40px"><button type="button" class="btn btn-sm btn-outline-danger remove-item-btn" onclick="removeQuoteItem(this)"><i class="bi bi-trash"></i></button></td>
  `;
  tbody.appendChild(tr);
  updateItemTotal(tr);
  attachItemListeners(tr);
  updateQuoteTotals();
}

function removeQuoteItem(btn) {
  const tr = btn.closest('tr');
  if (document.querySelectorAll('.quote-item-row').length > 1) {
    tr.remove();
    updateQuoteTotals();
  } else {
    showToast('At least one item is required.', 'warning');
  }
}

function attachItemListeners(tr) {
  tr.querySelectorAll('.item-qty, .item-price').forEach(input => {
    input.addEventListener('input', () => {
      updateItemTotal(tr);
      updateQuoteTotals();
    });
  });
}

function updateItemTotal(tr) {
  const qty = parseFloat(tr.querySelector('.item-qty')?.value) || 0;
  const price = parseFloat(tr.querySelector('.item-price')?.value) || 0;
  const total = qty * price;
  const cell = tr.querySelector('.item-total');
  if (cell) cell.textContent = formatCurrency(total);
  tr.dataset.total = total;
}

function updateQuoteTotals() {
  let subtotal = 0;
  document.querySelectorAll('.quote-item-row').forEach(tr => {
    subtotal += parseFloat(tr.dataset.total || 0);
  });
  const discountPct = parseFloat(document.getElementById('discount_pct')?.value) || 0;
  const taxPct = parseFloat(document.getElementById('tax_pct')?.value) || 0;
  const discountAmt = subtotal * discountPct / 100;
  const taxable = subtotal - discountAmt;
  const taxAmt = taxable * taxPct / 100;
  const grand = taxable + taxAmt;

  setEl('qt-subtotal', formatCurrency(subtotal));
  setEl('qt-discount', formatCurrency(discountAmt));
  setEl('qt-tax', formatCurrency(taxAmt));
  setEl('qt-total', formatCurrency(grand));
  setEl('qt-subtotal-val', subtotal.toFixed(2));
  setEl('qt-discount-val', discountAmt.toFixed(2));
  setEl('qt-tax-val', taxAmt.toFixed(2));
  setEl('qt-total-val', grand.toFixed(2));
}

// Init on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  const tbody = document.getElementById('quote-items-body');
  if (tbody) {
    // Re-attach listeners to existing rows (edit mode)
    tbody.querySelectorAll('.quote-item-row').forEach(tr => {
      attachItemListeners(tr);
      updateItemTotal(tr);
    });
    updateQuoteTotals();

    document.getElementById('discount_pct')?.addEventListener('input', updateQuoteTotals);
    document.getElementById('tax_pct')?.addEventListener('input', updateQuoteTotals);
  }
});

/* ── Image Gallery (Public Vehicle Detail) ── */
function switchMainImage(thumb) {
  const main = document.getElementById('main-vehicle-img');
  if (!main) return;
  main.src = thumb.src.replace('_thumb', '');
  main.src = thumb.getAttribute('data-full') || thumb.src;
  document.querySelectorAll('.gallery-thumb').forEach(t => t.classList.remove('active'));
  thumb.classList.add('active');
}

/* ── Image preview for uploads ── */
document.addEventListener('DOMContentLoaded', () => {
  const imgInputs = document.querySelectorAll('.img-upload-input');
  imgInputs.forEach(input => {
    input.addEventListener('change', function () {
      const previewId = this.getAttribute('data-preview');
      const preview = document.getElementById(previewId);
      if (!preview) return;
      const file = this.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = e => { preview.src = e.target.result; preview.style.display = 'block'; };
        reader.readAsDataURL(file);
      }
    });
  });
});

/* ── Admin Sidebar Toggle (mobile) ── */
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.admin-sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('d-none');
    });
    if (overlay) overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.add('d-none');
    });
  }
});

/* ── Confirm dialogs ── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', function (e) {
      if (!confirm(this.getAttribute('data-confirm'))) e.preventDefault();
    });
  });
});

/* ── Auto-dismiss flash alerts ── */
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.alert-autohide').forEach(el => {
      el.style.transition = 'opacity 0.5s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    });
  }, 4000);
});

/* ── Chart.js Dashboard ── */
function initDashboardCharts(data) {
  // Monthly Revenue Bar
  const revenueCtx = document.getElementById('revenueChart');
  if (revenueCtx && data.monthly_chart) {
    new Chart(revenueCtx, {
      type: 'bar',
      data: {
        labels: data.monthly_chart.labels,
        datasets: [{
          label: 'Revenue',
          data: data.monthly_chart.revenue,
          backgroundColor: 'rgba(26,58,92,0.75)',
          borderColor: '#1a3a5c',
          borderWidth: 1,
          borderRadius: 4,
        }, {
          label: 'Units Sold',
          data: data.monthly_chart.units,
          backgroundColor: 'rgba(232,160,32,0.75)',
          borderColor: '#e8a020',
          borderWidth: 1,
          borderRadius: 4,
          yAxisID: 'y2',
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom' } },
        scales: {
          y: { beginAtZero: true, ticks: { callback: v => 'Rs ' + formatNum(v) } },
          y2: { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: 'Units' } }
        }
      }
    });
  }

  // Pipeline Donut
  const pipelineCtx = document.getElementById('pipelineChart');
  if (pipelineCtx && data.pipeline_data) {
    new Chart(pipelineCtx, {
      type: 'doughnut',
      data: {
        labels: data.pipeline_data.labels,
        datasets: [{ data: data.pipeline_data.counts,
          backgroundColor: ['#1a3a5c','#2a5a8c','#e8a020','#28a745','#6c757d','#dc3545'],
          borderWidth: 2 }]
      },
      options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
    });
  }

  // Inventory Status Donut
  const invCtx = document.getElementById('inventoryChart');
  if (invCtx && data.inv_status) {
    new Chart(invCtx, {
      type: 'doughnut',
      data: {
        labels: data.inv_status.labels,
        datasets: [{ data: data.inv_status.counts,
          backgroundColor: ['#28a745','#ffc107','#dc3545','#6c757d'],
          borderWidth: 2 }]
      },
      options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
    });
  }
}

/* ── Cost Sheet Auto-Calc ── */
document.addEventListener('DOMContentLoaded', () => {
  const costInputs = document.querySelectorAll('.cost-input');
  if (!costInputs.length) return;
  costInputs.forEach(inp => inp.addEventListener('input', calcCostTotals));
  calcCostTotals();
});

function calcCostTotals() {
  let total = 0;
  document.querySelectorAll('.cost-input').forEach(inp => {
    // Purchase price is converted separately; LC value is informational and not part of landed total.
    if (inp.id === 'purchase_price_fc' || inp.name === 'lc_value') return;
    total += parseFloat(inp.value) || 0;
  });
  const exRate = parseFloat(document.getElementById('exchange_rate')?.value) || 1;
  const purFC = parseFloat(document.getElementById('purchase_price_fc')?.value) || 0;
  const purchaseLkr = purFC * exRate;
  setEl('purchase-lkr-display', formatCurrency(purchaseLkr));
  const totalLanded = purchaseLkr + total;
  setEl('cost-total-display', formatCurrency(totalLanded));
  const marginPct = parseFloat(document.getElementById('target_margin_pct')?.value) || 0;
  const targetPrice = totalLanded / (1 - marginPct / 100);
  setEl('target-price-display', formatCurrency(targetPrice));
}

/* ── Helpers ── */
function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) {
    if (el.tagName === 'INPUT') el.value = val;
    else el.textContent = val;
  }
}
function formatCurrency(n) {
  return 'Rs ' + (isNaN(n) ? '0.00' : Number(n).toLocaleString('en-LK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
}
function formatNum(n) {
  return Number(n).toLocaleString('en-LK');
}
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Toast notifications ── */
function showToast(msg, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;bottom:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  const colors = { success: '#28a745', danger: '#dc3545', warning: '#ffc107', info: '#17a2b8' };
  toast.style.cssText = `background:${colors[type]||colors.info};color:#fff;padding:0.75rem 1.25rem;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-size:0.875rem;min-width:220px;`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.4s'; setTimeout(() => toast.remove(), 400); }, 3500);
}

/* ── Vehicle filter form auto-submit ── */
document.addEventListener('DOMContentLoaded', () => {
  const autoForm = document.getElementById('vehicle-filter-form');
  if (!autoForm) return;
  autoForm.querySelectorAll('select').forEach(sel => {
    sel.addEventListener('change', () => autoForm.submit());
  });
});

/* ── Managed Make/Model dropdown linkage (supports multiple pairs) ── */
document.addEventListener('DOMContentLoaded', () => {
  const bindMakeModel = (makeSelect, modelSelect, makeInput, modelInput) => {
    if (!makeSelect || !modelSelect) return;
    const baseUrl = modelSelect.dataset.modelUrl || '';
    const valueField = modelSelect.dataset.valueField === 'name' ? 'name' : 'id';

    const applyModelOptions = (models, placeholder) => {
      const current = modelSelect.value;
      modelSelect.innerHTML = `<option value="">${placeholder}</option>`;
      models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m[valueField];
        opt.textContent = m.name;
        opt.dataset.make = m.make_id || '';
        modelSelect.appendChild(opt);
      });
      if (current) modelSelect.value = current;
    };

    const fetchModels = (makeId) => {
      if (!makeId || !baseUrl) {
        applyModelOptions([], modelSelect.dataset.placeholder || 'Select managed model…');
        return;
      }
      const url = baseUrl.replace(/\d+$/, makeId);
      fetch(url, { headers: { 'Accept': 'application/json' } })
        .then(r => r.ok ? r.json() : [])
        .then(data => applyModelOptions(data, modelSelect.dataset.placeholder || 'Select managed model…'))
        .catch(() => applyModelOptions([], modelSelect.dataset.placeholder || 'Select managed model…'));
    };

    makeSelect.addEventListener('change', () => {
      const sel = makeSelect.options[makeSelect.selectedIndex];
      if (makeInput) makeInput.value = sel && sel.value ? sel.text.replace(' (disabled)', '') : '';
      fetchModels(makeSelect.value);
      if (modelInput) modelInput.value = '';
    });

    modelSelect.addEventListener('change', () => {
      const sel = modelSelect.options[modelSelect.selectedIndex];
      if (modelInput && sel && sel.value) modelInput.value = sel.text.replace(' (disabled)', '');
    });

    // Initial sync
    if (makeSelect.value && modelSelect.options.length <= 1) {
      fetchModels(makeSelect.value);
    }
    if (makeSelect.value && makeInput && !makeInput.value) {
      const sel = makeSelect.options[makeSelect.selectedIndex];
      if (sel) makeInput.value = sel.text.replace(' (disabled)', '');
    }
    if (modelSelect.value && modelInput && !modelInput.value) {
      const sel = modelSelect.options[modelSelect.selectedIndex];
      if (sel) modelInput.value = sel.text.replace(' (disabled)', '');
    }
  };

  bindMakeModel(
    document.getElementById('make_id'),
    document.getElementById('model_id'),
    document.getElementById('make_text'),
    document.getElementById('model_text'),
  );
  bindMakeModel(
    document.getElementById('filter_make_id'),
    document.getElementById('filter_model_id')
  );
  bindMakeModel(
    document.getElementById('public_make'),
    document.getElementById('public_model')
  );
});

/* ── Price range labels ── */
document.addEventListener('DOMContentLoaded', () => {
  ['price_min', 'price_max', 'year_min', 'year_max'].forEach(id => {
    const el = document.getElementById(id);
    const lbl = document.getElementById(id + '_label');
    if (el && lbl) {
      el.addEventListener('input', () => { lbl.textContent = el.value ? (id.startsWith('price') ? 'Rs ' + formatNum(el.value) : el.value) : 'Any'; });
    }
  });
});
