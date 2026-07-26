function Navbar({ username, onLogout }) {
    const loginWithGitHub = () => {
      window.location.href =
        `${import.meta.env.VITE_API_URL}/auth/login`;
    };
  
    return (
      <nav>
        <h2>GitHub Assistant</h2>
  
        {username ? (
          <div>
            <span>{username}</span>
            <button onClick={onLogout}>
              Logout
            </button>
          </div>
        ) : (
          <button onClick={loginWithGitHub}>
            Login with GitHub
          </button>
        )}
      </nav>
    );
  }
  
  export default Navbar;