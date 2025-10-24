// FPL Analytics Dashboard JavaScript

const API_BASE = '';
let analyticsData = null;

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;

        // Update active tab
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update active content
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        document.getElementById(tabName).classList.add('active');
    });
});

// Loading overlay
function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

// Initialize and load all data
document.getElementById('loadDataBtn').addEventListener('click', loadAllAnalytics);

async function loadAllAnalytics() {
    showLoading();
    try {
        // Initialize
        const initResponse = await fetch(`${API_BASE}/api/init`);
        const initData = await initResponse.json();

        if (!initData.success) {
            alert('Failed to initialize analytics');
            return;
        }

        document.getElementById('gwInfo').innerHTML = `
            <p>Gameweeks Completed: ${initData.gameweeks_played} | Target GW: ${initData.target_gameweek}</p>
        `;

        // Load all analytics
        await Promise.all([
            loadTeamReliability(),
            loadDifferentials(),
            loadEmergingPlayers(),
            loadShotsAnalysis(),
            loadTopPlayers()
        ]);

        alert('Analytics data loaded successfully!');
    } catch (error) {
        console.error('Error loading analytics:', error);
        alert('Failed to load analytics data');
    } finally {
        hideLoading();
    }
}

async function loadTeamReliability() {
    const response = await fetch(`${API_BASE}/api/team_reliability`);
    const data = await response.json();

    // Create defensive chart - ALL TEAMS
    const defenseDiv = document.getElementById('defenseCharts');
    const allTeamsDefense = data.teams.sort((a, b) => a.xga_per_90 - b.xga_per_90);

    Plotly.newPlot('defenseCharts', [{
        type: 'bar',
        x: allTeamsDefense.map(t => t.short_name),
        y: allTeamsDefense.map(t => t.xga_per_90),
        marker: {color: 'lightblue'},
        text: allTeamsDefense.map(t => t.xga_per_90.toFixed(2)),
        textposition: 'outside'
    }], {
        title: 'All Teams - Expected Goals Against per 90',
        xaxis: {title: 'Team'},
        yaxis: {title: 'Expected Goals Against per 90'},
        height: 500
    });

    // Create attack chart - ALL TEAMS
    const attackDiv = document.getElementById('attackCharts');
    const allTeamsAttack = data.teams.sort((a, b) => b.xg_per_90 - a.xg_per_90);

    Plotly.newPlot('attackCharts', [{
        type: 'bar',
        x: allTeamsAttack.map(t => t.short_name),
        y: allTeamsAttack.map(t => t.xg_per_90),
        marker: {color: 'lightcoral'},
        text: allTeamsAttack.map(t => t.xg_per_90.toFixed(2)),
        textposition: 'outside'
    }], {
        title: 'All Teams - Expected Goals per 90',
        xaxis: {title: 'Team'},
        yaxis: {title: 'Expected Goals per 90'},
        height: 500
    });

    // Create table
    const tableDiv = document.getElementById('teamReliabilityTable');
    let tableHTML = `
        <h3>Team Reliability Data</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Team</th>
                    <th>xGA/90</th>
                    <th>xG/90</th>
                    <th>CS Rate</th>
                    <th>Shots Faced/90</th>
                </tr>
            </thead>
            <tbody>
    `;

    data.teams.forEach(team => {
        tableHTML += `
            <tr>
                <td>${team.short_name}</td>
                <td>${team.xga_per_90.toFixed(2)}</td>
                <td>${team.xg_per_90.toFixed(2)}</td>
                <td>${(team.clean_sheet_rate * 100).toFixed(0)}%</td>
                <td>${team.shots_faced_per_90.toFixed(1)}</td>
            </tr>
        `;
    });

    tableHTML += '</tbody></table>';
    tableDiv.innerHTML = tableHTML;
}

