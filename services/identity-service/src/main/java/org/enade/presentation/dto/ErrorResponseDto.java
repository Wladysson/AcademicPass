package org.enade.identity.presentation.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ErrorResponseDto(
        @JsonProperty("code")
        String code,

        @JsonProperty("message")
        String message
) {
}