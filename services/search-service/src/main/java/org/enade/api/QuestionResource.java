package org.enade.search.api;

import org.enade.search.application.SearchUseCase;
import org.enade.search.domain.model.SearchFilter;
import org.enade.search.domain.model.SearchResult;
import org.enade.search.presentation.dto.QuestionResponseDto;
import org.enade.search.presentation.dto.SearchRequestDto;
import org.enade.search.presentation.mapper.QuestionMapper;

import jakarta.validation.Valid;
import jakarta.ws.rs.BeanParam;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.List;

@Path("/api/v1/questions")
@Produces(MediaType.APPLICATION_JSON)
public class QuestionResource {

    private final SearchUseCase searchUseCase;
    private final QuestionMapper questionMapper;

    public QuestionResource(
            SearchUseCase searchUseCase,
            QuestionMapper questionMapper
    ) {
        this.searchUseCase = searchUseCase;
        this.questionMapper = questionMapper;
    }

    @GET
    public Response search(@Valid @BeanParam SearchRequestDto request) {
        SearchFilter filter = SearchFilter.from(request);

        SearchResult result = searchUseCase.search(filter);

        List<QuestionResponseDto> questions = result.questions()
                .stream()
                .map(questionMapper::toResponse)
                .toList();

        return Response.ok(questions)
                .header("X-Total-Count", result.totalElements())
                .header("X-Page", result.page())
                .header("X-Page-Size", result.pageSize())
                .build();
    }
}
