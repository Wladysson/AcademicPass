import { create } from "zustand";
import authApi from "../api/authApi";

const TOKEN_STORAGE_KEY = "access_token";

// Extrai o token considerando possíveis formatos de resposta da API.
function extractToken(response) {
  return (
    response?.access_token ||
    response?.accessToken ||
    response?.token ||
    response?.data?.access_token ||
    response?.data?.accessToken ||
    response?.data?.token ||
    null
  );
}

// Extrai os dados do usuário da resposta de autenticação.
function extractUser(response) {
  return (
    response?.user ||
    response?.usuario ||
    response?.data?.user ||
    response?.data?.usuario ||
    null
  );
}

// Obtém o perfil associado ao usuário autenticado.
function extractProfile(user) {
  return (
    user?.profile ||
    user?.role ||
    user?.perfil ||
    user?.roles?.[0] ||
    null
  );
}

// Persiste o token para utilização pelo gatewayClient.
function saveToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

const useAuthStore = create((set, get) => ({
  token: localStorage.getItem(TOKEN_STORAGE_KEY),
  user: null,
  profile: null,
  isAuthenticated: Boolean(localStorage.getItem(TOKEN_STORAGE_KEY)),
  isLoading: false,
  error: null,

  login: async (credentials) => {
    set({
      isLoading: true,
      error: null,
    });

    try {
      const response = await authApi.login(credentials);

      const token = extractToken(response);
      const user = extractUser(response);

      if (!token) {
        throw new Error(
          "A resposta de autenticação não contém um token de acesso."
        );
      }

      saveToken(token);

      set({
        token,
        user,
        profile: extractProfile(user),
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      return response;
    } catch (error) {
      saveToken(null);

      set({
        token: null,
        user: null,
        profile: null,
        isAuthenticated: false,
        isLoading: false,
        error: error.message,
      });

      throw error;
    }
  },

  logout: async () => {
    set({ isLoading: true, error: null });

    try {
      await authApi.logout();
    } finally {
      saveToken(null);

      set({
        token: null,
        user: null,
        profile: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  getSession: async () => {
    set({
      isLoading: true,
      error: null,
    });

    try {
      const response = await authApi.getSession();
      const user = extractUser(response) || response?.data || response?.user || null;
      const token =
        extractToken(response) || get().token;

      if (!user) {
        throw new Error("Não foi possível recuperar os dados da sessão.");
      }

      if (token) {
        saveToken(token);
      }

      set({
        token,
        user,
        profile: extractProfile(user),
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      return user;
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        saveToken(null);

        set({
          token: null,
          user: null,
          profile: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      } else {
        set({
          isLoading: false,
          error: error.message,
        });
      }

      throw error;
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));

export default useAuthStore;