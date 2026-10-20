package org.enade.search.api;

import org.enade.search.application.AggregationUseCase;
import org.enade.search.domain.model.SearchFilter;
import org.enade.search.presentation.dto.SearchRequestDto;

import jakarta.validation.Valid;
import jakarta.ws.rs.BeanParam;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/v1/aggregations")
@Produces(MediaType.APPLICATION_JSON)
public class AggregationResource {

    private final AggregationUseCase aggregationUseCase;

    public AggregationResource(AggregationUseCase aggregationUseCase) {
        this.aggregationUseCase = aggregationUseCase;
    }

    @GET
    public Response aggregate(@Valid @BeanParam SearchRequestDto request) {
        SearchFilter filter = SearchFilter.from(request);

        return Response.ok(aggregationUseCase.aggregate(filter))
                .build();
    }
}
