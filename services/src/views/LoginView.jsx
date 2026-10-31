import { useState } from "react";
import { useNavigate } from "react-router-dom";
import useAuthStore from "../stores/authStore";

function LoginView() {
  const navigate = useNavigate();

  const login = useAuthStore((state) => state.login);
  const isLoading = useAuthStore((state) => state.isLoading);
  const error = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);

  const [credentials, setCredentials] = useState({
    username: "",
    password: "",
  });

  const [showPassword, setShowPassword] = useState(false);

  function handleChange(event) {
    const { name, value } = event.target;

    setCredentials((current) => ({
      ...current,
      [name]: value,
    }));

    if (error) {
      clearError();
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    try {
      const response = await login(credentials);

      const user =
        response?.user ||
        response?.usuario ||
        response?.data?.user ||
        response?.data?.usuario;

      const profile =
        user?.profile ||
        user?.role ||
        user?.perfil ||
        user?.roles?.[0];

      if (profile === "PROFESSOR") {
        navigate("/professor/dashboard", { replace: true });
        return;
      }

      navigate("/search", { replace: true });
    } catch {
      // O erro é apresentado pelo estado compartilhado do authStore.
    }
  }

  return (
    <main className="login-page">
      <section className="login-container">
        <header className="login-header">
          <h1>AcademicPass</h1>
          <p>Plataforma de busca e organização de questões do ENADE</p>
        </header>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Usuário</label>

            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              placeholder="Informe seu usuário"
              value={credentials.username}
              onChange={handleChange}
              required
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Senha</label>

            <div className="password-field">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Informe sua senha"
                value={credentials.password}
                onChange={handleChange}
                required
                disabled={isLoading}
              />

              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={
                  showPassword ? "Ocultar senha" : "Mostrar senha"
                }
                disabled={isLoading}
              >
                {showPassword ? "Ocultar" : "Mostrar"}
              </button>
            </div>
          </div>

          {error && (
            <div className="login-error" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="login-submit"
            disabled={
              isLoading ||
              !credentials.username.trim() ||
              !credentials.password
            }
          >
            {isLoading ? "Autenticando..." : "Entrar"}
          </button>
        </form>

        <footer className="login-footer">
          <p>AcademicPass — Plataforma acadêmica ENADE</p>
        </footer>
      </section>
    </main>
  );
}

export default LoginView;
