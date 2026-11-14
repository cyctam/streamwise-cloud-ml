import { useEffect, useMemo, useState } from 'react';
import {
  Activity, ArrowUpRight, BarChart3, BrainCircuit, ChevronDown, Database,
  FileChartColumn, Gauge, Github, Layers3, LayoutDashboard, Menu, Network,
  RefreshCw, Sparkles, Users, X, BarChart3 as BarChartIcon,
} from 'lucide-react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { api } from './api';
import type {
  DatasetPreview, DatasetProfile, DatasetSummary, ForecastResponse,
  ModelMetrics, OverviewResponse, Recommendation,
} from './api';

type Page = 'overview' | 'datasets' | 'recommendations' | 'model' | 'forecasting' | 'architecture';
const NAV: { id: Page; label: string; icon: typeof LayoutDashboard; group: string }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, group: 'WORKSPACE' },
  { id: 'datasets', label: 'Data explorer', icon: Database, group: 'WORKSPACE' },
  { id: 'recommendations', label: 'Recommendations', icon: Sparkles, group: 'MACHINE LEARNING' },
  { id: 'model', label: 'Model evaluation', icon: BrainCircuit, group: 'MACHINE LEARNING' },
  { id: 'forecasting', label: 'Stream forecasting', icon: BarChartIcon, group: 'ANALYTICS' },
  { id: 'architecture', label: 'Architecture', icon: Network, group: 'ENGINEERING' },
];
const CHART_COLORS = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ec4899', '#06b6d4'];
const number = (value?: number) => value == null ? '—' : value.toLocaleString('en-US');
const percent = (value?: number | null) => value == null ? '—' : `${(value * 100).toFixed(1)}%`;

const tooltipStyle = { background: '#18181b', border: '1px solid #27272a', borderRadius: 8, color: '#ededed', fontSize: 12 };

