package org.enade.search.presentation.mapper;

import jakarta.enterprise.context.ApplicationScoped;
import org.enade.search.domain.model.Question;
import org.enade.search.infrastructure.identity.IdentityTokenValidator.ValidatedIdentity;
import org.enade.search.infrastructure.security.RoleAuthorizationPolicy;
import org.enade.search.presentation.dto.QuestionResponseDto;

import java.util.Objects;

@ApplicationScoped
public class QuestionMapper {

    private final RoleAuthorizationPolicy authorizationPolicy;

    public QuestionMapper(RoleAuthorizationPolicy authorizationPolicy) {
        this.authorizationPolicy = authorizationPolicy;
    }

    /**
     * Converte a questão para uma resposta segura, sem gabarito ou explicação.
     */
    public QuestionResponseDto toResponse(Question question) {
        Objects.requireNonNull(question, "A questão não pode ser nula.");

        return QuestionResponseDto.forStudent(
                question.id(),
                question.statement(),
                question.year(),
                question.exam(),
                question.area(),
                question.discipline(),
                question.topic(),
                question.institution(),
                question.alternatives(),
                question.publicationDate(),
                question.highlights()
        );
    }

    /**
     * Converte a questão conforme as permissões do usuário autenticado.
     */
    public QuestionResponseDto toResponse(
            Question question,
            ValidatedIdentity identity
    ) {
        Objects.requireNonNull(question, "A questão não pode ser nula.");

        if (identity == null) {
            return toResponse(question);
        }

        if (authorizationPolicy.canAccessCorrectAnswers(identity)) {
            return new QuestionResponseDto(
                    question.id(),
                    question.statement(),
                    question.year(),
                    question.exam(),
                    question.area(),
                    question.discipline(),
                    question.topic(),
                    question.institution(),
                    question.alternatives(),
                    question.correctAlternative(),
                    question.explanation(),
                    question.publicationDate(),
                    question.highlights()
            );
        }

        return toResponse(question);
    }
}
