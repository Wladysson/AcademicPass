import gatewayClient from "./gatewayClient";

const SELECTION_ENDPOINT = "/api/v1/selections";

export const selectionApi = {
  async getSelections() {
    try {
      const response = await gatewayClient.get(SELECTION_ENDPOINT);

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async addQuestion(questionId) {
    if (!questionId) {
      throw new Error("O identificador da questão é obrigatório.");
    }

    try {
      const response = await gatewayClient.post(SELECTION_ENDPOINT, {
        questionId,
      });

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async updateSelection(selectionId, data) {
    if (!selectionId) {
      throw new Error("O identificador da seleção é obrigatório.");
    }

    try {
      const response = await gatewayClient.patch(
        `${SELECTION_ENDPOINT}/${encodeURIComponent(selectionId)}`,
        data
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async removeQuestion(selectionId) {
    if (!selectionId) {
      throw new Error("O identificador da seleção é obrigatório.");
    }

    try {
      const response = await gatewayClient.delete(
        `${SELECTION_ENDPOINT}/${encodeURIComponent(selectionId)}`
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async clearSelections() {
    try {
      const response = await gatewayClient.delete(SELECTION_ENDPOINT);

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
      "Não foi possível gerenciar a seleção de questões.";

    return Object.assign(new Error(message), {
      status,
      code: responseData?.code,
      details: responseData,
    });
  },
};

export default selectionApi;