# v4 Section HTML 生成参考

> 本文档从原始模板提取各 section 的 HTML 结构，供 LLM 生成内容时参考。
> **关键原则：保留原始 CSS class 和结构，只替换内容数据。**

## ★★★ sections JSON 转义规范（必读，否则 JSON 解析必失败）★★★

sections JSON 文件本质是 **JSON 格式**，所有 HTML 内容都是 JSON 字符串值。
HTML 标签属性中的双引号 `"` 在 JSON 中**必须转义为 `\"`**，否则 JSON 解析必然失败。

### 什么情况需要转义？

**凡是 HTML 标签属性用了双引号的地方，在 sections JSON 中都必须转义。**

| 场景 | 错误写法（JSON 解析失败） | 正确写法（JSON 解析通过） |
|------|--------------------------|--------------------------|
| HTML class 属性 | `"sec01": "<div class="callout">` | `"sec01": "<div class=\"callout\">` |
| HTML id 属性 | `"sec02": "<div id="chart-revenue-trend">` | `"sec02": "<div id=\"chart-revenue-trend\">` |
| HTML href 属性 | `"footer": "<a href="https://...">` | `"footer": "<a href=\"https://...\">"` |
| HTML style 属性 | `"sec03": "<div style="width:100%">` | `"sec03": "<div style=\"width:100%\">"` |
| HTML data 属性 | `"sec04": "<div data-chart="bar">` | `"sec04": "<div data-chart=\"bar\">"` |

### 高频出错位置（根据历史 bug 统计）

1. **callout-title 标签**（最常出错）：
   ```json
   ❌ 错误: "<div class="callout-title">指引点评</div>"
   ✅ 正确: "<div class=\"callout-title\">指引点评</div>"
   ```

2. **图表容器 id**：
   ```json
   ❌ 错误: "<div id="chart-revenue-trend" style="width:100%;height:360px;"></div>"
   ✅ 正确: "<div id=\"chart-revenue-trend\" style=\"width:100%;height:360px;\"></div>"
   ```

3. **stat-card class**：
   ```json
   ❌ 错误: "<div class="stat-card"><div class="v">125.60 亿</div>"
   ✅ 正确: "<div class=\"stat-card\"><div class=\"v\">125.60 亿</div>"
   ```

4. **a 标签 href**：
   ```json
   ❌ 错误: "<a href="https://ir.netflix.net">ir.netflix.net</a>"
   ✅ 正确: "<a href=\"https://ir.netflix.net\">ir.netflix.net</a>"
   ```

### 转义规则总结

在 sections JSON 的 HTML 字符串值中：
- **所有 `"` → `\"`** （HTML 属性的双引号）
- **所有 `\` → `\\`** （反斜杠本身）
- 中文、数字、英文字母不需要转义
- HTML 标签的 `<` `>` `/` 不需要转义

### 验证方法

生成 sections JSON 后，在写入文件前先用 Python 验证：
```python
import json
# json_data 是你组装的 dict 对象
json_string = json.dumps(json_data, ensure_ascii=False, indent=2)
# 验证能否解析回来
json.loads(json_string)  # 不报错 = 合法
# 写入文件
with open("sections.json", "w", encoding="utf-8") as f:
    f.write(json_string)
