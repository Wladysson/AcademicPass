package org.enade.selection.application;

import java.util.Objects;
import org.enade.selection.domain.exception.SelectionException;
import org.enade.selection.domain.model.QuestionSelection;
import org.enade.selection.domain.model.SelectedQuestion;
import org.enade.selection.infrastructure.identity.IdentityTokenValidator;
import org.enade.selection.infrastructure.redis.QuestionSelectionRepository;
import org.enade.selection.presentation.dto.QuestionSelectionRequestDto;
import org.enade.selection.presentation.dto.QuestionSelectionResponseDto;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
public class QuestionSelectionUseCase {

    @Inject
    QuestionSelectionRepository questionSelectionRepository;

    @Inject
    IdentityTokenValidator identityTokenValidator;

    public QuestionSelectionResponseDto addQuestion(
            String authorization,
            QuestionSelectionRequestDto request
    ) {
        String userId = authenticatedUserId(authorization);

        if (request == null) {
            throw new SelectionException(
                    "Os dados da questão são obrigatórios."
            );
        }

        String questionId = requireValue(
                request.questionId(),
                "O identificador da questão é obrigatório."
        );

        QuestionSelection selection = questionSelectionRepository
                .findByUserId(userId)
                .orElseGet(() -> QuestionSelection.empty(userId));

        if (selection.containsQuestion(questionId)) {
            throw new SelectionException(
                    "A questão já está presente na seleção."
            );
        }

        SelectedQuestion selectedQuestion = new SelectedQuestion(
                questionId
        );

        QuestionSelection updatedSelection =
                selection.addQuestion(selectedQuestion);

        questionSelectionRepository.save(updatedSelection);

        return QuestionSelectionResponseDto.from(updatedSelection);
    }

    public QuestionSelectionResponseDto getSelection(
            String authorization
    ) {
        String userId = authenticatedUserId(authorization);

        QuestionSelection selection = questionSelectionRepository
                .findByUserId(userId)
                .orElseGet(() -> QuestionSelection.empty(userId));

        return QuestionSelectionResponseDto.from(selection);
    }

    public QuestionSelectionResponseDto removeQuestion(
            String authorization,
            String questionId
    ) {
        String userId = authenticatedUserId(authorization);

        String validatedQuestionId = requireValue(
                questionId,
                "O identificador da questão é obrigatório."
        );

        QuestionSelection selection = questionSelectionRepository
                .findByUserId(userId)
                .orElseThrow(() -> new SelectionException(
                        "Nenhuma seleção foi encontrada para o usuário."
                ));

        if (!selection.containsQuestion(validatedQuestionId)) {
            throw new SelectionException(
                    "A questão não está presente na seleção."
            );
        }

        QuestionSelection updatedSelection =
                selection.removeQuestion(validatedQuestionId);

        questionSelectionRepository.save(updatedSelection);

        return QuestionSelectionResponseDto.from(updatedSelection);
    }

    public void clearSelection(String authorization) {
        String userId = authenticatedUserId(authorization);

        questionSelectionRepository.deleteByUserId(userId);
    }

    private String authenticatedUserId(String authorization) {
        if (authorization == null || authorization.isBlank()) {
            throw new SelectionException(
                    "O cabeçalho Authorization é obrigatório."
            );
        }

        if (!authorization.startsWith("Bearer ")) {
            throw new SelectionException(
                    "O cabeçalho Authorization deve utilizar Bearer Token."
            );
        }

        String token = authorization.substring("Bearer ".length()).trim();

        if (token.isBlank()) {
            throw new SelectionException(
                    "O token de autenticação é obrigatório."
            );
        }

        String userId = identityTokenValidator.validateAndGetUserId(token);

        if (userId == null || userId.isBlank()) {
            throw new SelectionException(
                    "Não foi possível identificar o usuário autenticado."
            );
        }

        return userId;
    }

    private String requireValue(String value, String message) {
        if (value == null || value.isBlank()) {
            throw new SelectionException(message);
        }

        return value.trim();
    }
}