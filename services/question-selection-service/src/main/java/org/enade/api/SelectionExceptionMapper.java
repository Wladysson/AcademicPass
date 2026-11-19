package org.enade.selection.api;

import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;
import org.enade.selection.domain.exception.SelectionException;

@Provider
public class SelectionExceptionMapper
        implements ExceptionMapper<SelectionException> {

    @Override
    public Response toResponse(SelectionException exception) {
        String message = exception.getMessage();

        boolean authenticationError = message != null
                && (message.contains("Authorization")
                || message.contains("autenticação")
                || message.contains("autenticado"));

        Response.Status status = authenticationError
                ? Response.Status.UNAUTHORIZED
                : Response.Status.BAD_REQUEST;

        return Response.status(status)
                .type(MediaType.APPLICATION_JSON)
                .entity(new ErrorResponse(message))
                .build();
    }

    public record ErrorResponse(String message) {
    }
}