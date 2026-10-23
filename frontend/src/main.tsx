import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import PlaylistFormPage from "./pages/PlaylistFormPage";
import PlaylistPage from "./pages/PlaylistPage";
import PlaylistsPage from "./pages/PlaylistsPage";
import SettingsPage from "./pages/SettingsPage";
import "./styles.css";

function App() {
  return (
    <BrowserRouter>
      <header className="topbar">
        <span className="brand">Playlist Rotate</span>
        <nav>
          <NavLink to="/" end>Playlists</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
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