async function loadDifferentials() {
    const response = await fetch(`${API_BASE}/api/differentials`);
    const data = await response.json();

    if (data.players.length === 0) {
        document.getElementById('differentialsChart').innerHTML = '<p>No differentials found</p>';
        return;
    }

    // Chart
    const top10 = data.players.slice(0, 10);
    Plotly.newPlot('differentialsChart', [{
        type: 'bar',
        y: top10.map(p => `${p.web_name} (${p.position})`),
        x: top10.map(p => p.differential_score),
        orientation: 'h',
        marker: {color: 'purple'},
        text: top10.map(p => p.differential_score.toFixed(1)),
        textposition: 'outside'
    }], {
        title: 'Top Differential Players',
        xaxis: {title: 'Differential Score'},
        yaxis: {title: ''},
        height: 500
    });

    // Table
    let tableHTML = `
        <h3>All Differentials</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Pos</th>
                    <th>Price</th>
                    <th>Pts/90</th>
                    <th>Form</th>
                    <th>Own%</th>
                    <th>Score</th>
                </tr>
            </thead>
            <tbody>
    `;

    data.players.forEach(player => {
        tableHTML += `
            <tr>
                <td>${player.web_name}</td>
                <td>${player.team_name}</td>
                <td>${player.position}</td>
                <td>£${player.value.toFixed(1)}m</td>
                <td>${player.points_per_90.toFixed(1)}</td>
                <td>${player.form_score.toFixed(1)}</td>
                <td>${player.selected_by_percent.toFixed(1)}%</td>
                <td>${player.differential_score.toFixed(1)}</td>
            </tr>
        `;
    });

    tableHTML += '</tbody></table>';
    document.getElementById('differentialsTable').innerHTML = tableHTML;
}

async function loadEmergingPlayers() {
    const response = await fetch(`${API_BASE}/api/emerging_players`);
    const data = await response.json();

    if (data.players.length === 0) {
        document.getElementById('emergingChart').innerHTML = '<p>No emerging players found</p>';
        return;
    }

    // Chart
    const top10 = data.players.slice(0, 10);
    Plotly.newPlot('emergingChart', [{
        type: 'bar',
        y: top10.map(p => `${p.web_name} (${p.position})`),
        x: top10.map(p => p.emergence_score),
        orientation: 'h',
        marker: {color: 'gold'},
        text: top10.map(p => p.emergence_score.toFixed(1)),
        textposition: 'outside'
    }], {
        title: 'Top Emerging FPL Assets',
        xaxis: {title: 'Emergence Score'},
        yaxis: {title: ''},
        height: 500
    });

    // Table
    let tableHTML = `
        <h3>All Emerging Players</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Pos</th>
                    <th>Price</th>
                    <th>Form</th>
                    <th>Own%</th>
                    <th>Score</th>
                </tr>
            </thead>
            <tbody>
    `;

    data.players.forEach(player => {
        tableHTML += `
            <tr>
                <td>${player.web_name}</td>
                <td>${player.team_name}</td>
                <td>${player.position}</td>
                <td>£${player.value.toFixed(1)}m</td>
                <td>${player.form_score.toFixed(1)}</td>
                <td>${player.selected_by_percent.toFixed(1)}%</td>
                <td>${player.emergence_score.toFixed(1)}</td>
            </tr>
        `;
    });

    tableHTML += '</tbody></table>';
    document.getElementById('emergingTable').innerHTML = tableHTML;
}

