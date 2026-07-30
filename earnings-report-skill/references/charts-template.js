/**
 * ECharts 图表模板 (SVG 渲染 / 无动画 / 响应式)
 * ------------------------------------------------------------------
 * 适用于财报 HTML 报告。所有可变数据用 {{CHART_DATA_N}} 占位符标记，
 * 构建时由数据替换为 JSON 字面量。
 *
 * 关键规则（已在本模板中严格执行）：
 *   - 渲染器：echarts.init(el, null, { renderer: 'svg' })
 *   - 关闭动画：animation: false
 *   - resize：window.addEventListener('resize', fn)
 *   - 配色：从 CSS 变量读取 getComputedStyle(document.documentElement)
 *   - 移动端检测：var isMobile = window.innerWidth <= 700;
 *   - 移动端适配：字号缩小、饼图图例改底部水平、柱状图 X 轴旋转、grid 边距缩小
 *   - 双 Y 轴：每个系列显式绑定 yAxisIndex，绝不混合
 *   - Y 轴范围：不强制 min:0，根据数据范围动态计算
 *   - 整个文件用 IIFE 包裹
 *
 * 图表清单：
 *   1. 柱状图 + 折线图（双 Y 轴）：分部营收 + 增速
 *   2. 柱状图（条件颜色）：时间趋势
 *   3. 分组柱状图：实际 vs 预期
 *   4. 饼图（环形）：占比分布
 *   5. custom 范围柱 + scatter：指引区间 vs 预期
 */
