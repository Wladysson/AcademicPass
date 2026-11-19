import gatewayClient from "./gatewayClient";

const AUTH_ENDPOINT = "/api/v1/auth";

export const authApi = {
  async login(credentials) {
    try {
      const response = await gatewayClient.post(
        `${AUTH_ENDPOINT}/login`,
        {
          username: credentials.username,
          password: credentials.password,
        }
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async logout() {
    try {
      const response = await gatewayClient.post(
        `${AUTH_ENDPOINT}/logout`
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async getSession() {
    try {
      const response = await gatewayClient.get(
        `${AUTH_ENDPOINT}/session`
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  normalizeError(error) {
    const status = error.response?.status;
    const responseData = error.response?.data;

    const message =
      responseData?.message ||
      responseData?.detail ||
      error.message ||
      "Não foi possível concluir a operação de autenticação.";

    return Object.assign(new Error(message), {
      status,
      code: responseData?.code,
      details: responseData,
    });
  },
};

export default authApi;