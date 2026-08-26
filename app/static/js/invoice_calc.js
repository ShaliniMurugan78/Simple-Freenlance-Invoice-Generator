/**
 * Instant Deterministic Client-Side Invoice Calculations & Dynamic Row Manager
 */

function getCurrencySymbol(code) {
  const symbols = {
    INR: "₹",
    USD: "$",
    EUR: "€",
    GBP: "£"
  };
  return symbols[code] || "₹";
}

function formatNumber(num) {
  return (num || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function recalculateInvoice() {
  const currencySelect = document.getElementById("currencySelect");
  const currencyCode = currencySelect ? currencySelect.value : "INR";
  const symbol = getCurrencySymbol(currencyCode);

  const rows = document.querySelectorAll(".item-row");
  let subtotal = 0;

  rows.forEach(row => {
    const hoursInput = row.querySelector(".item-hours");
    const rateInput = row.querySelector(".item-rate");
    const amountSpan = row.querySelector(".item-amount");

    const hours = parseFloat(hoursInput.value) || 0;
    const rate = parseFloat(rateInput.value) || 0;
    const amount = Math.round(hours * rate * 100) / 100;

    if (amountSpan) {
      amountSpan.textContent = `${symbol}${formatNumber(amount)}`;
    }
    subtotal += amount;
  });

  subtotal = Math.round(subtotal * 100) / 100;

  const discountInput = document.getElementById("discountPercent");
  const discountPercent = parseFloat(discountInput ? discountInput.value : 0) || 0;
  const discountAmount = Math.round(subtotal * (discountPercent / 100) * 100) / 100;

  const taxableAmount = Math.max(0, Math.round((subtotal - discountAmount) * 100) / 100);

  const taxInput = document.getElementById("taxPercent");
  const taxPercent = parseFloat(taxInput ? taxInput.value : 0) || 0;
  const taxAmount = Math.round(taxableAmount * (taxPercent / 100) * 100) / 100;

  const grandTotal = Math.round((taxableAmount + taxAmount) * 100) / 100;

  // Update Summary UI
  const subtotalElem = document.getElementById("summarySubtotal");
  const discountElem = document.getElementById("summaryDiscount");
  const taxElem = document.getElementById("summaryTax");
  const totalElem = document.getElementById("summaryTotal");

  if (subtotalElem) subtotalElem.textContent = `${symbol}${formatNumber(subtotal)}`;
  if (discountElem) discountElem.textContent = `-${symbol}${formatNumber(discountAmount)}`;
  if (taxElem) taxElem.textContent = `+${symbol}${formatNumber(taxAmount)}`;
  if (totalElem) totalElem.textContent = `${symbol}${formatNumber(grandTotal)}`;
}

function attachRowListeners(row) {
  const inputs = row.querySelectorAll(".item-hours, .item-rate");
  inputs.forEach(input => {
    input.addEventListener("input", recalculateInvoice);
  });

  const removeBtn = row.querySelector(".remove-row-btn");
  if (removeBtn) {
    removeBtn.addEventListener("click", () => {
      const allRows = document.querySelectorAll(".item-row");
      if (allRows.length > 1) {
        row.remove();
        recalculateInvoice();
      } else {
        alert("An invoice must contain at least one line item.");
      }
    });
  }

  const aiBtn = row.querySelector(".ai-row-btn");
  if (aiBtn) {
    aiBtn.addEventListener("click", () => {
      window.activeRowForAI = row;
      const aiModal = document.getElementById("aiModal");
      if (aiModal) {
        aiModal.classList.add("active");
        const descInput = row.querySelector(".item-description");
        const aiServiceInput = document.getElementById("aiServiceName");
        if (aiServiceInput && descInput && descInput.value) {
          aiServiceInput.value = descInput.value;
        }
      }
    });
  }
}

function addNewLineItem(description = "", hours = 1, rate = 0) {
  const tbody = document.getElementById("itemsTableBody");
  if (!tbody) return;

  const row = document.createElement("tr");
  row.className = "item-row";
  row.innerHTML = `
    <td>
      <div style="display: flex; gap: 6px; align-items: center;">
        <input type="text" name="item_description[]" class="form-control item-description" placeholder="Service / Deliverable description" value="${description}" required>
        <button type="button" class="btn btn-sm btn-icon-only ai-row-btn" title="Generate with AI Assistant">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>
        </button>
      </div>
    </td>
    <td style="width: 100px;">
      <input type="number" name="item_hours[]" class="form-control item-hours numeric-cell" step="0.25" min="0.1" value="${hours}" required>
    </td>
    <td style="width: 140px;">
      <input type="number" name="item_rate[]" class="form-control item-rate numeric-cell" step="1" min="0" value="${rate}" required>
    </td>
    <td style="width: 130px; text-align: right; font-weight: 600;">
      <span class="item-amount">₹0.00</span>
    </td>
    <td style="width: 40px; text-align: center;">
      <button type="button" class="btn btn-sm btn-danger btn-icon-only remove-row-btn" title="Remove item">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>
    </td>
  `;

  tbody.appendChild(row);
  attachRowListeners(row);
  recalculateInvoice();
}

document.addEventListener("DOMContentLoaded", () => {
  // Attach listeners to initial rows
  document.querySelectorAll(".item-row").forEach(row => {
    attachRowListeners(row);
  });

  const addItemBtn = document.getElementById("addItemBtn");
  if (addItemBtn) {
    addItemBtn.addEventListener("click", () => {
      addNewLineItem();
    });
  }

  const discountInput = document.getElementById("discountPercent");
  if (discountInput) {
    discountInput.addEventListener("input", recalculateInvoice);
  }

  const taxInput = document.getElementById("taxPercent");
  if (taxInput) {
    taxInput.addEventListener("input", recalculateInvoice);
  }

  const currencySelect = document.getElementById("currencySelect");
  if (currencySelect) {
    currencySelect.addEventListener("change", recalculateInvoice);
  }

  // Initial calculation on page load
  recalculateInvoice();
});