async function loadShotsAnalysis() {
    const response = await fetch(`${API_BASE}/api/shots_analysis`);
    const data = await response.json();

    if (!data.by_player || data.by_player.length === 0) {
        document.getElementById('playerShotsChart').innerHTML = '<p>No shots data available</p>';
        return;
    }

    // Player Shots Chart
    const top15Players = data.by_player.slice(0, 15);
    Plotly.newPlot('playerShotsChart', [{
        type: 'bar',
        y: top15Players.map(p => `${p.web_name} (${p.position})`),
        x: top15Players.map(p => p.shots_per_90),
        orientation: 'h',
        marker: {color: 'lightblue'},
        text: top15Players.map(p => p.shots_per_90.toFixed(2)),
        textposition: 'outside',
        name: 'Shots/90'
    }], {
        title: 'Top Players by Shots per 90',
        xaxis: {title: 'Shots per 90 Minutes'},
        yaxis: {title: ''},
        height: 600
    });

    // Team Shots Chart
    if (data.team_shots && data.team_shots.length > 0) {
        const top15Teams = data.team_shots.slice(0, 15);
        Plotly.newPlot('teamShotsChart', [{
            type: 'bar',
            x: top15Teams.map(t => t.team_name),
            y: top15Teams.map(t => t.shots_per_90),
            marker: {color: 'lightcoral'},
            text: top15Teams.map(t => t.shots_per_90.toFixed(1)),
            textposition: 'outside',
            name: 'Shots/90'
        }], {
            title: 'Team Shots per 90',
            xaxis: {title: 'Team'},
            yaxis: {title: 'Shots per 90'},
            height: 400
        });
    }

    // Position Comparison Chart
    if (data.by_position && data.by_position.length > 0) {
        const positions = data.by_position;
        Plotly.newPlot('positionShotsChart', [
            {
                type: 'bar',
                x: positions.map(p => p.position),
                y: positions.map(p => p.avg_shots_per_90),
                name: 'Avg Shots/90',
                marker: {color: 'lightgreen'}
            },
            {
                type: 'bar',
                x: positions.map(p => p.position),
                y: positions.map(p => p.avg_shots_on_goal_per_90),
                name: 'Avg Shots on Goal/90',
                marker: {color: 'gold'}
            },
            {
                type: 'bar',
                x: positions.map(p => p.position),
                y: positions.map(p => p.avg_xg_per_90),
                name: 'Avg xG/90',
                marker: {color: 'purple'}
            }
        ], {
            title: 'Average Metrics by Position',
            xaxis: {title: 'Position'},
            yaxis: {title: 'Per 90 Minutes'},
            barmode: 'group',
            height: 400
        });
    }

    // Detailed Table
    let tableHTML = `
        <h3>Player Shots Analysis</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Pos</th>
                    <th>Price</th>
                    <th>Shots/90</th>
                    <th>SoG/90</th>
                    <th>xG/90</th>
                    <th>Goals</th>
                    <th>Points</th>
                </tr>
            </thead>
            <tbody>
    `;

    data.by_player.forEach(player => {
        tableHTML += `
            <tr>
                <td>${player.web_name}</td>
                <td>${player.team_name}</td>
                <td>${player.position}</td>
                <td>£${player.value.toFixed(1)}m</td>
                <td>${player.shots_per_90.toFixed(2)}</td>
                <td>${player.shots_on_goal_per_90.toFixed(2)}</td>
                <td>${player.xg_per_90.toFixed(3)}</td>
                <td>${player.goals_scored}</td>
                <td>${player.total_points}</td>
            </tr>
        `;
    });

    tableHTML += '</tbody></table>';
    document.getElementById('shotsTable').innerHTML = tableHTML;
}

async function loadTopPlayers() {
    const response = await fetch(`${API_BASE}/api/top_players`);
    const data = await response.json();

    // Store data globally
    window.topPlayersData = data;

    // Show GKP by default
    displayTopPlayersForPosition('GKP');

    // Add position button handlers
    document.querySelectorAll('.pos-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.pos-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            displayTopPlayersForPosition(btn.dataset.pos);
        });
    });
}

function displayTopPlayersForPosition(position) {
    const players = window.topPlayersData[position];

    if (!players || players.length === 0) {
        document.getElementById('topPlayersContent').innerHTML = '<p>No players found</p>';
        return;
    }

    let html = `
        <h3>Top ${position} Players</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Price</th>
                    <th>Total Points</th>
                    <th>Form</th>
                    <th>PPG</th>
                    <th>Ownership</th>
                </tr>
            </thead>
            <tbody>
    `;

    players.forEach(player => {
        html += `
            <tr>
                <td>${player.web_name}</td>
                <td>${player.team_name}</td>
                <td>£${player.value.toFixed(1)}m</td>
                <td>${player.total_points}</td>
                <td>${player.form_score.toFixed(1)}</td>
                <td>${player.ppg.toFixed(1)}</td>
                <td>${player.selected_by_percent.toFixed(1)}%</td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    document.getElementById('topPlayersContent').innerHTML = html;
}