```

**★ 强烈建议：使用 `json.dumps()` 生成 sections JSON，它会自动转义所有双引号，杜绝手动拼接的错误。**

## 可用 CSS 组件（class 速查）

| 组件 | class | 用途 |
|------|-------|------|
| 段落 | `p.lead` | 灰色大字引导段 |
| 段落 | `p` | 普通段落 |
| 标题 | `h2` | section 主标题 |
| 标题 | `h3` | 子标题 |
| 统计卡片 | `.stat-grid > .stat-card` | 4列统计卡片（.v值/.l标签/.d变化） |
| 表格 | `.table-wrap > table` | 数据表格（.num右对齐/.pos绿/.neg红） |
| 图表 | `.chart-figure` | 图表容器（.chart-title/.chart-desc/.chart-container/.chart-foot） |
| 重点框 | `.highlights-box` | 关键亮点列表 |
| 标注框 | `.callout` | 标注（.warn/.neg/.pos 变体） |
| 洞察卡 | `.insight-grid > .insight-card` | 洞察卡片网格（.icon.blue/.green/.orange/.red） |
| 风险列表 | `.risk-list > li` | 风险项（.risk-badge.high/.med/.low） |
| 时间线 | `.timeline > .timeline-item` | 时间线 |
| 术语表 | `dl.glossary > dt/dd` | 术语定义列表 |
| 引用 | `sup > a[href="#cite-N"]` | 正文引用标记 |

## 各 Section 生成规范

### header 块
```html
<header class="report-head">
  <div class="wrap">
    <div class="kicker">季度财报深度分析 · {报告日期}</div>
    <h1>{公司名} {季度} 财报深度分析</h1>
    <p class="sub">{一句话亮点摘要}</p>
    <div class="meta">报告日期：{日期}　|　财报发布：{发布日期}　|　数据来源：{来源}　|　{汇率备注}</div>
    <div class="stat-grid">
      <div class="stat-card"><div class="v">{营收}</div><div class="l">营收</div><div class="d">{YoY} YoY</div></div>
      <div class="stat-card"><div class="v">{净利润}</div><div class="l">净利润</div><div class="d {class}">{YoY} YoY</div></div>
      <div class="stat-card"><div class="v">{毛利率}</div><div class="l">毛利率</div><div class="d">{变化} pts</div></div>
      <div class="stat-card"><div class="v">{核心指标值}</div><div class="l">{核心指标标签}</div><div class="d">{变化}</div></div>
    </div>
  </div>
</header>
```

### sec01 核心摘要
**★ 不再重复 header 的 stat-grid，改用 highlights-box 展示关键亮点**
```html
<section id="sec01">
  <div class="section-num">01 / 核心摘要</div>
  <h2>核心摘要</h2>
  <p class="lead">{3-4句概述，含营收/利润/增速/核心亮点}</p>
  <div class="highlights-box">
    <h3>本季关键亮点</h3>
    <ul>
      <li>{亮点1}</li>
      <li>{亮点2}</li>
      <li>{亮点3}</li>
      <li>{亮点4}</li>
      <li>{亮点5}</li>
    </ul>
  </div>
  <div class="callout pos">
    <div class="callout-title">核心结论</div>
    <p>{核心结论段落}</p>
  </div>
</section>
```

### sec02 财务概览
**★ 必须包含完整的7行财务指标表格**
```html
<section id="sec02">
  <div class="section-num">02 / 财务概览</div>
  <h2>财务概览</h2>
  <p>{财务概览介绍}</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>财务指标</th><th class="num">本季度</th><th class="num">上季度</th><th class="num">同比</th><th class="num">环比</th></tr>
      </thead>
      <tbody>
        <tr><td>营业收入</td><td class="num">{值}</td><td class="num">{值}</td><td class="num pos">{YoY}</td><td class="num pos">{QoQ}</td></tr>
        <tr><td>毛利润</td>...</tr>
        <tr><td>营业利润</td>...</tr>
        <tr><td>净利润</td>...</tr>
        <tr><td>经营现金流</td>...</tr>
        <tr><td>资本支出</td>...</tr>
        <tr><td>自由现金流</td>...</tr>
      </tbody>
    </table>
  </div>
  <div class="chart-figure">
    <div class="chart-title">营收与净利润趋势（近8个季度）</div>
    <div class="chart-desc">{图表描述}</div>
    <div class="chart-container" id="chart-revenue-trend"></div>
    <div class="chart-foot">数据来源: {来源} · 单位: {货币}</div>
  </div>
