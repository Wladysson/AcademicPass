import { create } from "zustand";
import searchApi from "../api/searchApi";

const INITIAL_FILTERS = {
  query: "",
  year: null,
  area: null,
  discipline: null,
  exam: null,
  institution: null,
  page: 0,
  size: 20,
};

const useSearchStore = create((set, get) => ({
  // Estado da busca
  filters: { ...INITIAL_FILTERS },
  questions: [],
  totalResults: 0,
  currentPage: 0,
  pageSize: 20,

  // Estado da operação
  isLoading: false,
  error: null,

  // Atualiza um filtro específico.
  setFilter: (name, value) => {
    set((state) => ({
      filters: {
        ...state.filters,
        [name]: value,
        page: name === "page" ? value : 0,
      },
      currentPage: name === "page" ? value : 0,
    }));
  },

  // Atualiza vários filtros simultaneamente.
  setFilters: (newFilters) => {
    set((state) => ({
      filters: {
        ...state.filters,
        ...newFilters,
        page: 0,
      },
      currentPage: 0,
    }));
  },

  // Executa a busca utilizando os filtros atuais.
  searchQuestions: async () => {
    set({
      isLoading: true,
      error: null,
    });

    try {
      const { filters } = get();
      const response = await searchApi.searchQuestions(filters);

      const questions =
        response?.questions ||
        response?.items ||
        response?.results ||
        [];

      const totalResults =
        response?.totalResults ??
        response?.total ??
        response?.count ??
        questions.length;

      set({
        questions,
        totalResults,
        currentPage: filters.page,
        pageSize: filters.size,
        isLoading: false,
        error: null,
      });

      return response;
    } catch (error) {
      set({
        questions: [],
        totalResults: 0,
        isLoading: false,
        error: error.message,
      });

      throw error;
    }
  },

  // Recupera uma questão específica.
  getQuestionById: async (questionId) => {
    set({
      isLoading: true,
      error: null,
    });

    try {
      const question = await searchApi.getQuestionById(questionId);

      set({
        isLoading: false,
        error: null,
      });

      return question;
    } catch (error) {
      set({
        isLoading: false,
        error: error.message,
      });

      throw error;
    }
  },

  // Avança para a próxima página.
  nextPage: async () => {
    const { currentPage, pageSize, totalResults, filters } = get();

    if ((currentPage + 1) * pageSize >= totalResults) {
      return;
    }

    set({
      filters: {
        ...filters,
        page: currentPage + 1,
      },
      currentPage: currentPage + 1,
    });

    return get().searchQuestions();
  },

  // Retorna para a página anterior.
  previousPage: async () => {
    const { currentPage, filters } = get();

    if (currentPage <= 0) {
      return;
    }

    set({
      filters: {
        ...filters,
        page: currentPage - 1,
      },
      currentPage: currentPage - 1,
    });

    return get().searchQuestions();
  },

  // Define uma página específica.
  goToPage: async (page) => {
    const { filters, totalResults, pageSize } = get();

    if (
      !Number.isInteger(page) ||
      page < 0 ||
      page * pageSize >= totalResults
    ) {
      return;
    }

    set({
      filters: {
        ...filters,
        page,
      },
      currentPage: page,
    });

    return get().searchQuestions();
  },

  // Limpa os filtros e os resultados.
  resetSearch: () => {
    set({
      filters: { ...INITIAL_FILTERS },
      questions: [],
      totalResults: 0,
      currentPage: 0,
      pageSize: INITIAL_FILTERS.size,
      isLoading: false,
      error: null,
    });
  },

  // Limpa somente a mensagem de erro.
  clearError: () => {
    set({ error: null });
  },
}));

export default useSearchStore;