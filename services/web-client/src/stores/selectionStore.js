import { create } from "zustand";
import selectionApi from "../api/selectionApi";

const useSelectionStore = create((set, get) => ({
  selections: [],
  totalSelected: 0,
  isLoading: false,
  error: null,

  // Atualiza a seleção local com os dados retornados pela API.
  updateSelections: (selections) => {
    const normalizedSelections = Array.isArray(selections)
      ? selections
      : selections?.items || selections?.selections || [];

    set({
      selections: normalizedSelections,
      totalSelected: normalizedSelections.length,
    });
  },

  // Recupera as questões selecionadas pelo usuário.
  fetchSelections: async () => {
    set({
      isLoading: true,
      error: null,
    });

    try {
      const response = await selectionApi.getSelections();

      get().updateSelections(response);

      set({
        isLoading: false,
        error: null,
      });

      return response;
    } catch (error) {
      set({
        isLoading: false,
        error: error.message,
      });

      throw error;
    }
  },

  // Adiciona uma questão à seleção.
  addQuestion: async (questionId) => {
    if (!questionId) {
      throw new Error("O identificador da questão é obrigatório.");
    }

    set({
      isLoading: true,
      error: null,
    });

    try {
      const response = await selectionApi.addQuestion(questionId);

      if (Array.isArray(response)) {
        get().updateSelections(response);
      } else if (response?.selections || response?.items) {
        get().updateSelections(response);
      } else if (response) {
        const currentSelections = get().selections;

        get().updateSelections([
          ...currentSelections,
          response,
        ]);
      }

      set({
        isLoading: false,
        error: null,
      });

      return response;
    } catch (error) {
      set({
        isLoading: false,
        error: error.message,
      });

      throw error;
    }
  },

  // Atualiza os dados de uma seleção existente.
  updateSelection: async (selectionId, data) => {
    if (!selectionId) {
      throw new Error("O identificador da seleção é obrigatório.");
    }

    set({
      isLoading: true,
      error: null,
    });

    try {
      const response = await selectionApi.updateSelection(
        selectionId,
        data
      );

      if (response) {
        set((state) => ({
          selections: state.selections.map((selection) =>
            selection.id === selectionId
              ? { ...selection, ...response }
              : selection
          ),
        }));
      }

      set({
        isLoading: false,
        error: null,
      });

      return response;
    } catch (error) {
      set({
        isLoading: false,
        error: error.message,
      });

      throw error;
    }
  },

  // Remove uma questão da seleção.
  removeQuestion: async (selectionId) => {
    if (!selectionId) {
      throw new Error("O identificador da seleção é obrigatório.");
    }

    set({
      isLoading: true,
      error: null,
    });

    try {
      await selectionApi.removeQuestion(selectionId);

      set((state) => {
        const selections = state.selections.filter(
          (selection) => selection.id !== selectionId
        );

        return {
          selections,
          totalSelected: selections.length,
          isLoading: false,
          error: null,
        };
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error.message,
      });

      throw error;
    }
  },

  // Remove todas as questões selecionadas.
  clearSelections: async () => {
    set({
      isLoading: true,
      error: null,
    });

    try {
      await selectionApi.clearSelections();

      set({
        selections: [],
        totalSelected: 0,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error.message,
      });

      throw error;
    }
  },

  // Verifica se uma questão já está selecionada.
  isQuestionSelected: (questionId) => {
    return get().selections.some(
      (selection) =>
        selection.questionId === questionId ||
        selection.question_id === questionId
    );
  },

  // Limpa somente a mensagem de erro.
  clearError: () => {
    set({ error: null });
  },
}));

export default useSelectionStore;