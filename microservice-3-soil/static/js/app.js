/* Nutrient & Soil web app. Plain JavaScript, no build step.
   Screens are chosen from the URL hash, for example #/sample/smp_1a2b3c4d. */
(function () {
  "use strict";

  const API = "/api/v1/soil";
  const STORE = "nsSession";
  const app = document.getElementById("app");
  const nav = document.getElementById("nav");
  let session = readSession();
  let timer = null;

  const RANGES = {
    nitrogenMgKg: { label: "Nitrogen", unit: "mg/kg", min: 0, max: 1000, step: 1, good: "20 – 40" },
    phosphorusMgKg: { label: "Phosphorus", unit: "mg/kg", min: 0, max: 1000, step: 1, good: "15 – 30" },
    potassiumMgKg: { label: "Potassium", unit: "mg/kg", min: 0, max: 1500, step: 1, good: "120 – 250" },
    ph: { label: "pH", unit: "no unit", min: 0, max: 14, step: 0.1, good: "6.0 – 7.5" },
    moisturePct: { label: "Moisture", unit: "percent", min: 0, max: 100, step: 0.1, good: "15 – 45" },
  };
  const ROLE_NAMES = {
    FIELD_OPERATOR: "Field Operator", AGRONOMIST: "Agronomist", RESEARCHER: "Breeder / Researcher",
    FARMER: "Farmer", ADMIN: "Administrator",
  };
  const MEASURE_LABEL = { nitrogen: "Nitrogen", phosphorus: "Phosphorus", potassium: "Potassium", ph: "pH", moisture: "Moisture" };
  const STATE_TEXT = {
    RECEIVED: "Received", ANALYSING: "Analysing", READY: "Ready", ANALYSIS_FAILED: "Analysis failed",
    DEFICIENT: "Deficient", EXCESS: "Excess", OK: "OK", LOW: "Low", HIGH: "High",
    GOOD: "Good", FAIR: "Fair", POOR: "Poor", PENDING: "AI view pending", READY_AI: "AI view ready",
  };
  const BODY_KEYS = Object.keys(RANGES);

  // ---------- helpers ----------

  function readSession() {
    try { return JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) { return null; }
  }
  function saveSession(next) {
    session = next;
    if (next) localStorage.setItem(STORE, JSON.stringify(next));
    else localStorage.removeItem(STORE);
  }
  function esc(value) {
    return String(value === null || value === undefined ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  const GOOD_STATES = ["GOOD", "OK", "READY"];
  const WARN_STATES = ["FAIR", "PENDING", "RECEIVED", "ANALYSING", "LOW", "HIGH"];
  const BAD_STATES = ["POOR", "ANALYSIS_FAILED", "DEFICIENT", "EXCESS"];
  function badge(state) {
    let colour = "neutral";
    if (GOOD_STATES.indexOf(state) >= 0) colour = "good";
    else if (WARN_STATES.indexOf(state) >= 0) colour = "warn";
    else if (BAD_STATES.indexOf(state) >= 0) colour = "bad";
    return '<span class="badge ' + colour + '">' + esc(STATE_TEXT[state] || state || "—") + "</span>";
  }
  function show(message, kind) {
    const el = document.createElement("div");
    el.className = "notice " + (kind || "");
    el.textContent = message;
    return el;
  }
  function setMain(html) { app.innerHTML = html; }
  function clearTimer() { if (timer) { clearTimeout(timer); timer = null; } }
  function formatDate(value) { return value ? String(value).replace("T", " ").replace("Z", " UTC") : "—"; }

  async function refreshSession() {
    if (!session || !session.refresh) return false;
    try {
      const res = await fetch(API + "/auth/refresh", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshToken: session.refresh }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      saveSession(Object.assign({}, session, { access: data.accessToken, refresh: data.refreshToken }));
      return true;
    } catch (e) { return false; }
  }

  async function api(path, options, retried) {
    const opts = options || {};
    const headers = { "Content-Type": "application/json" };
    if (session && session.access && !opts.anonymous) headers.Authorization = "Bearer " + session.access;
    const res = await fetch(API + path, {
      method: opts.method || (opts.body ? "POST" : "GET"), headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    if (res.status === 401 && !opts.anonymous && !retried && session) {
      if (await refreshSession()) return api(path, opts, true);
      logout(true);
      throw new Error("Your session has ended. Please log in again.");
    }
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      const err = new Error((data.error && data.error.message) || "Request failed.");
      err.code = data.error && data.error.code;
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function logout(silent) {
    const refresh = session && session.refresh;
    saveSession(null);
    if (refresh && !silent) {
      fetch(API + "/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshToken: refresh }) }).catch(function () {});
    }
    renderNav();
    if (!silent) location.hash = "#/login";
  }

  function role() { return session && session.user ? session.user.role : null; }

  function renderNav() {
    const links = [];
    if (session) {
      links.push(["#/dashboard", "Dashboard"]);
      if (role() === "FIELD_OPERATOR") links.push(["#/submit", "Submit sample"]);
      if (["FIELD_OPERATOR", "AGRONOMIST", "FARMER"].indexOf(role()) >= 0) links.push(["#/history", "Field history"]);
      if (role() === "RESEARCHER") links.push(["#/history", "Anonymous history"]);
      if (role() === "ADMIN") links.push(["#/admin", "Administration"]);
    }
    links.push(["#/outbox", "Mail (dev)"]);
    let html = links.map(function (l) { return '<a href="' + l[0] + '">' + esc(l[1]) + "</a>"; }).join("");
    if (session) {
      html += '<span class="small"> ' + esc(session.user.fullName) + " · " + esc(ROLE_NAMES[role()] || role()) + "</span>";
      html += '<button class="secondary" id="logout">Log out</button>';
    } else {
      html += '<a href="#/login">Log in</a><a href="#/register">Register</a>';
    }
    nav.innerHTML = html;
    const btn = document.getElementById("logout");
    if (btn) btn.addEventListener("click", function () { logout(false); });
  }

  // ---------- router ----------

  const ROUTES = [
    { name: "", view: home },
    { name: "login", view: loginView, open: true },
    { name: "register", view: registerView, open: true },
    { name: "verify", view: verifyView, open: true },
    { name: "reset", view: resetView, open: true },
    { name: "dashboard", view: dashboardView, roles: null },
    { name: "submit", view: submitView, roles: ["FIELD_OPERATOR"] },
    { name: "sample", view: sampleView, roles: null, param: true },
    { name: "field", view: fieldView, roles: ["FIELD_OPERATOR", "AGRONOMIST", "FARMER"], param: true },
    { name: "history", view: historyView, roles: ["FIELD_OPERATOR", "AGRONOMIST", "FARMER", "RESEARCHER"] },
    { name: "admin", view: adminView, roles: ["ADMIN"] },
    { name: "outbox", view: outboxView, open: true },
  ];

  async function route() {
    clearTimer();
    renderNav();
    const raw = location.hash.replace(/^#\/?/, "");
    const qat = raw.indexOf("?");
    const path = qat >= 0 ? raw.slice(0, qat) : raw;
    const params = new URLSearchParams(qat >= 0 ? raw.slice(qat + 1) : "");
    const parts = path.split("/");
    const found = ROUTES.find(function (r) { return r.name === parts[0]; }) || ROUTES[0];
    if (found.name === "") return home();
    if (!found.open && !session) {
      location.hash = "#/login";
      return;
    }
    if (found.roles && found.roles.indexOf(role()) < 0) {
      setMain('<div class="card"><h1>Not available</h1><p>This screen is not available for your role.</p></div>');
      return;
    }
    try {
      await found.view(params, parts[1]);
    } catch (err) {
      setMain('<div class="card"><p class="notice error">' + esc(err.message) + "</p></div>");
    }
  }

  // ---------- public screens ----------

  function home() {
    if (session) { location.hash = "#/dashboard"; return; }
    setMain(
      '<section class="card"><h1>Soil nutrient and health records</h1>' +
      '<p>Field operators submit soil samples. Agronomists read the health of each field and the nutrients that are too low or too high. ' +
      'Breeders and researchers study history with no names or exact locations.</p>' +
      '<div class="actions"><a class="button" href="#/login">Log in</a><a class="button secondary" href="#/register">Request an account</a></div></section>'
    );
  }

  function loginView() {
    setMain(
      '<div class="card center"><h1>Log in</h1><form id="login">' +
      '<label>Email<input name="email" type="email" autocomplete="username" required></label>' +
      '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>' +
      '<label>Authenticator code <span class="hint">(administrators only)</span><input name="totpCode" inputmode="numeric" autocomplete="one-time-code"></label>' +
      '<div class="actions"><button type="submit">Log in</button></div>' +
      '<p class="small"><a href="#/reset">Forgot your password?</a> · <a href="#/register">Request an account</a></p>' +
      '<div id="msg"></div></form></div>'
    );
    document.getElementById("login").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      const f = ev.target;
      const msg = document.getElementById("msg");
      msg.innerHTML = "";
      try {
        const data = await api("/auth/login", {
          anonymous: true,
          body: { email: f.email.value, password: f.password.value, totpCode: f.totpCode.value || undefined },
        });
        saveSession({ access: data.accessToken, refresh: data.refreshToken, user: data.user });
        location.hash = "#/dashboard";
        renderNav();
      } catch (err) {
        msg.appendChild(show(err.message, "error"));
      }
    });
  }

  function registerView() {
    const options = Object.keys(ROLE_NAMES).filter(function (r) { return r !== "ADMIN"; })
      .map(function (r) { return '<option value="' + r + '">' + esc(ROLE_NAMES[r]) + "</option>"; }).join("");
    setMain(
      '<div class="card center"><h1>Request an account</h1><form id="register">' +
      '<label>Full name<input name="fullName" required minlength="2" maxlength="120"></label>' +
      '<label>Email<input name="email" type="email" required></label>' +
      '<label>Organisation<input name="organisation" required minlength="2" maxlength="120"></label>' +
      '<label>Role you are asking for<select name="requestedRole">' + options + "</select></label>" +
      '<label>Password <span class="hint">12 or more characters, with letters and numbers</span>' +
      '<input name="password" type="password" minlength="12" required autocomplete="new-password"></label>' +
      '<div class="actions"><button type="submit">Create account</button></div><div id="msg"></div></form></div>'
    );
    document.getElementById("register").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      const f = ev.target;
      const msg = document.getElementById("msg");
      msg.innerHTML = "";
      try {
        const data = await api("/auth/register", {
          anonymous: true,
          body: { fullName: f.fullName.value, email: f.email.value, organisation: f.organisation.value,
                  requestedRole: f.requestedRole.value, password: f.password.value },
        });
        msg.appendChild(show(data.message + " Open the link in the email, then wait for approval. "
          + "(In development mode, find the link under Mail (dev).)", ""));
        f.reset();
      } catch (err) { msg.appendChild(show(err.message, "error")); }
    });
  }

  async function verifyView(params) {
    const token = params.get("token");
    setMain('<div class="card center"><h1>Verify your email</h1><div id="msg"><p class="muted">Checking the link…</p></div></div>');
    const msg = document.getElementById("msg");
    if (!token) { msg.innerHTML = ""; msg.appendChild(show("No link token was found in this address.", "error")); return; }
    try {
      const data = await api("/auth/verify?token=" + encodeURIComponent(token), { anonymous: true });
      msg.innerHTML = "";
      msg.appendChild(show(data.message, ""));
      msg.insertAdjacentHTML("beforeend", '<p><a href="#/login">Go to log in</a></p>');
    } catch (err) { msg.innerHTML = ""; msg.appendChild(show(err.message, "error")); }
  }

  function resetView(params) {
    const token = params.get("token");
    if (!token) {
      setMain(
        '<div class="card center"><h1>Reset password</h1><form id="ask">' +
        '<label>Email<input name="email" type="email" required></label>' +
        '<div class="actions"><button type="submit">Send reset link</button></div><div id="msg"></div></form></div>');
      document.getElementById("ask").addEventListener("submit", async function (ev) {
        ev.preventDefault();
        const msg = document.getElementById("msg");
        try {
          const data = await api("/auth/password-reset", { anonymous: true, body: { email: ev.target.email.value } });
          msg.innerHTML = ""; msg.appendChild(show(data.message, ""));
        } catch (err) { msg.innerHTML = ""; msg.appendChild(show(err.message, "error")); }
      });
      return;
    }
    setMain(
      '<div class="card center"><h1>Choose a new password</h1><form id="set">' +
      '<label>New password<input name="newPassword" type="password" minlength="12" required autocomplete="new-password"></label>' +
      '<div class="actions"><button type="submit">Save password</button></div><div id="msg"></div></form></div>');
    document.getElementById("set").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      const msg = document.getElementById("msg");
      try {
        const data = await api("/auth/password-reset/confirm", { anonymous: true,
          body: { token: token, newPassword: ev.target.newPassword.value } });
        msg.innerHTML = ""; msg.appendChild(show(data.message, ""));
      } catch (err) { msg.innerHTML = ""; msg.appendChild(show(err.message, "error")); }
    });
  }

  async function outboxView() {
    const data = await api("/dev/outbox", { anonymous: true }).catch(function (e) { return { error: e.message }; });
    if (data.error) { setMain('<div class="card"><p class="notice">' + esc(data.error) + "</p></div>"); return; }
    const items = (data.items || []).map(function (m) {
      return '<div class="card"><strong>' + esc(m.subject) + "</strong><br><span class=\"small muted\">To " + esc(m.to) +
        " · " + esc(formatDate(m.at)) + '</span><pre class="mail">' + esc(m.body) + "</pre></div>";
    }).join("");
    setMain('<h1>Mail outbox (development)</h1><p class="muted">This service writes mail here instead of sending it. ' +
      'Use the links to verify an account or reset a password.</p>' + (items || '<p class="muted">Nothing yet.</p>'));
  }

  // ---------- signed-in screens ----------

  async function dashboardView() {
    if (role() === "ADMIN") { location.hash = "#/admin"; return; }
    if (role() === "RESEARCHER") { location.hash = "#/history"; return; }
    const [me, samples] = await Promise.all([api("/auth/me"), api("/soil-measurements?size=50")]);
    const fields = me.fields || [];
    const fieldCards = fields.length ? fields.map(function (f) {
      return '<div class="card"><strong>' + esc(f.farmName) + '</strong><div class="muted small">' + esc(f.region) +
        " · code " + esc(f.fieldCode) + '</div><div class="actions">' +
        '<a class="button" href="#/field/' + esc(f.fieldId) + '">Health</a>' +
        '<a class="button secondary" href="#/history?fieldId=' + esc(f.fieldId) + '">History</a></div></div>';
    }).join("") : '<p class="muted">No fields are assigned to you yet. An administrator assigns fields after approval.</p>';
    const rows = (samples.items || []).map(function (s) {
      return "<tr><td><a href=\"#/sample/" + esc(s.sampleId) + '">' + esc(s.sampleId) + "</a></td><td>" + esc(s.fieldId) +
        "</td><td>" + esc(s.sampleDate) + "</td><td>" + esc(s.depthCm) + " cm</td><td>v" + esc(s.version) +
        "</td><td>" + badge(s.state) + "</td></tr>";
    }).join("");
    setMain(
      '<h1>Welcome, ' + esc(session.user.fullName) + '</h1>' +
      (role() === "FIELD_OPERATOR" ? '<div class="actions"><a class="button" href="#/submit">Submit a soil sample</a></div>' : "") +
      "<h2>Your fields</h2><div class=\"grid\">" + fieldCards + "</div>" +
      "<h2>Samples</h2>" + (rows ? '<div class="wide-table"><table><thead><tr><th>Sample</th><th>Field</th><th>Date</th><th>Depth</th><th>Version</th><th>Status</th></tr></thead><tbody>' + rows + "</tbody></table></div>" : '<p class="muted">No samples yet.</p>')
    );
  }

  async function submitView() {
    const me = await api("/auth/me");
    const options = (me.fields || []).map(function (f) {
      return '<option value="' + esc(f.fieldId) + '">' + esc(f.farmName) + " (" + esc(f.region) + ")</option>";
    }).join("");
    if (!options) { setMain('<div class="card"><p>You have no assigned fields, so you cannot submit samples yet.</p></div>'); return; }
    const today = new Date().toISOString().slice(0, 10);
    const inputs = BODY_KEYS.map(function (key) {
      const r = RANGES[key];
      return '<div><label>' + esc(r.label) + ' (' + esc(r.unit) + ')<input name="' + key + '" type="number" required min="' + r.min +
        '" max="' + r.max + '" step="' + r.step + '"></label><div class="hint">Good range ' + esc(r.good) +
        " · possible " + r.min + " to " + r.max + "</div></div>";
    }).join("");
    setMain(
      '<h1>Submit a soil sample</h1><div class="card"><form id="submit">' +
      '<div class="row"><label>Field<select name="fieldId" required>' + options + '</select></label>' +
      '<label>Sample date<input name="sampleDate" type="date" required max="' + today + '" value="' + today + '"></label>' +
      '<label>Depth (cm)<input name="depthCm" type="number" required min="0" max="100" step="1" value="20"></label>' +
      '<label>Lab reference <span class="hint">optional</span><input name="labReference" maxlength="40"></label></div>' +
      '<h2>Measurements</h2><div class="row">' + inputs + '</div>' +
      '<div class="actions"><button type="submit">Send sample</button></div><div id="msg"></div></form></div>');

    document.getElementById("submit").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      const f = ev.target;
      const msg = document.getElementById("msg");
      msg.innerHTML = "";
      const body = { fieldId: f.fieldId.value, sampleDate: f.sampleDate.value, depthCm: Number(f.depthCm.value) };
      if (f.labReference.value) body.labReference = f.labReference.value;
      for (const key of BODY_KEYS) {
        const r = RANGES[key];
        const value = Number(f[key].value);
        if (f[key].value === "" || value < r.min || value > r.max) {
          msg.appendChild(show(r.label + " must be between " + r.min + " and " + r.max + ".", "error"));
          return;
        }
        body[key] = value;
      }
      try {
        const data = await api("/soil-measurements", { method: "POST", body: body });
        location.hash = "#/sample/" + data.sampleId;
      } catch (err) { msg.appendChild(show(err.message, "error")); }
    });
  }

  async function sampleView(params, sampleId) {
    clearTimer();
    const s = await api("/soil-measurements/" + encodeURIComponent(sampleId));
    const values = BODY_KEYS.map(function (key) {
      const name = { nitrogenMgKg: "nitrogen", phosphorusMgKg: "phosphorus", potassiumMgKg: "potassium", ph: "ph", moisturePct: "moisture" }[key];
      const r = RANGES[key];
      return "<tr><td>" + esc(r.label) + "</td><td>" + esc(s.values[name]) + " " + esc(r.unit) + "</td><td class=\"muted\">" + esc(r.good) + "</td></tr>";
    }).join("");
    const flags = (s.flags || []).map(function (f) {
      return "<tr><td>" + esc(MEASURE_LABEL[f.measurement]) + "</td><td>" + badge(f.level) + "</td><td>" + badge(f.state) +
        "</td><td>" + esc(f.severity || "—") + "</td><td>" + (f.aiLevel ? esc(f.aiLevel) + (f.disagreement ? " (disagrees with rule, rule kept)" : " (agrees)") : "<span class=\"muted\">AI view pending</span>") + "</td></tr>";
    }).join("");
    const versions = (s.versions || []).map(function (v) {
      return "<tr><td>v" + esc(v.version) + "</td><td>" + badge(v.state) + "</td><td>" + esc(formatDate(v.createdAt)) +
        "</td><td>" + (v.supersedesVersion ? "replaces v" + esc(v.supersedesVersion) : "original") + "</td></tr>";
    }).join("");
    const inFlight = s.state === "RECEIVED" || s.state === "ANALYSING";
    let correction = "";
    if (s.canCorrect) {
      correction = '<h2>Correct this sample</h2><p class="hint">A correction saves a new version. The old values stay in the history. Allowed for 7 days after submission.</p>' +
        '<form id="correct"><div class="row">' + BODY_KEYS.map(function (key) {
          const r = RANGES[key];
          const name = { nitrogenMgKg: "nitrogen", phosphorusMgKg: "phosphorus", potassiumMgKg: "potassium", ph: "ph", moisturePct: "moisture" }[key];
          return '<label>' + esc(r.label) + '<input name="' + key + '" type="number" step="' + r.step + '" min="' + r.min +
            '" max="' + r.max + '" placeholder="' + esc(s.values[name]) + '"></label>';
        }).join("") + '</div><div class="actions"><button type="submit">Save new version</button></div><div id="msg"></div></form>';
    }
    setMain(
      '<p><a href="#/dashboard">← Back</a></p><h1>Sample ' + esc(s.sampleId) + ' <span class="small muted">v' + esc(s.version) + '</span></h1>' +
      '<div class="card"><p>' + badge(s.state) + ' Field ' + esc(s.fieldId) + ' · ' + esc(s.sampleDate) + ' · depth ' + esc(s.depthCm) +
      ' cm' + (s.labReference ? " · lab " + esc(s.labReference) : "") + '</p>' +
      (inFlight ? '<p class="notice warn">Analysis is running. This page refreshes by itself. Analysis may take longer when the system is busy.</p>' : "") +
      (s.state === "ANALYSIS_FAILED" ? '<p class="notice warn">The soil AI did not answer after 3 tries. The rule-based flags are shown below and the AI view is pending.' +
        (s.canReanalyse ? ' <button id="again" class="secondary">Analyse again</button>' : "") + "</p>" : "") +
      (s.health ? '<p>Soil health: <span class="health-big badge ' + esc(String(s.health.healthStatus).toLowerCase()) + '">' + esc(STATE_TEXT[s.health.healthStatus]) + "</span> <span class=\"small muted\">rule " + esc(s.health.ruleVersion) + " · AI " + esc(s.health.aiView) + "</span></p>" : "") +
      '</div><h2>Values</h2><div class="wide-table"><table><thead><tr><th>Measurement</th><th>Value</th><th>Good range</th></tr></thead><tbody>' + values + "</tbody></table></div>" +
      (flags ? "<h2>Flags</h2><div class=\"wide-table\"><table><thead><tr><th>Measurement</th><th>Level</th><th>State</th><th>Severity</th><th>AI view</th></tr></thead><tbody>" + flags + "</tbody></table></div>" : "") +
      "<h2>Versions</h2><table><thead><tr><th>Version</th><th>Status</th><th>Saved</th><th>Note</th></tr></thead><tbody>" + versions + "</tbody></table>" + correction
    );

    if (inFlight) timer = setTimeout(function () { sampleView(params, sampleId); }, 3000);
    const again = document.getElementById("again");
    if (again) again.addEventListener("click", async function () {
      try { await api("/soil-measurements/" + encodeURIComponent(sampleId) + "/reanalyse", { method: "POST", body: {} }); sampleView(params, sampleId); }
      catch (err) { alert(err.message); }
    });
    const form = document.getElementById("correct");
    if (form) form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      const f = ev.target;
      const msg = document.getElementById("msg");
      const body = {};
      BODY_KEYS.forEach(function (key) { if (f[key].value !== "") body[key] = Number(f[key].value); });
      try {
        await api("/soil-measurements/" + encodeURIComponent(sampleId) + "/corrections", { method: "POST", body: body });
        sampleView(params, sampleId);
      } catch (err) { msg.innerHTML = ""; msg.appendChild(show(err.message, "error")); }
    });
  }

  async function fieldView(params, fieldId) {
    const h = await api("/soil-health?fieldId=" + encodeURIComponent(fieldId));
    const flagRows = h.flags.map(function (f) {
      return "<tr><td>" + esc(MEASURE_LABEL[f.measurement]) + "</td><td>" + badge(f.level) + "</td><td>" + badge(f.state) +
        "</td><td>" + esc(f.severity || "—") + "</td></tr>";
    }).join("");
    const deficiencies = h.deficiencies.length ? h.deficiencies.map(function (d) {
      return "<li>" + esc(MEASURE_LABEL[d.nutrient]) + " is " + badge(d.state) + " (" + esc(d.severity) + ")</li>";
    }).join("") : '<li class="muted">No nutrient is too low or too high.</li>';
    setMain(
      '<p><a href="#/dashboard">← Back</a></p><h1>Field health</h1>' +
      '<div class="card"><span class="health-big badge ' + esc(String(h.healthStatus).toLowerCase()) + '">' + esc(STATE_TEXT[h.healthStatus]) + "</span>" +
      '<p class="muted">From sample ' + esc(h.sampleId) + " v" + esc(h.version) + " taken " + esc(h.sampleDate) + ". Analysed " + esc(formatDate(h.analysedAt)) + ".</p>" +
      (h.aiView !== "READY" ? '<p class="notice warn">AI view pending. The rule-based flags are shown and nothing is hidden.</p>' : "") +
      '<div class="actions"><a class="button secondary" href="#/history?fieldId=' + esc(fieldId) + '">Field history</a></div></div>' +
      "<h2>Nutrients too low or too high</h2><ul>" + deficiencies + "</ul>" +
      '<h2>All measurements</h2><div class="wide-table"><table><thead><tr><th>Measurement</th><th>Level</th><th>State</th><th>Severity</th></tr></thead><tbody>' + flagRows + "</tbody></table></div>"
    );
  }

  async function historyView(params) {
    const fieldId = params.get("fieldId") || "";
    const isResearcher = role() === "RESEARCHER";
    setMain(
      "<h1>" + (isResearcher ? "Anonymous soil history" : "Field history") + '</h1>' +
      '<form id="filter" class="card"><div class="row">' +
      (isResearcher ? "" : '<label>Field ID<input name="fieldId" value="' + esc(fieldId) + '" placeholder="fld_0412"></label>') +
      '<label>Region<input name="region" placeholder="Region North"></label>' +
      '<label>From<input name="from" type="date"></label><label>To<input name="to" type="date"></label></div>' +
      '<div class="actions"><button type="submit">Show</button></div></form><div id="out"></div>'
    );
    if (isResearcher) document.getElementById("filter").insertAdjacentHTML("afterend", '<p class="notice">Researchers see a made-up field code and the region only.</p>');
    async function load(query) {
      const out = document.getElementById("out");
      out.innerHTML = '<p class="muted">Loading…</p>';
      try {
        const data = await api("/soil-history?" + query);
        const rows = data.items.map(function (r) {
          const who = r.fieldCode
            ? "<td>" + esc(r.fieldCode) + "</td><td>" + esc(r.region) + "</td>"
            : "<td>" + esc(r.fieldName) + " <span class=\"muted small\">" + esc(r.fieldId) + "</span></td><td>" + esc(r.region) + "</td>";
          return "<tr><td>" + esc(r.sampleDate) + "</td>" + who + "<td>" + esc(r.depthCm) + " cm</td><td>" +
            badge(r.healthStatus) + "</td><td>" + (r.outOfRange && r.outOfRange.length ? esc(r.outOfRange.map(function (m) { return MEASURE_LABEL[m]; }).join(", ")) : "—") + "</td></tr>";
        }).join("");
        out.innerHTML = rows
          ? '<div class="wide-table"><table><thead><tr><th>Date</th><th>' + (isResearcher ? "Field code" : "Field") + "</th><th>Region</th><th>Depth</th><th>Health</th><th>Out of good range</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
          : '<p class="muted">No analysed samples match.</p>';
      } catch (err) { out.innerHTML = ""; out.appendChild(show(err.message, "error")); }
    }
    document.getElementById("filter").addEventListener("submit", function (ev) {
      ev.preventDefault();
      const q = new URLSearchParams();
      ["fieldId", "region", "from", "to"].forEach(function (k) {
        const v = ev.target[k] && ev.target[k].value;
        if (v) q.set(k, v);
      });
      load(q.toString());
    });
    const initial = new URLSearchParams();
    if (fieldId) initial.set("fieldId", fieldId);
    load(initial.toString());
  }

  async function adminView() {
    const [accounts, fields, log, peers] = await Promise.all([
      api("/admin/accounts?status=ALL"), api("/admin/fields"), api("/admin/audit-log?size=40"),
      api("/integration/peers").catch(function () { return { peers: {}, configured: 0 }; }),
    ]);
    const pending = accounts.items.filter(function (a) { return a.status === "PENDING_APPROVAL"; });
    const pendingRows = pending.map(function (a) {
      return "<tr><td>" + esc(a.fullName) + "<div class=\"muted small\">" + esc(a.email) + " · " + esc(a.organisation) + "</div></td>" +
        "<td>" + esc(ROLE_NAMES[a.requestedRole]) + "</td><td><select data-role=\"" + esc(a.id) + "\">" +
        ["FIELD_OPERATOR", "AGRONOMIST", "RESEARCHER"].map(function (r) {
          return '<option value="' + r + '"' + (r === a.requestedRole ? " selected" : "") + ">" + esc(ROLE_NAMES[r]) + "</option>";
        }).join("") + '</select></td><td><button data-approve="' + esc(a.id) + '">Approve</button> ' +
        '<button class="danger" data-reject="' + esc(a.id) + '">Reject</button></td></tr>';
    }).join("");
    const accountRows = accounts.items.map(function (a) {
      return "<tr><td>" + esc(a.fullName) + "<div class=\"muted small\">" + esc(a.email) + "</div></td><td>" + esc(ROLE_NAMES[a.role] || "—") +
        "</td><td>" + badge(a.status) + "</td><td>" + esc(a.fields.join(", ") || "—") +
        '</td><td><button class="secondary" data-revoke="' + esc(a.id) + '">Cancel sessions</button></td></tr>';
    }).join("");
    const userOptions = accounts.items.filter(function (a) { return a.status === "ACTIVE" && ["FIELD_OPERATOR", "AGRONOMIST", "FARMER"].indexOf(a.role) >= 0; })
      .map(function (a) { return '<option value="' + esc(a.id) + '">' + esc(a.fullName) + " (" + esc(ROLE_NAMES[a.role]) + ")</option>"; }).join("");
    const fieldOptions = fields.items.map(function (f) { return '<option value="' + esc(f.fieldId) + '">' + esc(f.farmName) + " (" + esc(f.fieldId) + ")</option>"; }).join("");
    const fieldRows = fields.items.map(function (f) {
      return "<tr><td>" + esc(f.farmName) + "</td><td>" + esc(f.fieldId) + "</td><td>" + esc(f.region) + "</td><td>" + esc(f.fieldCode) + "</td></tr>";
    }).join("");
    const logRows = log.items.map(function (l) {
      return "<tr><td>" + esc(formatDate(l.at)) + "</td><td>" + esc(l.actorRole || "") + "</td><td>" + esc(l.action) + "</td><td>" + esc(l.target || "") +
        "</td><td>" + esc(l.outcome) + "</td></tr>";
    }).join("");
    const peerRows = Object.keys(peers.peers || {}).map(function (name) {
      const p = peers.peers[name];
      return "<tr><td>" + esc(name) + "</td><td>" + esc(p.url) + "</td><td>" + (p.reachable ? badge("READY") : badge("ANALYSIS_FAILED")) + "</td></tr>";
    }).join("");

    setMain(
      "<h1>Administration</h1>" +
      "<h2>Waiting for approval</h2>" + (pendingRows ? '<div class="wide-table"><table><thead><tr><th>Person</th><th>Requested</th><th>Approve as</th><th></th></tr></thead><tbody>' + pendingRows + "</tbody></table></div>" : '<p class="muted">Nobody is waiting.</p>') +
      '<div id="msg"></div>' +
      "<h2>Accounts</h2><div class=\"wide-table\"><table><thead><tr><th>Person</th><th>Role</th><th>Status</th><th>Fields</th><th></th></tr></thead><tbody>" + accountRows + "</tbody></table></div>" +
      '<div class="grid"><div class="card"><h2>Assign a field</h2><form id="assign">' +
      '<label>Person<select name="userId">' + userOptions + '</select></label>' +
      '<label>Field<select name="fieldId">' + fieldOptions + '</select></label>' +
      '<label>Reason<input name="reason" required minlength="3" placeholder="e.g. new season, field transfer"></label>' +
      '<div class="actions"><button type="submit">Assign</button><button type="button" class="secondary" id="unassign">Remove assignment</button></div></form></div>' +
      '<div class="card"><h2>New field</h2><form id="newfield">' +
      '<label>Farm name<input name="farmName" required minlength="2"></label>' +
      '<label>Region<input name="region" required minlength="2"></label>' +
      '<div class="actions"><button type="submit">Create field</button></div></form></div>' +
      '<div class="card"><h2>New administrator</h2><form id="newadmin">' +
      '<label>Full name<input name="fullName" required></label><label>Email<input name="email" type="email" required></label>' +
      '<label>Password<input name="password" type="password" minlength="12" required></label>' +
      '<div class="actions"><button type="submit">Create</button></div><div id="adminmsg"></div></form></div></div>' +
      "<h2>Fields</h2><div class=\"wide-table\"><table><thead><tr><th>Farm</th><th>ID</th><th>Region</th><th>Code shown to researchers</th></tr></thead><tbody>" + fieldRows + "</tbody></table></div>" +
      "<h2>Connected services</h2>" + (peerRows ? '<div class="wide-table"><table><thead><tr><th>Service</th><th>Address</th><th>Reachable</th></tr></thead><tbody>' + peerRows + "</tbody></table></div>" : '<p class="muted">No other service is configured yet (set PEER_SERVICES).</p>') +
      "<h2>Activity log</h2><p class=\"hint\">Measurement values are never written to this log.</p>" +
      '<div class="wide-table"><table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Target</th><th>Outcome</th></tr></thead><tbody>' + logRows + "</tbody></table></div>"
    );

    const msg = document.getElementById("msg");
    const act = async function (fn) {
      msg.innerHTML = "";
      try { const r = await fn(); msg.appendChild(show(r.message, "")); adminView(); }
      catch (err) { msg.appendChild(show(err.message, "error")); }
    };
    app.querySelectorAll("[data-approve]").forEach(function (b) {
      b.addEventListener("click", function () {
        const id = b.getAttribute("data-approve");
        const sel = app.querySelector('select[data-role="' + id + '"]');
        act(function () { return api("/admin/accounts/" + id + "/approve", { method: "POST", body: { role: sel.value } }); });
      });
    });
    app.querySelectorAll("[data-reject]").forEach(function (b) {
      b.addEventListener("click", function () {
        const id = b.getAttribute("data-reject");
        act(function () { return api("/admin/accounts/" + id + "/reject", { method: "POST", body: {} }); });
      });
    });
    app.querySelectorAll("[data-revoke]").forEach(function (b) {
      b.addEventListener("click", function () {
        const id = b.getAttribute("data-revoke");
        act(function () { return api("/admin/accounts/" + id + "/revoke-sessions", { method: "POST", body: {} }); });
      });
    });
    document.getElementById("assign").addEventListener("submit", function (ev) {
      ev.preventDefault();
      const f = ev.target;
      act(function () { return api("/admin/assignments", { method: "POST", body: { userId: f.userId.value, fieldId: f.fieldId.value, reason: f.reason.value } }); });
    });
    document.getElementById("unassign").addEventListener("click", function () {
      const f = document.getElementById("assign");
      if (!f.reason.value || f.reason.value.length < 3) { msg.appendChild(show("Give a reason first.", "error")); return; }
      act(function () { return api("/admin/assignments/remove", { method: "POST", body: { userId: f.userId.value, fieldId: f.fieldId.value, reason: f.reason.value } }); });
    });
    document.getElementById("newfield").addEventListener("submit", function (ev) {
      ev.preventDefault();
      const f = ev.target;
      act(function () { return api("/admin/fields", { method: "POST", body: { farmName: f.farmName.value, region: f.region.value } }); });
    });
    document.getElementById("newadmin").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      const f = ev.target;
      const out = document.getElementById("adminmsg");
      out.innerHTML = "";
      try {
        const r = await api("/admin/admins", { method: "POST", body: { fullName: f.fullName.value, email: f.email.value, password: f.password.value } });
        out.appendChild(show(r.message + " Secret: " + r.totpSecret, ""));
        f.reset();
      } catch (err) { out.appendChild(show(err.message, "error")); }
    });
  }

  // ---------- start ----------

  window.addEventListener("hashchange", route);
  renderNav();
  route();
})();
