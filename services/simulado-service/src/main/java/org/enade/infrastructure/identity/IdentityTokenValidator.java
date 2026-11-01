package org.enade.infrastructure.identity;

import jakarta.enterprise.context.ApplicationScoped;
import org.eclipse.microprofile.jwt.JsonWebToken;

@ApplicationScoped
public class IdentityTokenValidator {

    public String validarUsuarioAutenticado(JsonWebToken token) {
        if (token == null || !token.isValid()) {
            throw new SecurityException("Token de identidade inválido ou expirado.");
        }

        String userId = token.getSubject();

        if (userId == null || userId.isBlank()) {
            throw new SecurityException("Token não possui identificação do usuário.");
        }

        return userId;
    }

    public boolean possuiRole(JsonWebToken token, String role) {
        if (token == null || !token.isValid() || role == null || role.isBlank()) {
            return false;
        }

        return token.getGroups() != null && token.getGroups().contains(role);
    }
}