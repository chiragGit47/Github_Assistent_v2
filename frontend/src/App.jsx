import { useEffect, useState } from "react";

import Navbar from "./components/Navbar";
import api from "./services/api";
import ChatBox from "./components/ChatBox";

function App() {
  const [sessionId, setSessionId] = useState(
    sessionStorage.getItem("session_id")
  );

  const [username, setUsername] = useState(
    sessionStorage.getItem("username")
  );

  useEffect(() => {
    const params = new URLSearchParams(
      window.location.search
    );

    const returnedSessionId =
      params.get("session_id");

    const returnedUsername =
      params.get("username");

    if (returnedSessionId && returnedUsername) {
      sessionStorage.setItem(
        "session_id",
        returnedSessionId
      );

      sessionStorage.setItem(
        "username",
        returnedUsername
      );

      setSessionId(returnedSessionId);
      setUsername(returnedUsername);

      window.history.replaceState(
        {},
        document.title,
        window.location.pathname
      );
    }
  }, []);

  const logout = async () => {
    try {
      if (sessionId) {
        await api.post("/auth/logout", {
          session_id: sessionId,
        });
      }
    } finally {
      sessionStorage.clear();
      setSessionId(null);
      setUsername(null);
    }
  };

  return (
    <div className="app">
      <Navbar
        username={username}
        onLogout={logout}
      />
  
      <main>
        {sessionId ? (
          <ChatBox sessionId={sessionId} />
        ) : (
          <p>Log in to start using the assistant.</p>
        )}
      </main>
    </div>
  );
}

export default App;