</section>
```

### sec03 营收分析
**★ 必须包含营收构成表格（4-6行业务板块）+ 图表 + 驱动因素**
```html
<section id="sec03">
  <div class="section-num">03 / 营收分析</div>
  <h2>营收分析</h2>
  <p>{营收分析介绍}</p>
  <h3>营收构成</h3>
  <div class="table-wrap">
    <table>
      <thead><tr><th>业务板块</th><th class="num">营收</th><th class="num">占比</th><th class="num">同比</th></tr></thead>
      <tbody>
        <tr><td>{板块1}</td><td class="num">{营收}</td><td class="num">{占比}</td><td class="num pos">{YoY}</td></tr>
        <tr><td>{板块2}</td>...</tr>
        <!-- 4-6行，含合计行 -->
      </tbody>
    </table>
  </div>
  <div class="chart-figure">
    <div class="chart-title">营收构成（按业务板块）</div>
    <div class="chart-desc">{描述}</div>
    <div class="chart-container short" id="chart-revenue-mix"></div>
    <div class="chart-foot">数据来源: {来源}</div>
  </div>
  <div class="callout">
    <div class="callout-title">营收驱动因素</div>
    <p>{驱动因素分析}</p>
  </div>
</section>
```

### sec04 盈利能力分析
**★ 必须包含利润率 stat-grid + 成本结构表格**
```html
<section id="sec04">
  <div class="section-num">04 / 盈利能力</div>
  <h2>盈利能力分析</h2>
  <p>{介绍}</p>
  <div class="stat-grid">
    <div class="stat-card"><div class="l">毛利率</div><div class="v">{值}</div><div class="d {class}">{变化} pts</div></div>
    <div class="stat-card"><div class="l">营业利润率</div><div class="v">{值}</div><div class="d {class}">{变化} pts</div></div>
    <div class="stat-card"><div class="l">净利率</div><div class="v">{值}</div><div class="d {class}">{变化} pts</div></div>
    <div class="stat-card"><div class="l">ROE</div><div class="v">{值}</div><div class="d {class}">{变化} pts</div></div>
  </div>
  <div class="chart-figure">
    <div class="chart-title">利润率趋势对比</div>
    <div class="chart-desc">{描述}</div>
    <div class="chart-container" id="chart-margin-trend"></div>
    <div class="chart-foot">数据来源: {来源}</div>
  </div>
  <h3>成本结构分析</h3>
  <div class="table-wrap">
    <table>
      <thead><tr><th>成本项</th><th class="num">金额</th><th class="num">占营收比</th><th class="num">同比变动</th></tr></thead>
      <tbody>
        <tr><td>营业成本(COGS)</td>...</tr>
        <tr><td>研发费用</td>...</tr>
        <tr><td>销售与管理费用</td>...</tr>
        <tr><td>其他运营费用</td>...</tr>
      </tbody>
    </table>
  </div>
  <div class="callout {class}">
    <div class="callout-title">{标题}</div>
    <p>{盈利能力点评}</p>
  </div>
</section>
```

### sec05 资产负债与现金流
**★ 必须包含资产负债表表格 + 现金流图表 + insight-grid**
```html
<section id="sec05">
  <div class="section-num">05 / 资产负债与现金流</div>
  <h2>资产负债与现金流</h2>
  <p>{介绍}</p>
  <h3>资产负债表概要</h3>
  <div class="table-wrap">
    <table>
      <thead><tr><th>项目</th><th class="num">期末</th><th class="num">期初</th><th class="num">变动</th></tr></thead>
      <tbody>
        <tr><td>现金及等价物</td>...</tr>
        <tr><td>总资产</td>...</tr>
        <tr><td>总负债</td>...</tr>
        <tr><td>股东权益</td>...</tr>
        <tr><td>资产负债率</td>...</tr>
      </tbody>
    </table>
  </div>
  <h3>现金流分析</h3>
  <div class="chart-figure">
    <div class="chart-title">现金流结构（近4个季度）</div>
    <div class="chart-desc">{描述}</div>
    <div class="chart-container" id="chart-cashflow"></div>
    <div class="chart-foot">数据来源: {来源}</div>
  </div>
  <div class="insight-grid">
    <div class="insight-card"><div class="icon green">OCF</div><h4>经营现金流</h4><p>{分析}</p></div>
    <div class="insight-card"><div class="icon orange">CapEx</div><h4>资本支出</h4><p>{分析}</p></div>
    <div class="insight-card"><div class="icon blue">FCF</div><h4>自由现金流</h4><p>{分析}</p></div>
  </div>