(function () {
  'use strict';

  /* ============================================================
   * 0. 公共配置：CSS 变量取色 / 移动端检测 / 工具函数
   * ============================================================ */
  var rootStyle = getComputedStyle(document.documentElement);

  function cssVar(name, fallback) {
    var v = rootStyle.getPropertyValue(name);
    v = v ? v.trim() : '';
    return v || fallback;
  }

  // 调色板（全部来自 CSS 变量，带兜底值）
  var palette = {
    primary:    cssVar('--color-primary',    '#2563eb'),
    accent:     cssVar('--color-accent',     '#0ea5e9'),
    positive:   cssVar('--color-positive',   '#16a34a'),
    negative:   cssVar('--color-negative',   '#dc2626'),
    neutral:    cssVar('--color-neutral',    '#64748b'),
    text:       cssVar('--color-text',       '#1e293b'),
    textMuted:  cssVar('--color-text-muted', '#64748b'),
    grid:       cssVar('--color-grid',       '#e2e8f0'),
    surface:    cssVar('--color-surface',    '#ffffff'),
    series1:    cssVar('--color-series-1',   '#2563eb'),
    series2:    cssVar('--color-series-2',   '#0ea5e9'),
    series3:    cssVar('--color-series-3',   '#8b5cf6'),
    series4:    cssVar('--color-series-4',   '#f59e0b'),
    series5:    cssVar('--color-series-5',   '#10b981')
  };

  // 移动端检测
  var isMobile = window.innerWidth <= 700;

  // 字号工具：移动端等比缩小
  function fs(base) {
    return isMobile ? Math.round(base * 0.86) : base;
  }

  // 根据数据计算 Y 轴范围（不强制 min:0）
  function niceRange(values) {
    var min = Infinity, max = -Infinity, i, v;
    for (i = 0; i < values.length; i++) {
      v = values[i];
      if (v == null || typeof v !== 'number' || isNaN(v)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (min === Infinity) { min = 0; max = 1; }
    if (min === max) { min = min - 1; max = max + 1; }
    var pad = (max - min) * 0.1;
    return { min: +(min - pad).toFixed(2), max: +(max + pad).toFixed(2) };
  }

  // 通用 grid（移动端缩小边距）
  function makeGrid() {
    return isMobile
      ? { left: 38, right: 16, top: 34, bottom: 58, containLabel: true }
      : { left: 56, right: 28, top: 42, bottom: 48, containLabel: true };
  }

  // 通用坐标轴标签样式
  function axisLabel() {
    return { color: palette.textMuted, fontSize: fs(12) };
  }

  // 统一初始化：SVG + 无动画
  function makeChart(el) {
    return echarts.init(el, null, { renderer: 'svg' });
  }

  // 统一挂载 + resize 监听
  function render(el, option) {
    if (!el) return null;
    var chart = makeChart(el);
    chart.setOption(option);
    window.addEventListener('resize', function () { chart.resize(); });
    return chart;
  }

  /* ============================================================
   * 1. 柱状图 + 折线图（双 Y 轴）：分部营收 + 增速
   *    左轴：营收（柱，数值轴）   右轴：同比增速（折线，百分比）
   *    每个系列显式绑定 yAxisIndex，绝不混合
   * ============================================================ */
  function initSegmentRevenueChart() {
    var el = document.getElementById('chart-segment-revenue');

    // {{CHART_DATA_1}} 期望结构:
    // { categories: ['手机','HPC','IoT','汽车','其他'],
    //   revenue: [{ name:'本季', data:[120, 180, 30, 20, 15] }],
    //   growth:  [{ name:'同比增速', data:[8.5, 22.1, -3.2, 15.0, 4.4] }] }
    var data = {{CHART_DATA_1}};
    if (!el || !data) return;

    var categories = data.categories || [];
    var revSeries = data.revenue || [];
    var growSeries = data.growth || [];

    var allRev = [];
    revSeries.forEach(function (s) { allRev = allRev.concat(s.data || []); });
    var revRange = niceRange(allRev);

    var allGrow = [];
    growSeries.forEach(function (s) { allGrow = allGrow.concat(s.data || []); });
    var growRange = niceRange(allGrow);

    var series = [];
    revSeries.forEach(function (s, idx) {
      series.push({
        name: s.name,
        type: 'bar',
        yAxisIndex: 0,                 // 显式绑定左轴
        data: s.data,
        barMaxWidth: isMobile ? 18 : 30,
        itemStyle: {
          color: [palette.series1, palette.series2, palette.series3][idx % 3],
          borderRadius: [3, 3, 0, 0]
        }
      });
    });
    growSeries.forEach(function (s, idx) {
      series.push({
        name: s.name,
        type: 'line',
        yAxisIndex: 1,                 // 显式绑定右轴
        data: s.data,
        smooth: false,
        symbol: 'circle',
        symbolSize: isMobile ? 6 : 8,
        lineStyle: { width: 2, color: palette.accent },
        itemStyle: { color: palette.accent }
      });
    });

    var option = {
      animation: false,
      color: [palette.series1, palette.series2, palette.series3, palette.accent],
      grid: makeGrid(),
      legend: {
        top: 0,
        textStyle: { color: palette.textMuted, fontSize: fs(12) },
        itemWidth: fs(12),
        itemHeight: fs(12)
      },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: Object.assign({}, axisLabel(), {
          rotate: isMobile ? 45 : 0,
          interval: 0
        }),
        axisLine: { lineStyle: { color: palette.grid } },
        axisTick: { show: false }
      },
      yAxis: [
        {
          type: 'value',
          name: '营收',
          nameTextStyle: { color: palette.textMuted, fontSize: fs(11) },
          min: revRange.min,
          max: revRange.max,
          axisLabel: axisLabel(),
          splitLine: { lineStyle: { color: palette.grid } }
        },
        {
          type: 'value',
          name: '增速',
          nameTextStyle: { color: palette.textMuted, fontSize: fs(11) },
          min: growRange.min,
          max: growRange.max,
          axisLabel: Object.assign({}, axisLabel(), { formatter: '{value}%' }),
          splitLine: { show: false }
        }
      ],
      series: series
    };

    render(el, option);
  }

  /* ============================================================
   * 2. 柱状图（条件颜色）：时间趋势
   *    mode='sign'      -> 正绿负红
   *    mode='threshold' -> 高于均值用主色，低于用中性色，并画均值线
   * ============================================================ */
  function initTrendBarChart() {
    var el = document.getElementById('chart-trend-bar');

    // {{CHART_DATA_2}} 期望结构:
    // { categories: ['23Q1','23Q2','23Q3','23Q4','24Q1'],
    //   values:     [12.5, 18.2, -3.4, 25.1, 9.8],
    //   mode:       'sign' }
    var data = {{CHART_DATA_2}};
    if (!el || !data) return;

    var categories = data.categories || [];
    var values = data.values || [];
    var mode = data.mode || 'sign';

    var avg = values.length
      ? values.reduce(function (a, b) { return a + (b || 0); }, 0) / values.length
      : 0;

    var barColors = values.map(function (v) {
      if (mode === 'threshold') {
        return v >= avg ? palette.primary : palette.neutral;
      }
      return v >= 0 ? palette.positive : palette.negative;
    });

    var range = niceRange(values);

    var series = [{
      type: 'bar',
      barMaxWidth: isMobile ? 16 : 28,
      data: values.map(function (v, i) {
        return { value: v, itemStyle: { color: barColors[i] } };
      })
    }];

    if (mode === 'threshold') {
      series[0].markLine = {
        symbol: 'none',
        lineStyle: { color: palette.textMuted, type: 'dashed' },
        label: { color: palette.textMuted, fontSize: fs(10) },
        data: [{ yAxis: avg, name: '均值' }]
      };
    }

    var option = {
      animation: false,
      grid: makeGrid(),
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: Object.assign({}, axisLabel(), {
          rotate: isMobile ? 45 : 0,
          interval: isMobile ? 0 : 'auto'
        }),
        axisLine: { lineStyle: { color: palette.grid } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        min: range.min,
        max: range.max,
        axisLabel: axisLabel(),
        splitLine: { lineStyle: { color: palette.grid } }
      },
      series: series
    };

    render(el, option);
  }

  /* ============================================================
   * 3. 分组柱状图：实际 vs 预期
   * ============================================================ */
  function initActualVsExpectedChart() {
    var el = document.getElementById('chart-actual-vs-expected');

    // {{CHART_DATA_3}} 期望结构:
    // { categories: ['营收','毛利率','EPS','资本开支'],
    //   actual:    [185, 53.2, 1.44, 78],
    //   expected:  [183, 52.8, 1.40, 82],
    //   unit:      '亿/%' }
    var data = {{CHART_DATA_3}};
    if (!el || !data) return;

    var categories = data.categories || [];
    var actual = data.actual || [];
    var expected = data.expected || [];

    var range = niceRange(actual.concat(expected));

    var option = {
      animation: false,
      color: [palette.primary, palette.neutral],
      grid: makeGrid(),
      legend: {
        top: 0,
        textStyle: { color: palette.textMuted, fontSize: fs(12) },
        itemWidth: fs(12),
        itemHeight: fs(12)
      },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: Object.assign({}, axisLabel(), {
          rotate: isMobile ? 35 : 0,
          interval: 0
        }),
        axisLine: { lineStyle: { color: palette.grid } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        name: data.unit || '',
        nameTextStyle: { color: palette.textMuted, fontSize: fs(11) },
        min: range.min,
        max: range.max,
        axisLabel: axisLabel(),
        splitLine: { lineStyle: { color: palette.grid } }
      },
      series: [
        {
          name: '实际',
          type: 'bar',
          data: actual,
          barMaxWidth: isMobile ? 14 : 26,
          itemStyle: { color: palette.primary, borderRadius: [3, 3, 0, 0] }
        },
        {
          name: '预期',
          type: 'bar',
          data: expected,
          barMaxWidth: isMobile ? 14 : 26,
          itemStyle: { color: palette.neutral, borderRadius: [3, 3, 0, 0] }
        }
      ]
    };

    render(el, option);
  }

  /* ============================================================
   * 4. 饼图（环形）：占比分布
   *    移动端：图例移至底部水平排列、半径与中心点上移
   * ============================================================ */
  function initDonutChart() {
    var el = document.getElementById('chart-donut');

    // {{CHART_DATA_4}} 期望结构:
    // [{ name:'HPC', value:52 }, { name:'手机', value:38 },
    //  { name:'IoT', value:5 },  { name:'其他', value:5 }]
    var data = {{CHART_DATA_4}};
    if (!el || !data) return;

    var pieColors = [
      palette.series1, palette.series2, palette.series3,
      palette.series4, palette.series5, palette.neutral
    ];

    var legendConf = isMobile
      ? {
          bottom: 0, left: 'center', orient: 'horizontal',
          textStyle: { color: palette.textMuted, fontSize: fs(11) },
          itemWidth: fs(10), itemHeight: fs(10)
        }
      : {
          top: 'middle', right: 8, orient: 'vertical',
          textStyle: { color: palette.textMuted, fontSize: fs(12) },
          itemWidth: fs(12), itemHeight: fs(12)
        };

    var option = {
      animation: false,
      color: pieColors,
      legend: legendConf,
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      series: [{
        type: 'pie',
        radius: isMobile ? ['38%', '62%'] : ['52%', '72%'],
        center: isMobile ? ['50%', '42%'] : ['38%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: palette.surface, borderWidth: 2 },
        label: {
          show: !isMobile,
          color: palette.text,
          fontSize: fs(12),
          formatter: '{d}%'
        },
        labelLine: { show: !isMobile },
        data: data
      }]
    };

    render(el, option);
  }

  /* ============================================================
   * 5. custom 范围柱 + scatter：指引区间 vs 预期
   *    范围柱：管理层指引的低~高区间（custom rect）
   *    scatter：实际值（圆点）/ 一致预期（菱形）
   * ============================================================ */
  function initGuidanceRangeChart() {
    var el = document.getElementById('chart-guidance-range');

    // {{CHART_DATA_5}} 期望结构:
    // { categories: ['25Q4 营收','25Q4 毛利率','25Q4 EPS'],
    //   ranges:    [{ low: 180, high: 188 }, { low: 53.0, high: 55.0 }, { low: 1.38, high: 1.50 }],
    //   actual:    [185, 53.6, 1.44],
    //   consensus: [183, 53.2, 1.41] }
    var data = {{CHART_DATA_5}};
    if (!el || !data) return;

    var categories = data.categories || [];
    var ranges = data.ranges || [];
    var actual = data.actual || [];
    var consensus = data.consensus || [];

    var allVals = [];
    ranges.forEach(function (r) { if (r) { allVals.push(r.low, r.high); } });
    allVals = allVals.concat(actual).concat(consensus);
    var range = niceRange(allVals);

    // custom 范围柱渲染函数
    var renderItem = function (params, api) {
      var catIdx = api.value(0);
      var low = api.value(1);
      var high = api.value(2);
      var start = api.coord([catIdx, low]);
      var end = api.coord([catIdx, high]);
      var bandWidth = api.size([1, 0])[0] * 0.42;

      return {
        type: 'rect',
        shape: {
          x: start[0] - bandWidth / 2,
          y: end[1],
          width: bandWidth,
          height: start[1] - end[1]
        },
        style: { fill: palette.primary, opacity: 0.28 }
      };
    };

    var customData = categories.map(function (_, i) {
      var r = ranges[i] || {};
      return [i, r.low, r.high];
    });

    var option = {
      animation: false,
      grid: makeGrid(),
      legend: {
        top: 0,
        data: ['指引区间', '实际值', '一致预期'],
        textStyle: { color: palette.textMuted, fontSize: fs(12) },
        itemWidth: fs(12),
        itemHeight: fs(12)
      },
      tooltip: {
        trigger: 'axis',
        formatter: function (p) {
          var i = p[0].dataIndex;
          var r = ranges[i] || {};
          var lines = [p[0].axisValue];
          lines.push('指引区间: ' + (r.low == null ? '-' : r.low) + ' ~ ' + (r.high == null ? '-' : r.high));
          if (actual[i] != null) lines.push('实际值: ' + actual[i]);
          if (consensus[i] != null) lines.push('一致预期: ' + consensus[i]);
          return lines.join('<br/>');
        }
      },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: Object.assign({}, axisLabel(), {
          rotate: isMobile ? 35 : 0,
          interval: 0
        }),
        axisLine: { lineStyle: { color: palette.grid } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        min: range.min,
        max: range.max,
        axisLabel: axisLabel(),
        splitLine: { lineStyle: { color: palette.grid } }
      },
      series: [
        {
          name: '指引区间',
          type: 'custom',
          renderItem: renderItem,
          encode: { x: 0, y: [1, 2] },
          data: customData,
          z: 1
        },
        {
          name: '实际值',
          type: 'scatter',
          data: actual.map(function (v, i) { return [i, v]; }),
          symbolSize: isMobile ? 9 : 12,
          itemStyle: { color: palette.positive },
          z: 3
        },
        {
          name: '一致预期',
          type: 'scatter',
          symbol: 'diamond',
          data: consensus.map(function (v, i) { return [i, v]; }),
          symbolSize: isMobile ? 9 : 12,
          itemStyle: { color: palette.negative },
          z: 3
        }
      ]
    };

    render(el, option);
  }

  /* ============================================================
   * 启动
   * ============================================================ */
  function initAll() {
    initSegmentRevenueChart();
    initTrendBarChart();
    initActualVsExpectedChart();
    initDonutChart();
    initGuidanceRangeChart();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
