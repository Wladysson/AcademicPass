package org.enade.identity.domain.exception;

public class SessionExpiredException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public SessionExpiredException() {
        super("A sessão expirou ou não é mais válida.");
    }

    public SessionExpiredException(Throwable cause) {
        super("A sessão expirou ou não é mais válida.", cause);
    }
}
