package org.enade.identity.presentation.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonProperty.Access;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record LoginRequestDto(

        @JsonProperty("username")
        @NotBlank(message = "O nome de usuário é obrigatório.")
        @Size(max = 128, message = "O nome de usuário excede o tamanho permitido.")
        String username,

        @JsonProperty(value = "password", access = Access.WRITE_ONLY)
        @NotBlank(message = "A senha é obrigatória.")
        @Size(max = 1024, message = "A senha excede o tamanho permitido.")
        String password

) {

    @Override
    public String toString() {
        return "LoginRequestDto[username="
                + username
                + ", password=[REDACTED]]";
    }
}
