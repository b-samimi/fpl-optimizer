// FPL Transfer Review App - Main JavaScript

const API_BASE = '';
let currentTeam = null;
let allPlayers = [];

// Utility Functions
function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function showError(message) {
    alert(`Error: ${message}`);
}

// Initialize App
async function initApp() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/api/init`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            console.log(`Loaded ${data.total_players} players, Current GW: ${data.current_gameweek}`);
        } else {
            showError('Failed to initialize app');
        }
    } catch (error) {
        console.error('Init error:', error);
        showError('Failed to connect to server');
    } finally {
        hideLoading();
    }
}

// Load Team
async function loadTeam() {
    const managerId = document.getElementById('managerId').value;

    if (!managerId) {
        showError('Please enter a Manager ID');
        return;
    }

    showLoading();
    try {
        const response = await fetch(`${API_BASE}/api/team/${managerId}`);
        const data = await response.json();

        if (response.ok) {
            currentTeam = data;
            displayTeamStats(data.stats);
            displayTeam(data.team);
            displayRecommendations(data.team);
            document.getElementById('teamStats').classList.remove('hidden');
            document.getElementById('teamDisplay').classList.remove('hidden');
        } else {
            showError(data.error || 'Failed to load team');
        }
    } catch (error) {
        console.error('Load team error:', error);
        showError('Failed to load team data');
    } finally {
        hideLoading();
    }
}

// Display Team Stats
function displayTeamStats(stats) {
    document.getElementById('teamValue').textContent = `£${stats.total_value.toFixed(1)}m`;
    document.getElementById('totalPoints').textContent = stats.total_points;
    document.getElementById('avgForm').textContent = stats.avg_form.toFixed(1);

    const issuesEl = document.getElementById('playersWithIssues');
    issuesEl.textContent = stats.players_with_issues;
    issuesEl.className = 'stat-value';
    if (stats.players_with_issues > 0) {
        issuesEl.classList.add('warning');
    }
}

// Display Team
function displayTeam(team) {
    const container = document.getElementById('playersList');
    container.innerHTML = '';

    // Group by position
    const positions = ['GKP', 'DEF', 'MID', 'FWD'];

    positions.forEach(pos => {
        const posPlayers = team.filter(p => p.position === pos);

        if (posPlayers.length > 0) {
            const posSection = document.createElement('div');
            posSection.className = 'position-section';
            posSection.dataset.position = pos;

            const posHeader = document.createElement('h3');
            posHeader.className = 'position-header';
            posHeader.textContent = getPositionName(pos);
            posSection.appendChild(posHeader);

            posPlayers.forEach(player => {
                const playerCard = createPlayerCard(player);
                posSection.appendChild(playerCard);
            });

            container.appendChild(posSection);
        }
    });
}

function createPlayerCard(player) {
    const card = document.createElement('div');
    card.className = 'player-card';

    if (player.analysis.has_issues) {
        card.classList.add('has-issues');
    }

    const issuesBadges = player.analysis.issues.map(issue =>
        `<span class="badge badge-${issue.severity}">${issue.message}</span>`
    ).join('');

    card.innerHTML = `
        <div class="player-header">
            <div>
                <h4 class="player-name">${player.name}</h4>
                <p class="player-meta">${player.team} - ${player.position}</p>
            </div>
            <div class="player-value">£${player.value.toFixed(1)}m</div>
        </div>
        <div class="player-stats">
            <div class="stat">
                <span class="stat-label">Points</span>
                <span class="stat-val">${player.total_points}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Form</span>
                <span class="stat-val">${player.form.toFixed(1)}</span>
            </div>
            <div class="stat">
                <span class="stat-label">PPG</span>
                <span class="stat-val">${player.ppg.toFixed(1)}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Minutes</span>
                <span class="stat-val">${player.minutes}</span>
            </div>
        </div>
        ${issuesBadges ? `<div class="issues-badges">${issuesBadges}</div>` : ''}
        <div class="player-actions">
            <button class="btn-small btn-info" onclick="viewPlayerDetails(${player.id})">Details</button>
            ${player.analysis.has_issues ?
                `<button class="btn-small btn-warning" onclick="findReplacements(${player.id})">Find Replacement</button>`
                : ''}
        </div>
    `;

    return card;
}

// Display Recommendations
function displayRecommendations(team) {
    const container = document.getElementById('recommendationsList');

    // Filter players with issues and sort by priority
    const playersWithIssues = team
        .filter(p => p.analysis.has_issues)
        .sort((a, b) => b.analysis.priority - a.analysis.priority);

    if (playersWithIssues.length === 0) {
        container.innerHTML = '<p class="success-message">No urgent transfer recommendations. Your team looks good!</p>';
        return;
    }

    container.innerHTML = '';

    playersWithIssues.forEach((player, index) => {
        const recCard = document.createElement('div');
        recCard.className = 'recommendation-card';

        const priority = player.analysis.priority >= 5 ? 'HIGH' :
                        player.analysis.priority >= 3 ? 'MEDIUM' : 'LOW';
        const priorityClass = priority.toLowerCase();

        const issues = player.analysis.issues.map(i => i.message).join(', ');

        recCard.innerHTML = `
            <div class="rec-header">
                <h4>${index + 1}. Transfer Out: ${player.name} (${player.position})</h4>
                <span class="priority-badge ${priorityClass}">${priority} PRIORITY</span>
            </div>
            <p class="rec-issues">Issues: ${issues}</p>
            <button class="btn-small btn-primary" onclick="findReplacements(${player.id})">
                Find Replacements
            </button>
        `;

        container.appendChild(recCard);
    });
}

// Find Replacements
async function findReplacements(playerId) {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/api/replacements/${playerId}`);
        const data = await response.json();

        if (response.ok) {
            displayReplacementsModal(data);
        } else {
            showError(data.error || 'Failed to find replacements');
        }
    } catch (error) {
        console.error('Find replacements error:', error);
        showError('Failed to find replacements');
    } finally {
        hideLoading();
    }
}

