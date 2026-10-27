package org.enade.search.presentation.dto;

import java.time.Instant;
import java.util.Map;

public record ErrorResponseDto(
        Instant timestamp,
        int status,
        String error,
        String message,
        String path,
        Map<String, String> details
) {

    public ErrorResponseDto {
        timestamp = timestamp == null ? Instant.now() : timestamp;
        error = error == null || error.isBlank() ? "Erro" : error;
        message = message == null || message.isBlank()
                ? "Não foi possível processar a solicitação."
                : message;
        path = path == null ? "" : path;
        details = details == null ? Map.of() : Map.copyOf(details);
    }

    public static ErrorResponseDto of(
            int status,
            String error,
            String message,
            String path
    ) {
        return new ErrorResponseDto(
                Instant.now(),
                status,
                error,
                message,
                path,
                Map.of()
        );
    }

    public static ErrorResponseDto withDetails(
            int status,
            String error,
            String message,
            String path,
            Map<String, String> details
    ) {
        return new ErrorResponseDto(
                Instant.now(),
                status,
                error,
                message,
                path,
                details
        );
    }
}
