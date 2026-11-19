package org.enade.simulado.domain.model;

import java.time.Instant;
import java.util.List;
import java.util.Objects;

public class Simulado {

    private final String id;
    private final String exportId;
    private final String title;
    private final ExportFormat format;
    private final List<SimuladoQuestion> questions;
    private final Instant createdAt;

    public Simulado(
            String id,
            String exportId,
            String title,
            ExportFormat format,
            List<SimuladoQuestion> questions) {

        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador do simulado é obrigatório."
            );
        }

        if (exportId == null || exportId.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador da exportação é obrigatório."
            );
        }

        if (title == null || title.isBlank()) {
            throw new IllegalArgumentException(
                    "O título do simulado é obrigatório."
            );
        }

        if (format == null) {
            throw new IllegalArgumentException(
                    "O formato de exportação é obrigatório."
            );
        }

        if (questions == null || questions.isEmpty()) {
            throw new IllegalArgumentException(
                    "O simulado deve conter pelo menos uma questão."
            );
        }

        this.id = id;
        this.exportId = exportId;
        this.title = title;
        this.format = format;
        this.questions = List.copyOf(questions);
        this.createdAt = Instant.now();
    }

    public String getId() {
        return id;
    }

    public String getExportId() {
        return exportId;
    }

    public String getTitle() {
        return title;
    }

    public ExportFormat getFormat() {
        return format;
    }

    public List<SimuladoQuestion> getQuestions() {
        return questions;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    @Override
    public boolean equals(Object object) {
        if (this == object) {
            return true;
        }

        if (!(object instanceof Simulado other)) {
            return false;
        }

        return Objects.equals(id, other.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }
}