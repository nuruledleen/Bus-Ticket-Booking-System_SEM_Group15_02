(() => {
  const form = document.getElementById("schedule-form");
  if (!form) return;
  const errorBox = document.getElementById("admin-error");
  const FIELDS = ["operator", "bus_type", "origin", "destination", "departure_time",
                  "arrival_time", "fare_rm", "total_seats", "status"];

  function fill(values) {
    form.dataset.id = values.id || "";
    document.getElementById("form-title").textContent = values.id ? `Edit schedule #${values.id}` : "Add schedule";
    FIELDS.forEach((f) => (form.elements[f].value = values[f] ?? ""));
  }

  document.querySelectorAll(".edit-btn").forEach((btn) =>
    btn.addEventListener("click", () => {
      const s = JSON.parse(btn.dataset.schedule);
      fill({
        ...s,
        departure_time: s.departure_time.replace(" ", "T"),
        arrival_time: s.arrival_time.replace(" ", "T"),
        fare_rm: (s.fare_sen / 100).toFixed(2),
      });
      window.scrollTo({ top: 0, behavior: "smooth" });
    })
  );

  document.getElementById("reset-btn").addEventListener("click", () => fill({ status: "ACTIVE", total_seats: 40 }));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.textContent = "";
    const id = form.dataset.id;
    const payload = Object.fromEntries(FIELDS.map((f) => [f, form.elements[f].value]));
    const res = await fetch(id ? `/admin/api/schedules/${id}` : "/admin/api/schedules", {
      method: id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (res.ok) window.location.reload();
    else errorBox.textContent = [body.error.message, ...Object.values(body.error.details || {})].join(" ");
  });
})();
