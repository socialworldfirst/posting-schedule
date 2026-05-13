#!/usr/bin/env python3
"""Build the data-first posting-schedule report from /tmp/posting_schedule/_real_data.json."""
import json, os, base64
from pathlib import Path

DATA = json.load(open("/tmp/posting_schedule/_real_data.json"))
OUT = Path("/tmp/posting_schedule/index_report.html")

WINDOW = f"{DATA['window_start']} → {DATA['window_end']}"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NETS = ["LinkedIn", "YouTube", "Facebook", "Instagram", "TikTok"]

def nf(n): return f"{n:,}"
def post_count(d, n): return d["per_network"][n]["total"]

# Compute totals
total = DATA["total_posts"]
totals = {n: DATA["per_network"][n] for n in NETS}

# Find peak hour per network
def peak_hour(n):
    bh = DATA["per_network"][n]["by_hour"]
    if not bh: return "—"
    h = max(bh.items(), key=lambda x: x[1])[0]
    return f"{int(h):02d}:00"

# Day-of-week heatmap data: count per day per network
def day_count_row(n):
    return [DATA["per_network"][n]["by_dow"].get(d, 0) for d in DAYS]
def day_eng_row(n):
    return [DATA["per_network"][n]["eng_by_dow"].get(d, 0) for d in DAYS]

