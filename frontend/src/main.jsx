import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import { PrivateRoute } from "./components/PrivateRoute.jsx";
import { AgentLogsPage } from "./pages/AgentLogsPage.jsx";
import { DashboardPage } from "./pages/DashboardPage.jsx";
import { EvaluationPage } from "./pages/EvaluationPage.jsx";
import { LoginPage } from "./pages/LoginPage.jsx";
import { ProductDetailPage } from "./pages/ProductDetailPage.jsx";
import { ProductsPage } from "./pages/ProductsPage.jsx";
import { RegisterPage } from "./pages/RegisterPage.jsx";
import { SalesPage } from "./pages/SalesPage.jsx";
import { SimulationPage } from "./pages/SimulationPage.jsx";
import { UsersPage } from "./pages/UsersPage.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          {/* Public: first admin bootstrap (no JWT). Logged-in admins also use this route to invite users. */}
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/"
            element={
              <PrivateRoute>
                <App />
              </PrivateRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="products" element={<ProductsPage />} />
            <Route path="products/:sku" element={<ProductDetailPage />} />
            <Route path="sales" element={<SalesPage />} />
            <Route path="agent-logs" element={<AgentLogsPage />} />
            <Route path="evaluation" element={<EvaluationPage />} />
            <Route path="simulation" element={<SimulationPage />} />
            <Route path="users" element={<UsersPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
