package org.enade.selection.domain.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public final class QuestionSelection {

    private final String userId;
    private final Map<String, SelectedQuestion> questions;

    public QuestionSelection(
            String userId,
            List<SelectedQuestion> questions
    ) {
        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador do usuário é obrigatório."
            );
        }

        this.userId = userId.trim();
        this.questions = new LinkedHashMap<>();

        if (questions != null) {
            for (SelectedQuestion question : questions) {
                Objects.requireNonNull(
                        question,
                        "A questão selecionada não pode ser nula."
                );

                if (this.questions.putIfAbsent(
                        question.questionId(),
                        question
                ) != null) {
                    throw new IllegalArgumentException(
                            "A seleção não pode conter questões duplicadas."
                    );
                }
            }
        }
    }

    public static QuestionSelection empty(String userId) {
        return new QuestionSelection(userId, List.of());
    }

    public String userId() {
        return userId;
    }

    public List<SelectedQuestion> questions() {
        return Collections.unmodifiableList(
                new ArrayList<>(questions.values())
        );
    }

    public int totalQuestions() {
        return questions.size();
    }

    public boolean isEmpty() {
        return questions.isEmpty();
    }

    public boolean containsQuestion(String questionId) {
        if (questionId == null || questionId.isBlank()) {
            return false;
        }

        return questions.containsKey(questionId.trim());
    }

    public QuestionSelection addQuestion(SelectedQuestion question) {
        Objects.requireNonNull(
                question,
                "A questão selecionada não pode ser nula."
        );

        if (containsQuestion(question.questionId())) {
            throw new IllegalArgumentException(
                    "A questão já está presente na seleção."
            );
        }

        Map<String, SelectedQuestion> updatedQuestions =
                new LinkedHashMap<>(questions);

        updatedQuestions.put(question.questionId(), question);

        return new QuestionSelection(
                userId,
                new ArrayList<>(updatedQuestions.values())
        );
    }

    public QuestionSelection removeQuestion(String questionId) {
        if (questionId == null || questionId.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador da questão é obrigatório."
            );
        }

        String normalizedQuestionId = questionId.trim();

        if (!questions.containsKey(normalizedQuestionId)) {
            throw new IllegalArgumentException(
                    "A questão não está presente na seleção."
            );
        }

        Map<String, SelectedQuestion> updatedQuestions =
                new LinkedHashMap<>(questions);

        updatedQuestions.remove(normalizedQuestionId);

        return new QuestionSelection(
                userId,
                new ArrayList<>(updatedQuestions.values())
        );
    }
}
