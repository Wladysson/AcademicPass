package org.enade.selection.api;

import org.enade.selection.application.QuestionSelectionUseCase;
import org.enade.selection.presentation.dto.QuestionSelectionRequestDto;
import org.enade.selection.presentation.dto.QuestionSelectionResponseDto;

import jakarta.inject.Inject;
import jakarta.validation.Valid;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.DELETE;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.PATCH;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/v1/selections")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class QuestionSelectionResource {

    @Inject
    QuestionSelectionUseCase questionSelectionUseCase;

    @POST
    public Response addQuestion(
            @HeaderParam("Authorization") String authorization,
            @Valid QuestionSelectionRequestDto request
    ) {
        QuestionSelectionResponseDto response =
                questionSelectionUseCase.addQuestion(
                        authorization,
                        request
                );

        return Response.status(Response.Status.CREATED)
                .entity(response)
                .build();
    }

    @GET
    public Response getSelection(
            @HeaderParam("Authorization") String authorization
    ) {
        QuestionSelectionResponseDto response =
                questionSelectionUseCase.getSelection(authorization);

        return Response.ok(response).build();
    }

    @PATCH
    @Path("/{questionId}")
    public Response removeQuestion(
            @HeaderParam("Authorization") String authorization,
            @PathParam("questionId") String questionId
    ) {
        QuestionSelectionResponseDto response =
                questionSelectionUseCase.removeQuestion(
                        authorization,
                        questionId
                );

        return Response.ok(response).build();
    }

    @DELETE
    public Response clearSelection(
            @HeaderParam("Authorization") String authorization
    ) {
        questionSelectionUseCase.clearSelection(authorization);

        return Response.noContent().build();
    }
}