function displayReplacementsModal(data) {
    const modal = document.getElementById('replacementsModal');
    const content = document.getElementById('replacementsContent');

    content.innerHTML = `
        <h2>Replacements for ${data.player.name} (£${data.player.value.toFixed(1)}m)</h2>
        <div class="replacements-list">
            ${data.replacements.map(player => `
                <div class="replacement-card">
                    <div class="replacement-header">
                        <div>
                            <h4>${player.web_name}</h4>
                            <p>${player.team_name}</p>
                        </div>
                        <div class="replacement-value">£${player.value.toFixed(1)}m</div>
                    </div>
                    <div class="replacement-stats">
                        <div class="stat">
                            <span class="stat-label">Points</span>
                            <span class="stat-val">${player.total_points}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Form</span>
                            <span class="stat-val">${player.form_score.toFixed(1)}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">PPG</span>
                            <span class="stat-val">${player.ppg.toFixed(1)}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Owned</span>
                            <span class="stat-val">${player.selected_by.toFixed(1)}%</span>
                        </div>
                    </div>
                    <button class="btn-small btn-info" onclick="viewPlayerDetails(${player.id})">
                        View Details
                    </button>
                </div>
            `).join('')}
        </div>
    `;

    modal.classList.remove('hidden');
}

// Search Players
async function searchPlayers() {
    const query = document.getElementById('searchInput').value;
    const position = document.getElementById('positionFilter').value;
    const sortBy = document.getElementById('sortBy').value;

    showLoading();
    try {
        const params = new URLSearchParams({
            q: query,
            sort: sortBy,
            limit: 20
        });

        if (position) params.append('position', position);

        const response = await fetch(`${API_BASE}/api/players/search?${params}`);
        const data = await response.json();

        if (response.ok) {
            displaySearchResults(data.results);
        } else {
            showError(data.error || 'Search failed');
        }
    } catch (error) {
        console.error('Search error:', error);
        showError('Search failed');
    } finally {
        hideLoading();
    }
}

function displaySearchResults(players) {
    const container = document.getElementById('searchResults');

    if (players.length === 0) {
        container.innerHTML = '<p class="no-results">No players found</p>';
        return;
    }

    container.innerHTML = `
        <div class="search-results-grid">
            ${players.map(player => `
                <div class="search-result-card">
                    <div class="result-header">
                        <div>
                            <h4>${player.name}</h4>
                            <p class="result-meta">${player.team} - ${player.position}</p>
                        </div>
                        <div class="result-value">£${player.value.toFixed(1)}m</div>
                    </div>
                    <div class="result-stats">
                        <span>Pts: ${player.total_points}</span>
                        <span>Form: ${player.form.toFixed(1)}</span>
                        <span>PPG: ${player.ppg.toFixed(1)}</span>
                        <span>Own: ${player.selected_by.toFixed(1)}%</span>
                    </div>
                    <button class="btn-small btn-info" onclick="viewPlayerDetails(${player.id})">
                        View Details
                    </button>
                </div>
            `).join('')}
        </div>
    `;
}

// Load Top Players
async function loadTopPlayers() {
    const category = document.getElementById('topCategory').value;
    const position = document.getElementById('topPosition').value;

    showLoading();
    try {
        const params = new URLSearchParams({
            category: category,
            limit: 10
        });

        if (position) params.append('position', position);

        const response = await fetch(`${API_BASE}/api/top_players?${params}`);
        const data = await response.json();

        if (response.ok) {
            displayTopPlayers(data.players, data.category);
        } else {
            showError(data.error || 'Failed to load top players');
        }
    } catch (error) {
        console.error('Load top players error:', error);
        showError('Failed to load top players');
    } finally {
        hideLoading();
    }
}