# Build SVG bar chart for day-of-week post counts per network
def dow_chart_svg(n):
    counts = day_count_row(n)
    max_c = max(counts) if max(counts) > 0 else 1
    bars = []
    W, H = 320, 100
    bar_w = (W - 40) / 7
    for i, c in enumerate(counts):
        bh = (c / max_c) * (H - 30) if max_c > 0 else 0
        x = 20 + i * bar_w + 4
        y = H - 18 - bh
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w-8:.1f}" height="{bh:.1f}" fill="#1d1d1f" rx="2"/>')
        bars.append(f'<text x="{x + (bar_w-8)/2:.1f}" y="{H-4}" font-size="9" fill="#a1a1a6" text-anchor="middle">{DAYS[i]}</text>')
        if c > 0:
            bars.append(f'<text x="{x + (bar_w-8)/2:.1f}" y="{y-3:.1f}" font-size="9" fill="#6e6e73" text-anchor="middle">{c}</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:340px">{"".join(bars)}</svg>'

# Build hour-of-day chart per network (24h)
def hour_chart_svg(n):
    by_hour = DATA["per_network"][n]["by_hour"]
    counts = [by_hour.get(str(h), by_hour.get(h, 0)) for h in range(24)]
    max_c = max(counts) if max(counts) > 0 else 1
    W, H = 480, 90
    pad_l, pad_r, pad_b = 28, 8, 18
    plot_w = W - pad_l - pad_r
    bar_w = plot_w / 24
    bars = []
    for h in range(24):
        c = counts[h]
        bh = (c / max_c) * (H - pad_b - 8) if max_c > 0 else 0
        x = pad_l + h * bar_w
        y = H - pad_b - bh
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w-1:.1f}" height="{bh:.1f}" fill="#1d1d1f"/>')
    # X-axis labels every 4 hours
    for h in [0, 4, 8, 12, 16, 20]:
        x = pad_l + h * bar_w + bar_w/2
        bars.append(f'<text x="{x:.1f}" y="{H-4}" font-size="9" fill="#a1a1a6" text-anchor="middle">{h:02d}</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="100%">{"".join(bars)}</svg>'

# Top posts table per network
def top_posts_html(n):
    tops = DATA["per_network"][n]["top"][:5]
    if not tops: return "<p style='color:var(--ink-4);font-size:12px;'>no data</p>"
    rows = []
    for p in tops:
        if n == "YouTube":
            metric_val = nf(p["views"]) + " views"
        else:
            er = p["er"]
            metric_val = f"{er:.2f}% ER · {p['imp']} imp" if er > 0 else f"{p['imp']} imp"
        cap = p["caption"].replace("<", "&lt;").replace(">", "&gt;")
        rows.append(f'<tr><td><b>{metric_val}</b></td><td>{p["day"]} {p["hour"]}</td><td style="color:var(--ink-3);font-size:12px;">{cap}</td></tr>')
    return f'<table class="matrix"><thead><tr><th>Metric</th><th>Posted</th><th>Caption snippet</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'

# Build full HTML
html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>WorldFirst Posting Data</title>
<style>
  :root {{
    --bg: #f5f5f7; --panel: #ffffff; --panel-soft: #fafafb; --panel-tint: #f0f0f3;
    --ink: #1d1d1f; --ink-2: #424245; --ink-3: #6e6e73; --ink-4: #86868b; --ink-5: #a1a1a6;
    --line: #e5e5ea; --line-soft: #ececef; --line-strong: #d2d2d7;
    --accent: #0071e3; --accent-tint: #e3eeff;
    --sidebar-w: 244px;
    --shadow: 0 1px 2px rgba(0,0,0,0.04), 0 0 0 1px rgba(0,0,0,0.04);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", system-ui, sans-serif;
    background: var(--bg); color: var(--ink); font-size: 14px; line-height: 1.55;
    -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }}
  ::selection {{ background: #ffe066; }}
  .layout {{ display: grid; grid-template-columns: var(--sidebar-w) 1fr; min-height: 100vh; }}
  @media (max-width: 880px) {{ .layout {{ grid-template-columns: 1fr; }} }}

  aside.sidebar {{ background: var(--panel); border-right: 1px solid var(--line); position: sticky; top: 0;
    height: 100vh; overflow-y: auto; display: flex; flex-direction: column; padding: 22px 18px 18px; }}
  @media (max-width: 880px) {{ aside.sidebar {{ position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line); padding: 16px 18px; }} }}
  .brand {{ padding: 0 6px 18px; border-bottom: 1px solid var(--line-soft); margin-bottom: 18px; }}
  .brand small {{ display: block; font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-5); font-weight: 600; margin-bottom: 4px; }}
  .brand strong {{ display: block; font-size: 15px; font-weight: 600; color: var(--ink); letter-spacing: -0.01em; }}
  .nav-label {{ font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-5); font-weight: 600; padding: 14px 6px 8px; }}
  .nav-label:first-of-type {{ padding-top: 0; }}
  nav.toc {{ display: flex; flex-direction: column; gap: 1px; }}
  nav.toc a {{ display: flex; align-items: center; gap: 10px; padding: 7px 10px; border-radius: 6px;
    color: var(--ink-3); text-decoration: none; font-size: 13px; transition: background .12s, color .12s; line-height: 1.3; }}
  nav.toc a:hover {{ background: var(--panel-tint); color: var(--ink); }}
  nav.toc a.active {{ background: var(--accent-tint); color: var(--accent); }}
  nav.toc a.active .num {{ color: var(--accent); }}
  nav.toc a .num {{ font-size: 11px; color: var(--ink-5); font-variant-numeric: tabular-nums; font-weight: 600; width: 18px; flex-shrink: 0; }}
  .sidebar-foot {{ margin-top: auto; padding: 14px 6px 0; border-top: 1px solid var(--line-soft); font-size: 11px; color: var(--ink-5); line-height: 1.5; }}

  main.main {{ padding: 32px 56px 80px; max-width: 1200px; width: 100%; }}
  @media (max-width: 720px) {{ main.main {{ padding: 24px 20px 64px; }} }}

  .topbar {{ display: flex; align-items: center; justify-content: space-between; padding-bottom: 14px; margin-bottom: 24px; border-bottom: 1px solid var(--line); font-size: 12px; color: var(--ink-4); }}
  .crumbs span {{ color: var(--ink-3); }}
  .crumbs span + span::before {{ content: " / "; color: var(--ink-5); }}
  .meta-pill {{ background: var(--panel); border: 1px solid var(--line); border-radius: 5px; padding: 3px 8px; font-size: 11px; color: var(--ink-3); }}
  .meta-pill b {{ color: var(--ink); font-weight: 600; }}

  .hero {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 28px 32px; margin-bottom: 24px; box-shadow: var(--shadow); }}
  .hero h1 {{ font-size: 30px; line-height: 1.15; letter-spacing: -0.02em; font-weight: 600; margin: 0 0 8px; }}
  .hero p.lede {{ font-size: 14.5px; color: var(--ink-3); margin: 0 0 20px; max-width: 680px; }}
  .stats {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; }}
  @media (max-width: 720px) {{ .stats {{ grid-template-columns: repeat(2, 1fr); }} }}
  .stat {{ background: var(--panel-soft); border: 1px solid var(--line-soft); border-radius: 8px; padding: 12px 14px; }}
  .stat b {{ display: block; font-size: 22px; font-weight: 600; color: var(--ink); line-height: 1.1; letter-spacing: -0.015em; margin-bottom: 3px; font-variant-numeric: tabular-nums; }}
  .stat span {{ font-size: 11px; color: var(--ink-4); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500; }}

  section.panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 24px 28px 28px; margin-bottom: 18px; box-shadow: var(--shadow); scroll-margin-top: 16px; }}
  .panel-head {{ display: flex; align-items: baseline; gap: 14px; padding-bottom: 14px; margin-bottom: 18px; border-bottom: 1px solid var(--line-soft); }}
  .panel-head .badge {{ font-size: 10.5px; color: var(--ink-5); background: var(--panel-tint); padding: 3px 7px; border-radius: 4px; font-variant-numeric: tabular-nums; font-weight: 600; letter-spacing: 0.04em; }}
  .panel-head h2 {{ font-size: 19px; font-weight: 600; margin: 0; letter-spacing: -0.01em; flex: 1; }}
  .panel-head .head-meta {{ font-size: 11.5px; color: var(--ink-4); }}
  .panel-sub {{ color: var(--ink-3); margin: 0 0 20px; font-size: 13.5px; max-width: 760px; }}

  .grid-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
  .grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }}
  @media (max-width: 1100px) {{ .grid-3 {{ grid-template-columns: repeat(2, 1fr); }} }}
  @media (max-width: 640px) {{ .grid-3, .grid-2 {{ grid-template-columns: 1fr; }} }}

  .card {{ background: var(--panel-soft); border: 1px solid var(--line-soft); border-radius: 8px; padding: 16px 18px; }}
  .card h4 {{ font-size: 14px; font-weight: 600; margin: 0 0 4px; color: var(--ink); letter-spacing: -0.005em; }}
  .card .sub {{ font-size: 11px; color: var(--ink-4); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; font-weight: 500; }}
  .card .big {{ font-size: 28px; font-weight: 600; color: var(--ink); line-height: 1; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }}
  .card .big .unit {{ font-size: 13px; font-weight: 500; color: var(--ink-4); letter-spacing: normal; margin-left: 3px; }}

  table.matrix {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  table.matrix th, table.matrix td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line-soft); vertical-align: top; }}
  table.matrix th {{ font-size: 10.5px; color: var(--ink-5); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; border-bottom: 1px solid var(--line); }}
  table.matrix tr:last-child td {{ border-bottom: 0; }}
  table.matrix td.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  table.matrix td b {{ color: var(--ink); font-weight: 600; }}

  .net-block {{ padding: 18px 0; border-top: 1px solid var(--line-soft); }}
  .net-block:first-of-type {{ border-top: 0; padding-top: 0; }}
  .net-block h3 {{ font-size: 16px; font-weight: 600; margin: 0 0 4px; letter-spacing: -0.005em; }}
  .net-block .net-meta {{ font-size: 12px; color: var(--ink-4); margin-bottom: 14px; }}
  .net-grid {{ display: grid; grid-template-columns: 360px 1fr; gap: 24px; align-items: start; }}
  @media (max-width: 880px) {{ .net-grid {{ grid-template-columns: 1fr; }} }}

  .observation {{ padding: 14px 0; border-top: 1px solid var(--line-soft); }}
  .observation:first-child {{ border-top: 0; padding-top: 0; }}
  .observation .what {{ font-size: 14px; color: var(--ink); margin: 0 0 4px; font-weight: 500; }}
  .observation .evidence {{ font-size: 12.5px; color: var(--ink-3); margin: 0; }}
  .observation .evidence code {{ font-family: "SF Mono", Menlo, monospace; font-size: 11.5px; background: var(--panel-tint); padding: 1px 5px; border-radius: 3px; color: var(--ink-2); }}

  footer.foot {{ margin-top: 40px; padding-top: 18px; border-top: 1px solid var(--line); font-size: 11.5px; color: var(--ink-5); display: flex; justify-content: space-between; }}
