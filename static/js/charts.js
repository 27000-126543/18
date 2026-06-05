/* ECharts 图表通用配置 - 工业科技风 */

const CHART_BASE_OPTION = {
  backgroundColor: 'transparent',
  textStyle: {
    color: '#94a3b8',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif'
  },
  grid: { left: 50, right: 20, top: 30, bottom: 40, containLabel: true }
};

const COLOR_PALETTE = {
  cyan: '#00d4ff',
  cyanDim: 'rgba(0, 212, 255, 0.2)',
  cyanGlow: 'rgba(0, 212, 255, 0.4)',
  orange: '#ff6b35',
  orangeDim: 'rgba(255, 107, 53, 0.2)',
  green: '#10b981',
  greenDim: 'rgba(16, 185, 129, 0.2)',
  red: '#ff4444',
  redDim: 'rgba(255, 68, 68, 0.2)',
  yellow: '#f59e0b',
  blue: '#3b82f6',
  purple: '#a855f7'
};

function createRiskPieChart(domId, data) {
  const chart = echarts.init(document.getElementById(domId));
  const option = {
    ...CHART_BASE_OPTION,
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17, 28, 51, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#e2e8f0' },
      formatter: '{b}: {c} 台 ({d}%)'
    },
    legend: {
      bottom: 0,
      textStyle: { color: '#94a3b8', fontSize: 12 },
      itemGap: 20
    },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#0a1628',
        borderWidth: 2
      },
      label: {
        color: '#e2e8f0',
        fontFamily: 'monospace',
        fontSize: 12,
        formatter: '{b}\n{c}台'
      },
      labelLine: {
        lineStyle: { color: 'rgba(0, 212, 255, 0.3)' }
      },
      data: [
        { value: data.high, name: '高危', itemStyle: { color: COLOR_PALETTE.red } },
        { value: data.medium, name: '中危', itemStyle: { color: COLOR_PALETTE.orange } },
        { value: data.low, name: '低危', itemStyle: { color: COLOR_PALETTE.yellow } },
        { value: data.normal, name: '正常', itemStyle: { color: COLOR_PALETTE.green } }
      ].filter(d => d.value > 0)
    }]
  };
  chart.setOption(option);
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

function createRULBarChart(domId, data) {
  const chart = echarts.init(document.getElementById(domId));
  const xLabels = ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-100'];
  const colors = xLabels.map((_, i) => {
    if (i < 3) return COLOR_PALETTE.red;
    if (i < 6) return COLOR_PALETTE.orange;
    if (i < 8) return COLOR_PALETTE.yellow;
    return COLOR_PALETTE.green;
  });
  const option = {
    ...CHART_BASE_OPTION,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 28, 51, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#e2e8f0' },
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(0, 212, 255, 0.05)' } }
    },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.2)' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '设备数',
      nameTextStyle: { color: '#94a3b8' },
      axisLine: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.05)', type: 'dashed' } }
    },
    series: [{
      type: 'bar',
      data: data.map((v, i) => ({
        value: v,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: colors[i] },
            { offset: 1, color: colors[i] + '33' }
          ]),
          borderRadius: [3, 3, 0, 0]
        }
      })),
      barWidth: '60%',
      label: {
        show: true,
        position: 'top',
        color: '#e2e8f0',
        fontSize: 11,
        fontFamily: 'monospace'
      }
    }]
  };
  chart.setOption(option);
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

function createSensorLineChart(domId) {
  const chart = echarts.init(document.getElementById(domId));
  const option = {
    ...CHART_BASE_OPTION,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 28, 51, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#e2e8f0' }
    },
    legend: {
      top: 0,
      right: 0,
      textStyle: { color: '#94a3b8', fontSize: 12 },
      data: ['温度(℃)', '振动(mm/s)', '电流(A)']
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.2)' } },
      axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
      splitLine: { show: false }
    },
    yAxis: [
      {
        type: 'value',
        name: '温度/振动',
        nameTextStyle: { color: '#94a3b8' },
        axisLine: { show: false },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.05)', type: 'dashed' } }
      },
      {
        type: 'value',
        name: '电流',
        nameTextStyle: { color: '#94a3b8' },
        axisLine: { show: false },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '温度(℃)',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: COLOR_PALETTE.red, width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: COLOR_PALETTE.redDim },
            { offset: 1, color: 'transparent' }
          ])
        },
        data: []
      },
      {
        name: '振动(mm/s)',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: COLOR_PALETTE.cyan, width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: COLOR_PALETTE.cyanDim },
            { offset: 1, color: 'transparent' }
          ])
        },
        data: []
      },
      {
        name: '电流(A)',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: COLOR_PALETTE.green, width: 2, type: 'dashed' },
        data: []
      }
    ]
  };
  chart.setOption(option);
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

function createWOStatusChart(domId, data) {
  const chart = echarts.init(document.getElementById(domId));
  const labels = ['待分配', '进行中', '已完成', '已验证'];
  const keys = ['pending', 'in_progress', 'completed', 'verified'];
  const colors = [COLOR_PALETTE.yellow, COLOR_PALETTE.cyan, COLOR_PALETTE.green, COLOR_PALETTE.blue];
  const values = keys.map(k => data[k] || 0);

  const option = {
    ...CHART_BASE_OPTION,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 28, 51, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#e2e8f0' },
      axisPointer: { type: 'shadow' }
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.2)' } },
      axisLabel: { color: '#94a3b8', fontSize: 12 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '工单数',
      nameTextStyle: { color: '#94a3b8' },
      axisLine: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.05)', type: 'dashed' } }
    },
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({
        value: v,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: colors[i] },
            { offset: 1, color: colors[i] + '33' }
          ]),
          borderRadius: [4, 4, 0, 0]
        }
      })),
      barWidth: '50%',
      label: {
        show: true,
        position: 'top',
        color: '#e2e8f0',
        fontSize: 13,
        fontFamily: 'monospace',
        fontWeight: 'bold'
      }
    }]
  };
  chart.setOption(option);
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

function updateSensorChart(chart, data) {
  chart.setOption({
    xAxis: { data: data.times },
    series: [
      { data: data.temperature },
      { data: data.vibration },
      { data: data.current }
    ]
  });
}
