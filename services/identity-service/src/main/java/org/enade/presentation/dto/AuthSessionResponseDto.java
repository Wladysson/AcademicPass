package org.enade.identity.presentation.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;

public record AuthSessionResponseDto(
        @JsonProperty("token")
        String token,

        @JsonProperty("username")
        String username,

        @JsonProperty("role")
        String role,

        @JsonProperty("expiresAt")
        Instant expiresAt
) {
}