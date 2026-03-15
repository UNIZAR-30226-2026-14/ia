const botCountInput = document.getElementById("botCount");
const botLevelsContainer = document.getElementById("botLevels");
const randomnessInput = document.getElementById("randomness");
const seedInput = document.getElementById("seed");
const maxTurnsInput = document.getElementById("maxTurns");
const runBtn = document.getElementById("runBtn");
const compactRacksInput = document.getElementById("compactRacks");
const serverStatus = document.getElementById("serverStatus");

const rankingBars = document.getElementById("rankingBars");
const gameStateEl = document.getElementById("gameState");
const poolMeta = document.getElementById("poolMeta");
const poolTilesView = document.getElementById("poolTilesView");
const poolSummary = document.getElementById("poolSummary");
const poolToggle = document.getElementById("poolToggle");
const poolWrap = document.querySelector(".pool-wrap");

const firstBtn = document.getElementById("firstBtn");
const prevBtn = document.getElementById("prevBtn");
const playBtn = document.getElementById("playBtn");
const nextBtn = document.getElementById("nextBtn");
const lastBtn = document.getElementById("lastBtn");
const speedSelect = document.getElementById("speedSelect");
const turnSlider = document.getElementById("turnSlider");
const turnLabel = document.getElementById("turnLabel");

const turnInfo = document.getElementById("turnInfo");
const boardView = document.getElementById("boardView");
const racksView = document.getElementById("racksView");
const logView = document.getElementById("logView");
const timelinePreview = document.getElementById("timelinePreview");
const timelineToggle = document.getElementById("timelineToggle");
const timelineWrap = document.querySelector(".timeline-wrap");

const historySidebar = document.getElementById("historySidebar");
const historyToggle = document.getElementById("historyToggle");
const historyContent = document.getElementById("historyContent");
const historyList = document.getElementById("historyList");
const batchCountInput = document.getElementById("batchCount");
const batchBotCountInput = document.getElementById("batchBotCount");
const batchBotLevelsContainer = document.getElementById("batchBotLevels");
const batchRandomnessInput = document.getElementById("batchRandomness");
const batchMaxTurnsInput = document.getElementById("batchMaxTurns");
const batchRandomSeedInput = document.getElementById("batchRandomSeed");
const batchRandomLevelsInput = document.getElementById("batchRandomLevels");
const batchRandomRandomnessInput = document.getElementById("batchRandomRandomness");
const batchRandomMaxTurnsInput = document.getElementById("batchRandomMaxTurns");
const batchSeedInput = document.getElementById("batchSeed");
const batchCreateBtn = document.getElementById("batchCreateBtn");
const batchProgress = document.getElementById("batchProgress");
const batchProgressFill = document.getElementById("batchProgressFill");
const batchProgressText = document.getElementById("batchProgressText");
const historyStats = document.getElementById("historyStats");
const historyClearBtn = document.getElementById("historyClearBtn");

const presetButtons = document.querySelectorAll("[data-preset]");

const defaultLevels = [1, 5, 10, 8];
let timeline = [];
let cursor = 0;
let timer = null;
let lastResult = null;
let currentSearchTerm = ""; // Término de búsqueda actual para la línea temporal
let batchGames = []; // Partidas creadas en batch (no todas las ejecutadas)
let batchStats = null; // Estadísticas de las partidas batch

function buildBotSelectors(count, preserve = [], container = botLevelsContainer) {
  container.innerHTML = "";
  for (let i = 0; i < count; i += 1) {
    const value = preserve[i] || defaultLevels[i] || 5;
    const row = document.createElement("label");
    row.className = "bot-level";
    row.innerHTML = `<span>Bot-${i + 1}</span><input type="number" min="1" max="10" value="${value}" data-level-index="${i}" />`;
    container.appendChild(row);
  }
}

function readLevels() {
  return [...botLevelsContainer.querySelectorAll("input")]
    .map((input) => Math.max(1, Math.min(10, parseInt(input.value || "5", 10))))
    .filter((n) => !Number.isNaN(n));
}

function applyPreset(name) {
  const cfg = {
    balanced: { bots: 3, levels: [2, 6, 9], randomness: 0.25, seed: 1234, turns: 100 },
    competitive: { bots: 4, levels: [4, 7, 9, 10], randomness: 0.12, seed: 99, turns: 130 },
    chaos: { bots: 4, levels: [1, 3, 8, 10], randomness: 0.45, seed: 2026, turns: 110 },
  }[name];
  if (!cfg) return;

  botCountInput.value = String(cfg.bots);
  buildBotSelectors(cfg.bots, cfg.levels);
  randomnessInput.value = String(cfg.randomness);
  seedInput.value = String(cfg.seed);
  maxTurnsInput.value = String(cfg.turns);
}

function getTileClass(tile) {
  if (tile === "J*") return "tile-joker";
  const colorTag = tile.slice(0, 1);
  if (colorTag === "K") return "tile-black";
  if (colorTag === "B") return "tile-blue";
  if (colorTag === "R") return "tile-red";
  if (colorTag === "O") return "tile-orange";
  return "";
}

function parseTileParts(tile) {
  if (tile === "J*") return { value: "J", suit: "*", colorClass: "tile-joker" };
  const suit = tile.slice(0, 1);
  const value = tile.slice(1, 3);
  return { value, suit, colorClass: getTileClass(tile) };
}

