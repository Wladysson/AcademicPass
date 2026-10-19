package org.enade.identity.domain.exception;

public class InvalidCredentialsException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public InvalidCredentialsException() {
        super("Credenciais inválidas.");
    }

    public InvalidCredentialsException(Throwable cause) {
        super("Credenciais inválidas.", cause);
    }
}