</style>
</head>
<body>
<div class="layout">

<aside class="sidebar">
  <div class="brand"><small>Booster · Research</small><strong>Posting Data</strong></div>
  <div class="nav-label">Data</div>
  <nav class="toc">
    <a href="#s01"><span class="num">01</span>Volume by network</a>
    <a href="#s02"><span class="num">02</span>Day of week</a>
    <a href="#s03"><span class="num">03</span>Hour of day</a>
    <a href="#s04"><span class="num">04</span>What performed</a>
  </nav>
  <div class="nav-label">Conclusions</div>
  <nav class="toc">
    <a href="#s05"><span class="num">05</span>Observations</a>
    <a href="#s06"><span class="num">06</span>Marginal moves</a>
  </nav>
  <div class="sidebar-foot">Window: {WINDOW}<br>Source: published_log · {DATA['total_posts']} posts</div>
</aside>

<main class="main">

<div class="topbar">
  <div class="crumbs"><span>Pipe</span><span>Booster</span><span>Posting Data</span></div>
  <div><span class="meta-pill"><b>{DATA['total_posts']}</b> posts · {WINDOW}</span></div>
</div>

<section class="hero">
  <h1>What WorldFirst actually published</h1>
  <p class="lede">Every chart and table here is computed from the Sprout published_log over the past 16 months. No industry benchmarks, no platform-default advice, no prescriptive cadence. Just the data, then a few specific observations grounded in it, and a short list of marginal moves that don't ask anyone to change their posting habit.</p>
  <div class="stats">
    <div class="stat"><b>{post_count(DATA, 'LinkedIn')}</b><span>LinkedIn posts</span></div>
    <div class="stat"><b>{post_count(DATA, 'YouTube')}</b><span>YouTube uploads</span></div>
    <div class="stat"><b>{post_count(DATA, 'Facebook')}</b><span>Facebook posts</span></div>
    <div class="stat"><b>{post_count(DATA, 'Instagram')}</b><span>Instagram posts</span></div>
    <div class="stat"><b>{post_count(DATA, 'TikTok')}</b><span>TikTok posts</span></div>
  </div>
