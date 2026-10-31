import gatewayClient from "./gatewayClient";

const SEARCH_ENDPOINT = "/api/v1/questions";

export const searchApi = {
  async searchQuestions(filters = {}) {
    try {
      const response = await gatewayClient.get(SEARCH_ENDPOINT, {
        params: this.normalizeFilters(filters),
      });

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  async getQuestionById(questionId) {
    if (!questionId) {
      throw new Error("O identificador da questão é obrigatório.");
    }

    try {
      const response = await gatewayClient.get(
        `${SEARCH_ENDPOINT}/${encodeURIComponent(questionId)}`
      );

      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  },

  normalizeFilters(filters) {
    const normalized = {};

    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }

      if (Array.isArray(value)) {
        if (value.length > 0) {
          normalized[key] = value;
        }

        return;
      }

      normalized[key] = value;
    });

    return normalized;
  },

  normalizeError(error) {
    const status = error.response?.status;
    const responseData = error.response?.data;

    const message =
      responseData?.message ||
      responseData?.detail ||
      error.message ||
      "Não foi possível realizar a busca de questões.";

    return Object.assign(new Error(message), {
      status,
      code: responseData?.code,
      details: responseData,
    });
  },
};

export default searchApi;