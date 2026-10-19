package org.enade.identity.domain.model;

import java.util.Objects;
import java.util.UUID;

public class UserAccount {

    private final UUID id;
    private final String username;
    private final String displayName;
    private final String email;
    private final UserRole role;
    private final boolean active;

    public UserAccount(
            UUID id,
            String username,
            String displayName,
            String email,
            UserRole role,
            boolean active) {

        this.id = Objects.requireNonNull(id, "O identificador é obrigatório.");
        this.username = requireText(username, "O nome de usuário é obrigatório.");
        this.displayName = requireText(
                displayName,
                "O nome de exibição é obrigatório."
        );
        this.email = requireText(email, "O e-mail é obrigatório.");
        this.role = Objects.requireNonNull(role, "O papel é obrigatório.");
        this.active = active;
    }

    public UUID getId() {
        return id;
    }

    public String getUsername() {
        return username;
    }

    public String getDisplayName() {
        return displayName;
    }

    public String getEmail() {
        return email;
    }

    public UserRole getRole() {
        return role;
    }

    public boolean isActive() {
        return active;
    }

    public boolean canAuthenticate() {
        return active;
    }

    private static String requireText(String value, String message) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(message);
        }

        return value.trim();
    }
}