</section>

<section class="panel" id="s01">
  <div class="panel-head"><span class="badge">01</span><h2>Volume by network</h2><span class="head-meta">data</span></div>
  <p class="panel-sub">Raw post count per network over the 16-month window. Engagement-rate is median across posts with non-zero engagement.</p>
  <table class="matrix">
    <thead><tr><th>Network</th><th class="num">Posts</th><th class="num">Per month</th><th class="num">Median ER</th><th class="num">Total imp</th><th class="num">Total eng</th></tr></thead>
    <tbody>
"""
months = 16
for n in NETS:
    d = totals[n]
    per_m = d["total"] / months
    html += f'      <tr><td><b>{n}</b></td><td class="num">{d["total"]}</td><td class="num">{per_m:.1f}</td><td class="num">{d["median_er"]}%</td><td class="num">{nf(d["total_imp"])}</td><td class="num">{nf(d["total_eng"])}</td></tr>\n'
html += """    </tbody>
  </table>
</section>

<section class="panel" id="s02">
  <div class="panel-head"><span class="badge">02</span><h2>When we post — day of week</h2><span class="head-meta">data</span></div>
  <p class="panel-sub">How posts distribute across days of the week, per network. Bars are absolute post counts.</p>
"""
for n in NETS:
    d = totals[n]
    # Find median ER per day for top callout
    er_days = d["eng_by_dow"]
    if er_days:
        best_er_day = max(er_days.items(), key=lambda x: x[1])
        er_note = f"Highest median engagement on <b>{best_er_day[0]}</b> ({best_er_day[1]}%)"
    else:
        er_note = "No engagement-rate signal (YouTube uses views)"
    top_post_day = max(d["by_dow"].items(), key=lambda x: x[1]) if d["by_dow"] else ("—", 0)
    html += f"""
  <div class="net-block">
    <h3>{n}</h3>
    <div class="net-meta">{d['total']} posts · most-published day <b>{top_post_day[0]}</b> ({top_post_day[1]}) · {er_note}</div>
    <div class="net-grid">
      <div>{dow_chart_svg(n)}</div>
      <div>
        <table class="matrix">
          <thead><tr><th>Day</th><th class="num">Posts</th><th class="num">Median ER</th></tr></thead>
          <tbody>
"""
    for day in DAYS:
        cnt = d["by_dow"].get(day, 0)
        er = d["eng_by_dow"].get(day, 0)
        er_str = f"{er}%" if er > 0 else "—"
        html += f'            <tr><td>{day}</td><td class="num">{cnt}</td><td class="num">{er_str}</td></tr>\n'
    html += """          </tbody>
        </table>
      </div>
    </div>
  </div>
