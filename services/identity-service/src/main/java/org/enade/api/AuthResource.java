package org.enade.identity.api;

import org.enade.identity.application.AuthenticationUseCase;
import org.enade.identity.application.SessionUseCase;
import org.enade.identity.domain.exception.InvalidCredentialsException;
import org.enade.identity.presentation.dto.AuthSessionResponseDto;
import org.enade.identity.presentation.dto.ErrorResponseDto;
import org.enade.identity.presentation.dto.LoginRequestDto;

import jakarta.inject.Inject;
import jakarta.validation.Valid;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/v1/auth")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class AuthResource {

    private static final String AUTHORIZATION_PREFIX = "Bearer ";

    @Inject
    AuthenticationUseCase authenticationUseCase;

    @Inject
    SessionUseCase sessionUseCase;

    @POST
    @Path("/login")
    public Response login(@Valid LoginRequestDto request) {
        if (request == null
                || request.username() == null
                || request.username().isBlank()
                || request.password() == null
                || request.password().isBlank()) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .entity(new ErrorResponseDto(
                            "INVALID_REQUEST",
                            "Usuário e senha são obrigatórios."
                    ))
                    .build();
        }

        try {
            AuthSessionResponseDto session =
                    authenticationUseCase.authenticate(
                            request.username(),
                            request.password()
                    );

            return Response.ok(session).build();
        } catch (InvalidCredentialsException exception) {
            return Response.status(Response.Status.UNAUTHORIZED)
                    .entity(new ErrorResponseDto(
                            "INVALID_CREDENTIALS",
                            "Credenciais inválidas."
                    ))
                    .build();
        }
    }

    @POST
    @Path("/logout")
    public Response logout(
            @HeaderParam("Authorization") String authorizationHeader) {

        if (authorizationHeader == null
                || !authorizationHeader.startsWith(AUTHORIZATION_PREFIX)) {
            return Response.status(Response.Status.UNAUTHORIZED)
                    .entity(new ErrorResponseDto(
                            "UNAUTHORIZED",
                            "Token de sessão ausente ou inválido."
                    ))
                    .build();
        }

        String sessionToken = authorizationHeader
                .substring(AUTHORIZATION_PREFIX.length())
                .trim();

        if (sessionToken.isBlank()) {
            return Response.status(Response.Status.UNAUTHORIZED)
                    .entity(new ErrorResponseDto(
                            "UNAUTHORIZED",
                            "Token de sessão ausente ou inválido."
                    ))
                    .build();
        }

        try {
            sessionUseCase.logout(sessionToken);

            return Response.noContent().build();
        } catch (IllegalArgumentException exception) {
            return Response.status(Response.Status.UNAUTHORIZED)
                    .entity(new ErrorResponseDto(
                            "INVALID_SESSION",
                            "A sessão é inválida ou já expirou."
                    ))
                    .build();
        }
    }
}
