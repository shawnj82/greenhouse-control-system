// JavaScript for Crane Creek Greenhouse Web Interface

// Global variables
let currentZones = {};
let selectedZoneKeys = new Set();
let multiSelectMode = false;

// Helper: resolve grid container supporting legacy ID
function getGridContainer() {
    return document.getElementById('greenhouse-grid') ||
           document.getElementById('greenhouse-grid-table-container');
}

// Helper: ensure overlays exist inside the grid container
function ensureOverlays(container) {
    if (!container) return { fixturesOverlay: null, sensorsOverlay: null };
    // Prefer overlays under the container
    let fixturesOverlay = container.querySelector('#lights-overlay');
    let sensorsOverlay = container.querySelector('#sensors-overlay');
    // If overlays exist elsewhere in the DOM, move them under container
    if (!fixturesOverlay) {
        const stray = document.getElementById('lights-overlay');
        if (stray) {
            fixturesOverlay = stray;
        } else {
            fixturesOverlay = document.createElement('div');
            fixturesOverlay.id = 'lights-overlay';
            fixturesOverlay.className = 'lights-overlay';
        }
        container.appendChild(fixturesOverlay);
    }
    if (!sensorsOverlay) {
        const stray = document.getElementById('sensors-overlay');
        if (stray) {
            sensorsOverlay = stray;
        } else {
            sensorsOverlay = document.createElement('div');
            sensorsOverlay.id = 'sensors-overlay';
            sensorsOverlay.className = 'sensors-overlay';
        }
        container.appendChild(sensorsOverlay);
    }
    return { fixturesOverlay, sensorsOverlay };
}

