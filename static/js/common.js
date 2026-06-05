/* 通用工具函数 */

function updateClock() {
  const el = document.getElementById('currentTime');
  if (!el) return;
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  el.textContent = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

setInterval(updateClock, 1000);

function showModal(title, body, onConfirm) {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = body;
  const confirmBtn = document.getElementById('modalConfirm');
  if (onConfirm) {
    confirmBtn.style.display = 'inline-flex';
    confirmBtn.onclick = () => { onConfirm(); closeModal(); };
  } else {
    confirmBtn.style.display = 'none';
  }
  document.getElementById('globalModal').classList.add('show');
}

function closeModal() {
  document.getElementById('globalModal').classList.remove('show');
}

function apiGet(url, onSuccess, onError) {
  fetch(url, { headers: { 'Accept': 'application/json' } })
    .then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(data => { if (onSuccess) onSuccess(data); })
    .catch(e => {
      console.error('API Error:', url, e);
      if (onError) onError(e); else showModal('请求失败', `<p style="color:var(--text-dim)">${url}<br>${e.message}</p>`);
    });
}

function apiPost(url, data, onSuccess) {
  const body = new URLSearchParams();
  if (data) for (const k in data) body.append(k, data[k]);
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json' },
    body
  })
    .then(r => r.json())
    .then(d => { if (onSuccess) onSuccess(d); })
    .catch(e => { console.error('API Error:', url, e); });
}

function triggerCollect() {
  const btn = event.target.closest('button');
  const orig = btn.innerHTML;
  btn.innerHTML = '<span class="loading-spinner"></span> 采集中';
  btn.disabled = true;
  apiPost('/api/trigger/collect', {}, (d) => {
    btn.innerHTML = orig;
    btn.disabled = false;
    showModal('数据采集完成', `<p>成功采集 <b style="color:var(--cyan-primary)">${d.count}</b> 条传感器数据</p>`);
    if (typeof loadDashboardStats === 'function') loadDashboardStats();
    if (typeof loadEquipments === 'function') loadEquipments();
  });
}

function triggerAnalysis() {
  const btn = event.target.closest('button');
  const orig = btn.innerHTML;
  btn.innerHTML = '<span class="loading-spinner"></span> 分析中';
  btn.disabled = true;
  apiPost('/api/trigger/health_analysis', {}, (d) => {
    btn.innerHTML = orig;
    btn.disabled = false;
    showModal('健康分析完成',
      `<p>分析设备: <b style="color:var(--cyan-primary)">${d.analyzed}</b> 台</p>` +
      `<p>高风险设备: <b style="color:var(--orange-alert)">${d.high_risk}</b> 台 (已自动生成工单)</p>`);
    if (typeof loadDashboardStats === 'function') loadDashboardStats();
    if (typeof loadWorkOrders === 'function') loadWorkOrders();
  });
}

function fmtNumber(n) {
  if (n === null || n === undefined || isNaN(n)) return '-';
  return Number(n).toLocaleString();
}

function fmtFloat(n, d = 2) {
  if (n === null || n === undefined || isNaN(n)) return '-';
  return Number(n).toFixed(d);
}

function healthStatusTag(status) {
  const map = {
    high_risk: 'tag-high',
    medium_risk: 'tag-medium',
    low_risk: 'tag-low',
    normal: 'tag-normal'
  };
  const name = {
    high_risk: '高危',
    medium_risk: '中危',
    low_risk: '低危',
    normal: '正常'
  };
  return `<span class="tag ${map[status] || 'tag-info'}">${name[status] || status}</span>`;
}

function priorityTag(p) {
  const map = { high: 'tag-high', medium: 'tag-medium', low: 'tag-low' };
  const name = { high: '高', medium: '中', low: '低' };
  return `<span class="tag ${map[p] || 'tag-info'}">${name[p] || p}</span>`;
}

function workOrderStatusTag(s) {
  const map = {
    pending: 'tag-pending',
    in_progress: 'tag-in_progress',
    completed: 'tag-completed',
    verified: 'tag-verified',
    cancelled: 'tag-info'
  };
  const name = {
    pending: '待分配',
    in_progress: '进行中',
    completed: '已完成',
    verified: '已验证',
    cancelled: '已取消'
  };
  return `<span class="tag ${map[s] || 'tag-info'}">${name[s] || s}</span>`;
}

function approvalStatusTag(s) {
  const map = {
    pending: 'tag-pending',
    needs_approval: 'tag-medium',
    approved: 'tag-normal',
    rejected: 'tag-high',
    ordered: 'tag-in_progress'
  };
  const name = {
    pending: '待处理',
    needs_approval: '待审批',
    approved: '已通过',
    rejected: '已驳回',
    ordered: '已下单'
  };
  return `<span class="tag ${map[s] || 'tag-info'}">${name[s] || s}</span>`;
}

function sendTestEmail() {
  const btn = event.target.closest('button');
  const orig = btn.innerHTML;
  btn.innerHTML = '<span class="loading-spinner"></span> 发送中';
  btn.disabled = true;
  apiPost('/api/email/test', {}, (d) => {
    btn.innerHTML = orig;
    btn.disabled = false;
    if (d.success) {
      showModal('邮件发送成功',
        `<p style="color:var(--cyan-primary);">✓ ${d.message}</p>` +
        `<p style="color:var(--text-dim);font-size:13px;margin-top:8px;">请登录收件邮箱查看测试邮件</p>`);
    } else {
      showModal('邮件发送失败',
        `<p style="color:var(--orange-alert);">✗ ${d.message}</p>` +
        `<p style="color:var(--text-dim);font-size:13px;margin-top:8px;">请检查 config/settings.py 中的 EMAIL_CONFIG 配置</p>`);
    }
  });
}

document.addEventListener('click', e => {
  if (e.target.id === 'globalModal') closeModal();
});
