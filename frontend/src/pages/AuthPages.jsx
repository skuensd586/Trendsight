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
        window.alert(error.message || '登录失败');
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
          <p className="eyebrow">{isLogin ? 'Welcome back' : 'Join Trendsight'}</p>
          <h1>{isLogin ? '欢迎回来' : '创建你的分析工作台'}</h1>
          <p>
            {isLogin
              ? '继续查看实时舆情事件、风险预警和趋势报告。'
              : '配置你的关注平台、领域和关键词，让舆情监测更贴合任务目标。'}
          </p>
          <div className="auth-stats">
            <span>多源采集</span>
            <span>情感研判</span>
            <span>风险预测</span>
          </div>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <h2>{isLogin ? '账号登录' : '账号注册'}</h2>
          {!isLogin && (
            <label>
              <span>用户名</span>
              <div className="input-wrap">
                <UserRound size={18} />
                <input name="username" placeholder="请输入用户名" required />
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
              <input name="password" type="password" placeholder="请输入密码" required />
              <Eye size={18} />
            </div>
          </label>
          {!isLogin && (
            <label>
              <span>确认密码</span>
              <div className="input-wrap">
                <LockKeyhole size={18} />
                <input name="confirmPassword" type="password" placeholder="请再次输入密码" required />
              </div>
            </label>
          )}

          <button className="auth-submit" type="submit">
            {isLogin ? '登录系统' : '完成注册'}
          </button>
          <p className="auth-switch">
            {isLogin ? '还没有账号？' : '已有账号？'}
            <Link to={isLogin ? '/register' : '/login'}>{isLogin ? '立即注册' : '去登录'}</Link>
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