// Crop presets: per crop -> stage -> spectrum and targets
// Values are generalized best-practice ranges; tweak per environment/fixture
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
    kale: {
        seedling: { red: 35, blue: 35, white: 30, par: 150, hours: 16 },
        vegetative: { red: 50, blue: 25, white: 25, par: 250, hours: 16 }
    },
    tomato: {
        seedling: { red: 35, blue: 35, white: 30, par: 200, hours: 18 },
        vegetative: { red: 55, blue: 15, white: 30, par: 350, hours: 16 },
        flowering: { red: 60, blue: 10, white: 30, par: 450, hours: 14 },
        fruiting: { red: 65, blue: 10, white: 25, par: 500, hours: 14 }
    },
    pepper: {
        seedling: { red: 35, blue: 35, white: 30, par: 200, hours: 18 },
        vegetative: { red: 55, blue: 15, white: 30, par: 350, hours: 16 },
        flowering: { red: 60, blue: 10, white: 30, par: 450, hours: 14 },
        fruiting: { red: 65, blue: 10, white: 25, par: 500, hours: 14 }
    },
    cucumber: {
        seedling: { red: 35, blue: 35, white: 30, par: 200, hours: 18 },
        vegetative: { red: 55, blue: 15, white: 30, par: 350, hours: 16 },
        flowering: { red: 60, blue: 10, white: 30, par: 450, hours: 14 },
        fruiting: { red: 60, blue: 10, white: 30, par: 450, hours: 14 }
    },
    strawberry: {
        vegetative: { red: 55, blue: 20, white: 25, par: 250, hours: 16 },
        flowering: { red: 60, blue: 15, white: 25, par: 300, hours: 16 },
        fruiting: { red: 60, blue: 15, white: 25, par: 350, hours: 16 }
    },
    marigold: {
        seedling: { red: 40, blue: 30, white: 30, par: 150, hours: 16 },
        vegetative: { red: 50, blue: 20, white: 30, par: 200, hours: 16 },
        flowering: { red: 55, blue: 15, white: 30, par: 250, hours: 16 }
    },
    petunia: {
        seedling: { red: 40, blue: 30, white: 30, par: 150, hours: 16 },
        vegetative: { red: 50, blue: 20, white: 30, par: 200, hours: 16 },
        flowering: { red: 55, blue: 15, white: 30, par: 250, hours: 16 }
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
let gridSize = { rows: 4, cols: 6 };

// Device control functions
function controlDevice(device, action) {
    fetch(`/api/control/${device}/${action}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(`${device} turned ${action}`, 'success');
                setTimeout(updateStatus, 1000); // Update status after 1 second
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
        tempCard.textContent = status.temperature_c ? 
            status.temperature_c.toFixed(1) + '°C' : '--';
    }
    if (humCard) {
        humCard.textContent = status.humidity ? 
            status.humidity.toFixed(1) + '%' : '--';
    }
    if (lightCard) {
        lightCard.textContent = status.light_lux ? 
            Math.round(status.light_lux) + ' lux' : '--';
    }
    if (soilCard) {
        soilCard.textContent = status.soil_moisture ? 
            Math.round(status.soil_moisture) + '%' : '--';
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
        gridSize = zonesData.grid_size || { rows: 4, cols: 6 };
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
            const zone = currentZones.zones && currentZones.zones[key];
            if (zone) {
                cell.className += ' planted';
                let stageLine = '';
                if (zone.stage) {
                    stageLine = `<span class="zone-stage-badge">${zone.stage.charAt(0).toUpperCase() + zone.stage.slice(1)}</span><br>`;
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
    const showAmount = document.getElementById('showLightAmount');
    if (showAmount && showAmount.checked) {
        renderLightAmountOverlay();
    } else {
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
                const lightElement = document.createElement('div');
                lightElement.className = `light-fixture light-fixture-${light.status}`;
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
                const width = clampedColSpan * cellWidth + (clampedColSpan - 1) * colGap;
                const height = clampedRowSpan * cellHeight + (clampedRowSpan - 1) * rowGap;
                
                lightElement.style.cssText = `
                    position: absolute;
                    left: ${left}px;
                    top: ${top}px;
                    width: ${width}px;
                    height: ${height}px;
                    z-index: 20;
                `;
                
                // Add light info tooltip
                lightElement.innerHTML = `
                    <div class="light-info">
                        <div class="light-name">${light.name}</div>
                        <div class="light-specs">${light.width_inches}"×${light.height_inches}" | ${light.power_watts}W</div>
                        <div class="light-status status-${light.status}">${light.status.toUpperCase()}</div>
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
        const reading = currentLightSensors.readings?.[sid]?.lux;
        tt.textContent = `${cfg.name || sid} • ${cfg.type || ''} • ${reading != null ? Math.round(reading) + ' lux' : '—'}`;
        marker.appendChild(tt);

        overlay.appendChild(marker);
    }
}

function renderLightAmountOverlay() {
    const container = getGridContainer();
    if (!container) return;

    clearLightAmountOverlay();
    
    const overlay = document.createElement('div');
    overlay.id = 'light-amount-overlay';
    overlay.className = 'light-amount-overlay';
    overlay.style.gridTemplateColumns = `repeat(${gridSize.cols}, 1fr)`;
    overlay.style.gridTemplateRows = `repeat(${gridSize.rows}, 1fr)`;
    // Match the grid gap to align overlay cells with the underlying grid
    const cs = window.getComputedStyle(container);
    const gapVal = cs.gap || `${cs.rowGap || 0} ${cs.columnGap || 0}`;
    if (gapVal) overlay.style.gap = gapVal;
    
    // Calculate light amount for each grid cell
    for (let row = 0; row < gridSize.rows; row++) {
        for (let col = 0; col < gridSize.cols; col++) {
            const lightAmount = calculateLightAmount(row, col);
            const cell = document.createElement('div');
            cell.className = `light-amount-cell light-intensity-${lightAmount.intensity}`;
            
            // Add spectrum-based color if significant spectrum deviation
            const spectrumColor = getSpectrumColor(lightAmount.spectrum);
            if (spectrumColor) {
                cell.style.backgroundColor = spectrumColor;
            }
            
            const readingText = lightAmount.source === 'sensor' ? `${lightAmount.lux} (sensor)` : `${lightAmount.lux}`;
            cell.innerHTML = `
                <div class="light-amount-info">
                    ${readingText}
                </div>
            `;
            
            overlay.appendChild(cell);
        }
    }
    
    // Append under container; with z-index it will sit below fixtures and sensors
    container.appendChild(overlay);
}

function calculateLightAmount(row, col) {
    let totalLux = 0;
    let totalRed = 0;
    let totalBlue = 0;
    let totalWhite = 0;
    let lightCount = 0;
    
    // Base ambient light (simulated)
    const ambientLux = 50; // Base indoor lighting
    totalLux += ambientLux;
    
    // Check contribution from each light fixture
    if (currentLights.lights) {
        Object.values(currentLights.lights).forEach(light => {
            if (light.status === 'on') {
                const distance = getLightDistance(row, col, light.position);
                const contribution = getLightContribution(light, distance);
                
                if (contribution.lux > 0) {
                    totalLux += contribution.lux;
                    totalRed += contribution.red;
                    totalBlue += contribution.blue;
                    totalWhite += contribution.white;
                    lightCount++;
                }
            }
        });
    }
    
    // Use configured sensor reading if available for this cell
    const sensorReading = getConfiguredSensorReading(row, col);
    if (sensorReading != null) {
        totalLux = Math.max(totalLux, sensorReading);
        return {
            lux: Math.round(totalLux),
            intensity: Math.min(9, Math.floor(totalLux / 100)),
            spectrum: { red: totalRed || 33, blue: totalBlue || 33, white: totalWhite || 33 },
            source: 'sensor'
        };
    }
    
    // Calculate average spectrum
    const spectrum = lightCount > 0 ? {
        red: totalRed / lightCount,
        blue: totalBlue / lightCount,
        white: totalWhite / lightCount
    } : { red: 33, blue: 33, white: 33 };
    
    return {
        lux: Math.round(totalLux),
        intensity: Math.min(9, Math.floor(totalLux / 100)), // 0-9 scale
        spectrum: spectrum,
        source: 'predicted'
    };
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
    if (!currentLightSensors || !currentLightSensors.readings) return null;
    const key = `${row}-${col}`;
    // Find any sensor mapped to this zone_key
    for (const [sid, cfg] of Object.entries(currentLightSensors.config?.sensors || {})) {
        if (cfg.zone_key === key) {
            const reading = currentLightSensors.readings[sid];
            if (reading && reading.lux != null) return reading.lux;
        }
    }
    return null;
}

function getSpectrumColor(spectrum) {
    // Only apply spectrum color if significantly different from balanced white
    const balanced = { red: 33, blue: 33, white: 33 };
    const threshold = 15; // Significant deviation threshold
    
    const redDiff = Math.abs(spectrum.red - balanced.red);
    const blueDiff = Math.abs(spectrum.blue - balanced.blue);
    
    if (redDiff > threshold || blueDiff > threshold) {
        // Calculate color based on spectrum
        const r = Math.min(255, Math.round(spectrum.red * 2.55));
        const g = Math.min(255, Math.round(spectrum.white * 2.55));
        const b = Math.min(255, Math.round(spectrum.blue * 2.55));
        
        return `rgba(${r}, ${g}, ${b}, 0.3)`;
    }
    
    return null; // Use default intensity color
}

function toggleLight(lightId, light) {
    const newStatus = light.status === 'on' ? 'off' : 'on';
    
    // Update local data
    currentLights.lights[lightId].status = newStatus;
    
    // Save to server
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
            showNotification(`${light.name} turned ${newStatus}`, 'success');
            renderLightsOverlay(); // Re-render to update status
        } else {
            showNotification('Failed to update light status', 'error');
        }
    })
    .catch(error => {
        showNotification('Error updating light status', 'error');
        console.error('Error:', error);
    });
}

