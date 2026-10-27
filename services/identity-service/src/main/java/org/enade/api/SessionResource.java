package org.enade.identity.api;

import org.enade.identity.application.SessionUseCase;
import org.enade.identity.domain.exception.SessionExpiredException;
import org.enade.identity.presentation.dto.AuthSessionResponseDto;
import org.enade.identity.presentation.dto.ErrorResponseDto;

import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/v1/auth/session")
@Produces(MediaType.APPLICATION_JSON)
public class SessionResource {

    private static final String AUTHORIZATION_PREFIX = "Bearer ";

    @Inject
    SessionUseCase sessionUseCase;

    @GET
    public Response getCurrentSession(
            @HeaderParam("Authorization") String authorizationHeader) {

        if (authorizationHeader == null
                || !authorizationHeader.startsWith(AUTHORIZATION_PREFIX)) {
            return unauthorized(
                    "UNAUTHORIZED",
                    "Token de sessão ausente ou inválido."
            );
        }

        String sessionToken = authorizationHeader
                .substring(AUTHORIZATION_PREFIX.length())
                .trim();

        if (sessionToken.isBlank()) {
            return unauthorized(
                    "UNAUTHORIZED",
                    "Token de sessão ausente ou inválido."
            );
        }

        try {
            AuthSessionResponseDto session =
                    sessionUseCase.getCurrentSession(sessionToken);

            if (session == null) {
                return unauthorized(
                        "INVALID_SESSION",
                        "A sessão é inválida ou expirou."
                );
            }

            return Response.ok(session).build();
        } catch (SessionExpiredException exception) {
            return unauthorized(
                    "SESSION_EXPIRED",
                    "A sessão expirou. Faça login novamente."
            );
        } catch (IllegalArgumentException exception) {
            return unauthorized(
                    "INVALID_SESSION",
                    "A sessão é inválida ou expirou."
            );
        }
    }

    private Response unauthorized(String code, String message) {
        return Response.status(Response.Status.UNAUTHORIZED)
                .entity(new ErrorResponseDto(code, message))
                .build();
    }
}
