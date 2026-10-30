import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_GATEWAY_URL;

if (!API_BASE_URL) {
  throw new Error(
    "A variável VITE_API_GATEWAY_URL não foi definida."
  );
}

const gatewayClient = axios.create({
  baseURL: API_BASE_URL.replace(/\/+$/, ""),
  timeout: 15000,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

// Adiciona o token de autenticação às requisições protegidas.
gatewayClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Centraliza o tratamento de respostas HTTP.
gatewayClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
    }

    return Promise.reject(error);
  }
);

export default gatewayClient;