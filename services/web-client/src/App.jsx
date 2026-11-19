import React from "react";
import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import LoginView from "./views/LoginView.jsx";
import SearchView from "./views/SearchView.jsx";
import QuestionDetailView from "./views/QuestionDetailView.jsx";
import SelectionView from "./views/SelectionView.jsx";
import ProfessorDashboardView from "./views/ProfessorDashboardView.jsx";

function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={<Navigate to="/login" replace />}
      />

      <Route
        path="/login"
        element={<LoginView />}
      />

      <Route
        path="/search"
        element={<SearchView />}
      />

      <Route
        path="/questions/:id"
        element={<QuestionDetailView />}
      />

      <Route
        path="/selection"
        element={<SelectionView />}
      />

      <Route
        path="/professor/dashboard"
        element={<ProfessorDashboardView />}
      />

      <Route
        path="*"
        element={<Navigate to="/login" replace />}
      />
    </Routes>
  );
}

export default App;
