package org.enade.selection.presentation.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record QuestionSelectionRequestDto(

        @NotBlank(message = "O identificador da questão é obrigatório.")
        @Size(max = 128, message = "O identificador da questão deve ter no máximo 128 caracteres.")
        String questionId

) {
}