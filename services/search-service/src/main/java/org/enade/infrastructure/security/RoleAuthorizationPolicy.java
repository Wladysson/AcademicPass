package org.enade.search.infrastructure.security;

import jakarta.enterprise.context.ApplicationScoped;
import org.enade.search.domain.exception.SearchException;
import org.enade.search.infrastructure.identity.IdentityTokenValidator.ValidatedIdentity;
import java.util.Locale;
import java.util.Set;

@ApplicationScoped
public class RoleAuthorizationPolicy {

    private static final String STUDENT = "STUDENT";
    private static final String PROFESSOR = "PROFESSOR";

    private static final Set<String> ALLOWED_ROLES = Set.of(
            STUDENT,
            PROFESSOR
    );

    public void authorizeSearch(ValidatedIdentity identity) {
        requireAllowedRole(identity);
    }

    public void authorizeAggregation(ValidatedIdentity identity) {
        requireAllowedRole(identity);
    }

    public void authorizeCorrectAnswerAccess(ValidatedIdentity identity) {
        requireAllowedRole(identity);

        if (!PROFESSOR.equals(normalizeRole(identity.role()))) {
            throw new SearchException(
                    "Apenas usuários com perfil PROFESSOR podem acessar os gabaritos."
            );
        }
    }

    public boolean canAccessCorrectAnswers(ValidatedIdentity identity) {
        return identity != null
                && identity.role() != null
                && PROFESSOR.equals(normalizeRole(identity.role()));
    }

    private void requireAllowedRole(ValidatedIdentity identity) {
        if (identity == null) {
            throw new SearchException(
                    "A identidade autenticada é obrigatória para autorizar a operação."
            );
        }

        String role = normalizeRole(identity.role());

        if (role == null || !ALLOWED_ROLES.contains(role)) {
            throw new SearchException(
                    "O perfil informado não possui permissão para acessar este recurso."
            );
        }
    }

    private String normalizeRole(String role) {
        if (role == null || role.isBlank()) {
            return null;
        }

        return role.trim().toUpperCase(Locale.ROOT);
    }
}
