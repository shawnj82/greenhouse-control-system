
// Helper: resolve grid container supporting legacy ID
function getGridContainer() {
    return document.getElementById('greenhouse-grid') ||
           document.getElementById('greenhouse-grid-table-container');
}
// JavaScript for Crane Creek Greenhouse Web Interface

// Ensure overlay containers exist and return references
function ensureOverlays(container) {
    if (!container) container = getGridContainer();
    if (!container) return { fixturesOverlay: null, sensorsOverlay: null };

    let fixturesOverlay = container.querySelector('#lights-overlay');
    let sensorsOverlay = container.querySelector('#sensors-overlay');

    if (!fixturesOverlay) {
        fixturesOverlay = document.createElement('div');
        fixturesOverlay.id = 'lights-overlay';
        fixturesOverlay.className = 'lights-overlay';
        container.appendChild(fixturesOverlay);
    }
    if (!sensorsOverlay) {
        sensorsOverlay = document.createElement('div');
        sensorsOverlay.id = 'sensors-overlay';
        sensorsOverlay.className = 'sensors-overlay';
        container.appendChild(sensorsOverlay);
    }

    return { fixturesOverlay, sensorsOverlay };
}

async function renderLightAmountOverlay() {
    console.log('[LightOverlay] renderLightAmountOverlay() called');
    console.log('[LightOverlay] Current alpha setting:', luxScaleSettings.alpha);
    const container = getGridContainer();
    if (!container) {
        console.warn('[LightOverlay] No grid container found');
        return;
    }

    clearLightAmountOverlay();

    // Fetch zone light metrics
    let zoneMetrics = {};
    try {
        const resp = await fetch('/api/zone-light-metrics');
        const data = await resp.json();
        zoneMetrics = data.zones || {};
    } catch (e) {
        console.warn('[LightOverlay] Failed to fetch zone light metrics:', e);
        return;
    }

    const overlay = document.createElement('div');
    overlay.id = 'light-amount-overlay';
    overlay.className = 'light-amount-overlay';
    overlay.style.gridTemplateColumns = `repeat(${gridSize.cols}, 1fr)`;
    overlay.style.gridTemplateRows = `repeat(${gridSize.rows}, 1fr)`;
    // Match the grid gap to align overlay cells with the underlying grid
    const cs = window.getComputedStyle(container);
    const gapVal = cs.gap || `${cs.rowGap || 0} ${cs.columnGap || 0}`;
    if (gapVal) overlay.style.gap = gapVal;

    const lightMode = (userSettings.light_unit || 'lux').toLowerCase();
    let cellsWithData = 0;
    let cellsWithoutData = 0;

    for (let row = 0; row < gridSize.rows; row++) {
        for (let col = 0; col < gridSize.cols; col++) {
            const zoneKey = `${row}-${col}`;
            const zone = zoneMetrics[zoneKey];
            const cell = document.createElement('div');
            if (!zone) {
                cell.className = 'light-amount-cell no-data';
                overlay.appendChild(cell);
                cellsWithoutData++;
                continue;
            }
            cellsWithData++;
            
            // Check if zone data is valid
            const isValid = zone.valid !== false; // default to true if not specified
            
            let displayValue, colorValue, colorText, colorAlpha = luxScaleSettings.alpha;
            
            if (!isValid) {
                // No valid sensor data - show "?" with minimal styling
                displayValue = '?';
                cell.className = 'light-amount-cell no-data';
                cell.innerHTML = `
                    <div class="light-amount-info">
                        <div class="lux-value" style="color: #999; font-size: 1.2rem;">?</div>
                    </div>
                `;
            } else if (lightMode === 'par' && zone.ppfd != null) {
                displayValue = `${Math.round(zone.ppfd)} µmol`;
                colorValue = ppfdToColor(zone.ppfd);
                colorText = getTextColorForBackground(colorValue, colorAlpha);
                cell.style.backgroundColor = `rgba(${colorValue.r}, ${colorValue.g}, ${colorValue.b}, ${colorAlpha})`;
                cell.className = `light-amount-cell light-intensity-${Math.min(9, Math.floor((zone.lux || 0) / 100))}`;
                cell.innerHTML = `
                    <div class="light-amount-info">
                        <div class="lux-value" style="color: ${colorText};">${displayValue}</div>
                    </div>
                `;
            } else {
                displayValue = Math.round(zone.lux);
                // Use a default CCT if not available
                const cct = 4500;
                const baseRgb = cctToRgb(cct);
                const scaledRgb = scaleRgbByLuxLog(baseRgb, zone.lux, luxScaleSettings);
                colorValue = scaledRgb;
                colorText = getTextColorForBackground(scaledRgb, colorAlpha);
                cell.style.backgroundColor = `rgba(${scaledRgb.r}, ${scaledRgb.g}, ${scaledRgb.b}, ${colorAlpha})`;
                cell.className = `light-amount-cell light-intensity-${Math.min(9, Math.floor((zone.lux || 0) / 100))}`;
                cell.innerHTML = `
                    <div class="light-amount-info">
                        <div class="lux-value" style="color: ${colorText};">${displayValue}</div>
                    </div>
                `;
            }
            overlay.appendChild(cell);
        }
    }

    console.log(`[LightOverlay] Created ${cellsWithData} cells with data, ${cellsWithoutData} without data`);
    console.log('[LightOverlay] Overlay element:', overlay);
    console.log('[LightOverlay] Overlay childElementCount:', overlay.childElementCount);

    // Append under container; with z-index it will sit below fixtures and sensors
    container.appendChild(overlay);
    console.log('[LightOverlay] Overlay appended. Container now has', container.childElementCount, 'children');
    console.log('[LightOverlay] Overlay is in DOM:', document.body.contains(overlay));
}

const cropPresets = {
    lettuce: {
        seedling: { red: 35, blue: 35, white: 30, par: 150, hours: 16 },
        vegetative: { red: 45, blue: 25, white: 30, par: 200, hours: 16 },
        harvest: { red: 50, blue: 20, white: 30, par: 250, hours: 14 }
    },
    basil: {
        seedling: { red: 35, blue: 35, white: 30, par: 150, hours: 16 },
        vegetative: { red: 50, blue: 25, white: 25, par: 250, hours: 16 }
    },
    spinach: {
        seedling: { red: 35, blue: 35, white: 30, par: 150, hours: 16 },
        vegetative: { red: 45, blue: 25, white: 30, par: 200, hours: 16 }
    },
    zinnia: {
        seedling: { red: 40, blue: 30, white: 30, par: 150, hours: 16 },
        vegetative: { red: 50, blue: 20, white: 30, par: 200, hours: 16 },
        flowering: { red: 55, blue: 15, white: 30, par: 250, hours: 16 }
    },
    herbs: {
        seedling: { red: 35, blue: 35, white: 30, par: 150, hours: 16 },
        vegetative: { red: 50, blue: 25, white: 25, par: 200, hours: 16 }
    }
};
let currentLights = {};
let currentLightSensors = { config: { sensors: {} }, readings: {} };
let gridSize = { rows: 24, cols: 12 }; // Default will be overridden by zones.json
// Estimation settings (UI-backed)
let estimationSettings = {
    enabled: true,
    power: 1.5,      // Reduced from 2 to make distance falloff less aggressive
    maxSensors: 6,   // Increased from 4 to use more sensors in estimation
    maxDistance: 5   // Reduced from 100 to focus on nearby sensors only
};
// Lux scaling settings (log mapping)
let luxScaleSettings = {
    maxLux: 30000,  // Updated to 30k lux for white
    softFloor: 50,
    gamma: 2.0,
    alpha: 1.0
};

// Device control functions
function controlDevice(device, action) {
    fetch(`/api/control/${device}/${action}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(`${device} turned ${action}`, 'success');
                setTimeout(updateStatus, 1000); // Update status after 1 second
                // If a light was toggled, trigger immediate sensor refresh
                if (device.includes('light')) {
                    if (typeof refreshLightSensorsOnce === 'function') {
                        refreshLightSensorsOnce();
                    }
                }
            } else {
                showNotification(`Failed to control ${device}: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            showNotification(`Error controlling ${device}: ${error}`, 'error');
        });
}

