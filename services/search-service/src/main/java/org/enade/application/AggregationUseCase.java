package org.enade.search.application;

import jakarta.enterprise.context.ApplicationScoped;

import org.enade.search.domain.exception.SearchException;
import org.enade.search.domain.model.SearchFilter;
import org.enade.search.infrastructure.elasticsearch.QuestionRepository;
import org.enade.search.infrastructure.elasticsearch.AggregationBuilder;

import java.util.Map;

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

    public Map<String, Object> aggregate(SearchFilter filter) {
        if (filter == null) {
            throw new SearchException(
                    "Os filtros para agregação são obrigatórios."
            );
        }

        try {
            Map<String, Object> aggregations =
                    questionRepository.aggregate(filter);

            return aggregationBuilder.buildResponse(aggregations);
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