</section>
```

### sec06 运营指标
**★ KPI 必须基于公司实际业务（不同行业不同指标）**
```html
<section id="sec06">
  <div class="section-num">06 / 运营指标</div>
  <h2>关键运营指标</h2>
  <p>{介绍}</p>
  <div class="stat-grid">
    <div class="stat-card"><div class="l">{KPI1标签}</div><div class="v">{值}</div><div class="d pos">{变化}</div></div>
    <!-- 4个KPI，按公司实际业务选择 -->
  </div>
  <div class="chart-figure">
    <div class="chart-title">{图表标题}</div>
    <div class="chart-desc">{描述}</div>
    <div class="chart-container tall" id="chart-kpi-trend"></div>
    <div class="chart-foot">数据来源: {来源}</div>
  </div>
  <p>{运营指标点评}</p>
</section>
```

### sec07 分部与地区
```html
<section id="sec07">
  <div class="section-num">07 / 分部与地区业绩</div>
  <h2>分部与地区业绩</h2>
  <p>{介绍}</p>
  <h3>地区营收分布</h3>
  <div class="chart-figure">
    <div class="chart-title">各地区营收占比</div>
    <div class="chart-desc">{描述}</div>
    <div class="chart-container short" id="chart-geo"></div>
    <div class="chart-foot">数据来源: {来源}</div>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>地区</th><th class="num">营收</th><th class="num">占比</th><th class="num">同比</th><th>趋势</th></tr></thead>
      <tbody>
        <!-- 4个地区行 -->
      </tbody>
    </table>
  </div>
  <div class="insight-grid">
    <div class="insight-card"><div class="icon green">+</div><h4>增长亮点地区</h4><p>{分析}</p></div>
    <div class="insight-card"><div class="icon red">!</div><h4>承压地区</h4><p>{分析}</p></div>
  </div>
</section>
```

### sec08 业绩指引
```html
<section id="sec08">
  <div class="section-num">08 / 业绩指引与展望</div>
  <h2>业绩指引与展望</h2>
  <p>{介绍}</p>
  <h3>下季度指引</h3>
  <div class="table-wrap">
    <table>
      <thead><tr><th>指标</th><th class="num">指引区间</th><th class="num">市场预期</th><th>对比</th></tr></thead>
      <tbody>
        <tr><td>营收</td>...</tr>
        <tr><td>毛利率</td>...</tr>
        <tr><td>营业利润率</td>...</tr>
        <tr><td>资本支出</td>...</tr>
      </tbody>
    </table>
  </div>
  <h3>全年指引调整</h3>
  <div class="timeline">
    <div class="timeline-item">
      <div class="tl-date">{日期}</div>
      <h4>{标题}</h4>
      <p>{内容}</p>
    </div>
    <!-- 2-3个时间线项 -->
  </div>
  <div class="callout {class}">
    <div class="callout-title">{标题}</div>
    <p>{指引点评}</p>
  </div>
</section>
```

### sec09 管理层评论
```html
<section id="sec09">
  <div class="section-num">09 / 管理层评论</div>
  <h2>管理层评论</h2>
  <p>{介绍}</p>
  <div class="callout">
    <div class="callout-title">{CEO名} · 首席执行官</div>
    <p>"{引述}"</p>
  </div>
  <div class="callout">
    <div class="callout-title">{CFO名} · 首席财务官</div>
    <p>"{引述}"</p>
  </div>
  <h3>电话会议要点</h3>
  <div class="highlights-box">
    <ul>
      <li>{要点1}</li>
      <!-- 5-6个要点 -->
    </ul>
  </div>