function displayTopPlayers(players, category) {
    const container = document.getElementById('topPlayersList');

    const categoryNames = {
        'value_score': 'Value Score',
        'total_points': 'Total Points',
        'form_score': 'Form',
        'ppg': 'PPG'
    };

    container.innerHTML = `
        <div class="top-players-grid">
            ${players.map((player, index) => `
                <div class="top-player-card">
                    <div class="top-rank">#${index + 1}</div>
                    <div class="top-player-info">
                        <h4>${player.name}</h4>
                        <p>${player.team} - ${player.position}</p>
                        <div class="top-stat">
                            <span>${categoryNames[category]}: </span>
                            <strong>${player[category].toFixed(1)}</strong>
                        </div>
                        <div class="top-player-stats">
                            <span>£${player.value.toFixed(1)}m</span>
                            <span>${player.total_points} pts</span>
                            <span>Form: ${player.form.toFixed(1)}</span>
                        </div>
                    </div>
                    <button class="btn-small btn-info" onclick="viewPlayerDetails(${player.id})">
                        Details
                    </button>
                </div>
            `).join('')}
        </div>
    `;
}

// View Player Details
async function viewPlayerDetails(playerId) {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/api/player/${playerId}`);
        const data = await response.json();

        if (response.ok) {
            displayPlayerDetailsModal(data);
        } else {
            showError(data.error || 'Failed to load player details');
        }
    } catch (error) {
        console.error('Player details error:', error);
        showError('Failed to load player details');
    } finally {
        hideLoading();
    }
}

function displayPlayerDetailsModal(player) {
    const modal = document.getElementById('playerModal');
    const content = document.getElementById('playerDetails');

    const statusColors = {
        'a': 'green',
        'i': 'red',
        'd': 'orange',
        's': 'red',
        'u': 'gray'
    };

    content.innerHTML = `
        <h2>${player.full_name}</h2>
        <div class="player-detail-header">
            <div>
                <p class="detail-team">${player.team} - ${player.position}</p>
                <p class="detail-price">£${player.value.toFixed(1)}m</p>
            </div>
            <div class="detail-status ${statusColors[player.status]}">
                ${player.status === 'a' ? 'Available' : 'Unavailable'}
            </div>
        </div>

        <div class="detail-stats-grid">
            <div class="detail-stat">
                <h4>Total Points</h4>
                <p class="detail-stat-value">${player.total_points}</p>
            </div>
            <div class="detail-stat">
                <h4>Form</h4>
                <p class="detail-stat-value">${player.form.toFixed(1)}</p>
            </div>
            <div class="detail-stat">
                <h4>Points Per Game</h4>
                <p class="detail-stat-value">${player.ppg.toFixed(1)}</p>
            </div>
            <div class="detail-stat">
                <h4>Ownership</h4>
                <p class="detail-stat-value">${player.selected_by.toFixed(1)}%</p>
            </div>
        </div>

        <div class="detail-stats-grid">
            <div class="detail-stat">
                <h4>Minutes</h4>
                <p class="detail-stat-value">${player.minutes}</p>
            </div>
            <div class="detail-stat">
                <h4>Goals</h4>
                <p class="detail-stat-value">${player.goals_scored}</p>
            </div>
            <div class="detail-stat">
                <h4>Assists</h4>
                <p class="detail-stat-value">${player.assists}</p>
            </div>
            <div class="detail-stat">
                <h4>Clean Sheets</h4>
                <p class="detail-stat-value">${player.clean_sheets}</p>
            </div>
        </div>

        ${player.news ? `
            <div class="player-news">
                <h4>Latest News</h4>
                <p>${player.news}</p>
            </div>
        ` : ''}

        <div class="detail-value-score">
            <h4>Value Score: ${player.value_score.toFixed(1)}</h4>
            <p class="help-text">Higher is better (considers form, points per game, and price)</p>
        </div>
    `;

    modal.classList.remove('hidden');
}

// Position Filter
function filterByPosition(position) {
    const sections = document.querySelectorAll('.position-section');

    sections.forEach(section => {
        if (position === 'all' || section.dataset.position === position) {
            section.style.display = 'block';
        } else {
            section.style.display = 'none';
        }
    });

    // Update active button
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.position === position) {
            btn.classList.add('active');
        }
    });
}

// Helpers
function getPositionName(pos) {
    const names = {
        'GKP': 'Goalkeepers',
        'DEF': 'Defenders',
        'MID': 'Midfielders',
        'FWD': 'Forwards'
    };
    return names[pos] || pos;
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Initialize app
    initApp();

    // Team loading
    document.getElementById('loadTeamBtn').addEventListener('click', loadTeam);
    document.getElementById('managerId').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loadTeam();
    });

    // Position filters
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            filterByPosition(btn.dataset.position);
        });
    });

    // Search
    document.getElementById('searchBtn').addEventListener('click', searchPlayers);
    document.getElementById('searchInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchPlayers();
    });

    // Top players
    document.getElementById('loadTopBtn').addEventListener('click', loadTopPlayers);

    // Modal close buttons
    document.querySelectorAll('.modal .close').forEach(closeBtn => {
        closeBtn.addEventListener('click', () => {
            closeBtn.closest('.modal').classList.add('hidden');
        });
    });

    // Close modal on outside click
    window.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            e.target.classList.add('hidden');
        }
    });
});
