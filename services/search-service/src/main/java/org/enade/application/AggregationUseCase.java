package org.enade.search.application;

import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.enterprise.context.ApplicationScoped;

import org.enade.search.domain.exception.SearchException;
import org.enade.search.domain.model.SearchFilter;
import org.enade.search.infrastructure.elasticsearch.QuestionRepository;
import org.enade.search.infrastructure.elasticsearch.AggregationBuilder;

@ApplicationScoped
public class AggregationUseCase {

    private final QuestionRepository questionRepository;
    private final AggregationBuilder aggregationBuilder;

    public AggregationUseCase(
            QuestionRepository questionRepository,
            AggregationBuilder aggregationBuilder
    ) {
        this.questionRepository = questionRepository;
        this.aggregationBuilder = aggregationBuilder;
    }

    public ObjectNode aggregate(SearchFilter filter) {
        if (filter == null) {
            throw new SearchException(
                    "Os filtros para agregação são obrigatórios."
            );
        }

        try {
            return aggregationBuilder.buildResponse(
                    questionRepository.aggregate(filter)
            );
        } catch (SearchException exception) {
            throw exception;
        } catch (RuntimeException exception) {
            throw new SearchException(
                    "Não foi possível gerar as agregações das questões.",
                    exception
            );
        }
    }
}