package org.enade.search.domain.model;

import java.util.List;
public record SearchResult(
        List<Question> questions,
        long totalElements,
        int page,
        int pageSize,
        int totalPages
) {

    public SearchResult {
        if (questions == null) {
            questions = List.of();
        } else {
            questions = List.copyOf(questions);
        }

        if (totalElements < 0) {
            throw new IllegalArgumentException(
                    "O total de resultados não pode ser negativo."
            );
        }

        if (page < 0) {
            throw new IllegalArgumentException(
                    "A página não pode ser negativa."
            );
        }

        if (pageSize < 1 || pageSize > 100) {
            throw new IllegalArgumentException(
                    "O tamanho da página deve estar entre 1 e 100."
            );
        }

        int expectedTotalPages = totalElements == 0
                ? 0
                : (int) Math.ceil((double) totalElements / pageSize);

        if (totalPages != expectedTotalPages) {
            totalPages = expectedTotalPages;
        }

        if (questions.size() > pageSize) {
            throw new IllegalArgumentException(
                    "A quantidade de questões excede o tamanho da página."
            );
        }
    }

    public boolean hasNext() {
        return page + 1 < totalPages;
    }

    public boolean hasPrevious() {
        return page > 0 && totalPages > 0;
    }

    public boolean isEmpty() {
        return questions.isEmpty();
    }
}