function tileNode(tile) {
  const { value, suit, colorClass } = parseTileParts(tile);
  const compact = compactRacksInput.checked;
  const wrapper = document.createElement("span");
  wrapper.className = "tile-svg-wrap";
  wrapper.innerHTML = `
    <svg class="tile-svg ${compact ? "compact" : ""}" viewBox="0 0 72 94" aria-label="${tile}">
      <defs>
        <linearGradient id="tileBg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#fdfefe"/>
          <stop offset="100%" stop-color="#e8edf2"/>
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="68" height="90" rx="10" fill="#bcc8d8"/>
      <rect x="5" y="5" width="62" height="84" rx="9" fill="url(#tileBg)"/>
      <rect x="8" y="8" width="56" height="78" rx="8" fill="#ffffff"/>
      <text x="36" y="45" text-anchor="middle" class="${colorClass}" font-size="28" font-weight="700" font-family="Arial">${value}</text>
      <text x="36" y="70" text-anchor="middle" class="${colorClass}" font-size="13" font-weight="700" font-family="Arial">${suit}</text>
    </svg>
  `;
  return wrapper;
}

function parseMeldText(raw) {
  const inner = raw.replaceAll("[", "").replaceAll("]", "").trim();
  if (!inner) return [];
  return inner.split(/\s+/);
}

function tileValue(tile) {
  if (tile === "J*") return null;
  const n = parseInt(tile.slice(1, 3), 10);
  return Number.isNaN(n) ? null : n;
}

function tileColor(tile) {
  if (tile === "J*") return null;
  return tile.slice(0, 1);
}

function isGroupMeld(meld) {
  const naturals = meld.filter((t) => t !== "J*");
  if (!naturals.length) return false;
  const values = new Set(naturals.map(tileValue));
  const colors = naturals.map(tileColor);
  return values.size === 1 && new Set(colors).size === colors.length;
}

function isRunMeld(meld) {
  const naturals = meld.filter((t) => t !== "J*");
  if (!naturals.length) return false;
  const colors = new Set(naturals.map(tileColor));
  const values = naturals.map(tileValue);
  return colors.size === 1 && new Set(values).size === values.length;
}

function orderRunMeld(meld) {
  const naturals = meld.filter((t) => t !== "J*");
  const jokers = meld.filter((t) => t === "J*");
  const n = meld.length;
  const values = naturals.map(tileValue).filter((v) => v !== null);
  if (!values.length) return meld;

  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const minStart = Math.max(1, maxVal - n + 1);
  const maxStart = Math.min(minVal, 13 - n + 1);
  const naturalByValue = new Map(naturals.map((t) => [tileValue(t), t]));

  for (let start = minStart; start <= maxStart; start += 1) {
    const seqValues = [];
    for (let v = start; v < start + n; v += 1) seqValues.push(v);
    const seqSet = new Set(seqValues);
    const naturalsFit = values.every((v) => seqSet.has(v));
    if (!naturalsFit) continue;

    const result = [];
    let jokerIndex = 0;
    for (const v of seqValues) {
      const naturalTile = naturalByValue.get(v);
      if (naturalTile) result.push(naturalTile);
      else {
        result.push(jokers[jokerIndex] || "J*");
        jokerIndex += 1;
      }
    }
    return result;
  }

  return [...naturals.sort((a, b) => tileValue(a) - tileValue(b)), ...jokers];
}

function orderGroupMeld(meld) {
  const naturals = meld.filter((t) => t !== "J*");
  const jokers = meld.filter((t) => t === "J*");
  const colorOrder = { K: 1, B: 2, O: 3, R: 4 };
  naturals.sort((a, b) => (colorOrder[tileColor(a)] || 9) - (colorOrder[tileColor(b)] || 9));
  return [...naturals, ...jokers];
}

function normalizeMeldForDisplay(meld) {
  if (isRunMeld(meld)) {
    return { typeLabel: "Escalera (run)", tiles: orderRunMeld(meld) };
  }
  if (isGroupMeld(meld)) {
    return { typeLabel: "Grupo (set)", tiles: orderGroupMeld(meld) };
  }
  return { typeLabel: "Combinacion", tiles: meld };
}

