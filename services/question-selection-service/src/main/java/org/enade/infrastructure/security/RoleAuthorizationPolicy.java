package org.enade.selection.infrastructure.security;

import java.util.Collection;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

import org.enade.selection.domain.exception.SelectionException;

import jakarta.enterprise.context.ApplicationScoped;

@ApplicationScoped
public class RoleAuthorizationPolicy {

    private static final Set<String> SELECTION_READ_ROLES = Set.of(
            "STUDENT",
            "TEACHER",
            "ADMIN"
    );

    private static final Set<String> SELECTION_WRITE_ROLES = Set.of(
            "STUDENT",
            "ADMIN"
    );

    private static final Set<String> SELECTION_DELETE_ROLES = Set.of(
            "STUDENT",
            "ADMIN"
    );

    public void requireReadPermission(Collection<String> roles) {
        requireAnyRole(roles, SELECTION_READ_ROLES);
    }

    public void requireWritePermission(Collection<String> roles) {
        requireAnyRole(roles, SELECTION_WRITE_ROLES);
    }

    public void requireDeletePermission(Collection<String> roles) {
        requireAnyRole(roles, SELECTION_DELETE_ROLES);
    }

    public boolean canRead(Collection<String> roles) {
        return hasAnyRole(roles, SELECTION_READ_ROLES);
    }

    public boolean canWrite(Collection<String> roles) {
        return hasAnyRole(roles, SELECTION_WRITE_ROLES);
    }

    public boolean canDelete(Collection<String> roles) {
        return hasAnyRole(roles, SELECTION_DELETE_ROLES);
    }

    private void requireAnyRole(
            Collection<String> roles,
            Set<String> allowedRoles
    ) {
        if (!hasAnyRole(roles, allowedRoles)) {
            throw new SelectionException(
                    "O perfil do usuário não possui permissão para esta operação."
            );
        }
    }

    private boolean hasAnyRole(
            Collection<String> roles,
            Set<String> allowedRoles
    ) {
        if (roles == null || roles.isEmpty()) {
            return false;
        }

        Set<String> normalizedRoles = roles.stream()
                .filter(role -> role != null && !role.isBlank())
                .map(role -> role.trim().toUpperCase(Locale.ROOT))
                .collect(Collectors.toSet());

        return normalizedRoles.stream().anyMatch(allowedRoles::contains);
    }
}