import { Navigate, Route, Routes } from "react-router";

import ChatPage from "./pages/ChatPage";
import LoginPage from "./pages/LoginPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ChatPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}