function setPlaying(playing) {
  playBtn.textContent = playing ? "Pausar" : "Reproducir";
  if (playing) {
    const speed = parseInt(speedSelect.value, 10);
    timer = setInterval(() => {
      if (!timeline.length) return;
      if (cursor >= timeline.length - 1) {
        setPlaying(false);
        return;
      }
      cursor += 1;
      updateView();
    }, speed);
  } else if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

function parseAction(turn, botId) {
  if (turn.player_id !== botId) {
    return { text: "Esperando turno", cls: "action-wait" };
  }
  const detail = (turn.detail || "").toLowerCase();
  const move = (turn.move || "").toUpperCase();

  if (detail.includes("penalizacion")) {
    return { text: "Penalizacion por jugada invalida", cls: "action-penalty" };
  }
  if (move.includes("PASAR")) {
    const drawMatch = turn.detail.match(/roba\s+([0-9]{2}[KBOR]|J\*)/i);
    if (drawMatch) {
      return { text: `Pasa y coge ${drawMatch[1]}`, cls: "action-draw" };
    }
    return { text: "Pasa turno", cls: "action-pass" };
  }
  if (detail.startsWith("extiende")) {
    return { text: "Pone ficha en tablero", cls: "action-extend" };
  }
  if (detail.startsWith("juega")) {
    return { text: "Coloca grupo/escalera", cls: "action-play" };
  }
  if (detail.includes("roba")) {
    return { text: "Coge ficha del pozo", cls: "action-draw" };
  }
  return { text: "Realiza movimiento", cls: "action-play" };
}

function endReasonUi(data) {
  const winner = data.winner_id;
  if (winner) {
    return {
      text: `Partida finalizada: gana ${winner}`,
      cls: "end-winner",
    };
  }
  if (data.end_reason === "blocked_no_moves_no_draw") {
    return {
      text: "Partida finalizada: bloqueo (sin jugadas ni robos)",
      cls: "end-blocked",
    };
  }
  return {
    text: "Partida finalizada por limite de turnos",
    cls: "end-max",
  };
}

function buildRankingOrder(racks, rack_points) {
  const entries = Object.keys(rack_points || {}).map((bot) => ({
    bot,
    tiles: (racks && racks[bot]) ? racks[bot].length : 0,
    points: (rack_points && rack_points[bot]) != null ? rack_points[bot] : 0,
  }));
  entries.sort((a, b) => a.tiles - b.tiles || a.points - b.points);
  return entries;
}

function renderSummary(data) {
  const lastTurn = timeline.length ? timeline[timeline.length - 1] : null;
  const racks = lastTurn?.racks || {};
  const ordered = buildRankingOrder(racks, data.final_points);
  const n = Math.max(ordered.length, 1);

  if (rankingBars) {
    rankingBars.innerHTML = "";
    ordered.forEach(({ bot, tiles, points }, idx) => {
      const bar = document.createElement("div");
      bar.className = "rank-bar";
      const ratio = idx === 0 ? 100 : Math.max(6, Math.round(100 - (idx / n) * 100));
      bar.innerHTML = `
        <div>${bot}</div>
        <div class="rank-track"><div class="rank-fill" style="width:${ratio}%"></div></div>
        <div>${tiles}f · ${points}</div>
      `;
      rankingBars.appendChild(bar);
    });
  }
}

function renderRankingFromTurn(turn) {
  const ordered = buildRankingOrder(turn.racks, turn.rack_points);
  const n = Math.max(ordered.length, 1);

  if (rankingBars) {
    rankingBars.innerHTML = "";
    ordered.forEach(({ bot, tiles, points }, idx) => {
      const bar = document.createElement("div");
      bar.className = "rank-bar";
      const ratio = idx === 0 ? 100 : Math.max(6, Math.round(100 - (idx / n) * 100));
      bar.innerHTML = `
        <div>${bot}</div>
        <div class="rank-track"><div class="rank-fill" style="width:${ratio}%"></div></div>
        <div>${tiles}f · ${points}</div>
      `;
      rankingBars.appendChild(bar);
    });
  }
}

function renderPool(turn) {
  const counts = turn.pool_counts || {};
  const entries = Object.entries(counts);
  const total = turn.pool_remaining ?? 0;
  poolMeta.textContent = total === 0 ? "Total: 0 fichas." : `Total: ${total} fichas.`;
  poolTilesView.innerHTML = "";
  if (poolSummary) poolSummary.innerHTML = "";

  if (total === 0) {
    if (poolSummary) {
      const t = document.createElement("table");
      t.className = "pool-mini-table";
      t.innerHTML = "<tr><th>K</th><th>O</th><th>R</th><th>B</th><th>J*</th></tr><tr class=\"pool-row-total\"><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>";
      poolSummary.appendChild(t);
    }
    poolTilesView.textContent = "(bolsa vacía)";
    return;
  }

  if (poolSummary) {
    const bySuit = { K: 0, O: 0, R: 0, B: 0, "J*": 0 };
    entries.forEach(([tile, count]) => {
      if (tile === "J*") bySuit["J*"] = count;
      else if (tile.length >= 1) {
        const suit = tile.slice(0, 1);
        if (bySuit[suit] !== undefined) bySuit[suit] += count;
      }
    });
    const table = document.createElement("table");
    table.className = "pool-mini-table";
    table.innerHTML = "<tr><th>K</th><th>O</th><th>R</th><th>B</th><th>J*</th></tr>";
    const row = table.insertRow();
    row.innerHTML = `<td>${bySuit.K}</td><td>${bySuit.O}</td><td>${bySuit.R}</td><td>${bySuit.B}</td><td>${bySuit["J*"]}</td>`;
    const foot = table.insertRow();
    foot.className = "pool-row-total";
    foot.innerHTML = `<td colspan="5"><strong>Total ${total}</strong></td>`;
    poolSummary.appendChild(table);
  }

  entries.forEach(([tile, count]) => {
    const item = document.createElement("div");
    item.className = "pool-item";
    item.appendChild(tileNode(tile));

    const countSpan = document.createElement("span");
    countSpan.className = "pool-count";
    countSpan.textContent = `x${count}`;
    item.appendChild(countSpan);
    poolTilesView.appendChild(item);
  });
}

function renderBoard(turn) {
  boardView.innerHTML = "";
  const melds = turn.board_melds?.length
    ? turn.board_melds
    : (turn.board || []).map(parseMeldText);

  if (!melds.length) {
    boardView.textContent = "(tablero vacio)";
    return;
  }

  melds.forEach((meld, idx) => {
    const normalized = normalizeMeldForDisplay(meld);
    const box = document.createElement("div");
    box.className = "meld-box";
    const title = document.createElement("div");
    title.className = "meld-title";
    title.textContent = `${normalized.typeLabel} #${idx + 1}`;
    box.appendChild(title);

    const row = document.createElement("div");
    row.className = "tile-row";
    normalized.tiles.forEach((tile) => row.appendChild(tileNode(tile)));
    box.appendChild(row);
    boardView.appendChild(box);
  });
}

function renderRacks(turn) {
  racksView.innerHTML = "";
  if (compactRacksInput.checked) racksView.classList.add("compact");
  else racksView.classList.remove("compact");

  Object.entries(turn.racks).forEach(([bot, tiles]) => {
    const card = document.createElement("div");
    card.className = "rack-card";

    const header = document.createElement("div");
    header.className = "rack-header";
    const action = parseAction(turn, bot);
    header.innerHTML = `
      <div class="rack-player-side">
        <strong>${bot}</strong>
        <span class="action-badge ${action.cls}">${action.text}</span>
      </div>
      <span>${tiles.length} fichas</span>
    `;
    card.appendChild(header);

    const row = document.createElement("div");
    row.className = "tile-row";
    tiles.forEach((tile) => row.appendChild(tileNode(tile)));
    card.appendChild(row);

    racksView.appendChild(card);
  });
}

function renderLog() {
  if (!logView) return;
  logView.innerHTML = "";
  // Usar la variable global o leer del input directamente
  const searchInput = document.getElementById("timelineSearch");
  const showAllCheckbox = document.getElementById("timelineShowAll");
  const searchTerm = currentSearchTerm || (searchInput ? searchInput.value.toLowerCase().trim() : "");
  const showAll = showAllCheckbox ? showAllCheckbox.checked : false;
  
  timeline.forEach((turn, i) => {
    const line = document.createElement("div");
    const lineText =
      `T${String(turn.turn).padStart(3, "0")} ${turn.player_id} (nivel=${turn.level}) -> ${turn.move} | ` +
      `${turn.detail} | mano(rack)=${turn.rack_count} | pozo=${turn.pool_remaining}`;
    const matchesSearch = !searchTerm || lineText.toLowerCase().includes(searchTerm);
    
    // Si hay búsqueda y "ver todas" está activado, mostrar todas pero marcar las que coinciden
    const shouldShow = showAll && searchTerm ? true : matchesSearch;
    const shouldHighlight = searchTerm && matchesSearch && showAll;
    
    line.className = `log-line ${i === cursor ? "active" : ""} ${shouldShow ? "" : "hidden"} ${shouldHighlight ? "search-match-highlight" : ""}`;
    
    if (matchesSearch && searchTerm) {
      // Resaltar el término de búsqueda
      try {
        const escapedTerm = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const parts = lineText.split(new RegExp(`(${escapedTerm})`, 'gi'));
        line.innerHTML = parts.map((part) => 
          part.toLowerCase() === searchTerm.toLowerCase() 
            ? `<mark class="search-highlight">${part}</mark>` 
            : part
        ).join('');
      } catch (e) {
        // Si hay error en la regex, usar texto plano
        line.textContent = lineText;
      }
    } else {
      line.textContent = lineText;
    }
    line.addEventListener("click", () => {
      setPlaying(false);
      cursor = i;
      updateView();
    });
    logView.appendChild(line);
  });
}

function updateView() {
  if (!timeline.length) {
    turnLabel.textContent = "Turno 0/0";
    turnInfo.textContent = "Sin datos.";
    boardView.innerHTML = "";
    boardView.textContent = "(tablero vacío)";
    racksView.innerHTML = "";
    logView.innerHTML = "";
    if (timelinePreview) timelinePreview.textContent = "—";
    if (poolMeta) poolMeta.textContent = "—";
    poolTilesView.innerHTML = "";
    if (poolSummary) poolSummary.innerHTML = "<table class=\"pool-mini-table\"><tr><td>Total</td><td>—</td></tr></table>";
    if (gameStateEl) gameStateEl.textContent = "—";
    if (rankingBars) rankingBars.innerHTML = "";
    return;
  }

  const turn = timeline[cursor];
  turnSlider.max = String(timeline.length - 1);
  turnSlider.value = String(cursor);
  turnLabel.textContent = `Turno ${cursor + 1}/${timeline.length}`;
  turnInfo.textContent =
    `${turn.player_id} (nivel=${turn.level}, aleat=${turn.randomness.toFixed(2)}) | ` +
    `${turn.move} | ${turn.detail} | pozo restante=${turn.pool_remaining}`;

  if (gameStateEl) {
    const atEnd = cursor === timeline.length - 1 && lastResult;
    if (atEnd && lastResult.winner_id) {
      gameStateEl.textContent = `Ganador: ${lastResult.winner_id}`;
      gameStateEl.className = "game-state game-state-winner";
    } else if (atEnd && lastResult.end_reason === "blocked_no_moves_no_draw") {
      gameStateEl.textContent = "Partida finalizada: bloqueo (sin jugadas ni robos)";
      gameStateEl.className = "game-state game-state-blocked";
    } else if (atEnd && lastResult.end_reason === "max_turns") {
      gameStateEl.textContent = "Partida finalizada por límite de turnos";
      gameStateEl.className = "game-state game-state-max";
    } else {
      gameStateEl.textContent = "En curso";
      gameStateEl.className = "game-state";
    }
  }

  if (timelinePreview) {
    timelinePreview.textContent =
      `T${String(turn.turn).padStart(3, "0")} ${turn.player_id} (nivel=${turn.level}) → ${turn.move} | ${turn.detail} | mano=${turn.rack_count} | pozo=${turn.pool_remaining}`;
  }

  renderBoard(turn);
  renderRacks(turn);
  renderRankingFromTurn(turn);
  renderPool(turn);
  renderLog();
}

async function runSimulation() {
  setPlaying(false);
  runBtn.disabled = true;
  runBtn.textContent = "Simulando...";
  if (gameStateEl) gameStateEl.textContent = "Ejecutando partida...";
  try {
    const payload = {
      levels: readLevels(),
      randomness: parseFloat(randomnessInput.value),
      seed: parseInt(seedInput.value, 10),
      max_turns: parseInt(maxTurnsInput.value, 10),
    };

    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Error HTTP ${res.status}`);

    const data = await res.json();
    lastResult = data;
    timeline = data.timeline || [];
    cursor = 0;
    renderSummary(data);
    updateView();
    // NO guardar automáticamente - solo las creadas con batch
  } catch (err) {
    if (gameStateEl) {
      gameStateEl.textContent = `Error: ${err.message}`;
      gameStateEl.className = "game-state game-state-error";
    }
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Iniciar simulacion";
  }
}

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("offline");
    serverStatus.textContent = "Servidor conectado";
    serverStatus.style.background = "#0f3a2a";
    serverStatus.style.color = "#7efab7";
  } catch {
    serverStatus.textContent = "Servidor no disponible";
    serverStatus.style.background = "#4e1f26";
    serverStatus.style.color = "#ffb9c2";
  }
}

botCountInput.addEventListener("change", () => {
  const current = readLevels();
  buildBotSelectors(parseInt(botCountInput.value, 10), current);
});

presetButtons.forEach((btn) =>
  btn.addEventListener("click", () => applyPreset(btn.dataset.preset))
);

runBtn.addEventListener("click", runSimulation);

firstBtn.addEventListener("click", () => {
  setPlaying(false);
  cursor = 0;
  updateView();
});
prevBtn.addEventListener("click", () => {
  setPlaying(false);
  cursor = Math.max(0, cursor - 1);
  updateView();
});
nextBtn.addEventListener("click", () => {
  setPlaying(false);
  cursor = Math.min(Math.max(0, timeline.length - 1), cursor + 1);
  updateView();
});
lastBtn.addEventListener("click", () => {
  setPlaying(false);
  cursor = Math.max(0, timeline.length - 1);
  updateView();
});
playBtn.addEventListener("click", () => setPlaying(!timer));

turnSlider.addEventListener("input", () => {
  setPlaying(false);
  cursor = parseInt(turnSlider.value, 10) || 0;
  updateView();
});

compactRacksInput.addEventListener("change", updateView);

if (timelineToggle && timelineWrap) {
  timelineToggle.addEventListener("click", () => {
    const willOpen = !timelineWrap.classList.contains("is-open");
    timelineWrap.classList.toggle("is-open");
    timelineToggle.setAttribute("aria-expanded", timelineWrap.classList.contains("is-open"));
    if (willOpen) {
      setTimeout(() => {
        const active = logView.querySelector(".log-line.active");
        if (active) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }, 280);
    }
  });
}

// Inicializar buscador de timeline - enfoque más directo y robusto
let searchInitialized = false;

function setupTimelineSearch() {
  if (searchInitialized) return;
  
  // Intentar múltiples veces hasta que el elemento exista
  const searchInput = document.getElementById("timelineSearch");
  const searchClear = document.getElementById("timelineSearchClear");
  const showAllCheckbox = document.getElementById("timelineShowAll");
  
  if (!searchInput) {
    // Reintentar después de un breve delay (hasta 5 segundos)
    if (typeof setupTimelineSearch.attempts === 'undefined') {
      setupTimelineSearch.attempts = 0;
    }
    setupTimelineSearch.attempts++;
    if (setupTimelineSearch.attempts < 25) { // 25 intentos * 200ms = 5 segundos máximo
      setTimeout(setupTimelineSearch, 200);
    } else {
      console.error("No se pudo encontrar timelineSearch después de múltiples intentos");
    }
    return;
  }
  
  // Marcar como inicializado
  searchInitialized = true;
  console.log("Buscador de timeline inicializado correctamente");
  
  // Función para actualizar la vista
  const updateSearchView = () => {
    renderLog();
    // Scroll al primer resultado visible
    setTimeout(() => {
      if (!logView) return;
      const firstVisible = logView.querySelector(".log-line:not(.hidden)");
      if (firstVisible) {
        firstVisible.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }, 100);
  };
  
  // Event listener para input
  searchInput.addEventListener("input", function(e) {
    currentSearchTerm = this.value.toLowerCase().trim();
    updateSearchView();
  });
  
  // Event listener para Escape
  searchInput.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
      this.value = "";
      currentSearchTerm = "";
      if (showAllCheckbox) showAllCheckbox.checked = false;
      updateSearchView();
    }
  });
  
  // Event listener para el botón de limpiar
  if (searchClear) {
    searchClear.addEventListener("click", function(e) {
      e.preventDefault();
      e.stopPropagation();
      searchInput.value = "";
      currentSearchTerm = "";
      if (showAllCheckbox) showAllCheckbox.checked = false;
      updateSearchView();
      searchInput.focus();
    });
  }
  
  // Event listener para el checkbox "Ver todas las líneas"
  if (showAllCheckbox) {
    showAllCheckbox.addEventListener("change", function(e) {
      updateSearchView();
    });
  }
}

// Inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(setupTimelineSearch, 100);
  });
} else {
  setTimeout(setupTimelineSearch, 100);
}

// También intentar después de delays adicionales para asegurar que funcione
setTimeout(setupTimelineSearch, 500);
setTimeout(setupTimelineSearch, 1000);
setTimeout(setupTimelineSearch, 2000);

// Funciones para manejar partidas batch (solo las creadas con el botón)
function saveBatchGame(result) {
  const MAX_GAMES_WITH_TIMELINE = 50; // Guardar timeline completo para las últimas 50 partidas (carga rápida)
  
  const game = {
    id: Date.now() + Math.random(),
    timestamp: new Date().toISOString(),
    seed: result.seed,
    levels: result.levels,
    randomness: result.randomness,
    max_turns: result.max_turns,
    winner_id: result.winner_id,
    end_reason: result.end_reason,
    turns_played: result.turns_played,
    final_points: result.final_points,
  };
  
  // Asignar el timeline solo a la partida que acabamos de añadir (index 0)
  game.data = {
    seed: result.seed,
    levels: result.levels,
    randomness: result.randomness,
    max_turns: result.max_turns,
    winner_id: result.winner_id,
    end_reason: result.end_reason,
    turns_played: result.turns_played,
    final_points: result.final_points,
    timeline: result.timeline,
  };
  
  batchGames.unshift(game); // Añadir al principio
  
  // En partidas más antiguas (índice >= MAX_GAMES_WITH_TIMELINE), quitar solo el timeline para ahorrar espacio
  // NO sobrescribir su .data con el result nuevo (eso hacía que todas mostraran la misma partida)
  batchGames.forEach((g, index) => {
    if (index >= MAX_GAMES_WITH_TIMELINE && g.data) {
      delete g.data.timeline;
    }
  });
  
  // Reducir el límite a 100 partidas para evitar problemas de cuota
  if (batchGames.length > 100) {
    batchGames = batchGames.slice(0, 100);
  }
  
  try {
    localStorage.setItem("rummiplus_batch_games", JSON.stringify(batchGames));
    // Actualizar tanto las estadísticas como la lista de partidas
    updateBatchStats();
    renderHistoryList();
  } catch (error) {
    if (error.name === 'QuotaExceededError' || error.message.includes('quota')) {
      console.warn("Cuota de almacenamiento excedida. Eliminando timelines de partidas antiguas...");
      // Eliminar todos los timelines y guardar solo metadatos
      batchGames.forEach(g => {
        if (g.data) {
          delete g.data.timeline;
        }
      });
      try {
        localStorage.setItem("rummiplus_batch_games", JSON.stringify(batchGames));
        updateBatchStats();
        renderHistoryList();
      } catch (e) {
        console.error("No se pudo guardar después de reducir:", e);
        // Si aún falla, reducir a 50 partidas sin timeline
        batchGames = batchGames.slice(0, 50).map(g => {
          const { data, ...rest } = g;
          return rest;
        });
        try {
          localStorage.setItem("rummiplus_batch_games", JSON.stringify(batchGames));
          updateBatchStats();
          renderHistoryList();
        } catch (e2) {
          // Último recurso: limpiar todo
          localStorage.removeItem("rummiplus_batch_games");
          batchGames = [];
          updateBatchStats();
          renderHistoryList();
        }
      }
    } else {
      throw error;
    }
  }
}

function loadBatchGames() {
  try {
    const stored = localStorage.getItem("rummiplus_batch_games");
    if (stored) {
      batchGames = JSON.parse(stored);
      // Validar y limpiar datos corruptos o incompletos
      batchGames = batchGames.filter(game => {
        // Asegurar que todas las partidas tengan los campos mínimos necesarios
        if (!game || typeof game !== 'object') return false;
        if (!game.levels || !Array.isArray(game.levels) || game.levels.length === 0) {
          console.warn("Partida sin levels válido, eliminando:", game);
          return false;
        }
        if (game.seed === undefined || game.seed === null) {
          console.warn("Partida sin seed válido, eliminando:", game);
          return false;
        }
        // Asegurar valores por defecto para campos opcionales
        if (game.randomness === undefined) game.randomness = 0.25;
        if (game.max_turns === undefined) game.max_turns = 300;
        return true;
      });
      // Guardar de vuelta si se eliminaron partidas inválidas
      if (batchGames.length !== JSON.parse(stored).length) {
        localStorage.setItem("rummiplus_batch_games", JSON.stringify(batchGames));
      }
    }
  } catch (e) {
    console.error("Error cargando partidas batch:", e);
    batchGames = [];
  }
  renderHistoryList();
  updateBatchStats();
}

function updateBatchStats() {
  if (!historyStats) return;
  
  if (batchGames.length === 0) {
    historyStats.innerHTML = '<div class="stats-empty">Ejecuta partidas para ver estadísticas</div>';
    return;
  }
  
  const total = batchGames.length;
  const winners = {};
  const endReasons = {};
  let totalTurns = 0;
  const pointsByPlayer = {};
  const allPlayerIds = new Set(); // Para rastrear todos los bots que han participado
  const turnsDistribution = [];
  
  batchGames.forEach(game => {
    // Ganadores
    if (game.winner_id) {
      winners[game.winner_id] = (winners[game.winner_id] || 0) + 1;
      allPlayerIds.add(game.winner_id);
    }
    // Razones de finalización
    endReasons[game.end_reason] = (endReasons[game.end_reason] || 0) + 1;
    // Turnos
    totalTurns += game.turns_played;
    turnsDistribution.push(game.turns_played);
    // Puntos - esto nos ayuda a identificar todos los bots
    if (game.final_points) {
      Object.entries(game.final_points).forEach(([id, pts]) => {
        allPlayerIds.add(id);
        if (!pointsByPlayer[id]) {
          pointsByPlayer[id] = [];
        }
        pointsByPlayer[id].push(pts);
      });
    }
    // También revisar los niveles para identificar todos los bots
    if (game.levels) {
      game.levels.forEach((level, idx) => {
        const botId = `Bot-${idx + 1}`;
        allPlayerIds.add(botId);
        if (!pointsByPlayer[botId]) {
          pointsByPlayer[botId] = [];
        }
        if (!winners[botId]) {
          winners[botId] = 0;
        }
      });
    }
  });
  
  const avgTurns = total > 0 ? Math.round(totalTurns / total) : 0;
  turnsDistribution.sort((a, b) => a - b);
  const medianTurns = turnsDistribution.length > 0 
    ? turnsDistribution[Math.floor(turnsDistribution.length / 2)]
    : 0;
  const minTurns = turnsDistribution.length > 0 ? turnsDistribution[0] : 0;
  const maxTurns = turnsDistribution.length > 0 ? turnsDistribution[turnsDistribution.length - 1] : 0;
  
  // Ordenar todos los IDs de bot numéricamente (Bot-1, Bot-2, Bot-3, Bot-4)
  const sortedPlayerIds = Array.from(allPlayerIds).sort((a, b) => {
    const numA = parseInt(a.match(/\d+/)?.[0] || '0');
    const numB = parseInt(b.match(/\d+/)?.[0] || '0');
    return numA - numB;
  });
  
  const endReasonEntries = Object.entries(endReasons);
  
  let statsHTML = `
    <div class="stats-section">
      <div class="stats-row">
        <span class="stats-label">Total:</span>
        <span class="stats-value">${total}</span>
      </div>
      <div class="stats-row">
        <span class="stats-label">Turnos media:</span>
        <span class="stats-value">${avgTurns}</span>
      </div>
      <div class="stats-row">
        <span class="stats-label">Turnos:</span>
        <span class="stats-value">${minTurns}/${medianTurns}/${maxTurns}</span>
      </div>
    </div>
  `;
  
  // Mostrar victorias de todos los bots (incluso con 0 victorias)
  if (sortedPlayerIds.length > 0) {
    statsHTML += `
      <div class="stats-section">
        <div class="stats-title">Victorias</div>
        ${sortedPlayerIds.map(id => {
          const wins = winners[id] || 0;
          return `
            <div class="stats-row">
              <span class="stats-label">${id}:</span>
              <span class="stats-value">${wins} (${total > 0 ? Math.round(wins * 100 / total) : 0}%)</span>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }
  
  if (endReasonEntries.length > 0) {
    statsHTML += `
      <div class="stats-section">
        <div class="stats-title">Finalización</div>
        ${endReasonEntries.map(([reason, count]) => `
          <div class="stats-row">
            <span class="stats-label">${reason === 'winner' ? 'Ganador' : reason === 'max_turns' ? 'Límite' : reason === 'blocked_no_moves_no_draw' ? 'Bloqueo' : reason}:</span>
            <span class="stats-value">${count} (${Math.round(count * 100 / total)}%)</span>
          </div>
        `).join('')}
      </div>
    `;
  }
  
  // Mostrar puntos de todos los bots
  if (sortedPlayerIds.length > 0) {
    statsHTML += `
      <div class="stats-section">
        <div class="stats-title">Puntos media</div>
        ${sortedPlayerIds.map(id => {
          const points = pointsByPlayer[id] || [];
          if (points.length === 0) {
            return `
              <div class="stats-row">
                <span class="stats-label">${id}:</span>
                <span class="stats-value">-</span>
              </div>
            `;
          }
          const avg = Math.round(points.reduce((a, b) => a + b, 0) / points.length);
          const min = Math.min(...points);
          const max = Math.max(...points);
          return `
            <div class="stats-row">
              <span class="stats-label">${id}:</span>
              <span class="stats-value">${avg} (${min}-${max})</span>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }
  
  historyStats.innerHTML = statsHTML;
}

function renderHistoryList() {
  if (!historyList) return;
  
  // Actualizar el título con el contador
  const historyListHeader = document.querySelector(".history-list-header h3");
  if (historyListHeader) {
    historyListHeader.textContent = `Partidas creadas (${batchGames.length})`;
  }
  
  historyList.innerHTML = "";
  
  if (batchGames.length === 0) {
    historyList.innerHTML = '<div class="history-empty">No hay partidas creadas</div>';
    return;
  }
  
  // Renderizar TODAS las partidas sin límite
  batchGames.forEach((game, index) => {
    const item = document.createElement("div");
    item.className = "history-item";
    item.dataset.gameIndex = String(index);
    const date = new Date(game.timestamp);
    const winnerText = game.winner_id ? `Ganador: ${game.winner_id}` : `Finalizada: ${game.end_reason}`;
    const pointsText = game.final_points
      ? Object.entries(game.final_points)
          .map(([id, pts]) => `${id}:${pts}`)
          .join(", ")
      : "";
    item.innerHTML = `
      <div class="history-item-header">
        <span class="history-item-seed">Seed: ${game.seed}</span>
        <span class="history-item-date">${date.toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" })}</span>
      </div>
      <div class="history-item-body">
        <div class="history-item-winner">${winnerText}</div>
        <div class="history-item-info">Turnos: ${game.turns_played} | ${pointsText}</div>
      </div>
    `;
    item.addEventListener("click", async () => {
      const idx = parseInt(item.dataset.gameIndex, 10);
      const gameToLoad = batchGames[idx];
      if (gameToLoad) {
        await loadGame(gameToLoad);
      }
    });
    historyList.appendChild(item);
  });
  
  // Asegurar que el scroll funcione correctamente
  if (historyList && historyList.scrollHeight > historyList.clientHeight) {
    // El contenedor tiene scroll disponible
  }
}

async function loadGame(game) {
  // Validar que tenemos los datos mínimos necesarios
  if (!game) {
    console.error("loadGame: game es null o undefined");
    alert("Error: Datos de partida inválidos");
    return;
  }
  
  // Validar datos necesarios para regenerar
  if (!game.levels || !Array.isArray(game.levels) || game.levels.length === 0) {
    console.error("loadGame: levels inválido", game);
    alert("Error: No se pueden cargar los niveles de la partida");
    return;
  }
  
  if (game.seed === undefined || game.seed === null) {
    console.error("loadGame: seed inválido", game);
    alert("Error: No se puede cargar el seed de la partida");
    return;
  }
  
  // Si tenemos el timeline guardado, usarlo directamente (carga instantánea)
  if (game.data && game.data.timeline && Array.isArray(game.data.timeline) && game.data.timeline.length > 0) {
    try {
      timeline = game.data.timeline;
      lastResult = {
        winner_id: game.data.winner_id || game.winner_id,
        end_reason: game.data.end_reason || game.end_reason,
      };
      cursor = timeline.length - 1;
      setPlaying(false);
      updateView();
      return;
    } catch (e) {
      console.error("Error usando timeline guardado, regenerando:", e);
      // Continuar para regenerar desde el servidor
    }
  }
  
  // Si no tenemos timeline guardado, regenerarlo desde el servidor (más lento)
  let loadingMsg = null;
  try {
    // Mostrar indicador de carga
    try {
      loadingMsg = document.createElement("div");
      loadingMsg.textContent = "Cargando partida...";
      loadingMsg.style.cssText = "position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.9); color: white; padding: 20px; border-radius: 8px; z-index: 10000; font-family: monospace;";
      document.body.appendChild(loadingMsg);
    } catch (e) {
      console.warn("No se pudo mostrar mensaje de carga:", e);
    }
    
    const requestBody = {
      levels: game.levels,
      randomness: game.randomness !== undefined ? game.randomness : 0.25,
      seed: game.seed,
      max_turns: game.max_turns !== undefined ? game.max_turns : 300,
    };
    
    // Timeout más largo para partidas grandes
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 segundos timeout
    
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    if (loadingMsg && loadingMsg.parentNode) {
      document.body.removeChild(loadingMsg);
      loadingMsg = null;
    }
    
    if (!response.ok) {
      const errorText = await response.text().catch(() => "Error desconocido");
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }
    
    const result = await response.json();
    if (!result || !result.timeline) {
      throw new Error("Respuesta inválida del servidor: falta timeline");
    }
    
    timeline = result.timeline || [];
    lastResult = {
      winner_id: result.winner_id || game.winner_id,
      end_reason: result.end_reason || game.end_reason,
    };
    cursor = timeline.length - 1;
    setPlaying(false);
    updateView();
  } catch (error) {
    if (loadingMsg && loadingMsg.parentNode) {
      document.body.removeChild(loadingMsg);
    }
    console.error("Error cargando partida:", error);
    console.error("Datos de la partida:", game);
    alert("No se pudo cargar la partida. Error: " + error.message + "\n\nRevisa la consola para más detalles.");
  }
}

if (poolToggle && poolWrap) {
  poolToggle.addEventListener("click", () => {
    poolWrap.classList.toggle("is-open");
    const open = poolWrap.classList.contains("is-open");
    poolToggle.setAttribute("aria-expanded", open);
    const textSpan = poolToggle.querySelector(".pool-toggle-text");
    if (textSpan) textSpan.textContent = "Bolsa";
    const icon = poolToggle.querySelector(".pool-toggle-icon");
    if (icon) icon.textContent = open ? "▲" : "▼";
  });
}

buildBotSelectors(parseInt(botCountInput.value, 10), [1, 5, 10]);
checkHealth();

// Inicializar historial
loadBatchGames();
if (batchBotCountInput && batchBotLevelsContainer) {
  buildBotSelectors(parseInt(batchBotCountInput.value, 10), [1, 5, 10], batchBotLevelsContainer);
  batchBotCountInput.addEventListener("change", () => {
    buildBotSelectors(parseInt(batchBotCountInput.value, 10), [1, 5, 10], batchBotLevelsContainer);
  });
}

// Toggle del menú lateral de historial
if (historyToggle && historySidebar) {
  historyToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = historySidebar.classList.toggle("is-open");
    historyToggle.setAttribute("aria-expanded", isOpen);
    const icon = historyToggle.querySelector(".history-toggle-icon");
    if (icon) {
      icon.textContent = isOpen ? "▶" : "◀";
    }
  });
}

// Crear múltiples partidas
if (batchCreateBtn) {
  batchCreateBtn.addEventListener("click", async () => {
    const count = parseInt(batchCountInput.value, 10) || 5;
    const botCount = parseInt(batchBotCountInput.value, 10) || 3;
    const useRandomLevels = batchRandomLevelsInput && batchRandomLevelsInput.checked;
    const useRandomRandomness = batchRandomRandomnessInput && batchRandomRandomnessInput.checked;
    const useRandomMaxTurns = batchRandomMaxTurnsInput && batchRandomMaxTurnsInput.checked;
    const baseRandomness = parseFloat(batchRandomnessInput.value) || 0.25;
    const baseMaxTurns = parseInt(batchMaxTurnsInput.value, 10) || 300;
    const useRandomSeed = batchRandomSeedInput && batchRandomSeedInput.checked;
    const baseSeed = parseInt(batchSeedInput.value, 10) || 1000;
    
    batchCreateBtn.disabled = true;
    batchCreateBtn.textContent = "Creando...";
    if (batchProgress) batchProgress.style.display = "block";
    
    for (let i = 0; i < count; i++) {
      // Generar niveles
      let levels;
      if (useRandomLevels) {
        levels = Array.from({ length: botCount }, () => Math.floor(Math.random() * 10) + 1);
      } else {
        levels = Array.from(batchBotLevelsContainer.querySelectorAll("input")).map(
          (input) => Math.max(1, Math.min(10, parseInt(input.value || "5", 10)))
        );
      }
      
      // Generar aleatoriedad
      const randomness = useRandomRandomness ? Math.random() : baseRandomness;
      
      // Generar max_turns
      const maxTurns = useRandomMaxTurns 
        ? Math.floor(Math.random() * 200) + 200 // Entre 200 y 400
        : baseMaxTurns;
      
      // Generar seed
      const seed = useRandomSeed 
        ? baseSeed + i * 1000 + Math.floor(Math.random() * 1000) 
        : baseSeed + i;
      
      // Actualizar progreso
      if (batchProgressFill) {
        batchProgressFill.style.width = `${((i + 1) / count) * 100}%`;
      }
      if (batchProgressText) {
        batchProgressText.textContent = `${i + 1} / ${count}`;
      }
      
      try {
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            levels,
            randomness,
            seed,
            max_turns: maxTurns,
          }),
        });
        if (!response.ok) {
          const errorText = await response.text().catch(() => "Error desconocido");
          throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        const result = await response.json();
        if (!result || !result.seed) {
          throw new Error("Respuesta inválida del servidor");
        }
        saveBatchGame(result);
        // saveBatchGame ya actualiza estadísticas y lista automáticamente
      } catch (error) {
        console.error(`Error creando partida ${i + 1}/${count}:`, error);
        // Mostrar error en el progreso
        if (batchProgressText) {
          batchProgressText.textContent = `${i + 1} / ${count} (Error en ${i + 1})`;
        }
        // Continuar con la siguiente partida en lugar de detenerse
      }
      // Pequeño delay para evitar sobrecargar el servidor
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    
    batchCreateBtn.disabled = false;
    batchCreateBtn.textContent = "Crear partidas";
    if (batchProgress) batchProgress.style.display = "none";
    loadBatchGames();
    // Actualizar estadísticas una vez más al finalizar
    updateBatchStats();
  });
}

// Botón para limpiar todas las partidas guardadas
if (historyClearBtn) {
  historyClearBtn.addEventListener("click", () => {
    if (confirm("¿Estás seguro de que quieres eliminar todas las partidas guardadas? Esta acción no se puede deshacer.")) {
      batchGames = [];
      localStorage.removeItem("rummiplus_batch_games");
      renderHistoryList(); // Esto actualizará el contador también
      updateBatchStats();
    }
  });
}

runSimulation();
