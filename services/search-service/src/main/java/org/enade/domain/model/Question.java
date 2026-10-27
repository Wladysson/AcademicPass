package org.enade.search.domain.model;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public record Question(
        String id,
        String statement,
        String year,
        String exam,
        String area,
        String discipline,
        String topic,
        String institution,
        List<String> alternatives,
        String correctAlternative,
        String explanation,
        LocalDate publicationDate,
        Map<String, List<String>> highlights
) {

    public Question {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador da questão é obrigatório."
            );
        }

        if (statement == null || statement.isBlank()) {
            throw new IllegalArgumentException(
                    "O enunciado da questão é obrigatório."
            );
        }

        alternatives = alternatives == null
                ? List.of()
                : List.copyOf(alternatives);

        highlights = highlights == null
                ? Map.of()
                : Map.copyOf(highlights);
    }

    public boolean hasCorrectAlternative() {
        return correctAlternative != null
                && !correctAlternative.isBlank();
    }

    public boolean hasHighlights() {
        return !highlights.isEmpty();
    }

    public Question withHighlights(
            Map<String, List<String>> newHighlights
    ) {
        return new Question(
                id,
                statement,
                year,
                exam,
                area,
                discipline,
                topic,
                institution,
                alternatives,
                correctAlternative,
                explanation,
                publicationDate,
                newHighlights
        );
    }
}