function controlFan(speed) {
    document.getElementById('fanSpeedValue').textContent = speed + '%';
    fetch(`/api/control/fan/speed?speed=${speed}`)
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                showNotification(`Failed to set fan speed: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            showNotification(`Error setting fan speed: ${error}`, 'error');
        });
}

// Status update function
function updateStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            updateStatusDisplay(data);
        })
        .catch(error => {
            console.error('Error updating status:', error);
        });
}

function updateStatusDisplay(status) {
    // Update status cards if they exist
    const tempCard = document.querySelector('.status-card:nth-child(1) .status-value');
    const humCard = document.querySelector('.status-card:nth-child(2) .status-value');
    const lightCard = document.querySelector('.status-card:nth-child(3) .status-value');
    const soilCard = document.querySelector('.status-card:nth-child(4) .status-value');

    if (tempCard) {
        const tC = (status.temperature_c != null && !Number.isNaN(status.temperature_c)) ? Number(status.temperature_c) : null;
        if (tC == null) {
            tempCard.textContent = '--';
        } else if ((userSettings.temperature_unit || 'C') === 'F') {
            const f = (tC * 9/5) + 32;
            tempCard.textContent = f.toFixed(1) + '°F';
        } else {
            tempCard.textContent = tC.toFixed(1) + '°C';
        }
    }
    if (humCard) {
        humCard.textContent = (status.humidity != null && !Number.isNaN(status.humidity)) ?
            Number(status.humidity).toFixed(1) + '%' : '--';
    }
    if (lightCard) {
        const lightMode = (userSettings.light_unit || 'lux').toLowerCase();
        if (lightMode === 'par') {
            const v = status.light_ppfd != null ? Number(status.light_ppfd) : null;
            lightCard.textContent = (v != null && !Number.isNaN(v)) ? Math.round(v) + ' µmol' : '--';
        } else {
            const v = status.light_lux != null ? Number(status.light_lux) : null;
            lightCard.textContent = (v != null && !Number.isNaN(v)) ? Math.round(v) + ' lux' : '--';
        }
    }
    if (soilCard) {
        soilCard.textContent = (status.soil_moisture != null && !Number.isNaN(status.soil_moisture)) ? 
            Math.round(Number(status.soil_moisture)) + '%' : '--';
    }
}

// Greenhouse grid functions
function loadGreenhouseGrid(editable = false) {
    Promise.all([
        fetch('/api/zones').then(response => response.json()),
        fetch('/api/lights').then(response => response.json()),
        fetch('/api/light-sensors').then(response => response.json())
    ])
    .then(([zonesData, lightsData, lightSensorsData]) => {
        currentZones = zonesData;
        currentLights = lightsData;
        currentLightSensors = lightSensorsData || { config: { sensors: {} }, readings: {} };
        gridSize = zonesData.grid_size || { rows: 24, cols: 12 };
        renderGrid(editable);
        
        // Render lights overlay after a short delay to ensure grid is rendered
        setTimeout(() => {
            renderLightsOverlay();
        }, 100);
    })
    .catch(error => {
        console.error('Error loading grid data:', error);
        // Fallback to default grid
        renderGrid(editable);
    });
}

function renderGrid(editable = false) {
    const container = getGridContainer();
    if (!container) return;

    // Performance check for very large grids
    const totalCells = gridSize.rows * gridSize.cols;
    if (totalCells > 2000) {
        console.warn(`Large grid detected (${gridSize.rows}×${gridSize.cols} = ${totalCells} cells). Consider using smaller sections for better performance.`);
    }
    
    // For very large grids, warn user about potential performance impact
    if (totalCells > 5000 && editable) {
        const proceed = confirm(`This grid size (${gridSize.rows}×${gridSize.cols} = ${totalCells} cells) may impact browser performance. Continue?`);
        if (!proceed) return;
    }

    // Clear the container; we'll re-add overlays later
    while (container.firstChild) container.removeChild(container.firstChild);
    container.style.display = 'grid';
    container.style.gridTemplateColumns = `repeat(${gridSize.cols}, 1fr)`;
    // Ensure overlays position relative to the grid container, even for legacy containers
    container.style.position = 'relative';
    if (!container.classList.contains('grid-container')) {
        container.classList.add('grid-container');
    }

    // Insert grid cells before overlays (if present) so overlays remain on top
    let overlays = [];
    if (!editable) {
        overlays = Array.from(container.children).filter(child => child.id === 'lights-overlay' || child.id === 'sensors-overlay');
        overlays.forEach(ov => container.removeChild(ov));
    }
    let cellCount = 0;
    for (let row = 0; row < gridSize.rows; row++) {
        for (let col = 0; col < gridSize.cols; col++) {
            const cell = document.createElement('div');
            const key = `${row}-${col}`;
            
            cell.className = 'grid-cell';
            if (editable) {
                cell.className += ' editable';
            }
            const zone = currentZones.zones && currentZones.zones[key];
            if (zone) {
                cell.className += ' planted';
                let stageLine = '';
                if (zone.stage || zone.growth_stage) {
                    const stage = zone.stage || zone.growth_stage;
                    stageLine = `<span class="zone-stage-badge">${stage.charAt(0).toUpperCase() + stage.slice(1)}</span><br>`;
                }
                cell.innerHTML = `
                    <div style="font-size: 0.7rem;">
                        <strong>${zone.crop_type || 'Unknown'}</strong><br>
                        ${stageLine}
                        ${zone.planted_date ? new Date(zone.planted_date).toLocaleDateString() : ''}
                    </div>
                `;
                if (zone.planted_date) {
                    const plantedDate = new Date(zone.planted_date);
                    const daysSincePlanted = Math.floor((new Date() - plantedDate) / (1000 * 60 * 60 * 24));
                    const waterFreq = zone.water_needs || 2;
                    if (daysSincePlanted > 0 && daysSincePlanted % waterFreq === 0) {
                        cell.className += ' needs-water';
                    }
                }
            } else {
                cell.innerHTML = `<span style="color: #999;">${row + 1},${col + 1}</span>`;
            }
            
            // Add click event listener for editable grids
            if (editable) {
                cell.addEventListener('click', function() {
                    selectZone(key, cell);
                });
                cell.style.cursor = 'pointer';
            }
            
            container.appendChild(cell);
            cellCount++;
        }
    }
    // If no cells rendered, append a small note (should not happen)
    if (cellCount === 0) {
        const note = document.createElement('div');
        note.style.color = '#999';
        note.textContent = 'No grid cells to display.';
        container.appendChild(note);
    }
    // ...existing code...
    // ...existing code...
    // Ensure overlays exist and are on top for both dashboard and zones
    const { fixturesOverlay, sensorsOverlay } = ensureOverlays(container);
    container.appendChild(fixturesOverlay);
    container.appendChild(sensorsOverlay);
    renderLightsOverlay();
}

// Lights overlay functions
function renderLightsOverlay() {
    const container = getGridContainer();
    const { fixturesOverlay } = ensureOverlays(container);
    // On dashboard, overlays may not exist yet when this is called (due to async grid rendering)
    if (!fixturesOverlay || !container) {
        // Only log if in editable mode (zones page)
        if (window.location.pathname === '/zones') {
            console.log('Missing overlay or container elements');
        }
        return;
    }

    // Handle light fixtures overlay
    const showFixtures = document.getElementById('showLightFixtures');
    if (showFixtures && showFixtures.checked) {
        renderLightFixtures(fixturesOverlay, container);
    } else {
        fixturesOverlay.style.display = 'none';
        fixturesOverlay.innerHTML = '';
    }

    // Handle light amount overlay
    // Render initially if checked, but don't re-render on every call (let sensor refresh handle updates)
    const showAmount = document.getElementById('showLightAmount');
    if (showAmount && showAmount.checked) {
        const existingOverlay = document.getElementById('light-amount-overlay');
        if (!existingOverlay) {
            // Only render if overlay doesn't exist yet (initial load or after being cleared)
            console.log('[LightOverlay] Initial render - checkbox is checked, overlay does not exist');
            renderLightAmountOverlay();
        } else {
            console.log('[LightOverlay] Overlay already exists, skipping re-render');
        }
    } else if (showAmount) {
        console.log('[LightOverlay] Clearing overlay - checkbox is unchecked');
        clearLightAmountOverlay();
    }

    // Handle sensor markers overlay
    const showSensorMarkers = document.getElementById('showSensorMarkers');
    if (showSensorMarkers && showSensorMarkers.checked) {
        renderSensorMarkers();
    } else {
        clearSensorMarkers();
    }
}

function renderLightFixtures(overlay, container) {
    overlay.innerHTML = '';
    overlay.style.display = 'block';
    
    // Wait for container to be properly sized
    setTimeout(() => {
        // Get container content-box dimensions for scaling
        const rect = container.getBoundingClientRect();
        const cs = window.getComputedStyle(container);
        const paddingLeft = parseFloat(cs.paddingLeft) || 0;
        const paddingRight = parseFloat(cs.paddingRight) || 0;
        const paddingTop = parseFloat(cs.paddingTop) || 0;
        const paddingBottom = parseFloat(cs.paddingBottom) || 0;
        const borderLeft = parseFloat(cs.borderLeftWidth) || 0;
        const borderRight = parseFloat(cs.borderRightWidth) || 0;
        const borderTop = parseFloat(cs.borderTopWidth) || 0;
        const borderBottom = parseFloat(cs.borderBottomWidth) || 0;
        const totalWidth = rect.width;
        const totalHeight = rect.height;
        const contentWidth = totalWidth - borderLeft - borderRight - paddingLeft - paddingRight;
        const contentHeight = totalHeight - borderTop - borderBottom - paddingTop - paddingBottom;
        
        // Skip if container has no size yet
            if (contentWidth <= 0 || contentHeight <= 0) {
            setTimeout(() => renderLightsOverlay(), 100);
            return;
        }
        
    // Account for CSS grid gaps when computing cell size
    const colGap = parseFloat(cs.columnGap || cs.gap || '0') || 0;
    const rowGap = parseFloat(cs.rowGap || cs.gap || '0') || 0;
    const cellWidth = (contentWidth - colGap * (gridSize.cols - 1)) / gridSize.cols;
    const cellHeight = (contentHeight - rowGap * (gridSize.rows - 1)) / gridSize.rows;
        
        // Render each light fixture
        if (currentLights.lights) {
            Object.entries(currentLights.lights).forEach(([lightId, light]) => {
                // Handle both old and new light data formats
                const status = light.status || 'on';
                const widthIn = light.width_inches || 24;
                const depthIn = (light.depth_inches != null ? light.depth_inches : (light.height_inches || 12));
                const du = (userSettings.distance_unit || 'in').toLowerCase();
                const widthDisp = du === 'cm' ? Math.round(widthIn * 2.54) + 'cm' : `${widthIn}"`;
                const depthDisp = du === 'cm' ? Math.round(depthIn * 2.54) + 'cm' : `${depthIn}"`;
                
                const lightElement = document.createElement('div');
                lightElement.className = `light-fixture light-fixture-${status}`;
                lightElement.setAttribute('data-light-id', lightId);
                
                // Guard and clamp positions within grid
                const pos = light.position || {};
                const col = Math.max(0, parseInt(pos.col) || 0);
                const row = Math.max(0, parseInt(pos.row) || 0);
                const colSpan = Math.max(1, parseInt(pos.col_span) || 1);
                const rowSpan = Math.max(1, parseInt(pos.row_span) || 1);
                if (col >= gridSize.cols || row >= gridSize.rows) {
                    return; // out of bounds
                }
                const clampedColSpan = Math.max(1, Math.min(colSpan, gridSize.cols - col));
                const clampedRowSpan = Math.max(1, Math.min(rowSpan, gridSize.rows - row));
                // Calculate position and size relative to overlay origin (padding edge)
                const left = col * (cellWidth + colGap);
                const top = row * (cellHeight + rowGap);
                const width_px = clampedColSpan * cellWidth + (clampedColSpan - 1) * colGap;
                const height_px = clampedRowSpan * cellHeight + (clampedRowSpan - 1) * rowGap;
                
                lightElement.style.cssText = `
                    position: absolute;
                    left: ${left}px;
                    top: ${top}px;
                    width: ${width_px}px;
                    height: ${height_px}px;
                    z-index: 20;
                `;
                
                // Add light info tooltip
                lightElement.innerHTML = `
                    <div class="light-info">
                        <div class="light-name">${light.name}</div>
                        <div class="light-specs">${widthDisp}×${depthDisp} | ${light.power_watts}W</div>
                        <div class="light-status status-${status}">${status.toUpperCase()}</div>
                    </div>
                `;
                
                // Add click handler for light control
                lightElement.addEventListener('click', (e) => {
                    e.stopPropagation();
                    toggleLight(lightId, light);
                });
                
                overlay.appendChild(lightElement);
            });
        }
    }, 50);
}

