/**
 * Smart Freelance Invoice & Financial Management Platform - Core UX Script
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Mobile Sidebar Toggle
  const sidebar = document.querySelector(".app-sidebar");
  const navToggle = document.querySelector(".mobile-nav-toggle");
  
  if (navToggle && sidebar) {
    navToggle.addEventListener("click", () => {
      sidebar.classList.toggle("mobile-open");
    });
  }

  // 2. Auto-dismiss Flash Alerts
  document.querySelectorAll(".flash-close-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const msg = e.target.closest(".flash-message");
      if (msg) msg.remove();
    });
  });

  // 3. Custom Accessible Confirmation Modal for Destructive Actions
  const confirmForms = document.querySelectorAll("form[data-confirm]");
  confirmForms.forEach(form => {
    form.addEventListener("submit", (e) => {
      const message = form.getAttribute("data-confirm") || "Are you sure you want to proceed?";
      if (!window.confirm(message)) {
        e.preventDefault();
      }
    });
  });

  // 4. Modal Open/Close Event Listeners
  document.querySelectorAll("[data-modal-open]").forEach(trigger => {
    trigger.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = trigger.getAttribute("data-modal-open");
      const modal = document.getElementById(targetId);
      if (modal) modal.classList.add("active");
    });
  });

  document.querySelectorAll("[data-modal-close]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const modal = btn.closest(".modal-backdrop");
      if (modal) modal.classList.remove("active");
    });
  });
});
