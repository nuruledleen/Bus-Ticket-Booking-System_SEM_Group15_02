(() => {
  const app = document.getElementById("booking-app");
  if (!app) return;
  const scheduleId = Number(app.dataset.scheduleId);
  const maxSeats = Number(app.dataset.maxSeats);
  const selected = new Set();
  const el = (id) => document.getElementById(id);
  const rm = (sen) => "RM " + (sen / 100).toFixed(2);

  async function api(url, options) {
    const res = await fetch(url, options);
    const body = await res.json();
    if (!res.ok) throw body.error;
    return body;
  }

  function clearErrors() {
    document.querySelectorAll("[data-error-for]").forEach((n) => (n.textContent = ""));
    el("form-error").textContent = "";
  }

  function showErrors(error) {
    el("form-error").textContent = error.message || "Something went wrong.";
    Object.entries(error.details || {}).forEach(([key, message]) => {
      const target = document.querySelector(`[data-error-for="${key}"]`);
      if (target) target.textContent = message;
      else el("form-error").textContent += " " + message;
    });
  }

  async function loadSeats() {
    const { seats } = await api(`/api/schedules/${scheduleId}/seats`);
    const map = el("seat-map");
    map.innerHTML = "";
    seats.forEach((seat, i) => {
      if (i % 4 === 2) map.appendChild(Object.assign(document.createElement("span"), { className: "aisle" }));
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = seat.number;
      btn.className = "seat";
      if (!seat.available) {
        btn.disabled = true;
        btn.classList.add("taken");
        selected.delete(seat.number);
      } else if (selected.has(seat.number)) {
        btn.classList.add("selected");
      }
      btn.addEventListener("click", () => toggleSeat(seat.number, btn));
      map.appendChild(btn);
    });
  }

  const passengerFields = (i) => `
    <label>Full name <input name="name" autocomplete="off"></label>
    <small class="field-error" data-error-for="passengers.${i}.name"></small>
    <label>Age <input name="age" type="number" min="1" max="120"></label>
    <small class="field-error" data-error-for="passengers.${i}.age"></small>
    <label>Gender <select name="gender"><option value="">Select</option>
      <option value="M">Male</option><option value="F">Female</option></select></label>
    <small class="field-error" data-error-for="passengers.${i}.gender"></small>`;

  function readPassengers() {
    return [...document.querySelectorAll("#passenger-fields fieldset")].map((fs) => ({
      seat_number: Number(fs.dataset.seat),
      name: fs.querySelector("[name=name]").value,
      age: fs.querySelector("[name=age]").value,
      gender: fs.querySelector("[name=gender]").value,
    }));
  }

  function renderPassengers() {
    const saved = Object.fromEntries(readPassengers().map((p) => [p.seat_number, p]));
    const box = el("passenger-fields");
    box.innerHTML = "";
    if (!selected.size) {
      box.innerHTML = '<p class="muted">Select a seat to begin.</p>';
      return;
    }
    [...selected].sort((a, b) => a - b).forEach((seat, i) => {
      const fs = document.createElement("fieldset");
      fs.dataset.seat = seat;
      fs.innerHTML = `<legend>Seat ${seat}</legend>` + passengerFields(i);
      const old = saved[seat];
      if (old) {
        fs.querySelector("[name=name]").value = old.name;
        fs.querySelector("[name=age]").value = old.age;
        fs.querySelector("[name=gender]").value = old.gender;
      }
      box.appendChild(fs);
    });
  }

  async function updateSummary() {
    const box = el("fare-summary");
    el("submit-btn").disabled = !selected.size;
    if (!selected.size) { box.textContent = ""; return; }
    const q = await api(`/api/schedules/${scheduleId}/quote?seat_count=${selected.size}`);
    box.innerHTML = `<dl><dt>Fare (${q.seat_count} seat${q.seat_count > 1 ? "s" : ""})</dt><dd>${rm(q.base_sen)}</dd>
      <dt>Service fee</dt><dd>${rm(q.service_fee_sen)}</dd>
      <dt><strong>Total</strong></dt><dd><strong>${rm(q.total_sen)}</strong></dd></dl>`;
  }

  async function toggleSeat(number, btn) {
    clearErrors();
    if (selected.has(number)) selected.delete(number);
    else if (selected.size >= maxSeats) { showErrors({ message: `You can select up to ${maxSeats} seats.` }); return; }
    else selected.add(number);
    btn.classList.toggle("selected", selected.has(number));
    renderPassengers();
    try { await updateSummary(); } catch (error) { showErrors(error); }
  }

  el("booking-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();
    const payload = {
      schedule_id: scheduleId,
      contact: { email: el("email").value, phone: el("phone").value },
      passengers: readPassengers(),
    };
    try {
      const { booking } = await api("/api/bookings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      window.location.href = `/bookings/${booking.reference}`;
    } catch (error) {
      showErrors(error);
      if (error.code === "conflict") {   // someone else took a seat: refresh the map
        await loadSeats();
        renderPassengers();
        await updateSummary();
      }
    }
  });

  renderPassengers();
  loadSeats().catch(showErrors);
})();
