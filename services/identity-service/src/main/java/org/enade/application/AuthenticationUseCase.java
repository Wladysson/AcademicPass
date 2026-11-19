package org.enade.identity.application;

import org.enade.identity.domain.exception.InvalidCredentialsException;
import org.enade.identity.domain.model.UserAccount;
import org.enade.identity.infrastructure.ldap.LdapAuthenticationRepository;
import org.enade.identity.presentation.dto.AuthSessionResponseDto;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
public class AuthenticationUseCase {

    @Inject
    LdapAuthenticationRepository ldapAuthenticationRepository;
    @Inject
    SessionUseCase sessionUseCase;

    public AuthSessionResponseDto authenticate(
            String username,
            String password) {

        validateCredentials(username, password);

        UserAccount user;

        try {
            user = ldapAuthenticationRepository.authenticate(
                    username.trim(),
                    password
            );
        } catch (InvalidCredentialsException exception) {
            throw exception;
        } catch (RuntimeException exception) {
            throw new IllegalStateException(
                    "Não foi possível concluir a autenticação no LDAP.",
                    exception
            );
        }

        if (user == null) {
            throw new InvalidCredentialsException();
        }

        if (user.getUsername() == null
                || user.getUsername().isBlank()
                || user.getRole() == null) {
            throw new IllegalStateException(
                    "O LDAP retornou dados incompletos para o usuário autenticado."
            );
        }

        return sessionUseCase.createSession(user);
    }

    private void validateCredentials(String username, String password) {
        if (username == null
                || username.isBlank()
                || password == null
                || password.isBlank()) {
            throw new InvalidCredentialsException();
        }
    }
}
