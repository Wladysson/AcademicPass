import gatewayClient from "./gatewayClient";

const SIMULADO_ENDPOINT = "/api/v1/simulados";

export const simuladoApi = {
  async createSimulado(data) {
    if (!data || typeof data !== "object") {
      throw new Error("Os dados para criação do simulado são obrigatórios.");
    }

    try {
      const response = await gatewayClient.post(
        SIMULADO_ENDPOINT,
        data
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async getSimuladoStatus(simuladoId) {
    if (!simuladoId) {
      throw new Error("O identificador do simulado é obrigatório.");
    }

    try {
      const response = await gatewayClient.get(
        `${SIMULADO_ENDPOINT}/${encodeURIComponent(simuladoId)}/status`
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async getSimulado(simuladoId) {
    if (!simuladoId) {
      throw new Error("O identificador do simulado é obrigatório.");
    }

    try {
      const response = await gatewayClient.get(
        `${SIMULADO_ENDPOINT}/${encodeURIComponent(simuladoId)}`
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async exportSimulado(simuladoId, format = "pdf") {
    if (!simuladoId) {
      throw new Error("O identificador do simulado é obrigatório.");
    }

    const supportedFormats = ["pdf", "docx"];

    if (!supportedFormats.includes(format.toLowerCase())) {
      throw new Error("Formato de exportação não suportado.");
    }

    try {
      const response = await gatewayClient.get(
        `${SIMULADO_ENDPOINT}/${encodeURIComponent(simuladoId)}/export`,
        {
          params: { format: format.toLowerCase() },
          responseType: "blob",
        }
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
      "Não foi possível processar a operação do simulado.";

    return Object.assign(new Error(message), {
      status,
      code: responseData?.code,
      details: responseData,
    });
  },
};

export default simuladoApi;