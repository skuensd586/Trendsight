import { Link, useNavigate } from 'react-router-dom';
import { Eye, LockKeyhole, Mail, Radar, UserRound } from 'lucide-react';
import { api, isBackendMode } from '../api/index.js';

function AuthLayout({ mode }) {
  const navigate = useNavigate();
  const isLogin = mode === 'login';

  const handleSubmit = async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const username = form.get('username') || form.get('email') || 'analyst';
    const password = form.get('password') || '';
    if (isBackendMode() && isLogin) {
      try {
        const result = await api.login({ username: String(username), password: String(password) });
        localStorage.setItem('trendsight-token', result.token);
        localStorage.setItem('trendsight-user', result.username || String(username));
        navigate('/dashboard');
      } catch (error) {
        window.alert(error.message || '登录失败，请检查账号或密码');
      }
      return;
    }
    localStorage.setItem('trendsight-user', String(username).split('@')[0]);
    navigate('/dashboard');
  };

  return (
    <main className="auth-page">
      <Link to="/" className="auth-brand">
        <span className="brand-symbol">
          <Radar size={20} strokeWidth={2.4} />
        </span>
        <span>Trendsight</span>
      </Link>

      <section className="auth-card">
        <div className="auth-welcome">
          <p className="eyebrow">{isLogin ? '登录' : '注册'}</p>
          <h1>{isLogin ? '登录 Trendsight' : '创建账号'}</h1>
          <p>
            {isLogin
              ? '查看最新事件、风险预警和趋势报告。'
              : '设置关注平台、领域和关键词，进入看板后可继续修改。'}
          </p>
          <div className="auth-stats">
            <span>事件监测</span>
            <span>情绪分析</span>
            <span>风险提醒</span>
          </div>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <h2>{isLogin ? '登录账号' : '注册账号'}</h2>
          {!isLogin && (
            <label>
              <span>用户名</span>
              <div className="input-wrap">
                <UserRound size={18} />
                <input name="username" placeholder="例如 analyst" required />
              </div>
            </label>
          )}
          <label>
            <span>{isLogin ? '用户名' : '邮箱'}</span>
            <div className="input-wrap">
              {isLogin ? <UserRound size={18} /> : <Mail size={18} />}
              <input name={isLogin ? 'username' : 'email'} placeholder={isLogin ? 'analyst' : 'name@example.com'} required />
            </div>
          </label>
          <label>
            <span>密码</span>
            <div className="input-wrap">
              <LockKeyhole size={18} />
              <input name="password" type="password" placeholder="输入密码" required />
              <Eye size={18} />
            </div>
          </label>
          {!isLogin && (
            <label>
              <span>确认密码</span>
              <div className="input-wrap">
                <LockKeyhole size={18} />
                <input name="confirmPassword" type="password" placeholder="再次输入密码" required />
              </div>
            </label>
          )}

          <button className="auth-submit" type="submit">
            {isLogin ? '登录并进入看板' : '注册并进入看板'}
          </button>
          <p className="auth-switch">
            {isLogin ? '还没有账号？' : '已有账号？'}
            <Link to={isLogin ? '/register' : '/login'}>{isLogin ? '创建账号' : '登录账号'}</Link>
          </p>
        </form>
      </section>
    </main>
  );
}

export function LoginPage() {
  return <AuthLayout mode="login" />;
}

export function RegisterPage() {
  return <AuthLayout mode="register" />;
}