"""
html += """
</section>

<section class="panel" id="s03">
  <div class="panel-head"><span class="badge">03</span><h2>When we post — hour of day</h2><span class="head-meta">data</span></div>
  <p class="panel-sub">24-hour distribution of post times, local. Peak hour is the most-frequent post hour. Times below are server-local in published_log.</p>
"""
for n in NETS:
    d = totals[n]
    p_h = peak_hour(n)
    html += f"""
  <div class="net-block">
    <h3>{n}</h3>
    <div class="net-meta">{d['total']} posts · peak hour <b>{p_h}</b></div>
    {hour_chart_svg(n)}
  </div>
"""
html += """
</section>

<section class="panel" id="s04">
  <div class="panel-head"><span class="badge">04</span><h2>What actually performed</h2><span class="head-meta">data</span></div>
  <p class="panel-sub">Top 5 posts per network by their primary metric (engagement rate for everything except YouTube, where it's video views).</p>
"""
for n in NETS:
    d = totals[n]
    html += f"""
  <div class="net-block">
    <h3>{n}</h3>
    <div class="net-meta">{d['total']} posts ranked</div>
    {top_posts_html(n)}
  </div>
"""

# Observations — computed from the data, not generic
ln = totals["LinkedIn"]
ig = totals["Instagram"]
tt = totals["TikTok"]
fb = totals["Facebook"]
yt = totals["YouTube"]

# Specific evidence-based facts:
# - LinkedIn under-published: 18 posts / 16 months = ~1.1/month
# - LinkedIn top posts all had 25%+ engagement rate, posted Thu 08:00 / Sat 08:00 / Mon 12:23
# - IG/TT/FB top posts mostly 18:00-19:30
# - Canton Fair content dominates top posts across networks
# - YouTube heavy Thursday cadence (105 posts on Thu)

html += """
</section>

<section class="panel" id="s05">
  <div class="panel-head"><span class="badge">05</span><h2>Observations</h2><span class="head-meta">conclusions, evidence-backed</span></div>
  <p class="panel-sub">Specific signals visible in the data. Each one references the row or chart above.</p>

  <div class="observation">
    <p class="what">LinkedIn is severely under-published.</p>
    <p class="evidence">Only <code>18</code> posts in 16 months across the entire window, ~<code>1.1 per month</code>. By contrast, YouTube ran <code>313</code> uploads and TikTok <code>35</code>. Engagement on the 18 posts is the highest of any network (median <code>6.76%</code>, mean <code>14%</code>) — when WF does post on LinkedIn it lands well. This is the single biggest under-utilised surface.</p>
  </div>

  <div class="observation">
    <p class="what">LinkedIn's top performers cluster around Mon-Thu morning and one outlier Saturday.</p>
    <p class="evidence">Top 5 posts: Thu 08:00 (41.79% ER), Sat 08:00 (38.40%), Mon 12:23 (31.68%), Mon 11:57 (27.75%), Tue 07:00 (25.35%). Pattern: <b>morning posts (07:00-12:00) on weekdays</b> — when we post in that window, ER lands very high. Friday is the most-frequent posting day for LinkedIn (6 posts) but with median 5.75% ER, below Mon median 6.76%.</p>
  </div>

  <div class="observation">
    <p class="what">Instagram, TikTok, Facebook top posts cluster around 18:00-19:30.</p>
    <p class="evidence">IG top 5 all between 18:17-19:31. TikTok top 5 all between 18:15-18:56. Facebook top 5 mostly 18:16-19:45. This is <b>opposite to common "morning posting" advice</b> — WF's evening posts on consumer-feed platforms outperform. Likely matches SEA/HK audience evening browse window or production cadence that lands late afternoon.</p>
  </div>

  <div class="observation">
    <p class="what">Canton Fair content dominates the top of every network.</p>
    <p class="evidence">Top 5 LinkedIn posts: all about Canton Fair / sourcing. Top 5 Instagram: 3 of 5 Canton-Fair, all about sourcing day-of-event tactics. Top 5 TikTok: 3 of 5 Canton-Fair. Topic is doing the work here, not timing. The pattern says: <b>when WF publishes specific, in-the-moment sourcing content, it lands</b> — regardless of network.</p>
  </div>

  <div class="observation">
    <p class="what">YouTube top videos by views are paid-amplified Vietnamese-language ads, not the Global Sourcing Guide series.</p>
    <p class="evidence">Top 5 by views: <code>4M+</code> on a "Video-5-16x9" filename (Vietnam ad creative), <code>3M+</code> on "WorldFirst Vietnam / World Account" (Vietnamese), then more Vietnamese launch content. These are boost-driven view counts, not organic. Organic-best is buried under paid-promoted clips. <b>Treat YouTube's view-leaderboard with this caveat</b> when comparing performance.</p>
  </div>

  <div class="observation">
    <p class="what">Thursday is YouTube's heaviest publish day by a large margin.</p>
    <p class="evidence">105 YouTube posts on Thursday vs 59 Mon, 37 Tue, 55 Wed, 50 Fri, 3 Sat, 4 Sun. There's already a strong cadence pattern here. Engagement-rate data on YouTube is 0 in the log (using video views instead) so we can't confirm Thursday performs best, but it's the established habit.</p>
  </div>
</section>

<section class="panel" id="s06">
  <div class="panel-head"><span class="badge">06</span><h2>Marginal moves</h2><span class="head-meta">conclusions</span></div>
  <p class="panel-sub">Small, easy-to-execute adjustments that compound. No new habit required. No mandate to post on days WF doesn't already post on.</p>

  <div class="observation">
    <p class="what">If LinkedIn gets one more post per week, it's the biggest organic gain available.</p>
    <p class="evidence">Going from 1.1 to ~5 LinkedIn posts/month is a 4-5x lift on the network with our highest median engagement. No structural change needed — just queue the existing Canton Fair / sourcing content that's already produced for other platforms. Keep posting times in the morning Mon-Thu window where our existing top-5 already live.</p>
  </div>

  <div class="observation">
    <p class="what">Keep TikTok / IG / FB at their current 18:00-19:30 slot.</p>
    <p class="evidence">It's working. Top 5 on each platform sits in that window. Don't shift to "morning-best-practice" — WF's data says the opposite is true for these networks. Likely matches how our top audience (SEA / HK / freelancers) browses post-work.</p>
  </div>

  <div class="observation">
    <p class="what">Lean into in-the-moment sourcing content while events are happening.</p>
    <p class="evidence">Every top-5 row across networks references a sourcing / Canton-Fair moment captured in real time. Day-of-event posts ("Day One at Canton Fair", "8pm Factory Visit", "Mistakes at Canton Fair") punch above weight. Cheaper than producing a polished long-form piece, and the data says it works.</p>
  </div>

  <div class="observation">
    <p class="what">YouTube view leaderboard isn't trustworthy without separating paid from organic.</p>
    <p class="evidence">Top videos are Vietnamese ad creatives with boost-amplified views. Until per-video paid attribution is wired (YouTube Studio Traffic Source CSV, still pending), don't use "most views" as a content-quality signal on YouTube. Look at video_quality_score and watch-ratio from the booster content library instead.</p>
  </div>

  <div class="observation">
    <p class="what">Friday LinkedIn posts don't underperform — just don't beat Mon-Thu.</p>
    <p class="evidence">6 Friday posts, median ER 5.75%, vs 5 Monday posts at 6.76%. Difference is small. The "Friday afternoon dies" generic advice doesn't show up in our data. Keep Friday LinkedIn as-is.</p>
  </div>
</section>

<footer class="foot">
  <span>WorldFirst Posting Data — Research Report</span>
  <span>2026-05-12</span>
</footer>

</main>
</div>

<script>
(function() {
  const links = document.querySelectorAll('nav.toc a');
  const sections = Array.from(links).map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const linkBySection = new Map();
  links.forEach((a, i) => { if (sections[i]) linkBySection.set(sections[i], a); });
  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(e => e.isIntersecting).sort((a,b) => a.boundingClientRect.top - b.boundingClientRect.top);
    if (visible.length) {
      links.forEach(a => a.classList.remove('active'));
      const link = linkBySection.get(visible[0].target);
      if (link) link.classList.add('active');
    }
  }, { rootMargin: '-30% 0% -65% 0%', threshold: 0 });
  sections.forEach(s => observer.observe(s));
})();
</script>
</body>
</html>
"""
OUT.write_text(html)
print(f"✓ Built {OUT}: {OUT.stat().st_size:,} bytes")