function getLightDisplayOption() {
    // This function is no longer needed with independent checkboxes
    // but keeping for compatibility
    const showFixtures = document.getElementById('showLightFixtures');
    const showAmount = document.getElementById('showLightAmount');
    
    if (showFixtures && showFixtures.checked) return 'fixtures';
    if (showAmount && showAmount.checked) return 'amount';
    return 'none';
}

function clearLightAmountOverlay() {
    const existingOverlay = document.getElementById('light-amount-overlay');
    if (existingOverlay) {
        existingOverlay.remove();
    }
}

function clearSensorMarkers() {
    const overlay = document.getElementById('sensors-overlay');
    if (overlay) overlay.innerHTML = '';
}

function renderSensorMarkers() {
    const overlay = document.getElementById('sensors-overlay');
    const container = getGridContainer();
    if (!overlay || !container) return;
    overlay.innerHTML = '';

    const rect = container.getBoundingClientRect();
    const cs = window.getComputedStyle(container);
    const paddingLeft = parseFloat(cs.paddingLeft) || 0;
    const paddingRight = parseFloat(cs.paddingRight) || 0;
    const paddingTop = parseFloat(cs.paddingTop) || 0;
    const paddingBottom = parseFloat(cs.paddingBottom) || 0;
    const borderLeft = parseFloat(cs.borderLeftWidth) || 0;
    const borderRight = parseFloat(cs.borderRightWidth) || 0;
    const borderTop = parseFloat(cs.borderTopWidth) || 0;
    const borderBottom = parseFloat(cs.borderBottomWidth) || 0;
    const contentWidth = rect.width - borderLeft - borderRight - paddingLeft - paddingRight;
    const contentHeight = rect.height - borderTop - borderBottom - paddingTop - paddingBottom;
    if (contentWidth <= 0 || contentHeight <= 0) {
        setTimeout(renderSensorMarkers, 100);
        return;
    }
    const colGap = parseFloat(cs.columnGap || cs.gap || '0') || 0;
    const rowGap = parseFloat(cs.rowGap || cs.gap || '0') || 0;
    const cellWidth = (contentWidth - colGap * (gridSize.cols - 1)) / gridSize.cols;
    const cellHeight = (contentHeight - rowGap * (gridSize.rows - 1)) / gridSize.rows;

    const sensors = currentLightSensors?.config?.sensors || {};
    console.log('[renderSensorMarkers] sensors:', sensors);
    for (const [sid, cfg] of Object.entries(sensors)) {
        console.log(`[renderSensorMarkers] sensor ${sid}:`, cfg);
        const [rowStr, colStr] = String(cfg.zone_key || '').split('-');
        const row = parseInt(rowStr, 10);
        const col = parseInt(colStr, 10);
        if (Number.isNaN(row) || Number.isNaN(col)) {
            console.log(`[renderSensorMarkers] sensor ${sid} has invalid zone_key:`, cfg.zone_key);
            continue;
        }

    const x = col * (cellWidth + colGap) + cellWidth / 2 - 9;
    const y = row * (cellHeight + rowGap) + cellHeight / 2 - 9;

        const marker = document.createElement('div');
        marker.className = 'sensor-marker';
        marker.style.left = `${x}px`;
        marker.style.top = `${y}px`;
        marker.title = cfg.name || sid;

        const label = document.createElement('span');
        label.textContent = 'S';
        marker.appendChild(label);

    const tt = document.createElement('div');
    tt.className = 'tooltip';
    const mode = (userSettings.light_unit || 'lux').toLowerCase();
    let readingStr = '—';
    // Try new data structure first (raw_color_data), then fall back to legacy
    const readingLux = currentLightSensors.readings?.[sid]?.raw_color_data?.lux ?? currentLightSensors.readings?.[sid]?.light_metrics?.lux?.value;
    const readingPPFD = currentLightSensors.readings?.[sid]?.raw_color_data?.ppfd_approx ?? currentLightSensors.readings?.[sid]?.light_metrics?.PPFD?.value;
    if (mode === 'par' && readingPPFD != null) {
        readingStr = Math.round(readingPPFD) + ' µmol';
    } else if (readingLux != null) {
        readingStr = Math.round(readingLux) + ' lux';
    }
    tt.textContent = `${cfg.name || sid} • ${cfg.type || ''} • ${readingStr}`;
    marker.appendChild(tt);

        overlay.appendChild(marker);
    }
}

// removed duplicate sensor-based renderLightAmountOverlay; async API-based version is defined above
// --- PPFD color scale helper ---
function ppfdToColor(ppfd) {
    // Use same color temperature and log scaling as lux view
    // Scale PPFD to match the 0-1000 range
    const cct = 4500; // Use same neutral white as lux view
    const baseRgb = cctToRgb(cct);
    const scaledRgb = scaleRgbByLuxLog(baseRgb, ppfd, {
        maxLux: 1000,  // Max PPFD value
        softFloor: 10, // Adjusted for PPFD range
        gamma: 2.0,    // Same gamma as lux view
        alpha: 1.0
    });
    return scaledRgb;
}

function calculateLightAmount(row, col) {
    // Use ONLY actual sensor reading if available for this cell
    const sensorData = getConfiguredSensorReading(row, col);
    if (sensorData && sensorData.lux != null) {
        const spectrum = sensorData.bands ? {
            red: sensorData.bands.red?.value || 33,
            blue: sensorData.bands.blue?.value || 33,
            green: sensorData.bands.green?.value || 33
        } : { red: 33, blue: 33, green: 33 };

        return {
            lux: Math.round(sensorData.lux),
            intensity: Math.min(9, Math.floor(sensorData.lux / 100)),
            spectrum: spectrum,
            source: 'sensor',
            sensorName: sensorData.name,
            colorTemp: sensorData.color_temp,
            ppfd: sensorData.ppfd
        };
    }
    // No direct sensor coverage for this cell — estimate from other sensors if enabled
    if (!estimationSettings.enabled) return null;
    const est = estimateLightFromSensors(row, col, {
        power: estimationSettings.power,
        maxSensors: estimationSettings.maxSensors,
        maxDistance: estimationSettings.maxDistance
    });
    if (est) {
        return {
            lux: Math.round(est.lux),
            intensity: Math.min(9, Math.floor(est.lux / 100)),
            spectrum: est.spectrum || { red: 33, blue: 33, green: 33 },
            source: 'estimated',
            colorTemp: est.color_temp || null,
            ppfd: est.ppfd != null ? Math.round(est.ppfd) : null,
            sensorCount: est.sensorCount
        };
    }
    // Not enough data to estimate
    return null;
}

function getLightDistance(row, col, lightPos) {
    const centerRow = lightPos.row + lightPos.row_span / 2;
    const centerCol = lightPos.col + lightPos.col_span / 2;
    return Math.sqrt(Math.pow(row - centerRow, 2) + Math.pow(col - centerCol, 2));
}

function getLightContribution(light, distance) {
    // Simple inverse square law approximation
    const maxDistance = 5; // Maximum effective distance in grid cells
    if (distance > maxDistance) {
        return { lux: 0, red: 0, blue: 0, white: 0 };
    }
    
    const powerFactor = light.power_watts / 100; // Normalize to 100W
    const dimmingFactor = light.dimming_level / 100;
    const distanceFactor = Math.max(0, 1 - (distance / maxDistance));
    
    const baseLux = 300 * powerFactor * dimmingFactor * distanceFactor;
    
    return {
        lux: baseLux,
        red: baseLux * (light.spectrum.red_percent / 100),
        blue: baseLux * (light.spectrum.blue_percent / 100),
        white: baseLux * (light.spectrum.white_percent / 100)
    };
}

function getConfiguredSensorReading(row, col) {
    console.log('[getConfiguredSensorReading] Called for', row, col, '- currentLightSensors:', currentLightSensors);
    if (!currentLightSensors || !currentLightSensors.readings) {
        console.log('[getConfiguredSensorReading] No currentLightSensors or readings');
        return null;
    }
    const key = `${row}-${col}`;
    console.log('[getConfiguredSensorReading] Looking for zone_key:', key);
    console.log('[getConfiguredSensorReading] Available sensors:', Object.keys(currentLightSensors.config?.sensors || {}));
    
    // Find any sensor mapped to this zone_key
    for (const [sid, cfg] of Object.entries(currentLightSensors.config?.sensors || {})) {
        console.log('[getConfiguredSensorReading] Checking sensor', sid, 'zone_key:', cfg.zone_key);
        if (cfg.zone_key === key) {
            const reading = currentLightSensors.readings[sid];
            console.log('[getConfiguredSensorReading] Found matching sensor!', sid, 'reading:', reading);
            // Handle new data structure: raw_color_data contains lux, ppfd_approx, color_temperature_k
            if (reading && reading.raw_color_data?.lux != null) {
                return {
                    lux: reading.raw_color_data.lux,
                    color_temp: reading.raw_color_data.color_temperature_k,
                    ppfd: reading.raw_color_data.ppfd_approx,
                    bands: reading.bands || null,
                    name: cfg.name || sid,
                    type: cfg.type
                };
            }
            // Legacy fallback for old data structure
            if (reading && reading.light_metrics?.lux?.value != null) {
                return {
                    lux: reading.light_metrics.lux.value,
                    color_temp: reading.light_metrics?.color_temp?.value,
                    ppfd: reading.light_metrics?.PPFD?.value,
                    bands: reading.bands,
                    name: cfg.name || sid,
                    type: cfg.type
                };
            }
        }
    }
    return null;
}

