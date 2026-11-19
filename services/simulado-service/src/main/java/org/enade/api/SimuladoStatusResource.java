package org.enade.simulado.api;

import org.enade.simulado.application.SimuladoGenerationUseCase;
import org.enade.simulado.presentation.dto.SimuladoStatusResponseDto;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/v1/simulados/exports")
@Produces(MediaType.APPLICATION_JSON)
public class SimuladoStatusResource {

    @Inject
    SimuladoGenerationUseCase simuladoGenerationUseCase;

    @GET
    @Path("/{id}")
    public Response consultarStatus(@PathParam("id") String id) {
        SimuladoStatusResponseDto response =
                simuladoGenerationUseCase.consultarStatus(id);

        return Response.ok(response).build();
    }
}