package org.enade.selection.presentation.dto;

import java.time.Instant;
import java.util.List;

import org.enade.selection.domain.model.QuestionSelection;
import org.enade.selection.domain.model.SelectedQuestion;

public record QuestionSelectionResponseDto(
        String userId,
        List<SelectedQuestionResponse> questions,
        int totalQuestions,
        Instant updatedAt
) {

    public QuestionSelectionResponseDto {
        questions = questions == null
                ? List.of()
                : List.copyOf(questions);
    }

    public static QuestionSelectionResponseDto from(
            QuestionSelection selection
    ) {
        if (selection == null) {
            throw new IllegalArgumentException(
                    "A seleção não pode ser nula."
            );
        }

        List<SelectedQuestionResponse> questions =
                selection.questions().stream()
                        .map(SelectedQuestionResponse::from)
                        .toList();

        Instant updatedAt = questions.stream()
                .map(SelectedQuestionResponse::selectedAt)
                .max(Instant::compareTo)
                .orElse(null);

        return new QuestionSelectionResponseDto(
                selection.userId(),
                questions,
                selection.totalQuestions(),
                updatedAt
        );
    }

    public record SelectedQuestionResponse(
            String questionId,
            Instant selectedAt
    ) {

        public static SelectedQuestionResponse from(
                SelectedQuestion question
        ) {
            if (question == null) {
                throw new IllegalArgumentException(
                        "A questão selecionada não pode ser nula."
                );
            }

            return new SelectedQuestionResponse(
                    question.questionId(),
                    question.selectedAt()
            );
        }
    }
}