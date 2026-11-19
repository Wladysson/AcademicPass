package org.enade.identity.domain.model;

import java.time.Instant;
import java.util.Objects;

public class AuthSession {

    private final String token;
    private final String username;
    private final UserRole role;
    private final Instant createdAt;
    private final Instant expiresAt;
    private final boolean revoked;

    public AuthSession(
            String token,
            String username,
            UserRole role,
            Instant createdAt,
            Instant expiresAt,
            boolean revoked) {

        this.token = requireText(token, "O token da sessão é obrigatório.");
        this.username = requireText(
                username,
                "O nome de usuário é obrigatório."
        );
        this.role = Objects.requireNonNull(
                role,
                "O papel do usuário é obrigatório."
        );
        this.createdAt = Objects.requireNonNull(
                createdAt,
                "A data de criação é obrigatória."
        );
        this.expiresAt = Objects.requireNonNull(
                expiresAt,
                "A data de expiração é obrigatória."
        );

        if (!expiresAt.isAfter(createdAt)) {
            throw new IllegalArgumentException(
                    "A expiração deve ocorrer após a criação da sessão."
            );
        }

        this.revoked = revoked;
    }

    public String getToken() {
        return token;
    }

    public String getUsername() {
        return username;
    }

    public UserRole getRole() {
        return role;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }

    public boolean isRevoked() {
        return revoked;
    }

    public boolean isExpired() {
        return !expiresAt.isAfter(Instant.now());
    }

    public boolean isValid() {
        return !revoked && !isExpired();
    }

    private static String requireText(String value, String message) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(message);
        }

        return value.trim();
    }
}
