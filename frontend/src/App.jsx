import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Book from "./pages/Book";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Marketplace from "./pages/Marketplace";
import Pay from "./pages/Pay";
import Register from "./pages/Register";
import VendorDetail from "./pages/VendorDetail";

function NavBar() {
  const { user, logout } = useAuth();
  return (
    <nav className="nav">
      <Link to="/" className="brand">EventLogix</Link>
      <div>
        <Link to="/vendors">Marketplace</Link>
        {user ? (
          <>
            <Link to="/dashboard">Dashboard</Link>
            <span className="muted">{user.username} ({user.role})</span>
            <button className="link" onClick={logout}>Log out</button>
          </>
        ) : (
          <>
            <Link to="/login">Log in</Link>
            <Link to="/register">Sign up</Link>
          </>
        )}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <NavBar />
        <main className="container">
          <Routes>
            <Route path="/" element={<Navigate to="/vendors" replace />} />
            <Route path="/vendors" element={<Marketplace />} />
            <Route path="/vendors/:id" element={<VendorDetail />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/book"
              element={<ProtectedRoute roles={["CLIENT"]}><Book /></ProtectedRoute>}
            />
            <Route
              path="/bookings/:id/pay"
              element={<ProtectedRoute roles={["CLIENT"]}><Pay /></ProtectedRoute>}
            />
            <Route
              path="/dashboard"
              element={<ProtectedRoute><Dashboard /></ProtectedRoute>}
            />
            <Route path="*" element={<p className="center">Page not found.</p>} />
          </Routes>
        </main>
      </AuthProvider>
    </BrowserRouter>
  );
}