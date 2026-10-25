(() => {
  const btn = document.getElementById("cancel-btn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    if (!confirm("Cancel this booking? This cannot be undone.")) return;
    const res = await fetch(`/api/bookings/${btn.dataset.reference}/cancel`, { method: "POST" });
    const body = await res.json();
    if (res.ok) window.location.reload();
    else document.getElementById("cancel-error").textContent = body.error.message;
  });
})();