// Zone configuration functions (for zones.html)
function selectZone(key, cellElement) {
    // Select single cell (single-select mode)
    cellElement.classList.add('selected');
    selectedZoneKey = key;
    selectedZoneKeys.add(key);
    
    // Show zone details panel
    const detailsPanel = document.getElementById('zoneDetails');
    if (detailsPanel) {
        detailsPanel.style.display = 'block';
        updateSelectionHeader();
        loadZoneFormForKey(key);
    }
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
        light_spectrum: {
            red_percent: parseInt(document.getElementById('redPercent').value) || 35,
            blue_percent: parseInt(document.getElementById('bluePercent').value) || 25,
            white_percent: parseInt(document.getElementById('whitePercent').value) || 40,
            par_target: parseInt(document.getElementById('parTarget').value) || 200
        }
    };

    // Determine targets
    const targets = selectedZoneKeys.size > 0 ? Array.from(selectedZoneKeys) : (selectedZoneKey ? [selectedZoneKey] : []);
    targets.forEach(k => {
        currentZones.zones[k] = { ...zoneConfig };
    });

    // Re-render grid
    renderGrid(true);
    if (!multiSelectMode) {
        closeZoneConfig();
    } else {
        updateSelectionHeader();
    }
    showNotification(`Zone configuration applied to ${targets.length} cell(s)`, 'success');
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
    const rows = parseInt(document.getElementById('gridRows').value) || 4;
    const cols = parseInt(document.getElementById('gridCols').value) || 6;
    
    gridSize = { rows, cols };
    currentZones.grid_size = gridSize;
    
    renderGrid(true);
    showNotification(`Grid resized to ${rows}×${cols}`, 'success');
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
    } else {
        // Reset to defaults
        const form = document.getElementById('zoneForm');
        if (form) form.reset();
        document.getElementById('redPercent').value = 35;
        document.getElementById('bluePercent').value = 25;
        document.getElementById('whitePercent').value = 40;
        document.getElementById('parTarget').value = 200;
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
        document.getElementById('lightHeight').value = 12;
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
        height_inches: parseInt(document.getElementById('lightHeight').value) || 12,
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
        notes: document.getElementById('lightNotes').value
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
        document.getElementById('lightHeight').value = light.height_inches || 12;
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
        html += `
            <tr>
                <td><strong>${light.name}</strong></td>
                <td>${light.type}</td>
                <td>${light.width_inches}"×${light.height_inches}"</td>
                <td>R${light.position.row} C${light.position.col} (${light.position.row_span}×${light.position.col_span})</td>
                <td>${light.power_watts}W</td>
                <td><span class="status status-${light.status}">${light.status.toUpperCase()}</span></td>
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
    
    if (showLightFixtures) {
        showLightFixtures.addEventListener('change', function() {
            console.log('Light fixtures toggle changed to:', this.checked);
            renderLightsOverlay();
        });
    }
    
    if (showLightAmount) {
        showLightAmount.addEventListener('change', function() {
            console.log('Light amount toggle changed to:', this.checked);
            renderLightsOverlay();
        });
    }
    if (showSensorMarkers) {
        showSensorMarkers.addEventListener('change', function() {
            console.log('Sensor markers toggle changed to:', this.checked);
            renderLightsOverlay();
        });
    }
    
    // Zones are always shown; no toggle handler needed
});