import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import PlaylistFormPage from "./pages/PlaylistFormPage";
import PlaylistPage from "./pages/PlaylistPage";
import PlaylistsPage from "./pages/PlaylistsPage";
import SettingsPage from "./pages/SettingsPage";
import "./styles.css";

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
        <path d="M20 12a8 8 0 1 1-2.34-5.66" />
        <path d="M20 4v4.5h-4.5" />
      </svg>
    </span>
  );
}

function App() {
  return (
    <BrowserRouter>
      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/" className="brand">
            <BrandMark />
            <span className="brand-name">Playlist Rotate</span>
          </Link>
          <nav className="nav">
            <NavLink to="/" end>Playlists</NavLink>
            <NavLink to="/settings">Settings</NavLink>
          </nav>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<PlaylistsPage />} />
          <Route path="/playlists/new" element={<PlaylistFormPage />} />
          <Route path="/playlists/:id" element={<PlaylistPage />} />
          <Route path="/playlists/:id/edit" element={<PlaylistFormPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
