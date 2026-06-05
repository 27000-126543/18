/* 仪表盘页面逻辑 */

let riskPieChart, rulBarChart, sensorLineChart, woStatusChart;
let equipmentList = [];

document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  loadDashboardStats();
  loadEquipments();
  setInterval(loadDashboardStats, 30000);
});

function initCharts() {
  riskPieChart = createRiskPieChart('chartRiskPie',
    { high: 0, medium: 0, low: 0, normal: 0 });
  rulBarChart = createRULBarChart('chartRULBar', Array(10).fill(0));
  sensorLineChart = createSensorLineChart('chartSensorLine');
  woStatusChart = createWOStatusChart('chartWOStatus', {});
}

function loadDashboardStats() {
  apiGet('/api/dashboard/stats', (data) => {
    document.getElementById('kpiTotal').textContent = fmtNumber(data.active_equipments);
    document.getElementById('kpiHighRisk').textContent = fmtNumber(data.risk_distribution.high + data.risk_distribution.medium);
    document.getElementById('kpiPendingWO').textContent =
      fmtNumber((data.work_order_stats.pending || 0) + (data.work_order_stats.in_progress || 0));

    const totalRisk = data.risk_distribution.high + data.risk_distribution.medium +
      data.risk_distribution.low + data.risk_distribution.normal;
    const avgHealth = totalRisk > 0
      ? Math.round((data.risk_distribution.normal * 95 + data.risk_distribution.low * 75 +
        data.risk_distribution.medium * 45 + data.risk_distribution.high * 15) / totalRisk)
      : 0;
    document.getElementById('kpiAvgHealth').textContent = avgHealth;

    riskPieChart.setOption({
      series: [{
        data: [
          { value: data.risk_distribution.high, name: '高危', itemStyle: { color: '#ff4444' } },
          { value: data.risk_distribution.medium, name: '中危', itemStyle: { color: '#ff6b35' } },
          { value: data.risk_distribution.low, name: '低危', itemStyle: { color: '#f59e0b' } },
          { value: data.risk_distribution.normal, name: '正常', itemStyle: { color: '#10b981' } }
        ].filter(d => d.value > 0)
      }]
    });

    rulBarChart.setOption({
      series: [{
        data: data.rul_distribution
      }]
    });

    woStatusChart.setOption({
      series: [{ data: [
        data.work_order_stats.pending || 0,
        data.work_order_stats.in_progress || 0,
        data.work_order_stats.completed || 0,
        data.work_order_stats.verified || 0
      ]}]
    });

    renderAnomalyList(data.anomalies);
    renderLowStockList(data.low_stock);
  });
}

function loadEquipments() {
  apiGet('/api/equipments/list', (list) => {
    equipmentList = list;
    const sel = document.getElementById('equipmentSelect');
    if (!sel) return;
    sel.innerHTML = list.map(e =>
      `<option value="${e.id}">${e.equipment_code} - ${e.name} [RUL:${fmtFloat(e.rul_score,0)}]</option>`
    ).join('');
    if (list.length > 0) {
      loadSensorData(list[0].id);
      sel.onchange = () => loadSensorData(parseInt(sel.value));
    }
  });
}

function loadSensorData(equipmentId) {
  const eq = equipmentList.find(e => e.id === equipmentId);
  apiGet(`/api/sensor/realtime/${equipmentId}?hours=24`, (data) => {
    updateSensorChart(sensorLineChart, data);
    if (eq) {
      document.getElementById('sensorInfo').textContent =
        `${eq.equipment_code} ${eq.name} | 位置: ${eq.location || '-'} | RUL评分: ${fmtFloat(eq.rul_score, 1)}`;
    }
  });
}

function renderAnomalyList(anomalies) {
  const el = document.getElementById('anomalyList');
  if (!el) return;
  if (!anomalies || anomalies.length === 0) {
    el.innerHTML = '<div style="padding:20px 0;text-align:center;color:var(--text-dim);">暂无异常告警</div>';
    return;
  }
  el.innerHTML = anomalies.slice(0, 10).map(a => `
    <div class="alert-item">
      <div class="alert-icon ${a.vibration > 7 || a.temperature > 75 ? 'danger' : 'warning'}">⚠</div>
      <div class="alert-content">
        <div class="alert-title">${a.equipment_code} - ${a.equipment_name}</div>
        <div class="alert-desc">
          温度: <b style="color:var(--red-danger)">${fmtFloat(a.temperature,1)}℃</b> &nbsp;
          振动: <b style="color:var(--cyan-primary)">${fmtFloat(a.vibration,2)}mm/s</b> &nbsp;
          电流: <b style="color:var(--green-ok)">${fmtFloat(a.current,2)}A</b>
        </div>
      </div>
      <div class="alert-time">${(a.collection_time||'').slice(11,19)}</div>
    </div>
  `).join('');
}

function renderLowStockList(parts) {
  const el = document.getElementById('lowStockList');
  if (!el) return;
  if (!parts || parts.length === 0) {
    el.innerHTML = '<div style="padding:20px 0;text-align:center;color:var(--text-dim);">暂无库存预警</div>';
    return;
  }
  el.innerHTML = parts.map(p => `
    <div class="alert-item">
      <div class="alert-icon ${p.current_stock == 0 ? 'danger' : 'warning'}">📦</div>
      <div class="alert-content">
        <div class="alert-title">${p.part_code} - ${p.name}</div>
        <div class="alert-desc">
          当前库存: <b style="color:${p.current_stock == 0 ? 'var(--red-danger)' : 'var(--orange-alert)'}">${p.current_stock}</b>
          / 安全库存: ${p.safety_stock}
          <div class="health-bar" style="margin-top:4px;">
            <div class="health-bar-fill" style="width:${Math.min(100, p.stock_pct || 0)}%"></div>
          </div>
        </div>
      </div>
    </div>
  `).join('');
}