</section>
```

### sec10 风险因素
```html
<section id="sec10">
  <div class="section-num">10 / 风险因素</div>
  <h2>风险因素</h2>
  <p>{介绍}</p>
  <ul class="risk-list">
    <li>
      <span class="risk-badge high">高</span>
      <div class="risk-body">
        <h4>{风险标题}</h4>
        <p>{风险描述}</p>
      </div>
    </li>
    <!-- 5项风险，含 high/med/low 等级 -->
  </ul>
  <div class="callout warn">
    <div class="callout-title">风险提示</div>
    <p>{风险总结}</p>
  </div>
</section>
```

### sec11 投资观点
```html
<section id="sec11">
  <div class="section-num">11 / 投资观点</div>
  <h2>投资观点</h2>
  <p class="lead">{投资观点引导}</p>
  <div class="stat-grid">
    <div class="stat-card"><div class="l">当前股价</div><div class="v">{值}</div><div class="d {class}">{变化}</div></div>
    <div class="stat-card"><div class="l">目标价</div><div class="v">{值}</div><div class="d pos">{上行空间}</div></div>
    <div class="stat-card"><div class="l">市盈率(PE)</div><div class="v">{值}</div><div class="d">{变化}</div></div>
    <div class="stat-card"><div class="l">市值</div><div class="v">{值}</div><div class="d">{变化}</div></div>
  </div>
  <div class="insight-grid">
    <div class="insight-card"><div class="icon green">+</div><h4>看多因素</h4><p>{分析}</p></div>
    <div class="insight-card"><div class="icon red">-</div><h4>看空因素</h4><p>{分析}</p></div>
    <div class="insight-card"><div class="icon blue">i</div><h4>催化剂</h4><p>{分析}</p></div>
  </div>
  <div class="callout {class}">
    <div class="callout-title">{评级}</div>
    <p>{投资结论}</p>
  </div>
</section>
```

### sec12 附录
```html
<section id="sec12">
  <div class="section-num">12 / 附录</div>
  <h2>附录</h2>
  <h3>术语表</h3>
  <dl class="glossary">
    <dt>{术语1}</dt>
    <dd>{定义1}</dd>
    <!-- 5个术语 -->
  </dl>
  <h3>近8个季度财务数据</h3>
  <div class="chart-figure">
    <div class="chart-title">综合财务指标雷达图</div>
    <div class="chart-desc">{描述}</div>
    <div class="chart-container" id="chart-radar"></div>
    <div class="chart-foot">数据来源: {来源}</div>
  </div>
  <hr class="divider">
  <h3>数据说明</h3>
  <p>{数据说明}</p>
</section>
```

### footer 块
**★ 参考资料必须 ≥5 条，且与正文引用编号对应**
```html
<footer>
  <div class="wrap">
    <div class="footer-top">
      <h3>参考资料</h3>
      <ol class="sources">
        <li id="cite-1"><a href="{URL}">{标题}</a> · {日期}</li>
        <!-- ≥5条，id 从 cite-1 开始 -->
      </ol>
    </div>
    <div class="disclaimer">
      <p>{免责声明}</p>
      <p>本报告基于公开财务数据自动生成，仅供参考，不构成任何投资建议。投资有风险，决策需谨慎。报告中涉及的所有财务数据均来源于公开披露文件，分析师观点基于截至 {日期} 可获得的信息。</p>
    </div>
    <div class="footer-meta">
      <span>报告生成: {时间}</span>
      <span>报告版本: {版本}</span>
    </div>
  </div>
</footer>
```

## 图表 ID 约定（charts.js 使用）

| ID | 用途 | 所在 section |
|----|------|-------------|
| `chart-revenue-trend` | 营收净利润趋势 | sec02 |
| `chart-revenue-mix` | 营收构成 | sec03 |
| `chart-margin-trend` | 利润率趋势 | sec04 |
| `chart-cashflow` | 现金流结构 | sec05 |
| `chart-kpi-trend` | KPI趋势 | sec06 |
| `chart-geo` | 地区分布 | sec07 |
| `chart-radar` | 综合雷达 | sec12 |

**注意：** 图表容器 `<div class="chart-container" id="..."></div>` 必须保留，charts.js 会通过 ID 挂载 ECharts 实例。
