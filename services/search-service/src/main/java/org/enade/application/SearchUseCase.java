package org.enade.search.application;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.core.Response;

import org.enade.search.domain.exception.SearchException;
import org.enade.search.domain.model.SearchFilter;
import org.enade.search.domain.model.SearchResult;
import org.enade.search.infrastructure.elasticsearch.QuestionRepository;
import org.enade.search.infrastructure.redis.SearchCacheRepository;

@ApplicationScoped
public class SearchUseCase {

    private final QuestionRepository questionRepository;
    private final SearchCacheRepository searchCacheRepository;

    public SearchUseCase(
            QuestionRepository questionRepository,
            SearchCacheRepository searchCacheRepository
    ) {
        this.questionRepository = questionRepository;
        this.searchCacheRepository = searchCacheRepository;
    }

    public SearchResult search(SearchFilter filter) {
        validateFilter(filter);

        try {
            SearchResult cachedResult = searchCacheRepository.find(filter);

            if (cachedResult != null) {
                return cachedResult;
            }

            SearchResult result = questionRepository.search(filter);

            searchCacheRepository.save(filter, result);

            return result;
        } catch (SearchException exception) {
            throw exception;
        } catch (WebApplicationException exception) {
            throw exception;
        } catch (RuntimeException exception) {
            throw new SearchException(
                    "Não foi possível realizar a busca de questões.",
                    exception
            );
        }
    }

    private void validateFilter(SearchFilter filter) {
        if (filter == null) {
            throw new SearchException("Os filtros de busca são obrigatórios.");
        }

        if (filter.page() < 0) {
            throw new SearchException("A página não pode ser negativa.");
        }

        if (filter.pageSize() < 1 || filter.pageSize() > 100) {
            throw new SearchException(
                    "O tamanho da página deve estar entre 1 e 100."
            );
        }
    }
}