function findNearbySensorReading(targetRow, targetCol, maxDistance) {
    if (!currentLightSensors || !currentLightSensors.readings) return null;
    
    let closestSensor = null;
    let closestDistance = Infinity;
    
    // Check all configured sensors
    for (const [sid, cfg] of Object.entries(currentLightSensors.config?.sensors || {})) {
        if (!cfg.zone_key) continue;
        
        const [rowStr, colStr] = cfg.zone_key.split('-');
        const sensorRow = parseInt(rowStr, 10);
        const sensorCol = parseInt(colStr, 10);
        
        if (isNaN(sensorRow) || isNaN(sensorCol)) continue;
        
        // Calculate distance from target cell
        const distance = Math.sqrt(
            Math.pow(targetRow - sensorRow, 2) + Math.pow(targetCol - sensorCol, 2)
        );
        
        // Skip if too far or closer sensor already found
        if (distance > maxDistance || distance >= closestDistance) continue;
        
        const reading = currentLightSensors.readings[sid];
        // Try new data structure first (raw_color_data), then fall back to legacy
        const luxVal = reading?.raw_color_data?.lux ?? reading?.light_metrics?.lux?.value;
        if (reading && luxVal != null) {
            closestDistance = distance;
            closestSensor = {
                lux: luxVal,
                color_temp: reading.raw_color_data?.color_temperature_k ?? reading.light_metrics?.color_temp?.value,
                ppfd: reading.raw_color_data?.ppfd_approx ?? reading.light_metrics?.PPFD?.value,
                bands: reading.bands,
                name: cfg.name || sid,
                type: cfg.type,
                distance: distance
            };
        }
    }
    
    return closestSensor;
}

// Estimate light metrics for a cell using inverse-distance weighting from available sensors
function estimateLightFromSensors(targetRow, targetCol, options = {}) {
    if (!currentLightSensors || !currentLightSensors.readings) return null;
    const power = options.power ?? 2; // IDW power parameter
    const maxSensors = options.maxSensors ?? 4; // use up to N nearest sensors
    const maxDistance = options.maxDistance ?? Infinity; // in grid cells
    const minSensors = options.minSensors ?? 1; // require at least this many sensors to estimate

    const sensors = [];
    for (const [sid, cfg] of Object.entries(currentLightSensors.config?.sensors || {})) {
        if (!cfg.zone_key) continue;
        const [rowStr, colStr] = cfg.zone_key.split('-');
        const sRow = parseInt(rowStr, 10);
        const sCol = parseInt(colStr, 10);
        if (isNaN(sRow) || isNaN(sCol)) continue;

        const reading = currentLightSensors.readings[sid];
        // Try new data structure first (raw_color_data), then fall back to legacy
        let luxVal = reading?.raw_color_data?.lux;
        if (luxVal == null) luxVal = reading?.light_metrics?.lux?.value;
        if (luxVal == null) continue;

        const dist = Math.sqrt(Math.pow(targetRow - sRow, 2) + Math.pow(targetCol - sCol, 2));
        if (dist > maxDistance) continue;

        sensors.push({
            id: sid,
            distance: dist,
            lux: luxVal,
            ppfd: reading?.raw_color_data?.ppfd_approx ?? reading?.light_metrics?.PPFD?.value,
            color_temp: reading?.raw_color_data?.color_temperature_k ?? reading?.light_metrics?.color_temp?.value,
            bands: reading?.bands
        });
    }

    if (sensors.length < minSensors) return null;

    // If a sensor is exactly at this cell, caller would have handled it; guard anyway
    const exact = sensors.find(s => s.distance === 0);
    if (exact) {
        return {
            lux: exact.lux,
            ppfd: exact.ppfd,
            color_temp: exact.color_temp,
            spectrum: bandsToSpectrum(exact.bands),
            sensorCount: 1
        };
    }

    // Sort by distance and take up to maxSensors
    sensors.sort((a, b) => a.distance - b.distance);
    const selected = sensors.slice(0, maxSensors);
    let wSum = 0;
    let luxSum = 0;
    let ppfdSum = 0;
    let ctSum = 0;
    let redSum = 0, blueSum = 0, greenSum = 0;

    for (const s of selected) {
        const d = Math.max(s.distance, 0.001); // avoid division by zero
        const w = 1 / Math.pow(d, power);
        wSum += w;
        luxSum += w * s.lux;
        if (s.ppfd != null) { ppfdSum += w * s.ppfd; }
        if (s.color_temp != null) { ctSum += w * s.color_temp; }
        if (s.bands) {
            const r = s.bands.red?.value ?? 33;
            const b = s.bands.blue?.value ?? 33;
            const g = s.bands.green?.value ?? 33;
            redSum += w * r;
            blueSum += w * b;
            greenSum += w * g;
        }
    }

    if (wSum === 0) return null;
    const est = {
        lux: luxSum / wSum,
        ppfd: ppfdSum > 0 ? (ppfdSum / wSum) : null,
        color_temp: ctSum > 0 ? (ctSum / wSum) : null,
        spectrum: {
            red: redSum / wSum,
            blue: blueSum / wSum,
            green: greenSum / wSum
        },
        sensorCount: selected.length
    };
    return est;
}

function bandsToSpectrum(bands) {
    if (!bands) return { red: 33, blue: 33, green: 33 };
    return {
        red: bands.red?.value ?? 33,
        blue: bands.blue?.value ?? 33,
        green: bands.green?.value ?? 33
    };
}

function getSpectrumColor(spectrum) {
    // Only apply spectrum color if significantly different from balanced white
    const balanced = { red: 33, blue: 33, green: 33, white: 33 };
    const threshold = 15; // Significant deviation threshold
    
    const red = spectrum.red ?? 33;
    const blue = spectrum.blue ?? 33;
    const whiteOrGreen = spectrum.white ?? spectrum.green ?? 33;
    const redDiff = Math.abs(red - balanced.red);
    const blueDiff = Math.abs(blue - balanced.blue);
    
    if (redDiff > threshold || blueDiff > threshold) {
        // Calculate color based on spectrum
        const r = Math.min(255, Math.round(red * 2.55));
        const g = Math.min(255, Math.round(whiteOrGreen * 2.55));
        const b = Math.min(255, Math.round(blue * 2.55));
        
        return `rgba(${r}, ${g}, ${b}, 0.3)`;
    }
    
    return null; // Use default intensity color
}

// Convert color temperature (Kelvin) to approximate RGB for visualization
// Uses a common approximation valid for ~1000K to 40000K
function cctToRgb(kelvin) {
    let temp = kelvin / 100;
    let r, g, b;

    // Red
    if (temp <= 66) {
        r = 255;
    } else {
        r = temp - 60;
        r = 329.698727446 * Math.pow(r, -0.1332047592);
        r = Math.min(255, Math.max(0, r));
    }

    // Green
    if (temp <= 66) {
        g = 99.4708025861 * Math.log(temp) - 161.1195681661;
    } else {
        g = temp - 60;
        g = 288.1221695283 * Math.pow(g, -0.0755148492);
    }
    g = Math.min(255, Math.max(0, g));

    // Blue
    if (temp >= 66) {
        b = 255;
    } else if (temp <= 19) {
        b = 0;
    } else {
        b = temp - 10;
        b = 138.5177312231 * Math.log(b) - 305.0447927307;
        b = Math.min(255, Math.max(0, b));
    }

    return { r: Math.round(r), g: Math.round(g), b: Math.round(b) };
}

// Map lux to alpha transparency for overlay brightness
// Calibrated for typical greenhouse ranges; clamp between 0.1 and 0.35 (less opaque)
function luxToAlpha(lux) {
    if (!Number.isFinite(lux)) return 0.25;
    // Example mapping: 0 lux -> 0.1 alpha, 1000 lux -> ~0.17, 5000 lux -> ~0.35
    const maxLux = 5000;
    const normalized = Math.min(1, Math.max(0, lux / maxLux));
    return 0.10 + normalized * (0.35 - 0.10);
}

// Scale RGB by lux similar to the provided Python function
// scale = min(lux / max_lux, 1.0); return (int(r*scale), int(g*scale), int(b*scale))
function scaleRgbByLux(rgb, lux, maxLux = 100000) {
    const scale = Math.min(Math.max((Number(lux) || 0) / maxLux, 0), 1);
    return {
        r: Math.round(rgb.r * scale),
        g: Math.round(rgb.g * scale),
        b: Math.round(rgb.b * scale)
    };
}

// Hybrid log10 scaling with soft floor and gamma
function logLuxScale(lux, { maxLux, softFloor, gamma }) {
    const L0 = Math.max(1, Number(softFloor) || 1);
    const Lmax = Math.max(L0 + 1, Number(maxLux) || 100000);
    const L = Math.max(0, Number(lux) || 0);
    const s = (Math.log10(L + L0) - Math.log10(L0)) / (Math.log10(Lmax + L0) - Math.log10(L0));
    const clamped = Math.min(1, Math.max(0, s));
    const g = Math.max(0.1, Number(gamma) || 1);
    return Math.pow(clamped, g);
}

function scaleRgbByLuxLog(rgb, lux, settings) {
    const scale = logLuxScale(lux, settings);
    return {
        r: Math.round(rgb.r * scale),
        g: Math.round(rgb.g * scale),
        b: Math.round(rgb.b * scale)
    };
}

