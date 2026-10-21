package org.enade.selection.domain.exception;

public class SelectionException extends RuntimeException {

    public SelectionException(String message) {
        super(message);
    }

    public SelectionException(String message, Throwable cause) {
        super(message, cause);
    }
}
