package org.enade.simulado.presentation.dto;

import org.enade.simulado.domain.model.ExportFormat;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;

public class SimuladoExportRequestDto {

    @NotBlank(message = "O título do simulado é obrigatório.")
    @Size(max = 150, message = "O título deve ter no máximo 150 caracteres.")
    private String title;

    @NotNull(message = "O formato da exportação é obrigatório.")
    private ExportFormat format;

    @Size(
            min = 1,
            max = 200,
            message = "A seleção deve conter entre 1 e 200 questões."
    )
    private List<@NotBlank(message = "O identificador da questão não pode ser vazio.")
            String> questionIds;

    public SimuladoExportRequestDto() {
    }

    public SimuladoExportRequestDto(
            String title,
            ExportFormat format,
            List<String> questionIds
    ) {
        this.title = title;
        this.format = format;
        this.questionIds = questionIds;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public ExportFormat getFormat() {
        return format;
    }

    public void setFormat(ExportFormat format) {
        this.format = format;
    }

    public List<String> getQuestionIds() {
        return questionIds;
    }

    public void setQuestionIds(List<String> questionIds) {
        this.questionIds = questionIds;
    }
}