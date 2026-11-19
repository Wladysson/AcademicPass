package org.enade.simulado.domain.exception;

public class SimuladoExportException extends RuntimeException {

    public SimuladoExportException(String message) {
        super(message);
    }

    public SimuladoExportException(String message, Throwable cause) {
        super(message, cause);
    }
}