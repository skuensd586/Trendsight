import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CircleUserRound, Clock3, Globe2, LogOut, Plus, Save, X } from 'lucide-react';
import AppShell from '../components/AppShell.jsx';
import { api } from '../api/index.js';
import { focusAreas, focusKeywords, platformSettings } from '../data/events.js';

export default function ProfilePage() {
  const navigate = useNavigate();
  const [platforms, setPlatforms] = useState(platformSettings);
  const [areas, setAreas] = useState(focusAreas);
  const [keywords, setKeywords] = useState(focusKeywords);
  const user = localStorage.getItem('trendsight-user') || '分析师';
  const normalPlatforms = platforms.map((platform, index) => ({ platform, index })).filter(({ platform }) => platform.status !== '限流');
  const limitedPlatforms = platforms.map((platform, index) => ({ platform, index })).filter(({ platform }) => platform.status === '限流');

  useEffect(() => {
    let alive = true;
    api
      .getUserProfile()
      .then((profile) => {
        if (!alive) return;
        const preferences = profile.preferences || {};
        setAreas(preferences.fields || focusAreas);
        setKeywords(preferences.keywords || focusKeywords);
        if (preferences.platform_urls?.length) {
          setPlatforms(
            preferences.platform_urls.map((source) => ({
              name: source.name || source.platform_name || '新采集源',
              url: source.url || 'https://',
              frequency: source.frequency || (source.frequency_minutes ? `${source.frequency_minutes} 分钟` : '10 分钟'),
              status: source.status === 'limited' ? '限流' : source.status || '正常',
            })),
          );
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const addPlatform = () => {
    setPlatforms((current) => [...current, { name: '新采集源', url: 'https://', frequency: '10 分钟', status: '正常' }]);
  };

  const updatePlatform = (index, key, value) => {
    setPlatforms((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, [key]: value } : item)));
  };

  const removePlatform = (index) => {
    setPlatforms((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const logout = () => {
    localStorage.removeItem('trendsight-user');
    localStorage.removeItem('trendsight-token');
    navigate('/');
  };

  const savePreferences = async () => {
    await api.updateUserPreferences({
      fields: areas,
      keywords,
      platform_urls: platforms.map((platform) => ({
        platform_name: platform.name,
        url: platform.url,
        frequency_minutes: Number.parseInt(platform.frequency, 10) || 10,
        status: platform.status === '限流' ? 'limited' : 'normal',
      })),
    });
  };

  return (
    <AppShell>
      <section className="profile-console">
        <div className="profile-heading">
          <p className="eyebrow">Personal Center</p>
          <h1>个人中心</h1>
          <p>配置采集源、关注领域与关键词，系统将据此推送更贴近任务目标的舆情事件。</p>
        </div>

        <section className="profile-console-grid">
          <article className="account-card">
            <div className="account-avatar">
              <CircleUserRound size={28} />
            </div>
            <div>
              <span>账号信息</span>
              <h2>{user}</h2>
              <p>舆情分析师 · 监测中心</p>
            </div>
            <dl>
              <div>
                <dt>关注领域</dt>
                <dd>{areas.length} 个</dd>
              </div>
              <div>
                <dt>采集源</dt>
                <dd>{platforms.length} 个</dd>
              </div>
              <div>
                <dt>今日推送</dt>
                <dd>23 条</dd>
              </div>
            </dl>
          </article>

          <PreferenceEditor title="关注领域 / 关键词" areas={areas} setAreas={setAreas} keywords={keywords} setKeywords={setKeywords} />
        </section>

        <article className="source-config-card">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Sources</span>
              <h2>采集平台 / 网址</h2>
              <p>配置需要监测的新闻网站与社交平台，并设置采集频率与运行状态。</p>
            </div>
            <button className="icon-action" type="button" onClick={addPlatform} aria-label="新增采集源">
              <Plus size={18} />
            </button>
          </div>

          <div className="source-list grouped">
            <SourceGroup title="正常运行" items={normalPlatforms} updatePlatform={updatePlatform} removePlatform={removePlatform} />
            <SourceGroup title="限流 / 异常关注" items={limitedPlatforms} updatePlatform={updatePlatform} removePlatform={removePlatform} empty="暂无异常采集源" />
          </div>
        </article>

        <div className="profile-actions">
          <button type="button" className="save-button" onClick={savePreferences}>
            <Save size={18} />
            保存配置
          </button>
          <button type="button" className="logout-button" onClick={logout}>
            <LogOut size={18} />
            退出登录
          </button>
        </div>
      </section>
    </AppShell>
  );
}

function SourceGroup({ title, items, updatePlatform, removePlatform, empty = '暂无采集源' }) {
  return (
    <section className="source-group">
      <div className="source-group-title">
        <h3>{title}</h3>
        <span>{items.length} 个</span>
      </div>
      {items.length === 0 ? (
        <p className="empty-source">{empty}</p>
      ) : (
        items.map(({ platform, index }) => (
          <div className="source-config-row" key={`${platform.name}-${index}`}>
            <div className="source-avatar">
              <Globe2 size={18} />
            </div>
            <div className="source-fields">
              <input value={platform.name} onChange={(event) => updatePlatform(index, 'name', event.target.value)} aria-label="平台名称" />
              <input value={platform.url} onChange={(event) => updatePlatform(index, 'url', event.target.value)} aria-label="平台网址" />
            </div>
            <label className="source-frequency">
              <Clock3 size={15} />
              <select value={platform.frequency || '10 分钟'} onChange={(event) => updatePlatform(index, 'frequency', event.target.value)}>
                <option>5 分钟</option>
                <option>10 分钟</option>
                <option>15 分钟</option>
                <option>30 分钟</option>
              </select>
            </label>
            <select
              className={`source-status ${platform.status === '限流' ? 'limited' : ''}`}
              value={platform.status || '正常'}
              onChange={(event) => updatePlatform(index, 'status', event.target.value)}
            >
              <option>正常</option>
              <option>限流</option>
            </select>
            <button type="button" onClick={() => removePlatform(index)} aria-label="删除采集源">
              <X size={17} />
            </button>
          </div>
        ))
      )}
    </section>
  );
}

function PreferenceEditor({ title, areas, setAreas, keywords, setKeywords }) {
  const [draft, setDraft] = useState('');
  const [mode, setMode] = useState('keyword');

  const addValue = () => {
    const value = draft.trim();
    if (!value) return;
    if (mode === 'area') setAreas((current) => [...current, value]);
    else setKeywords((current) => [...current, value]);
    setDraft('');
  };

  return (
    <article className="preference-console-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Preference</span>
          <h2>{title}</h2>
          <p>命中这些领域和关键词的事件会被优先监测。</p>
        </div>
      </div>

      <div className="chip-area">
        {[...areas, ...keywords].map((value) => {
          const isArea = areas.includes(value);
          return (
            <button
              key={value}
              type="button"
              onClick={() => {
                if (isArea) setAreas((current) => current.filter((item) => item !== value));
                else setKeywords((current) => current.filter((item) => item !== value));
              }}
            >
              {value}
              <X size={14} />
            </button>
          );
        })}
      </div>

      <div className="preference-add-row">
        <select value={mode} onChange={(event) => setMode(event.target.value)}>
          <option value="keyword">关键词</option>
          <option value="area">领域</option>
        </select>
        <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="新增关键词或领域，回车添加" />
        <button type="button" onClick={addValue}>
          添加
        </button>
      </div>
    </article>
  );
}