export default function App() {
  const [page, setPage] = useState<Page>('overview');
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [navSearch, setNavSearch] = useState('');
  
  const [datasetList, setDatasetList] = useState<DatasetSummary[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('user_interactions');
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  
  const [metrics, setMetrics] = useState<ModelMetrics | { error: string } | null>(null);
  
  const [userId, setUserId] = useState('user_00042');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [recommendError, setRecommendError] = useState('');
  const [recommendLoading, setRecommendLoading] = useState(false);
  
  const [contentList, setContentList] = useState<{ content_id: string; title: string; genre: string; content_type: string }[]>([]);
  const [contentId, setContentId] = useState('content_00001');
  const [forecastMethod, setForecastMethod] = useState('moving_average');
  const [forecastPeriods, setForecastPeriods] = useState(14);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [forecastError, setForecastError] = useState('');
  const [forecastLoading, setForecastLoading] = useState(false);

  const refresh = async () => {
    setLoading(true); setError('');
    try { setOverview(await api.overview()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load API data'); }
    finally { setLoading(false); }
  };

  useEffect(() => { void refresh(); }, []);
  
  useEffect(() => {
    if (page === 'datasets' && datasetList.length === 0) {
      api.datasets().then(result => {
        setDatasetList(result.datasets);
        if (result.datasets.length) setSelectedDataset(result.datasets.find(item => item.name === 'user_interactions')?.name || result.datasets[0].name);
      }).catch(cause => setError(cause instanceof Error ? cause.message : 'Dataset request failed'));
    }
    if (page === 'model' && !metrics) {
      api.metrics().then(setMetrics).catch(cause => setMetrics({ error: cause instanceof Error ? cause.message : 'Model metrics unavailable' }));
    }
    if (page === 'forecasting' && contentList.length === 0) {
      api.content().then(result => {
        setContentList(result.items);
        if (result.items.length) setContentId(result.items[0].content_id);
      }).catch(cause => setForecastError(cause instanceof Error ? cause.message : 'Content catalog unavailable'));
    }
  }, [page, datasetList.length, metrics, contentList.length]);

  useEffect(() => {
    if (page !== 'datasets' || !selectedDataset) return;
    Promise.all([api.preview(selectedDataset), api.profile(selectedDataset)])
      .then(([nextPreview, nextProfile]) => { setPreview(nextPreview); setProfile(nextProfile); })
      .catch(cause => setError(cause instanceof Error ? cause.message : 'Dataset inspection failed'));
  }, [page, selectedDataset]);

  const active = NAV.find(item => item.id === page)!;
  const visibleNav = useMemo(() => NAV.filter(item => !navSearch || item.label.toLowerCase().includes(navSearch.toLowerCase())), [navSearch]);

  const runRecommendations = async () => {
    setRecommendLoading(true); setRecommendError(''); setRecommendations([]);
    try { const result = await api.recommendations(userId.trim(), 10); setRecommendations(result.items); }
    catch (cause) { setRecommendError(cause instanceof Error ? cause.message : 'Recommendation request failed'); }
    finally { setRecommendLoading(false); }
  };

  const runForecast = async () => {
    setForecastLoading(true); setForecastError(''); setForecast(null);
    try { setForecast(await api.forecast(contentId, forecastMethod, forecastPeriods)); }
    catch (cause) { setForecastError(cause instanceof Error ? cause.message : 'Forecast request failed'); }
    finally { setForecastLoading(false); }
  };

  return (
    <div className="app-shell">
      <Sidebar 
        active={page} setPage={setPage} mobileOpen={mobileOpen} setMobileOpen={setMobileOpen}
        navSearch={navSearch} setNavSearch={setNavSearch} visibleNav={visibleNav} overview={overview}
        loading={loading} error={error}
      />
      {mobileOpen && <button className="scrim" onClick={() => setMobileOpen(false)} />}
      <main className="main-area">
        <header className="topbar">
          <div className="top-left">
            <button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)}><Menu size={18} /></button>
            <span>Workspace</span><span>/</span><b>{active.label}</b>
          </div>
          <div className="top-actions">
            <div className="env-pill"><span className="pulse-dot" /> LOCAL</div>
            <button className="icon-button" onClick={() => void refresh()}><RefreshCw size={16} /></button>
            <a className="icon-button" href="https://github.com/cyctam/streamwise-cloud-ml" target="_blank" rel="noreferrer"><Github size={16} /></a>
          </div>
        </header>
        
        <div className="page-wrap">
          <div className="page-heading">
            <div>
              <div className="eyebrow">{active.group}</div>
              <h1>{active.label}</h1>
              <p>{pageDescriptions[page]}</p>
            </div>
          </div>

          {error && (
            <div className="alert">
              <div><b>API Error</b><span>{error}</span></div>
            </div>
          )}

          {page === 'overview' && <Overview data={overview} loading={loading} />}
          {page === 'datasets' && <Datasets datasets={datasetList} selected={selectedDataset} preview={preview} profile={profile} onSelect={setSelectedDataset} />}
          {page === 'recommendations' && <Recommendations userId={userId} setUserId={setUserId} items={recommendations} error={recommendError} loading={recommendLoading} onRun={runRecommendations} />}
          {page === 'model' && <ModelPage metrics={metrics} />}
          {page === 'forecasting' && <Forecasting contentList={contentList} contentId={contentId} setContentId={setContentId} method={forecastMethod} setMethod={setForecastMethod} periods={forecastPeriods} setPeriods={setForecastPeriods} result={forecast} error={forecastError} loading={forecastLoading} onRun={runForecast} />}
          {page === 'architecture' && <Architecture />}
          
          <footer className="footer">
            <span>STREAMWISE · HYBRID RECOMMENDATION SYSTEM</span>
            <span>API {overview ? '2.1.0' : '—'}</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

const pageDescriptions: Record<Page, string> = {
  overview: 'Monitor the dataset, engagement signals, and recommendation service.',
  datasets: 'Inspect source tables, data quality, column distributions, and sample records.',
  recommendations: 'Generate ranked, unseen titles from content and collaborative signals.',
  model: 'Review offline ranking metrics against a popularity baseline.',
  forecasting: 'Explore transparent statistical baselines using observed playback history.',
  architecture: 'Trace the implemented data-to-inference workflow and deployment boundary.',
};

function Sidebar({ active, setPage, mobileOpen, setMobileOpen, navSearch, setNavSearch, visibleNav, overview, loading, error }: any) {
  return (
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="brand">
        <div className="brand-mark"><Activity size={18} /></div>
        <div><strong>streamwise</strong><span>ML ENGINEERING</span></div>
        <button className="icon-button mobile-close" onClick={() => setMobileOpen(false)}><X size={18} /></button>
      </div>
      
      <div className="workspace-switch">
        <div className="workspace-avatar">S</div>
        <div><b>Streamwise Lab</b><span>Recommendation workspace</span></div>
        <ChevronDown size={14} />
      </div>

      <label className="nav-search">
        <Database size={14} />
        <input value={navSearch} onChange={e => setNavSearch(e.target.value)} placeholder="Find a page..." />
      </label>

      {['WORKSPACE', 'MACHINE LEARNING', 'ANALYTICS', 'ENGINEERING'].map(group => (
        <div className="nav-group" key={group}>
          <div className="nav-label">{group}</div>
          {visibleNav.filter((i: any) => i.group === group).map((item: any) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={`nav-item ${active === item.id ? 'active' : ''}`} onClick={() => { setPage(item.id); setMobileOpen(false); }}>
                <Icon size={16} /><span>{item.label}</span>
              </button>
            );
          })}
        </div>
      ))}

      <div className="sidebar-bottom">
        <div className="pipeline-status">
          <div className="status-line"><span className="pulse-dot" /> API CONNECTION</div>
          <b>{loading ? 'Checking service' : error ? 'Connection issue' : 'API responding'}</b>
          <small>{overview?.model?.loaded ? 'Model artifact loaded' : 'Model artifact unavailable'}</small>
        </div>
      </div>
    </aside>
  );
}

function Overview({ data, loading }: { data: OverviewResponse | null; loading: boolean }) {
  const kpis = data?.kpis;
  const cards = [
    { label: 'USERS', value: kpis?.users, icon: Users },
    { label: 'CATALOG', value: kpis?.content, icon: Layers3 },
    { label: 'INTERACTIONS', value: kpis?.interactions, icon: Activity },
    { label: 'POSITIVE SIGNALS', value: kpis?.positive_events, icon: ArrowUpRight },
  ];
  return (
    <>
      <div className="kpi-grid">
        {cards.map(card => {
          const Icon = card.icon;
          return (
            <div className="kpi-card" key={card.label}>
              <div className="kpi-top"><span>{card.label}</span><Icon size={16} /></div>
              <div className="kpi-value">{loading ? '—' : number(card.value)}</div>
            </div>
          );
        })}
      </div>
      
      <div className="content-grid">
        <section className="panel chart-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">ENGAGEMENT</span><h2>Daily positive interactions</h2></div>
            <Activity size={18} />
          </div>
          {data?.daily_activity.length ? (
            <div className="chart-area">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.daily_activity} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorEvents" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={v => v.slice(5)} tick={{ fill: '#a1a1aa', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#a1a1aa', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="events" stroke="#10b981" strokeWidth={2} fill="url(#colorEvents)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : <div className="empty-state">{loading ? 'Loading…' : 'No data'}</div>}
        </section>
        
        <section className="panel mix-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">DISTRIBUTION</span><h2>Genre engagement</h2></div>
            <BarChart3 size={18} />
          </div>
          {data?.genre_distribution.length ? (
            <>
              <div className="donut-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={data.genre_distribution} dataKey="interactions" nameKey="genre" innerRadius={60} outerRadius={80} paddingAngle={2} stroke="none">
                      {data.genre_distribution.map((entry, index) => <Cell key={entry.genre} fill={CHART_COLORS[index % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="donut-center"><b>{number(kpis?.interactions)}</b><span>EVENTS</span></div>
              </div>
              <div className="legend-list">
                {data.genre_distribution.slice(0, 6).map((item, index) => (
                  <div key={item.genre} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span><i style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} />{item.genre}</span>
                    <b>{number(item.interactions)}</b>
                  </div>
                ))}
              </div>
            </>
          ) : <div className="empty-state">{loading ? 'Loading…' : 'No data'}</div>}
        </section>
      </div>

      <div className="bottom-grid">
        <section className="panel">
          <div className="panel-heading">
            <div><span className="section-kicker">TAXONOMY</span><h2>Interaction signals</h2></div>
          </div>
          <div>
            {(data?.event_distribution || []).map((item) => {
              const max = Math.max(...(data?.event_distribution || []).map(r => r.count), 1);
              return (
                <div className="event-bar-row" key={item.event}>
                  <span style={{ color: 'var(--muted)', textTransform: 'capitalize' }}>{item.event.replace(/_/g, ' ')}</span>
                  <div><i style={{ width: `${(item.count / max) * 100}%` }} /></div>
                  <b>{number(item.count)}</b>
                </div>
              );
            })}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div><span className="section-kicker">MODEL</span><h2>Hybrid Recommender</h2></div>
            <BrainCircuit size={18} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '24px' }}>
            <span className={`pulse-dot`} style={{ background: data?.model?.loaded ? '#10b981' : '#f59e0b' }} />
            <div>
              <b style={{ display: 'block', fontSize: '13px' }}>{data?.model?.loaded ? 'Artifact Loaded' : 'Model Unavailable'}</b>
              <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{data?.model?.loaded ? 'Ready for inference' : 'Train the pipeline to generate artifact'}</span>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}

function Datasets({ datasets, selected, preview, profile, onSelect }: any) {
  return (
    <>
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        {datasets.map((d: any) => (
          <button key={d.name} onClick={() => onSelect(d.name)} className="panel" style={{ textAlign: 'left', cursor: 'pointer', borderColor: selected === d.name ? 'var(--accent)' : 'var(--line)' }}>
            <div className="kpi-top"><Database size={16} /><span>{number(d.rows)} rows</span></div>
            <div style={{ fontSize: '14px', fontWeight: 500, marginBottom: '4px', textTransform: 'capitalize' }}>{d.name.replace(/_/g, ' ')}</div>
            <div style={{ fontSize: '11px', color: 'var(--muted)' }}>{d.columns} columns</div>
          </button>
        ))}
      </div>

      <section className="panel" style={{ marginTop: '16px' }}>
        <div className="panel-heading"><div><span className="section-kicker">PREVIEW</span><h2>{preview?.name.replace(/_/g, ' ') || 'Loading…'}</h2></div></div>
        {preview?.rows.length ? (
          <div className="table-scroll">
            <table>
              <thead><tr>{preview.columns.map((c: string) => <th key={c}>{c.replace(/_/g, ' ')}</th>)}</tr></thead>
              <tbody>{preview.rows.map((row: any, i: number) => <tr key={i}>{preview.columns.map((c: string) => <td key={c}>{String(row[c] ?? '—')}</td>)}</tr>)}</tbody>
            </table>
          </div>
        ) : <div className="empty-state">No data</div>}
      </section>

      <section className="panel" style={{ marginTop: '16px' }}>
        <div className="panel-heading"><div><span className="section-kicker">PROFILE</span><h2>Column statistics</h2></div><FileChartColumn size={18} /></div>
        {profile?.columns.length ? (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Field</th><th>Type</th><th>Missing</th><th>Unique</th><th>Summary</th></tr></thead>
              <tbody>
                {profile.columns.map((c: any) => (
                  <tr key={c.name}>
                    <td style={{ fontWeight: 500 }}>{c.name}</td>
                    <td>{c.dtype}</td>
                    <td>{c.missing} ({c.missing_pct}%)</td>
                    <td>{number(c.unique)}</td>
                    <td>{c.statistics ? `min ${c.statistics.min} · max ${c.statistics.max}` : (c.top_values || []).map((t: any) => t.value).join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="empty-state">No data</div>}
      </section>
    </>
  );
}

function Recommendations({ userId, setUserId, items, error, loading, onRun }: any) {
  return (
    <section className="panel recommend-panel">
      <div className="panel-heading">
        <div><span className="section-kicker">INFERENCE</span><h2>Personalized Ranking</h2></div>
      </div>
      <div className="recommend-form">
        <label>USER ID</label>
        <div className="input-row">
          <div className="input-wrap">
            <Users size={16} />
            <input value={userId} onChange={e => setUserId(e.target.value)} onKeyDown={e => e.key === 'Enter' && onRun()} placeholder="user_00042" />
          </div>
          <button className="button-primary" disabled={loading || !userId.trim()} onClick={onRun}>
            {loading ? 'Ranking…' : 'Generate'} <ArrowUpRight size={16} />
          </button>
        </div>
      </div>
      {error && <div style={{ color: '#ef4444', fontSize: '12px', marginBottom: '16px' }}>{error}</div>}
      {items.length ? (
        <div className="ranking-list">
          {items.map((item: any) => (
            <div className="ranking-row" key={item.content_id}>
              <div className="rank-number">{String(item.rank).padStart(2, '0')}</div>
              <div className="ranking-title">
                <b>{item.title}</b>
                <span>{item.genre} · {item.content_type}</span>
              </div>
              <div className="score-column"><b>{item.hybrid_score.toFixed(3)}</b><span>SCORE</span></div>
              <div className="score-track"><i style={{ width: `${item.hybrid_score * 100}%` }} /></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state"><Sparkles size={24} /><b>No ranking generated</b><span>Enter a user ID to run inference.</span></div>
      )}
    </section>
  );
}

function ModelPage({ metrics }: any) {
  if (metrics && 'error' in metrics) return <div className="empty-state"><BrainCircuit size={24} /><b>Model unavailable</b><span>{metrics.error}</span></div>;
  if (!metrics) return <div className="empty-state">Loading metrics…</div>;

  const cards = [
    { label: 'PRECISION @ 10', value: metrics.hybrid.precision_at_k, baseline: metrics.popularity_baseline.precision_at_k },
    { label: 'RECALL @ 10', value: metrics.hybrid.recall_at_k, baseline: metrics.popularity_baseline.recall_at_k },
    { label: 'NDCG @ 10', value: metrics.hybrid.ndcg_at_k, baseline: metrics.popularity_baseline.ndcg_at_k },
  ];
  const chartData = cards.map(c => ({ name: c.label.split(' ')[0], Hybrid: c.value, Baseline: c.baseline }));

  return (
    <>
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        {cards.map(c => (
          <div className="kpi-card" key={c.label}>
            <div className="kpi-top"><span>{c.label}</span><Gauge size={16} /></div>
            <div className="kpi-value">{percent(c.value)}</div>
            <div className="kpi-note">Baseline: {percent(c.baseline)}</div>
          </div>
        ))}
      </div>
      <div className="panel" style={{ marginTop: '16px' }}>
        <div className="panel-heading"><div><span className="section-kicker">COMPARISON</span><h2>Hybrid vs Popularity</h2></div></div>
        <div style={{ height: '300px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => typeof v === 'number' ? percent(v) : v} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#a1a1aa' }} />
              <Bar dataKey="Hybrid" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Baseline" fill="#3f3f46" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}

function Forecasting({ contentList, contentId, setContentId, method, setMethod, periods, setPeriods, result, error, loading, onRun }: any) {
  const chartData = result ? [
    ...result.history.map((r: any) => ({ date: r.date, actual: r.actual, forecast: null })),
    ...result.forecast.map((r: any) => ({ date: r.date, actual: null, forecast: r.value })),
  ] : [];

  return (
    <section className="panel">
      <div className="panel-heading"><div><span className="section-kicker">FORECAST</span><h2>Configuration</h2></div></div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 100px auto', gap: '16px', alignItems: 'end', marginBottom: '24px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '10px', color: 'var(--muted)', marginBottom: '8px', fontFamily: 'JetBrains Mono' }}>CONTENT</label>
          <select value={contentId} onChange={e => setContentId(e.target.value)} style={{ width: '100%', height: '36px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: '6px', color: '#fff', padding: '0 10px' }}>
            {contentList.map((i: any) => <option key={i.content_id} value={i.content_id}>{i.title}</option>)}
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '10px', color: 'var(--muted)', marginBottom: '8px', fontFamily: 'JetBrains Mono' }}>METHOD</label>
          <select value={method} onChange={e => setMethod(e.target.value)} style={{ width: '100%', height: '36px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: '6px', color: '#fff', padding: '0 10px' }}>
            <option value="moving_average">Moving Avg</option>
            <option value="linear_trend">Linear Trend</option>
            <option value="seasonal_naive">Seasonal Naive</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '10px', color: 'var(--muted)', marginBottom: '8px', fontFamily: 'JetBrains Mono' }}>HORIZON</label>
          <select value={periods} onChange={e => setPeriods(Number(e.target.value))} style={{ width: '100%', height: '36px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: '6px', color: '#fff', padding: '0 10px' }}>
            {[7, 14, 30, 60].map(v => <option key={v} value={v}>{v} days</option>)}
          </select>
        </div>
        <button className="button-primary" onClick={onRun} disabled={loading || !contentId}>{loading ? '...' : 'Run'} <ArrowUpRight size={16} /></button>
      </div>

      {error && <div style={{ color: '#ef4444', fontSize: '12px' }}>{error}</div>}
      
      {result ? (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
            <div className="kpi-card"><div className="kpi-top"><span>HISTORY</span></div><div className="kpi-value" style={{ fontSize: '20px' }}>{result.history.reduce((a: any, b: any) => a + b.actual, 0)}</div></div>
            <div className="kpi-card"><div className="kpi-top"><span>FORECAST</span></div><div className="kpi-value" style={{ fontSize: '20px' }}>{result.forecast.reduce((a: any, b: any) => a + b.value, 0).toFixed(1)}</div></div>
            <div className="kpi-card"><div className="kpi-top"><span>AVG / DAY</span></div><div className="kpi-value" style={{ fontSize: '20px' }}>{(result.forecast.reduce((a: any, b: any) => a + b.value, 0) / result.forecast.length).toFixed(1)}</div></div>
          </div>
          <div style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickFormatter={v => v.slice(5)} tick={{ fill: '#a1a1aa', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={20} />
                <YAxis tick={{ fill: '#a1a1aa', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#a1a1aa' }} />
                <Line type="monotone" dataKey="actual" stroke="#10b981" strokeWidth={2} dot={false} name="Observed" />
                <Line type="monotone" dataKey="forecast" stroke="#6366f1" strokeWidth={2} strokeDasharray="4 4" dot={false} name="Forecast" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : <div className="empty-state"><BarChart3 size={24} /><b>No forecast calculated</b><span>Select a configuration to run.</span></div>}
    </section>
  );
}

function Architecture() {
  const stages = [
    { n: '01', t: 'Source datasets', d: 'User profiles, content metadata, and interactions as CSV.', s: 'Implemented' },
    { n: '02', t: 'Data preparation', d: 'Validate identifiers and build sparse matrix.', s: 'Implemented' },
    { n: '03', t: 'Hybrid model training', d: 'TF-IDF combined with TruncatedSVD latent factors.', s: 'Implemented' },
    { n: '04', t: 'Offline evaluation', d: 'Holdout Precision@10, Recall@10, NDCG@10.', s: 'Implemented' },
    { n: '05', t: 'Inference API', d: 'FastAPI serves ranking and forecasting endpoints.', s: 'Implemented' },
    { n: '06', t: 'Web application', d: 'React dashboard consuming API results.', s: 'Implemented' },
    { n: '07', t: 'Cloud delivery', d: 'Terraform & GitHub Actions for AWS provisioning.', s: 'Pending' },
  ];
  return (
    <div style={{ maxWidth: '800px' }}>
      {stages.map((stage) => (
        <div key={stage.n} style={{ display: 'flex', gap: '20px', marginBottom: '24px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'var(--panel)', border: '1px solid var(--line)', display: 'grid', placeItems: 'center', flexShrink: 0, fontFamily: 'JetBrains Mono', fontSize: '12px', color: 'var(--muted)' }}>{stage.n}</div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
              <b style={{ fontSize: '14px', color: '#fff' }}>{stage.t}</b>
              <span style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px', background: stage.s === 'Implemented' ? '#064e3b' : '#451a03', color: stage.s === 'Implemented' ? '#34d399' : '#fbbf24', border: `1px solid ${stage.s === 'Implemented' ? '#065f46' : '#78350f'}` }}>{stage.s}</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--muted)', lineHeight: 1.6 }}>{stage.d}</span>
          </div>
        </div>
      ))}
    </div>
  );
}