// Choose readable text color for a semi-transparent background over a light grid
function getTextColorForBackground(rgb, alpha) {
    // Blend background rgb over the base grid color (#f9f9f9) to get perceived color
    const base = { r: 249, g: 249, b: 249 };
    const r = Math.round((1 - alpha) * base.r + alpha * rgb.r);
    const g = Math.round((1 - alpha) * base.g + alpha * rgb.g);
    const b = Math.round((1 - alpha) * base.b + alpha * rgb.b);
    // Compute relative luminance
    const srgbToLin = (c) => {
        c /= 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    const L = 0.2126 * srgbToLin(r) + 0.7152 * srgbToLin(g) + 0.0722 * srgbToLin(b);
    // Return dark text when background is light, and white text when background is dark
    return L > 0.6 ? '#222' : '#fff';
}

function toggleLight(lightId, light) {
    const current = (currentLights.lights && currentLights.lights[lightId]) ? currentLights.lights[lightId] : light || {};
    const currentStatus = current.status || 'off';
    const action = currentStatus === 'on' ? 'off' : 'on';

    fetch(`/api/lights/${lightId}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            if (!currentLights.lights) currentLights.lights = {};
            if (!currentLights.lights[lightId]) currentLights.lights[lightId] = {};
            currentLights.lights[lightId].status = action;
            showNotification(`${current.name || 'Light'} turned ${action}`, 'success');
            renderLightsOverlay();
            renderLightsTable();
        } else {
            showNotification(`Light control failed: ${data.error || 'unknown error'}`, 'error');
        }
    })
    .catch(err => {
        showNotification(`Control error: ${err}`, 'error');
        console.error('Light control error:', err);
    });
}

// Zone configuration functions (for zones.html)
function selectZone(key, cellElement) {
    if (!multiSelectMode) {
        // Single select mode - clear previous selections
        clearSelection();
        cellElement.classList.add('selected');
        selectedZoneKey = key;
        selectedZoneKeys.clear();
        selectedZoneKeys.add(key);
    } else {
        // Multi-select mode - toggle selection
        if (selectedZoneKeys.has(key)) {
            selectedZoneKeys.delete(key);
            cellElement.classList.remove('selected');
            if (selectedZoneKey === key) {
                selectedZoneKey = null;
            }
        } else {
            selectedZoneKeys.add(key);
            cellElement.classList.add('selected');
            if (!selectedZoneKey) {
                selectedZoneKey = key; // Set first selection as primary
            }
        }
    }
    
    // Show/hide zone details panel based on selection
    const detailsPanel = document.getElementById('zoneDetails');
    if (detailsPanel) {
        if (selectedZoneKeys.size > 0) {
            detailsPanel.style.display = 'block';
            updateSelectionHeader();
            loadZoneFormForKey(selectedZoneKey || Array.from(selectedZoneKeys)[0]);
        } else {
            detailsPanel.style.display = 'none';
        }
    }
}

function clearSelection() {
    // Remove selected class from all cells
    const gridCells = document.querySelectorAll('.grid-cell.selected');
    gridCells.forEach(cell => cell.classList.remove('selected'));
    
    // Clear selection state
    selectedZoneKeys.clear();
    selectedZoneKey = null;
}

function applyZoneConfig() {
    if (selectedZoneKeys.size === 0 && !selectedZoneKey) return;
    
    const cropType = document.getElementById('cropType').value;
    const customCrop = document.getElementById('customCrop').value;
    const plantedDate = document.getElementById('plantedDate').value;
    
    if (!cropType && !customCrop) {
        showNotification('Please select or enter a crop type', 'warning');
        return;
    }
    
    // Ensure zones object exists
    if (!currentZones.zones) {
        currentZones.zones = {};
    }

    // Determine targets
    const targets = selectedZoneKeys.size > 0 ? Array.from(selectedZoneKeys) : (selectedZoneKey ? [selectedZoneKey] : []);
    
    // Handle empty zones - clear the zone data
    if (cropType === 'empty') {
        targets.forEach(k => {
            delete currentZones.zones[k];
        });
        showNotification(`Cleared ${targets.length} zone(s)`, 'success');
    } else {
        // Zone configuration to apply
        const zoneConfig = {
            crop_type: cropType === 'custom' ? customCrop : cropType,
            custom_crop: customCrop,
            stage: document.getElementById('cropStage')?.value || '',
            planted_date: plantedDate,
            water_needs: parseInt(document.getElementById('waterNeeds').value) || 2,
            light_hours: parseInt(document.getElementById('lightHours').value) || 12,
            temp_min: parseInt(document.getElementById('tempMin').value) || 18,
            temp_max: parseInt(document.getElementById('tempMax').value) || 24,
            notes: document.getElementById('notes').value,
            dli_config: {
                target_dli: parseFloat(document.getElementById('targetDli').value) || 14,
                morning_start_time: document.getElementById('morningStartTime').value || '06:00',
                evening_end_time: document.getElementById('eveningEndTime').value || '20:00',
                priority: document.getElementById('lightPriority').value || 'medium'
            },
            light_spectrum: {
                red_percent: parseInt(document.getElementById('redPercent').value) || 35,
                blue_percent: parseInt(document.getElementById('bluePercent').value) || 25,
                white_percent: parseInt(document.getElementById('whitePercent').value) || 40,
                par_target: parseInt(document.getElementById('parTarget').value) || 200
            },
            color_temp_schedule: getCurrentColorTempSchedule()
        };

        targets.forEach(k => {
            currentZones.zones[k] = { ...zoneConfig };
        });
        showNotification(`Zone configuration applied to ${targets.length} cell(s)`, 'success');
    }

    // Re-render grid
    renderGrid(true);
    if (!multiSelectMode) {
        closeZoneConfig();
    } else {
        updateSelectionHeader();
    }
}

function clearZone() {
    const targets = selectedZoneKeys.size > 0 ? Array.from(selectedZoneKeys) : (selectedZoneKey ? [selectedZoneKey] : []);
    if (targets.length === 0) return;

    let count = 0;
    targets.forEach(k => {
        if (currentZones.zones && currentZones.zones[k]) {
            delete currentZones.zones[k];
            count++;
        }
    });
    renderGrid(true);
    if (!multiSelectMode) {
        closeZoneConfig();
    } else {
        updateSelectionHeader();
    }
    showNotification(`Cleared ${count} zone(s)`, 'success');
}

function closeZoneConfig() {
    const detailsPanel = document.getElementById('zoneDetails');
    if (detailsPanel) {
        detailsPanel.style.display = 'none';
    }
    
    clearAllSelections();
}

function resizeGrid() {
    const rows = parseInt(document.getElementById('gridRows').value) || 24;
    const cols = parseInt(document.getElementById('gridCols').value) || 12;
    
    // Validate grid size bounds
    if (rows < 1 || rows > 100 || cols < 1 || cols > 100) {
        showNotification('Grid size must be between 1×1 and 100×100', 'error');
        return;
    }
    
    const totalCells = rows * cols;
    
    // Warn for very large grids
    if (totalCells > 5000) {
        const proceed = confirm(`Large grid (${rows}×${cols} = ${totalCells} cells) may impact performance. Continue?`);
        if (!proceed) return;
    }
    
    gridSize = { rows, cols };
    currentZones.grid_size = gridSize;
    
    renderGrid(true);
    showNotification(`Grid resized to ${rows}×${cols} (${totalCells} cells)`, 'success');
}

function saveZones() {
    fetch('/api/zones', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(currentZones)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Zones configuration saved successfully', 'success');
        } else {
            showNotification('Failed to save zones configuration', 'error');
        }
    })
    .catch(error => {
        showNotification('Error saving zones configuration', 'error');
        console.error('Error:', error);
    });
}

// Multi-select helpers
function toggleMultiSelectMode(enabled) {
    multiSelectMode = enabled;
    if (!enabled) {
        // Collapse to single-select if more than one selected
        if (selectedZoneKeys.size > 1) {
            const first = selectedZoneKeys.values().next().value;
            clearAllSelections();
            const cell = getCellElementByKey(first);
            if (cell) selectZone(first, cell);
        }
    } else {
        // Ensure details panel is visible when entering multi-select
        const detailsPanel = document.getElementById('zoneDetails');
        if (detailsPanel) detailsPanel.style.display = 'block';
    }
    updateSelectionHeader();
}

function toggleCellSelection(key, cellElement) {
    if (selectedZoneKeys.has(key)) {
        selectedZoneKeys.delete(key);
        cellElement.classList.remove('selected');
    } else {
        selectedZoneKeys.add(key);
        cellElement.classList.add('selected');
    }
    // Keep last selected as primary
    selectedZoneKey = key;
    const detailsPanel = document.getElementById('zoneDetails');
    if (detailsPanel) detailsPanel.style.display = selectedZoneKeys.size > 0 ? 'block' : 'none';
    updateSelectionHeader();
    // If exactly one cell is selected, populate the form from that zone
    if (selectedZoneKeys.size === 1) {
        const onlyKey = Array.from(selectedZoneKeys)[0];
        loadZoneFormForKey(onlyKey);
    }
}

function clearAllSelections() {
    document.querySelectorAll('.grid-cell.selected').forEach(cell => cell.classList.remove('selected'));
    selectedZoneKeys.clear();
    selectedZoneKey = null;
    updateSelectionHeader();
}

function updateSelectionHeader() {
    const headerSpan = document.getElementById('selectedZone');
    if (!headerSpan) return;
    const count = selectedZoneKeys.size || (selectedZoneKey ? 1 : 0);
    if (count <= 1) {
        const key = selectedZoneKey || Array.from(selectedZoneKeys)[0];
        if (key) {
            headerSpan.textContent = `(${parseInt(key.split('-')[0]) + 1}, ${parseInt(key.split('-')[1]) + 1})`;
        } else {
            headerSpan.textContent = '';
        }
    } else {
        headerSpan.textContent = `${count} cells selected`;
    }
}

// Populate form from a specific zone key (or defaults if empty)
function loadZoneFormForKey(key) {
    const zone = currentZones.zones && currentZones.zones[key];
    if (zone) {
        document.getElementById('cropType').value = zone.crop_type || '';
        handleCropChange(); // populate stages before setting stage value
        if (zone.stage && document.getElementById('cropStage')) {
            document.getElementById('cropStage').value = zone.stage;
        }
        document.getElementById('customCrop').value = zone.custom_crop || '';
        document.getElementById('plantedDate').value = zone.planted_date || '';
        document.getElementById('waterNeeds').value = zone.water_needs ?? 2;
        document.getElementById('lightHours').value = zone.light_hours ?? 12;
        document.getElementById('tempMin').value = zone.temp_min ?? 18;
        document.getElementById('tempMax').value = zone.temp_max ?? 24;
        document.getElementById('notes').value = zone.notes || '';

        const ls = zone.light_spectrum || {};
        document.getElementById('redPercent').value = ls.red_percent ?? 35;
        document.getElementById('bluePercent').value = ls.blue_percent ?? 25;
        document.getElementById('whitePercent').value = ls.white_percent ?? 40;
        document.getElementById('parTarget').value = ls.par_target ?? 200;
        
        // Load DLI configuration
        const dli = zone.dli_config || {};
        document.getElementById('targetDli').value = dli.target_dli ?? 14;
        document.getElementById('morningStartTime').value = dli.morning_start_time || '06:00';
        document.getElementById('eveningEndTime').value = dli.evening_end_time || '20:00';
        document.getElementById('lightPriority').value = dli.priority || 'medium';
        
        // Load color temperature schedule
        setColorTempSchedule(zone.color_temp_schedule);
    } else {
        // Reset to defaults
        const form = document.getElementById('zoneForm');
        if (form) form.reset();
        document.getElementById('redPercent').value = 35;
        document.getElementById('bluePercent').value = 25;
        document.getElementById('whitePercent').value = 40;
        document.getElementById('parTarget').value = 200;
        
        // Reset DLI configuration to defaults
        document.getElementById('targetDli').value = 14;
        document.getElementById('morningStartTime').value = '06:00';
        document.getElementById('eveningEndTime').value = '20:00';
        document.getElementById('lightPriority').value = 'medium';
        
        // Reset color temperature schedule
        setColorTempSchedule({ enabled: false });
    }
    updateSpectrumTotal();
}

// Handle crop change: populate stage options and optionally auto-fill defaults
function handleCropChange() {
    const crop = document.getElementById('cropType')?.value || '';
    const stageGroup = document.getElementById('stageGroup');
    const stageSelect = document.getElementById('cropStage');
    if (!stageGroup || !stageSelect) return;
    // Reset options
    stageSelect.innerHTML = '';
    if (crop && cropPresets[crop]) {
        stageGroup.style.display = '';
        const stages = Object.keys(cropPresets[crop]);
        stages.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = s.charAt(0).toUpperCase() + s.slice(1);
            stageSelect.appendChild(opt);
        });
        // Auto-select first stage and fill defaults
        stageSelect.value = stages[0];
        applyPreset(crop, stages[0]);
    } else {
        stageGroup.style.display = 'none';
    }
}

function handleStageChange() {
    const crop = document.getElementById('cropType')?.value || '';
    const stage = document.getElementById('cropStage')?.value || '';
    if (crop && stage && cropPresets[crop]?.[stage]) {
        applyPreset(crop, stage);
    }
}

function applyPreset(crop, stage) {
    const p = cropPresets[crop][stage];
    if (!p) return;
    document.getElementById('redPercent').value = p.red;
    document.getElementById('bluePercent').value = p.blue;
    document.getElementById('whitePercent').value = p.white;
    document.getElementById('parTarget').value = p.par;
    if (p.hours) {
        document.getElementById('lightHours').value = p.hours;
    }
    updateSpectrumTotal();
}

function getCellElementByKey(key) {
    const [r, c] = key.split('-').map(n => parseInt(n, 10));
    const container = document.getElementById('greenhouse-grid');
    if (!container) return null;
    // Cells were appended row-major; locate by index
    const idx = r * gridSize.cols + c;
    return container.children[idx] || null;
}

// Notification system
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Style the notification
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem;
        border-radius: 5px;
        color: white;
        font-weight: bold;
        z-index: 1000;
        max-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    
    // Set background color based on type
    switch (type) {
        case 'success':
            notification.style.backgroundColor = '#4caf50';
            break;
        case 'error':
            notification.style.backgroundColor = '#f44336';
            break;
        case 'warning':
            notification.style.backgroundColor = '#ff9800';
            break;
        default:
            notification.style.backgroundColor = '#2196f3';
    }
    
    // Add to page
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Light spectrum management functions
function updateSpectrumTotal() {
    const red = parseInt(document.getElementById('redPercent').value) || 0;
    const blue = parseInt(document.getElementById('bluePercent').value) || 0;
    const white = parseInt(document.getElementById('whitePercent').value) || 0;
    const total = red + blue + white;
    
    const totalElement = document.getElementById('spectrumTotal');
    if (totalElement) {
        totalElement.textContent = total;
        
        // Color code the total based on whether it equals 100%
        if (total === 100) {
            totalElement.style.color = '#4caf50';
        } else if (total > 100) {
            totalElement.style.color = '#f44336';
        } else {
            totalElement.style.color = '#ff9800';
        }
    }
}

// Light configuration functions (for lights.html)
function updateLightSpectrumTotal() {
    const red = parseInt(document.getElementById('lightRedPercent').value) || 0;
    const blue = parseInt(document.getElementById('lightBluePercent').value) || 0;
    const white = parseInt(document.getElementById('lightWhitePercent').value) || 0;
    const total = red + blue + white;
    
    const totalElement = document.getElementById('lightSpectrumTotal');
    if (totalElement) {
        totalElement.textContent = total;
        
        // Color code the total based on whether it equals 100%
        if (total === 100) {
            totalElement.style.color = '#4caf50';
        } else if (total > 100) {
            totalElement.style.color = '#f44336';
        } else {
            totalElement.style.color = '#ff9800';
        }
    }
}

function addNewLight() {
    const lightId = 'light-' + Date.now();
    selectedLightKey = lightId;
    
    // Show light details panel
    const detailsPanel = document.getElementById('lightDetails');
    if (detailsPanel) {
        detailsPanel.style.display = 'block';
        document.getElementById('selectedLight').textContent = `(New Light)`;
        
        // Clear form for new light
        document.getElementById('lightForm').reset();
        document.getElementById('lightName').value = 'New Light Fixture';
        document.getElementById('lightWidth').value = 24;
    document.getElementById('lightDepth').value = 12;
        document.getElementById('lightPower').value = 100;
        document.getElementById('dimmingLevel').value = 100;
        document.getElementById('positionRow').value = 0;
        document.getElementById('positionCol').value = 0;
        document.getElementById('rowSpan').value = 1;
        document.getElementById('colSpan').value = 2;
        document.getElementById('lightRedPercent').value = 40;
        document.getElementById('lightBluePercent').value = 20;
        document.getElementById('lightWhitePercent').value = 40;
        updateLightSpectrumTotal();
    }
}

function buildControlConfig() {
    const controlType = document.getElementById('controlType').value;
    
    if (controlType === 'none') {
        return {
            type: 'none',
            description: 'No hardware control configured'
        };
    } else if (controlType === 'gpio') {
        const pin = parseInt(document.getElementById('gpioPin').value);
        const activeLow = !!document.getElementById('gpioActiveLow').checked;
        return {
            type: 'gpio',
            pin: pin || null,
            active_low: activeLow,
            description: pin ? `GPIO pin ${pin} for on/off control` : 'GPIO pin not configured'
        };
    } else if (controlType === 'pwm') {
        const pin = parseInt(document.getElementById('pwmPin').value);
        const frequency = parseInt(document.getElementById('pwmFrequency').value) || 1000;
        return {
            type: 'pwm',
            pin: pin || null,
            frequency: frequency,
            description: pin ? `PWM pin ${pin} at ${frequency}Hz for dimming` : 'PWM pin not configured'
        };
    } else if (controlType === 'rgb') {
        const redPin = parseInt(document.getElementById('redPin').value);
        const greenPin = parseInt(document.getElementById('greenPin').value);
        const bluePin = parseInt(document.getElementById('bluePin').value);
        return {
            type: 'rgb',
            pins: {
                red: redPin || null,
                green: greenPin || null,
                blue: bluePin || null
            },
            description: (redPin && greenPin && bluePin) 
                ? `RGB control on pins R:${redPin}, G:${greenPin}, B:${bluePin}`
                : 'RGB pins not fully configured'
        };
    } else if (controlType === 'i2c') {
        const address = document.getElementById('i2cAddress').value;
        const bus = parseInt(document.getElementById('i2cBus').value) || 1;
        const device = document.getElementById('i2cDevice').value;
        return {
            type: 'i2c',
            address: address || null,
            bus: bus,
            device: device || 'Unknown',
            description: address 
                ? `I2C device ${device || 'Unknown'} at ${address} on bus ${bus}`
                : 'I2C address not configured'
        };
    }
    
    return { type: 'none', description: 'Unknown control type' };
}

function applyLightConfig() {
    if (!selectedLightKey) return;
    
    const name = document.getElementById('lightName').value;
    const type = document.getElementById('lightType').value;
    
    if (!name.trim()) {
        showNotification('Please enter a light name', 'warning');
        return;
    }
    
    // Ensure lights object exists
    if (!currentLights.lights) {
        currentLights.lights = {};
    }
    
    // Create light configuration
    currentLights.lights[selectedLightKey] = {
        name: name,
        type: type,
    width_inches: parseInt(document.getElementById('lightWidth').value) || 24,
    depth_inches: parseInt(document.getElementById('lightDepth').value) || 12,
        position: {
            row: parseInt(document.getElementById('positionRow').value) || 0,
            col: parseInt(document.getElementById('positionCol').value) || 0,
            row_span: parseInt(document.getElementById('rowSpan').value) || 1,
            col_span: parseInt(document.getElementById('colSpan').value) || 2
        },
        power_watts: parseInt(document.getElementById('lightPower').value) || 100,
        spectrum: {
            red_percent: parseInt(document.getElementById('lightRedPercent').value) || 40,
            blue_percent: parseInt(document.getElementById('lightBluePercent').value) || 20,
            white_percent: parseInt(document.getElementById('lightWhitePercent').value) || 40
        },
        dimming_level: parseInt(document.getElementById('dimmingLevel').value) || 100,
        status: 'on',
        notes: document.getElementById('lightNotes').value,
        control: buildControlConfig()
    };
    
    // Re-render lights
    renderLightsOverlay();
    renderLightsTable();
    closeLightConfig();
    showNotification('Light configuration applied', 'success');
}

function deleteLight() {
    if (!selectedLightKey) return;
    
    if (currentLights.lights && currentLights.lights[selectedLightKey]) {
        if (confirm(`Are you sure you want to delete "${currentLights.lights[selectedLightKey].name}"?`)) {
            delete currentLights.lights[selectedLightKey];
            renderLightsOverlay();
            renderLightsTable();
            closeLightConfig();
            showNotification('Light deleted', 'success');
        }
    }
}

function closeLightConfig() {
    const detailsPanel = document.getElementById('lightDetails');
    if (detailsPanel) {
        detailsPanel.style.display = 'none';
    }
    selectedLightKey = null;
}

function loadControlConfig(control) {
    const controlType = control.type || 'none';
    document.getElementById('controlType').value = controlType;
    
    // Clear all control fields first
    const fields = ['gpioPin', 'pwmPin', 'pwmFrequency', 'redPin', 'greenPin', 'bluePin', 'i2cAddress', 'i2cBus', 'i2cDevice'];
    fields.forEach(field => {
        const element = document.getElementById(field);
        if (element) element.value = '';
    });
    
    // Load specific control configuration
    if (controlType === 'gpio' && control.pin) {
        document.getElementById('gpioPin').value = control.pin;
        document.getElementById('gpioActiveLow').checked = !!control.active_low;
    } else if (controlType === 'pwm') {
        if (control.pin) document.getElementById('pwmPin').value = control.pin;
        if (control.frequency) document.getElementById('pwmFrequency').value = control.frequency;
    } else if (controlType === 'rgb' && control.pins) {
        if (control.pins.red) document.getElementById('redPin').value = control.pins.red;
        if (control.pins.green) document.getElementById('greenPin').value = control.pins.green;
        if (control.pins.blue) document.getElementById('bluePin').value = control.pins.blue;
    } else if (controlType === 'i2c') {
        if (control.address) document.getElementById('i2cAddress').value = control.address;
        if (control.bus) document.getElementById('i2cBus').value = control.bus;
        if (control.device) document.getElementById('i2cDevice').value = control.device;
    }
    
    // Update control field visibility
    if (typeof updateControlFields === 'function') {
        updateControlFields();
    }
}

function editLight(lightId) {
    selectedLightKey = lightId;
    const light = currentLights.lights[lightId];
    
    if (!light) return;
    
    // Show light details panel
    const detailsPanel = document.getElementById('lightDetails');
    if (detailsPanel) {
        detailsPanel.style.display = 'block';
        document.getElementById('selectedLight').textContent = light.name;
        
        // Load light data into form
        document.getElementById('lightName').value = light.name || '';
        document.getElementById('lightType').value = light.type || 'LED Panel';
    document.getElementById('lightWidth').value = light.width_inches || 24;
    document.getElementById('lightDepth').value = (light.depth_inches != null ? light.depth_inches : (light.height_inches || 12));
        document.getElementById('lightPower').value = light.power_watts || 100;
        document.getElementById('dimmingLevel').value = light.dimming_level || 100;
        document.getElementById('positionRow').value = light.position.row || 0;
        document.getElementById('positionCol').value = light.position.col || 0;
        document.getElementById('rowSpan').value = light.position.row_span || 1;
        document.getElementById('colSpan').value = light.position.col_span || 2;
        document.getElementById('lightRedPercent').value = light.spectrum.red_percent || 40;
        document.getElementById('lightBluePercent').value = light.spectrum.blue_percent || 20;
        document.getElementById('lightWhitePercent').value = light.spectrum.white_percent || 40;
        document.getElementById('lightNotes').value = light.notes || '';
        
        // Load control configuration
        loadControlConfig(light.control || {});
        
        updateLightSpectrumTotal();
    }
}

function renderLightsTable() {
    const tableContainer = document.getElementById('lightsTable');
    if (!tableContainer) return;
    
    if (!currentLights.lights || Object.keys(currentLights.lights).length === 0) {
        tableContainer.innerHTML = '<p>No light fixtures configured. <a href="#" onclick="addNewLight()">Add your first light</a>.</p>';
        return;
    }
    
    let html = `
        <table class="lights-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Position</th>
                    <th>Power</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    Object.entries(currentLights.lights).forEach(([lightId, light]) => {
        // Handle both old and new light data formats
    const width = light.width_inches || 24;
    const depth = (light.depth_inches != null ? light.depth_inches : (light.height_inches || 12));
        const rowSpan = light.position.row_span || 1;
        const colSpan = light.position.col_span || 1;
        const status = light.status || 'on';
        
        html += `
            <tr>
                <td><strong>${light.name}</strong></td>
                <td>${light.type}</td>
                <td>${width}"×${depth}"</td>
                <td>R${light.position.row} C${light.position.col} (${rowSpan}×${colSpan})</td>
                <td>${light.power_watts}W</td>
                <td><span class="status status-${status}">${status.toUpperCase()}</span></td>
                <td>
                    <button onclick="editLight('${lightId}')" class="btn btn-sm btn-primary">Edit</button>
                    <button onclick="toggleLight('${lightId}', currentLights.lights['${lightId}'])" class="btn btn-sm btn-secondary">Toggle</button>
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    tableContainer.innerHTML = html;
}

function saveLights() {
    fetch('/api/lights', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(currentLights)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Lights configuration saved successfully', 'success');
        } else {
            showNotification('Failed to save lights configuration', 'error');
        }
    })
    .catch(error => {
        showNotification('Error saving lights configuration', 'error');
        console.error('Error:', error);
    });
}

// Handle crop type selection and spectrum input changes
document.addEventListener('DOMContentLoaded', function() {
    const cropTypeSelect = document.getElementById('cropType');
    const customCropField = document.getElementById('customCrop');
    
    if (cropTypeSelect && customCropField) {
        cropTypeSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                customCropField.style.display = 'block';
                customCropField.required = true;
            } else {
                customCropField.style.display = 'none';
                customCropField.required = false;
                customCropField.value = '';
            }
        });
    }
    
    // Add event listeners for spectrum inputs
    const spectrumInputs = ['redPercent', 'bluePercent', 'whitePercent'];
    spectrumInputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('input', updateSpectrumTotal);
            input.addEventListener('change', updateSpectrumTotal);
        }
    });
    
    // Load grid automatically if on zones page (editing mode), or dashboard (view mode)
    if (window.location.pathname === '/zones') {
        loadGreenhouseGrid(true); // Enable editing mode
    } else if (getGridContainer()) {
        loadGreenhouseGrid(false); // Dashboard: view mode
    }
    
    // Add layer toggle event listeners
    // Light display checkbox event listeners
    const showLightFixtures = document.getElementById('showLightFixtures');
    const showLightAmount = document.getElementById('showLightAmount');
    const showSensorMarkers = document.getElementById('showSensorMarkers');
    const enableEstimation = document.getElementById('enableEstimation');
    const estPower = document.getElementById('estPower');
    const estMaxSensors = document.getElementById('estMaxSensors');
    const estMaxDistance = document.getElementById('estMaxDistance');
    const luxMaxLux = document.getElementById('luxMaxLux');
    const luxSoftFloor = document.getElementById('luxSoftFloor');
    const luxGamma = document.getElementById('luxGamma');
    const luxAlpha = document.getElementById('luxAlpha');
    const luxAlphaValue = document.getElementById('luxAlphaValue');
    
    if (showLightFixtures) {
        showLightFixtures.addEventListener('change', function() {
            console.log('Light fixtures toggle changed to:', this.checked);
            renderLightsOverlay();
        });
    }
    
    if (showLightAmount) {
        console.log('[Init] Attaching light amount toggle handler');
        showLightAmount.addEventListener('change', function() {
            console.log('Light amount toggle changed to:', this.checked);
            if (this.checked) {
                // Pull fresh sensor data FIRST, then render the overlay
                console.log('[LightOverlay] Checkbox checked - fetching sensor data');
                if (typeof refreshLightSensorsOnce === 'function') {
                    refreshLightSensorsOnce().then(() => {
                        console.log('[LightOverlay] Sensor data loaded - rendering overlay');
                        renderLightAmountOverlay();
                    });
                } else {
                    // Fallback if refreshLightSensorsOnce doesn't exist
                    console.log('[LightOverlay] Rendering overlay without fresh data');
                    renderLightAmountOverlay();
                }
            } else {
                // Clear the overlay when disabled
                console.log('[LightOverlay] Checkbox unchecked - clearing overlay');
                clearLightAmountOverlay();
            }
        });
    } else {
        console.warn('[Init] showLightAmount element not found!');
    }
    if (showSensorMarkers) {
        showSensorMarkers.addEventListener('change', function() {
            console.log('Sensor markers toggle changed to:', this.checked);
            renderLightsOverlay();
        });
    }
    // Estimation controls wiring
    function updateEstimationSettings() {
        estimationSettings.enabled = enableEstimation ? !!enableEstimation.checked : true;
        estimationSettings.power = estPower && !isNaN(parseFloat(estPower.value)) ? parseFloat(estPower.value) : 2;
        estimationSettings.maxSensors = estMaxSensors && !isNaN(parseInt(estMaxSensors.value)) ? parseInt(estMaxSensors.value) : 4;
        estimationSettings.maxDistance = estMaxDistance && !isNaN(parseInt(estMaxDistance.value)) ? parseInt(estMaxDistance.value) : 100;
        if (showLightAmount && showLightAmount.checked) {
            renderLightAmountOverlay();
        }
    }
    if (enableEstimation) enableEstimation.addEventListener('change', updateEstimationSettings);
    if (estPower) estPower.addEventListener('input', updateEstimationSettings);
    if (estMaxSensors) estMaxSensors.addEventListener('input', updateEstimationSettings);
    if (estMaxDistance) estMaxDistance.addEventListener('input', updateEstimationSettings);
    // Initialize from current UI values on load
    updateEstimationSettings();

    // Lux scaling controls wiring
    function updateLuxScaleSettings() {
        luxScaleSettings.maxLux = luxMaxLux && !isNaN(parseInt(luxMaxLux.value)) ? parseInt(luxMaxLux.value) : 100000;
        luxScaleSettings.softFloor = luxSoftFloor && !isNaN(parseInt(luxSoftFloor.value)) ? parseInt(luxSoftFloor.value) : 50;
        luxScaleSettings.gamma = luxGamma && !isNaN(parseFloat(luxGamma.value)) ? parseFloat(luxGamma.value) : 2.0;
        luxScaleSettings.alpha = luxAlpha && !isNaN(parseFloat(luxAlpha.value)) ? parseFloat(luxAlpha.value) : 1.0;
        
        // Update the alpha display value
        if (luxAlphaValue) {
            luxAlphaValue.textContent = luxScaleSettings.alpha.toFixed(2);
        }
        
        if (showLightAmount && showLightAmount.checked) {
            renderLightAmountOverlay();
        }
    }
    if (luxMaxLux) luxMaxLux.addEventListener('input', updateLuxScaleSettings);
    if (luxSoftFloor) luxSoftFloor.addEventListener('input', updateLuxScaleSettings);
    if (luxGamma) luxGamma.addEventListener('input', updateLuxScaleSettings);
    if (luxAlpha) luxAlpha.addEventListener('input', updateLuxScaleSettings);
    updateLuxScaleSettings();
    
    // Zones are always shown; no toggle handler needed
});

// --- Live light-sensor refresh (dashboard + lights page) ---
function refreshLightSensorsOnce() {
    return fetch('/api/light-sensors')
        .then(r => r.json())
        .then(data => {
            // Check if sensor readings actually changed (compare lux values to avoid re-render on timestamp change)
            let readingsChanged = false;
            const oldReadings = currentLightSensors?.readings || {};
            const newReadings = data?.readings || {};
            
            // Check each sensor - consider significant if lux changes by more than 1%
            for (const sid in newReadings) {
                const oldLux = oldReadings[sid]?.raw_color_data?.lux;
                const newLux = newReadings[sid]?.raw_color_data?.lux;
                
                // If one has data and other doesn't, it's a change
                if ((oldLux == null) !== (newLux == null)) {
                    readingsChanged = true;
                    break;
                }
                
                // If both have data, check if change is significant (> 1% or > 10 lux)
                if (oldLux != null && newLux != null) {
                    const luxDiff = Math.abs(newLux - oldLux);
                    const percentChange = oldLux > 0 ? (luxDiff / oldLux) * 100 : 100;
                    if (luxDiff > 10 || percentChange > 1) {
                        readingsChanged = true;
                        break;
                    }
                }
            }
            
            // Also check if sensors were added/removed
            if (Object.keys(oldReadings).length !== Object.keys(newReadings).length) {
                readingsChanged = true;
            }
            
            // Update global cache
            currentLightSensors = data || { config: { sensors: {} }, readings: {} };

            // Ensure overlays exist before rendering
            const container = getGridContainer();
            if (container) ensureOverlays(container);

            // If on dashboard or zones view with overlays, refresh markers and (optionally) light map
            const showSensorMarkers = document.getElementById('showSensorMarkers');
            if (!showSensorMarkers || showSensorMarkers.checked) {
                renderSensorMarkers();
            }
            
            // Only re-render light amount overlay if readings changed significantly and overlay is visible
            const showLightAmount = document.getElementById('showLightAmount');
            if (showLightAmount && showLightAmount.checked && readingsChanged) {
                console.log('[LightOverlay] Rendering due to significant sensor change');
                renderLightAmountOverlay();
            }

            // If on lights page, update sensor readings without rebuilding form controls
            if (document.getElementById('lightSensorsTable')) {
                // Use updateSensorReadings if it exists (lights page), otherwise renderLightSensorsTable
                if (typeof updateSensorReadings === 'function') {
                    updateSensorReadings();
                } else {
                    // Check if any dropdown is currently open before full refresh
                    const hasActiveDropdown = document.querySelector('#lightSensorsTable select:focus') || 
                                            document.querySelector('#lightSensorsTable input:focus');
                    if (!hasActiveDropdown) {
                        renderLightSensorsTable();
                    }
                }
            }
        })
        .catch(err => {
            console.error('Failed to refresh light sensors:', err);
        });
}

function scheduleLightSensorRefresh() {
    // Only schedule if we have a grid or a sensors table present
    if (!getGridContainer() && !document.getElementById('lightSensorsTable')) return;

    // Get update cadence from backend; fall back to 10s
    fetch('/api/frontend-config')
        .then(r => r.json())
        .then(cfg => {
            const interval = Math.max(1000, Number(cfg.update_interval_ms) || 10000);
            if (cfg && cfg.user_settings) {
                userSettings = cfg.user_settings;
                try { window.userSettings = userSettings; } catch(_) {}
            }
            // Initial refresh to get fresh readings after page load
            refreshLightSensorsOnce();
            // Periodic refresh
            setInterval(refreshLightSensorsOnce, interval);
            console.log(`Light sensors will refresh every ${interval}ms`);
        })
        .catch(() => {
            // Safe default
            refreshLightSensorsOnce();
            setInterval(refreshLightSensorsOnce, 10000);
            console.log('Light sensors will refresh every 10000ms (default)');
        });
}

// Start auto-refresh shortly after DOM ready so initial grid/render has occurred
document.addEventListener('DOMContentLoaded', function() {
    // Defer slightly to allow initial renderGrid/loadGreenhouseGrid to complete
    setTimeout(scheduleLightSensorRefresh, 200);
});

// Color temperature scheduling functions
let colorTempProfiles = {};

// Load color temperature profiles
async function loadColorTempProfiles() {
    try {
        const response = await fetch('/api/color-temp-profiles');
        if (response.ok) {
            colorTempProfiles = await response.json();
        } else {
            console.error('Failed to load color temperature profiles');
        }
    } catch (error) {
        console.error('Error loading color temperature profiles:', error);
    }
}

// Toggle color temperature schedule visibility
function toggleColorTempSchedule() {
    const checkbox = document.getElementById('enableColorTempSchedule');
    const details = document.getElementById('colorTempScheduleDetails');
    
    if (checkbox && details) {
        details.style.display = checkbox.checked ? 'block' : 'none';
    }
}

// Handle plant type profile selection
function handlePlantTypeProfileChange() {
    const profileSelect = document.getElementById('plantTypeProfile');
    const profile = profileSelect.value;
    
    if (profile && profile !== 'custom' && colorTempProfiles.profiles && colorTempProfiles.profiles[profile]) {
        const profileData = colorTempProfiles.profiles[profile];
        
        // Update the time and color temperature inputs
        document.getElementById('morningTime').value = profileData.schedule.morning.time;
        document.getElementById('morningColorTemp').value = profileData.schedule.morning.color_temp_k;
        
        document.getElementById('middayTime').value = profileData.schedule.midday.time;
        document.getElementById('middayColorTemp').value = profileData.schedule.midday.color_temp_k;
        
        document.getElementById('afternoonTime').value = profileData.schedule.afternoon.time;
        document.getElementById('afternoonColorTemp').value = profileData.schedule.afternoon.color_temp_k;
    }
}

// Get current color temperature schedule from form
function getCurrentColorTempSchedule() {
    const enabled = document.getElementById('enableColorTempSchedule').checked;
    
    if (!enabled) {
        return { enabled: false };
    }
    
    return {
        enabled: true,
        profile: document.getElementById('plantTypeProfile').value,
        schedule: {
            morning: {
                time: document.getElementById('morningTime').value,
                color_temp_k: parseInt(document.getElementById('morningColorTemp').value)
            },
            midday: {
                time: document.getElementById('middayTime').value,
                color_temp_k: parseInt(document.getElementById('middayColorTemp').value)
            },
            afternoon: {
                time: document.getElementById('afternoonTime').value,
                color_temp_k: parseInt(document.getElementById('afternoonColorTemp').value)
            }
        }
    };
}

// Set color temperature schedule in form
function setColorTempSchedule(schedule) {
    const enableCheckbox = document.getElementById('enableColorTempSchedule');
    const details = document.getElementById('colorTempScheduleDetails');
    
    if (schedule && schedule.enabled) {
        enableCheckbox.checked = true;
        details.style.display = 'block';
        
        if (schedule.profile) {
            document.getElementById('plantTypeProfile').value = schedule.profile;
        }
        
        if (schedule.schedule) {
            if (schedule.schedule.morning) {
                document.getElementById('morningTime').value = schedule.schedule.morning.time || '06:00';
                document.getElementById('morningColorTemp').value = schedule.schedule.morning.color_temp_k || 5000;
            }
            if (schedule.schedule.midday) {
                document.getElementById('middayTime').value = schedule.schedule.midday.time || '12:00';
                document.getElementById('middayColorTemp').value = schedule.schedule.midday.color_temp_k || 4000;
            }
            if (schedule.schedule.afternoon) {
                document.getElementById('afternoonTime').value = schedule.schedule.afternoon.time || '18:00';
                document.getElementById('afternoonColorTemp').value = schedule.schedule.afternoon.color_temp_k || 3000;
            }
        }
    } else {
        enableCheckbox.checked = false;
        details.style.display = 'none';
    }
}

// Initialize color temperature controls
function initColorTempControls() {
    // Load profiles first
    loadColorTempProfiles();
    
    // Add event listeners
    const enableCheckbox = document.getElementById('enableColorTempSchedule');
    const profileSelect = document.getElementById('plantTypeProfile');
    
    if (enableCheckbox) {
        enableCheckbox.addEventListener('change', toggleColorTempSchedule);
    }
    
    if (profileSelect) {
        profileSelect.addEventListener('change', handlePlantTypeProfileChange);
    }
    
    // Initial toggle state
    toggleColorTempSchedule();
}

// Call initialization when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize color temperature controls if on zones page
    if (window.location.pathname === '/zones') {
        setTimeout(initColorTempControls, 100); // Small delay to ensure other DOM elements are ready
    }
});