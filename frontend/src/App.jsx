import { Navigate, Route, Routes } from 'react-router-dom';
import LandingPage from './pages/LandingPage.jsx';
import { LoginPage, RegisterPage } from './pages/AuthPages.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import EventDetailPage from './pages/EventDetailPage.jsx';
import ProfilePage from './pages/ProfilePage.jsx';
import QAPage from './pages/QAPage.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/events/:id" element={<EventDetailPage />} />
      <Route path="/qa" element={<QAPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
