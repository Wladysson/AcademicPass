package org.enade.selection.domain.model;

import java.time.Instant;
import java.util.Objects;

public record SelectedQuestion(
        String questionId,
        Instant selectedAt
) {

    public SelectedQuestion {
        if (questionId == null || questionId.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador da questão é obrigatório."
            );
        }

        questionId = questionId.trim();

        selectedAt = Objects.requireNonNullElseGet(
                selectedAt,
                Instant::now
        );
    }

    public SelectedQuestion(String questionId) {
        this(questionId, Instant.now());
    }
}
