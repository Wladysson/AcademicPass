package org.enade.simulado.api;

import org.enade.simulado.application.SimuladoExportUseCase;
import org.enade.simulado.presentation.dto.SimuladoExportRequestDto;
import org.enade.simulado.presentation.dto.SimuladoExportResponseDto;
import jakarta.inject.Inject;
import jakarta.validation.Valid;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/v1/simulados")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class SimuladoResource {

    @Inject
    SimuladoExportUseCase simuladoExportUseCase;

    @POST
    @Path("/export")
    public Response exportar(@Valid SimuladoExportRequestDto request) {
        SimuladoExportResponseDto response =
                simuladoExportUseCase.solicitarExportacao(request);

        return Response.accepted(response).build();
    }
}